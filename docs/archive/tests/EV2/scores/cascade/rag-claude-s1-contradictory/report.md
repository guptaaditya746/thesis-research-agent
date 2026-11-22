# Evaluation of run rag-claude-s1-contradictory on rag-claude-s1-e4e9d603

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 201     | 162     | 159       | 0.791       | 0.981    | 0.876 | 1.000           |
| all             | all           | 201     | 162     | 159       | 0.791       | 0.981    | 0.876 | 1.000           |
| author_claim    | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 68      | 61      | 58        | 0.853       | 0.951    | 0.899 | 1.000           |
| condition       | all           | 68      | 61      | 58        | 0.853       | 0.951    | 0.899 | 1.000           |
| measurement     | contradictory | 88      | 61      | 61        | 0.693       | 1.000    | 0.819 | 1.000           |
| measurement     | all           | 88      | 61      | 61        | 0.693       | 1.000    | 0.819 | 1.000           |
| metric          | contradictory | 25      | 20      | 20        | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | all           | 25      | 20      | 20        | 0.800       | 1.000    | 0.889 | 1.000           |

Facts no item matched: 3; items matching no fact: 42.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 61                     | 0.951                  | 0.951                     | 1.000             | 0.951             | 0.869          | 20        | 0.850       |
| all           | 61                     | 0.951                  | 0.951                     | 1.000             | 0.951             | 0.869          | 20        | 0.850       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 20        | 20           | 0.050                | 0.250          | 0.200               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 20        | 20           | 0.000                | 1.000          | 0.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| contradictory | agent-baseline  | 20        | 20           | 0.000                | 1.000          | 0.000               | -              | -         |
| contradictory | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| contradictory | rag-baseline    | 20        | 20           | 0.050                | 0.250          | 0.200               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 20   | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | yes              | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | contradictory | 20        | 20               | 20               | 0          | 0            |
| evidence-engine | all           | 20        | 20               | 20               | 0          | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.899 [0.83, 0.95] | BCa      |
| metric          | 0.889 [0.80, 0.95] | BCa      |
| measurement     | 0.819 [0.74, 0.88] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.876 [0.82, 0.92] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               | -          |
| rag-baseline    | 0.050 [0.00, 0.25]   | BCa      | 0.950 [0.75, 1.00]    | BCa             | 20         |
| agent-baseline  | 0.000 [n/a]          | -        | 1.000 [n/a]           | -               | 20         |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | contradictory | 406          | 406      | 1.000    |
| all             | all           | 406          | 406      | 1.000    |
| author_claim    | contradictory | 40           | 40       | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
| condition       | contradictory | 179          | 179      | 1.000    |
| condition       | all           | 179          | 179      | 1.000    |
| measurement     | contradictory | 61           | 61       | 1.000    |
| measurement     | all           | 61           | 61       | 1.000    |
| metric          | contradictory | 126          | 126      | 1.000    |
| metric          | all           | 126          | 126      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20              | 0      | 0              |
| llm_condition@1#45b3761c700e      | 61      | 58              | 40     | 37             |
| llm_measurement@1#02bd5a7ab104    | 68      | 53              | 28     | 15             |
| llm_metric@1#41e1e53a1fc4         | 20      | 20              | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 28      | 21              | 7      | 0              |
| regex_measurement@2#e2d17eb260ea  | 60      | 46              | 20     | 8              |
| regex_metric@2#0affe2d9ce77       | 18      | 13              | 5      | 0              |

Facts no extractor found: condition 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 61      | 61      | 58        | 0.951       | 0.951    | 0.951 | 1.000           | -                      | 40     | 37             |
| llm_condition@1#45b3761c700e      | all             | all     | 61      | 61      | 58        | 0.951       | 0.951    | 0.951 | 1.000           | -                      | 40     | 37             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 68      | 61      | 53        | 0.779       | 0.869    | 0.822 | 1.000           | 0.943                  | 28     | 15             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 68      | 61      | 53        | 0.779       | 0.869    | 0.822 | 1.000           | -                      | 28     | 15             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 21        | 0.750       | 0.344    | 0.472 | 1.000           | -                      | 7      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 21        | 0.750       | 0.344    | 0.472 | 1.000           | -                      | 7      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 60      | 61      | 46        | 0.767       | 0.754    | 0.760 | 1.000           | 0.957                  | 20     | 8              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 60      | 61      | 46        | 0.767       | 0.754    | 0.760 | 1.000           | -                      | 20     | 8              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20            | 20083          | 2356            | 51.900    |
| llm_condition@1#45b3761c700e      | 20      | 29            | 31085          | 5146            | 104.903   |
| llm_measurement@1#02bd5a7ab104    | 20      | 40            | 51199          | 10698           | 213.911   |
| llm_metric@1#41e1e53a1fc4         | 20      | 25            | 26894          | 2051            | 47.941    |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 19939          | 3074            | 72.758    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.133     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.131     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.305     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.138     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.133     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 104     | 5.200       |
| calls            | 200     | 10.000      |
| input_tokens     | 149200  | 7460.000    |
| made_model_calls | 107     | 5.350       |
| model_calls      | 134     | 6.700       |
| output_tokens    | 23325   | 1166.250    |
| seconds          | 493.460 | 24.673      |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.700          |
| input_tokens  | 7460.000       |
| output_tokens | 1166.250       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 18   | 0    | 2    | 0    | 1.000       | 0.900    |

Screened out wrongly: S002, S014
