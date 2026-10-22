# Evaluation of run rag-claude-s1-mixed-cf-S001-contradicts on rag-claude-s1-cf-5893772b

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 42      | 38      | 38        | 0.905       | 1.000    | 0.950 | 1.000           |
| all             | paraphrased   | 23      | 34      | 20        | 0.870       | 0.588    | 0.702 | 1.000           |
| all             | distributed   | 32      | 26      | 26        | 0.812       | 1.000    | 0.897 | 1.000           |
| all             | complex       | 81      | 74      | 71        | 0.877       | 0.959    | 0.916 | 1.000           |
| all             | contradictory | 41      | 38      | 36        | 0.878       | 0.947    | 0.911 | 1.000           |
| all             | all           | 219     | 210     | 191       | 0.872       | 0.910    | 0.890 | 1.000           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 17      | 15      | 15        | 0.882       | 1.000    | 0.938 | 1.000           |
| condition       | paraphrased   | 13      | 13      | 11        | 0.846       | 0.846    | 0.846 | 1.000           |
| condition       | distributed   | 13      | 9       | 9         | 0.692       | 1.000    | 0.818 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 16      | 15      | 13        | 0.812       | 0.867    | 0.839 | 1.000           |
| condition       | all           | 68      | 61      | 57        | 0.838       | 0.934    | 0.884 | 1.000           |
| measurement     | explicit      | 16      | 15      | 15        | 0.938       | 1.000    | 0.968 | 1.000           |
| measurement     | paraphrased   | 4       | 13      | 4         | 1.000       | 0.308    | 0.471 | 1.000           |
| measurement     | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | complex       | 55      | 50      | 47        | 0.855       | 0.940    | 0.895 | 1.000           |
| measurement     | contradictory | 17      | 15      | 15        | 0.882       | 1.000    | 0.938 | 1.000           |
| measurement     | all           | 101     | 102     | 90        | 0.891       | 0.882    | 0.887 | 1.000           |
| metric          | explicit      | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | paraphrased   | 2       | 4       | 1         | 0.500       | 0.250    | 0.333 | 1.000           |
| metric          | distributed   | 6       | 4       | 4         | 0.667       | 1.000    | 0.800 | 1.000           |
| metric          | complex       | 13      | 11      | 11        | 0.846       | 1.000    | 0.917 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 30      | 27      | 24        | 0.800       | 0.889    | 0.842 | 1.000           |

