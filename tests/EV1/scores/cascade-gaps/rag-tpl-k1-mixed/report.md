# Evaluation of run rag-tpl-k1-mixed on rag-tpl-k1-9c3bbb32

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 30      | 48      | 30        | 1.000       | 0.625    | 0.769 | 1.000           |
| all             | paraphrased   | 19      | 43      | 19        | 1.000       | 0.442    | 0.613 | 1.000           |
| all             | distributed   | 24      | 26      | 24        | 1.000       | 0.923    | 0.960 | 1.000           |
| all             | complex       | 49      | 72      | 48        | 0.980       | 0.667    | 0.793 | 1.000           |
| all             | contradictory | 26      | 38      | 24        | 0.923       | 0.632    | 0.750 | 1.000           |
| all             | all           | 148     | 227     | 145       | 0.980       | 0.639    | 0.773 | 1.000           |
| author_claim    | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 10      | 19      | 10        | 1.000       | 0.526    | 0.690 | 1.000           |
| condition       | paraphrased   | 8       | 17      | 8         | 1.000       | 0.471    | 0.640 | 1.000           |
| condition       | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | complex       | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | contradictory | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 1.000           |
| condition       | all           | 42      | 69      | 42        | 1.000       | 0.609    | 0.757 | 1.000           |
| measurement     | explicit      | 10      | 19      | 10        | 1.000       | 0.526    | 0.690 | 1.000           |
| measurement     | paraphrased   | 4       | 16      | 4         | 1.000       | 0.250    | 0.400 | 1.000           |
| measurement     | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| measurement     | complex       | 26      | 48      | 25        | 0.962       | 0.521    | 0.676 | 1.000           |
| measurement     | contradictory | 10      | 15      | 8         | 0.800       | 0.533    | 0.640 | 1.000           |
| measurement     | all           | 58      | 107     | 55        | 0.948       | 0.514    | 0.667 | 1.000           |
| metric          | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased   | 2       | 5       | 2         | 1.000       | 0.400    | 0.571 | 1.000           |
| metric          | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 26      | 29      | 26        | 1.000       | 0.897    | 0.945 | 1.000           |

Facts no item matched: 82; items matching no fact: 3.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 10                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 5         | 1.000       |
| paraphrased   | 4                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 0.250       |
| distributed   | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| complex       | 25                     | 0.920                  | 0.920                     | 1.000             | 0.920             | 1.000          | 3         | 0.000       |
| contradictory | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| all           | 55                     | 0.964                  | 0.964                     | 1.000             | 0.964             | 1.000          | 20        | 0.700       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 24        | 20           | 0.875                | 0.850          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | evidence-engine | 5         | 5            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | evidence-engine | 5         | 4            | 0.400                | 0.250          | 1.000               | -              |
| distributed   | evidence-engine | 5         | 4            | 1.000                | 1.000          | 1.000               | -              |
| complex       | evidence-engine | 5         | 3            | 1.000                | 1.000          | 1.000               | -              |
| contradictory | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 4    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 1    | 0    | 1    | 1.000       | 0.500    |
| evidence-engine | large_effect    | 1    | 0    | 1    | 1.000       | 0.500    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | no                   |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.757 [0.68, 0.83] | BCa      |
| metric          | 0.945 [0.85, 0.99] | BCa      |
| measurement     | 0.667 [0.56, 0.79] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.773 [0.70, 0.85] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.875 [0.71, 0.96]   | BCa      | -                     | -               |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 106          | 106      | 1.000    |
| all             | paraphrased   | 90           | 90       | 1.000    |
| all             | distributed   | 60           | 60       | 1.000    |
| all             | complex       | 133          | 133      | 1.000    |
| all             | contradictory | 77           | 77       | 1.000    |
| all             | all           | 466          | 466      | 1.000    |
| author_claim    | explicit      | 10           | 10       | 1.000    |
| author_claim    | paraphrased   | 10           | 10       | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 44           | 44       | 1.000    |
| condition       | explicit      | 48           | 48       | 1.000    |
| condition       | paraphrased   | 43           | 43       | 1.000    |
| condition       | distributed   | 27           | 27       | 1.000    |
| condition       | complex       | 41           | 41       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 199          | 199      | 1.000    |
| measurement     | explicit      | 19           | 19       | 1.000    |
| measurement     | paraphrased   | 16           | 16       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 48           | 48       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 107          | 107      | 1.000    |
| metric          | explicit      | 29           | 29       | 1.000    |
| metric          | paraphrased   | 21           | 21       | 1.000    |
| metric          | distributed   | 16           | 16       | 1.000    |
| metric          | complex       | 36           | 36       | 1.000    |
| metric          | contradictory | 14           | 14       | 1.000    |
| metric          | all           | 116          | 116      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | 0       | 0               | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | 19      | 19              | 18     | 18             |
| llm_measurement@1#957820ab7bd1    | 35      | 35              | 27     | 27             |
| llm_metric@1#6186147fa702         | 3       | 3               | 3      | 3              |
| regex_author_claim@2#75e32ebcdf68 | 22      | 22              | 22     | 22             |
| regex_condition@2#a0c64d9b6305    | 24      | 24              | 23     | 23             |
| regex_measurement@2#b984f16ded3b  | 31      | 28              | 23     | 20             |
| regex_metric@2#94a3000eacae       | 23      | 23              | 23     | 23             |

