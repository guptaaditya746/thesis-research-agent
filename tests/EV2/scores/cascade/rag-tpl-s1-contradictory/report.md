# Evaluation of run rag-tpl-s1-contradictory on rag-tpl-s1-56b0bc02

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 200     | 162     | 162       | 0.810       | 1.000    | 0.895 | 1.000           |
| all             | all           | 200     | 162     | 162       | 0.810       | 1.000    | 0.895 | 1.000           |
| author_claim    | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| condition       | all           | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| measurement     | contradictory | 89      | 61      | 61        | 0.685       | 1.000    | 0.813 | 1.000           |
| measurement     | all           | 89      | 61      | 61        | 0.685       | 1.000    | 0.813 | 1.000           |
| metric          | contradictory | 25      | 20      | 20        | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | all           | 25      | 20      | 20        | 0.800       | 1.000    | 0.889 | 1.000           |

Facts no item matched: 0; items matching no fact: 38.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 61                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.836          | 20        | 0.750       |
| all           | 61                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.836          | 20        | 0.750       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| contradictory | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

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

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.961 [0.93, 0.98] | BCa      |
| metric          | 0.889 [0.80, 0.95] | BCa      |
| measurement     | 0.813 [0.73, 0.88] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.895 [0.84, 0.93] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               | -          |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | contradictory | 343          | 343      | 1.000    |
| all             | all           | 343          | 343      | 1.000    |
| author_claim    | contradictory | 40           | 40       | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
| condition       | contradictory | 172          | 172      | 1.000    |
| condition       | all           | 172          | 172      | 1.000    |
| measurement     | contradictory | 61           | 61       | 1.000    |
| measurement     | all           | 61           | 61       | 1.000    |
| metric          | contradictory | 70           | 70       | 1.000    |
| metric          | all           | 70           | 70       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20              | 0      | 0              |
| llm_condition@1#45b3761c700e      | 61      | 61              | 38     | 38             |
| llm_measurement@1#02bd5a7ab104    | 71      | 51              | 29     | 13             |
| llm_metric@1#41e1e53a1fc4         | 20      | 20              | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 28      | 23              | 5      | 0              |
| regex_measurement@2#e2d17eb260ea  | 60      | 48              | 18     | 10             |
| regex_metric@2#0affe2d9ce77       | 18      | 13              | 5      | 0              |

Facts no extractor found: none

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| llm_condition@1#45b3761c700e      | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 71      | 61      | 51        | 0.718       | 0.836    | 0.773 | 1.000           | 1.000                  | 29     | 13             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 71      | 61      | 51        | 0.718       | 0.836    | 0.773 | 1.000           | -                      | 29     | 13             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 60      | 61      | 48        | 0.800       | 0.787    | 0.793 | 1.000           | 1.000                  | 18     | 10             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 60      | 61      | 48        | 0.800       | 0.787    | 0.793 | 1.000           | -                      | 18     | 10             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20            | 16389          | 2362            | 64.185    |
| llm_condition@1#45b3761c700e      | 20      | 40            | 36417          | 6570            | 177.681   |
| llm_measurement@1#02bd5a7ab104    | 20      | 40            | 44304          | 11391           | 294.235   |
| llm_metric@1#41e1e53a1fc4         | 20      | 29            | 25680          | 2217            | 64.898    |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 14169          | 1475            | 41.904    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.138     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.133     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.321     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.141     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.137     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 80      | 4.000       |
| calls            | 200     | 10.000      |
| input_tokens     | 136959  | 6847.950    |
| made_model_calls | 149     | 7.450       |
| model_calls      | 149     | 7.450       |
| output_tokens    | 24013   | 1200.650    |
| seconds          | 645.011 | 32.251      |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 7.450          |
| input_tokens  | 6847.950       |
| output_tokens | 1200.750       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 19   | 0    | 1    | 0    | 1.000       | 0.950    |

Screened out wrongly: S013
