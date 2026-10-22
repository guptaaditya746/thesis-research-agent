# Evaluation of run rag-claude-k1-mixed on rag-claude-k1-adf90d94

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 52      | 48      | 48        | 0.923       | 1.000    | 0.960 | 1.000           |
| all             | paraphrased   | 33      | 43      | 28        | 0.848       | 0.651    | 0.737 | 1.000           |
| all             | distributed   | 35      | 26      | 26        | 0.743       | 1.000    | 0.852 | 1.000           |
| all             | complex       | 80      | 72      | 70        | 0.875       | 0.972    | 0.921 | 1.000           |
| all             | contradictory | 41      | 38      | 36        | 0.878       | 0.947    | 0.911 | 1.000           |
| all             | all           | 241     | 227     | 208       | 0.863       | 0.916    | 0.889 | 1.000           |
| author_claim    | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 21      | 19      | 19        | 0.905       | 1.000    | 0.950 | 1.000           |
| condition       | paraphrased   | 17      | 17      | 13        | 0.765       | 0.765    | 0.765 | 1.000           |
| condition       | distributed   | 15      | 9       | 9         | 0.600       | 1.000    | 0.750 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 16      | 15      | 13        | 0.812       | 0.867    | 0.839 | 1.000           |
| condition       | all           | 78      | 69      | 63        | 0.808       | 0.913    | 0.857 | 1.000           |
| measurement     | explicit      | 20      | 19      | 19        | 0.950       | 1.000    | 0.974 | 1.000           |
| measurement     | paraphrased   | 8       | 16      | 8         | 1.000       | 0.500    | 0.667 | 1.000           |
| measurement     | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | complex       | 54      | 48      | 46        | 0.852       | 0.958    | 0.902 | 1.000           |
| measurement     | contradictory | 17      | 15      | 15        | 0.882       | 1.000    | 0.938 | 1.000           |
| measurement     | all           | 108     | 107     | 97        | 0.898       | 0.907    | 0.902 | 1.000           |
| metric          | explicit      | 6       | 5       | 5         | 0.833       | 1.000    | 0.909 | 1.000           |
| metric          | paraphrased   | 3       | 5       | 2         | 0.667       | 0.400    | 0.500 | 1.000           |
| metric          | distributed   | 7       | 4       | 4         | 0.571       | 1.000    | 0.727 | 1.000           |
| metric          | complex       | 13      | 11      | 11        | 0.846       | 1.000    | 0.917 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 33      | 29      | 26        | 0.788       | 0.897    | 0.839 | 1.000           |

Facts no item matched: 19; items matching no fact: 33.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 19                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.947          | 5         | 0.800       |
| paraphrased   | 8                      | 0.500                  | 0.500                     | 1.000             | 0.500             | 1.000          | 4         | 0.500       |
| distributed   | 9                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| complex       | 46                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.935          | 3         | 0.333       |
| contradictory | 15                     | 0.867                  | 0.867                     | 1.000             | 0.867             | 1.000          | 4         | 1.000       |
| all           | 97                     | 0.938                  | 0.938                     | 1.000             | 0.938             | 0.959          | 20        | 0.750       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 24        | 20           | 0.917                | 0.900          | 1.000               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 24        | 20           | 0.167                | 0.250          | 0.400               | 0.857          | 0.857     |
| agent-baseline  | mixed   | mixed      | yes             | 24        | 20           | 0.750                | 1.000          | 0.800               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit      | agent-baseline  | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit      | evidence-engine | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit      | rag-baseline    | 5         | 5            | 0.200                | 0.200          | 1.000               | 1.000          | 1.000     |
| paraphrased   | agent-baseline  | 5         | 4            | 0.800                | 1.000          | 1.000               | -              | -         |
| paraphrased   | evidence-engine | 5         | 4            | 0.600                | 0.500          | 1.000               | -              | -         |
| paraphrased   | rag-baseline    | 5         | 4            | 0.000                | 0.250          | 0.000               | 1.000          | 1.000     |
| distributed   | agent-baseline  | 5         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed   | evidence-engine | 5         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed   | rag-baseline    | 5         | 4            | 0.000                | 0.250          | 0.000               | 0.500          | 0.500     |
| complex       | agent-baseline  | 5         | 3            | 0.800                | 1.000          | 1.000               | -              | -         |
| complex       | evidence-engine | 5         | 3            | 1.000                | 1.000          | 1.000               | -              | -         |
| complex       | rag-baseline    | 5         | 3            | 0.600                | 0.333          | 1.000               | 1.000          | 1.000     |
| contradictory | agent-baseline  | 4         | 4            | 0.000                | 1.000          | 0.000               | -              | -         |
| contradictory | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| contradictory | rag-baseline    | 4         | 4            | 0.000                | 0.250          | 0.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 4    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 2    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | large_effect    | 1    | 0    | 1    | 1.000       | 0.500    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit      | 5         | 5                | 5                | 0          | 0            |
| evidence-engine | paraphrased   | 5         | 3                | 5                | 2          | 0            |
| evidence-engine | distributed   | 5         | 5                | 5                | 0          | 0            |
| evidence-engine | complex       | 5         | 5                | 5                | 0          | 0            |
| evidence-engine | contradictory | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | all           | 24        | 22               | 24               | 2          | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.857 [0.77, 0.92] | BCa      |
| metric          | 0.839 [0.74, 0.91] | BCa      |
| measurement     | 0.902 [0.83, 0.96] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.889 [0.85, 0.93] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.917 [0.71, 1.00]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.167 [0.04, 0.33]   | BCa      | 0.750 [0.54, 0.92]    | BCa             | 24         |
| agent-baseline  | 0.750 [0.54, 0.92]   | BCa      | 0.167 [-0.04, 0.42]   | BCa             | 24         |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 109          | 109      | 1.000    |
| all             | paraphrased   | 94           | 94       | 1.000    |
| all             | distributed   | 72           | 72       | 1.000    |
| all             | complex       | 156          | 156      | 1.000    |
| all             | contradictory | 88           | 88       | 1.000    |
| all             | all           | 519          | 519      | 1.000    |
| author_claim    | explicit      | 10           | 10       | 1.000    |
| author_claim    | paraphrased   | 10           | 10       | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 44           | 44       | 1.000    |
| condition       | explicit      | 42           | 42       | 1.000    |
| condition       | paraphrased   | 40           | 40       | 1.000    |
| condition       | distributed   | 31           | 31       | 1.000    |
| condition       | complex       | 46           | 46       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 199          | 199      | 1.000    |
| measurement     | explicit      | 19           | 19       | 1.000    |
| measurement     | paraphrased   | 16           | 16       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 48           | 48       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 107          | 107      | 1.000    |
| metric          | explicit      | 38           | 38       | 1.000    |
| metric          | paraphrased   | 28           | 28       | 1.000    |
| metric          | distributed   | 24           | 24       | 1.000    |
| metric          | complex       | 54           | 54       | 1.000    |
| metric          | contradictory | 25           | 25       | 1.000    |
| metric          | all           | 169          | 169      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 22      | 22              | 0      | 0              |
| llm_condition@1#45b3761c700e      | 69      | 63              | 53     | 47             |
| llm_measurement@1#02bd5a7ab104    | 98      | 93              | 41     | 37             |
| llm_metric@1#41e1e53a1fc4         | 25      | 25              | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | 22      | 22              | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 25      | 16              | 9      | 0              |
| regex_measurement@2#e2d17eb260ea  | 67      | 60              | 10     | 4              |
| regex_metric@2#0affe2d9ce77       | 26      | 19              | 8      | 1              |

