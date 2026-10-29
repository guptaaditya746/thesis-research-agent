# Evaluation of run (baselines only) on rag-claude-s1-ec928480

Question: Which methods or system variants do the papers compare?
Question id: inv-methods (kind inventory)
Levels: complex, contradictory, distributed, explicit, paraphrased

## C. Inventory

| system       | target    | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|--------------|-----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| rag-baseline | condition | 8         | 14                 | 4         | 0.500       | 0.286    | 0.364 | 0.271             | 0.213          | 0.239      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- rag-baseline: false positives Parametric-Only / Closed-Book / Vanilla LLM, Question Reformulation, Retrieval-Augmented Generation (RAG) / Retrieve-Then-Read, Self-Consistency Decoding / Voting; missed RAG pipeline, closed-book model, no-retrieval baseline, parametric-only model, query-rewriting variant, retrieval-augmented generator, retrieval-augmented model, retrieve-then-read model, self-consistency decoding, vanilla LLM

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system       | metric    | interval           | method   | n   |
|--------------|-----------|--------------------|----------|-----|
| rag-baseline | precision | 0.500 [0.17, 0.86] | BCa      | 18  |
| rag-baseline | recall    | 0.286 [0.08, 0.57] | BCa      | 18  |
| rag-baseline | f1        | 0.364 [0.11, 0.62] | BCa      | 18  |
