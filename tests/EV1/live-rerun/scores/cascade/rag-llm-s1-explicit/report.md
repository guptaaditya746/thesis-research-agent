# Evaluation of run rag-llm-s1-explicit on rag-llm-s1-5848c762

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: explicit

## A. Extraction

| evidence_type   | level    | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|----------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit | 116     | 88      | 84        | 0.724       | 0.955    | 0.824 | 1.000           |
| all             | all      | 116     | 88      | 84        | 0.724       | 0.955    | 0.824 | 1.000           |
| author_claim    | explicit | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all      | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit | 41      | 33      | 29        | 0.707       | 0.879    | 0.784 | 1.000           |
| condition       | all      | 41      | 33      | 29        | 0.707       | 0.879    | 0.784 | 1.000           |
| measurement     | explicit | 39      | 33      | 33        | 0.846       | 1.000    | 0.917 | 1.000           |
| measurement     | all      | 39      | 33      | 33        | 0.846       | 1.000    | 0.917 | 1.000           |
| metric          | explicit | 25      | 11      | 11        | 0.440       | 1.000    | 0.611 | 1.000           |
| metric          | all      | 25      | 11      | 11        | 0.440       | 1.000    | 0.611 | 1.000           |

Facts no item matched: 4; items matching no fact: 32.

## B. Integration

| level    | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|----------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit | 33                     | 0.879                  | 0.879                     | 1.000             | 0.788             | 0.939          | 11        | 0.636       |
| all      | 33                     | 0.879                  | 0.879                     | 1.000             | 0.788             | 0.939          | 11        | 0.636       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| rag-baseline    | refuted | mixed      | no              | 11        | 11           | 0.273                | 0.273          | 1.000               | 1.000          |
| agent-baseline  | mixed   | mixed      | yes             | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level    | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|----------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit | agent-baseline  | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |
| explicit | evidence-engine | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| explicit | rag-baseline    | 11        | 11           | 0.273                | 0.273          | 1.000               | 1.000          |

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
| condition       | 0.784 [0.65, 0.87] | BCa      |
| metric          | 0.611 [0.52, 0.73] | BCa      |
| measurement     | 0.917 [0.87, 0.96] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.824 [0.77, 0.88] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |
| rag-baseline    | 0.273 [0.09, 0.64]   | BCa      | 0.727 [0.36, 0.91]    | BCa             |
| agent-baseline  | 0.909 [0.63, 1.00]   | BCa      | 0.091 [0.00, 0.37]    | BCa             |

## Locate recall

| evidence_type   | level    | placements   | inside   | recall   |
|-----------------|----------|--------------|----------|----------|
| all             | explicit | 287          | 287      | 1.000    |
| all             | all      | 287          | 287      | 1.000    |
| author_claim    | explicit | 22           | 22       | 1.000    |
| author_claim    | all      | 22           | 22       | 1.000    |
| condition       | explicit | 149          | 149      | 1.000    |
| condition       | all      | 149          | 149      | 1.000    |
| measurement     | explicit | 33           | 33       | 1.000    |
| measurement     | all      | 33           | 33       | 1.000    |
| metric          | explicit | 83           | 83       | 1.000    |
| metric          | all      | 83           | 83       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 11      | 11              | 0      | 0              |
| llm_condition@1#134ab1a38338      | 33      | 29              | 23     | 19             |
| llm_measurement@1#5212fc43026f    | 33      | 29              | 25     | 21             |
| llm_metric@1#1ca12a572ef8         | 11      | 11              | 5      | 5              |
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 0      | 0              |
| regex_condition@2#80486860164a    | 18      | 10              | 8      | 0              |
| regex_measurement@2#9edb306c5b05  | 14      | 12              | 6      | 4              |
| regex_metric@2#67f41f33eff7       | 20      | 6               | 14     | 0              |

Facts no extractor found: condition 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 33      | 33      | 29        | 0.879       | 0.879    | 0.879 | 1.000           | -                      | 23     | 19             |
| llm_condition@1#134ab1a38338      | all             | all     | 33      | 33      | 29        | 0.879       | 0.879    | 0.879 | 1.000           | -                      | 23     | 19             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 33      | 33      | 29        | 0.879       | 0.879    | 0.879 | 1.000           | 0.862                  | 25     | 21             |
| llm_measurement@1#5212fc43026f    | all             | all     | 33      | 33      | 29        | 0.879       | 0.879    | 0.879 | 1.000           | -                      | 25     | 21             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 5      | 5              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 5      | 5              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 18      | 33      | 10        | 0.556       | 0.303    | 0.392 | 1.000           | -                      | 8      | 0              |
| regex_condition@2#80486860164a    | all             | all     | 18      | 33      | 10        | 0.556       | 0.303    | 0.392 | 1.000           | -                      | 8      | 0              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 14      | 33      | 12        | 0.857       | 0.364    | 0.511 | 1.000           | 1.000                  | 6      | 4              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 14      | 33      | 12        | 0.857       | 0.364    | 0.511 | 1.000           | -                      | 6      | 4              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 20      | 11      | 6         | 0.300       | 0.545    | 0.387 | 1.000           | -                      | 14     | 0              |
| regex_metric@2#67f41f33eff7       | all             | all     | 20      | 11      | 6         | 0.300       | 0.545    | 0.387 | 1.000           | -                      | 14     | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 11      | 11            | 12992          | 1316            | 36.875    |
| llm_condition@1#134ab1a38338      | 11      | 16            | 20132          | 2801            | 75.219    |
| llm_measurement@1#5212fc43026f    | 11      | 21            | 32039          | 6607            | 170.920   |
| llm_metric@1#1ca12a572ef8         | 11      | 14            | 17375          | 1158            | 34.217    |
| llm_screen@1#6bec6abaf6a0         | 11      | 11            | 11771          | 972             | 28.779    |
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.075     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.077     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.185     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.077     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.073     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 44      | 4.000       |
| calls            | 110     | 10.000      |
| input_tokens     | 94309   | 8573.545    |
| made_model_calls | 73      | 6.636       |
| model_calls      | 73      | 6.636       |
| output_tokens    | 12854   | 1168.545    |
| seconds          | 347.186 | 31.562      |

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
| regex_measurement  | 11      | 11          | 1.000             | 1.000            |
| regex_metric       | 11      | 11          | 1.000             | 1.000            |
| regex_screen       | 11      | 11          | 1.000             | 1.000            |

## Funnel

Strategy `all` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.636          |
| input_tokens  | 8573.545       |
| output_tokens | 1168.545       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 11          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
