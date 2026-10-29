# Evaluation of run (baselines only) on rag-claude-s1-ec928480

Question: Which evaluation metrics do the papers report?
Question id: inv-metrics (kind inventory)
Levels: complex, contradictory, distributed, explicit, paraphrased

## C. Inventory

| system       | target   | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|--------------|----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| rag-baseline | metric   | 5         | 7                  | 5         | 1.000       | 0.714    | 0.833 | 0.200             | 0.741          | 0.315      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- rag-baseline: false positives none; missed fact-level accuracy, hallucination frequency

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system       | metric    | interval           | method   | n   |
|--------------|-----------|--------------------|----------|-----|
| rag-baseline | precision | 1.000 [n/a]        | -        | 7   |
| rag-baseline | recall    | 0.714 [0.29, 1.00] | BCa      | 7   |
| rag-baseline | f1        | 0.833 [0.44, 1.00] | BCa      | 7   |
