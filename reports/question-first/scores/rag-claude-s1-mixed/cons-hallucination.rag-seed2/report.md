# Evaluation of run (baselines only) on rag-claude-s1-ec928480

Question: Do the authors' conclusions about hallucination agree with their reported results?
Question id: cons-hallucination (kind consistency)
Levels: complex, contradictory, distributed, explicit, paraphrased

## C. Consistency

| system       | metric             | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   | agreeing_precision   | agreeing_recall   | disagreeing_precision   | disagreeing_recall   |
|--------------|--------------------|------------------|----------------------|----------------|----------------------|---------------------------------|----------------------|-------------------|-------------------------|----------------------|
| rag-baseline | hallucination_rate | 9                | 0.111                | 0.111          | 9                    | 0.111                           | 1.000                | 0.125             | n/a                     | 0.000                |

Over the studies truth can decide (its question metric is the claim metric and `agrees` is not null: duplicates and papers with missing data or no claim drop out): a decidable paper left out or called undetermined is wrong; completeness is the share given true or false; the agreeing and disagreeing sets are over the same studies. `*_all_papers`: the old number over every study truth lists, `agrees` null right when truth's is null too.

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system       | metric             | interval           | method   | n   |
|--------------|--------------------|--------------------|----------|-----|
| rag-baseline | per_study_accuracy | 0.111 [0.00, 0.56] | BCa      | 9   |
