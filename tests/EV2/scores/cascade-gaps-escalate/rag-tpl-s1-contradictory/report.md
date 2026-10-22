# Evaluation of run rag-tpl-s1-contradictory-escalate on rag-tpl-s1-56b0bc02

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 123     | 162     | 113       | 0.919       | 0.698    | 0.793 | 1.000           |
| all             | all           | 123     | 162     | 113       | 0.919       | 0.698    | 0.793 | 1.000           |
| author_claim    | contradictory | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |
| author_claim    | all           | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |
| condition       | contradictory | 41      | 61      | 40        | 0.976       | 0.656    | 0.784 | 1.000           |
| condition       | all           | 41      | 61      | 40        | 0.976       | 0.656    | 0.784 | 1.000           |
| measurement     | contradictory | 46      | 61      | 37        | 0.804       | 0.607    | 0.692 | 1.000           |
| measurement     | all           | 46      | 61      | 37        | 0.804       | 0.607    | 0.692 | 1.000           |
| metric          | contradictory | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |
| metric          | all           | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |

Facts no item matched: 49; items matching no fact: 10.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 37                     | 0.973                  | 0.973                     | 1.000             | 0.973             | 1.000          | 20        | 0.700       |
| all           | 37                     | 0.973                  | 0.973                     | 1.000             | 0.973             | 1.000          | 20        | 0.700       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.750                | 0.850          | 0.882               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| contradictory | evidence-engine | 20        | 20           | 0.750                | 0.850          | 0.882               | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 15   | 0    | 5    | 1.000       | 0.750    |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | contradictory | 20        | 15               | 20               | 5          | 0            |
| evidence-engine | all           | 20        | 15               | 20               | 5          | 0            |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.784 [0.69, 0.86] | BCa      |
| metric          | 0.947 [0.82, 1.00] | BCa      |
| measurement     | 0.692 [0.60, 0.77] | BCa      |
| author_claim    | 0.947 [0.82, 1.00] | BCa      |
| all             | 0.793 [0.70, 0.85] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.750 [0.50, 0.90]   | BCa      | -                     | -               | -          |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | contradictory | 343          | 314      | 0.915    |
| all             | all           | 343          | 314      | 0.915    |
| author_claim    | contradictory | 40           | 36       | 0.900    |
| author_claim    | all           | 40           | 36       | 0.900    |
| condition       | contradictory | 172          | 158      | 0.919    |
| condition       | all           | 172          | 158      | 0.919    |
| measurement     | contradictory | 61           | 56       | 0.918    |
| measurement     | all           | 61           | 56       | 0.918    |
| metric          | contradictory | 70           | 64       | 0.914    |
| metric          | all           | 70           | 64       | 0.914    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 17      | 17              | 16     | 16             |
| llm_measurement@1#02bd5a7ab104    | 26      | 24              | 21     | 19             |
| llm_metric@1#41e1e53a1fc4         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | 18      | 18              | 18     | 18             |
| regex_condition@2#0a5bf730763c    | 25      | 24              | 24     | 23             |
| regex_measurement@2#e2d17eb260ea  | 25      | 18              | 20     | 13             |
| regex_metric@2#0affe2d9ce77       | 16      | 16              | 16     | 16             |

Facts no extractor found: author_claim 2, condition 21, measurement 24, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 162     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 17      | 28      | 17        | 1.000       | 0.607    | 0.756 | 1.000           | -                      | 16     | 16             |
| llm_condition@1#45b3761c700e      | all             | all     | 17      | 28      | 17        | 1.000       | 0.607    | 0.756 | 1.000           | -                      | 16     | 16             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 26      | 34      | 24        | 0.923       | 0.706    | 0.800 | 1.000           | 1.000                  | 21     | 19             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 26      | 34      | 24        | 0.923       | 0.706    | 0.800 | 1.000           | -                      | 21     | 19             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 18      | 18      | 18        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 18     | 18             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 18      | 18      | 18        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 18     | 18             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 25      | 56      | 24        | 0.960       | 0.429    | 0.593 | 1.000           | -                      | 24     | 23             |
| regex_condition@2#0a5bf730763c    | all             | all     | 25      | 56      | 24        | 0.960       | 0.429    | 0.593 | 1.000           | -                      | 24     | 23             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 25      | 56      | 18        | 0.720       | 0.321    | 0.444 | 1.000           | 0.944                  | 20     | 13             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 25      | 56      | 18        | 0.720       | 0.321    | 0.444 | 1.000           | -                      | 20     | 13             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 16      | 18      | 16        | 1.000       | 0.889    | 0.941 | 1.000           | -                      | 16     | 16             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 16      | 18      | 16        | 1.000       | 0.889    | 0.941 | 1.000           | -                      | 16     | 16             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 9       | 18            | 16600          | 1951            | 57.088    |
| llm_measurement@1#02bd5a7ab104    | 10      | 20            | 22157          | 4092            | 115.936   |
| llm_metric@1#41e1e53a1fc4         | 2       | 4             | 3762           | 269             | 8.364     |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 14169          | 1475            | 44.580    |
| regex_author_claim@2#fd7877790c48 | 18      | 0             | 0              | 0               | 0.257     |
| regex_condition@2#0a5bf730763c    | 18      | 0             | 0              | 0               | 0.252     |
| regex_measurement@2#e2d17eb260ea  | 18      | 0             | 0              | 0               | 0.273     |
| regex_metric@2#0affe2d9ce77       | 18      | 0             | 0              | 0               | 0.243     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.261     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 133     | 6.650       |
| input_tokens     | 56688   | 2834.400    |
| made_model_calls | 62      | 3.100       |
| model_calls      | 62      | 3.100       |
| output_tokens    | 7787    | 389.350     |
| seconds          | 228.345 | 11.417      |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 6.650          |
| model_calls   | 3.100          |
| input_tokens  | 2834.400       |
| output_tokens | 389.350        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 7           |
| 1               | 10          |
| exhausted       | 1           |
| skipped         | 2           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 18   | 0    | 2    | 0    | 1.000       | 0.900    |

Screened out wrongly: S009, S013
