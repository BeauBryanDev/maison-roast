
import pathlib
import re
import time

import voyageai
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from basil.models import KnowledgeDocument

# Chunk basil/knowledge/*.md, embed with Voyage, write KnowledgeDocument.

KNOWLEDGE_DIR = pathlib.Path(settings.BASE_DIR) / 'basil' / 'knowledge'

MAX_CHUNK_TOKENS = 512
OVERLAP_TOKENS = 64

# A Voyage account with no payment method is capped at 3 requests and 10K
# tokens per minute. 8 chunks is roughly 3K tokens, so this paces under both.
BATCH_SIZE = 8
BATCH_DELAY_SECONDS = 21
MAX_RETRIES = 5

# Voyage's tokenizer is a local HF download. Without it, estimate: English
# prose runs about 1.35 tokens per whitespace word.
WORDS_TO_TOKENS = 1.35

_tokenizer_failed = False


def count_tokens(text, client=None):
    
    global _tokenizer_failed
    
    if client is not None and not _tokenizer_failed:
        
        try:
            return len(client.tokenize([text], model=settings.VOYAGE_MODEL)[0])
        
        except Exception:
            
            _tokenizer_failed = True  # offline or no tokenizer; estimate instead
            
    return int(len(text.split()) * WORDS_TO_TOKENS)


def split_documents(text):
    """
    Split a markdown file into individual documents based on H1 headings.
    Maison_Roast_Story_Telling.md is five: the story, refund, delivery,
    allergens and the social description. Treating the file as one document
    would label a refund answer with the story's title.
    """
    parts = re.split(r'(?m)^#\s+(.+)$', text)
    preamble = parts[0].strip()

    documents = []
    
    if preamble:
        documents.append(('', preamble))
        
    for i in range(1, len(parts), 2):
        
        body = parts[i + 1] if i + 1 < len(parts) else ''
        documents.append((parts[i].strip(), body))
        
    return documents


def split_sections(body):
    """H2 sections within one document, keeping the heading with its text."""
    parts = re.split(r'(?m)^##\s+(.+)$', body)
    sections = []

    preamble = parts[0].strip()
    
    if preamble:
        
        sections.append(('', preamble))
        
    for i in range(1, len(parts), 2):
        
        content = (parts[i + 1] if i + 1 < len(parts) else '').strip()
        
        if content:
            
            sections.append((parts[i].strip(), content))
            
    return sections


def split_table(block, client):
    """Split a long markdown table by rows, repeating the header each time.

    The per-product allergen table is 42 rows in one block with no blank line
    to break on. Without the repeated header a piece reads 'Yes | Yes | No'
    with nothing saying which columns those are -- which is the one place in
    this corpus where a misread answer is a safety problem.
    """
    lines = [line for line in block.splitlines() if line.strip()]
    
    if len(lines) < 3 or not lines[1].strip().startswith('|'):
        return [block]

    header, separator, rows = lines[0], lines[1], lines[2:]
    header_tokens = count_tokens(f'{header}\n{separator}', client)

    pieces = []
    current = []
    current_tokens = header_tokens

    for row in rows:
        
        row_tokens = count_tokens(row, client)
        
        if current and current_tokens + row_tokens > MAX_CHUNK_TOKENS:
            
            pieces.append('\n'.join([header, separator, *current]))
            current = []
            current_tokens = header_tokens
            continue
        
        current.append(row)
        current_tokens += row_tokens

    if current:
        pieces.append('\n'.join([header, separator, *current]))
        
    return pieces


def split_oversized(content, client):
    """Break a too-long section into overlapping pieces.

    Splits on blank lines so a markdown table or a numbered step is not cut in
    half. A single paragraph longer than the budget is left whole: chopping it
    mid-sentence costs more meaning than the overflow does.
    """
    if count_tokens(content, client) <= MAX_CHUNK_TOKENS:
        return [content]

    blocks = []
    
    for block in re.split(r'\n\s*\n', content):
        
        if not block.strip():
            continue
        
        if block.lstrip().startswith('|') and count_tokens(block, client) > MAX_CHUNK_TOKENS:
            blocks.extend(split_table(block, client))
            
        else:
            blocks.append(block)

    pieces = []
    current = []
    current_tokens = 0

    for block in blocks:
        
        block_tokens = count_tokens(block, client)
        
        if current and current_tokens + block_tokens > MAX_CHUNK_TOKENS:
            
            pieces.append('\n\n'.join(current))
 
            overlap = []
            
            overlap_tokens = 0
            
            for previous in reversed(current):
                
                previous_tokens = count_tokens(previous, client)
                
                if overlap_tokens + previous_tokens > OVERLAP_TOKENS:
                    break
                
                overlap.insert(0, previous)
                overlap_tokens += previous_tokens
                
            current = overlap
            
            current_tokens = overlap_tokens

        current.append(block)
        current_tokens += block_tokens

    if current:
        pieces.append('\n\n'.join(current))
        
    return pieces


