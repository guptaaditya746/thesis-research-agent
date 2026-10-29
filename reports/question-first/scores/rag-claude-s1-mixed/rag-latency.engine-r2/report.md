# Evaluation of run rag-claude-s1-mixed-r2 on rag-claude-s1-ec928480

Question: Does retrieval-augmented generation change the latency of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 27      | 34      | 20        | 0.741       | 0.588    | 0.656 | 1.000           |
| all             | paraphrased   | 33      | 30      | 12        | 0.364       | 0.400    | 0.381 | 0.917           |
| all             | distributed   | 33      | 22      | 12        | 0.364       | 0.545    | 0.436 | 1.000           |
| all             | complex       | 76      | 70      | 58        | 0.763       | 0.829    | 0.795 | 1.000           |
| all             | contradictory | 34      | 34      | 21        | 0.618       | 0.618    | 0.618 | 0.952           |
| all             | all           | 203     | 190     | 123       | 0.606       | 0.647    | 0.626 | 0.984           |
| condition       | explicit      | 16      | 15      | 12        | 0.750       | 0.800    | 0.774 | 1.000           |
| condition       | paraphrased   | 30      | 13      | 11        | 0.367       | 0.846    | 0.512 | 0.909           |
| condition       | distributed   | 18      | 9       | 8         | 0.444       | 0.889    | 0.593 | 1.000           |
| condition       | complex       | 23      | 9       | 9         | 0.391       | 1.000    | 0.562 | 1.000           |
| condition       | contradictory | 17      | 15      | 10        | 0.588       | 0.667    | 0.625 | 0.900           |
| condition       | all           | 104     | 61      | 50        | 0.481       | 0.820    | 0.606 | 0.960           |
| measurement     | explicit      | 4       | 15      | 4         | 1.000       | 0.267    | 0.421 | 1.000           |
| measurement     | paraphrased   | 0       | 13      | 0         | n/a         | 0.000    | 0.000 | -               |
| measurement     | distributed   | 0       | 9       | 0         | n/a         | 0.000    | 0.000 | -               |
| measurement     | complex       | 40      | 50      | 38        | 0.950       | 0.760    | 0.844 | 1.000           |
| measurement     | contradictory | 9       | 15      | 7         | 0.778       | 0.467    | 0.583 | 1.000           |
| measurement     | all           | 53      | 102     | 49        | 0.925       | 0.480    | 0.632 | 1.000           |
| metric          | explicit      | 7       | 4       | 4         | 0.571       | 1.000    | 0.727 | 1.000           |
| metric          | paraphrased   | 3       | 4       | 1         | 0.333       | 0.250    | 0.286 | 1.000           |
| metric          | distributed   | 15      | 4       | 4         | 0.267       | 1.000    | 0.421 | 1.000           |
| metric          | complex       | 13      | 11      | 11        | 0.846       | 1.000    | 0.917 | 1.000           |
| metric          | contradictory | 8       | 4       | 4         | 0.500       | 1.000    | 0.667 | 1.000           |
| metric          | all           | 46      | 27      | 24        | 0.522       | 0.889    | 0.658 | 1.000           |

