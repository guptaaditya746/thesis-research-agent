# Evaluation of run rag-claude-s1-mixed-r2 on rag-claude-s1-ec928480

Question: Does retrieval-augmented generation reduce the hallucination rate of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 37      | 38      | 29        | 0.784       | 0.763    | 0.773 | 0.966           |
| all             | paraphrased   | 38      | 34      | 16        | 0.421       | 0.471    | 0.444 | 0.938           |
| all             | distributed   | 34      | 26      | 20        | 0.588       | 0.769    | 0.667 | 1.000           |
| all             | complex       | 66      | 74      | 44        | 0.667       | 0.595    | 0.629 | 1.000           |
| all             | contradictory | 34      | 38      | 25        | 0.735       | 0.658    | 0.694 | 0.960           |
| all             | all           | 209     | 210     | 134       | 0.641       | 0.638    | 0.640 | 0.978           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 15      | 15      | 12        | 0.800       | 0.800    | 0.800 | 0.917           |
| condition       | paraphrased   | 30      | 13      | 11        | 0.367       | 0.846    | 0.512 | 0.909           |
| condition       | distributed   | 17      | 9       | 8         | 0.471       | 0.889    | 0.615 | 1.000           |
| condition       | complex       | 23      | 9       | 9         | 0.391       | 1.000    | 0.562 | 1.000           |
| condition       | contradictory | 17      | 15      | 10        | 0.588       | 0.667    | 0.625 | 0.900           |
| condition       | all           | 102     | 61      | 50        | 0.490       | 0.820    | 0.613 | 0.940           |
| measurement     | explicit      | 11      | 15      | 9         | 0.818       | 0.600    | 0.692 | 1.000           |
| measurement     | paraphrased   | 0       | 13      | 0         | n/a         | 0.000    | 0.000 | -               |
| measurement     | distributed   | 4       | 9       | 4         | 1.000       | 0.444    | 0.615 | 1.000           |
| measurement     | complex       | 20      | 50      | 20        | 1.000       | 0.400    | 0.571 | 1.000           |
| measurement     | contradictory | 9       | 15      | 7         | 0.778       | 0.467    | 0.583 | 1.000           |
| measurement     | all           | 44      | 102     | 40        | 0.909       | 0.392    | 0.548 | 1.000           |
| metric          | explicit      | 7       | 4       | 4         | 0.571       | 1.000    | 0.727 | 1.000           |
| metric          | paraphrased   | 4       | 4       | 1         | 0.250       | 0.250    | 0.250 | 1.000           |
| metric          | distributed   | 9       | 4       | 4         | 0.444       | 1.000    | 0.615 | 1.000           |
| metric          | complex       | 19      | 11      | 11        | 0.579       | 1.000    | 0.733 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 43      | 27      | 24        | 0.558       | 0.889    | 0.686 | 1.000           |

Facts no item matched: 76; items matching no fact: 75.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 9                      | 0.778                  | 1.000                     | 0.778             | 0.778             | 0.667          | 3         | 0.667       |
| paraphrased   | 0                      | -                      | -                         | -                 | -                 | -              | 3         | 0.000       |
| distributed   | 4                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 2         | 1.000       |
| complex       | 20                     | 0.000                  | 0.550                     | 0.150             | 0.550             | 0.000          | 0         | -           |
| contradictory | 7                      | 0.286                  | 0.857                     | 0.286             | 0.857             | 0.286          | 1         | 1.000       |
| all           | 40                     | 0.325                  | 0.750                     | 0.400             | 0.700             | 0.300          | 9         | 0.556       |

## C. Synthesis

