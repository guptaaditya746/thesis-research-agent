# Evaluation of run rag-tpl-hard-mixed on rag-tpl-hard-b1c0fdfe

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 204     | 181     | 180       | 0.882       | 0.994    | 0.935 | 1.000           |
| all             | paraphrased   | 142     | 155     | 138       | 0.972       | 0.890    | 0.929 | 1.000           |
| all             | distributed   | 195     | 159     | 158       | 0.810       | 0.994    | 0.893 | 1.000           |
| all             | complex       | 483     | 476     | 456       | 0.944       | 0.958    | 0.951 | 1.000           |
| all             | contradictory | 195     | 168     | 165       | 0.846       | 0.982    | 0.909 | 1.000           |
| all             | all           | 1219    | 1139    | 1097      | 0.900       | 0.963    | 0.930 | 1.000           |
| author_claim    | explicit      | 23      | 23      | 23        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 21      | 21      | 21        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 21      | 21      | 21        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 21      | 21      | 21        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 74      | 68      | 67        | 0.905       | 0.985    | 0.944 | 1.000           |
| condition       | paraphrased   | 58      | 57      | 56        | 0.966       | 0.982    | 0.974 | 1.000           |
| condition       | distributed   | 85      | 60      | 59        | 0.694       | 0.983    | 0.814 | 1.000           |
| condition       | complex       | 75      | 67      | 67        | 0.893       | 1.000    | 0.944 | 1.000           |
| condition       | contradictory | 68      | 64      | 61        | 0.897       | 0.953    | 0.924 | 1.000           |
| condition       | all           | 360     | 316     | 310       | 0.861       | 0.981    | 0.917 | 1.000           |
| measurement     | explicit      | 76      | 67      | 67        | 0.882       | 1.000    | 0.937 | 1.000           |
| measurement     | paraphrased   | 44      | 56      | 44        | 1.000       | 0.786    | 0.880 | 1.000           |
| measurement     | distributed   | 59      | 59      | 59        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | complex       | 333     | 338     | 318       | 0.955       | 0.941    | 0.948 | 1.000           |
| measurement     | contradictory | 82      | 62      | 62        | 0.756       | 1.000    | 0.861 | 1.000           |
| measurement     | all           | 594     | 582     | 550       | 0.926       | 0.945    | 0.935 | 1.000           |
| metric          | explicit      | 31      | 23      | 23        | 0.742       | 1.000    | 0.852 | 1.000           |
| metric          | paraphrased   | 19      | 21      | 17        | 0.895       | 0.810    | 0.850 | 1.000           |
| metric          | distributed   | 31      | 20      | 20        | 0.645       | 1.000    | 0.784 | 1.000           |
| metric          | complex       | 54      | 50      | 50        | 0.926       | 1.000    | 0.962 | 1.000           |
| metric          | contradictory | 24      | 21      | 21        | 0.875       | 1.000    | 0.933 | 1.000           |
| metric          | all           | 159     | 135     | 131       | 0.824       | 0.970    | 0.891 | 1.000           |

