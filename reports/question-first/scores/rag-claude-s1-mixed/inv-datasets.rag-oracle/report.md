# Evaluation of run (baselines only) on rag-claude-s1-ec928480

Question: Which datasets do the papers evaluate on?
Question id: inv-datasets (kind inventory)
Levels: complex, contradictory, distributed, explicit, paraphrased

## C. Inventory

| system              | target   | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|---------------------|----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| rag-oracle-passages | dataset  | 9         | 9                  | 9         | 1.000       | 1.000    | 1.000 | 1.000             | 0.875          | 0.933      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- rag-oracle-passages: false positives none; missed none

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system              | metric    | interval    | method   | n   |
|---------------------|-----------|-------------|----------|-----|
| rag-oracle-passages | precision | 1.000 [n/a] | -        | 9   |
| rag-oracle-passages | recall    | 1.000 [n/a] | -        | 9   |
| rag-oracle-passages | f1        | 1.000 [n/a] | -        | 9   |
