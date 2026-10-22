# Evaluation of run rag-claude-s1-complex on rag-claude-s1-a5fa1731

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 455     | 431     | 414       | 0.910       | 0.961    | 0.935 | 1.000           |
| all             | all     | 455     | 431     | 414       | 0.910       | 0.961    | 0.935 | 1.000           |
| author_claim    | complex | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 66      | 61      | 58        | 0.879       | 0.951    | 0.913 | 1.000           |
| condition       | all     | 66      | 61      | 58        | 0.879       | 0.951    | 0.913 | 1.000           |
| measurement     | complex | 312     | 300     | 286       | 0.917       | 0.953    | 0.935 | 1.000           |
| measurement     | all     | 312     | 300     | 286       | 0.917       | 0.953    | 0.935 | 1.000           |
| metric          | complex | 57      | 50      | 50        | 0.877       | 1.000    | 0.935 | 1.000           |
| metric          | all     | 57      | 50      | 50        | 0.877       | 1.000    | 0.935 | 1.000           |

Facts no item matched: 17; items matching no fact: 41.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 286                    | 0.944                  | 0.944                     | 1.000             | 0.944             | 0.965          | 20        | 0.150       |
| all     | 286                    | 0.944                  | 0.944                     | 1.000             | 0.944             | 0.965          | 20        | 0.150       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 20        | 20           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| complex | agent-baseline  | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| complex | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| complex | rag-baseline    | 20        | 20           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 1    | 0    | 0.000       | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | yes              | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level   | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | complex | 20        | 20               | 20               | 0          | 0            |
| evidence-engine | all     | 20        | 20               | 20               | 0          | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.913 [0.80, 0.97] | BCa      |
| metric          | 0.935 [0.89, 0.97] | BCa      |
| measurement     | 0.935 [0.90, 0.96] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.935 [0.90, 0.96] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               | -          |
| rag-baseline    | 0.350 [0.15, 0.60]   | BCa      | 0.650 [0.40, 0.85]    | BCa             | 20         |
| agent-baseline  | 1.000 [n/a]          | -        | 0.000 [n/a]           | -               | 20         |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 908          | 908      | 1.000    |
| all             | all     | 908          | 908      | 1.000    |
| author_claim    | complex | 40           | 40       | 1.000    |
| author_claim    | all     | 40           | 40       | 1.000    |
| condition       | complex | 293          | 293      | 1.000    |
| condition       | all     | 293          | 293      | 1.000    |
| measurement     | complex | 300          | 300      | 1.000    |
| measurement     | all     | 300          | 300      | 1.000    |
| metric          | complex | 275          | 275      | 1.000    |
| metric          | all     | 275          | 275      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20              | 0      | 0              |
| llm_condition@1#45b3761c700e      | 61      | 58              | 38     | 35             |
| llm_measurement@1#02bd5a7ab104    | 287     | 276             | 46     | 35             |
| llm_metric@1#41e1e53a1fc4         | 49      | 49              | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 28      | 23              | 5      | 0              |
| regex_measurement@2#e2d17eb260ea  | 266     | 251             | 25     | 10             |
| regex_metric@2#0affe2d9ce77       | 50      | 43              | 8      | 1              |

Facts no extractor found: condition 3, measurement 14

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 61      | 61      | 58        | 0.951       | 0.951    | 0.951 | 1.000           | -                      | 38     | 35             |
| llm_condition@1#45b3761c700e      | all             | all     | 61      | 61      | 58        | 0.951       | 0.951    | 0.951 | 1.000           | -                      | 38     | 35             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 287     | 300     | 276       | 0.962       | 0.920    | 0.940 | 1.000           | 0.949                  | 46     | 35             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 287     | 300     | 276       | 0.962       | 0.920    | 0.940 | 1.000           | -                      | 46     | 35             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 49      | 50      | 49        | 1.000       | 0.980    | 0.990 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 49      | 50      | 49        | 1.000       | 0.980    | 0.990 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 266     | 300     | 251       | 0.944       | 0.837    | 0.887 | 1.000           | 0.944                  | 25     | 10             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 266     | 300     | 251       | 0.944       | 0.837    | 0.887 | 1.000           | -                      | 25     | 10             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 50      | 50      | 43        | 0.860       | 0.860    | 0.860 | 1.000           | -                      | 8      | 1              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 50      | 50      | 43        | 0.860       | 0.860    | 0.860 | 1.000           | -                      | 8      | 1              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20            | 23240          | 2368            | 53.222    |
| llm_condition@1#45b3761c700e      | 20      | 28            | 34887          | 5254            | 119.682   |
| llm_measurement@1#02bd5a7ab104    | 20      | 40            | 75207          | 45665           | 940.782   |
| llm_metric@1#41e1e53a1fc4         | 20      | 32            | 40014          | 4963            | 107.214   |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 21020          | 1667            | 39.692    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.156     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.154     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.389     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.157     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.148     |

## Cost

| measure          | total    | per_paper   |
|------------------|----------|-------------|
| cached_calls     | 104      | 5.200       |
| calls            | 200      | 10.000      |
| input_tokens     | 194368   | 9718.400    |
| made_model_calls | 114      | 5.700       |
| model_calls      | 140      | 7.000       |
| output_tokens    | 59917    | 2995.850    |
| seconds          | 1262.953 | 63.148      |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 7.000          |
| input_tokens  | 9718.400       |
| output_tokens | 2995.850       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
