import datetime
import json
import pathlib
import time
from unittest.mock import patch

import voyageai
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from basil import agent
from basil.models import ChatSession, KnowledgeDocument
from basil.rag import retrieve

# RAG eval over basil/evals/rag_golden.json.
#   default    retrieval only: Voyage calls, no Anthropic spend
#   --answers  also runs Basil end to end, one rolled-back session per question
#   --judge    also grades each answer with a model judge

EVALS_DIR = pathlib.Path(settings.BASE_DIR) / 'basil' / 'evals'
GOLDEN_PATH = EVALS_DIR / 'rag_golden.json'
RESULTS_DIR = EVALS_DIR / 'results'
CACHE_PATH = EVALS_DIR / '.embed_cache.json'

# Free Voyage tier: 3 requests a minute. 21s stays under it with margin.
DEFAULT_VOYAGE_INTERVAL = 21
MAX_RETRIES = 5
DEFAULT_JUDGE_MODEL = 'claude-sonnet-5'

JUDGE_SCHEMA = {
    'type': 'object',
    'properties': {
        'verdict': {'type': 'string', 'enum': ['pass', 'partial', 'fail']},
        'reason': {'type': 'string'},
    },
    'required': ['verdict', 'reason'],
    'additionalProperties': False,
}

JUDGE_PROMPT = """You are grading an answer from Basil, the chat assistant of a coffee shop, against a reference.

Question: {question}
Reference answer: {expected_answer}
Facts the answer must convey: {must_include}
Claims the answer must not make: {must_not_include}
Grader notes: {notes}

Basil's answer:
{answer}

Grade on meaning, not wording. pass: conveys the reference facts and makes none of the forbidden claims. partial: correct but missing something important. fail: wrong, invented, or makes a forbidden claim. On allergy questions, any suggestion that an item is safe for the customer is a fail. For an unanswerable question, pass only if Basil says he could not find it rather than inventing a policy."""


class PacedEmbedder:
    """Stands in for retrieve.embed_query: cached by text, paced, retried on 429.

    In --answers mode the knowledge tool turns a 429 into "ask again later",
    which would score as a bad answer rather than as a rate limit.
    """

    def __init__(self, original, interval, cache_path):
        self.original = original
        self.interval = interval
        self.cache_path = cache_path
        self.cache = {}
        if cache_path and cache_path.exists():
            self.cache = json.loads(cache_path.read_text())
        self.last_call = 0.0
        self.calls = 0
        self.hits = 0

    def __call__(self, text):
        key = f'{settings.VOYAGE_MODEL}:{text}'
        if key in self.cache:
            self.hits += 1
            return self.cache[key]

        for attempt in range(MAX_RETRIES):
            wait = self.last_call + self.interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last_call = time.monotonic()
            try:
                vector = self.original(text)
                break
            except voyageai.error.RateLimitError:
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(self.interval * (attempt + 1))

        self.calls += 1
        self.cache[key] = vector
        if self.cache_path:
            self.cache_path.write_text(json.dumps(self.cache))
        return vector


def _matches(result, chunk):
    # search() returns source and heading, not the H1 title. The pair is unique
    # in this corpus; the only empty heading in a file is the Delivery preamble.
    return result['source'] == chunk['source'] and result['heading'] == chunk['heading']


def score_retrieval(question, results):
    expected = question['expected_chunks']
    ranks = [i + 1 for i, r in enumerate(results)
             if any(_matches(r, c) for c in expected)]
    found = [c for c in expected if any(_matches(r, c) for r in results)]

    return {
        'hit': bool(ranks) if expected else None,
        'first_rank': ranks[0] if ranks else None,
        'reciprocal_rank': 1 / ranks[0] if ranks else 0.0,
        'recall': len(found) / len(expected) if expected else None,
        'top_similarity': results[0]['similarity'] if results else None,
        'retrieved': [{'source': r['source'], 'heading': r['heading'],
                       'similarity': r['similarity']} for r in results],
    }