Facts no item matched: 67; items matching no fact: 80.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 4                      | 0.250                  | 0.750                     | 0.250             | 0.500             | 0.000          | 0         | -           |
| complex       | 38                     | 0.895                  | 0.895                     | 0.947             | 0.895             | 0.921          | 3         | 0.667       |
| contradictory | 7                      | 0.571                  | 0.857                     | 0.714             | 0.857             | 0.000          | 0         | -           |
| all           | 49                     | 0.796                  | 0.878                     | 0.857             | 0.857             | 0.714          | 3         | 0.667       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 3            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| explicit      | evidence-engine | 4         | 0            | -                    | -              | -                   | 1.000                           | -              | -         |
| paraphrased   | evidence-engine | 4         | 0            | -                    | -              | -                   | 1.000                           | -              | -         |
| distributed   | evidence-engine | 4         | 0            | -                    | -              | -                   | 1.000                           | -              | -         |
| complex       | evidence-engine | 4         | 3            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |
| contradictory | evidence-engine | 4         | 0            | -                    | -              | -                   | 1.000                           | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | n/a         | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | n/a         | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | n/a         | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | yes              | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.606 [0.54, 0.68] | BCa      |
| metric          | 0.658 [0.54, 0.79] | BCa      |
| measurement     | 0.632 [0.43, 0.77] | BCa      |
| all             | 0.626 [0.53, 0.73] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               | -          |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 88           | 80       | 0.909    |
| all             | paraphrased   | 73           | 65       | 0.890    |
| all             | distributed   | 75           | 67       | 0.893    |
| all             | complex       | 159          | 151      | 0.950    |
| all             | contradictory | 88           | 80       | 0.909    |
| all             | all           | 483          | 443      | 0.917    |
| author_claim    | explicit      | 8            | 0        | 0.000    |
| author_claim    | paraphrased   | 8            | 0        | 0.000    |
| author_claim    | distributed   | 8            | 0        | 0.000    |
| author_claim    | complex       | 8            | 0        | 0.000    |
| author_claim    | contradictory | 8            | 0        | 0.000    |
| author_claim    | all           | 40           | 0        | 0.000    |
| condition       | explicit      | 34           | 34       | 1.000    |
| condition       | paraphrased   | 30           | 30       | 1.000    |
| condition       | distributed   | 32           | 32       | 1.000    |
| condition       | complex       | 46           | 46       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 182          | 182      | 1.000    |
| measurement     | explicit      | 15           | 15       | 1.000    |
| measurement     | paraphrased   | 13           | 13       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 50           | 50       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 102          | 102      | 1.000    |
| metric          | explicit      | 31           | 31       | 1.000    |
| metric          | paraphrased   | 22           | 22       | 1.000    |
| metric          | distributed   | 26           | 26       | 1.000    |
| metric          | complex       | 55           | 55       | 1.000    |
| metric          | contradictory | 25           | 25       | 1.000    |
| metric          | all           | 159          | 159      | 1.000    |

## Cascade contribution

| extractor                              | found   | found_matched   | only   | only_matched   |
|----------------------------------------|---------|-----------------|--------|----------------|
| abbrev_condition@1#ea9c557ddc1a        | 2       | 2               | 0      | 0              |
| abbrev_metric@1#52506d2e3a69           | 4       | 4               | 0      | 0              |
| gliner_condition@1#c8fde69a32e1        | 62      | 11              | 57     | 6              |
| gliner_metric@1#ce2c7d899fd3           | 28      | 14              | 14     | 0              |
| llm_condition@1#45b3761c700e           | 29      | 27              | 22     | 20             |
| llm_measurement@1#4171ae269b7f         | 6       | 5               | 0      | 0              |
| llm_metric@1#f77fae6f7754              | 14      | 14              | 1      | 1              |
| number_measurement@1#9489bf6f9408      | 24      | 23              | 18     | 18             |
| regex_condition@2#1d6558c26117         | 23      | 22              | 17     | 16             |
| regex_measurement_units@1#a0d7822bd8cd | 29      | 26              | 29     | 26             |
| regex_metric@2#7b60cc978d29            | 23      | 15              | 17     | 9              |

