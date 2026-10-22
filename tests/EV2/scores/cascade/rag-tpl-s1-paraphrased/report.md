# Evaluation of run rag-tpl-s1-paraphrased on rag-tpl-s1-4d15ddc4

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: paraphrased

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | paraphrased | 157     | 162     | 155       | 0.987       | 0.957    | 0.972 | 1.000           |
| all             | all         | 157     | 162     | 155       | 0.987       | 0.957    | 0.972 | 1.000           |
| author_claim    | paraphrased | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased | 61      | 61      | 59        | 0.967       | 0.967    | 0.967 | 1.000           |
| condition       | all         | 61      | 61      | 59        | 0.967       | 0.967    | 0.967 | 1.000           |
| measurement     | paraphrased | 57      | 61      | 57        | 1.000       | 0.934    | 0.966 | 1.000           |
| measurement     | all         | 57      | 61      | 57        | 1.000       | 0.934    | 0.966 | 1.000           |
| metric          | paraphrased | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           |
| metric          | all         | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           |

Facts no item matched: 7; items matching no fact: 2.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| paraphrased | 57                     | 0.965                  | 0.965                     | 1.000             | 0.965             | 1.000          | 20        | 0.950       |
| all         | 57                     | 0.965                  | 0.965                     | 1.000             | 0.965             | 1.000          | 20        | 0.950       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.950                | 0.950          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| paraphrased | evidence-engine | 20        | 20           | 0.950                | 0.950          | 1.000               | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level       | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|-------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | paraphrased | 20        | 19               | 20               | 1          | 0            |
| evidence-engine | all         | 20        | 19               | 20               | 1          | 0            |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.967 [0.84, 1.00] | BCa      |
| metric          | 0.974 [0.86, 1.00] | BCa      |
| measurement     | 0.966 [0.84, 1.00] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.972 [0.91, 1.00] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.950 [0.75, 1.00]   | BCa      | -                     | -               | -          |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | paraphrased | 344          | 344      | 1.000    |
| all             | all         | 344          | 344      | 1.000    |
| author_claim    | paraphrased | 40           | 40       | 1.000    |
| author_claim    | all         | 40           | 40       | 1.000    |
| condition       | paraphrased | 162          | 162      | 1.000    |
| condition       | all         | 162          | 162      | 1.000    |
| measurement     | paraphrased | 61           | 61       | 1.000    |
| measurement     | all         | 61           | 61       | 1.000    |
| metric          | paraphrased | 81           | 81       | 1.000    |
| metric          | all         | 81           | 81       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20              | 0      | 0              |
| llm_condition@1#45b3761c700e      | 61      | 59              | 61     | 59             |
| llm_measurement@1#02bd5a7ab104    | 57      | 57              | 57     | 57             |
| llm_metric@1#41e1e53a1fc4         | 19      | 19              | 19     | 19             |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 0       | 0               | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | 0       | 0               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 0       | 0               | 0      | 0              |

Facts no extractor found: condition 2, measurement 4, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 61      | 61      | 59        | 0.967       | 0.967    | 0.967 | 1.000           | -                      | 61     | 59             |
| llm_condition@1#45b3761c700e      | all             | all     | 61      | 61      | 59        | 0.967       | 0.967    | 0.967 | 1.000           | -                      | 61     | 59             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 57      | 61      | 57        | 1.000       | 0.934    | 0.966 | 1.000           | 0.965                  | 57     | 57             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 57      | 61      | 57        | 1.000       | 0.934    | 0.966 | 1.000           | -                      | 57     | 57             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           | -                      | 19     | 19             |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           | -                      | 19     | 19             |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 0       | 20      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 0       | 20      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20            | 16789          | 2366            | 51.115    |
| llm_condition@1#45b3761c700e      | 20      | 40            | 37545          | 7123            | 146.453   |
| llm_measurement@1#02bd5a7ab104    | 20      | 40            | 48239          | 14003           | 277.064   |
| llm_metric@1#41e1e53a1fc4         | 20      | 20            | 18869          | 1774            | 39.962    |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 14569          | 1494            | 34.371    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.145     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.140     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.300     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.142     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.150     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 104     | 5.200       |
| calls            | 200     | 10.000      |
| input_tokens     | 136011  | 6800.550    |
| made_model_calls | 112     | 5.600       |
| model_calls      | 140     | 7.000       |
| output_tokens    | 26760   | 1338.000    |
| seconds          | 551.109 | 27.555      |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 7.000          |
| input_tokens  | 6800.550       |
| output_tokens | 1338.000       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
