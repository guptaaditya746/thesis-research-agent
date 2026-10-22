# Evaluation of run rag-tpl-s1-complex-escalate on rag-tpl-s1-f0f5d48e

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 288     | 431     | 277       | 0.962       | 0.643    | 0.771 | 1.000           |
| all             | all     | 288     | 431     | 277       | 0.962       | 0.643    | 0.771 | 1.000           |
| author_claim    | complex | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 41      | 61      | 41        | 1.000       | 0.672    | 0.804 | 1.000           |
| condition       | all     | 41      | 61      | 41        | 1.000       | 0.672    | 0.804 | 1.000           |
| measurement     | complex | 177     | 300     | 166       | 0.938       | 0.553    | 0.696 | 1.000           |
| measurement     | all     | 177     | 300     | 166       | 0.938       | 0.553    | 0.696 | 1.000           |
| metric          | complex | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all     | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 154; items matching no fact: 11.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 166                    | 0.825                  | 0.861                     | 0.964             | 0.861             | 0.964          | 20        | 0.000       |
| all     | 166                    | 0.825                  | 0.861                     | 0.964             | 0.861             | 0.964          | 20        | 0.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| complex | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

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

| system          | level   | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | complex | 20        | 20               | 20               | 0          | 0            |
| evidence-engine | all     | 20        | 20               | 20               | 0          | 0            |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.804 [0.74, 0.87] | BCa      |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 0.696 [0.60, 0.78] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.771 [0.70, 0.82] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               | -          |

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
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 15      | 15              | 13     | 13             |
| llm_measurement@1#02bd5a7ab104    | 97      | 90              | 78     | 71             |
| llm_metric@1#41e1e53a1fc4         | 5       | 5               | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 20     | 20             |
| regex_condition@2#0a5bf730763c    | 28      | 28              | 26     | 26             |
| regex_measurement@2#e2d17eb260ea  | 99      | 95              | 80     | 76             |
| regex_metric@2#0affe2d9ce77       | 48      | 48              | 45     | 45             |

Facts no extractor found: condition 20, measurement 134

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 431     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 15      | 30      | 15        | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 13     | 13             |
| llm_condition@1#45b3761c700e      | all             | all     | 15      | 30      | 15        | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 13     | 13             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 97      | 218     | 90        | 0.928       | 0.413    | 0.571 | 1.000           | 0.822                  | 78     | 71             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 97      | 218     | 90        | 0.928       | 0.413    | 0.571 | 1.000           | -                      | 78     | 71             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 26     | 26             |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 26     | 26             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 99      | 300     | 95        | 0.960       | 0.317    | 0.476 | 1.000           | 0.863                  | 80     | 76             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 99      | 300     | 95        | 0.960       | 0.317    | 0.476 | 1.000           | -                      | 80     | 76             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 48      | 50      | 48        | 1.000       | 0.960    | 0.980 | 1.000           | -                      | 45     | 45             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 48      | 50      | 48        | 1.000       | 0.960    | 0.980 | 1.000           | -                      | 45     | 45             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 10      | 19            | 20512          | 1719            | 49.556    |
| llm_measurement@1#02bd5a7ab104    | 15      | 30            | 43467          | 16015           | 401.599   |
| llm_metric@1#41e1e53a1fc4         | 2       | 3             | 3587           | 468             | 12.673    |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 17726          | 1400            | 41.719    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.313     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.312     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.354     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.302     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.296     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 147     | 7.350       |
| input_tokens     | 85292   | 4264.600    |
| made_model_calls | 72      | 3.600       |
| model_calls      | 72      | 3.600       |
| output_tokens    | 19602   | 980.100     |
| seconds          | 508.417 | 25.421      |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.350          |
| model_calls   | 3.600          |
| input_tokens  | 4264.600       |
| output_tokens | 980.100        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 5           |
| 1               | 15          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
