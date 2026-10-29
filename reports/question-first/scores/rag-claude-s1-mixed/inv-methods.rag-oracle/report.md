# Evaluation of run (baselines only) on rag-claude-s1-ec928480

Question: Which methods or system variants do the papers compare?
Question id: inv-methods (kind inventory)
Levels: complex, contradictory, distributed, explicit, paraphrased

## C. Inventory

| system              | target    | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|---------------------|-----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| rag-oracle-passages | condition | 8         | 14                 | 2         | 0.250       | 0.143    | 0.182 | 0.117             | 0.115          | 0.116      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- rag-oracle-passages: false positives Chain-of-Thought (CoT) Prompting, Fine-Tuned Models, Parametric-Only / Closed-Book / No-Retrieval Baseline, Query Rewriting/Reformulation, Retrieval-Augmented Generation (RAG) / Retrieve-Then-Read, Self-Consistency / Voting; missed RAG pipeline, chain-of-thought prompting, closed-book model, fine-tuned model, no-retrieval baseline, parametric-only model, query-rewriting variant, retrieval-augmented generator, retrieval-augmented model, retrieve-then-read model, self-consistency decoding, vanilla LLM

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system              | metric    | interval           | method   | n   |
|---------------------|-----------|--------------------|----------|-----|
| rag-oracle-passages | precision | 0.250 [0.00, 0.67] | BCa      | 20  |
| rag-oracle-passages | recall    | 0.143 [0.00, 0.43] | BCa      | 20  |
| rag-oracle-passages | f1        | 0.182 [0.00, 0.46] | BCa      | 20  |
