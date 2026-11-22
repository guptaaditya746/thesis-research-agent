# Evaluation of run rag-claude-s1-complex on rag-claude-s1-a5fa1731

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 305     | 431     | 302       | 0.990       | 0.701    | 0.821 | 1.000           |
| all             | all     | 305     | 431     | 302       | 0.990       | 0.701    | 0.821 | 1.000           |
| author_claim    | complex | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 46      | 61      | 46        | 1.000       | 0.754    | 0.860 | 1.000           |
| condition       | all     | 46      | 61      | 46        | 1.000       | 0.754    | 0.860 | 1.000           |
| measurement     | complex | 187     | 300     | 186       | 0.995       | 0.620    | 0.764 | 1.000           |
| measurement     | all     | 187     | 300     | 186       | 0.995       | 0.620    | 0.764 | 1.000           |
| metric          | complex | 52      | 50      | 50        | 0.962       | 1.000    | 0.980 | 1.000           |
| metric          | all     | 52      | 50      | 50        | 0.962       | 1.000    | 0.980 | 1.000           |

Facts no item matched: 129; items matching no fact: 3.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 186                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.000       |
| all     | 186                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.000       |

## C. Synthesis

| system               | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|----------------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine      | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |
| bm25-answer-baseline | mixed   | mixed      | yes             | 20        | 20           | 0.850                | 0.950          | 0.895               | 0.850                           | 1.000          | 1.000     |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level   | system               | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|---------|----------------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| complex | bm25-answer-baseline | 20        | 20           | 0.850                | 0.950          | 0.895               | 0.850                           | 1.000          | 1.000     |
| complex | evidence-engine      | 20        | 20           | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | n/a         | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | n/a         | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | n/a         | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | yes              | yes                  |

## Cost per system

| system               | model_calls   | input_tokens   | output_tokens   | tokens   |
|----------------------|---------------|----------------|-----------------|----------|
| evidence-engine      | 68            | 101178         | 34383           | 135561   |
| bm25-answer-baseline | 2             | 14219          | 2257            | 16476    |

Model calls and tokens each system recorded (D41): the engine's run.json `cost`, a baseline's answering and mapping calls, the agent baseline's agent (its tokens not split into in and out). The engine's counts include calls replayed from its record cache (the system's cost, not this rerun's spend: `made_model_calls` under Cost is that). `-`: not recorded.

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or passage search), downstream when it is wrong too (synthesis or reasoning).

| system          | level   | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | complex | 20        | 20               | 20               | 0          | 0            |
| evidence-engine | all     | 20        | 20               | 20               | 0          | 0            |

Not attributed (not this oracle's counterpart): bm25-answer-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.860 [0.79, 0.93] | BCa      |
| metric          | 0.980 [0.93, 1.00] | BCa      |
| measurement     | 0.764 [0.70, 0.84] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.821 [0.77, 0.88] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system               | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|----------------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine      | 1.000 [n/a]          | -        | -                     | -               | -          |
| bm25-answer-baseline | 0.850 [0.65, 0.95]   | BCa      | 0.150 [0.05, 0.35]    | BCa             | 20         |

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
| llm_author_claim@1#30bafc9430a4   | 0       | 0               | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | 22      | 22              | 18     | 18             |
| llm_measurement@1#341c436d3c29    | 128     | 127             | 88     | 87             |
| llm_metric@1#dcbd836bf6b8         | 5       | 5               | 2      | 2              |
| regex_author_claim@2#6b89fc3599f7 | 20      | 20              | 20     | 20             |
| regex_condition@2#96b289932633    | 28      | 28              | 24     | 24             |
| regex_measurement@2#67eb53dc0d9c  | 99      | 99              | 59     | 59             |
| regex_metric@2#c011982de96a       | 50      | 48              | 47     | 45             |

Facts no extractor found: condition 15, measurement 114

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | all             | all     | 0       | 431     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | condition       | all     | 22      | 30      | 22        | 1.000       | 0.733    | 0.846 | 1.000           | -                      | 18     | 18             |
| llm_condition@1#73b7cbb40c1e      | all             | all     | 22      | 30      | 22        | 1.000       | 0.733    | 0.846 | 1.000           | -                      | 18     | 18             |
| llm_measurement@1#341c436d3c29    | measurement     | all     | 128     | 218     | 127       | 0.992       | 0.583    | 0.734 | 1.000           | 1.000                  | 88     | 87             |
| llm_measurement@1#341c436d3c29    | all             | all     | 128     | 218     | 127       | 0.992       | 0.583    | 0.734 | 1.000           | -                      | 88     | 87             |
| llm_metric@1#dcbd836bf6b8         | metric          | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#dcbd836bf6b8         | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#6b89fc3599f7 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#6b89fc3599f7 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#96b289932633    | condition       | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 24     | 24             |
| regex_condition@2#96b289932633    | all             | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 24     | 24             |
| regex_measurement@2#67eb53dc0d9c  | measurement     | all     | 99      | 300     | 99        | 1.000       | 0.330    | 0.496 | 1.000           | 1.000                  | 59     | 59             |
| regex_measurement@2#67eb53dc0d9c  | all             | all     | 99      | 300     | 99        | 1.000       | 0.330    | 0.496 | 1.000           | -                      | 59     | 59             |
| regex_metric@2#c011982de96a       | metric          | all     | 50      | 50      | 48        | 0.960       | 0.960    | 0.960 | 1.000           | -                      | 47     | 45             |
| regex_metric@2#c011982de96a       | all             | all     | 50      | 50      | 48        | 0.960       | 0.960    | 0.960 | 1.000           | -                      | 47     | 45             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#73b7cbb40c1e      | 10      | 14            | 17865          | 1979            | 0.068     |
| llm_measurement@1#341c436d3c29    | 15      | 30            | 56573          | 30175           | 0.140     |
| llm_metric@1#dcbd836bf6b8         | 2       | 4             | 5720           | 572             | 0.014     |
| llm_screen@1#b51a1127185c         | 20      | 20            | 21020          | 1657            | 0.134     |
| regex_author_claim@2#6b89fc3599f7 | 20      | 0             | 0              | 0               | 0.129     |
| regex_condition@2#96b289932633    | 20      | 0             | 0              | 0               | 0.132     |
| regex_measurement@2#67eb53dc0d9c  | 20      | 0             | 0              | 0               | 0.148     |
| regex_metric@2#c011982de96a       | 20      | 0             | 0              | 0               | 0.147     |
| regex_screen@1#3fb490c481d0       | 20      | 0             | 0              | 0               | 0.141     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 147     | 7.350       |
| input_tokens     | 101178  | 5058.900    |
| made_model_calls | 68      | 3.400       |
| model_calls      | 68      | 3.400       |
| output_tokens    | 34383   | 1719.150    |
| seconds          | 385.317 | 19.266      |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.350          |
| model_calls   | 3.400          |
| input_tokens  | 5058.900       |
| output_tokens | 1719.150       |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 5           |
| 1               | 15          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
