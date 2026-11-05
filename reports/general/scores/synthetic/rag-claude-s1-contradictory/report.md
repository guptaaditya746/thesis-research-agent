# Evaluation of run rag-claude-s1-contradictory on rag-claude-s1-e4e9d603

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 113     | 162     | 108       | 0.956       | 0.667    | 0.785 | 0.981           |
| all             | all           | 113     | 162     | 108       | 0.956       | 0.667    | 0.785 | 0.981           |
| author_claim    | contradictory | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |
| author_claim    | all           | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |
| condition       | contradictory | 37      | 61      | 37        | 1.000       | 0.607    | 0.755 | 0.946           |
| condition       | all           | 37      | 61      | 37        | 1.000       | 0.607    | 0.755 | 0.946           |
| measurement     | contradictory | 40      | 61      | 35        | 0.875       | 0.574    | 0.693 | 1.000           |
| measurement     | all           | 40      | 61      | 35        | 0.875       | 0.574    | 0.693 | 1.000           |
| metric          | contradictory | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |
| metric          | all           | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |

Facts no item matched: 54; items matching no fact: 5.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 35                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.800       |
| all           | 35                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.800       |

## C. Synthesis

| system               | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|----------------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine      | mixed   | mixed      | yes             | 20        | 20           | 0.800                | 0.900          | 0.889               | 0.800                           | -              | -         |
| bm25-answer-baseline | mixed   | mixed      | yes             | 20        | 20           | 0.300                | 0.900          | 0.333               | 0.300                           | 0.880          | 0.880     |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system               | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|---------------|----------------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| contradictory | bm25-answer-baseline | 20        | 20           | 0.300                | 0.900          | 0.333               | 0.300                           | 0.880          | 0.880     |
| contradictory | evidence-engine      | 20        | 20           | 0.800                | 0.900          | 0.889               | 0.800                           | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 16   | 0    | 4    | 1.000       | 0.800    |
| evidence-engine | duplicate       | 0    | 0    | 0    | n/a         | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | n/a         | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Cost per system

| system               | model_calls   | input_tokens   | output_tokens   | tokens   |
|----------------------|---------------|----------------|-----------------|----------|
| evidence-engine      | 59            | 69498          | 9592            | 79090    |
| bm25-answer-baseline | 2             | 12248          | 2657            | 14905    |

Model calls and tokens each system recorded (D41): the engine's run.json `cost`, a baseline's answering and mapping calls, the agent baseline's agent (its tokens not split into in and out). The engine's counts include calls replayed from its record cache (the system's cost, not this rerun's spend: `made_model_calls` under Cost is that). `-`: not recorded.

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or passage search), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | contradictory | 20        | 16               | 20               | 4          | 0            |
| evidence-engine | all           | 20        | 16               | 20               | 4          | 0            |

