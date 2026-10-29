# Evaluation of run (baselines only) on rag-claude-s1-ec928480

Question: Which datasets do the papers evaluate on?
Question id: inv-datasets (kind inventory)
Levels: complex, contradictory, distributed, explicit, paraphrased

## C. Inventory

| system       | target   | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|--------------|----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| rag-baseline | dataset  | 5         | 9                  | 5         | 1.000       | 0.556    | 0.714 | 1.000             | 0.292          | 0.452      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- rag-baseline: false positives none; missed BioClaimQA, OpenFactQA, PopCultureQA, SciFactBench

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system       | metric    | interval           | method     | n   |
|--------------|-----------|--------------------|------------|-----|
| rag-baseline | precision | 1.000 [1.00, 1.00] | percentile | 9   |
| rag-baseline | recall    | 0.556 [0.22, 0.89] | BCa        | 9   |
| rag-baseline | f1        | 0.714 [0.36, 0.94] | BCa        | 9   |
