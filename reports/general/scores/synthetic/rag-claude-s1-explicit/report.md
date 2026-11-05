# Evaluation of run rag-claude-s1-explicit on rag-claude-s1-eb14377d

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: explicit

## A. Extraction

| evidence_type   | level    | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|----------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit | 126     | 162     | 122       | 0.968       | 0.753    | 0.847 | 0.992           |
| all             | all      | 126     | 162     | 122       | 0.968       | 0.753    | 0.847 | 0.992           |
| author_claim    | explicit | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit | 41      | 61      | 41        | 1.000       | 0.672    | 0.804 | 0.976           |
| condition       | all      | 41      | 61      | 41        | 1.000       | 0.672    | 0.804 | 0.976           |
| measurement     | explicit | 41      | 61      | 41        | 1.000       | 0.672    | 0.804 | 1.000           |
| measurement     | all      | 41      | 61      | 41        | 1.000       | 0.672    | 0.804 | 1.000           |
| metric          | explicit | 24      | 20      | 20        | 0.833       | 1.000    | 0.909 | 1.000           |
| metric          | all      | 24      | 20      | 20        | 0.833       | 1.000    | 0.909 | 1.000           |

Facts no item matched: 40; items matching no fact: 4.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Integration

| level    | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|----------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit | 41                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 1.000       |
| all      | 41                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 1.000       |

## C. Synthesis

| system               | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|----------------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine      | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |
| bm25-answer-baseline | mixed   | mixed      | yes             | 20        | 20           | 0.900                | 0.900          | 1.000               | 0.900                           | 1.000          | 1.000     |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level    | system               | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|----------|----------------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| explicit | bm25-answer-baseline | 20        | 20           | 0.900                | 0.900          | 1.000               | 0.900                           | 1.000          | 1.000     |
| explicit | evidence-engine      | 20        | 20           | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |

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
| evidence-engine      | 59            | 65930          | 9076            | 75006    |
| bm25-answer-baseline | 2             | 12495          | 2272            | 14767    |

Model calls and tokens each system recorded (D41): the engine's run.json `cost`, a baseline's answering and mapping calls, the agent baseline's agent (its tokens not split into in and out). The engine's counts include calls replayed from its record cache (the system's cost, not this rerun's spend: `made_model_calls` under Cost is that). `-`: not recorded.

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or passage search), downstream when it is wrong too (synthesis or reasoning).

| system          | level    | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|----------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit | 20        | 20               | 20               | 0          | 0            |
| evidence-engine | all      | 20        | 20               | 20               | 0          | 0            |

Not attributed (not this oracle's counterpart): bm25-answer-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.804 [0.74, 0.87] | BCa      |
| metric          | 0.909 [0.82, 0.98] | BCa      |
| measurement     | 0.804 [0.74, 0.87] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.847 [0.80, 0.90] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system               | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|----------------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine      | 1.000 [n/a]          | -        | -                     | -               | -          |
| bm25-answer-baseline | 0.900 [0.70, 1.00]   | BCa      | 0.100 [0.00, 0.30]    | BCa             | 20         |

## Locate recall

| evidence_type   | level    | placements   | inside   | recall   |
|-----------------|----------|--------------|----------|----------|
| all             | explicit | 417          | 417      | 1.000    |
| all             | all      | 417          | 417      | 1.000    |
| author_claim    | explicit | 40           | 40       | 1.000    |
| author_claim    | all      | 40           | 40       | 1.000    |
| condition       | explicit | 172          | 172      | 1.000    |
| condition       | all      | 172          | 172      | 1.000    |
| measurement     | explicit | 61           | 61       | 1.000    |
| measurement     | all      | 61           | 61       | 1.000    |
| metric          | explicit | 144          | 144      | 1.000    |
| metric          | all      | 144          | 144      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | 0       | 0               | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | 14      | 14              | 13     | 13             |
| llm_measurement@1#341c436d3c29    | 25      | 25              | 17     | 17             |
| llm_metric@1#dcbd836bf6b8         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#6b89fc3599f7 | 20      | 20              | 20     | 20             |
| regex_condition@2#96b289932633    | 28      | 28              | 27     | 27             |
| regex_measurement@2#67eb53dc0d9c  | 24      | 24              | 16     | 16             |
| regex_metric@2#c011982de96a       | 22      | 18              | 22     | 18             |

Facts no extractor found: condition 20, measurement 20

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | all             | all     | 0       | 162     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | condition       | all     | 14      | 30      | 14        | 1.000       | 0.467    | 0.636 | 1.000           | -                      | 13     | 13             |
| llm_condition@1#73b7cbb40c1e      | all             | all     | 14      | 30      | 14        | 1.000       | 0.467    | 0.636 | 1.000           | -                      | 13     | 13             |
| llm_measurement@1#341c436d3c29    | measurement     | all     | 25      | 38      | 25        | 1.000       | 0.658    | 0.794 | 1.000           | 1.000                  | 17     | 17             |
| llm_measurement@1#341c436d3c29    | all             | all     | 25      | 38      | 25        | 1.000       | 0.658    | 0.794 | 1.000           | -                      | 17     | 17             |
| llm_metric@1#dcbd836bf6b8         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#dcbd836bf6b8         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#6b89fc3599f7 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#6b89fc3599f7 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#96b289932633    | condition       | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 0.964           | -                      | 27     | 27             |
| regex_condition@2#96b289932633    | all             | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 0.964           | -                      | 27     | 27             |
| regex_measurement@2#67eb53dc0d9c  | measurement     | all     | 24      | 61      | 24        | 1.000       | 0.393    | 0.565 | 1.000           | 1.000                  | 16     | 16             |
| regex_measurement@2#67eb53dc0d9c  | all             | all     | 24      | 61      | 24        | 1.000       | 0.393    | 0.565 | 1.000           | -                      | 16     | 16             |
| regex_metric@2#c011982de96a       | metric          | all     | 22      | 20      | 18        | 0.818       | 0.900    | 0.857 | 1.000           | -                      | 22     | 18             |
| regex_metric@2#c011982de96a       | all             | all     | 22      | 20      | 18        | 0.818       | 0.900    | 0.857 | 1.000           | -                      | 22     | 18             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#73b7cbb40c1e      | 10      | 13            | 14042          | 1238            | 0.070     |
| llm_measurement@1#341c436d3c29    | 12      | 24            | 32776          | 6101            | 0.089     |
| llm_metric@1#dcbd836bf6b8         | 2       | 2             | 2188           | 166             | 0.014     |
| llm_screen@1#b51a1127185c         | 20      | 20            | 16924          | 1571            | 0.135     |
| regex_author_claim@2#6b89fc3599f7 | 20      | 0             | 0              | 0               | 0.136     |
| regex_condition@2#96b289932633    | 20      | 0             | 0              | 0               | 0.134     |
| regex_measurement@2#67eb53dc0d9c  | 20      | 0             | 0              | 0               | 0.138     |
| regex_metric@2#c011982de96a       | 20      | 0             | 0              | 0               | 0.135     |
| regex_screen@1#3fb490c481d0       | 20      | 0             | 0              | 0               | 0.134     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 144     | 7.200       |
| input_tokens     | 65930   | 3296.500    |
| made_model_calls | 59      | 2.950       |
| model_calls      | 59      | 2.950       |
| output_tokens    | 9076    | 453.800     |
| seconds          | 96.758  | 4.838       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.200          |
| model_calls   | 2.950          |
| input_tokens  | 3296.500       |
| output_tokens | 453.800        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 8           |
| 1               | 12          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
