# Evaluation of run rag-claude-s1-explicit on rag-claude-s1-eb14377d

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: explicit

## A. Extraction

| evidence_type   | level    | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|----------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit | 185     | 162     | 158       | 0.854       | 0.975    | 0.911 | 1.000           |
| all             | all      | 185     | 162     | 158       | 0.854       | 0.975    | 0.911 | 1.000           |
| author_claim    | explicit | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit | 67      | 61      | 57        | 0.851       | 0.934    | 0.891 | 1.000           |
| condition       | all      | 67      | 61      | 57        | 0.851       | 0.934    | 0.891 | 1.000           |
| measurement     | explicit | 69      | 61      | 61        | 0.884       | 1.000    | 0.938 | 1.000           |
| measurement     | all      | 69      | 61      | 61        | 0.884       | 1.000    | 0.938 | 1.000           |
| metric          | explicit | 29      | 20      | 20        | 0.690       | 1.000    | 0.816 | 1.000           |
| metric          | all      | 29      | 20      | 20        | 0.690       | 1.000    | 0.816 | 1.000           |

Facts no item matched: 4; items matching no fact: 27.

## B. Integration

| level    | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|----------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit | 61                     | 0.934                  | 0.934                     | 1.000             | 0.885             | 0.951          | 20        | 0.750       |
| all      | 61                     | 0.934                  | 0.934                     | 1.000             | 0.885             | 0.951          | 20        | 0.750       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 20        | 20           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level    | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|----------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit | agent-baseline  | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit | rag-baseline    | 20        | 20           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | yes              | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level    | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|----------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit | 20        | 20               | 20               | 0          | 0            |
| evidence-engine | all      | 20        | 20               | 20               | 0          | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.891 [0.78, 0.95] | BCa      |
| metric          | 0.816 [0.73, 0.89] | BCa      |
| measurement     | 0.938 [0.90, 0.97] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.911 [0.86, 0.94] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               | -          |
| rag-baseline    | 0.350 [0.15, 0.60]   | BCa      | 0.650 [0.40, 0.85]    | BCa             | 20         |
| agent-baseline  | 1.000 [n/a]          | -        | 0.000 [n/a]           | -               | 20         |

## Locate recall

| evidence_type   | level    | placements   | inside   | recall   |
|-----------------|----------|--------------|----------|----------|
| all             | explicit | 417          | 417      | 1.000    |
| all             | all      | 417          | 417      | 1.000    |
| author_claim    | explicit | 40           | 40       | 1.000    |
| author_claim    | all      | 40           | 40       | 1.000    |
| condition       | explicit | 172          | 172      | 1.000    |
| condition       | all      | 172          | 172      | 1.000    |
| measurement     | explicit | 61           | 61       | 1.000    |
| measurement     | all      | 61           | 61       | 1.000    |
| metric          | explicit | 144          | 144      | 1.000    |
| metric          | all      | 144          | 144      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20              | 0      | 0              |
| llm_condition@1#45b3761c700e      | 61      | 57              | 39     | 35             |
| llm_measurement@1#02bd5a7ab104    | 61      | 56              | 45     | 40             |
| llm_metric@1#41e1e53a1fc4         | 19      | 19              | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 28      | 22              | 6      | 0              |
| regex_measurement@2#e2d17eb260ea  | 24      | 21              | 8      | 5              |
| regex_metric@2#0affe2d9ce77       | 22      | 13              | 10     | 1              |

Facts no extractor found: condition 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           | -                      | 39     | 35             |
| llm_condition@1#45b3761c700e      | all             | all     | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           | -                      | 39     | 35             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 61      | 61      | 56        | 0.918       | 0.918    | 0.918 | 1.000           | 0.929                  | 45     | 40             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 61      | 61      | 56        | 0.918       | 0.918    | 0.918 | 1.000           | -                      | 45     | 40             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 22        | 0.786       | 0.361    | 0.494 | 1.000           | -                      | 6      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 22        | 0.786       | 0.361    | 0.494 | 1.000           | -                      | 6      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 24      | 61      | 21        | 0.875       | 0.344    | 0.494 | 1.000           | 1.000                  | 8      | 5              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 24      | 61      | 21        | 0.875       | 0.344    | 0.494 | 1.000           | -                      | 8      | 5              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 22      | 20      | 13        | 0.591       | 0.650    | 0.619 | 1.000           | -                      | 10     | 1              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 22      | 20      | 13        | 0.591       | 0.650    | 0.619 | 1.000           | -                      | 10     | 1              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20            | 19144          | 2382            | 39.034    |
| llm_condition@1#45b3761c700e      | 20      | 27            | 27719          | 4978            | 75.913    |
| llm_measurement@1#02bd5a7ab104    | 20      | 40            | 52386          | 12265           | 173.529   |
| llm_metric@1#41e1e53a1fc4         | 20      | 23            | 24032          | 1988            | 33.501    |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 16924          | 1551            | 27.328    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.143     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.140     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.257     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.144     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.138     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 128     | 6.400       |
| calls            | 200     | 10.000      |
| input_tokens     | 140205  | 7010.250    |
| made_model_calls | 78      | 3.900       |
| model_calls      | 130     | 6.500       |
| output_tokens    | 23164   | 1158.200    |
| seconds          | 351.325 | 17.566      |

## Re-execution stability

| extractor          | calls   | identical   | identical_share   | item_stability   |
|--------------------|---------|-------------|-------------------|------------------|
| llm_author_claim   | 20      | 20          | 1.000             | 1.000            |
| llm_condition      | 20      | 20          | 1.000             | 1.000            |
| llm_measurement    | 20      | 20          | 1.000             | 1.000            |
| llm_metric         | 20      | 20          | 1.000             | 1.000            |
| llm_screen         | 20      | 18          | 0.900             | 0.900            |
| regex_author_claim | 20      | 20          | 1.000             | 1.000            |
| regex_condition    | 20      | 20          | 1.000             | 1.000            |
| regex_measurement  | 20      | 20          | 1.000             | 1.000            |
| regex_metric       | 20      | 20          | 1.000             | 1.000            |
| regex_screen       | 20      | 20          | 1.000             | 1.000            |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.500          |
| input_tokens  | 7010.250       |
| output_tokens | 1158.200       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