Facts no item matched: 42; items matching no fact: 122.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 67                     | 0.985                  | 0.985                     | 1.000             | 0.970             | 0.896          | 22        | 0.727       |
| paraphrased   | 44                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.800       |
| distributed   | 59                     | 0.983                  | 0.983                     | 1.000             | 0.864             | 0.627          | 19        | 1.000       |
| complex       | 318                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.981          | 20        | 0.000       |
| contradictory | 62                     | 0.952                  | 0.952                     | 1.000             | 0.952             | 0.984          | 19        | 0.947       |
| all           | 550                    | 0.991                  | 0.991                     | 1.000             | 0.976             | 0.935          | 100       | 0.690       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 112       | 100          | 0.929                | 0.960          | 0.958               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 112       | 100          | 0.116                | 0.050          | 0.400               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 112       | 100          | 0.375                | 0.380          | 0.842               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit      | agent-baseline  | 24        | 22           | 0.417                | 0.364          | 1.000               | -              | -         |
| explicit      | evidence-engine | 24        | 22           | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit      | rag-baseline    | 24        | 22           | 0.125                | 0.045          | 1.000               | 1.000          | 1.000     |
| paraphrased   | agent-baseline  | 23        | 20           | 0.478                | 0.400          | 1.000               | -              | -         |
| paraphrased   | evidence-engine | 23        | 20           | 0.826                | 0.800          | 1.000               | -              | -         |
| paraphrased   | rag-baseline    | 23        | 20           | 0.130                | 0.000          | -                   | -              | -         |
| distributed   | agent-baseline  | 21        | 19           | 0.476                | 0.421          | 1.000               | -              | -         |
| distributed   | evidence-engine | 21        | 19           | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed   | rag-baseline    | 21        | 19           | 0.048                | 0.000          | -                   | 1.000          | 1.000     |
| complex       | agent-baseline  | 22        | 20           | 0.455                | 0.400          | 1.000               | -              | -         |
| complex       | evidence-engine | 22        | 20           | 0.818                | 1.000          | 0.800               | -              | -         |
| complex       | rag-baseline    | 22        | 20           | 0.136                | 0.050          | 1.000               | 1.000          | 1.000     |
| contradictory | agent-baseline  | 22        | 19           | 0.045                | 0.316          | 0.000               | -              | -         |
| contradictory | evidence-engine | 22        | 19           | 1.000                | 1.000          | 1.000               | -              | -         |
| contradictory | rag-baseline    | 22        | 19           | 0.136                | 0.158          | 0.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 19   | 4    | 0    | 0.826       | 1.000    |
| evidence-engine | duplicate       | 6    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | large_effect    | 6    | 1    | 0    | 0.857       | 1.000    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit      | 24        | 24               | 24               | 0          | 0            |
| evidence-engine | paraphrased   | 23        | 19               | 23               | 4          | 0            |
| evidence-engine | distributed   | 21        | 21               | 21               | 0          | 0            |
| evidence-engine | complex       | 22        | 18               | 18               | 0          | 4            |
| evidence-engine | contradictory | 22        | 22               | 22               | 0          | 0            |
| evidence-engine | all           | 112       | 104              | 108              | 4          | 4            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.917 [0.89, 0.94] | BCa      |
| metric          | 0.891 [0.85, 0.92] | BCa      |
| measurement     | 0.935 [0.91, 0.95] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.930 [0.91, 0.94] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.929 [0.87, 0.96]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.116 [0.06, 0.18]   | BCa      | 0.812 [0.74, 0.88]    | BCa             | 112        |
| agent-baseline  | 0.375 [0.29, 0.46]   | BCa      | 0.554 [0.45, 0.64]    | BCa             | 112        |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 407          | 407      | 1.000    |
| all             | paraphrased   | 330          | 330      | 1.000    |
| all             | distributed   | 359          | 359      | 1.000    |
| all             | complex       | 841          | 841      | 1.000    |
| all             | contradictory | 357          | 357      | 1.000    |
| all             | all           | 2294         | 2294     | 1.000    |
| author_claim    | explicit      | 46           | 46       | 1.000    |
| author_claim    | paraphrased   | 42           | 42       | 1.000    |
| author_claim    | distributed   | 40           | 40       | 1.000    |
| author_claim    | complex       | 42           | 42       | 1.000    |
| author_claim    | contradictory | 42           | 42       | 1.000    |
| author_claim    | all           | 212          | 212      | 1.000    |
| condition       | explicit      | 181          | 181      | 1.000    |
| condition       | paraphrased   | 155          | 155      | 1.000    |
| condition       | distributed   | 180          | 180      | 1.000    |
| condition       | complex       | 291          | 291      | 1.000    |
| condition       | contradictory | 180          | 180      | 1.000    |
| condition       | all           | 987          | 987      | 1.000    |
| measurement     | explicit      | 67           | 67       | 1.000    |
| measurement     | paraphrased   | 56           | 56       | 1.000    |
| measurement     | distributed   | 59           | 59       | 1.000    |
| measurement     | complex       | 338          | 338      | 1.000    |
| measurement     | contradictory | 62           | 62       | 1.000    |
| measurement     | all           | 582          | 582      | 1.000    |
| metric          | explicit      | 113          | 113      | 1.000    |
| metric          | paraphrased   | 77           | 77       | 1.000    |
| metric          | distributed   | 80           | 80       | 1.000    |
| metric          | complex       | 170          | 170      | 1.000    |
| metric          | contradictory | 73           | 73       | 1.000    |
| metric          | all           | 513          | 513      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 106     | 106             | 0      | 0              |
| llm_condition@1#45b3761c700e      | 316     | 302             | 231    | 217            |
| llm_measurement@1#02bd5a7ab104    | 559     | 535             | 285    | 261            |
| llm_metric@1#41e1e53a1fc4         | 133     | 123             | 79     | 69             |
| regex_author_claim@2#fd7877790c48 | 106     | 106             | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 129     | 93              | 44     | 8              |
| regex_measurement@2#e2d17eb260ea  | 309     | 289             | 35     | 15             |
| regex_metric@2#0affe2d9ce77       | 80      | 62              | 26     | 8              |

