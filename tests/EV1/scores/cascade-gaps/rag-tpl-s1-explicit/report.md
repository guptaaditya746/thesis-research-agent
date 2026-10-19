# Evaluation of run rag-tpl-s1-explicit on rag-tpl-s1-59c5118b

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: explicit

## A. Extraction

| evidence_type   | level    | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|----------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit | 120     | 162     | 118       | 0.983       | 0.728    | 0.837 | 1.000           |
| all             | all      | 120     | 162     | 118       | 0.983       | 0.728    | 0.837 | 1.000           |
| author_claim    | explicit | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit | 41      | 61      | 40        | 0.976       | 0.656    | 0.784 | 1.000           |
| condition       | all      | 41      | 61      | 40        | 0.976       | 0.656    | 0.784 | 1.000           |
| measurement     | explicit | 39      | 61      | 38        | 0.974       | 0.623    | 0.760 | 1.000           |
| measurement     | all      | 39      | 61      | 38        | 0.974       | 0.623    | 0.760 | 1.000           |
| metric          | explicit | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 44; items matching no fact: 2.

## B. Integration

| level    | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|----------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit | 38                     | 1.000                  | 1.000                     | 1.000             | 0.974             | 1.000          | 0         | -           |
| all      | 38                     | 1.000                  | 1.000                     | 1.000             | 0.974             | 1.000          | 0         | -           |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.900                | 0.900          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level    | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|----------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit | evidence-engine | 20        | 20           | 0.900                | 0.900          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
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
| condition       | 0.784 [0.73, 0.85] | BCa      |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 0.760 [0.66, 0.83] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.837 [0.78, 0.89] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.900 [0.70, 1.00]   | BCa      | -                     | -               |

## Locate recall

| evidence_type   | level    | placements   | inside   | recall   |
|-----------------|----------|--------------|----------|----------|
| all             | explicit | 364          | 364      | 1.000    |
| all             | all      | 364          | 364      | 1.000    |
| author_claim    | explicit | 40           | 40       | 1.000    |
| author_claim    | all      | 40           | 40       | 1.000    |
| condition       | explicit | 162          | 162      | 1.000    |
| condition       | all      | 162          | 162      | 1.000    |
| measurement     | explicit | 61           | 61       | 1.000    |
| measurement     | all      | 61           | 61       | 1.000    |
| metric          | explicit | 101          | 101      | 1.000    |
| metric          | all      | 101          | 101      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | 0       | 0               | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | 15      | 15              | 13     | 13             |
| llm_measurement@1#957820ab7bd1    | 36      | 35              | 26     | 25             |
| llm_metric@1#6186147fa702         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#75e32ebcdf68 | 20      | 20              | 20     | 20             |
| regex_condition@2#a0c64d9b6305    | 28      | 27              | 26     | 25             |
| regex_measurement@2#b984f16ded3b  | 13      | 13              | 3      | 3              |
| regex_metric@2#94a3000eacae       | 18      | 18              | 18     | 18             |

Facts no extractor found: condition 21, measurement 23

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | all             | all     | 0       | 162     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | condition       | all     | 15      | 30      | 15        | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 13     | 13             |
| llm_condition@1#f75a85c10bd4      | all             | all     | 15      | 30      | 15        | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 13     | 13             |
| llm_measurement@1#957820ab7bd1    | measurement     | all     | 36      | 53      | 35        | 0.972       | 0.660    | 0.787 | 1.000           | 1.000                  | 26     | 25             |
| llm_measurement@1#957820ab7bd1    | all             | all     | 36      | 53      | 35        | 0.972       | 0.660    | 0.787 | 1.000           | -                      | 26     | 25             |
| llm_metric@1#6186147fa702         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#6186147fa702         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#75e32ebcdf68 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#75e32ebcdf68 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#a0c64d9b6305    | condition       | all     | 28      | 61      | 27        | 0.964       | 0.443    | 0.607 | 1.000           | -                      | 26     | 25             |
| regex_condition@2#a0c64d9b6305    | all             | all     | 28      | 61      | 27        | 0.964       | 0.443    | 0.607 | 1.000           | -                      | 26     | 25             |
| regex_measurement@2#b984f16ded3b  | measurement     | all     | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | 1.000                  | 3      | 3              |
| regex_measurement@2#b984f16ded3b  | all             | all     | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | -                      | 3      | 3              |
| regex_metric@2#94a3000eacae       | metric          | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |
| regex_metric@2#94a3000eacae       | all             | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#f75a85c10bd4      | 10      | 19            | 16660          | 1712            | 48.082    |
| llm_measurement@1#957820ab7bd1    | 17      | 34            | 37876          | 7571            | 197.000   |
| llm_metric@1#6186147fa702         | 2       | 2             | 1979           | 186             | 5.306     |
| llm_screen@1#a1013a736e72         | 20      | 20            | 13590          | 1382            | 39.354    |
| regex_author_claim@2#75e32ebcdf68 | 20      | 0             | 0              | 0               | 0.283     |
| regex_condition@2#a0c64d9b6305    | 20      | 0             | 0              | 0               | 0.279     |
| regex_measurement@2#b984f16ded3b  | 20      | 0             | 0              | 0               | 0.281     |
| regex_metric@2#94a3000eacae       | 20      | 0             | 0              | 0               | 0.265     |
| regex_screen@1#a2821956ee33       | 20      | 0             | 0              | 0               | 0.271     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 149     | 7.450       |
| input_tokens     | 70105   | 3505.250    |
| made_model_calls | 75      | 3.750       |
| model_calls      | 75      | 3.750       |
| output_tokens    | 10851   | 542.550     |
| seconds          | 292.374 | 14.619      |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.450          |
| model_calls   | 3.750          |
| input_tokens  | 3505.250       |
| output_tokens | 542.550        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 1           |
| 1               | 17          |
| exhausted       | 2           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