Facts no extractor found: condition 11, measurement 53, metric 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                              | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|----------------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_condition@1#ea9c557ddc1a        | condition       | all     | 2       | 36      | 2         | 1.000       | 0.056    | 0.105 | 1.000           | -                      | 0      | 0              |
| abbrev_condition@1#ea9c557ddc1a        | all             | all     | 2       | 36      | 2         | 1.000       | 0.056    | 0.105 | 1.000           | -                      | 0      | 0              |
| abbrev_metric@1#52506d2e3a69           | metric          | all     | 4       | 17      | 4         | 1.000       | 0.235    | 0.381 | 1.000           | -                      | 0      | 0              |
| abbrev_metric@1#52506d2e3a69           | all             | all     | 4       | 17      | 4         | 1.000       | 0.235    | 0.381 | 1.000           | -                      | 0      | 0              |
| gliner_condition@1#c8fde69a32e1        | condition       | all     | 62      | 36      | 11        | 0.177       | 0.306    | 0.224 | 0.909           | -                      | 57     | 6              |
| gliner_condition@1#c8fde69a32e1        | all             | all     | 62      | 36      | 11        | 0.177       | 0.306    | 0.224 | 0.909           | -                      | 57     | 6              |
| gliner_metric@1#ce2c7d899fd3           | metric          | all     | 28      | 17      | 14        | 0.500       | 0.824    | 0.622 | 1.000           | -                      | 14     | 0              |
| gliner_metric@1#ce2c7d899fd3           | all             | all     | 28      | 17      | 14        | 0.500       | 0.824    | 0.622 | 1.000           | -                      | 14     | 0              |
| llm_condition@1#45b3761c700e           | condition       | all     | 29      | 36      | 27        | 0.931       | 0.750    | 0.831 | 1.000           | -                      | 22     | 20             |
| llm_condition@1#45b3761c700e           | all             | all     | 29      | 36      | 27        | 0.931       | 0.750    | 0.831 | 1.000           | -                      | 22     | 20             |
| llm_measurement@1#4171ae269b7f         | measurement     | all     | 6       | 18      | 5         | 0.833       | 0.278    | 0.417 | 1.000           | 1.000                  | 0      | 0              |
| llm_measurement@1#4171ae269b7f         | all             | all     | 6       | 18      | 5         | 0.833       | 0.278    | 0.417 | 1.000           | -                      | 0      | 0              |
| llm_metric@1#f77fae6f7754              | metric          | all     | 14      | 17      | 14        | 1.000       | 0.824    | 0.903 | 1.000           | -                      | 1      | 1              |
| llm_metric@1#f77fae6f7754              | all             | all     | 14      | 17      | 14        | 1.000       | 0.824    | 0.903 | 1.000           | -                      | 1      | 1              |
| number_measurement@1#9489bf6f9408      | measurement     | all     | 24      | 30      | 23        | 0.958       | 0.767    | 0.852 | 1.000           | 1.000                  | 18     | 18             |
| number_measurement@1#9489bf6f9408      | all             | all     | 24      | 30      | 23        | 0.958       | 0.767    | 0.852 | 1.000           | -                      | 18     | 18             |
| regex_condition@2#1d6558c26117         | condition       | all     | 23      | 61      | 22        | 0.957       | 0.361    | 0.524 | 0.955           | -                      | 17     | 16             |
| regex_condition@2#1d6558c26117         | all             | all     | 23      | 61      | 22        | 0.957       | 0.361    | 0.524 | 0.955           | -                      | 17     | 16             |
| regex_measurement_units@1#a0d7822bd8cd | measurement     | all     | 29      | 102     | 26        | 0.897       | 0.255    | 0.397 | 1.000           | 0.615                  | 29     | 26             |
| regex_measurement_units@1#a0d7822bd8cd | all             | all     | 29      | 102     | 26        | 0.897       | 0.255    | 0.397 | 1.000           | -                      | 29     | 26             |
| regex_metric@2#7b60cc978d29            | metric          | all     | 23      | 27      | 15        | 0.652       | 0.556    | 0.600 | 1.000           | -                      | 17     | 9              |
| regex_metric@2#7b60cc978d29            | all             | all     | 23      | 27      | 15        | 0.652       | 0.556    | 0.600 | 1.000           | -                      | 17     | 9              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                              | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|----------------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_condition@1#ea9c557ddc1a        | 12      | 0             | 0              | 0               | 0.079     |
| abbrev_metric@1#52506d2e3a69           | 16      | 0             | 0              | 0               | 0.102     |
| gliner_condition@1#c8fde69a32e1        | 12      | 40            | 0              | 0               | 0.088     |
| gliner_metric@1#ce2c7d899fd3           | 16      | 51            | 0              | 0               | 0.112     |
| llm_condition@1#45b3761c700e           | 12      | 15            | 18091          | 2621            | 0.084     |
| llm_measurement@1#4171ae269b7f         | 1       | 2             | 3332           | 960             | 0.007     |
| llm_metric@1#f77fae6f7754              | 16      | 20            | 22910          | 1582            | 0.104     |
| llm_screen@1#41b0d6e6793f              | 20      | 20            | 18681          | 1750            | 0.131     |
| number_measurement@1#9489bf6f9408      | 2       | 0             | 0              | 0               | 0.017     |
| regex_condition@2#1d6558c26117         | 20      | 0             | 0              | 0               | 0.129     |
| regex_measurement_units@1#a0d7822bd8cd | 20      | 0             | 0              | 0               | 0.132     |
| regex_metric@2#7b60cc978d29            | 20      | 0             | 0              | 0               | 0.139     |
| regex_screen@1#858a6ebc69c6            | 20      | 0             | 0              | 0               | 0.129     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 187     | 9.350       |
| input_tokens     | 63014   | 3150.700    |
| made_model_calls | 148     | 7.400       |
| model_calls      | 148     | 7.400       |
| output_tokens    | 6913    | 345.650     |
| seconds          | 95.209  | 4.760       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 9.350          |
| model_calls   | 7.400          |
| input_tokens  | 3150.700       |
| output_tokens | 345.650        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 1           |
| 3               | 2           |
| exhausted       | 17          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
