
import pathlib
from unittest.mock import patch

import voyageai
from django.conf import settings
from django.test import TestCase

from .models import KnowledgeDocument
from .tools import TOOL_SCHEMAS, dispatch
from .tools import knowledge as knowledge_tool
from .management.commands.ingest_knowledge import (
    KNOWLEDGE_DIR,
    MAX_CHUNK_TOKENS,
    chunk_markdown,
    count_tokens,
    split_documents,
    split_table,
)

# Corpus chunking and retrieval tests. 
# # No Voyage call is ever made.

class SplitDocumentsTestCase(TestCase):
    def test_one_file_can_hold_several_documents(self):
        """Maison_Roast_Story_Telling.md is five documents, each with an H1."""
        text = '# Story\nonce upon a time\n\n# Refund Policy\nfourteen days\n'
        documents = split_documents(text)

        self.assertEqual([title for title, _ in documents],
                         ['Story', 'Refund Policy'])

    def test_a_refund_chunk_is_not_labelled_with_the_story(self):
        text = '# Story\nfounded in 1974\n\n# Refund Policy\n## Timeline\nfourteen days\n'
        chunks = chunk_markdown(text, 'mixed.md')

        refund = [c for c in chunks if 'fourteen days' in c['content']][0]
        self.assertEqual(refund['title'], 'Refund Policy')
        self.assertIn('Refund Policy', refund['content'])
        self.assertNotIn('Story', refund['content'])


class ChunkMarkdownTestCase(TestCase):
    def test_every_chunk_names_itself(self):
        """Retrieval returns one chunk alone, so it has to carry its titles."""
        text = '# Handbook\n## Panna Cotta\nSimmer the cream.\n'
        chunk = chunk_markdown(text, 'h.md')[0]

        self.assertIn('Handbook', chunk['content'])
        self.assertIn('Panna Cotta', chunk['content'])
        self.assertIn('Simmer the cream.', chunk['content'])

    def test_chunk_index_is_contiguous_per_source(self):
        text = '# A\n## One\nx\n\n## Two\ny\n\n# B\n## Three\nz\n'
        chunks = chunk_markdown(text, 'a.md')

        self.assertEqual([c['chunk_index'] for c in chunks], [0, 1, 2])

    def test_a_long_section_is_split_with_overlap(self):
        paragraph = ' '.join(['word'] * 200)
        text = f'# T\n## Long\n{paragraph}\n\n{paragraph}\n\n{paragraph}\n'
        chunks = chunk_markdown(text, 'long.md')

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(count_tokens(chunk['content']),
                                 MAX_CHUNK_TOKENS * 1.1)


class SplitTableTestCase(TestCase):
    """The per-product allergen table is one block with no blank line to split
    on, and a piece without its header is unreadable."""

    def _table(self, rows):
        header = '| Product | Contains Dairy |'
        separator = '|---|---|'
        body = '\n'.join(f'| item{i} | Yes |' for i in range(rows))
        return f'{header}\n{separator}\n{body}'

    def test_every_piece_keeps_the_header(self):
        pieces = split_table(self._table(300), None)

        self.assertGreater(len(pieces), 1)
        for piece in pieces:
            self.assertIn('Contains Dairy', piece)
            self.assertIn('|---|', piece)

    def test_no_row_is_lost(self):
        pieces = split_table(self._table(300), None)
        joined = '\n'.join(pieces)

        for i in range(300):
            self.assertIn(f'| item{i} |', joined)

    def test_a_short_table_is_left_alone(self):
        self.assertEqual(len(split_table(self._table(3), None)), 1)


class RealCorpusTestCase(TestCase):
    """Guards the actual documents in basil/knowledge/, not a fixture."""

    def setUp(self):
        self.paths = sorted(KNOWLEDGE_DIR.glob('*.md'))

    def test_the_corpus_is_present(self):
        self.assertTrue(self.paths, 'basil/knowledge/ has no markdown')

    def test_no_chunk_is_far_over_budget(self):
        for path in self.paths:
            for chunk in chunk_markdown(path.read_text(encoding='utf-8'),
                                        path.name):
                self.assertLessEqual(
                    count_tokens(chunk['content']), MAX_CHUNK_TOKENS * 1.1,
                    f"{path.name} #{chunk['chunk_index']} is oversized")

    def test_the_allergen_table_survives_chunking(self):
        """A customer asking about one product must still reach its row."""
        path = KNOWLEDGE_DIR / 'Maison_Roast_Story_Telling.md'
        if not path.exists():
            self.skipTest('story file renamed')

        chunks = chunk_markdown(path.read_text(encoding='utf-8'), path.name)
        rows = [c for c in chunks if 'Contains Gluten' in c['content']]

        self.assertTrue(rows)
        for chunk in rows:
            self.assertIn('| Product |', chunk['content'])
        self.assertTrue(any('cannoli' in c['content'] for c in rows))


class SearchKnowledgeBaseToolTestCase(TestCase):
    """MASTER_SPEC §4.8. The Voyage client is mocked -- no test may call it."""

    def setUp(self):
        KnowledgeDocument.objects.create(
            source='policies.md', chunk_index=0, content='Refunds take 7 days.',
            embedding=[0.1] * settings.VOYAGE_DIM,
            metadata={'heading': 'Refunds'},
        )

    def _hits(self):
        return [{'text': 'Refunds take 7 days.', 'source': 'policies.md',
                 'heading': 'Refunds', 'similarity': 0.81}]

    def test_it_is_a_registered_tool(self):
        names = [t['name'] for t in TOOL_SCHEMAS]
        self.assertIn('search_knowledge_base', names)
        self.assertEqual(len(names), 9)

    def test_it_returns_passages(self):
        with patch.object(knowledge_tool, 'search', return_value=self._hits()):
            result = dispatch('search_knowledge_base', {'query': 'refunds?'})

        self.assertEqual(result['results'][0]['source'], 'policies.md')
        self.assertEqual(result['results'][0]['similarity'], 0.81)

    def test_an_empty_query_is_refused_without_calling_voyage(self):
        with patch.object(knowledge_tool, 'search') as search:
            result = dispatch('search_knowledge_base', {'query': '   '})

        self.assertIn('error', result)
        search.assert_not_called()

    def test_an_empty_corpus_says_so(self):
        KnowledgeDocument.objects.all().delete()
        with patch.object(knowledge_tool, 'search') as search:
            result = dispatch('search_knowledge_base', {'query': 'refunds?'})

        self.assertIn('ingest_knowledge', result['error'])
        search.assert_not_called()

    def test_a_rate_limit_does_not_read_as_no_such_policy(self):
        """Voyage's free tier allows 3 requests a minute. Basil must not tell
        the customer the shop has no refund policy because of a 429."""
        error = voyageai.error.RateLimitError('slow down')
        with patch.object(knowledge_tool, 'search', side_effect=error):
            result = dispatch('search_knowledge_base', {'query': 'refunds?'})

        self.assertIn('rate limited', result['error'])

    def test_a_crash_never_reaches_the_agent(self):
        with patch.object(knowledge_tool, 'search', side_effect=RuntimeError('boom')):
            result = dispatch('search_knowledge_base', {'query': 'refunds?'})

        self.assertIn('error', result)

    def test_no_results_is_not_an_error(self):
        with patch.object(knowledge_tool, 'search', return_value=[]):
            result = dispatch('search_knowledge_base', {'query': 'unicorns'})

        self.assertEqual(result['results'], [])
        self.assertIn('note', result)
