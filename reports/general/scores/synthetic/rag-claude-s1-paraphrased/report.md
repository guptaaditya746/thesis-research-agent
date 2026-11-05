# Evaluation of run rag-claude-s1-paraphrased on rag-claude-s1-c34803f0

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: paraphrased

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | paraphrased | 88      | 162     | 87        | 0.989       | 0.537    | 0.696 | 0.977           |
| all             | all         | 88      | 162     | 87        | 0.989       | 0.537    | 0.696 | 0.977           |
| author_claim    | paraphrased | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased | 37      | 61      | 37        | 1.000       | 0.607    | 0.755 | 1.000           |
| condition       | all         | 37      | 61      | 37        | 1.000       | 0.607    | 0.755 | 1.000           |
| measurement     | paraphrased | 21      | 61      | 21        | 1.000       | 0.344    | 0.512 | 1.000           |
| measurement     | all         | 21      | 61      | 21        | 1.000       | 0.344    | 0.512 | 1.000           |
| metric          | paraphrased | 10      | 20      | 9         | 0.900       | 0.450    | 0.600 | 0.778           |
| metric          | all         | 10      | 20      | 9         | 0.900       | 0.450    | 0.600 | 0.778           |

Facts no item matched: 75; items matching no fact: 1.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| paraphrased | 21                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.350       |
| all         | 21                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.350       |

## C. Synthesis

| system               | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|----------------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine      | mixed   | mixed      | yes             | 20        | 20           | 0.350                | 0.350          | 1.000               | 0.350                           | -              | -         |
| bm25-answer-baseline | mixed   | mixed      | yes             | 20        | 20           | 0.900                | 0.900          | 1.000               | 0.900                           | 0.944          | 0.944     |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system               | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|-------------|----------------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| paraphrased | bm25-answer-baseline | 20        | 20           | 0.900                | 0.900          | 1.000               | 0.900                           | 0.944          | 0.944     |
| paraphrased | evidence-engine      | 20        | 20           | 0.350                | 0.350          | 1.000               | 0.350                           | -              | -         |

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
| evidence-engine      | 75            | 84943          | 10870           | 95813    |
| bm25-answer-baseline | 2             | 12201          | 2189            | 14390    |

Model calls and tokens each system recorded (D41): the engine's run.json `cost`, a baseline's answering and mapping calls, the agent baseline's agent (its tokens not split into in and out). The engine's counts include calls replayed from its record cache (the system's cost, not this rerun's spend: `made_model_calls` under Cost is that). `-`: not recorded.

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or passage search), downstream when it is wrong too (synthesis or reasoning).

| system          | level       | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|-------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | paraphrased | 20        | 7                | 20               | 13         | 0            |
| evidence-engine | all         | 20        | 7                | 20               | 13         | 0            |

Not attributed (not this oracle's counterpart): bm25-answer-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.755 [0.60, 0.88] | BCa      |
| metric          | 0.600 [0.38, 0.79] | BCa      |
| measurement     | 0.512 [0.26, 0.73] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.696 [0.54, 0.83] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system               | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|----------------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine      | 0.350 [0.15, 0.55]   | BCa      | -                     | -               | -          |
| bm25-answer-baseline | 0.900 [0.70, 1.00]   | BCa      | -0.550 [-0.80, -0.25] | BCa             | 20         |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | paraphrased | 368          | 368      | 1.000    |
| all             | all         | 368          | 368      | 1.000    |
| author_claim    | paraphrased | 40           | 40       | 1.000    |
| author_claim    | all         | 40           | 40       | 1.000    |
| condition       | paraphrased | 163          | 163      | 1.000    |
| condition       | all         | 163          | 163      | 1.000    |
| measurement     | paraphrased | 61           | 61       | 1.000    |
| measurement     | all         | 61           | 61       | 1.000    |
| metric          | paraphrased | 104          | 104      | 1.000    |
| metric          | all         | 104          | 104      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | 0       | 0               | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | 37      | 37              | 37     | 37             |
| llm_measurement@1#341c436d3c29    | 21      | 21              | 21     | 21             |
| llm_metric@1#dcbd836bf6b8         | 7       | 7               | 7      | 7              |
| regex_author_claim@2#6b89fc3599f7 | 20      | 20              | 20     | 20             |
| regex_condition@2#96b289932633    | 0       | 0               | 0      | 0              |
| regex_measurement@2#67eb53dc0d9c  | 0       | 0               | 0      | 0              |
| regex_metric@2#c011982de96a       | 3       | 2               | 3      | 2              |

Facts no extractor found: condition 24, measurement 40, metric 11

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | all             | all     | 0       | 162     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | condition       | all     | 37      | 61      | 37        | 1.000       | 0.607    | 0.755 | 1.000           | -                      | 37     | 37             |
| llm_condition@1#73b7cbb40c1e      | all             | all     | 37      | 61      | 37        | 1.000       | 0.607    | 0.755 | 1.000           | -                      | 37     | 37             |
| llm_measurement@1#341c436d3c29    | measurement     | all     | 21      | 25      | 21        | 1.000       | 0.840    | 0.913 | 1.000           | 1.000                  | 21     | 21             |
| llm_measurement@1#341c436d3c29    | all             | all     | 21      | 25      | 21        | 1.000       | 0.840    | 0.913 | 1.000           | -                      | 21     | 21             |
| llm_metric@1#dcbd836bf6b8         | metric          | all     | 7       | 8       | 7         | 1.000       | 0.875    | 0.933 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#dcbd836bf6b8         | all             | all     | 7       | 8       | 7         | 1.000       | 0.875    | 0.933 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@2#6b89fc3599f7 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#6b89fc3599f7 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#96b289932633    | condition       | all     | 0       | 61      | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_condition@2#96b289932633    | all             | all     | 0       | 61      | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#67eb53dc0d9c  | measurement     | all     | 0       | 61      | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#67eb53dc0d9c  | all             | all     | 0       | 61      | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#c011982de96a       | metric          | all     | 3       | 20      | 2         | 0.667       | 0.100    | 0.174 | 0.000           | -                      | 3      | 2              |
| regex_metric@2#c011982de96a       | all             | all     | 3       | 20      | 2         | 0.667       | 0.100    | 0.174 | 0.000           | -                      | 3      | 2              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#73b7cbb40c1e      | 20      | 31            | 35249          | 3569            | 0.134     |
| llm_measurement@1#341c436d3c29    | 9       | 16            | 21284          | 4886            | 0.061     |
| llm_metric@1#dcbd836bf6b8         | 8       | 8             | 9763           | 691             | 0.051     |
| llm_screen@1#b51a1127185c         | 20      | 20            | 18647          | 1724            | 0.129     |
| regex_author_claim@2#6b89fc3599f7 | 20      | 0             | 0              | 0               | 0.125     |
| regex_condition@2#96b289932633    | 20      | 0             | 0              | 0               | 0.123     |
| regex_measurement@2#67eb53dc0d9c  | 20      | 0             | 0              | 0               | 0.123     |
| regex_metric@2#c011982de96a       | 20      | 0             | 0              | 0               | 0.124     |
| regex_screen@1#3fb490c481d0       | 20      | 0             | 0              | 0               | 0.128     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 157     | 7.850       |
| input_tokens     | 84943   | 4247.150    |
| made_model_calls | 75      | 3.750       |
| model_calls      | 75      | 3.750       |
| output_tokens    | 10870   | 543.500     |
| seconds          | 308.876 | 15.444      |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.850          |
| model_calls   | 3.750          |
| input_tokens  | 4247.150       |
| output_tokens | 543.500        |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 7           |
| exhausted       | 13          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