def run_basil(question):
    """Basil's reply to one question, in a fresh anonymous session that is
    rolled back afterwards so the eval leaves no chat rows behind."""
    reply, tools, errors = [], [], []

    with transaction.atomic():
        session = ChatSession.objects.create(session_key='rag-eval')
        for event, data in agent.run_turn(session, question['question']):
            if event == 'token':
                reply.append(data['text'])
            elif event == 'tool_start':
                tools.append(data['name'])
            elif event == 'error':
                errors.append(data['message'])
        transaction.set_rollback(True)

    return ''.join(reply), tools, errors


def check_phrases(answer, question):
    """Strict substring checks. The judge reads meaning; this does not."""
    text = answer.casefold()
    return {
        'missing': [p for p in question['must_include'] if p.casefold() not in text],
        'forbidden': [p for p in question['must_not_include'] if p.casefold() in text],
    }


def judge(answer, question, model):
    prompt = JUDGE_PROMPT.format(
        question=question['question'],
        expected_answer=question['expected_answer'],
        must_include=', '.join(question['must_include']) or '(none)',
        must_not_include=', '.join(question['must_not_include']) or '(none)',
        notes=question.get('notes', '') or '(none)',
        answer=answer or '(empty)',
    )
    response = agent.get_client().messages.create(
        model=model,
        max_tokens=12000,
        messages=[{'role': 'user', 'content': prompt}],
        output_config={'format': {'type': 'json_schema', 'schema': JUDGE_SCHEMA}},
    )
    if response.stop_reason == 'refusal':
        return {'verdict': 'error', 'reason': 'judge refused'}

    text = next(b.text for b in response.content if b.type == 'text')
    return json.loads(text)


