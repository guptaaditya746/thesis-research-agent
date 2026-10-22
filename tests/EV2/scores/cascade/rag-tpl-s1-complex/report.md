# Evaluation of run rag-tpl-s1-complex on rag-tpl-s1-f0f5d48e

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 446     | 431     | 411       | 0.922       | 0.954    | 0.937 | 1.000           |
| all             | all     | 446     | 431     | 411       | 0.922       | 0.954    | 0.937 | 1.000           |
| author_claim    | complex | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| condition       | all     | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| measurement     | complex | 305     | 300     | 280       | 0.918       | 0.933    | 0.926 | 1.000           |
| measurement     | all     | 305     | 300     | 280       | 0.918       | 0.933    | 0.926 | 1.000           |
| metric          | complex | 55      | 50      | 50        | 0.909       | 1.000    | 0.952 | 1.000           |
| metric          | all     | 55      | 50      | 50        | 0.909       | 1.000    | 0.952 | 1.000           |

Facts no item matched: 20; items matching no fact: 35.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 280                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.957          | 20        | 0.000       |
| all     | 280                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.957          | 20        | 0.000       |

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
| condition       | 0.961 [0.93, 0.98] | BCa      |
| metric          | 0.952 [0.91, 0.98] | BCa      |
| measurement     | 0.926 [0.89, 0.95] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.937 [0.91, 0.96] | BCa      |

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
| llm_author_claim@1#be3c17081ff9   | 20      | 20              | 0      | 0              |
| llm_condition@1#45b3761c700e      | 61      | 61              | 38     | 38             |
| llm_measurement@1#02bd5a7ab104    | 280     | 268             | 39     | 27             |
| llm_metric@1#41e1e53a1fc4         | 50      | 50              | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 28      | 23              | 5      | 0              |
| regex_measurement@2#e2d17eb260ea  | 266     | 253             | 25     | 12             |
| regex_metric@2#0affe2d9ce77       | 48      | 43              | 5      | 0              |

Facts no extractor found: measurement 20

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| llm_condition@1#45b3761c700e      | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 280     | 300     | 268       | 0.957       | 0.893    | 0.924 | 1.000           | 1.000                  | 39     | 27             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 280     | 300     | 268       | 0.957       | 0.893    | 0.924 | 1.000           | -                      | 39     | 27             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 266     | 300     | 253       | 0.951       | 0.843    | 0.894 | 1.000           | 1.000                  | 25     | 12             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 266     | 300     | 253       | 0.951       | 0.843    | 0.894 | 1.000           | -                      | 25     | 12             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 48      | 50      | 43        | 0.896       | 0.860    | 0.878 | 1.000           | -                      | 5      | 0              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 48      | 50      | 43        | 0.896       | 0.860    | 0.878 | 1.000           | -                      | 5      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20            | 19946          | 2436            | 68.148    |
| llm_condition@1#45b3761c700e      | 20      | 40            | 43531          | 6647            | 185.694   |
| llm_measurement@1#02bd5a7ab104    | 20      | 40            | 67471          | 44061           | 1125.696  |
| llm_metric@1#41e1e53a1fc4         | 20      | 26            | 28685          | 4543            | 123.179   |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 17726          | 1400            | 44.682    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.156     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.153     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.416     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.151     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.147     |

## Cost

| measure          | total    | per_paper   |
|------------------|----------|-------------|
| cached_calls     | 80       | 4.000       |
| calls            | 200      | 10.000      |
| input_tokens     | 177359   | 8867.950    |
| made_model_calls | 146      | 7.300       |
| model_calls      | 146      | 7.300       |
| output_tokens    | 59131    | 2956.550    |
| seconds          | 1549.753 | 77.488      |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 7.300          |
| input_tokens  | 8867.950       |
| output_tokens | 2954.350       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
