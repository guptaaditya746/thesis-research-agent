# Evaluation of run rag-llm-s1-complex on rag-llm-s1-a2b5bbc1

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 118     | 242     | 111       | 0.941       | 0.459    | 0.617 | 0.928           |
| all             | all     | 118     | 242     | 111       | 0.941       | 0.459    | 0.617 | 0.928           |
| author_claim    | complex | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 18      | 33      | 18        | 1.000       | 0.545    | 0.706 | 0.556           |
| condition       | all     | 18      | 33      | 18        | 1.000       | 0.545    | 0.706 | 0.556           |
| measurement     | complex | 55      | 170     | 55        | 1.000       | 0.324    | 0.489 | 1.000           |
| measurement     | all     | 55      | 170     | 55        | 1.000       | 0.324    | 0.489 | 1.000           |
| metric          | complex | 34      | 28      | 27        | 0.794       | 0.964    | 0.871 | 1.000           |
| metric          | all     | 34      | 28      | 27        | 0.794       | 0.964    | 0.871 | 1.000           |

Facts no item matched: 131; items matching no fact: 7.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 55                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 11        | 0.000       |
| all     | 55                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 11        | 0.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 11        | 11           | 0.273                | 0.273          | 1.000               | -              |
| rag-baseline    | refuted | mixed      | no              | 11        | 11           | 0.182                | 0.545          | 0.333               | 1.000          |
| agent-baseline  | mixed   | mixed      | yes             | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| complex | agent-baseline  | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| complex | evidence-engine | 11        | 11           | 0.273                | 0.273          | 1.000               | -              |
| complex | rag-baseline    | 11        | 11           | 0.182                | 0.545          | 0.333               | 1.000          |

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
| condition       | 0.706 [0.60, 0.80] | BCa      |
| metric          | 0.871 [0.80, 0.94] | BCa      |
| measurement     | 0.489 [0.30, 0.63] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.617 [0.49, 0.72] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.273 [0.09, 0.55]   | BCa      | -                     | -               |
| rag-baseline    | 0.182 [0.00, 0.55]   | BCa      | 0.091 [-0.18, 0.36]   | BCa             |
| agent-baseline  | 1.000 [n/a]          | -        | -0.727 [-0.91, -0.45] | BCa             |

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
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 11     | 11             |
| regex_condition@2#80486860164a    | 18      | 18              | 18     | 18             |
| regex_measurement@2#9edb306c5b05  | 55      | 55              | 55     | 55             |
| regex_metric@2#67f41f33eff7       | 34      | 27              | 34     | 27             |

Facts no extractor found: condition 15, measurement 115, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_condition@2#80486860164a    | condition       | all     | 18      | 33      | 18        | 1.000       | 0.545    | 0.706 | 0.556           | -                      | 18     | 18             |
| regex_condition@2#80486860164a    | all             | all     | 18      | 33      | 18        | 1.000       | 0.545    | 0.706 | 0.556           | -                      | 18     | 18             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 55      | 170     | 55        | 1.000       | 0.324    | 0.489 | 1.000           | 1.000                  | 55     | 55             |
| regex_measurement@2#9edb306c5b05  | all             | all     | 55      | 170     | 55        | 1.000       | 0.324    | 0.489 | 1.000           | -                      | 55     | 55             |
| regex_metric@2#67f41f33eff7       | metric          | all     | 34      | 28      | 27        | 0.794       | 0.964    | 0.871 | 1.000           | -                      | 34     | 27             |
| regex_metric@2#67f41f33eff7       | all             | all     | 34      | 28      | 27        | 0.794       | 0.964    | 0.871 | 1.000           | -                      | 34     | 27             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.172     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.153     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.189     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.153     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.147     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 55      | 5.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 1.303   | 0.118       |

## Funnel

Strategy `all` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 5.000          |
| model_calls   | 0.000          |
| input_tokens  | 0.000          |
| output_tokens | 0.000          |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 11          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
