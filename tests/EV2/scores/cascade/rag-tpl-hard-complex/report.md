# Evaluation of run rag-tpl-hard-complex on rag-tpl-hard-24ab4663

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 1403    | 2469    | 1373      | 0.979       | 0.556    | 0.709 | 1.000           |
| all             | all     | 1403    | 2469    | 1373      | 0.979       | 0.556    | 0.709 | 1.000           |
| author_claim    | complex | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 207     | 332     | 196       | 0.947       | 0.590    | 0.727 | 1.000           |
| condition       | all     | 207     | 332     | 196       | 0.947       | 0.590    | 0.727 | 1.000           |
| measurement     | complex | 859     | 1768    | 844       | 0.983       | 0.477    | 0.643 | 1.000           |
| measurement     | all     | 859     | 1768    | 844       | 0.983       | 0.477    | 0.643 | 1.000           |
| metric          | complex | 231     | 263     | 227       | 0.983       | 0.863    | 0.919 | 1.000           |
| metric          | all     | 231     | 263     | 227       | 0.983       | 0.863    | 0.919 | 1.000           |

Facts no item matched: 1096; items matching no fact: 30.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 844                    | 0.981                  | 0.981                     | 1.000             | 0.981             | 0.988          | 100       | 0.000       |
| all     | 844                    | 0.981                  | 0.981                     | 1.000             | 0.981             | 0.988          | 100       | 0.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 112       | 100          | 0.321                | 0.340          | 0.706               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 112       | 100          | 0.143                | 0.060          | 0.833               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 112       | 100          | 0.946                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| complex | agent-baseline  | 112       | 100          | 0.946                | 1.000          | 1.000               | -              | -         |
| complex | evidence-engine | 112       | 100          | 0.321                | 0.340          | 0.706               | -              | -         |
| complex | rag-baseline    | 112       | 100          | 0.143                | 0.060          | 0.833               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 10   | 0    | 0.000       | -        |
| evidence-engine | duplicate       | 0    | 0    | 6    | -           | 0.000    |
| evidence-engine | large_effect    | 2    | 4    | 4    | 0.333       | 0.333    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | no                   |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level   | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | complex | 112       | 36               | 92               | 56         | 20           |
| evidence-engine | all     | 112       | 36               | 92               | 56         | 20           |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.727 [0.69, 0.76] | BCa      |
| metric          | 0.919 [0.90, 0.94] | BCa      |
| measurement     | 0.643 [0.59, 0.70] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.709 [0.67, 0.75] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.321 [0.23, 0.41]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.143 [0.09, 0.21]   | BCa      | 0.179 [0.10, 0.26]    | BCa             | 112        |
| agent-baseline  | 0.946 [0.89, 0.98]   | BCa      | -0.625 [-0.73, -0.51] | BCa             | 112        |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 4323         | 4323     | 1.000    |
| all             | all     | 4323         | 4323     | 1.000    |
| author_claim    | complex | 212          | 212      | 1.000    |
| author_claim    | all     | 212          | 212      | 1.000    |
| condition       | complex | 1454         | 1454     | 1.000    |
| condition       | all     | 1454         | 1454     | 1.000    |
| measurement     | complex | 1768         | 1768     | 1.000    |
| measurement     | all     | 1768         | 1768     | 1.000    |
| metric          | complex | 889          | 889      | 1.000    |
| metric          | all     | 889          | 889      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20              | 0      | 0              |
| llm_condition@1#45b3761c700e      | 68      | 65              | 42     | 39             |
| llm_measurement@1#02bd5a7ab104    | 318     | 308             | 72     | 62             |
| llm_metric@1#41e1e53a1fc4         | 52      | 52              | 14     | 14             |
| regex_author_claim@2#fd7877790c48 | 106     | 106             | 86     | 86             |
| regex_condition@2#0a5bf730763c    | 165     | 157             | 139    | 131            |
| regex_measurement@2#e2d17eb260ea  | 787     | 782             | 541    | 536            |
| regex_metric@2#0affe2d9ce77       | 217     | 213             | 179    | 175            |

Facts no extractor found: condition 136, measurement 924, metric 36

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 20      | 106     | 20        | 1.000       | 0.189    | 0.317 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 20      | 106     | 20        | 1.000       | 0.189    | 0.317 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 68      | 332     | 65        | 0.956       | 0.196    | 0.325 | 1.000           | -                      | 42     | 39             |
| llm_condition@1#45b3761c700e      | all             | all     | 68      | 332     | 65        | 0.956       | 0.196    | 0.325 | 1.000           | -                      | 42     | 39             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 318     | 1768    | 308       | 0.969       | 0.174    | 0.295 | 1.000           | 0.948                  | 72     | 62             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 318     | 1768    | 308       | 0.969       | 0.174    | 0.295 | 1.000           | -                      | 72     | 62             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 52      | 263     | 52        | 1.000       | 0.198    | 0.330 | 1.000           | -                      | 14     | 14             |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 52      | 263     | 52        | 1.000       | 0.198    | 0.330 | 1.000           | -                      | 14     | 14             |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 86     | 86             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 86     | 86             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 165     | 332     | 157       | 0.952       | 0.473    | 0.632 | 1.000           | -                      | 139    | 131            |
| regex_condition@2#0a5bf730763c    | all             | all     | 165     | 332     | 157       | 0.952       | 0.473    | 0.632 | 1.000           | -                      | 139    | 131            |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 787     | 1768    | 782       | 0.994       | 0.442    | 0.612 | 1.000           | 0.980                  | 541    | 536            |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 787     | 1768    | 782       | 0.994       | 0.442    | 0.612 | 1.000           | -                      | 541    | 536            |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 217     | 263     | 213       | 0.982       | 0.810    | 0.888 | 1.000           | -                      | 179    | 175            |
| regex_metric@2#0affe2d9ce77       | all             | all     | 217     | 263     | 213       | 0.982       | 0.810    | 0.888 | 1.000           | -                      | 179    | 175            |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 112     | 112           | 43232          | 4575            | 2.688     |
| llm_condition@1#45b3761c700e      | 112     | 129           | 67170          | 10343           | 2.716     |
| llm_measurement@1#02bd5a7ab104    | 112     | 132           | 79296          | 52620           | 3.979     |
| llm_metric@1#41e1e53a1fc4         | 112     | 120           | 58255          | 8358            | 2.737     |
| llm_screen@1#41b0d6e6793f         | 109     | 109           | 37827          | 3028            | 2.532     |
| regex_author_claim@2#fd7877790c48 | 112     | 0             | 0              | 0               | 1.085     |
| regex_condition@2#0a5bf730763c    | 112     | 0             | 0              | 0               | 0.870     |
| regex_measurement@2#e2d17eb260ea  | 112     | 0             | 0              | 0               | 1.009     |
| regex_metric@2#0affe2d9ce77       | 112     | 0             | 0              | 0               | 0.864     |
| regex_screen@1#858a6ebc69c6       | 112     | 0             | 0              | 0               | 0.850     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 663     | 5.920       |
| calls            | 1117    | 9.973       |
| input_tokens     | 191221  | 1707.330    |
| made_model_calls | 454     | 4.054       |
| model_calls      | 602     | 5.375       |
| output_tokens    | 66895   | 597.277     |
| seconds          | 26.455  | 0.236       |

## Funnel

Strategy `all` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 9.973          |
| model_calls   | 5.375          |
| input_tokens  | 2551.607       |
| output_tokens | 704.679        |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 112         |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 3    | 0    | 3    | 0.972       | 1.000    |

Screened out wrongly: none
