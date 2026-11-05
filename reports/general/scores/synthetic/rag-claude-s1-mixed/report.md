# Evaluation of run rag-claude-s1-mixed on rag-claude-s1-ec928480

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 24      | 38      | 24        | 1.000       | 0.632    | 0.774 | 0.958           |
| all             | paraphrased   | 22      | 34      | 22        | 1.000       | 0.647    | 0.786 | 0.955           |
| all             | distributed   | 25      | 26      | 24        | 0.960       | 0.923    | 0.941 | 1.000           |
| all             | complex       | 60      | 74      | 60        | 1.000       | 0.811    | 0.896 | 1.000           |
| all             | contradictory | 26      | 38      | 24        | 0.923       | 0.632    | 0.750 | 0.958           |
| all             | all           | 157     | 210     | 154       | 0.981       | 0.733    | 0.839 | 0.981           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 0.875           |
| condition       | paraphrased   | 10      | 13      | 10        | 1.000       | 0.769    | 0.870 | 1.000           |
| condition       | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 0.875           |
| condition       | all           | 43      | 61      | 43        | 1.000       | 0.705    | 0.827 | 0.953           |
| measurement     | explicit      | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 1.000           |
| measurement     | paraphrased   | 6       | 13      | 6         | 1.000       | 0.462    | 0.632 | 1.000           |
| measurement     | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| measurement     | complex       | 36      | 50      | 36        | 1.000       | 0.720    | 0.837 | 1.000           |
| measurement     | contradictory | 10      | 15      | 8         | 0.800       | 0.533    | 0.640 | 1.000           |
| measurement     | all           | 68      | 102     | 66        | 0.971       | 0.647    | 0.776 | 1.000           |
| metric          | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased   | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 0.500           |
| metric          | distributed   | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 26      | 27      | 25        | 0.962       | 0.926    | 0.943 | 0.960           |

Facts no item matched: 56; items matching no fact: 3.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| paraphrased   | 6                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 0.500       |
| distributed   | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| complex       | 36                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 0.000       |
| contradictory | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| all           | 66                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.700       |

## C. Synthesis

| system               | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|----------------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine      | mixed   | mixed      | yes             | 20        | 20           | 0.900                | 0.900          | 1.000               | 0.900                           | -              | -         |
| bm25-answer-baseline | mixed   | mixed      | yes             | 20        | 20           | 0.700                | 0.900          | 0.778               | 0.700                           | 0.727          | 0.727     |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system               | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|---------------|----------------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| explicit      | bm25-answer-baseline | 4         | 4            | 1.000                | 1.000          | 1.000               | 1.000                           | 1.000          | 1.000     |
| explicit      | evidence-engine      | 4         | 4            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |
| paraphrased   | bm25-answer-baseline | 4         | 4            | 0.750                | 0.750          | 1.000               | 0.750                           | 0.333          | 0.333     |
| paraphrased   | evidence-engine      | 4         | 4            | 0.500                | 0.500          | 1.000               | 0.500                           | -              | -         |
| distributed   | bm25-answer-baseline | 4         | 4            | 0.750                | 0.750          | 1.000               | 0.750                           | 0.667          | 0.667     |
| distributed   | evidence-engine      | 4         | 4            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |
| complex       | bm25-answer-baseline | 4         | 4            | 0.500                | 1.000          | 0.500               | 0.500                           | 0.600          | 0.600     |
| complex       | evidence-engine      | 4         | 4            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |
| contradictory | bm25-answer-baseline | 4         | 4            | 0.500                | 1.000          | 0.500               | 0.500                           | 0.750          | 0.750     |
| contradictory | evidence-engine      | 4         | 4            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 4    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 0    | 0    | 0    | n/a         | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | n/a         | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Cost per system

| system               | model_calls   | input_tokens   | output_tokens   | tokens   |
|----------------------|---------------|----------------|-----------------|----------|
| evidence-engine      | 64            | 79408          | 13356           | 92764    |
| bm25-answer-baseline | 2             | 13172          | 2759            | 15931    |

Model calls and tokens each system recorded (D41): the engine's run.json `cost`, a baseline's answering and mapping calls, the agent baseline's agent (its tokens not split into in and out). The engine's counts include calls replayed from its record cache (the system's cost, not this rerun's spend: `made_model_calls` under Cost is that). `-`: not recorded.

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or passage search), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit      | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | paraphrased   | 4         | 2                | 4                | 2          | 0            |
| evidence-engine | distributed   | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | complex       | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | contradictory | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | all           | 20        | 18               | 20               | 2          | 0            |

