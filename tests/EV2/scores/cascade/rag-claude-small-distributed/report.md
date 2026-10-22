# Evaluation of run rag-claude-small-distributed on rag-claude-small-5cbb2530

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 17      | 34      | 17        | 1.000       | 0.500    | 0.667 | 0.882           |
| all             | all         | 17      | 34      | 17        | 1.000       | 0.500    | 0.667 | 0.882           |
| author_claim    | distributed | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 9       | 12      | 9         | 1.000       | 0.750    | 0.857 | 0.778           |
| condition       | all         | 9       | 12      | 9         | 1.000       | 0.750    | 0.857 | 0.778           |
| measurement     | distributed | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | all         | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               |
| metric          | distributed | 3       | 5       | 3         | 1.000       | 0.600    | 0.750 | 1.000           |
| metric          | all         | 3       | 5       | 3         | 1.000       | 0.600    | 0.750 | 1.000           |

Facts no item matched: 17; items matching no fact: 0.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 0                      | -                      | -                         | -                 | -                 | -              | 5         | 0.000       |
| all         | 0                      | -                      | -                         | -                 | -                 | -              | 5         | 0.000       |

## C. Synthesis

| system          | label        | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|--------------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | insufficient | mixed      | no              | 5         | 5            | 0.000                | 0.000          | -                   | -              | -         |
| rag-baseline    | mixed        | mixed      | yes             | 5         | 5            | 0.800                | 0.800          | 1.000               | 1.000          | 1.000     |
| agent-baseline  | mixed        | mixed      | yes             | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| distributed | agent-baseline  | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed | evidence-engine | 5         | 5            | 0.000                | 0.000          | -                   | -              | -         |
| distributed | rag-baseline    | 5         | 5            | 0.800                | 0.800          | 1.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.857 [0.72, 1.00] | BCa      |
| metric          | 0.750 [0.33, 1.00] | BCa      |
| measurement     | 0.000 [n/a]        | -        |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.667 [0.53, 0.80] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.000 [n/a]          | -        | -                     | -               | -          |
| rag-baseline    | 0.800 [0.20, 1.00]   | BCa      | -0.800 [-1.00, -0.20] | BCa             | 5          |
| agent-baseline  | 1.000 [n/a]          | -        | -1.000 [n/a]          | -               | 5          |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | distributed | 118          | 118      | 1.000    |
| all             | all         | 118          | 118      | 1.000    |
| author_claim    | distributed | 10           | 10       | 1.000    |
| author_claim    | all         | 10           | 10       | 1.000    |
| condition       | distributed | 69           | 69       | 1.000    |
| condition       | all         | 69           | 69       | 1.000    |
| measurement     | distributed | 12           | 12       | 1.000    |
| measurement     | all         | 12           | 12       | 1.000    |
| metric          | distributed | 27           | 27       | 1.000    |
| metric          | all         | 27           | 27       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 0       | 0               | 0      | 0              |
| llm_measurement@1#02bd5a7ab104    | 0       | 0               | 0      | 0              |
| llm_metric@1#41e1e53a1fc4         | 0       | 0               | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | 5       | 5               | 5      | 5              |
| regex_condition@2#0a5bf730763c    | 9       | 9               | 9      | 9              |
| regex_measurement@2#e2d17eb260ea  | 0       | 0               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 3       | 3               | 3      | 3              |

Facts no extractor found: condition 3, measurement 12, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 0       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | all             | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 0       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 0       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 5      | 5              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 5      | 5              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 9       | 12      | 9         | 1.000       | 0.750    | 0.857 | 0.778           | -                      | 9      | 9              |
| regex_condition@2#0a5bf730763c    | all             | all     | 9       | 12      | 9         | 1.000       | 0.750    | 0.857 | 0.778           | -                      | 9      | 9              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 3       | 5       | 3         | 1.000       | 0.600    | 0.750 | 1.000           | -                      | 3      | 3              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 3       | 5       | 3         | 1.000       | 0.600    | 0.750 | 1.000           | -                      | 3      | 3              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 5       | 5             | 5722           | 597             | 0.129     |
| llm_condition@1#45b3761c700e      | 5       | 5             | 6112           | 922             | 0.130     |
| llm_measurement@1#02bd5a7ab104    | 5       | 5             | 0              | 0               | 0.136     |
| llm_metric@1#41e1e53a1fc4         | 5       | 5             | 6242           | 494             | 0.138     |
| llm_screen@1#41b0d6e6793f         | 5       | 5             | 5167           | 501             | 0.850     |
| regex_author_claim@2#fd7877790c48 | 5       | 0             | 0              | 0               | 0.076     |
| regex_condition@2#0a5bf730763c    | 5       | 0             | 0              | 0               | 0.069     |
| regex_measurement@2#e2d17eb260ea  | 5       | 0             | 0              | 0               | 0.076     |
| regex_metric@2#0affe2d9ce77       | 5       | 0             | 0              | 0               | 0.068     |
| regex_screen@1#858a6ebc69c6       | 5       | 0             | 0              | 0               | 0.078     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 50      | 10.000      |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 25      | 5.000       |
| model_calls      | 25      | 5.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 2.076   | 0.415       |

## Funnel

Strategy `all` over 5 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 5.000          |
| input_tokens  | 4648.600       |
| output_tokens | 502.800        |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 5           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 5           | 5    | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
