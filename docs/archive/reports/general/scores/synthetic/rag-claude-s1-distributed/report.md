# Evaluation of run rag-claude-s1-distributed on rag-claude-s1-869ad7e8

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 126     | 162     | 124       | 0.984       | 0.765    | 0.861 | 1.000           |
| all             | all         | 126     | 162     | 124       | 0.984       | 0.765    | 0.861 | 1.000           |
| author_claim    | distributed | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 43      | 61      | 42        | 0.977       | 0.689    | 0.808 | 1.000           |
| condition       | all         | 43      | 61      | 42        | 0.977       | 0.689    | 0.808 | 1.000           |
| measurement     | distributed | 42      | 61      | 42        | 1.000       | 0.689    | 0.816 | 1.000           |
| measurement     | all         | 42      | 61      | 42        | 1.000       | 0.689    | 0.816 | 1.000           |
| metric          | distributed | 21      | 20      | 20        | 0.952       | 1.000    | 0.976 | 1.000           |
| metric          | all         | 21      | 20      | 20        | 0.952       | 1.000    | 0.976 | 1.000           |

Facts no item matched: 38; items matching no fact: 2.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 42                     | 1.000                  | 1.000                     | 1.000             | 0.976             | 1.000          | 20        | 1.000       |
| all         | 42                     | 1.000                  | 1.000                     | 1.000             | 0.976             | 1.000          | 20        | 1.000       |

## C. Synthesis

| system               | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|----------------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine      | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |
| bm25-answer-baseline | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | 1.000                           | 0.950          | 0.950     |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system               | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|-------------|----------------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| distributed | bm25-answer-baseline | 20        | 20           | 1.000                | 1.000          | 1.000               | 1.000                           | 0.950          | 0.950     |
| distributed | evidence-engine      | 20        | 20           | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |

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
| evidence-engine      | 72            | 94828          | 12167           | 106995   |
| bm25-answer-baseline | 2             | 11501          | 1897            | 13398    |

Model calls and tokens each system recorded (D41): the engine's run.json `cost`, a baseline's answering and mapping calls, the agent baseline's agent (its tokens not split into in and out). The engine's counts include calls replayed from its record cache (the system's cost, not this rerun's spend: `made_model_calls` under Cost is that). `-`: not recorded.

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or passage search), downstream when it is wrong too (synthesis or reasoning).

| system          | level       | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|-------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | distributed | 20        | 20               | 20               | 0          | 0            |
| evidence-engine | all         | 20        | 20               | 20               | 0          | 0            |

Not attributed (not this oracle's counterpart): bm25-answer-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.808 [0.75, 0.88] | BCa      |
| metric          | 0.976 [0.89, 1.00] | BCa      |
| measurement     | 0.816 [0.75, 0.89] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.861 [0.81, 0.91] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system               | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|----------------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine      | 1.000 [n/a]          | -        | -                     | -               | -          |
| bm25-answer-baseline | 1.000 [n/a]          | -        | 0.000 [n/a]           | -               | 20         |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | distributed | 418          | 418      | 1.000    |
| all             | all         | 418          | 418      | 1.000    |
| author_claim    | distributed | 40           | 40       | 1.000    |
| author_claim    | all         | 40           | 40       | 1.000    |
| condition       | distributed | 199          | 199      | 1.000    |
| condition       | all         | 199          | 199      | 1.000    |
| measurement     | distributed | 61           | 61       | 1.000    |
| measurement     | all         | 61           | 61       | 1.000    |
| metric          | distributed | 118          | 118      | 1.000    |
| metric          | all         | 118          | 118      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | 0       | 0               | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | 15      | 14              | 15     | 14             |
| llm_measurement@1#341c436d3c29    | 42      | 42              | 42     | 42             |
| llm_metric@1#dcbd836bf6b8         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#6b89fc3599f7 | 20      | 20              | 20     | 20             |
| regex_condition@2#96b289932633    | 28      | 28              | 28     | 28             |
| regex_measurement@2#67eb53dc0d9c  | 0       | 0               | 0      | 0              |
| regex_metric@2#c011982de96a       | 19      | 18              | 19     | 18             |

Facts no extractor found: condition 19, measurement 19

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | all             | all     | 0       | 162     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | condition       | all     | 15      | 30      | 14        | 0.933       | 0.467    | 0.622 | 1.000           | -                      | 15     | 14             |
| llm_condition@1#73b7cbb40c1e      | all             | all     | 15      | 30      | 14        | 0.933       | 0.467    | 0.622 | 1.000           | -                      | 15     | 14             |
| llm_measurement@1#341c436d3c29    | measurement     | all     | 42      | 61      | 42        | 1.000       | 0.689    | 0.816 | 1.000           | 1.000                  | 42     | 42             |
| llm_measurement@1#341c436d3c29    | all             | all     | 42      | 61      | 42        | 1.000       | 0.689    | 0.816 | 1.000           | -                      | 42     | 42             |
| llm_metric@1#dcbd836bf6b8         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#dcbd836bf6b8         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#6b89fc3599f7 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#6b89fc3599f7 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#96b289932633    | condition       | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 28     | 28             |
| regex_condition@2#96b289932633    | all             | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 28     | 28             |
| regex_measurement@2#67eb53dc0d9c  | measurement     | all     | 0       | 61      | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#67eb53dc0d9c  | all             | all     | 0       | 61      | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#c011982de96a       | metric          | all     | 19      | 20      | 18        | 0.947       | 0.900    | 0.923 | 1.000           | -                      | 19     | 18             |
| regex_metric@2#c011982de96a       | all             | all     | 19      | 20      | 18        | 0.947       | 0.900    | 0.923 | 1.000           | -                      | 19     | 18             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#73b7cbb40c1e      | 10      | 10            | 12585          | 1247            | 0.067     |
| llm_measurement@1#341c436d3c29    | 20      | 40            | 59626          | 8654            | 0.154     |
| llm_metric@1#dcbd836bf6b8         | 2       | 2             | 2447           | 200             | 0.013     |
| llm_screen@1#b51a1127185c         | 20      | 20            | 20170          | 2066            | 0.131     |
| regex_author_claim@2#6b89fc3599f7 | 20      | 0             | 0              | 0               | 0.130     |
| regex_condition@2#96b289932633    | 20      | 0             | 0              | 0               | 0.136     |
| regex_measurement@2#67eb53dc0d9c  | 20      | 0             | 0              | 0               | 0.135     |
| regex_metric@2#c011982de96a       | 20      | 0             | 0              | 0               | 0.150     |
| regex_screen@1#3fb490c481d0       | 20      | 0             | 0              | 0               | 0.131     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 152     | 7.600       |
| input_tokens     | 94828   | 4741.400    |
| made_model_calls | 72      | 3.600       |
| model_calls      | 72      | 3.600       |
| output_tokens    | 12167   | 608.350     |
| seconds          | 120.573 | 6.029       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.600          |
| model_calls   | 3.600          |
| input_tokens  | 4741.400       |
| output_tokens | 608.350        |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
