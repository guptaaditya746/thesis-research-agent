# Evaluation of run rag-claude-s1-mixed on rag-claude-s1-ec928480

Question: Do the authors' conclusions about hallucination agree with their reported results?
Question id: cons-hallucination (kind consistency)
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 34      | 38      | 34        | 1.000       | 0.895    | 0.944 | 1.000           |
| all             | paraphrased   | 22      | 34      | 20        | 0.909       | 0.588    | 0.714 | 1.000           |
| all             | distributed   | 26      | 26      | 26        | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | complex       | 72      | 74      | 72        | 1.000       | 0.973    | 0.986 | 1.000           |
| all             | contradictory | 39      | 38      | 36        | 0.923       | 0.947    | 0.935 | 1.000           |
| all             | all           | 193     | 210     | 188       | 0.974       | 0.895    | 0.933 | 1.000           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased   | 13      | 13      | 11        | 0.846       | 0.846    | 0.846 | 1.000           |
| condition       | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 15      | 15      | 13        | 0.867       | 0.867    | 0.867 | 1.000           |
| condition       | all           | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           |
| measurement     | explicit      | 12      | 15      | 12        | 1.000       | 0.800    | 0.889 | 1.000           |
| measurement     | paraphrased   | 4       | 13      | 4         | 1.000       | 0.308    | 0.471 | 1.000           |
| measurement     | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | complex       | 48      | 50      | 48        | 1.000       | 0.960    | 0.980 | 1.000           |
| measurement     | contradictory | 16      | 15      | 15        | 0.938       | 1.000    | 0.968 | 1.000           |
| measurement     | all           | 89      | 102     | 88        | 0.989       | 0.863    | 0.921 | 1.000           |
| metric          | explicit      | 3       | 4       | 3         | 1.000       | 0.750    | 0.857 | 1.000           |
| metric          | paraphrased   | 1       | 4       | 1         | 1.000       | 0.250    | 0.400 | 1.000           |
| metric          | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           |

Facts no item matched: 22; items matching no fact: 5.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Claim to result

| claims   | claim_correct   | claim_accuracy   |
|----------|-----------------|------------------|
| 20       | 20              | 1.000            |

Author-claim items whose claim span overlaps a true claim, and the share with its direction.

Measurement linkage (no pair check: a consistency answer names no measurement pair):

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|
| explicit      | 12                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          |
| paraphrased   | 4                      | 0.500                  | 0.500                     | 1.000             | 0.500             | 1.000          |
| distributed   | 9                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          |
| complex       | 48                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          |
| contradictory | 15                     | 0.867                  | 0.867                     | 1.000             | 0.867             | 1.000          |
| all           | 88                     | 0.955                  | 0.955                     | 1.000             | 0.955             | 1.000          |

## C. Consistency

| system          | metric             | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   | agreeing_precision   | agreeing_recall   | disagreeing_precision   | disagreeing_recall   |
|-----------------|--------------------|------------------|----------------------|----------------|----------------------|---------------------------------|----------------------|-------------------|-------------------------|----------------------|
| evidence-engine | hallucination_rate | 9                | 0.556                | 0.556          | 9                    | 0.556                           | 1.000                | 0.500             | 1.000                   | 1.000                |

Over the studies truth can decide (its question metric is the claim metric and `agrees` is not null: duplicates and papers with missing data or no claim drop out): a decidable paper left out or called undetermined is wrong; completeness is the share given true or false; the agreeing and disagreeing sets are over the same studies. `*_all_papers`: the old number over every study truth lists, `agrees` null right when truth's is null too.

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.934 [0.83, 0.98] | BCa      |
| metric          | 0.920 [0.79, 0.98] | BCa      |
| measurement     | 0.921 [0.82, 0.97] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.933 [0.88, 0.97] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric             | interval           | method   | n   |
|-----------------|--------------------|--------------------|----------|-----|
| evidence-engine | per_study_accuracy | 0.556 [0.22, 0.89] | BCa      | 9   |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 88           | 88       | 1.000    |
| all             | paraphrased   | 73           | 73       | 1.000    |
| all             | distributed   | 75           | 75       | 1.000    |
| all             | complex       | 159          | 159      | 1.000    |
| all             | contradictory | 88           | 88       | 1.000    |
| all             | all           | 483          | 483      | 1.000    |
| author_claim    | explicit      | 8            | 8        | 1.000    |
| author_claim    | paraphrased   | 8            | 8        | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
| condition       | explicit      | 34           | 34       | 1.000    |
| condition       | paraphrased   | 30           | 30       | 1.000    |
| condition       | distributed   | 32           | 32       | 1.000    |
| condition       | complex       | 46           | 46       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 182          | 182      | 1.000    |
| measurement     | explicit      | 15           | 15       | 1.000    |
| measurement     | paraphrased   | 13           | 13       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 50           | 50       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 102          | 102      | 1.000    |
| metric          | explicit      | 31           | 31       | 1.000    |
| metric          | paraphrased   | 22           | 22       | 1.000    |
| metric          | distributed   | 26           | 26       | 1.000    |
| metric          | complex       | 55           | 55       | 1.000    |
| metric          | contradictory | 25           | 25       | 1.000    |
| metric          | all           | 159          | 159      | 1.000    |

## Cascade contribution

| extractor                       | found   | found_matched   | only   | only_matched   |
|---------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#0bbf299aba25 | 20      | 20              | 20     | 20             |
| llm_condition@1#45b3761c700e    | 61      | 57              | 61     | 57             |
| llm_measurement@1#02bd5a7ab104  | 89      | 88              | 89     | 88             |
| llm_metric@1#41e1e53a1fc4       | 23      | 23              | 23     | 23             |

Facts no extractor found: condition 4, measurement 14, metric 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                       | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|---------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#0bbf299aba25 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| llm_author_claim@1#0bbf299aba25 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| llm_condition@1#45b3761c700e    | condition       | all     | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           | -                      | 61     | 57             |
| llm_condition@1#45b3761c700e    | all             | all     | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           | -                      | 61     | 57             |
| llm_measurement@1#02bd5a7ab104  | measurement     | all     | 89      | 102     | 88        | 0.989       | 0.863    | 0.921 | 1.000           | 0.955                  | 89     | 88             |
| llm_measurement@1#02bd5a7ab104  | all             | all     | 89      | 102     | 88        | 0.989       | 0.863    | 0.921 | 1.000           | -                      | 89     | 88             |
| llm_metric@1#41e1e53a1fc4       | metric          | all     | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           | -                      | 23     | 23             |
| llm_metric@1#41e1e53a1fc4       | all             | all     | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           | -                      | 23     | 23             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                       | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|---------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#0bbf299aba25 | 20      | 20            | 21101          | 2369            | 0.135     |
| llm_condition@1#45b3761c700e    | 20      | 25            | 27916          | 4758            | 0.139     |
| llm_measurement@1#02bd5a7ab104  | 20      | 40            | 55862          | 17077           | 0.149     |
| llm_metric@1#41e1e53a1fc4       | 20      | 24            | 27035          | 2372            | 0.135     |
| llm_screen@1#41b0d6e6793f       | 20      | 20            | 18681          | 1757            | 0.141     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 100     | 5.000       |
| input_tokens     | 150595  | 7529.750    |
| made_model_calls | 129     | 6.450       |
| model_calls      | 129     | 6.450       |
| output_tokens    | 28333   | 1416.650    |
| seconds          | 309.509 | 15.475      |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 5.000          |
| model_calls   | 6.450          |
| input_tokens  | 7529.750       |
| output_tokens | 1416.650       |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 5           |
| exhausted       | 15          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
