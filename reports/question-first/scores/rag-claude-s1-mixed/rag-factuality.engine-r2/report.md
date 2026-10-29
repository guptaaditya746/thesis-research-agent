# Evaluation of run rag-claude-s1-mixed-r2 on rag-claude-s1-ec928480

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 24      | 38      | 24        | 1.000       | 0.632    | 0.774 | 0.958           |
| all             | paraphrased   | 26      | 34      | 26        | 1.000       | 0.765    | 0.867 | 0.962           |
| all             | distributed   | 25      | 26      | 24        | 0.960       | 0.923    | 0.941 | 1.000           |
| all             | complex       | 69      | 74      | 63        | 0.913       | 0.851    | 0.881 | 1.000           |
| all             | contradictory | 26      | 38      | 24        | 0.923       | 0.632    | 0.750 | 0.958           |
| all             | all           | 170     | 210     | 161       | 0.947       | 0.767    | 0.847 | 0.981           |
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
| measurement     | paraphrased   | 9       | 13      | 9         | 1.000       | 0.692    | 0.818 | 1.000           |
| measurement     | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| measurement     | complex       | 45      | 50      | 39        | 0.867       | 0.780    | 0.821 | 1.000           |
| measurement     | contradictory | 10      | 15      | 8         | 0.800       | 0.533    | 0.640 | 1.000           |
| measurement     | all           | 80      | 102     | 72        | 0.900       | 0.706    | 0.791 | 1.000           |
| metric          | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased   | 3       | 4       | 3         | 1.000       | 0.750    | 0.857 | 0.667           |
| metric          | distributed   | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 27      | 27      | 26        | 0.963       | 0.963    | 0.963 | 0.962           |

Facts no item matched: 49; items matching no fact: 9.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| paraphrased   | 9                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 0.750       |
| distributed   | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| complex       | 39                     | 0.923                  | 0.923                     | 1.000             | 0.923             | 1.000          | 4         | 0.750       |
| contradictory | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| all           | 72                     | 0.958                  | 0.958                     | 1.000             | 0.958             | 1.000          | 20        | 0.900       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.950                | 0.950          | 1.000               | 0.950                           | -              | -         |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| explicit      | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |
| paraphrased   | evidence-engine | 4         | 4            | 0.750                | 0.750          | 1.000               | 0.750                           | -              | -         |
| distributed   | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |
| complex       | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |
| contradictory | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | 1.000                           | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 4    | 0    | 0    | 1.000       | 1.000    |
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
| condition       | 0.827 [0.75, 0.91] | BCa      |
| metric          | 0.963 [0.87, 1.00] | BCa      |
| measurement     | 0.791 [0.68, 0.87] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.847 [0.78, 0.90] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.950 [0.75, 1.00]   | BCa      | -                     | -               | -          |

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
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 21      | 21              | 20     | 20             |
| llm_measurement@1#02bd5a7ab104    | 51      | 48              | 47     | 44             |
| llm_metric@1#41e1e53a1fc4         | 3       | 3               | 3      | 3              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 20     | 20             |
| regex_condition@2#0a5bf730763c    | 23      | 23              | 22     | 22             |
| regex_measurement@2#e2d17eb260ea  | 33      | 28              | 29     | 24             |
| regex_metric@2#0affe2d9ce77       | 24      | 23              | 24     | 23             |

Facts no extractor found: condition 18, measurement 30, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 210     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 21      | 36      | 21        | 1.000       | 0.583    | 0.737 | 1.000           | -                      | 20     | 20             |
| llm_condition@1#45b3761c700e      | all             | all     | 21      | 36      | 21        | 1.000       | 0.583    | 0.737 | 1.000           | -                      | 20     | 20             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 51      | 72      | 48        | 0.941       | 0.667    | 0.780 | 1.000           | 1.000                  | 47     | 44             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 51      | 72      | 48        | 0.941       | 0.667    | 0.780 | 1.000           | -                      | 47     | 44             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 3      | 3              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 3      | 3              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 0.913           | -                      | 22     | 22             |
| regex_condition@2#0a5bf730763c    | all             | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 0.913           | -                      | 22     | 22             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 33      | 102     | 28        | 0.848       | 0.275    | 0.415 | 1.000           | 0.893                  | 29     | 24             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 33      | 102     | 28        | 0.848       | 0.275    | 0.415 | 1.000           | -                      | 29     | 24             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 24      | 27      | 23        | 0.958       | 0.852    | 0.902 | 0.957           | -                      | 24     | 23             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 24      | 27      | 23        | 0.958       | 0.852    | 0.902 | 0.957           | -                      | 24     | 23             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 12      | 15            | 17774          | 1704            | 0.084     |
| llm_measurement@1#02bd5a7ab104    | 14      | 28            | 39169          | 8643            | 0.134     |
| llm_metric@1#41e1e53a1fc4         | 3       | 3             | 3614           | 291             | 0.020     |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 18681          | 1753            | 0.132     |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.133     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.133     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.135     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.135     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.133     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 149     | 7.450       |
| input_tokens     | 79238   | 3961.900    |
| made_model_calls | 66      | 3.300       |
| model_calls      | 66      | 3.300       |
| output_tokens    | 12391   | 619.550     |
| seconds          | 169.705 | 8.485       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.450          |
| model_calls   | 3.300          |
| input_tokens  | 3961.900       |
| output_tokens | 619.550        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 5           |
| 1               | 14          |
| exhausted       | 1           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