Not attributed (not this oracle's counterpart): bm25-answer-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.827 [0.75, 0.91] | BCa      |
| metric          | 0.943 [0.83, 0.98] | BCa      |
| measurement     | 0.776 [0.64, 0.88] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.839 [0.77, 0.91] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system               | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|----------------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine      | 0.900 [0.70, 1.00]   | BCa      | -                     | -               | -          |
| bm25-answer-baseline | 0.700 [0.45, 0.85]   | BCa      | 0.200 [0.00, 0.45]    | BCa             | 20         |

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
| llm_author_claim@1#30bafc9430a4   | 0       | 0               | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | 21      | 21              | 20     | 20             |
| llm_measurement@1#341c436d3c29    | 45      | 45              | 35     | 35             |
| llm_metric@1#dcbd836bf6b8         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#6b89fc3599f7 | 20      | 20              | 20     | 20             |
| regex_condition@2#96b289932633    | 23      | 23              | 22     | 22             |
| regex_measurement@2#67eb53dc0d9c  | 33      | 31              | 23     | 21             |
| regex_metric@2#c011982de96a       | 24      | 23              | 24     | 23             |

Facts no extractor found: condition 18, measurement 36, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | all             | all     | 0       | 210     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | condition       | all     | 21      | 36      | 21        | 1.000       | 0.583    | 0.737 | 1.000           | -                      | 20     | 20             |
| llm_condition@1#73b7cbb40c1e      | all             | all     | 21      | 36      | 21        | 1.000       | 0.583    | 0.737 | 1.000           | -                      | 20     | 20             |
| llm_measurement@1#341c436d3c29    | measurement     | all     | 45      | 69      | 45        | 1.000       | 0.652    | 0.789 | 1.000           | 1.000                  | 35     | 35             |
| llm_measurement@1#341c436d3c29    | all             | all     | 45      | 69      | 45        | 1.000       | 0.652    | 0.789 | 1.000           | -                      | 35     | 35             |
| llm_metric@1#dcbd836bf6b8         | metric          | all     | 2       | 3       | 2         | 1.000       | 0.667    | 0.800 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#dcbd836bf6b8         | all             | all     | 2       | 3       | 2         | 1.000       | 0.667    | 0.800 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#6b89fc3599f7 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#6b89fc3599f7 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#96b289932633    | condition       | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 0.913           | -                      | 22     | 22             |
| regex_condition@2#96b289932633    | all             | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 0.913           | -                      | 22     | 22             |
| regex_measurement@2#67eb53dc0d9c  | measurement     | all     | 33      | 102     | 31        | 0.939       | 0.304    | 0.459 | 1.000           | 1.000                  | 23     | 21             |
| regex_measurement@2#67eb53dc0d9c  | all             | all     | 33      | 102     | 31        | 0.939       | 0.304    | 0.459 | 1.000           | -                      | 23     | 21             |
| regex_metric@2#c011982de96a       | metric          | all     | 24      | 27      | 23        | 0.958       | 0.852    | 0.902 | 0.957           | -                      | 24     | 23             |
| regex_metric@2#c011982de96a       | all             | all     | 24      | 27      | 23        | 0.958       | 0.852    | 0.902 | 0.957           | -                      | 24     | 23             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#73b7cbb40c1e      | 12      | 15            | 17774          | 1704            | 0.083     |
| llm_measurement@1#341c436d3c29    | 13      | 26            | 39339          | 9706            | 0.103     |
| llm_metric@1#dcbd836bf6b8         | 3       | 3             | 3614           | 195             | 0.020     |
| llm_screen@1#b51a1127185c         | 20      | 20            | 18681          | 1751            | 0.135     |
| regex_author_claim@2#6b89fc3599f7 | 20      | 0             | 0              | 0               | 0.133     |
| regex_condition@2#96b289932633    | 20      | 0             | 0              | 0               | 0.133     |
| regex_measurement@2#67eb53dc0d9c  | 20      | 0             | 0              | 0               | 0.146     |
| regex_metric@2#c011982de96a       | 20      | 0             | 0              | 0               | 0.135     |
| regex_screen@1#3fb490c481d0       | 20      | 0             | 0              | 0               | 0.133     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 148     | 7.400       |
| calls            | 148     | 7.400       |
| input_tokens     | 79408   | 3970.400    |
| made_model_calls | 0       | 0.000       |
| model_calls      | 64      | 3.200       |
| output_tokens    | 13356   | 667.800     |
| seconds          | 2.637   | 0.132       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.400          |
| model_calls   | 3.200          |
| input_tokens  | 3970.400       |
| output_tokens | 667.800        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 5           |
| 1               | 13          |
| exhausted       | 2           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
