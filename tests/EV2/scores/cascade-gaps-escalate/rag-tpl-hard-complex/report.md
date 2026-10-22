# Evaluation of run rag-tpl-hard-complex-escalate on rag-tpl-hard-24ab4663

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 1112    | 2469    | 1108      | 0.996       | 0.449    | 0.619 | 1.000           |
| all             | all     | 1112    | 2469    | 1108      | 0.996       | 0.449    | 0.619 | 1.000           |
| author_claim    | complex | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 165     | 332     | 162       | 0.982       | 0.488    | 0.652 | 1.000           |
| condition       | all     | 165     | 332     | 162       | 0.982       | 0.488    | 0.652 | 1.000           |
| measurement     | complex | 624     | 1768    | 624       | 1.000       | 0.353    | 0.522 | 1.000           |
| measurement     | all     | 624     | 1768    | 624       | 1.000       | 0.353    | 0.522 | 1.000           |
| metric          | complex | 217     | 263     | 216       | 0.995       | 0.821    | 0.900 | 1.000           |
| metric          | all     | 217     | 263     | 216       | 0.995       | 0.821    | 0.900 | 1.000           |

Facts no item matched: 1361; items matching no fact: 4.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 624                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 100       | 0.000       |
| all     | 624                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 100       | 0.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 112       | 100          | 0.205                | 0.170          | 0.647               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 112       | 100          | 0.143                | 0.060          | 0.833               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 112       | 100          | 0.946                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| complex | agent-baseline  | 112       | 100          | 0.946                | 1.000          | 1.000               | -              | -         |
| complex | evidence-engine | 112       | 100          | 0.205                | 0.170          | 0.647               | -              | -         |
| complex | rag-baseline    | 112       | 100          | 0.143                | 0.060          | 0.833               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 6    | 0    | 0.000       | -        |
| evidence-engine | duplicate       | 0    | 0    | 6    | -           | 0.000    |
| evidence-engine | large_effect    | 1    | 2    | 5    | 0.333       | 0.167    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | no                   |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level   | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | complex | 112       | 23               | 92               | 69         | 20           |
| evidence-engine | all     | 112       | 23               | 92               | 69         | 20           |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.652 [0.61, 0.69] | BCa      |
| metric          | 0.900 [0.88, 0.92] | BCa      |
| measurement     | 0.522 [0.48, 0.56] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.619 [0.59, 0.65] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.205 [0.14, 0.29]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.143 [0.09, 0.21]   | BCa      | 0.062 [0.00, 0.12]    | BCa             | 112        |
| agent-baseline  | 0.946 [0.89, 0.98]   | BCa      | -0.741 [-0.82, -0.62] | BCa             | 112        |

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
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 0       | 0               | 0      | 0              |
| llm_measurement@1#02bd5a7ab104    | 0       | 0               | 0      | 0              |
| llm_metric@1#41e1e53a1fc4         | 0       | 0               | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | 106     | 106             | 106    | 106            |
| regex_condition@2#0a5bf730763c    | 165     | 162             | 165    | 162            |
| regex_measurement@2#e2d17eb260ea  | 624     | 624             | 624    | 624            |
| regex_metric@2#0affe2d9ce77       | 217     | 216             | 217    | 216            |

Facts no extractor found: condition 170, measurement 1144, metric 47

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 2469    | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 0       | 137     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | all             | all     | 0       | 137     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 0       | 180     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 0       | 180     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 0       | 80      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 0       | 80      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_author_claim@2#fd7877790c48 | all             | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_condition@2#0a5bf730763c    | condition       | all     | 165     | 332     | 162       | 0.982       | 0.488    | 0.652 | 1.000           | -                      | 165    | 162            |
| regex_condition@2#0a5bf730763c    | all             | all     | 165     | 332     | 162       | 0.982       | 0.488    | 0.652 | 1.000           | -                      | 165    | 162            |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 624     | 1768    | 624       | 1.000       | 0.353    | 0.522 | 1.000           | 1.000                  | 624    | 624            |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 624     | 1768    | 624       | 1.000       | 0.353    | 0.522 | 1.000           | -                      | 624    | 624            |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 217     | 263     | 216       | 0.995       | 0.821    | 0.900 | 1.000           | -                      | 217    | 216            |
| regex_metric@2#0affe2d9ce77       | all             | all     | 217     | 263     | 216       | 0.995       | 0.821    | 0.900 | 1.000           | -                      | 217    | 216            |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 49      | 49            | 10235          | 1041            | 1.564     |
| llm_measurement@1#02bd5a7ab104    | 11      | 11            | 4098           | 1135            | 0.347     |
| llm_metric@1#41e1e53a1fc4         | 32      | 32            | 7660           | 930             | 0.913     |
| llm_screen@1#41b0d6e6793f         | 112     | 112           | 37827          | 3028            | 3.476     |
| regex_author_claim@2#fd7877790c48 | 109     | 0             | 0              | 0               | 1.675     |
| regex_condition@2#0a5bf730763c    | 109     | 0             | 0              | 0               | 1.557     |
| regex_measurement@2#e2d17eb260ea  | 109     | 0             | 0              | 0               | 1.926     |
| regex_metric@2#0affe2d9ce77       | 109     | 0             | 0              | 0               | 1.583     |
| regex_screen@1#858a6ebc69c6       | 112     | 0             | 0              | 0               | 1.508     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 752     | 6.714       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 204     | 1.821       |
| model_calls      | 204     | 1.821       |
| output_tokens    | 0       | 0.000       |
| seconds          | 20.672  | 0.185       |

## Funnel

Strategy `gaps` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 6.714          |
| model_calls   | 1.821          |
| input_tokens  | 534.107        |
| output_tokens | 54.768         |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 17          |
| exhausted       | 92          |
| skipped         | 3           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 3    | 0    | 3    | 0.972       | 1.000    |

Screened out wrongly: none