Facts no item matched: 19; items matching no fact: 28.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 15                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.933          | 4         | 0.750       |
| paraphrased   | 4                      | 0.500                  | 0.500                     | 1.000             | 0.500             | 1.000          | 4         | 0.250       |
| distributed   | 9                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| complex       | 47                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.936          | 4         | 0.250       |
| contradictory | 15                     | 0.867                  | 0.867                     | 1.000             | 0.867             | 1.000          | 4         | 1.000       |
| all           | 90                     | 0.956                  | 0.956                     | 1.000             | 0.956             | 0.956          | 20        | 0.650       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.850                | 0.850          | 1.000               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 20        | 20           | 0.200                | 0.250          | 0.800               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 20        | 20           | 0.750                | 1.000          | 0.750               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit      | agent-baseline  | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit      | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit      | rag-baseline    | 4         | 4            | 0.250                | 0.250          | 1.000               | 1.000          | 1.000     |
| paraphrased   | agent-baseline  | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| paraphrased   | evidence-engine | 4         | 4            | 0.250                | 0.250          | 1.000               | -              | -         |
| paraphrased   | rag-baseline    | 4         | 4            | 0.000                | 0.000          | -                   | -              | -         |
| distributed   | agent-baseline  | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed   | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed   | rag-baseline    | 4         | 4            | 0.250                | 0.250          | 1.000               | 1.000          | 1.000     |
| complex       | agent-baseline  | 4         | 4            | 0.750                | 1.000          | 0.750               | -              | -         |
| complex       | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| complex       | rag-baseline    | 4         | 4            | 0.500                | 0.500          | 1.000               | 1.000          | 1.000     |
| contradictory | agent-baseline  | 4         | 4            | 0.000                | 1.000          | 0.000               | -              | -         |
| contradictory | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| contradictory | rag-baseline    | 4         | 4            | 0.000                | 0.250          | 0.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 4    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit      | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | paraphrased   | 4         | 1                | 4                | 3          | 0            |
| evidence-engine | distributed   | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | complex       | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | contradictory | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | all           | 20        | 17               | 20               | 3          | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.884 [0.79, 0.94] | BCa      |
| metric          | 0.842 [0.75, 0.92] | BCa      |
| measurement     | 0.887 [0.80, 0.94] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.890 [0.85, 0.93] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.850 [0.60, 0.95]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.200 [0.05, 0.45]   | BCa      | 0.650 [0.40, 0.85]    | BCa             | 20         |
| agent-baseline  | 0.750 [0.50, 0.90]   | BCa      | 0.100 [-0.20, 0.40]   | BCa             | 20         |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 92           | 92       | 1.000    |
| all             | paraphrased   | 73           | 73       | 1.000    |
| all             | distributed   | 75           | 75       | 1.000    |
| all             | complex       | 159          | 159      | 1.000    |
| all             | contradictory | 88           | 88       | 1.000    |
| all             | all           | 487          | 487      | 1.000    |
| author_claim    | explicit      | 8            | 8        | 1.000    |
| author_claim    | paraphrased   | 8            | 8        | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
| condition       | explicit      | 41           | 41       | 1.000    |
| condition       | paraphrased   | 30           | 30       | 1.000    |
| condition       | distributed   | 32           | 32       | 1.000    |
| condition       | complex       | 46           | 46       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 189          | 189      | 1.000    |
| measurement     | explicit      | 15           | 15       | 1.000    |
| measurement     | paraphrased   | 13           | 13       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 50           | 50       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 102          | 102      | 1.000    |
| metric          | explicit      | 28           | 28       | 1.000    |
| metric          | paraphrased   | 22           | 22       | 1.000    |
| metric          | distributed   | 26           | 26       | 1.000    |
| metric          | complex       | 55           | 55       | 1.000    |
| metric          | contradictory | 25           | 25       | 1.000    |
| metric          | all           | 156          | 156      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20              | 0      | 0              |
| llm_condition@1#45b3761c700e      | 61      | 57              | 45     | 41             |
| llm_measurement@1#02bd5a7ab104    | 91      | 86              | 34     | 30             |
| llm_metric@1#41e1e53a1fc4         | 23      | 23              | 6      | 6              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 23      | 16              | 7      | 0              |
| regex_measurement@2#e2d17eb260ea  | 67      | 60              | 10     | 4              |
| regex_metric@2#0affe2d9ce77       | 24      | 18              | 7      | 1              |

Facts no extractor found: condition 4, measurement 12, metric 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           | -                      | 45     | 41             |
| llm_condition@1#45b3761c700e      | all             | all     | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           | -                      | 45     | 41             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 91      | 102     | 86        | 0.945       | 0.843    | 0.891 | 1.000           | 0.953                  | 34     | 30             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 91      | 102     | 86        | 0.945       | 0.843    | 0.891 | 1.000           | -                      | 34     | 30             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           | -                      | 6      | 6              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           | -                      | 6      | 6              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 23      | 61      | 16        | 0.696       | 0.262    | 0.381 | 1.000           | -                      | 7      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 23      | 61      | 16        | 0.696       | 0.262    | 0.381 | 1.000           | -                      | 7      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 67      | 102     | 60        | 0.896       | 0.588    | 0.710 | 1.000           | 0.967                  | 10     | 4              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 67      | 102     | 60        | 0.896       | 0.588    | 0.710 | 1.000           | -                      | 10     | 4              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 24      | 27      | 18        | 0.750       | 0.667    | 0.706 | 1.000           | -                      | 7      | 1              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 24      | 27      | 18        | 0.750       | 0.667    | 0.706 | 1.000           | -                      | 7      | 1              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20            | 21114          | 2376            | 3.494     |
| llm_condition@1#45b3761c700e      | 20      | 24            | 27128          | 4690            | 8.111     |
| llm_measurement@1#02bd5a7ab104    | 20      | 40            | 56876          | 16885           | 21.579    |
| llm_metric@1#41e1e53a1fc4         | 20      | 23            | 26152          | 2350            | 3.111     |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 18894          | 1784            | 3.548     |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.125     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.125     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.152     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.132     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.124     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 194     | 9.700       |
| calls            | 200     | 10.000      |
| input_tokens     | 150164  | 7508.200    |
| made_model_calls | 6       | 0.300       |
| model_calls      | 127     | 6.350       |
| output_tokens    | 28085   | 1404.250    |
| seconds          | 41.567  | 2.078       |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.350          |
| input_tokens  | 7508.200       |
| output_tokens | 1404.250       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
