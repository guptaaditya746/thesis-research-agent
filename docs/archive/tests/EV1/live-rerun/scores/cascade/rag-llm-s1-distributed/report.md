# Evaluation of run rag-llm-s1-distributed on rag-llm-s1-d60fff2f

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 121     | 88      | 85        | 0.702       | 0.966    | 0.813 | 1.000           |
| all             | all         | 121     | 88      | 85        | 0.702       | 0.966    | 0.813 | 1.000           |
| author_claim    | distributed | 12      | 11      | 11        | 0.917       | 1.000    | 0.957 | 1.000           |
| author_claim    | all         | 12      | 11      | 11        | 0.917       | 1.000    | 0.957 | 1.000           |
| condition       | distributed | 50      | 33      | 30        | 0.600       | 0.909    | 0.723 | 1.000           |
| condition       | all         | 50      | 33      | 30        | 0.600       | 0.909    | 0.723 | 1.000           |
| measurement     | distributed | 33      | 33      | 33        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | all         | 33      | 33      | 33        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | distributed | 26      | 11      | 11        | 0.423       | 1.000    | 0.595 | 1.000           |
| metric          | all         | 26      | 11      | 11        | 0.423       | 1.000    | 0.595 | 1.000           |

Facts no item matched: 3; items matching no fact: 36.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 33                     | 0.909                  | 0.909                     | 1.000             | 0.727             | 0.879          | 11        | 1.000       |
| all         | 33                     | 0.909                  | 0.909                     | 1.000             | 0.727             | 0.879          | 11        | 1.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| rag-baseline    | mixed   | mixed      | yes             | 11        | 11           | 0.545                | 0.545          | 1.000               | 1.000          |
| agent-baseline  | mixed   | mixed      | yes             | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| distributed | agent-baseline  | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| distributed | evidence-engine | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| distributed | rag-baseline    | 11        | 11           | 0.545                | 0.545          | 1.000               | 1.000          |

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
| condition       | 0.723 [0.63, 0.81] | BCa      |
| metric          | 0.595 [0.52, 0.67] | BCa      |
| measurement     | 1.000 [n/a]        | -        |
| author_claim    | 0.957 [0.84, 1.00] | BCa      |
| all             | 0.813 [0.77, 0.85] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |
| rag-baseline    | 0.545 [0.27, 0.82]   | BCa      | 0.455 [0.18, 0.73]    | BCa             |
| agent-baseline  | 1.000 [n/a]          | -        | 0.000 [n/a]           | -               |

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
| llm_author_claim@1#fefdf4416c50   | 12      | 11              | 1      | 0              |
| llm_condition@1#134ab1a38338      | 39      | 28              | 33     | 22             |
| llm_measurement@1#5212fc43026f    | 33      | 33              | 33     | 33             |
| llm_metric@1#1ca12a572ef8         | 12      | 10              | 7      | 5              |
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 0      | 0              |
| regex_condition@2#80486860164a    | 17      | 8               | 11     | 2              |
| regex_measurement@2#9edb306c5b05  | 0       | 0               | 0      | 0              |
| regex_metric@2#67f41f33eff7       | 19      | 6               | 14     | 1              |

Facts no extractor found: condition 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 12      | 11      | 11        | 0.917       | 1.000    | 0.957 | 1.000           | -                      | 1      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 12      | 11      | 11        | 0.917       | 1.000    | 0.957 | 1.000           | -                      | 1      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 39      | 33      | 28        | 0.718       | 0.848    | 0.778 | 1.000           | -                      | 33     | 22             |
| llm_condition@1#134ab1a38338      | all             | all     | 39      | 33      | 28        | 0.718       | 0.848    | 0.778 | 1.000           | -                      | 33     | 22             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 33      | 33      | 33        | 1.000       | 1.000    | 1.000 | 1.000           | 0.909                  | 33     | 33             |
| llm_measurement@1#5212fc43026f    | all             | all     | 33      | 33      | 33        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 33     | 33             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 12      | 11      | 10        | 0.833       | 0.909    | 0.870 | 1.000           | -                      | 7      | 5              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 12      | 11      | 10        | 0.833       | 0.909    | 0.870 | 1.000           | -                      | 7      | 5              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 17      | 33      | 8         | 0.471       | 0.242    | 0.320 | 1.000           | -                      | 11     | 2              |
| regex_condition@2#80486860164a    | all             | all     | 17      | 33      | 8         | 0.471       | 0.242    | 0.320 | 1.000           | -                      | 11     | 2              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 0       | 33      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 0       | 33      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 19      | 11      | 6         | 0.316       | 0.545    | 0.400 | 1.000           | -                      | 14     | 1              |
| regex_metric@2#67f41f33eff7       | all             | all     | 19      | 11      | 6         | 0.316       | 0.545    | 0.400 | 1.000           | -                      | 14     | 1              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 11      | 17            | 25009          | 1455            | 44.688    |
| llm_condition@1#134ab1a38338      | 11      | 20            | 33005          | 3505            | 96.821    |
| llm_measurement@1#5212fc43026f    | 11      | 28            | 48523          | 4848            | 134.906   |
| llm_metric@1#1ca12a572ef8         | 11      | 18            | 29144          | 1350            | 43.122    |
| llm_screen@1#6bec6abaf6a0         | 11      | 11            | 16305          | 1089            | 33.176    |
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.076     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.077     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.229     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.078     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.079     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 44      | 4.000       |
| calls            | 110     | 10.000      |
| input_tokens     | 151986  | 13816.909   |
| made_model_calls | 94      | 8.545       |
| model_calls      | 94      | 8.545       |
| output_tokens    | 12247   | 1113.364    |
| seconds          | 354.012 | 32.183      |

## Re-execution stability

| extractor          | calls   | identical   | identical_share   | item_stability   |
|--------------------|---------|-------------|-------------------|------------------|
| llm_author_claim   | 11      | 11          | 1.000             | 1.000            |
| llm_condition      | 11      | 11          | 1.000             | 1.000            |
| llm_measurement    | 11      | 11          | 1.000             | 1.000            |
| llm_metric         | 11      | 11          | 1.000             | 1.000            |
| llm_screen         | 11      | 11          | 1.000             | 1.000            |
| regex_author_claim | 11      | 11          | 1.000             | 1.000            |
| regex_condition    | 11      | 11          | 1.000             | 1.000            |
| regex_measurement  | 11      | 11          | 1.000             | -                |
| regex_metric       | 11      | 11          | 1.000             | 1.000            |
| regex_screen       | 11      | 11          | 1.000             | 1.000            |

## Funnel

Strategy `all` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 8.545          |
| input_tokens  | 13816.909      |
| output_tokens | 1113.364       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 11          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
