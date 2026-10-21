# Evaluation of run rag-llm-s1-explicit on rag-llm-s1-5848c762

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: explicit

## A. Extraction

| evidence_type   | level    | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|----------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit | 78      | 88      | 65        | 0.833       | 0.739    | 0.783 | 0.923           |
| all             | all      | 78      | 88      | 65        | 0.833       | 0.739    | 0.783 | 0.923           |
| author_claim    | explicit | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all      | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit | 23      | 33      | 22        | 0.957       | 0.667    | 0.786 | 0.773           |
| condition       | all      | 23      | 33      | 22        | 0.957       | 0.667    | 0.786 | 0.773           |
| measurement     | explicit | 24      | 33      | 22        | 0.917       | 0.667    | 0.772 | 1.000           |
| measurement     | all      | 24      | 33      | 22        | 0.917       | 0.667    | 0.772 | 1.000           |
| metric          | explicit | 20      | 11      | 10        | 0.500       | 0.909    | 0.645 | 1.000           |
| metric          | all      | 20      | 11      | 10        | 0.500       | 0.909    | 0.645 | 1.000           |

Facts no item matched: 23; items matching no fact: 13.

## B. Integration

| level    | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|----------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit | 22                     | 0.909                  | 1.000                     | 0.909             | 1.000             | 0.818          | 11        | 1.000       |
| all      | 22                     | 0.909                  | 1.000                     | 0.909             | 1.000             | 0.818          | 11        | 1.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |
| rag-baseline    | refuted | mixed      | no              | 11        | 11           | 0.273                | 0.273          | 1.000               | 1.000          |
| agent-baseline  | mixed   | mixed      | yes             | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level    | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|----------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit | agent-baseline  | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |
| explicit | evidence-engine | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |
| explicit | rag-baseline    | 11        | 11           | 0.273                | 0.273          | 1.000               | 1.000          |

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
| condition       | 0.786 [0.71, 0.86] | BCa      |
| metric          | 0.645 [0.49, 0.79] | BCa      |
| measurement     | 0.772 [0.70, 0.85] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.783 [0.72, 0.86] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.909 [0.61, 1.00]   | BCa      | -                     | -               |
| rag-baseline    | 0.273 [0.09, 0.64]   | BCa      | 0.636 [0.27, 0.91]    | BCa             |
| agent-baseline  | 0.909 [0.63, 1.00]   | BCa      | 0.000 [-0.27, 0.27]   | BCa             |

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
| llm_author_claim@1#fefdf4416c50   | 0       | 0               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 5       | 5               | 5      | 5              |
| llm_measurement@1#5212fc43026f    | 12      | 12              | 10     | 10             |
| llm_metric@1#1ca12a572ef8         | 0       | 0               | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 11     | 11             |
| regex_condition@2#80486860164a    | 18      | 17              | 18     | 17             |
| regex_measurement@2#9edb306c5b05  | 14      | 12              | 12     | 10             |
| regex_metric@2#67f41f33eff7       | 20      | 10              | 20     | 10             |

Facts no extractor found: condition 11, measurement 11, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | all             | all     | 0       | 88      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 5       | 11      | 5         | 1.000       | 0.455    | 0.625 | 1.000           | -                      | 5      | 5              |
| llm_condition@1#134ab1a38338      | all             | all     | 5       | 11      | 5         | 1.000       | 0.455    | 0.625 | 1.000           | -                      | 5      | 5              |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 12      | 18      | 12        | 1.000       | 0.667    | 0.800 | 1.000           | 0.833                  | 10     | 10             |
| llm_measurement@1#5212fc43026f    | all             | all     | 12      | 18      | 12        | 1.000       | 0.667    | 0.800 | 1.000           | -                      | 10     | 10             |
| llm_metric@1#1ca12a572ef8         | all             | all     | 0       | 88      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_condition@2#80486860164a    | condition       | all     | 18      | 33      | 17        | 0.944       | 0.515    | 0.667 | 0.706           | -                      | 18     | 17             |
| regex_condition@2#80486860164a    | all             | all     | 18      | 33      | 17        | 0.944       | 0.515    | 0.667 | 0.706           | -                      | 18     | 17             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 14      | 33      | 12        | 0.857       | 0.364    | 0.511 | 1.000           | 1.000                  | 12     | 10             |
| regex_measurement@2#9edb306c5b05  | all             | all     | 14      | 33      | 12        | 0.857       | 0.364    | 0.511 | 1.000           | -                      | 12     | 10             |
| regex_metric@2#67f41f33eff7       | metric          | all     | 20      | 11      | 10        | 0.500       | 0.909    | 0.645 | 1.000           | -                      | 20     | 10             |
| regex_metric@2#67f41f33eff7       | all             | all     | 20      | 11      | 10        | 0.500       | 0.909    | 0.645 | 1.000           | -                      | 20     | 10             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#134ab1a38338      | 4       | 6             | 7206           | 548             | 16.686    |
| llm_measurement@1#5212fc43026f    | 6       | 12            | 17471          | 2473            | 66.094    |
| llm_screen@1#6bec6abaf6a0         | 11      | 11            | 11771          | 972             | 0.073     |
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.073     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.072     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.074     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.074     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.075     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 66      | 6.000       |
| calls            | 76      | 6.909       |
| input_tokens     | 36448   | 3313.455    |
| made_model_calls | 18      | 1.636       |
| model_calls      | 29      | 2.636       |
| output_tokens    | 3993    | 363.000     |
| seconds          | 83.854  | 7.623       |

## Funnel

Strategy `gaps` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 6.909          |
| model_calls   | 2.636          |
| input_tokens  | 3313.455       |
| output_tokens | 363.000        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 5           |
| 1               | 6           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
