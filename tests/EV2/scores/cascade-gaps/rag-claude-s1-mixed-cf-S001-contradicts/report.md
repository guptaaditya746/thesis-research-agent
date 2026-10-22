# Evaluation of run rag-claude-s1-mixed-cf-S001-contradicts on rag-claude-s1-cf-5893772b

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 24      | 38      | 24        | 1.000       | 0.632    | 0.774 | 0.958           |
| all             | paraphrased   | 22      | 34      | 20        | 0.909       | 0.588    | 0.714 | 0.950           |
| all             | distributed   | 25      | 26      | 24        | 0.960       | 0.923    | 0.941 | 1.000           |
| all             | complex       | 69      | 74      | 63        | 0.913       | 0.851    | 0.881 | 1.000           |
| all             | contradictory | 26      | 38      | 24        | 0.923       | 0.632    | 0.750 | 0.958           |
| all             | all           | 166     | 210     | 155       | 0.934       | 0.738    | 0.824 | 0.981           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 0.875           |
| condition       | paraphrased   | 10      | 13      | 8         | 0.800       | 0.615    | 0.696 | 1.000           |
| condition       | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 0.875           |
| condition       | all           | 43      | 61      | 41        | 0.953       | 0.672    | 0.788 | 0.951           |
| measurement     | explicit      | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 1.000           |
| measurement     | paraphrased   | 6       | 13      | 6         | 1.000       | 0.462    | 0.632 | 1.000           |
| measurement     | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| measurement     | complex       | 45      | 50      | 39        | 0.867       | 0.780    | 0.821 | 1.000           |
| measurement     | contradictory | 10      | 15      | 8         | 0.800       | 0.533    | 0.640 | 1.000           |
| measurement     | all           | 77      | 102     | 69        | 0.896       | 0.676    | 0.771 | 1.000           |
| metric          | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased   | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 0.500           |
| metric          | distributed   | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 26      | 27      | 25        | 0.962       | 0.926    | 0.943 | 0.960           |

Facts no item matched: 55; items matching no fact: 11.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| paraphrased   | 6                      | 0.667                  | 0.667                     | 1.000             | 0.667             | 1.000          | 4         | 0.500       |
| distributed   | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| complex       | 39                     | 0.923                  | 0.923                     | 1.000             | 0.923             | 1.000          | 4         | 0.750       |
| contradictory | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| all           | 69                     | 0.928                  | 0.928                     | 1.000             | 0.928             | 1.000          | 20        | 0.850       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.900                | 0.900          | 1.000               | -              | -         |
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
| paraphrased   | evidence-engine | 4         | 4            | 0.500                | 0.500          | 1.000               | -              | -         |
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
| evidence-engine | paraphrased   | 4         | 2                | 4                | 2          | 0            |
| evidence-engine | distributed   | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | complex       | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | contradictory | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | all           | 20        | 18               | 20               | 2          | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.788 [0.70, 0.87] | BCa      |
| metric          | 0.943 [0.83, 0.98] | BCa      |
| measurement     | 0.771 [0.65, 0.85] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.824 [0.76, 0.88] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.900 [0.70, 1.00]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.200 [0.05, 0.45]   | BCa      | 0.700 [0.45, 0.85]    | BCa             | 20         |
| agent-baseline  | 0.750 [0.50, 0.90]   | BCa      | 0.150 [-0.10, 0.40]   | BCa             | 20         |

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
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 21      | 19              | 20     | 18             |
| llm_measurement@1#02bd5a7ab104    | 48      | 45              | 44     | 41             |
| llm_metric@1#41e1e53a1fc4         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 20     | 20             |
| regex_condition@2#0a5bf730763c    | 23      | 23              | 22     | 22             |
| regex_measurement@2#e2d17eb260ea  | 33      | 28              | 29     | 24             |
| regex_metric@2#0affe2d9ce77       | 24      | 23              | 24     | 23             |

Facts no extractor found: condition 20, measurement 33, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 210     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 21      | 36      | 19        | 0.905       | 0.528    | 0.667 | 1.000           | -                      | 20     | 18             |
| llm_condition@1#45b3761c700e      | all             | all     | 21      | 36      | 19        | 0.905       | 0.528    | 0.667 | 1.000           | -                      | 20     | 18             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 48      | 69      | 45        | 0.938       | 0.652    | 0.769 | 1.000           | 0.956                  | 44     | 41             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 48      | 69      | 45        | 0.938       | 0.652    | 0.769 | 1.000           | -                      | 44     | 41             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 2       | 3       | 2         | 1.000       | 0.667    | 0.800 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 2       | 3       | 2         | 1.000       | 0.667    | 0.800 | 1.000           | -                      | 2      | 2              |
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
| llm_condition@1#45b3761c700e      | 12      | 15            | 17987          | 1712            | 3.345     |
| llm_measurement@1#02bd5a7ab104    | 13      | 26            | 36724          | 7977            | 11.758    |
| llm_metric@1#41e1e53a1fc4         | 3       | 3             | 3614           | 291             | 0.019     |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 18894          | 1784            | 0.129     |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.126     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.123     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.132     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.126     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.126     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 146     | 7.300       |
| calls            | 148     | 7.400       |
| input_tokens     | 77219   | 3860.950    |
| made_model_calls | 3       | 0.150       |
| model_calls      | 64      | 3.200       |
| output_tokens    | 11777   | 588.850     |
| seconds          | 16.974  | 0.849       |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.400          |
| model_calls   | 3.200          |
| input_tokens  | 3860.950       |
| output_tokens | 588.200        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 5           |
| 1               | 13          |
| exhausted       | 2           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