Not attributed (not this oracle's counterpart): bm25-answer-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.755 [0.64, 0.84] | BCa      |
| metric          | 0.947 [0.82, 1.00] | BCa      |
| measurement     | 0.693 [0.59, 0.77] | BCa      |
| author_claim    | 0.947 [0.82, 1.00] | BCa      |
| all             | 0.785 [0.67, 0.85] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system               | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|----------------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine      | 0.800 [0.60, 0.95]   | BCa      | -                     | -               | -          |
| bm25-answer-baseline | 0.300 [0.15, 0.55]   | BCa      | 0.500 [0.15, 0.75]    | BCa             | 20         |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | contradictory | 406          | 362      | 0.892    |
| all             | all           | 406          | 362      | 0.892    |
| author_claim    | contradictory | 40           | 36       | 0.900    |
| author_claim    | all           | 40           | 36       | 0.900    |
| condition       | contradictory | 179          | 160      | 0.894    |
| condition       | all           | 179          | 160      | 0.894    |
| measurement     | contradictory | 61           | 55       | 0.902    |
| measurement     | all           | 61           | 55       | 0.902    |
| metric          | contradictory | 126          | 111      | 0.881    |
| metric          | all           | 126          | 111      | 0.881    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | 0       | 0               | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | 12      | 12              | 12     | 12             |
| llm_measurement@1#341c436d3c29    | 25      | 25              | 17     | 17             |
| llm_metric@1#dcbd836bf6b8         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#6b89fc3599f7 | 18      | 18              | 18     | 18             |
| regex_condition@2#96b289932633    | 25      | 25              | 25     | 25             |
| regex_measurement@2#67eb53dc0d9c  | 23      | 18              | 15     | 10             |
| regex_metric@2#c011982de96a       | 16      | 16              | 16     | 16             |

Facts no extractor found: author_claim 2, condition 24, measurement 26, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#30bafc9430a4   | all             | all     | 0       | 162     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#73b7cbb40c1e      | condition       | all     | 12      | 26      | 12        | 1.000       | 0.462    | 0.632 | 1.000           | -                      | 12     | 12             |
| llm_condition@1#73b7cbb40c1e      | all             | all     | 12      | 26      | 12        | 1.000       | 0.462    | 0.632 | 1.000           | -                      | 12     | 12             |
| llm_measurement@1#341c436d3c29    | measurement     | all     | 25      | 37      | 25        | 1.000       | 0.676    | 0.806 | 1.000           | 1.000                  | 17     | 17             |
| llm_measurement@1#341c436d3c29    | all             | all     | 25      | 37      | 25        | 1.000       | 0.676    | 0.806 | 1.000           | -                      | 17     | 17             |
| llm_metric@1#dcbd836bf6b8         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#dcbd836bf6b8         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#6b89fc3599f7 | author_claim    | all     | 18      | 18      | 18        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 18     | 18             |
| regex_author_claim@2#6b89fc3599f7 | all             | all     | 18      | 18      | 18        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 18     | 18             |
| regex_condition@2#96b289932633    | condition       | all     | 25      | 55      | 25        | 1.000       | 0.455    | 0.625 | 0.920           | -                      | 25     | 25             |
| regex_condition@2#96b289932633    | all             | all     | 25      | 55      | 25        | 1.000       | 0.455    | 0.625 | 0.920           | -                      | 25     | 25             |
| regex_measurement@2#67eb53dc0d9c  | measurement     | all     | 23      | 55      | 18        | 0.783       | 0.327    | 0.462 | 1.000           | 1.000                  | 15     | 10             |
| regex_measurement@2#67eb53dc0d9c  | all             | all     | 23      | 55      | 18        | 0.783       | 0.327    | 0.462 | 1.000           | -                      | 15     | 10             |
| regex_metric@2#c011982de96a       | metric          | all     | 16      | 18      | 16        | 1.000       | 0.889    | 0.941 | 1.000           | -                      | 16     | 16             |
| regex_metric@2#c011982de96a       | all             | all     | 16      | 18      | 16        | 1.000       | 0.889    | 0.941 | 1.000           | -                      | 16     | 16             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#73b7cbb40c1e      | 9       | 13            | 14215          | 1128            | 0.060     |
| llm_measurement@1#341c436d3c29    | 12      | 24            | 32914          | 5193            | 0.088     |
| llm_metric@1#dcbd836bf6b8         | 2       | 2             | 2430           | 192             | 0.013     |
| llm_screen@1#b51a1127185c         | 20      | 20            | 19939          | 3079            | 0.132     |
| regex_author_claim@2#6b89fc3599f7 | 18      | 0             | 0              | 0               | 0.121     |
| regex_condition@2#96b289932633    | 18      | 0             | 0              | 0               | 0.124     |
| regex_measurement@2#67eb53dc0d9c  | 18      | 0             | 0              | 0               | 0.120     |
| regex_metric@2#c011982de96a       | 18      | 0             | 0              | 0               | 0.117     |
| regex_screen@1#3fb490c481d0       | 20      | 0             | 0              | 0               | 0.131     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 135     | 6.750       |
| input_tokens     | 69498   | 3474.900    |
| made_model_calls | 59      | 2.950       |
| model_calls      | 59      | 2.950       |
| output_tokens    | 9592    | 479.600     |
| seconds          | 95.742  | 4.787       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 6.750          |
| model_calls   | 2.950          |
| input_tokens  | 3474.900       |
| output_tokens | 479.600        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 6           |
| 1               | 12          |
| skipped         | 2           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 18   | 0    | 2    | 0    | 1.000       | 0.900    |

Screened out wrongly: S002, S014
