# Evaluation of run rag-claude-s1-mixed on rag-claude-s1-ec928480

Question: Do the authors' conclusions about factual accuracy agree with their reported results?
Question id: cons-accuracy (kind consistency)
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 32      | 38      | 27        | 0.844       | 0.711    | 0.771 | 0.963           |
| all             | paraphrased   | 40      | 34      | 21        | 0.525       | 0.618    | 0.568 | 0.905           |
| all             | distributed   | 36      | 26      | 20        | 0.556       | 0.769    | 0.645 | 1.000           |
| all             | complex       | 94      | 74      | 70        | 0.745       | 0.946    | 0.833 | 1.000           |
| all             | contradictory | 39      | 38      | 28        | 0.718       | 0.737    | 0.727 | 0.964           |
| all             | all           | 241     | 210     | 166       | 0.689       | 0.790    | 0.736 | 0.976           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 15      | 15      | 12        | 0.800       | 0.800    | 0.800 | 0.917           |
| condition       | paraphrased   | 30      | 13      | 11        | 0.367       | 0.846    | 0.512 | 0.909           |
| condition       | distributed   | 17      | 9       | 8         | 0.471       | 0.889    | 0.615 | 1.000           |
| condition       | complex       | 23      | 9       | 9         | 0.391       | 1.000    | 0.562 | 1.000           |
| condition       | contradictory | 17      | 15      | 10        | 0.588       | 0.667    | 0.625 | 0.900           |
| condition       | all           | 102     | 61      | 50        | 0.490       | 0.820    | 0.613 | 0.940           |
| measurement     | explicit      | 8       | 15      | 7         | 0.875       | 0.467    | 0.609 | 1.000           |
| measurement     | paraphrased   | 4       | 13      | 4         | 1.000       | 0.308    | 0.471 | 1.000           |
| measurement     | distributed   | 4       | 9       | 4         | 1.000       | 0.444    | 0.615 | 1.000           |
| measurement     | complex       | 56      | 50      | 46        | 0.821       | 0.920    | 0.868 | 1.000           |
| measurement     | contradictory | 13      | 15      | 10        | 0.769       | 0.667    | 0.714 | 1.000           |
| measurement     | all           | 85      | 102     | 71        | 0.835       | 0.696    | 0.759 | 1.000           |
| metric          | explicit      | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | paraphrased   | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 0.500           |
| metric          | distributed   | 11      | 4       | 4         | 0.364       | 1.000    | 0.533 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | all           | 34      | 27      | 25        | 0.735       | 0.926    | 0.820 | 0.960           |

Facts no item matched: 44; items matching no fact: 75.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Claim to result

| claims   | claim_correct   | claim_accuracy   |
|----------|-----------------|------------------|
| 20       | 20              | 1.000            |

Author-claim items whose claim span overlaps a true claim, and the share with its direction.

Measurement linkage (no pair check: a consistency answer names no measurement pair):

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|
| explicit      | 7                      | 0.571                  | 1.000                     | 0.571             | 0.857             | 0.571          |
| paraphrased   | 4                      | 1.000                  | 1.000                     | 1.000             | 0.750             | 1.000          |
| distributed   | 4                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          |
| complex       | 46                     | 0.804                  | 0.804                     | 1.000             | 0.804             | 1.000          |
| contradictory | 10                     | 0.800                  | 1.000                     | 0.800             | 1.000             | 0.800          |
| all           | 71                     | 0.803                  | 0.873                     | 0.930             | 0.845             | 0.930          |

## C. Consistency

| system          | metric           | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   | agreeing_precision   | agreeing_recall   | disagreeing_precision   | disagreeing_recall   |
|-----------------|------------------|------------------|----------------------|----------------|----------------------|---------------------------------|----------------------|-------------------|-------------------------|----------------------|
| evidence-engine | factual_accuracy | 11               | 0.909                | 0.909          | 11                   | 0.909                           | 1.000                | 0.875             | 1.000                   | 1.000                |
| rag-baseline    | factual_accuracy | 11               | 0.182                | 0.273          | 11                   | 0.182                           | 0.667                | 0.250             | n/a                     | 0.000                |
| agent-baseline  | factual_accuracy | 11               | 0.909                | 1.000          | 11                   | 0.909                           | 0.889                | 1.000             | 1.000                   | 0.667                |

