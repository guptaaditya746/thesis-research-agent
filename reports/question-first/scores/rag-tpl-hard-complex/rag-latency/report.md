# Evaluation of run rag-tpl-hard-complex on rag-tpl-hard-24ab4663

Question: Does retrieval-augmented generation change the latency of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 1643    | 2363    | 1350      | 0.822       | 0.571    | 0.674 | 1.000           |
| all             | all     | 1643    | 2363    | 1350      | 0.822       | 0.571    | 0.674 | 1.000           |
| condition       | complex | 394     | 332     | 256       | 0.650       | 0.771    | 0.705 | 1.000           |
| condition       | all     | 394     | 332     | 256       | 0.650       | 0.771    | 0.705 | 1.000           |
| measurement     | complex | 922     | 1768    | 854       | 0.926       | 0.483    | 0.635 | 1.000           |
| measurement     | all     | 922     | 1768    | 854       | 0.926       | 0.483    | 0.635 | 1.000           |
| metric          | complex | 327     | 263     | 240       | 0.734       | 0.913    | 0.814 | 1.000           |
| metric          | all     | 327     | 263     | 240       | 0.734       | 0.913    | 0.814 | 1.000           |

Facts no item matched: 1013; items matching no fact: 293.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 854                    | 0.651                  | 0.840                     | 0.738             | 0.840             | 0.662          | 52        | 0.769       |
| all     | 854                    | 0.651                  | 0.840                     | 0.738             | 0.840             | 0.662          | 52        | 0.769       |

## C. Synthesis

| system          | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|-----------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine | mixed     | mixed      | yes             | 112       | 52           | 0.942                | 0.962          | 0.980               | 0.973                           | -              | -         |
| rag-baseline    | supported | mixed      | no              | 112       | 52           | 0.019                | 0.019          | 1.000               | 0.545                           | 1.000          | 1.000     |
| agent-baseline  | mixed     | mixed      | yes             | 112       | 52           | 0.115                | 0.154          | 0.750               | 0.589                           | -              | -         |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| complex | agent-baseline  | 112       | 52           | 0.115                | 0.154          | 0.750               | 0.589                           | -              | -         |
| complex | evidence-engine | 112       | 52           | 0.942                | 0.962          | 0.980               | 0.973                           | -              | -         |
| complex | rag-baseline    | 112       | 52           | 0.019                | 0.019          | 1.000               | 0.545                           | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | n/a         | -        |
| evidence-engine | duplicate       | 3    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | large_effect    | 0    | 0    | 0    | n/a         | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.705 [0.68, 0.73] | BCa      |
| metric          | 0.814 [0.79, 0.84] | BCa      |
| measurement     | 0.635 [0.59, 0.68] | BCa      |
| all             | 0.674 [0.64, 0.70] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.942 [0.85, 0.98]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.019 [0.00, 0.11]   | BCa      | 0.923 [0.83, 0.98]    | BCa             | 52         |
| agent-baseline  | 0.115 [0.04, 0.23]   | BCa      | 0.827 [0.71, 0.90]    | BCa             | 52         |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 4323         | 4111     | 0.951    |
| all             | all     | 4323         | 4111     | 0.951    |
| author_claim    | complex | 212          | 0        | 0.000    |
| author_claim    | all     | 212          | 0        | 0.000    |
| condition       | complex | 1454         | 1454     | 1.000    |
| condition       | all     | 1454         | 1454     | 1.000    |
| measurement     | complex | 1768         | 1768     | 1.000    |
| measurement     | all     | 1768         | 1768     | 1.000    |
| metric          | complex | 889          | 889      | 1.000    |
| metric          | all     | 889          | 889      | 1.000    |

## Cascade contribution

| extractor                              | found   | found_matched   | only   | only_matched   |
|----------------------------------------|---------|-----------------|--------|----------------|
| abbrev_condition@1#ea9c557ddc1a        | 0       | 0               | 0      | 0              |
| abbrev_metric@1#52506d2e3a69           | 0       | 0               | 0      | 0              |
| gliner_condition@1#c8fde69a32e1        | 215     | 80              | 143    | 8              |
| gliner_metric@1#ce2c7d899fd3           | 161     | 112             | 63     | 14             |
| llm_condition@1#45b3761c700e           | 120     | 120             | 56     | 56             |
| llm_measurement@1#4171ae269b7f         | 237     | 204             | 59     | 52             |
| llm_metric@1#f77fae6f7754              | 122     | 108             | 24     | 10             |
| number_measurement@1#9489bf6f9408      | 343     | 310             | 131    | 124            |
| regex_condition@2#1d6558c26117         | 162     | 159             | 123    | 120            |
| regex_measurement_units@1#a0d7822bd8cd | 579     | 551             | 520    | 492            |
| regex_metric@2#7b60cc978d29            | 216     | 192             | 142    | 118            |

