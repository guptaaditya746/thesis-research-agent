# Evaluation of run rag-claude-s1-mixed on rag-claude-s1-ec928480

Question: Does retrieval-augmented generation change the latency of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 30      | 34      | 30        | 1.000       | 0.882    | 0.938 | 1.000           |
| all             | paraphrased   | 18      | 30      | 16        | 0.889       | 0.533    | 0.667 | 1.000           |
| all             | distributed   | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | complex       | 68      | 70      | 67        | 0.985       | 0.957    | 0.971 | 1.000           |
| all             | contradictory | 35      | 34      | 32        | 0.914       | 0.941    | 0.928 | 1.000           |
| all             | all           | 173     | 190     | 167       | 0.965       | 0.879    | 0.920 | 1.000           |
| condition       | explicit      | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased   | 13      | 13      | 11        | 0.846       | 0.846    | 0.846 | 1.000           |
| condition       | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 15      | 15      | 13        | 0.867       | 0.867    | 0.867 | 1.000           |
| condition       | all           | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           |
| measurement     | explicit      | 12      | 15      | 12        | 1.000       | 0.800    | 0.889 | 1.000           |
| measurement     | paraphrased   | 4       | 13      | 4         | 1.000       | 0.308    | 0.471 | 1.000           |
| measurement     | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | complex       | 48      | 50      | 47        | 0.979       | 0.940    | 0.959 | 1.000           |
| measurement     | contradictory | 16      | 15      | 15        | 0.938       | 1.000    | 0.968 | 1.000           |
| measurement     | all           | 89      | 102     | 87        | 0.978       | 0.853    | 0.911 | 1.000           |
| metric          | explicit      | 3       | 4       | 3         | 1.000       | 0.750    | 0.857 | 1.000           |
| metric          | paraphrased   | 1       | 4       | 1         | 1.000       | 0.250    | 0.400 | 1.000           |
| metric          | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           |

Facts no item matched: 23; items matching no fact: 6.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 12                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| paraphrased   | 4                      | 0.500                  | 0.500                     | 1.000             | 0.500             | 1.000          | 0         | -           |
| distributed   | 9                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| complex       | 47                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 3         | 1.000       |
| contradictory | 15                     | 0.867                  | 0.867                     | 1.000             | 0.867             | 1.000          | 0         | -           |
| all           | 87                     | 0.954                  | 0.954                     | 1.000             | 0.954             | 1.000          | 3         | 1.000       |

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
| condition       | 0.934 [0.83, 0.98] | BCa      |
| metric          | 0.920 [0.79, 0.98] | BCa      |
| measurement     | 0.911 [0.80, 0.96] | BCa      |
| all             | 0.920 [0.86, 0.96] | BCa      |

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

| extractor                      | found   | found_matched   | only   | only_matched   |
|--------------------------------|---------|-----------------|--------|----------------|
| llm_condition@1#45b3761c700e   | 61      | 57              | 61     | 57             |
| llm_measurement@1#4171ae269b7f | 89      | 87              | 89     | 87             |
| llm_metric@1#f77fae6f7754      | 23      | 23              | 23     | 23             |

Facts no extractor found: condition 4, measurement 15, metric 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                      | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|--------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_condition@1#45b3761c700e   | condition       | all     | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           | -                      | 61     | 57             |
| llm_condition@1#45b3761c700e   | all             | all     | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           | -                      | 61     | 57             |
| llm_measurement@1#4171ae269b7f | measurement     | all     | 89      | 102     | 87        | 0.978       | 0.853    | 0.911 | 1.000           | 0.954                  | 89     | 87             |
| llm_measurement@1#4171ae269b7f | all             | all     | 89      | 102     | 87        | 0.978       | 0.853    | 0.911 | 1.000           | -                      | 89     | 87             |
| llm_metric@1#f77fae6f7754      | metric          | all     | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           | -                      | 23     | 23             |
| llm_metric@1#f77fae6f7754      | all             | all     | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           | -                      | 23     | 23             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                      | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|--------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e   | 20      | 25            | 27916          | 4725            | 0.141     |
| llm_measurement@1#4171ae269b7f | 20      | 40            | 56473          | 17205           | 0.153     |
| llm_metric@1#f77fae6f7754      | 20      | 26            | 28903          | 2490            | 0.138     |
| llm_screen@1#41b0d6e6793f      | 20      | 20            | 18681          | 1748            | 0.139     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 80      | 4.000       |
| input_tokens     | 131973  | 6598.650    |
| made_model_calls | 111     | 5.550       |
| model_calls      | 111     | 5.550       |
| output_tokens    | 26168   | 1308.400    |
| seconds          | 283.698 | 14.185      |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 4.000          |
| model_calls   | 5.550          |
| input_tokens  | 6598.650       |
| output_tokens | 1308.400       |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 3           |
| exhausted       | 17          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
