# Evaluation of run rag-tpl-gen-s1-multi_experiment on rag-tpl-gen-s1-c568fd7b

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: multi_experiment

## A. Extraction

| evidence_type   | level            | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|------------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | all              | 122     | 431     | 122       | 1.000       | 0.283    | 0.441 | 1.000           |
| all             | multi_experiment | 122     | 431     | 122       | 1.000       | 0.283    | 0.441 | 1.000           |
| author_claim    | all              | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | multi_experiment | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all              | 30      | 61      | 30        | 1.000       | 0.492    | 0.659 | 1.000           |
| condition       | multi_experiment | 30      | 61      | 30        | 1.000       | 0.492    | 0.659 | 1.000           |
| measurement     | all              | 60      | 300     | 60        | 1.000       | 0.200    | 0.333 | 1.000           |
| measurement     | multi_experiment | 60      | 300     | 60        | 1.000       | 0.200    | 0.333 | 1.000           |
| metric          | all              | 12      | 50      | 12        | 1.000       | 0.240    | 0.387 | 1.000           |
| metric          | multi_experiment | 12      | 50      | 12        | 1.000       | 0.240    | 0.387 | 1.000           |

Facts no item matched: 309; items matching no fact: 0.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Integration

| level            | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|------------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| all              | 60                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.250       |
| multi_experiment | 60                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.250       |

## C. Synthesis

| system               | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|----------------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine      | supported | mixed      | no              | 20        | 20           | 0.250                | 0.250          | 1.000               | 0.250                           | -              | -         |
| bm25-answer-baseline | mixed     | mixed      | yes             | 20        | 20           | 0.800                | 0.900          | 0.889               | 0.800                           | 0.923          | 0.923     |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level            | system               | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|------------------|----------------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| multi_experiment | bm25-answer-baseline | 20        | 20           | 0.800                | 0.900          | 0.889               | 0.800                           | 0.923          | 0.923     |
| multi_experiment | evidence-engine      | 20        | 20           | 0.250                | 0.250          | 1.000               | 0.250                           | -              | -         |

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
| evidence-engine      | 75            | 107715         | 21180           | 128895   |
| bm25-answer-baseline | 2             | 10631          | 2315            | 12946    |

Model calls and tokens each system recorded (D41): the engine's run.json `cost`, a baseline's answering and mapping calls, the agent baseline's agent (its tokens not split into in and out). The engine's counts include calls replayed from its record cache (the system's cost, not this rerun's spend: `made_model_calls` under Cost is that). `-`: not recorded.

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or passage search), downstream when it is wrong too (synthesis or reasoning).

| system          | level            | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|------------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | all              | 20        | 5                | 20               | 15         | 0            |
| evidence-engine | multi_experiment | 20        | 5                | 20               | 15         | 0            |

Not attributed (not this oracle's counterpart): bm25-answer-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.659 [0.55, 0.80] | BCa      |
| metric          | 0.387 [0.17, 0.64] | BCa      |
| measurement     | 0.333 [0.13, 0.61] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.441 [0.28, 0.66] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system               | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|----------------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine      | 0.250 [0.10, 0.50]   | BCa      | -                     | -               | -          |
| bm25-answer-baseline | 0.800 [0.60, 0.95]   | BCa      | -0.550 [-0.75, -0.30] | BCa             | 20         |

## Locate recall

| evidence_type   | level            | placements   | inside   | recall   |
|-----------------|------------------|--------------|----------|----------|
| all             | all              | 947          | 947      | 1.000    |
| all             | multi_experiment | 947          | 947      | 1.000    |
| author_claim    | all              | 40           | 40       | 1.000    |
| author_claim    | multi_experiment | 40           | 40       | 1.000    |
| condition       | all              | 345          | 345      | 1.000    |
| condition       | multi_experiment | 345          | 345      | 1.000    |
| measurement     | all              | 300          | 300      | 1.000    |
| measurement     | multi_experiment | 300          | 300      | 1.000    |
| metric          | all              | 262          | 262      | 1.000    |
| metric          | multi_experiment | 262          | 262      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | 0       | 0               | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | 30      | 30              | 30     | 30             |
| llm_measurement@1#341c436d3c29    | 60      | 60              | 60     | 60             |
| llm_metric@1#dcbd836bf6b8         | 12      | 12              | 12     | 12             |
| regex_author_claim@2#6b89fc3599f7 | 20      | 20              | 20     | 20             |
| regex_condition@2#96b289932633    | 0       | 0               | 0      | 0              |
| regex_measurement@2#67eb53dc0d9c  | 0       | 0               | 0      | 0              |
| regex_metric@2#c011982de96a       | 0       | 0               | 0      | 0              |

Facts no extractor found: condition 31, measurement 240, metric 38

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | all             | all     | 0       | 431     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | condition       | all     | 30      | 61      | 30        | 1.000       | 0.492    | 0.659 | 1.000           | -                      | 30     | 30             |
| llm_condition@1#73b7cbb40c1e      | all             | all     | 30      | 61      | 30        | 1.000       | 0.492    | 0.659 | 1.000           | -                      | 30     | 30             |
| llm_measurement@1#341c436d3c29    | measurement     | all     | 60      | 68      | 60        | 1.000       | 0.882    | 0.938 | 1.000           | 1.000                  | 60     | 60             |
| llm_measurement@1#341c436d3c29    | all             | all     | 60      | 68      | 60        | 1.000       | 0.882    | 0.938 | 1.000           | -                      | 60     | 60             |
| llm_metric@1#dcbd836bf6b8         | metric          | all     | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 12     | 12             |
| llm_metric@1#dcbd836bf6b8         | all             | all     | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 12     | 12             |
| regex_author_claim@2#6b89fc3599f7 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#6b89fc3599f7 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#96b289932633    | condition       | all     | 0       | 61      | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_condition@2#96b289932633    | all             | all     | 0       | 61      | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#67eb53dc0d9c  | measurement     | all     | 0       | 300     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#67eb53dc0d9c  | all             | all     | 0       | 300     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#c011982de96a       | metric          | all     | 0       | 50      | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#c011982de96a       | all             | all     | 0       | 50      | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#73b7cbb40c1e      | 20      | 40            | 52645          | 3728            | 0.153     |
| llm_measurement@1#341c436d3c29    | 5       | 10            | 25941          | 14918           | 0.049     |
| llm_metric@1#dcbd836bf6b8         | 5       | 5             | 6810           | 1008            | 0.034     |
| llm_screen@1#b51a1127185c         | 20      | 20            | 22319          | 1526            | 0.150     |
| regex_author_claim@2#6b89fc3599f7 | 20      | 0             | 0              | 0               | 0.132     |
| regex_condition@2#96b289932633    | 20      | 0             | 0              | 0               | 0.129     |
| regex_measurement@2#67eb53dc0d9c  | 20      | 0             | 0              | 0               | 0.135     |
| regex_metric@2#c011982de96a       | 20      | 0             | 0              | 0               | 0.130     |
| regex_screen@1#3fb490c481d0       | 20      | 0             | 0              | 0               | 0.150     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 150     | 7.500       |
| input_tokens     | 107715  | 5385.750    |
| made_model_calls | 75      | 3.750       |
| model_calls      | 75      | 3.750       |
| output_tokens    | 21180   | 1059.000    |
| seconds          | 231.872 | 11.594      |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.500          |
| model_calls   | 3.750          |
| input_tokens  | 5385.750       |
| output_tokens | 1059.000       |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 5           |
| exhausted       | 15          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
