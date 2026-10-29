# Evaluation of run (baselines only) on rag-tpl-hard-24ab4663

Question: Do the authors' conclusions about hallucination agree with their reported results?
Question id: cons-hallucination (kind consistency)
Levels: complex

## C. Consistency

| system       | metric             | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   | agreeing_precision   | agreeing_recall   | disagreeing_precision   | disagreeing_recall   |
|--------------|--------------------|------------------|----------------------|----------------|----------------------|---------------------------------|----------------------|-------------------|-------------------------|----------------------|
| rag-baseline | hallucination_rate | 55               | 0.055                | 0.055          | 62                   | 0.048                           | 1.000                | 0.055             | n/a                     | -                    |

Over the studies truth can decide (its question metric is the claim metric and `agrees` is not null: duplicates and papers with missing data or no claim drop out): a decidable paper left out or called undetermined is wrong; completeness is the share given true or false; the agreeing and disagreeing sets are over the same studies. `*_all_papers`: the old number over every study truth lists, `agrees` null right when truth's is null too.

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system       | metric             | interval           | method   | n   |
|--------------|--------------------|--------------------|----------|-----|
| rag-baseline | per_study_accuracy | 0.055 [0.02, 0.15] | BCa      | 55  |