Over the studies truth can decide (its question metric is the claim metric and `agrees` is not null: duplicates and papers with missing data or no claim drop out): a decidable paper left out or called undetermined is wrong; completeness is the share given true or false; the agreeing and disagreeing sets are over the same studies. `*_all_papers`: the old number over every study truth lists, `agrees` null right when truth's is null too.

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.613 [0.55, 0.70] | BCa      |
| metric          | 0.820 [0.67, 0.93] | BCa      |
| measurement     | 0.759 [0.64, 0.85] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.736 [0.66, 0.80] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric             | interval           | method   | n   |
|-----------------|--------------------|--------------------|----------|-----|
| evidence-engine | per_study_accuracy | 0.909 [0.59, 1.00] | BCa      | 11  |
| rag-baseline    | per_study_accuracy | 0.182 [0.00, 0.55] | BCa      | 11  |
| agent-baseline  | per_study_accuracy | 0.909 [0.61, 1.00] | BCa      | 11  |

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

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| abbrev_condition@1#eafcbe39d1a0   | 2       | 2               | 0      | 0              |
| abbrev_metric@1#dac5a8a5c84b      | 2       | 2               | 0      | 0              |
| gliner_condition@1#52e6222ffa49   | 62      | 12              | 58     | 8              |
| gliner_metric@1#0a7a21786921      | 13      | 5               | 8      | 0              |
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 25      | 24              | 20     | 19             |
| llm_measurement@1#02bd5a7ab104    | 38      | 29              | 14     | 11             |
| llm_metric@1#41e1e53a1fc4         | 6       | 6               | 2      | 2              |
| number_measurement@1#a78269e0513d | 40      | 34              | 16     | 16             |
| regex_author_claim@2#c58240a3a7a4 | 20      | 20              | 20     | 20             |
| regex_condition@2#207f8f280e4a    | 23      | 22              | 18     | 17             |
| regex_measurement@2#a65f61f0d966  | 31      | 26              | 31     | 26             |
| regex_metric@2#a5a76405f5d5       | 24      | 23              | 19     | 18             |

