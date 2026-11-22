# Evaluation of run rag-llm-s1-complex on rag-llm-s1-a2b5bbc1

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 180     | 242     | 167       | 0.928       | 0.690    | 0.791 | 0.970           |
| all             | all     | 180     | 242     | 167       | 0.928       | 0.690    | 0.791 | 0.970           |
| author_claim    | complex | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 28      | 33      | 25        | 0.893       | 0.758    | 0.820 | 0.800           |
| condition       | all     | 28      | 33      | 25        | 0.893       | 0.758    | 0.820 | 0.800           |
| measurement     | complex | 107     | 170     | 104       | 0.972       | 0.612    | 0.751 | 1.000           |
| measurement     | all     | 107     | 170     | 104       | 0.972       | 0.612    | 0.751 | 1.000           |
| metric          | complex | 34      | 28      | 27        | 0.794       | 0.964    | 0.871 | 1.000           |
| metric          | all     | 34      | 28      | 27        | 0.794       | 0.964    | 0.871 | 1.000           |

Facts no item matched: 75; items matching no fact: 13.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 104                    | 0.962                  | 1.000                     | 0.962             | 0.981             | 0.933          | 11        | 0.455       |
| all     | 104                    | 0.962                  | 1.000                     | 0.962             | 0.981             | 0.933          | 11        | 0.455       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |
| rag-baseline    | refuted | mixed      | no              | 11        | 11           | 0.182                | 0.545          | 0.333               | 1.000          |
| agent-baseline  | mixed   | mixed      | yes             | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| complex | agent-baseline  | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| complex | evidence-engine | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |
| complex | rag-baseline    | 11        | 11           | 0.182                | 0.545          | 0.333               | 1.000          |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 1    | 0    | 0.000       | -        |
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
| condition       | 0.820 [0.75, 0.89] | BCa      |
| metric          | 0.871 [0.80, 0.94] | BCa      |
| measurement     | 0.751 [0.64, 0.88] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.791 [0.70, 0.89] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.909 [0.61, 1.00]   | BCa      | -                     | -               |
| rag-baseline    | 0.182 [0.00, 0.55]   | BCa      | 0.727 [0.45, 0.91]    | BCa             |
| agent-baseline  | 1.000 [n/a]          | -        | -0.091 [-0.39, 0.00]  | BCa             |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 580          | 580      | 1.000    |
| all             | all     | 580          | 580      | 1.000    |
| author_claim    | complex | 22           | 22       | 1.000    |
| author_claim    | all     | 22           | 22       | 1.000    |
| condition       | complex | 221          | 221      | 1.000    |
| condition       | all     | 221          | 221      | 1.000    |
| measurement     | complex | 170          | 170      | 1.000    |
| measurement     | all     | 170          | 170      | 1.000    |
| metric          | complex | 167          | 167      | 1.000    |
| metric          | all     | 167          | 167      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 0       | 0               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 10      | 10              | 10     | 10             |
| llm_measurement@1#5212fc43026f    | 58      | 56              | 52     | 50             |
| llm_metric@1#1ca12a572ef8         | 0       | 0               | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 11     | 11             |
| regex_condition@2#80486860164a    | 18      | 15              | 18     | 15             |
| regex_measurement@2#9edb306c5b05  | 55      | 54              | 49     | 48             |
| regex_metric@2#67f41f33eff7       | 34      | 27              | 34     | 27             |

Facts no extractor found: condition 8, measurement 66, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | all             | all     | 0       | 242     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 10      | 11      | 10        | 1.000       | 0.909    | 0.952 | 1.000           | -                      | 10     | 10             |
| llm_condition@1#134ab1a38338      | all             | all     | 10      | 11      | 10        | 1.000       | 0.909    | 0.952 | 1.000           | -                      | 10     | 10             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 58      | 118     | 56        | 0.966       | 0.475    | 0.636 | 1.000           | 0.929                  | 52     | 50             |
| llm_measurement@1#5212fc43026f    | all             | all     | 58      | 118     | 56        | 0.966       | 0.475    | 0.636 | 1.000           | -                      | 52     | 50             |
| llm_metric@1#1ca12a572ef8         | all             | all     | 0       | 242     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_condition@2#80486860164a    | condition       | all     | 18      | 33      | 15        | 0.833       | 0.455    | 0.588 | 0.667           | -                      | 18     | 15             |
| regex_condition@2#80486860164a    | all             | all     | 18      | 33      | 15        | 0.833       | 0.455    | 0.588 | 0.667           | -                      | 18     | 15             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 55      | 170     | 54        | 0.982       | 0.318    | 0.480 | 1.000           | 1.000                  | 49     | 48             |
| regex_measurement@2#9edb306c5b05  | all             | all     | 55      | 170     | 54        | 0.982       | 0.318    | 0.480 | 1.000           | -                      | 49     | 48             |
| regex_metric@2#67f41f33eff7       | metric          | all     | 34      | 28      | 27        | 0.794       | 0.964    | 0.871 | 1.000           | -                      | 34     | 27             |
| regex_metric@2#67f41f33eff7       | all             | all     | 34      | 28      | 27        | 0.794       | 0.964    | 0.871 | 1.000           | -                      | 34     | 27             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#134ab1a38338      | 4       | 7             | 9329           | 1034            | 29.023    |
| llm_measurement@1#5212fc43026f    | 8       | 16            | 28082          | 9555            | 240.346   |
| llm_screen@1#6bec6abaf6a0         | 11      | 11            | 12527          | 921             | 0.069     |
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.068     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.073     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.076     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.072     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.071     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 66      | 6.000       |
| calls            | 78      | 7.091       |
| input_tokens     | 49938   | 4539.818    |
| made_model_calls | 23      | 2.091       |
| model_calls      | 34      | 3.091       |
| output_tokens    | 11510   | 1046.364    |
| seconds          | 270.449 | 24.586      |

## Funnel

Strategy `gaps` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.091          |
| model_calls   | 3.091          |
| input_tokens  | 4539.818       |
| output_tokens | 1046.364       |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 3           |
| 1               | 8           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
