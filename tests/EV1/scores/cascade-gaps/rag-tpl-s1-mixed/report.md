# Evaluation of run rag-tpl-s1-mixed on rag-tpl-s1-6162b495

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 24      | 38      | 24        | 1.000       | 0.632    | 0.774 | 1.000           |
| all             | paraphrased   | 12      | 34      | 12        | 1.000       | 0.353    | 0.522 | 1.000           |
| all             | distributed   | 24      | 26      | 24        | 1.000       | 0.923    | 0.960 | 1.000           |
| all             | complex       | 50      | 74      | 49        | 0.980       | 0.662    | 0.790 | 1.000           |
| all             | contradictory | 26      | 38      | 24        | 0.923       | 0.632    | 0.750 | 1.000           |
| all             | all           | 136     | 210     | 133       | 0.978       | 0.633    | 0.769 | 1.000           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 1.000           |
| condition       | paraphrased   | 5       | 13      | 5         | 1.000       | 0.385    | 0.556 | 1.000           |
| condition       | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | complex       | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | contradictory | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 1.000           |
| condition       | all           | 37      | 61      | 37        | 1.000       | 0.607    | 0.755 | 1.000           |
| measurement     | explicit      | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 1.000           |
| measurement     | paraphrased   | 2       | 13      | 2         | 1.000       | 0.154    | 0.267 | 1.000           |
| measurement     | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| measurement     | complex       | 27      | 50      | 26        | 0.963       | 0.520    | 0.675 | 1.000           |
| measurement     | contradictory | 10      | 15      | 8         | 0.800       | 0.533    | 0.640 | 1.000           |
| measurement     | all           | 55      | 102     | 52        | 0.945       | 0.510    | 0.662 | 1.000           |
| metric          | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased   | 1       | 4       | 1         | 1.000       | 0.250    | 0.400 | 1.000           |
| metric          | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 24      | 27      | 24        | 1.000       | 0.889    | 0.941 | 1.000           |

Facts no item matched: 77; items matching no fact: 3.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| paraphrased   | 2                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| distributed   | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| complex       | 26                     | 0.923                  | 0.923                     | 1.000             | 0.923             | 1.000          | 0         | -           |
| contradictory | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| all           | 52                     | 0.962                  | 0.962                     | 1.000             | 0.962             | 1.000          | 0         | -           |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.850                | 0.850          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | evidence-engine | 4         | 4            | 0.250                | 0.250          | 1.000               | -              |
| distributed   | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| complex       | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| contradictory | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 4    | 0    | 0.000       | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.755 [0.67, 0.84] | BCa      |
| metric          | 0.941 [0.83, 0.99] | BCa      |
| measurement     | 0.662 [0.55, 0.80] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.769 [0.69, 0.84] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.850 [0.65, 0.95]   | BCa      | -                     | -               |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 84           | 84       | 1.000    |
| all             | paraphrased   | 72           | 72       | 1.000    |
| all             | distributed   | 60           | 60       | 1.000    |
| all             | complex       | 138          | 138      | 1.000    |
| all             | contradictory | 77           | 77       | 1.000    |
| all             | all           | 431          | 431      | 1.000    |
| author_claim    | explicit      | 8            | 8        | 1.000    |
| author_claim    | paraphrased   | 8            | 8        | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
| condition       | explicit      | 38           | 38       | 1.000    |
| condition       | paraphrased   | 34           | 34       | 1.000    |
| condition       | distributed   | 27           | 27       | 1.000    |
| condition       | complex       | 43           | 43       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 182          | 182      | 1.000    |
| measurement     | explicit      | 15           | 15       | 1.000    |
| measurement     | paraphrased   | 13           | 13       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 50           | 50       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 102          | 102      | 1.000    |
| metric          | explicit      | 23           | 23       | 1.000    |
| metric          | paraphrased   | 17           | 17       | 1.000    |
| metric          | distributed   | 16           | 16       | 1.000    |
| metric          | complex       | 37           | 37       | 1.000    |
| metric          | contradictory | 14           | 14       | 1.000    |
| metric          | all           | 107          | 107      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | 0       | 0               | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | 15      | 15              | 14     | 14             |
| llm_measurement@1#957820ab7bd1    | 29      | 29              | 24     | 24             |
| llm_metric@1#6186147fa702         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#75e32ebcdf68 | 20      | 20              | 20     | 20             |
| regex_condition@2#a0c64d9b6305    | 23      | 23              | 22     | 22             |
| regex_measurement@2#b984f16ded3b  | 31      | 28              | 26     | 23             |
| regex_metric@2#94a3000eacae       | 22      | 22              | 22     | 22             |

