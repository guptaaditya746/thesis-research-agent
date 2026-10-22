# Evaluation of run rag-tpl-s1-complex on rag-tpl-s1-f0f5d48e

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 195     | 431     | 195       | 1.000       | 0.452    | 0.623 | 1.000           |
| all             | all     | 195     | 431     | 195       | 1.000       | 0.452    | 0.623 | 1.000           |
| author_claim    | complex | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           |
| condition       | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           |
| measurement     | complex | 99      | 300     | 99        | 1.000       | 0.330    | 0.496 | 1.000           |
| measurement     | all     | 99      | 300     | 99        | 1.000       | 0.330    | 0.496 | 1.000           |
| metric          | complex | 48      | 50      | 48        | 1.000       | 0.960    | 0.980 | 1.000           |
| metric          | all     | 48      | 50      | 48        | 1.000       | 0.960    | 0.980 | 1.000           |

Facts no item matched: 236; items matching no fact: 0.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 99                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.000       |
| all     | 99                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.250                | 0.250          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| complex | evidence-engine | 20        | 20           | 0.250                | 0.250          | 1.000               | -              | -         |

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

| system          | level   | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | complex | 20        | 5                | 20               | 15         | 0            |
| evidence-engine | all     | 20        | 5                | 20               | 15         | 0            |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.629 [0.52, 0.73] | BCa      |
| metric          | 0.980 [0.94, 1.00] | BCa      |
| measurement     | 0.496 [0.38, 0.60] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.623 [0.53, 0.70] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.250 [0.10, 0.50]   | BCa      | -                     | -               | -          |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 773          | 773      | 1.000    |
| all             | all     | 773          | 773      | 1.000    |
| author_claim    | complex | 40           | 40       | 1.000    |
| author_claim    | all     | 40           | 40       | 1.000    |
| condition       | complex | 263          | 263      | 1.000    |
| condition       | all     | 263          | 263      | 1.000    |
| measurement     | complex | 300          | 300      | 1.000    |
| measurement     | all     | 300          | 300      | 1.000    |
| metric          | complex | 170          | 170      | 1.000    |
| metric          | all     | 170          | 170      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 20     | 20             |
| regex_condition@2#0a5bf730763c    | 28      | 28              | 28     | 28             |
| regex_measurement@2#e2d17eb260ea  | 99      | 99              | 99     | 99             |
| regex_metric@2#0affe2d9ce77       | 48      | 48              | 48     | 48             |

Facts no extractor found: condition 33, measurement 201, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 28     | 28             |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 28     | 28             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 99      | 300     | 99        | 1.000       | 0.330    | 0.496 | 1.000           | 1.000                  | 99     | 99             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 99      | 300     | 99        | 1.000       | 0.330    | 0.496 | 1.000           | -                      | 99     | 99             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 48      | 50      | 48        | 1.000       | 0.960    | 0.980 | 1.000           | -                      | 48     | 48             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 48      | 50      | 48        | 1.000       | 0.960    | 0.980 | 1.000           | -                      | 48     | 48             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.304     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.273     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.347     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.290     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.274     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 100     | 5.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 2.643   | 0.132       |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 5.000          |
| model_calls   | 0.000          |
| input_tokens  | 0.000          |
| output_tokens | 0.000          |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
