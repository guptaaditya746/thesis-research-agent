# Evaluation of run rag-tpl-s1-explicit on rag-tpl-s1-59c5118b

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: explicit

## A. Extraction

| evidence_type   | level    | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|----------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit | 177     | 162     | 161       | 0.910       | 0.994    | 0.950 | 1.000           |
| all             | all      | 177     | 162     | 161       | 0.910       | 0.994    | 0.950 | 1.000           |
| author_claim    | explicit | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit | 66      | 61      | 60        | 0.909       | 0.984    | 0.945 | 1.000           |
| condition       | all      | 66      | 61      | 60        | 0.909       | 0.984    | 0.945 | 1.000           |
| measurement     | explicit | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| measurement     | all      | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| metric          | explicit | 25      | 20      | 20        | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | all      | 25      | 20      | 20        | 0.800       | 1.000    | 0.889 | 1.000           |

Facts no item matched: 1; items matching no fact: 16.

## B. Integration

| level    | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|----------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit | 61                     | 0.984                  | 0.984                     | 1.000             | 0.951             | 0.934          | 20        | 0.750       |
| all      | 61                     | 0.984                  | 0.984                     | 1.000             | 0.951             | 0.934          | 20        | 0.750       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level    | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|----------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

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

| system          | level    | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|----------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit | 20        | 20               | 20               | 0          | 0            |
| evidence-engine | all      | 20        | 20               | 20               | 0          | 0            |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.945 [0.88, 0.98] | BCa      |
| metric          | 0.889 [0.80, 0.95] | BCa      |
| measurement     | 0.961 [0.93, 0.98] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.950 [0.91, 0.97] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               | -          |

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
| llm_author_claim@1#be3c17081ff9   | 20      | 20              | 0      | 0              |
| llm_condition@1#45b3761c700e      | 61      | 60              | 38     | 37             |
| llm_measurement@1#02bd5a7ab104    | 61      | 56              | 53     | 48             |
| llm_metric@1#41e1e53a1fc4         | 20      | 20              | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 28      | 23              | 5      | 0              |
| regex_measurement@2#e2d17eb260ea  | 13      | 13              | 5      | 5              |
| regex_metric@2#0affe2d9ce77       | 18      | 13              | 5      | 0              |

Facts no extractor found: condition 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | -                      | 38     | 37             |
| llm_condition@1#45b3761c700e      | all             | all     | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | -                      | 38     | 37             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 61      | 61      | 56        | 0.918       | 0.918    | 0.918 | 1.000           | 0.982                  | 53     | 48             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 61      | 61      | 56        | 0.918       | 0.918    | 0.918 | 1.000           | -                      | 53     | 48             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | 1.000                  | 5      | 5              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | -                      | 5      | 5              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20            | 15810          | 2378            | 50.718    |
| llm_condition@1#45b3761c700e      | 20      | 37            | 32201          | 6179            | 124.156   |
| llm_measurement@1#02bd5a7ab104    | 20      | 40            | 45880          | 12392           | 238.187   |
| llm_metric@1#41e1e53a1fc4         | 20      | 21            | 18682          | 1890            | 42.779    |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 13590          | 1445            | 32.518    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.134     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.139     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.281     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.130     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.133     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 104     | 5.200       |
| calls            | 200     | 10.000      |
| input_tokens     | 126163  | 6308.150    |
| made_model_calls | 111     | 5.550       |
| model_calls      | 138     | 6.900       |
| output_tokens    | 24284   | 1214.200    |
| seconds          | 490.350 | 24.518      |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.900          |
| input_tokens  | 6308.150       |
| output_tokens | 1214.200       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
