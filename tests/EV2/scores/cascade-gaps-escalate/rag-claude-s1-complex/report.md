# Evaluation of run rag-claude-s1-complex-escalate on rag-claude-s1-a5fa1731

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 324     | 431     | 302       | 0.932       | 0.701    | 0.800 | 1.000           |
| all             | all     | 324     | 431     | 302       | 0.932       | 0.701    | 0.800 | 1.000           |
| author_claim    | complex | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 46      | 61      | 46        | 1.000       | 0.754    | 0.860 | 1.000           |
| condition       | all     | 46      | 61      | 46        | 1.000       | 0.754    | 0.860 | 1.000           |
| measurement     | complex | 206     | 300     | 186       | 0.903       | 0.620    | 0.735 | 1.000           |
| measurement     | all     | 206     | 300     | 186       | 0.903       | 0.620    | 0.735 | 1.000           |
| metric          | complex | 52      | 50      | 50        | 0.962       | 1.000    | 0.980 | 1.000           |
| metric          | all     | 52      | 50      | 50        | 0.962       | 1.000    | 0.980 | 1.000           |

Facts no item matched: 129; items matching no fact: 22.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 186                    | 0.866                  | 0.887                     | 0.978             | 0.887             | 0.978          | 20        | 0.500       |
| all     | 186                    | 0.866                  | 0.887                     | 0.978             | 0.887             | 0.978          | 20        | 0.500       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.950                | 1.000          | 0.950               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 20        | 20           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| complex | agent-baseline  | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| complex | evidence-engine | 20        | 20           | 0.950                | 1.000          | 0.950               | -              | -         |
| complex | rag-baseline    | 20        | 20           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 1    | 0    | 0.000       | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level   | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | complex | 20        | 19               | 20               | 1          | 0            |
| evidence-engine | all     | 20        | 19               | 20               | 1          | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.860 [0.79, 0.93] | BCa      |
| metric          | 0.980 [0.93, 1.00] | BCa      |
| measurement     | 0.735 [0.64, 0.81] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.800 [0.73, 0.85] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.950 [0.73, 1.00]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.350 [0.15, 0.60]   | BCa      | 0.600 [0.30, 0.80]    | BCa             | 20         |
| agent-baseline  | 1.000 [n/a]          | -        | -0.050 [-0.27, 0.00]  | BCa             | 20         |

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
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 22      | 22              | 18     | 18             |
| llm_measurement@1#02bd5a7ab104    | 118     | 110             | 107    | 99             |
| llm_metric@1#41e1e53a1fc4         | 5       | 5               | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 20     | 20             |
| regex_condition@2#0a5bf730763c    | 28      | 28              | 24     | 24             |
| regex_measurement@2#e2d17eb260ea  | 99      | 87              | 88     | 76             |
| regex_metric@2#0affe2d9ce77       | 50      | 48              | 47     | 45             |

Facts no extractor found: condition 15, measurement 114

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 431     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 22      | 30      | 22        | 1.000       | 0.733    | 0.846 | 1.000           | -                      | 18     | 18             |
| llm_condition@1#45b3761c700e      | all             | all     | 22      | 30      | 22        | 1.000       | 0.733    | 0.846 | 1.000           | -                      | 18     | 18             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 118     | 218     | 110       | 0.932       | 0.505    | 0.655 | 1.000           | 0.909                  | 107    | 99             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 118     | 218     | 110       | 0.932       | 0.505    | 0.655 | 1.000           | -                      | 107    | 99             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 24     | 24             |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 24     | 24             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 99      | 300     | 87        | 0.879       | 0.290    | 0.436 | 1.000           | 0.828                  | 88     | 76             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 99      | 300     | 87        | 0.879       | 0.290    | 0.436 | 1.000           | -                      | 88     | 76             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 50      | 50      | 48        | 0.960       | 0.960    | 0.960 | 1.000           | -                      | 47     | 45             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 50      | 50      | 48        | 0.960       | 0.960    | 0.960 | 1.000           | -                      | 47     | 45             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 10      | 14            | 17865          | 1982            | 38.044    |
| llm_measurement@1#02bd5a7ab104    | 15      | 30            | 51624          | 21275           | 428.159   |
| llm_metric@1#41e1e53a1fc4         | 2       | 4             | 5720           | 572             | 15.940    |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 21020          | 1667            | 39.662    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.273     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.254     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.312     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.255     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.242     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 30      | 1.500       |
| calls            | 147     | 7.350       |
| input_tokens     | 96229   | 4811.450    |
| made_model_calls | 53      | 2.650       |
| model_calls      | 68      | 3.400       |
| output_tokens    | 25496   | 1274.800    |
| seconds          | 524.386 | 26.219      |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.350          |
| model_calls   | 3.400          |
| input_tokens  | 4811.450       |
| output_tokens | 1274.800       |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 5           |
| 1               | 15          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