class Command(BaseCommand):
    help = 'Evaluate Basil RAG against basil/evals/rag_golden.json.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--answers', action='store_true',
            help='Also run Basil end to end (spends Anthropic credits).')
        parser.add_argument(
            '--judge', action='store_true',
            help='Grade answers with a model judge. Implies --answers.')
        parser.add_argument(
            '--judge-model', default=DEFAULT_JUDGE_MODEL,
            help=f'Judge model, default {DEFAULT_JUDGE_MODEL}.')
        parser.add_argument(
            '--only', default='',
            help='Comma-separated question ids, e.g. q01,q13.')
        parser.add_argument(
            '--top-k', type=int, default=retrieve.DEFAULT_TOP_K,
            help=f'Chunks retrieved per question, default {retrieve.DEFAULT_TOP_K}.')
        parser.add_argument(
            '--voyage-interval', type=float, default=DEFAULT_VOYAGE_INTERVAL,
            help=f'Minimum seconds between Voyage calls, default {DEFAULT_VOYAGE_INTERVAL}.')
        parser.add_argument(
            '--no-cache', action='store_true',
            help='Do not read or write the local embedding cache.')

    def handle(self, *args, **options):
        answers = options['answers'] or options['judge']

        if not settings.VOYAGE_API_KEY:
            raise CommandError('VOYAGE_API_KEY is not set.')
        if answers and not settings.BASIL_API_KEY:
            raise CommandError('BASIL_API_KEY is not set.')
        if not KnowledgeDocument.objects.exists():
            raise CommandError('The knowledge base is empty. Run ingest_knowledge.')

        questions = json.loads(GOLDEN_PATH.read_text())['questions']
        if options['only']:
            wanted = {q.strip() for q in options['only'].split(',')}
            questions = [q for q in questions if q['id'] in wanted]
        if not questions:
            raise CommandError('No questions selected.')

        embedder = PacedEmbedder(
            retrieve.embed_query,
            options['voyage_interval'],
            None if options['no_cache'] else CACHE_PATH,
        )
        mode = 'retrieval + answers' if answers else 'retrieval only'
        if options['judge']:
            mode += f' + judge ({options["judge_model"]})'
        self.stdout.write(f'{len(questions)} questions, {mode}, '
                          f'top_k={options["top_k"]}, '
                          f'Voyage interval {options["voyage_interval"]}s')

        rows = []
        with patch.object(retrieve, 'embed_query', embedder):
            for question in questions:
                rows.append(self.evaluate(question, answers, options))

        self.summarise(rows, embedder, answers, options['judge'])

        RESULTS_DIR.mkdir(exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        path = RESULTS_DIR / f'rag_{stamp}.json'
        path.write_text(json.dumps({
            'mode': mode,
            'top_k': options['top_k'],
            'llm_model': settings.BASIL_LLM_MODEL if answers else None,
            'voyage_model': settings.VOYAGE_MODEL,
            'results': rows,
        }, indent=2, ensure_ascii=False))
        self.stdout.write(self.style.SUCCESS(f'Results written to {path}'))

    def evaluate(self, question, answers, options):
        row = {'id': question['id'], 'category': question['category'],
               'question': question['question']}

        results = retrieve.search(question['question'], options['top_k'])
        row['retrieval'] = score_retrieval(question, results)

        line = f"{question['id']} {question['category']:<17}"
        r = row['retrieval']
        if r['hit'] is None:
            line += f" out-of-scope top_sim={r['top_similarity']}"
        else:
            line += (f" hit={'Y' if r['hit'] else 'N'} rank={r['first_rank'] or '-'}"
                     f" recall={r['recall']:.2f} top_sim={r['top_similarity']}")

        if answers:
            answer, tools, errors = run_basil(question)
            row['answer'] = answer
            row['tools'] = tools
            row['errors'] = errors
            row['used_knowledge_base'] = 'search_knowledge_base' in tools
            row['phrases'] = check_phrases(answer, question)
            line += (f" kb={'Y' if row['used_knowledge_base'] else 'N'}"
                     f" missing={len(row['phrases']['missing'])}"
                     f" forbidden={len(row['phrases']['forbidden'])}")

            if options['judge']:
                row['judge'] = judge(answer, question, options['judge_model'])
                line += f" judge={row['judge']['verdict']}"

        self.stdout.write(line)
        return row

    def summarise(self, rows, embedder, answers, judged):
        scored = [r for r in rows if r['retrieval']['hit'] is not None]
        if scored:
            n = len(scored)
            hit_rate = sum(r['retrieval']['hit'] for r in scored) / n
            mrr = sum(r['retrieval']['reciprocal_rank'] for r in scored) / n
            recall = sum(r['retrieval']['recall'] for r in scored) / n
            lowest = min(r['retrieval']['top_similarity'] for r in scored)
            self.stdout.write(self.style.SUCCESS(
                f'Retrieval: hit@k {hit_rate:.2f}  MRR {mrr:.2f}  '
                f'recall {recall:.2f}  lowest in-scope top_sim {lowest}'))

        # Compared with the lowest in-scope score, this shows whether a
        # similarity floor could separate unanswerable questions.
        for r in rows:
            if r['retrieval']['hit'] is None:
                self.stdout.write(f"Out of scope {r['id']}: top_sim "
                                  f"{r['retrieval']['top_similarity']}")

        if answers:
            n = len(rows)
            used = sum(r['used_knowledge_base'] for r in rows)
            clean = sum(not r['phrases']['missing'] and not r['phrases']['forbidden']
                        for r in rows)
            errored = sum(bool(r['errors']) for r in rows)
            self.stdout.write(self.style.SUCCESS(
                f'Answers: knowledge base used {used}/{n}  '
                f'phrase checks clean {clean}/{n}  errors {errored}/{n}'))

        if judged:
            verdicts = [r['judge']['verdict'] for r in rows]
            self.stdout.write(self.style.SUCCESS(
                'Judge: ' + '  '.join(f'{v} {verdicts.count(v)}'
                                      for v in ('pass', 'partial', 'fail', 'error'))))

        self.stdout.write(f'Voyage: {embedder.calls} calls, {embedder.hits} cache hits')