Facts no extractor found: condition 6, measurement 10, metric 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 69      | 69      | 63        | 0.913       | 0.913    | 0.913 | 1.000           | -                      | 53     | 47             |
| llm_condition@1#45b3761c700e      | all             | all     | 69      | 69      | 63        | 0.913       | 0.913    | 0.913 | 1.000           | -                      | 53     | 47             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 98      | 107     | 93        | 0.949       | 0.869    | 0.907 | 1.000           | 0.935                  | 41     | 37             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 98      | 107     | 93        | 0.949       | 0.869    | 0.907 | 1.000           | -                      | 41     | 37             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 25      | 29      | 25        | 1.000       | 0.862    | 0.926 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 25      | 29      | 25        | 1.000       | 0.862    | 0.926 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 25      | 69      | 16        | 0.640       | 0.232    | 0.340 | 1.000           | -                      | 9      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 25      | 69      | 16        | 0.640       | 0.232    | 0.340 | 1.000           | -                      | 9      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 67      | 107     | 60        | 0.896       | 0.561    | 0.690 | 1.000           | 0.967                  | 10     | 4              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 67      | 107     | 60        | 0.896       | 0.561    | 0.690 | 1.000           | -                      | 10     | 4              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 26      | 29      | 19        | 0.731       | 0.655    | 0.691 | 1.000           | -                      | 8      | 1              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 26      | 29      | 19        | 0.731       | 0.655    | 0.691 | 1.000           | -                      | 8      | 1              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 24      | 24            | 24196          | 2626            | 20.685    |
| llm_condition@1#45b3761c700e      | 24      | 28            | 30465          | 5081            | 37.191    |
| llm_measurement@1#02bd5a7ab104    | 24      | 46            | 63341          | 18086           | 121.575   |
| llm_metric@1#41e1e53a1fc4         | 24      | 27            | 29568          | 2485            | 18.216    |
| llm_screen@1#41b0d6e6793f         | 23      | 23            | 20968          | 1926            | 16.056    |
| regex_author_claim@2#fd7877790c48 | 24      | 0             | 0              | 0               | 0.154     |
| regex_condition@2#0a5bf730763c    | 24      | 0             | 0              | 0               | 0.156     |
| regex_measurement@2#e2d17eb260ea  | 24      | 0             | 0              | 0               | 0.238     |
| regex_metric@2#0affe2d9ce77       | 24      | 0             | 0              | 0               | 0.156     |
| regex_screen@1#858a6ebc69c6       | 24      | 0             | 0              | 0               | 0.156     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 194     | 8.083       |
| calls            | 239     | 9.958       |
| input_tokens     | 168538  | 7022.417    |
| made_model_calls | 47      | 1.958       |
| model_calls      | 148     | 6.167       |
| output_tokens    | 30204   | 1258.500    |
| seconds          | 215.920 | 8.997       |

## Funnel

Strategy `all` over 24 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 9.958          |
| model_calls   | 6.167          |
| input_tokens  | 7022.417       |
| output_tokens | 1258.500       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 24          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 24          | 22   | 0    | 0    | 2    | 1.000       | 1.000    |

Screened out wrongly: none
