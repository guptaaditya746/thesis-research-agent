# Evaluation of run (baselines only) on rag-claude-s1-ec928480

Question: Which evaluation metrics do the papers report?
Question id: inv-metrics (kind inventory)
Levels: complex, contradictory, distributed, explicit, paraphrased

## C. Inventory

| system       | target   | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|--------------|----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| rag-baseline | metric   | 8         | 7                  | 6         | 0.750       | 0.857    | 0.800 | 0.800             | 0.296          | 0.432      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- rag-baseline: false positives metric for unsupported statements, share of answers containing unsupported statements; missed hallucination frequency

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system       | metric    | interval           | method   | n   |
|--------------|-----------|--------------------|----------|-----|
| rag-baseline | precision | 0.750 [0.38, 1.00] | BCa      | 9   |
| rag-baseline | recall    | 0.857 [0.39, 1.00] | BCa      | 9   |
| rag-baseline | f1        | 0.800 [0.50, 0.94] | BCa      | 9   |
