# Evaluation of run rag-llm-s1-distributed on rag-llm-s1-d60fff2f

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 85      | 88      | 73        | 0.859       | 0.830    | 0.844 | 0.945           |
| all             | all         | 85      | 88      | 73        | 0.859       | 0.830    | 0.844 | 0.945           |
| author_claim    | distributed | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 29      | 33      | 26        | 0.897       | 0.788    | 0.839 | 0.846           |
| condition       | all         | 29      | 33      | 26        | 0.897       | 0.788    | 0.839 | 0.846           |
| measurement     | distributed | 26      | 33      | 26        | 1.000       | 0.788    | 0.881 | 1.000           |
| measurement     | all         | 26      | 33      | 26        | 1.000       | 0.788    | 0.881 | 1.000           |
| metric          | distributed | 19      | 11      | 10        | 0.526       | 0.909    | 0.667 | 1.000           |
| metric          | all         | 19      | 11      | 10        | 0.526       | 0.909    | 0.667 | 1.000           |

Facts no item matched: 15; items matching no fact: 12.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 26                     | 0.923                  | 1.000                     | 0.923             | 1.000             | 0.846          | 11        | 1.000       |
| all         | 26                     | 0.923                  | 1.000                     | 0.923             | 1.000             | 0.846          | 11        | 1.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |
| rag-baseline    | mixed   | mixed      | yes             | 11        | 11           | 0.545                | 0.545          | 1.000               | 1.000          |
| agent-baseline  | mixed   | mixed      | yes             | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| distributed | agent-baseline  | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| distributed | evidence-engine | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |
| distributed | rag-baseline    | 11        | 11           | 0.545                | 0.545          | 1.000               | 1.000          |

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
| condition       | 0.839 [0.76, 0.91] | BCa      |
| metric          | 0.667 [0.44, 0.79] | BCa      |
| measurement     | 0.881 [0.77, 0.97] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.844 [0.75, 0.90] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.909 [0.61, 1.00]   | BCa      | -                     | -               |
| rag-baseline    | 0.545 [0.27, 0.82]   | BCa      | 0.364 [-0.09, 0.73]   | BCa             |
| agent-baseline  | 1.000 [n/a]          | -        | -0.091 [-0.39, 0.00]  | BCa             |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | distributed | 260          | 260      | 1.000    |
| all             | all         | 260          | 260      | 1.000    |
| author_claim    | distributed | 22           | 22       | 1.000    |
| author_claim    | all         | 22           | 22       | 1.000    |
| condition       | distributed | 144          | 144      | 1.000    |
| condition       | all         | 144          | 144      | 1.000    |
| measurement     | distributed | 33           | 33       | 1.000    |
| measurement     | all         | 33           | 33       | 1.000    |
| metric          | distributed | 61           | 61       | 1.000    |
| metric          | all         | 61           | 61       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 0       | 0               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 13      | 13              | 12     | 12             |
| llm_measurement@1#5212fc43026f    | 26      | 26              | 26     | 26             |
| llm_metric@1#1ca12a572ef8         | 0       | 0               | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 11     | 11             |
| regex_condition@2#80486860164a    | 17      | 14              | 16     | 13             |
| regex_measurement@2#9edb306c5b05  | 0       | 0               | 0      | 0              |
| regex_metric@2#67f41f33eff7       | 19      | 10              | 19     | 10             |

Facts no extractor found: condition 7, measurement 7, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | all             | all     | 0       | 88      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 13      | 14      | 13        | 1.000       | 0.929    | 0.963 | 1.000           | -                      | 12     | 12             |
| llm_condition@1#134ab1a38338      | all             | all     | 13      | 14      | 13        | 1.000       | 0.929    | 0.963 | 1.000           | -                      | 12     | 12             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 26      | 33      | 26        | 1.000       | 0.788    | 0.881 | 1.000           | 0.923                  | 26     | 26             |
| llm_measurement@1#5212fc43026f    | all             | all     | 26      | 33      | 26        | 1.000       | 0.788    | 0.881 | 1.000           | -                      | 26     | 26             |
| llm_metric@1#1ca12a572ef8         | all             | all     | 0       | 88      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_condition@2#80486860164a    | condition       | all     | 17      | 33      | 14        | 0.824       | 0.424    | 0.560 | 0.714           | -                      | 16     | 13             |
| regex_condition@2#80486860164a    | all             | all     | 17      | 33      | 14        | 0.824       | 0.424    | 0.560 | 0.714           | -                      | 16     | 13             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 0       | 33      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 0       | 33      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 19      | 11      | 10        | 0.526       | 0.909    | 0.667 | 1.000           | -                      | 19     | 10             |
| regex_metric@2#67f41f33eff7       | all             | all     | 19      | 11      | 10        | 0.526       | 0.909    | 0.667 | 1.000           | -                      | 19     | 10             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#134ab1a38338      | 5       | 8             | 13340          | 1351            | 38.283    |
| llm_measurement@1#5212fc43026f    | 11      | 28            | 47829          | 3841            | 110.470   |
| llm_screen@1#6bec6abaf6a0         | 11      | 11            | 16305          | 1089            | 0.075     |
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.071     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.074     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.071     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.074     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.085     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 66      | 6.000       |
| calls            | 82      | 7.455       |
| input_tokens     | 77474   | 7043.091    |
| made_model_calls | 36      | 3.273       |
| model_calls      | 47      | 4.273       |
| output_tokens    | 6281    | 571.000     |
| seconds          | 149.956 | 13.632      |

## Funnel

Strategy `gaps` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.455          |
| model_calls   | 4.273          |
| input_tokens  | 7043.091       |
| output_tokens | 571.000        |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 11          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
