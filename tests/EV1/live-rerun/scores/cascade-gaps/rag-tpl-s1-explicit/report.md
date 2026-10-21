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
| explicit | 38                     | 1.000                  | 1.000                     | 1.000             | 0.974             | 1.000          | 20        | 0.850       |
| all      | 38                     | 1.000                  | 1.000                     | 1.000             | 0.974             | 1.000          | 20        | 0.850       |

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
| llm_author_claim@1#fefdf4416c50   | 0       | 0               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 15      | 15              | 13     | 13             |
| llm_measurement@1#5212fc43026f    | 36      | 35              | 26     | 25             |
| llm_metric@1#1ca12a572ef8         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#b2161f228a8c | 20      | 20              | 20     | 20             |
| regex_condition@2#80486860164a    | 28      | 27              | 26     | 25             |
| regex_measurement@2#9edb306c5b05  | 13      | 13              | 3      | 3              |
| regex_metric@2#67f41f33eff7       | 18      | 18              | 18     | 18             |

Facts no extractor found: condition 21, measurement 23

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | all             | all     | 0       | 162     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 15      | 30      | 15        | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 13     | 13             |
| llm_condition@1#134ab1a38338      | all             | all     | 15      | 30      | 15        | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 13     | 13             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 36      | 53      | 35        | 0.972       | 0.660    | 0.787 | 1.000           | 1.000                  | 26     | 25             |
| llm_measurement@1#5212fc43026f    | all             | all     | 36      | 53      | 35        | 0.972       | 0.660    | 0.787 | 1.000           | -                      | 26     | 25             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#b2161f228a8c | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#80486860164a    | condition       | all     | 28      | 61      | 27        | 0.964       | 0.443    | 0.607 | 1.000           | -                      | 26     | 25             |
| regex_condition@2#80486860164a    | all             | all     | 28      | 61      | 27        | 0.964       | 0.443    | 0.607 | 1.000           | -                      | 26     | 25             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | 1.000                  | 3      | 3              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | -                      | 3      | 3              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |
| regex_metric@2#67f41f33eff7       | all             | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#134ab1a38338      | 10      | 19            | 16660          | 1710            | 48.677    |
| llm_measurement@1#5212fc43026f    | 17      | 34            | 37876          | 7553            | 196.588   |
| llm_metric@1#1ca12a572ef8         | 2       | 2             | 1979           | 184             | 5.265     |
| llm_screen@1#6bec6abaf6a0         | 20      | 20            | 13590          | 1365            | 0.140     |
| regex_author_claim@2#b2161f228a8c | 20      | 0             | 0              | 0               | 0.135     |
| regex_condition@2#80486860164a    | 20      | 0             | 0              | 0               | 0.139     |
| regex_measurement@2#9edb306c5b05  | 20      | 0             | 0              | 0               | 0.136     |
| regex_metric@2#67f41f33eff7       | 20      | 0             | 0              | 0               | 0.139     |
| regex_screen@1#8301b6896dc3       | 20      | 0             | 0              | 0               | 0.145     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 120     | 6.000       |
| calls            | 149     | 7.450       |
| input_tokens     | 70105   | 3505.250    |
| made_model_calls | 55      | 2.750       |
| model_calls      | 75      | 3.750       |
| output_tokens    | 10812   | 540.600     |
| seconds          | 252.619 | 12.631      |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.450          |
| model_calls   | 3.750          |
| input_tokens  | 3505.250       |
| output_tokens | 540.600        |

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