| system          | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|-----------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine | supported | mixed      | no              | 20        | 9            | 0.667                | 0.667          | 1.000               | 0.850                           | -              | -         |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| explicit      | evidence-engine | 4         | 3            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |
| paraphrased   | evidence-engine | 4         | 3            | 0.000                | 0.000          | -                   | 0.250                           | -              | -         |
| distributed   | evidence-engine | 4         | 2            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |
| complex       | evidence-engine | 4         | 0            | -                    | -              | -                   | 1.000                           | -              | -         |
| contradictory | evidence-engine | 4         | 1            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 1    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 0    | 0    | 0    | n/a         | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | n/a         | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.613 [0.55, 0.70] | BCa      |
| metric          | 0.686 [0.59, 0.80] | BCa      |
| measurement     | 0.548 [0.39, 0.74] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.640 [0.57, 0.74] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.667 [0.33, 0.89]   | BCa      | -                     | -               | -          |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 88           | 88       | 1.000    |
| all             | paraphrased   | 73           | 73       | 1.000    |
| all             | distributed   | 75           | 75       | 1.000    |
| all             | complex       | 159          | 159      | 1.000    |
| all             | contradictory | 88           | 88       | 1.000    |
| all             | all           | 483          | 483      | 1.000    |
| author_claim    | explicit      | 8            | 8        | 1.000    |
| author_claim    | paraphrased   | 8            | 8        | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
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

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| abbrev_condition@1#8587f7b799e0   | 2       | 2               | 0      | 0              |
| abbrev_metric@1#1c52ebcdca5c      | 2       | 2               | 0      | 0              |
| gliner_condition@1#6df192dba74f   | 62      | 12              | 58     | 8              |
| gliner_metric@1#cdbeb73388e0      | 30      | 17              | 14     | 1              |
| llm_author_claim@1#0bbf299aba25   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 25      | 24              | 20     | 19             |
| llm_measurement@1#02bd5a7ab104    | 10      | 8               | 8      | 6              |
| llm_metric@1#41e1e53a1fc4         | 14      | 14              | 2      | 2              |
| number_measurement@1#d7f39465e8e3 | 4       | 4               | 2      | 2              |
| regex_author_claim@2#f0e017f040b9 | 20      | 20              | 20     | 20             |
| regex_condition@2#dacfca378fed    | 23      | 22              | 18     | 17             |
| regex_measurement@2#8955e245e6dd  | 33      | 31              | 32     | 30             |
| regex_metric@2#ae09439dbca7       | 24      | 18              | 11     | 5              |

