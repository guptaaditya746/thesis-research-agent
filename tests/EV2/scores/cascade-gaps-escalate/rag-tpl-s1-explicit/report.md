# Evaluation of run rag-tpl-s1-explicit-escalate on rag-tpl-s1-59c5118b

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: explicit

## A. Extraction

| evidence_type   | level    | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|----------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit | 124     | 162     | 122       | 0.984       | 0.753    | 0.853 | 1.000           |
| all             | all      | 124     | 162     | 122       | 0.984       | 0.753    | 0.853 | 1.000           |
| author_claim    | explicit | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit | 43      | 61      | 42        | 0.977       | 0.689    | 0.808 | 1.000           |
| condition       | all      | 43      | 61      | 42        | 0.977       | 0.689    | 0.808 | 1.000           |
| measurement     | explicit | 41      | 61      | 40        | 0.976       | 0.656    | 0.784 | 1.000           |
| measurement     | all      | 41      | 61      | 40        | 0.976       | 0.656    | 0.784 | 1.000           |
| metric          | explicit | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 40; items matching no fact: 2.

## B. Integration

| level    | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|----------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit | 40                     | 1.000                  | 1.000                     | 1.000             | 0.975             | 1.000          | 20        | 0.850       |
| all      | 40                     | 1.000                  | 1.000                     | 1.000             | 0.975             | 1.000          | 20        | 0.850       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.900                | 0.900          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level    | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|----------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit | evidence-engine | 20        | 20           | 0.900                | 0.900          | 1.000               | -              | -         |

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

| system          | level    | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|----------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit | 20        | 18               | 20               | 2          | 0            |
| evidence-engine | all      | 20        | 18               | 20               | 2          | 0            |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.808 [0.75, 0.88] | BCa      |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 0.784 [0.69, 0.86] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.853 [0.80, 0.91] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.900 [0.70, 1.00]   | BCa      | -                     | -               | -          |

## Locate recall

| evidence_type   | level    | placements   | inside   | recall   |
|-----------------|----------|--------------|----------|----------|
| all             | explicit | 364          | 364      | 1.000    |
| all             | all      | 364          | 364      | 1.000    |
| author_claim    | explicit | 40           | 40       | 1.000    |
| author_claim    | all      | 40           | 40       | 1.000    |
| condition       | explicit | 162          | 162      | 1.000    |
| condition       | all      | 162          | 162      | 1.000    |
| measurement     | explicit | 61           | 61       | 1.000    |
| measurement     | all      | 61           | 61       | 1.000    |
| metric          | explicit | 101          | 101      | 1.000    |
| metric          | all      | 101          | 101      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 18      | 18              | 15     | 15             |
| llm_measurement@1#02bd5a7ab104    | 38      | 37              | 28     | 27             |
| llm_metric@1#41e1e53a1fc4         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 20     | 20             |
| regex_condition@2#0a5bf730763c    | 28      | 27              | 25     | 24             |
| regex_measurement@2#e2d17eb260ea  | 13      | 13              | 3      | 3              |
| regex_metric@2#0affe2d9ce77       | 18      | 18              | 18     | 18             |

Facts no extractor found: condition 19, measurement 21

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 162     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 18      | 30      | 18        | 1.000       | 0.600    | 0.750 | 1.000           | -                      | 15     | 15             |
| llm_condition@1#45b3761c700e      | all             | all     | 18      | 30      | 18        | 1.000       | 0.600    | 0.750 | 1.000           | -                      | 15     | 15             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 38      | 53      | 37        | 0.974       | 0.698    | 0.813 | 1.000           | 1.000                  | 28     | 27             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 38      | 53      | 37        | 0.974       | 0.698    | 0.813 | 1.000           | -                      | 28     | 27             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 27        | 0.964       | 0.443    | 0.607 | 1.000           | -                      | 25     | 24             |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 27        | 0.964       | 0.443    | 0.607 | 1.000           | -                      | 25     | 24             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | 1.000                  | 3      | 3              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | -                      | 3      | 3              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 10      | 19            | 16806          | 1974            | 40.301    |
| llm_measurement@1#02bd5a7ab104    | 17      | 34            | 38259          | 7945            | 152.349   |
| llm_metric@1#41e1e53a1fc4         | 2       | 2             | 1979           | 186             | 2.639     |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 13590          | 1445            | 32.504    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.253     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.252     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.260     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.244     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.250     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 31      | 1.550       |
| calls            | 149     | 7.450       |
| input_tokens     | 70634   | 3531.700    |
| made_model_calls | 58      | 2.900       |
| model_calls      | 75      | 3.750       |
| output_tokens    | 11550   | 577.500     |
| seconds          | 230.222 | 11.511      |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.450          |
| model_calls   | 3.750          |
| input_tokens  | 3531.700       |
| output_tokens | 577.500        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 1           |
| 1               | 17          |
| exhausted       | 2           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
