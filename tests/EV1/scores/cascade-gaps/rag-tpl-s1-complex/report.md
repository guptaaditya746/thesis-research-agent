# Evaluation of run rag-tpl-s1-complex on rag-tpl-s1-f0f5d48e

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 288     | 431     | 277       | 0.962       | 0.643    | 0.771 | 1.000           |
| all             | all     | 288     | 431     | 277       | 0.962       | 0.643    | 0.771 | 1.000           |
| author_claim    | complex | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 41      | 61      | 41        | 1.000       | 0.672    | 0.804 | 1.000           |
| condition       | all     | 41      | 61      | 41        | 1.000       | 0.672    | 0.804 | 1.000           |
| measurement     | complex | 177     | 300     | 166       | 0.938       | 0.553    | 0.696 | 1.000           |
| measurement     | all     | 177     | 300     | 166       | 0.938       | 0.553    | 0.696 | 1.000           |
| metric          | complex | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all     | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 154; items matching no fact: 11.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 166                    | 0.825                  | 0.861                     | 0.964             | 0.861             | 0.964          | 0         | -           |
| all     | 166                    | 0.825                  | 0.861                     | 0.964             | 0.861             | 0.964          | 0         | -           |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| complex | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | yes              | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.804 [0.74, 0.87] | BCa      |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 0.696 [0.60, 0.78] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.771 [0.70, 0.82] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 773          | 773      | 1.000    |
| all             | all     | 773          | 773      | 1.000    |
| author_claim    | complex | 40           | 40       | 1.000    |
| author_claim    | all     | 40           | 40       | 1.000    |
| condition       | complex | 263          | 263      | 1.000    |
| condition       | all     | 263          | 263      | 1.000    |
| measurement     | complex | 300          | 300      | 1.000    |
| measurement     | all     | 300          | 300      | 1.000    |
| metric          | complex | 170          | 170      | 1.000    |
| metric          | all     | 170          | 170      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | 0       | 0               | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | 15      | 15              | 13     | 13             |
| llm_measurement@1#957820ab7bd1    | 97      | 90              | 78     | 71             |
| llm_metric@1#6186147fa702         | 5       | 5               | 2      | 2              |
| regex_author_claim@2#75e32ebcdf68 | 20      | 20              | 20     | 20             |
| regex_condition@2#a0c64d9b6305    | 28      | 28              | 26     | 26             |
| regex_measurement@2#b984f16ded3b  | 99      | 95              | 80     | 76             |
| regex_metric@2#94a3000eacae       | 48      | 48              | 45     | 45             |

Facts no extractor found: condition 20, measurement 134

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | all             | all     | 0       | 431     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | condition       | all     | 15      | 30      | 15        | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 13     | 13             |
| llm_condition@1#f75a85c10bd4      | all             | all     | 15      | 30      | 15        | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 13     | 13             |
| llm_measurement@1#957820ab7bd1    | measurement     | all     | 97      | 218     | 90        | 0.928       | 0.413    | 0.571 | 1.000           | 0.822                  | 78     | 71             |
| llm_measurement@1#957820ab7bd1    | all             | all     | 97      | 218     | 90        | 0.928       | 0.413    | 0.571 | 1.000           | -                      | 78     | 71             |
| llm_metric@1#6186147fa702         | metric          | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#6186147fa702         | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#75e32ebcdf68 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#75e32ebcdf68 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#a0c64d9b6305    | condition       | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 26     | 26             |
| regex_condition@2#a0c64d9b6305    | all             | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 26     | 26             |
| regex_measurement@2#b984f16ded3b  | measurement     | all     | 99      | 300     | 95        | 0.960       | 0.317    | 0.476 | 1.000           | 0.863                  | 80     | 76             |
| regex_measurement@2#b984f16ded3b  | all             | all     | 99      | 300     | 95        | 0.960       | 0.317    | 0.476 | 1.000           | -                      | 80     | 76             |
| regex_metric@2#94a3000eacae       | metric          | all     | 48      | 50      | 48        | 1.000       | 0.960    | 0.980 | 1.000           | -                      | 45     | 45             |
| regex_metric@2#94a3000eacae       | all             | all     | 48      | 50      | 48        | 1.000       | 0.960    | 0.980 | 1.000           | -                      | 45     | 45             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#f75a85c10bd4      | 10      | 18            | 19457          | 1677            | 48.243    |
| llm_measurement@1#957820ab7bd1    | 15      | 30            | 43467          | 15979           | 400.983   |
| llm_metric@1#6186147fa702         | 2       | 3             | 3587           | 468             | 12.697    |
| llm_screen@1#a1013a736e72         | 20      | 20            | 17726          | 1427            | 42.524    |
| regex_author_claim@2#75e32ebcdf68 | 20      | 0             | 0              | 0               | 0.315     |
| regex_condition@2#a0c64d9b6305    | 20      | 0             | 0              | 0               | 0.325     |
| regex_measurement@2#b984f16ded3b  | 20      | 0             | 0              | 0               | 0.353     |
| regex_metric@2#94a3000eacae       | 20      | 0             | 0              | 0               | 0.303     |
| regex_screen@1#a2821956ee33       | 20      | 0             | 0              | 0               | 0.290     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 147     | 7.350       |
| input_tokens     | 84237   | 4211.850    |
| made_model_calls | 71      | 3.550       |
| model_calls      | 71      | 3.550       |
| output_tokens    | 19551   | 977.550     |
| seconds          | 507.335 | 25.367      |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.350          |
| model_calls   | 3.550          |
| input_tokens  | 4211.850       |
| output_tokens | 977.550        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 5           |
| 1               | 15          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