Facts no extractor found: condition 27, measurement 52, metric 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | all             | all     | 0       | 227     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | condition       | all     | 19      | 44      | 19        | 1.000       | 0.432    | 0.603 | 1.000           | -                      | 18     | 18             |
| llm_condition@1#f75a85c10bd4      | all             | all     | 19      | 44      | 19        | 1.000       | 0.432    | 0.603 | 1.000           | -                      | 18     | 18             |
| llm_measurement@1#957820ab7bd1    | measurement     | all     | 35      | 84      | 35        | 1.000       | 0.417    | 0.588 | 1.000           | 1.000                  | 27     | 27             |
| llm_measurement@1#957820ab7bd1    | all             | all     | 35      | 84      | 35        | 1.000       | 0.417    | 0.588 | 1.000           | -                      | 27     | 27             |
| llm_metric@1#6186147fa702         | metric          | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 3      | 3              |
| llm_metric@1#6186147fa702         | all             | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 3      | 3              |
| regex_author_claim@2#75e32ebcdf68 | author_claim    | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 22     | 22             |
| regex_author_claim@2#75e32ebcdf68 | all             | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 22     | 22             |
| regex_condition@2#a0c64d9b6305    | condition       | all     | 24      | 69      | 24        | 1.000       | 0.348    | 0.516 | 1.000           | -                      | 23     | 23             |
| regex_condition@2#a0c64d9b6305    | all             | all     | 24      | 69      | 24        | 1.000       | 0.348    | 0.516 | 1.000           | -                      | 23     | 23             |
| regex_measurement@2#b984f16ded3b  | measurement     | all     | 31      | 107     | 28        | 0.903       | 0.262    | 0.406 | 1.000           | 0.929                  | 23     | 20             |
| regex_measurement@2#b984f16ded3b  | all             | all     | 31      | 107     | 28        | 0.903       | 0.262    | 0.406 | 1.000           | -                      | 23     | 20             |
| regex_metric@2#94a3000eacae       | metric          | all     | 23      | 29      | 23        | 1.000       | 0.793    | 0.885 | 1.000           | -                      | 23     | 23             |
| regex_metric@2#94a3000eacae       | all             | all     | 23      | 29      | 23        | 1.000       | 0.793    | 0.885 | 1.000           | -                      | 23     | 23             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#f75a85c10bd4      | 14      | 25            | 24269          | 2177            | 20.358    |
| llm_measurement@1#957820ab7bd1    | 16      | 32            | 37302          | 6345            | 41.309    |
| llm_metric@1#6186147fa702         | 3       | 3             | 2909           | 284             | 2.702     |
| llm_screen@1#a1013a736e72         | 23      | 23            | 17365          | 1793            | 0.149     |
| regex_author_claim@2#75e32ebcdf68 | 22      | 0             | 0              | 0               | 0.143     |
| regex_condition@2#a0c64d9b6305    | 22      | 0             | 0              | 0               | 0.144     |
| regex_measurement@2#b984f16ded3b  | 22      | 0             | 0              | 0               | 0.142     |
| regex_metric@2#94a3000eacae       | 22      | 0             | 0              | 0               | 0.140     |
| regex_screen@1#a2821956ee33       | 24      | 0             | 0              | 0               | 0.156     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 159     | 6.625       |
| calls            | 168     | 7.000       |
| input_tokens     | 81845   | 3410.208    |
| made_model_calls | 16      | 0.667       |
| model_calls      | 83      | 3.458       |
| output_tokens    | 10599   | 441.625     |
| seconds          | 66.513  | 2.771       |

## Funnel

Strategy `gaps` over 24 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.000          |
| model_calls   | 3.458          |
| input_tokens  | 3410.208       |
| output_tokens | 441.625        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 3           |
| 1               | 14          |
| exhausted       | 5           |
| skipped         | 2           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 24          | 22   | 0    | 0    | 2    | 1.000       | 1.000    |

Screened out wrongly: none