def chunk_markdown(text, source, client=None):
    """Chunk one file into self-contained, embeddable pieces."""
    chunks = []

    for title, body in split_documents(text):
        for heading, content in split_sections(body):
            for piece in split_oversized(content, client):
                # Every chunk carries its own titles. Retrieval returns the
                # chunk alone, so a piece that only says "Yes | Yes | No" has
                # to name what it is about.
                header = ' — '.join(part for part in (title, heading) if part)
                body_text = f'{header}\n\n{piece}' if header else piece
                chunks.append({
                    'source': source,
                    'title': title,
                    'heading': heading,
                    'content': body_text,
                })

    for index, chunk in enumerate(chunks):
        
        chunk['chunk_index'] = index
        
    return chunks


def embed_with_retry(client, texts, on_wait=None):
    """Embed one batch, backing off when the account's rate limit is hit."""
    for attempt in range(MAX_RETRIES):
        try:
            return client.embed(texts, model=settings.VOYAGE_MODEL,
                                input_type='document')
        except voyageai.error.RateLimitError:
            if attempt == MAX_RETRIES - 1:
                raise
            
            wait = BATCH_DELAY_SECONDS * (attempt + 2)
            
            if on_wait:
                on_wait(wait)
                
            time.sleep(wait)
            
    return None


class Command(BaseCommand):
    help = 'Chunk basil/knowledge/*.md and embed into KnowledgeDocument.'

    def add_arguments(self, parser):
        
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Chunk and report only. No API call, nothing written.')
        parser.add_argument(
            '--wipe', action='store_true',
            help='Delete every existing row first, including orphans.')

    def handle(self, *args, **options):
        
        if not KNOWLEDGE_DIR.exists():
            
            self.stderr.write(self.style.ERROR(f'No such dir: {KNOWLEDGE_DIR}'))
            return

        paths = sorted(KNOWLEDGE_DIR.glob('**/*.md'))
        
        if not paths:
            self.stderr.write(self.style.ERROR(f'No .md under {KNOWLEDGE_DIR}'))
            return

        client = None
        
        if not options['dry_run']:
            
            if not settings.VOYAGE_API_KEY:
                
                self.stderr.write(self.style.ERROR('VOYAGE_API_KEY is not set.'))
                return
            
            client = voyageai.Client(api_key=settings.VOYAGE_API_KEY)

        chunks = []
        
        for path in paths:
            
            source = str(path.relative_to(KNOWLEDGE_DIR))
            
            found = chunk_markdown(path.read_text(encoding='utf-8'), source, client)
            
            chunks.extend(found)

            longest = max((count_tokens(c['content'], client) for c in found), default=0)
            self.stdout.write(f'{source}: {len(found)} chunks, longest {longest} tokens')

        self.stdout.write(self.style.SUCCESS(f'Total chunks: {len(chunks)}'))

        if options['dry_run']:
            
            for chunk in chunks:
                
                preview = chunk['content'][:100].replace('\n', ' ')
                self.stdout.write(f"  [{chunk['source']} #{chunk['chunk_index']}] {preview}…")
                
            self.stdout.write(self.style.WARNING('Dry run: nothing embedded or written.'))
            
            return

        if options['wipe']:
            
            deleted, _ = KnowledgeDocument.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Wiped {deleted} rows.'))

        embedded = 0
        
        for start in range(0, len(chunks), BATCH_SIZE):
            
            if start:
                time.sleep(BATCH_DELAY_SECONDS)

            batch = chunks[start:start + BATCH_SIZE]
            result = embed_with_retry(
                client, [c['content'] for c in batch],
                on_wait=lambda s: self.stdout.write(
                    self.style.WARNING(f'rate limited, waiting {s}s')
                    ),
            )

            with transaction.atomic():
                
                for chunk, embedding in zip(batch, result.embeddings):
                    
                    KnowledgeDocument.objects.update_or_create(
                        source=chunk['source'],
                        chunk_index=chunk['chunk_index'],
                        defaults={
                            'content': chunk['content'],
                            'embedding': embedding,
                            'metadata': {'title': chunk['title'],
                                         'heading': chunk['heading']},
                        },
                    )
                    
            embedded += len(batch)
            
            self.stdout.write(f'embedded {embedded}/{len(chunks)}')

        # A file that shrank leaves rows beyond its new last index behind.
        # They would still be retrievable, quoting text no document contains.
        stale = 0
        for source in {c['source'] for c in chunks}:
            
            highest = max(c['chunk_index'] for c in chunks if c['source'] == source)
            
            removed, _ = KnowledgeDocument.objects.filter(
                                                    source=source, 
                                                    chunk_index__gt=highest
                                                    ).delete()
            
            stale += removed
            
        if stale:
            
            self.stdout.write(self.style.WARNING(f'Removed {stale} stale chunks.'))

        self.stdout.write(self.style.SUCCESS(
            
            f'{KnowledgeDocument.objects.count()} chunks in the corpus.'))
