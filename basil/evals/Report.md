# Basil RAG Eval — Report

**Date:** 2026-10-29
**Agent:** Basil, Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
**Retrieval:** Voyage `voyage-4-lite` (1024 dims), pgvector HNSW cosine, top_k = 4
**Judge:** Claude Sonnet 5 (`claude-sonnet-5`)
**Golden set:** 24 questions, `basil/evals/rag_golden.json`
**Runner:** `python manage.py eval_rag --voyage-interval 21 --judge`

## Headline

Basil's knowledge base is in very good shape. Retrieval finds the right passage
for 22 of 23 answerable questions, and it is usually the first result. When Basil
searches, he answers accurately and in his own voice, including the
safety-critical allergy questions.

| Metric | Result |
|---|---|
| Retrieval hit@4 | **0.96** |
| Retrieval MRR | **0.91** |
| Retrieval recall | **0.91** |
| Judge: pass | **17 / 24**, plus 4 partial |
| Judge pass rate when Basil searched the knowledge base | **13 / 18** |
| Tool or API errors | **0 / 24** |

## The corpus

Four markdown files in `basil/knowledge/`: the brand story, refund and delivery
policies, the allergen reference and coffee knowledge (all in
`Maison_Roast_Story_Telling.md`), plus `Classic_Cakes.md`, `Cook_Handbook.md` and
`Cheese.md`. Ingested as 93 chunks.

The golden set covers every file: refund policy (5), brand story (4), delivery
(3), allergens (3), coffee knowledge (3), recipes (3), cheese (2), and one
question the documents cannot answer.

## Retrieval

- **The right passage came first for 20 of 23 questions.** Hits scored 0.50–0.65
  cosine similarity on most questions.
- **The allergen table works as designed.** It is split into pieces with the
  header repeated in each one, and the retrieved piece held the exact product
  row asked about: `carrot_cake`, `chocolate_mousse`, `tiramisu`. This was
  checked against the database, not inferred from headings.
- **Cross-lingual retrieval works.** The Spanish refund question (q19) found the
  English "Change of Mind or Wrong Order" section at rank 1.
- **Nothing in the documents scored low.** The wedding-catering question (q20)
  topped out at 0.26 similarity, against a lowest in-scope top score of 0.379.
  That gap is a promising basis for a similarity floor later.
- The coffee sections, though stored under the wrong H1 title, still ranked
  first. The H2 heading on every chunk carries them.

## Answers

When Basil reaches for the knowledge base, the answers are accurate, warm and
grounded:

- **Refunds and delivery:** exact windows and figures. 14 days, 24 hours for
  damage, 7 business days to process, the $3.00 + $0.50/km fee worked out as
  $6.00 for 6 km, and the dispute email quoted correctly.
- **Allergens, the questions that matter most:** the severe peanut allergy
  question (q13) passed. Basil did not call the tiramisu safe, named the
  cross-contact risk, and sent the customer to a staff member. The gluten-free
  question (q12) passed with the shared-kitchen caveat in place.
- **Coffee and recipes:** brewing temperature, light against dark roast,
  tiramisu chilling time and beignet frying temperature were all correct. He did
  not mix up the beignet and cannoli frying temperatures.
- **Spanish:** asked in Spanish, he answered in Spanish, with the correct
  48-hour policy.
- **Not inventing a policy:** asked about wedding catering (q20), he said the
  knowledge base had nothing on it and suggested contacting the shop.
- **Persona:** every answer stayed in character: short, friendly, no markdown
  tables pasted through, no "as an AI".

## Room to grow

- **Searching on every topic.** Basil reliably searches for policies, allergens
  and coffee. For cheese (q21, q22), the shop's music (q24) and its atmosphere
  (q03), he answered from his persona instead of searching. The answers were
  there in the documents; the tool description simply does not mention those
  topics yet. Broadening it is the single biggest improvement available.
- **Staying with what was retrieved.** Twice he added a friendly line the
  documents do not support: "not set up for catering" (q20), and the weather
  delay explanation (q09).
- **One retrieval near-miss (q04).** The refund-window question retrieved a
  sibling section that also states the 14 days, so the answer was right but
  left out the "unopened packaging" condition.

## Notes on the judge

Sonnet 5 graded strictly, and three of its verdicts are harsher than Basil
deserved:

- **q05:** marked fail for mentioning 14 days. That window is in the documents;
  the golden question's forbidden list was too broad.
- **q14:** marked partial for details (Andes, volcanic soil) it called
  unverified. They are in the corpus; the judge only sees the reference answer,
  not what Basil retrieved.
- **q09:** marked fail, though the free-delivery part was right; partial fits
  better.

Read with those adjusted, Basil's pass rate is around **17–18 of 24**.

## Prompt caching, observed

The usage log confirms caching is active. Within a turn, the second request reads
the conversation from cache (`cache_read=4105`) instead of paying for it again.
Every eval question starts in a fresh session, so this run shows only cache
writes on first requests. In real multi-turn conversations those writes are read
back on the next turn.

## Reproducing

```bash
python manage.py eval_rag --voyage-interval 21            # retrieval only, Voyage
python manage.py eval_rag --voyage-interval 21 --judge    # + Basil answers + judge
python manage.py eval_rag --only q13,q20 --judge          # a subset
```

Results land in `basil/evals/results/` (gitignored). Query embeddings are cached in
`basil/evals/.embed_cache.json`, so retrieval re-runs make no Voyage calls.
