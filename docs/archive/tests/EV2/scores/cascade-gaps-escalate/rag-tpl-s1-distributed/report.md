# Evaluation of run rag-tpl-s1-distributed-escalate on rag-tpl-s1-79207ad1

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 127     | 162     | 126       | 0.992       | 0.778    | 0.872 | 1.000           |
| all             | all         | 127     | 162     | 126       | 0.992       | 0.778    | 0.872 | 1.000           |
| author_claim    | distributed | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 44      | 61      | 43        | 0.977       | 0.705    | 0.819 | 1.000           |
| condition       | all         | 44      | 61      | 43        | 0.977       | 0.705    | 0.819 | 1.000           |
| measurement     | distributed | 43      | 61      | 43        | 1.000       | 0.705    | 0.827 | 1.000           |
| measurement     | all         | 43      | 61      | 43        | 1.000       | 0.705    | 0.827 | 1.000           |
| metric          | distributed | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 36; items matching no fact: 1.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 43                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 1.000       |
| all         | 43                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 1.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| distributed | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

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

| system          | level       | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|-------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | distributed | 20        | 20               | 20               | 0          | 0            |
| evidence-engine | all         | 20        | 20               | 20               | 0          | 0            |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.819 [0.76, 0.88] | BCa      |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 0.827 [0.76, 0.90] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.872 [0.83, 0.92] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               | -          |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | distributed | 364          | 364      | 1.000    |
| all             | all         | 364          | 364      | 1.000    |
| author_claim    | distributed | 40           | 40       | 1.000    |
| author_claim    | all         | 40           | 40       | 1.000    |
| condition       | distributed | 183          | 183      | 1.000    |
| condition       | all         | 183          | 183      | 1.000    |
| measurement     | distributed | 61           | 61       | 1.000    |
| measurement     | all         | 61           | 61       | 1.000    |
| metric          | distributed | 80           | 80       | 1.000    |
| metric          | all         | 80           | 80       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 16      | 16              | 16     | 16             |
| llm_measurement@1#02bd5a7ab104    | 43      | 43              | 43     | 43             |
| llm_metric@1#41e1e53a1fc4         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 20     | 20             |
| regex_condition@2#0a5bf730763c    | 28      | 27              | 28     | 27             |
| regex_measurement@2#e2d17eb260ea  | 0       | 0               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 18      | 18              | 18     | 18             |

Facts no extractor found: condition 18, measurement 18

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 162     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 16      | 30      | 16        | 1.000       | 0.533    | 0.696 | 1.000           | -                      | 16     | 16             |
| llm_condition@1#45b3761c700e      | all             | all     | 16      | 30      | 16        | 1.000       | 0.533    | 0.696 | 1.000           | -                      | 16     | 16             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 43      | 61      | 43        | 1.000       | 0.705    | 0.827 | 1.000           | 1.000                  | 43     | 43             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 43      | 61      | 43        | 1.000       | 0.705    | 0.827 | 1.000           | -                      | 43     | 43             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 27        | 0.964       | 0.443    | 0.607 | 1.000           | -                      | 28     | 27             |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 27        | 0.964       | 0.443    | 0.607 | 1.000           | -                      | 28     | 27             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 10      | 10            | 10718          | 1030            | 29.103    |
| llm_measurement@1#02bd5a7ab104    | 20      | 40            | 47386          | 6324            | 170.531   |
| llm_metric@1#41e1e53a1fc4         | 2       | 2             | 2278           | 204             | 5.820     |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 16650          | 2072            | 57.596    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.300     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.281     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.299     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.277     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.279     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 152     | 7.600       |
| input_tokens     | 77032   | 3851.600    |
| made_model_calls | 72      | 3.600       |
| model_calls      | 72      | 3.600       |
| output_tokens    | 9630    | 481.500     |
| seconds          | 265.775 | 13.289      |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.600          |
| model_calls   | 3.600          |
| input_tokens  | 3851.600       |
| output_tokens | 481.500        |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
