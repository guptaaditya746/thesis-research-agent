# Evaluation of run (baselines only) on rag-tpl-hard-24ab4663

Question: Which method achieves the highest factual accuracy within each paper?
Question id: best-accuracy (kind best)
Levels: complex

## C. Best

| system       | winner   | expected_winner   | winner_correct   | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   |
|--------------|----------|-------------------|------------------|------------------|----------------------|----------------|----------------------|---------------------------------|
| rag-baseline | -        | rag               | no               | 40               | 0.000                | 0.000          | 100                  | 0.600                           |

`winner_correct`: the winner (or the tie) is truth's; per-study accuracy of the paper's winner and tie over the studies truth can decide (a winner or a tie): a decidable paper left out or given neither is wrong, a paper with no comparison is not counted; completeness is the share of them given a winner or tie. `*_all_papers`: the old number over truth's studies not screened out and not a duplicate, where silence on a no-comparison paper is right (the engine does not leave duplicates out, which shows in its wins).

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system       | metric             | interval    | method   | n   |
|--------------|--------------------|-------------|----------|-----|
| rag-baseline | per_study_accuracy | 0.000 [n/a] | -        | 40  |
