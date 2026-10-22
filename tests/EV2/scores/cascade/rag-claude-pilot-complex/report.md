# Evaluation of run rag-claude-pilot-complex on rag-claude-pilot-d04573ee

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 78      | 80      | 76        | 0.974       | 0.950    | 0.962 | 1.000           |
| all             | all     | 78      | 80      | 76        | 0.974       | 0.950    | 0.962 | 1.000           |
| author_claim    | complex | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 12      | 11      | 10        | 0.833       | 0.909    | 0.870 | 1.000           |
| condition       | all     | 12      | 11      | 10        | 0.833       | 0.909    | 0.870 | 1.000           |
| measurement     | complex | 55      | 58      | 55        | 1.000       | 0.948    | 0.973 | 1.000           |
| measurement     | all     | 55      | 58      | 55        | 1.000       | 0.948    | 0.973 | 1.000           |
| metric          | complex | 8       | 8       | 8         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all     | 8       | 8       | 8         | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 4; items matching no fact: 2.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 55                     | 0.891                  | 0.891                     | 1.000             | 0.891             | 1.000          | 3         | 0.000       |
| all     | 55                     | 0.891                  | 0.891                     | 1.000             | 0.891             | 1.000          | 3         | 0.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 3         | 3            | 0.667                | 1.000          | 0.667               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| complex | evidence-engine | 3         | 3            | 0.667                | 1.000          | 0.667               | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 1    | 0    | 0.000       | -        |
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
| condition       | 0.870 [0.67, 1.00] | BCa      |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 0.973 [0.97, 0.98] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.962 [0.94, 0.97] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.667 [0.00, 1.00]   | BCa      | -                     | -               | -          |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 147          | 147      | 1.000    |
| all             | all     | 147          | 147      | 1.000    |
| author_claim    | complex | 6            | 6        | 1.000    |
| author_claim    | all     | 6            | 6        | 1.000    |
| condition       | complex | 39           | 39       | 1.000    |
| condition       | all     | 39           | 39       | 1.000    |
| measurement     | complex | 58           | 58       | 1.000    |
| measurement     | all     | 58           | 58       | 1.000    |
| metric          | complex | 44           | 44       | 1.000    |
| metric          | all     | 44           | 44       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 3       | 3               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 11      | 10              | 8      | 7              |
| llm_measurement@1#02bd5a7ab104    | 55      | 55              | 12     | 12             |
| llm_metric@1#41e1e53a1fc4         | 8       | 8               | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | 3       | 3               | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 4       | 3               | 1      | 0              |
| regex_measurement@2#e2d17eb260ea  | 43      | 43              | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 6       | 6               | 0      | 0              |

Facts no extractor found: condition 1, measurement 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 11      | 11      | 10        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 8      | 7              |
| llm_condition@1#45b3761c700e      | all             | all     | 11      | 11      | 10        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 8      | 7              |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 55      | 58      | 55        | 1.000       | 0.948    | 0.973 | 1.000           | 0.891                  | 12     | 12             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 55      | 58      | 55        | 1.000       | 0.948    | 0.973 | 1.000           | -                      | 12     | 12             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 8       | 8       | 8         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 8       | 8       | 8         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 4       | 11      | 3         | 0.750       | 0.273    | 0.400 | 1.000           | -                      | 1      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 4       | 11      | 3         | 0.750       | 0.273    | 0.400 | 1.000           | -                      | 1      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 43      | 58      | 43        | 1.000       | 0.741    | 0.851 | 1.000           | 0.907                  | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 43      | 58      | 43        | 1.000       | 0.741    | 0.851 | 1.000           | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 6       | 8       | 6         | 1.000       | 0.750    | 0.857 | 1.000           | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 6       | 8       | 6         | 1.000       | 0.750    | 0.857 | 1.000           | -                      | 0      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 3       | 3             | 3370           | 359             | 9.997     |
| llm_condition@1#45b3761c700e      | 3       | 3             | 3604           | 812             | 20.934    |
| llm_measurement@1#02bd5a7ab104    | 3       | 6             | 11911          | 8729            | 214.408   |
| llm_metric@1#41e1e53a1fc4         | 3       | 6             | 7332           | 873             | 23.889    |
| llm_screen@1#41b0d6e6793f         | 3       | 3             | 3037           | 247             | 7.809     |
| regex_author_claim@2#fd7877790c48 | 3       | 0             | 0              | 0               | 0.053     |
| regex_condition@2#0a5bf730763c    | 3       | 0             | 0              | 0               | 0.049     |
| regex_measurement@2#e2d17eb260ea  | 3       | 0             | 0              | 0               | 0.072     |
| regex_metric@2#0affe2d9ce77       | 3       | 0             | 0              | 0               | 0.047     |
| regex_screen@1#858a6ebc69c6       | 3       | 0             | 0              | 0               | 0.046     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 30      | 10.000      |
| input_tokens     | 29254   | 9751.333    |
| made_model_calls | 21      | 7.000       |
| model_calls      | 21      | 7.000       |
| output_tokens    | 11020   | 3673.333    |
| seconds          | 277.562 | 92.521      |

## Funnel

Strategy `all` over 3 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 7.000          |
| input_tokens  | 9751.333       |
| output_tokens | 3673.333       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 3           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 3           | 3    | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