Facts no extractor found: condition 6, measurement 32, metric 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 316     | 316     | 302       | 0.956       | 0.956    | 0.956 | 1.000           | -                      | 231    | 217            |
| llm_condition@1#45b3761c700e      | all             | all     | 316     | 316     | 302       | 0.956       | 0.956    | 0.956 | 1.000           | -                      | 231    | 217            |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 559     | 582     | 535       | 0.957       | 0.919    | 0.938 | 1.000           | 0.991                  | 285    | 261            |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 559     | 582     | 535       | 0.957       | 0.919    | 0.938 | 1.000           | -                      | 285    | 261            |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 133     | 135     | 123       | 0.925       | 0.911    | 0.918 | 1.000           | -                      | 79     | 69             |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 133     | 135     | 123       | 0.925       | 0.911    | 0.918 | 1.000           | -                      | 79     | 69             |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 129     | 316     | 93        | 0.721       | 0.294    | 0.418 | 1.000           | -                      | 44     | 8              |
| regex_condition@2#0a5bf730763c    | all             | all     | 129     | 316     | 93        | 0.721       | 0.294    | 0.418 | 1.000           | -                      | 44     | 8              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 309     | 582     | 289       | 0.935       | 0.497    | 0.649 | 1.000           | 0.993                  | 35     | 15             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 309     | 582     | 289       | 0.935       | 0.497    | 0.649 | 1.000           | -                      | 35     | 15             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 80      | 135     | 62        | 0.775       | 0.459    | 0.577 | 1.000           | -                      | 26     | 8              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 80      | 135     | 62        | 0.775       | 0.459    | 0.577 | 1.000           | -                      | 26     | 8              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 112     | 112           | 97634          | 12701           | 332.800   |
| llm_condition@1#45b3761c700e      | 112     | 190           | 180912         | 31146           | 787.107   |
| llm_measurement@1#02bd5a7ab104    | 112     | 218           | 274663         | 98155           | 2251.636  |
| llm_metric@1#41e1e53a1fc4         | 112     | 127           | 122241         | 12775           | 334.869   |
| llm_screen@1#41b0d6e6793f         | 109     | 109           | 83485          | 8405            | 230.453   |
| regex_author_claim@2#fd7877790c48 | 112     | 0             | 0              | 0               | 0.868     |
| regex_condition@2#0a5bf730763c    | 112     | 0             | 0              | 0               | 0.871     |
| regex_measurement@2#e2d17eb260ea  | 112     | 0             | 0              | 0               | 1.804     |
| regex_metric@2#0affe2d9ce77       | 112     | 0             | 0              | 0               | 0.854     |
| regex_screen@1#858a6ebc69c6       | 112     | 0             | 0              | 0               | 0.871     |

## Cost

| measure          | total    | per_paper   |
|------------------|----------|-------------|
| cached_calls     | 477      | 4.259       |
| calls            | 1117     | 9.973       |
| input_tokens     | 758935   | 6776.205    |
| made_model_calls | 727      | 6.491       |
| model_calls      | 756      | 6.750       |
| output_tokens    | 163191   | 1457.062    |
| seconds          | 3949.058 | 35.259      |

## Funnel

Strategy `all` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 9.973          |
| model_calls   | 6.750          |
| input_tokens  | 6776.205       |
| output_tokens | 1456.982       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 112         |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 0    | 0    | 6    | 1.000       | 1.000    |

Screened out wrongly: none
