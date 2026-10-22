# Evaluation of run rag-claude-s1-paraphrased-escalate on rag-claude-s1-c34803f0

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: paraphrased

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | paraphrased | 89      | 162     | 86        | 0.966       | 0.531    | 0.685 | 0.977           |
| all             | all         | 89      | 162     | 86        | 0.966       | 0.531    | 0.685 | 0.977           |
| author_claim    | paraphrased | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased | 34      | 61      | 32        | 0.941       | 0.525    | 0.674 | 1.000           |
| condition       | all         | 34      | 61      | 32        | 0.941       | 0.525    | 0.674 | 1.000           |
| measurement     | paraphrased | 25      | 61      | 25        | 1.000       | 0.410    | 0.581 | 1.000           |
| measurement     | all         | 25      | 61      | 25        | 1.000       | 0.410    | 0.581 | 1.000           |
| metric          | paraphrased | 10      | 20      | 9         | 0.900       | 0.450    | 0.600 | 0.778           |
| metric          | all         | 10      | 20      | 9         | 0.900       | 0.450    | 0.600 | 0.778           |

Facts no item matched: 76; items matching no fact: 3.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| paraphrased | 25                     | 0.920                  | 0.920                     | 1.000             | 0.920             | 1.000          | 20        | 0.450       |
| all         | 25                     | 0.920                  | 0.920                     | 1.000             | 0.920             | 1.000          | 20        | 0.450       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.450                | 0.450          | 1.000               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 20        | 20           | 0.200                | 0.400          | 0.500               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| paraphrased | agent-baseline  | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| paraphrased | evidence-engine | 20        | 20           | 0.450                | 0.450          | 1.000               | -              | -         |
| paraphrased | rag-baseline    | 20        | 20           | 0.200                | 0.400          | 0.500               | 1.000          | 1.000     |

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
| evidence-engine | paraphrased | 20        | 9                | 20               | 11         | 0            |
| evidence-engine | all         | 20        | 9                | 20               | 11         | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.674 [0.52, 0.80] | BCa      |
| metric          | 0.600 [0.38, 0.79] | BCa      |
| measurement     | 0.581 [0.33, 0.78] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.685 [0.53, 0.81] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.450 [0.25, 0.65]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.200 [0.05, 0.45]   | BCa      | 0.250 [0.00, 0.50]    | BCa             | 20         |
| agent-baseline  | 1.000 [n/a]          | -        | -0.550 [-0.75, -0.35] | BCa             | 20         |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | paraphrased | 368          | 368      | 1.000    |
| all             | all         | 368          | 368      | 1.000    |
| author_claim    | paraphrased | 40           | 40       | 1.000    |
| author_claim    | all         | 40           | 40       | 1.000    |
| condition       | paraphrased | 163          | 163      | 1.000    |
| condition       | all         | 163          | 163      | 1.000    |
| measurement     | paraphrased | 61           | 61       | 1.000    |
| measurement     | all         | 61           | 61       | 1.000    |
| metric          | paraphrased | 104          | 104      | 1.000    |
| metric          | all         | 104          | 104      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 34      | 32              | 34     | 32             |
| llm_measurement@1#02bd5a7ab104    | 25      | 25              | 25     | 25             |
| llm_metric@1#41e1e53a1fc4         | 7       | 7               | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 20     | 20             |
| regex_condition@2#0a5bf730763c    | 0       | 0               | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | 0       | 0               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 3       | 2               | 3      | 2              |

Facts no extractor found: condition 29, measurement 36, metric 11

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 162     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 34      | 61      | 32        | 0.941       | 0.525    | 0.674 | 1.000           | -                      | 34     | 32             |
| llm_condition@1#45b3761c700e      | all             | all     | 34      | 61      | 32        | 0.941       | 0.525    | 0.674 | 1.000           | -                      | 34     | 32             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 25      | 25      | 25        | 1.000       | 1.000    | 1.000 | 1.000           | 0.920                  | 25     | 25             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 25      | 25      | 25        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 25     | 25             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 7       | 7       | 7         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 7       | 7       | 7         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 3       | 20      | 2         | 0.667       | 0.100    | 0.174 | 0.000           | -                      | 3      | 2              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 3       | 20      | 2         | 0.667       | 0.100    | 0.174 | 0.000           | -                      | 3      | 2              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 20      | 31            | 35099          | 3367            | 75.249    |
| llm_measurement@1#02bd5a7ab104    | 9       | 18            | 24984          | 4930            | 86.290    |
| llm_metric@1#41e1e53a1fc4         | 7       | 7             | 8573           | 694             | 14.245    |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 18647          | 1724            | 40.428    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.267     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.263     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.247     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.266     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.261     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 33      | 1.650       |
| calls            | 156     | 7.800       |
| input_tokens     | 87303   | 4365.150    |
| made_model_calls | 59      | 2.950       |
| model_calls      | 76      | 3.800       |
| output_tokens    | 10715   | 535.750     |
| seconds          | 218.820 | 10.941      |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.800          |
| model_calls   | 3.800          |
| input_tokens  | 4365.150       |
| output_tokens | 535.750        |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 9           |
| exhausted       | 11          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
