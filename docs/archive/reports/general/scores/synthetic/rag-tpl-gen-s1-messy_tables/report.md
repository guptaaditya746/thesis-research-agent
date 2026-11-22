# Evaluation of run rag-tpl-gen-s1-messy_tables on rag-tpl-gen-s1-67aa3bd7

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: messy_tables

## A. Extraction

| evidence_type   | level        | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|--------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | all          | 161     | 281     | 161       | 1.000       | 0.573    | 0.729 | 1.000           |
| all             | messy_tables | 161     | 281     | 161       | 1.000       | 0.573    | 0.729 | 1.000           |
| author_claim    | all          | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | messy_tables | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all          | 39      | 61      | 39        | 1.000       | 0.639    | 0.780 | 1.000           |
| condition       | messy_tables | 39      | 61      | 39        | 1.000       | 0.639    | 0.780 | 1.000           |
| measurement     | all          | 52      | 150     | 52        | 1.000       | 0.347    | 0.515 | 1.000           |
| measurement     | messy_tables | 52      | 150     | 52        | 1.000       | 0.347    | 0.515 | 1.000           |
| metric          | all          | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | messy_tables | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 120; items matching no fact: 0.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Integration

| level        | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|--------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| all          | 52                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.950       |
| messy_tables | 52                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.950       |

## C. Synthesis

| system               | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|----------------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine      | mixed   | mixed      | yes             | 20        | 20           | 0.950                | 0.950          | 1.000               | 0.950                           | -              | -         |
| bm25-answer-baseline | mixed   | mixed      | yes             | 20        | 20           | 0.900                | 0.900          | 1.000               | 0.900                           | 1.000          | 1.000     |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level        | system               | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|--------------|----------------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| messy_tables | bm25-answer-baseline | 20        | 20           | 0.900                | 0.900          | 1.000               | 0.900                           | 1.000          | 1.000     |
| messy_tables | evidence-engine      | 20        | 20           | 0.950                | 0.950          | 1.000               | 0.950                           | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | n/a         | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | n/a         | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | n/a         | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Cost per system

| system               | model_calls   | input_tokens   | output_tokens   | tokens   |
|----------------------|---------------|----------------|-----------------|----------|
| evidence-engine      | 82            | 91208          | 12116           | 103324   |
| bm25-answer-baseline | 2             | 10871          | 2972            | 13843    |

Model calls and tokens each system recorded (D41): the engine's run.json `cost`, a baseline's answering and mapping calls, the agent baseline's agent (its tokens not split into in and out). The engine's counts include calls replayed from its record cache (the system's cost, not this rerun's spend: `made_model_calls` under Cost is that). `-`: not recorded.

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or passage search), downstream when it is wrong too (synthesis or reasoning).

| system          | level        | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|--------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | all          | 20        | 19               | 20               | 1          | 0            |
| evidence-engine | messy_tables | 20        | 19               | 20               | 1          | 0            |