Facts no extractor found: condition 11, measurement 62, metric 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_condition@1#8587f7b799e0   | condition       | all     | 2       | 36      | 2         | 1.000       | 0.056    | 0.105 | 1.000           | -                      | 0      | 0              |
| abbrev_condition@1#8587f7b799e0   | all             | all     | 2       | 36      | 2         | 1.000       | 0.056    | 0.105 | 1.000           | -                      | 0      | 0              |
| abbrev_metric@1#1c52ebcdca5c      | metric          | all     | 2       | 21      | 2         | 1.000       | 0.095    | 0.174 | 1.000           | -                      | 0      | 0              |
| abbrev_metric@1#1c52ebcdca5c      | all             | all     | 2       | 21      | 2         | 1.000       | 0.095    | 0.174 | 1.000           | -                      | 0      | 0              |
| gliner_condition@1#6df192dba74f   | condition       | all     | 62      | 36      | 12        | 0.194       | 0.333    | 0.245 | 0.833           | -                      | 58     | 8              |
| gliner_condition@1#6df192dba74f   | all             | all     | 62      | 36      | 12        | 0.194       | 0.333    | 0.245 | 0.833           | -                      | 58     | 8              |
| gliner_metric@1#cdbeb73388e0      | metric          | all     | 30      | 21      | 17        | 0.567       | 0.810    | 0.667 | 1.000           | -                      | 14     | 1              |
| gliner_metric@1#cdbeb73388e0      | all             | all     | 30      | 21      | 17        | 0.567       | 0.810    | 0.667 | 1.000           | -                      | 14     | 1              |
| llm_author_claim@1#0bbf299aba25   | all             | all     | 0       | 210     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 25      | 36      | 24        | 0.960       | 0.667    | 0.787 | 1.000           | -                      | 20     | 19             |
| llm_condition@1#45b3761c700e      | all             | all     | 25      | 36      | 24        | 0.960       | 0.667    | 0.787 | 1.000           | -                      | 20     | 19             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 10      | 12      | 8         | 0.800       | 0.667    | 0.727 | 1.000           | 1.000                  | 8      | 6              |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 10      | 12      | 8         | 0.800       | 0.667    | 0.727 | 1.000           | -                      | 8      | 6              |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 14      | 21      | 14        | 1.000       | 0.667    | 0.800 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 14      | 21      | 14        | 1.000       | 0.667    | 0.800 | 1.000           | -                      | 2      | 2              |
| number_measurement@1#d7f39465e8e3 | measurement     | all     | 4       | 12      | 4         | 1.000       | 0.333    | 0.500 | 1.000           | 0.500                  | 2      | 2              |
| number_measurement@1#d7f39465e8e3 | all             | all     | 4       | 12      | 4         | 1.000       | 0.333    | 0.500 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#f0e017f040b9 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#f0e017f040b9 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#dacfca378fed    | condition       | all     | 23      | 61      | 22        | 0.957       | 0.361    | 0.524 | 0.955           | -                      | 18     | 17             |
| regex_condition@2#dacfca378fed    | all             | all     | 23      | 61      | 22        | 0.957       | 0.361    | 0.524 | 0.955           | -                      | 18     | 17             |
| regex_measurement@2#8955e245e6dd  | measurement     | all     | 33      | 102     | 31        | 0.939       | 0.304    | 0.459 | 1.000           | 0.194                  | 32     | 30             |
| regex_measurement@2#8955e245e6dd  | all             | all     | 33      | 102     | 31        | 0.939       | 0.304    | 0.459 | 1.000           | -                      | 32     | 30             |
| regex_metric@2#ae09439dbca7       | metric          | all     | 24      | 27      | 18        | 0.750       | 0.667    | 0.706 | 1.000           | -                      | 11     | 5              |
| regex_metric@2#ae09439dbca7       | all             | all     | 24      | 27      | 18        | 0.750       | 0.667    | 0.706 | 1.000           | -                      | 11     | 5              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_condition@1#8587f7b799e0   | 12      | 0             | 0              | 0               | 0.077     |
| abbrev_metric@1#1c52ebcdca5c      | 14      | 0             | 0              | 0               | 0.091     |
| gliner_condition@1#6df192dba74f   | 12      | 40            | 0              | 0               | 0.088     |
| gliner_metric@1#cdbeb73388e0      | 14      | 46            | 0              | 0               | 0.097     |
| llm_condition@1#45b3761c700e      | 12      | 15            | 18108          | 2367            | 0.080     |
| llm_measurement@1#02bd5a7ab104    | 4       | 8             | 10914          | 1870            | 0.028     |
| llm_metric@1#41e1e53a1fc4         | 14      | 14            | 17243          | 1261            | 0.091     |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 18681          | 1732            | 0.131     |
| number_measurement@1#d7f39465e8e3 | 4       | 0             | 0              | 0               | 0.027     |
| regex_author_claim@2#f0e017f040b9 | 20      | 0             | 0              | 0               | 0.130     |
| regex_condition@2#dacfca378fed    | 20      | 0             | 0              | 0               | 0.129     |
| regex_measurement@2#8955e245e6dd  | 20      | 0             | 0              | 0               | 0.134     |
| regex_metric@2#ae09439dbca7       | 20      | 0             | 0              | 0               | 0.131     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.129     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 206     | 10.300      |
| input_tokens     | 64946   | 3247.300    |
| made_model_calls | 143     | 7.150       |
| model_calls      | 143     | 7.150       |
| output_tokens    | 7230    | 361.500     |
| seconds          | 82.955  | 4.148       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.300         |
| model_calls   | 7.150          |
| input_tokens  | 3247.300       |
| output_tokens | 361.500        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 2           |
| 2               | 1           |
| 3               | 3           |
| exhausted       | 14          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