Facts no extractor found: condition 11, measurement 31, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_condition@1#eafcbe39d1a0   | condition       | all     | 2       | 36      | 2         | 1.000       | 0.056    | 0.105 | 1.000           | -                      | 0      | 0              |
| abbrev_condition@1#eafcbe39d1a0   | all             | all     | 2       | 36      | 2         | 1.000       | 0.056    | 0.105 | 1.000           | -                      | 0      | 0              |
| abbrev_metric@1#dac5a8a5c84b      | metric          | all     | 2       | 8       | 2         | 1.000       | 0.250    | 0.400 | 1.000           | -                      | 0      | 0              |
| abbrev_metric@1#dac5a8a5c84b      | all             | all     | 2       | 8       | 2         | 1.000       | 0.250    | 0.400 | 1.000           | -                      | 0      | 0              |
| gliner_condition@1#52e6222ffa49   | condition       | all     | 62      | 36      | 12        | 0.194       | 0.333    | 0.245 | 0.833           | -                      | 58     | 8              |
| gliner_condition@1#52e6222ffa49   | all             | all     | 62      | 36      | 12        | 0.194       | 0.333    | 0.245 | 0.833           | -                      | 58     | 8              |
| gliner_metric@1#0a7a21786921      | metric          | all     | 13      | 8       | 5         | 0.385       | 0.625    | 0.476 | 1.000           | -                      | 8      | 0              |
| gliner_metric@1#0a7a21786921      | all             | all     | 13      | 8       | 5         | 0.385       | 0.625    | 0.476 | 1.000           | -                      | 8      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 210     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 25      | 36      | 24        | 0.960       | 0.667    | 0.787 | 1.000           | -                      | 20     | 19             |
| llm_condition@1#45b3761c700e      | all             | all     | 25      | 36      | 24        | 0.960       | 0.667    | 0.787 | 1.000           | -                      | 20     | 19             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 38      | 43      | 29        | 0.763       | 0.674    | 0.716 | 1.000           | 0.931                  | 14     | 11             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 38      | 43      | 29        | 0.763       | 0.674    | 0.716 | 1.000           | -                      | 14     | 11             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 6       | 8       | 6         | 1.000       | 0.750    | 0.857 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 6       | 8       | 6         | 1.000       | 0.750    | 0.857 | 1.000           | -                      | 2      | 2              |
| number_measurement@1#a78269e0513d | measurement     | all     | 40      | 55      | 34        | 0.850       | 0.618    | 0.716 | 1.000           | 0.882                  | 16     | 16             |
| number_measurement@1#a78269e0513d | all             | all     | 40      | 55      | 34        | 0.850       | 0.618    | 0.716 | 1.000           | -                      | 16     | 16             |
| regex_author_claim@2#c58240a3a7a4 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#c58240a3a7a4 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#207f8f280e4a    | condition       | all     | 23      | 61      | 22        | 0.957       | 0.361    | 0.524 | 0.955           | -                      | 18     | 17             |
| regex_condition@2#207f8f280e4a    | all             | all     | 23      | 61      | 22        | 0.957       | 0.361    | 0.524 | 0.955           | -                      | 18     | 17             |
| regex_measurement@2#a65f61f0d966  | measurement     | all     | 31      | 102     | 26        | 0.839       | 0.255    | 0.391 | 1.000           | 0.615                  | 31     | 26             |
| regex_measurement@2#a65f61f0d966  | all             | all     | 31      | 102     | 26        | 0.839       | 0.255    | 0.391 | 1.000           | -                      | 31     | 26             |
| regex_metric@2#a5a76405f5d5       | metric          | all     | 24      | 27      | 23        | 0.958       | 0.852    | 0.902 | 0.957           | -                      | 19     | 18             |
| regex_metric@2#a5a76405f5d5       | all             | all     | 24      | 27      | 23        | 0.958       | 0.852    | 0.902 | 0.957           | -                      | 19     | 18             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_condition@1#eafcbe39d1a0   | 12      | 0             | 0              | 0               | 0.077     |
| abbrev_metric@1#dac5a8a5c84b      | 8       | 0             | 0              | 0               | 0.054     |
| gliner_condition@1#52e6222ffa49   | 12      | 40            | 0              | 0               | 0.093     |
| gliner_metric@1#0a7a21786921      | 8       | 25            | 0              | 0               | 0.056     |
| llm_condition@1#45b3761c700e      | 12      | 15            | 18108          | 2367            | 0.081     |
| llm_measurement@1#02bd5a7ab104    | 7       | 14            | 22270          | 6274            | 0.051     |
| llm_metric@1#41e1e53a1fc4         | 8       | 10            | 11265          | 798             | 0.055     |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 18681          | 1747            | 0.135     |
| number_measurement@1#a78269e0513d | 8       | 0             | 0              | 0               | 0.059     |
| regex_author_claim@2#c58240a3a7a4 | 20      | 0             | 0              | 0               | 0.134     |
| regex_condition@2#207f8f280e4a    | 20      | 0             | 0              | 0               | 0.130     |
| regex_measurement@2#a65f61f0d966  | 20      | 0             | 0              | 0               | 0.133     |
| regex_metric@2#a5a76405f5d5       | 20      | 0             | 0              | 0               | 0.131     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.136     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 195     | 9.750       |
| input_tokens     | 70324   | 3516.200    |
| made_model_calls | 124     | 6.200       |
| model_calls      | 124     | 6.200       |
| output_tokens    | 11186   | 559.300     |
| seconds          | 164.675 | 8.234       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 9.750          |
| model_calls   | 6.200          |
| input_tokens  | 3516.200       |
| output_tokens | 559.300        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 3           |
| 2               | 1           |
| 3               | 6           |
| exhausted       | 10          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