Facts no extractor found: condition 76, measurement 914, metric 23

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                              | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|----------------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_condition@1#ea9c557ddc1a        | condition       | all     | 0       | 137     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_condition@1#ea9c557ddc1a        | all             | all     | 0       | 137     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_metric@1#52506d2e3a69           | metric          | all     | 0       | 122     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_metric@1#52506d2e3a69           | all             | all     | 0       | 122     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| gliner_condition@1#c8fde69a32e1        | condition       | all     | 215     | 137     | 80        | 0.372       | 0.584    | 0.455 | 1.000           | -                      | 143    | 8              |
| gliner_condition@1#c8fde69a32e1        | all             | all     | 215     | 137     | 80        | 0.372       | 0.584    | 0.455 | 1.000           | -                      | 143    | 8              |
| gliner_metric@1#ce2c7d899fd3           | metric          | all     | 161     | 122     | 112       | 0.696       | 0.918    | 0.792 | 1.000           | -                      | 63     | 14             |
| gliner_metric@1#ce2c7d899fd3           | all             | all     | 161     | 122     | 112       | 0.696       | 0.918    | 0.792 | 1.000           | -                      | 63     | 14             |
| llm_condition@1#45b3761c700e           | condition       | all     | 120     | 137     | 120       | 1.000       | 0.876    | 0.934 | 1.000           | -                      | 56     | 56             |
| llm_condition@1#45b3761c700e           | all             | all     | 120     | 137     | 120       | 1.000       | 0.876    | 0.934 | 1.000           | -                      | 56     | 56             |
| llm_measurement@1#4171ae269b7f         | measurement     | all     | 237     | 552     | 204       | 0.861       | 0.370    | 0.517 | 1.000           | 0.892                  | 59     | 52             |
| llm_measurement@1#4171ae269b7f         | all             | all     | 237     | 552     | 204       | 0.861       | 0.370    | 0.517 | 1.000           | -                      | 59     | 52             |
| llm_metric@1#f77fae6f7754              | metric          | all     | 122     | 122     | 108       | 0.885       | 0.885    | 0.885 | 1.000           | -                      | 24     | 10             |
| llm_metric@1#f77fae6f7754              | all             | all     | 122     | 122     | 108       | 0.885       | 0.885    | 0.885 | 1.000           | -                      | 24     | 10             |
| number_measurement@1#9489bf6f9408      | measurement     | all     | 343     | 600     | 310       | 0.904       | 0.517    | 0.657 | 1.000           | 0.948                  | 131    | 124            |
| number_measurement@1#9489bf6f9408      | all             | all     | 343     | 600     | 310       | 0.904       | 0.517    | 0.657 | 1.000           | -                      | 131    | 124            |
| regex_condition@2#1d6558c26117         | condition       | all     | 162     | 332     | 159       | 0.981       | 0.479    | 0.644 | 1.000           | -                      | 123    | 120            |
| regex_condition@2#1d6558c26117         | all             | all     | 162     | 332     | 159       | 0.981       | 0.479    | 0.644 | 1.000           | -                      | 123    | 120            |
| regex_measurement_units@1#a0d7822bd8cd | measurement     | all     | 579     | 1768    | 551       | 0.952       | 0.312    | 0.470 | 1.000           | 0.517                  | 520    | 492            |
| regex_measurement_units@1#a0d7822bd8cd | all             | all     | 579     | 1768    | 551       | 0.952       | 0.312    | 0.470 | 1.000           | -                      | 520    | 492            |
| regex_metric@2#7b60cc978d29            | metric          | all     | 216     | 263     | 192       | 0.889       | 0.730    | 0.802 | 1.000           | -                      | 142    | 118            |
| regex_metric@2#7b60cc978d29            | all             | all     | 216     | 263     | 192       | 0.889       | 0.730    | 0.802 | 1.000           | -                      | 142    | 118            |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                              | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|----------------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_condition@1#ea9c557ddc1a        | 46      | 0             | 0              | 0               | 0.300     |
| abbrev_metric@1#52506d2e3a69           | 54      | 0             | 0              | 0               | 0.347     |
| gliner_condition@1#c8fde69a32e1        | 46      | 149           | 0              | 0               | 0.345     |
| gliner_metric@1#ce2c7d899fd3           | 54      | 177           | 0              | 0               | 0.381     |
| llm_condition@1#45b3761c700e           | 46      | 81            | 93625          | 12096           | 0.317     |
| llm_measurement@1#4171ae269b7f         | 30      | 60            | 97383          | 38644           | 0.240     |
| llm_metric@1#f77fae6f7754              | 54      | 68            | 78836          | 10934           | 0.368     |
| llm_screen@1#41b0d6e6793f              | 109     | 109           | 102099         | 8160            | 0.731     |
| number_measurement@1#9489bf6f9408      | 32      | 0             | 0              | 0               | 0.276     |
| regex_condition@2#1d6558c26117         | 106     | 0             | 0              | 0               | 0.701     |
| regex_measurement_units@1#a0d7822bd8cd | 106     | 0             | 0              | 0               | 0.791     |
| regex_metric@2#7b60cc978d29            | 106     | 0             | 0              | 0               | 0.706     |
| regex_screen@1#858a6ebc69c6            | 112     | 0             | 0              | 0               | 0.735     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 901     | 8.045       |
| input_tokens     | 371943  | 3320.920    |
| made_model_calls | 644     | 5.750       |
| model_calls      | 644     | 5.750       |
| output_tokens    | 69834   | 623.518     |
| seconds          | 712.604 | 6.363       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 8.045          |
| model_calls   | 5.750          |
| input_tokens  | 3320.920       |
| output_tokens | 623.518        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 19          |
| 2               | 11          |
| 3               | 20          |
| exhausted       | 56          |
| skipped         | 6           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 0    | 0    | 6    | 1.000       | 1.000    |

Screened out wrongly: none