Not attributed (not this oracle's counterpart): bm25-answer-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.780 [0.72, 0.85] | BCa      |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 0.515 [0.45, 0.58] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.729 [0.68, 0.77] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system               | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|----------------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine      | 0.950 [0.73, 1.00]   | BCa      | -                     | -               | -          |
| bm25-answer-baseline | 0.900 [0.70, 1.00]   | BCa      | 0.050 [-0.10, 0.25]   | BCa             | 20         |

## Locate recall

| evidence_type   | level        | placements   | inside   | recall   |
|-----------------|--------------|--------------|----------|----------|
| all             | all          | 502          | 502      | 1.000    |
| all             | messy_tables | 502          | 502      | 1.000    |
| author_claim    | all          | 40           | 40       | 1.000    |
| author_claim    | messy_tables | 40           | 40       | 1.000    |
| condition       | all          | 162          | 162      | 1.000    |
| condition       | messy_tables | 162          | 162      | 1.000    |
| measurement     | all          | 150          | 150      | 1.000    |
| measurement     | messy_tables | 150          | 150      | 1.000    |
| metric          | all          | 150          | 150      | 1.000    |
| metric          | messy_tables | 150          | 150      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | 0       | 0               | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | 14      | 14              | 11     | 11             |
| llm_measurement@1#341c436d3c29    | 38      | 38              | 27     | 27             |
| llm_metric@1#dcbd836bf6b8         | 5       | 5               | 2      | 2              |
| regex_author_claim@2#6b89fc3599f7 | 20      | 20              | 20     | 20             |
| regex_condition@2#96b289932633    | 28      | 28              | 25     | 25             |
| regex_measurement@2#67eb53dc0d9c  | 25      | 25              | 14     | 14             |
| regex_metric@2#c011982de96a       | 48      | 48              | 45     | 45             |

Facts no extractor found: condition 22, measurement 98

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | all             | all     | 0       | 281     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | condition       | all     | 14      | 30      | 14        | 1.000       | 0.467    | 0.636 | 1.000           | -                      | 11     | 11             |
| llm_condition@1#73b7cbb40c1e      | all             | all     | 14      | 30      | 14        | 1.000       | 0.467    | 0.636 | 1.000           | -                      | 11     | 11             |
| llm_measurement@1#341c436d3c29    | measurement     | all     | 38      | 144     | 38        | 1.000       | 0.264    | 0.418 | 1.000           | 1.000                  | 27     | 27             |
| llm_measurement@1#341c436d3c29    | all             | all     | 38      | 144     | 38        | 1.000       | 0.264    | 0.418 | 1.000           | -                      | 27     | 27             |
| llm_metric@1#dcbd836bf6b8         | metric          | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#dcbd836bf6b8         | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#6b89fc3599f7 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#6b89fc3599f7 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#96b289932633    | condition       | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 25     | 25             |
| regex_condition@2#96b289932633    | all             | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 25     | 25             |
| regex_measurement@2#67eb53dc0d9c  | measurement     | all     | 25      | 150     | 25        | 1.000       | 0.167    | 0.286 | 1.000           | 1.000                  | 14     | 14             |
| regex_measurement@2#67eb53dc0d9c  | all             | all     | 25      | 150     | 25        | 1.000       | 0.167    | 0.286 | 1.000           | -                      | 14     | 14             |
| regex_metric@2#c011982de96a       | metric          | all     | 48      | 50      | 48        | 1.000       | 0.960    | 0.980 | 1.000           | -                      | 45     | 45             |
| regex_metric@2#c011982de96a       | all             | all     | 48      | 50      | 48        | 1.000       | 0.960    | 0.980 | 1.000           | -                      | 45     | 45             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#73b7cbb40c1e      | 10      | 20            | 19884          | 1672            | 0.066     |
| llm_measurement@1#341c436d3c29    | 19      | 38            | 50839          | 8594            | 0.140     |
| llm_metric@1#dcbd836bf6b8         | 2       | 4             | 4418           | 557             | 0.013     |
| llm_screen@1#b51a1127185c         | 20      | 20            | 16067          | 1293            | 0.127     |
| regex_author_claim@2#6b89fc3599f7 | 20      | 0             | 0              | 0               | 0.125     |
| regex_condition@2#96b289932633    | 20      | 0             | 0              | 0               | 0.126     |
| regex_measurement@2#67eb53dc0d9c  | 20      | 0             | 0              | 0               | 0.128     |
| regex_metric@2#c011982de96a       | 20      | 0             | 0              | 0               | 0.137     |
| regex_screen@1#3fb490c481d0       | 20      | 0             | 0              | 0               | 0.124     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 151     | 7.550       |
| input_tokens     | 91208   | 4560.400    |
| made_model_calls | 82      | 4.100       |
| model_calls      | 82      | 4.100       |
| output_tokens    | 12116   | 605.800     |
| seconds          | 115.984 | 5.799       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.550          |
| model_calls   | 4.100          |
| input_tokens  | 4560.400       |
| output_tokens | 605.800        |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 19          |
| exhausted       | 1           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