Facts no extractor found: condition 24, measurement 50, metric 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | all             | all     | 0       | 210     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | condition       | all     | 15      | 36      | 15        | 1.000       | 0.417    | 0.588 | 1.000           | -                      | 14     | 14             |
| llm_condition@1#f75a85c10bd4      | all             | all     | 15      | 36      | 15        | 1.000       | 0.417    | 0.588 | 1.000           | -                      | 14     | 14             |
| llm_measurement@1#957820ab7bd1    | measurement     | all     | 29      | 68      | 29        | 1.000       | 0.426    | 0.598 | 1.000           | 1.000                  | 24     | 24             |
| llm_measurement@1#957820ab7bd1    | all             | all     | 29      | 68      | 29        | 1.000       | 0.426    | 0.598 | 1.000           | -                      | 24     | 24             |
| llm_metric@1#6186147fa702         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#6186147fa702         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#75e32ebcdf68 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#75e32ebcdf68 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#a0c64d9b6305    | condition       | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 1.000           | -                      | 22     | 22             |
| regex_condition@2#a0c64d9b6305    | all             | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 1.000           | -                      | 22     | 22             |
| regex_measurement@2#b984f16ded3b  | measurement     | all     | 31      | 102     | 28        | 0.903       | 0.275    | 0.421 | 1.000           | 0.929                  | 26     | 23             |
| regex_measurement@2#b984f16ded3b  | all             | all     | 31      | 102     | 28        | 0.903       | 0.275    | 0.421 | 1.000           | -                      | 26     | 23             |
| regex_metric@2#94a3000eacae       | metric          | all     | 22      | 27      | 22        | 1.000       | 0.815    | 0.898 | 1.000           | -                      | 22     | 22             |
| regex_metric@2#94a3000eacae       | all             | all     | 22      | 27      | 22        | 1.000       | 0.815    | 0.898 | 1.000           | -                      | 22     | 22             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#f75a85c10bd4      | 12      | 22            | 21294          | 1742            | 18.681    |
| llm_measurement@1#957820ab7bd1    | 13      | 26            | 30267          | 5080            | 12.081    |
| llm_metric@1#6186147fa702         | 2       | 2             | 1941           | 189             | 2.697     |
| llm_screen@1#a1013a736e72         | 20      | 20            | 15335          | 1569            | 8.978     |
| regex_author_claim@2#75e32ebcdf68 | 20      | 0             | 0              | 0               | 0.172     |
| regex_condition@2#a0c64d9b6305    | 20      | 0             | 0              | 0               | 0.175     |
| regex_measurement@2#b984f16ded3b  | 20      | 0             | 0              | 0               | 0.170     |
| regex_metric@2#94a3000eacae       | 20      | 0             | 0              | 0               | 0.168     |
| regex_screen@1#a2821956ee33       | 20      | 0             | 0              | 0               | 0.180     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 117     | 5.850       |
| calls            | 147     | 7.350       |
| input_tokens     | 68837   | 3441.850    |
| made_model_calls | 15      | 0.750       |
| model_calls      | 70      | 3.500       |
| output_tokens    | 8580    | 429.000     |
| seconds          | 44.487  | 2.224       |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.350          |
| model_calls   | 3.500          |
| input_tokens  | 3441.850       |
| output_tokens | 429.000        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 4           |
| 1               | 13          |
| exhausted       | 3           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
