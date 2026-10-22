# Evaluation of run rag-claude-k1-mixed on rag-claude-k1-adf90d94

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 21      | 48      | 21        | 1.000       | 0.438    | 0.609 | 0.952           |
| all             | paraphrased   | 6       | 43      | 6         | 1.000       | 0.140    | 0.245 | 0.833           |
| all             | distributed   | 17      | 26      | 14        | 0.824       | 0.538    | 0.651 | 1.000           |
| all             | complex       | 38      | 72      | 38        | 1.000       | 0.528    | 0.691 | 1.000           |
| all             | contradictory | 24      | 38      | 22        | 0.917       | 0.579    | 0.710 | 0.955           |
| all             | all           | 106     | 227     | 101       | 0.953       | 0.445    | 0.607 | 0.970           |
| author_claim    | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 7       | 19      | 7         | 1.000       | 0.368    | 0.538 | 0.857           |
| condition       | paraphrased   | 0       | 17      | 0         | 0.000       | 0.000    | 0.000 | -               |
| condition       | distributed   | 7       | 9       | 6         | 0.857       | 0.667    | 0.750 | 1.000           |
| condition       | complex       | 4       | 9       | 4         | 1.000       | 0.444    | 0.615 | 1.000           |
| condition       | contradictory | 7       | 15      | 7         | 1.000       | 0.467    | 0.636 | 0.857           |
| condition       | all           | 25      | 69      | 24        | 0.960       | 0.348    | 0.511 | 0.917           |
| measurement     | explicit      | 5       | 19      | 5         | 1.000       | 0.263    | 0.417 | 1.000           |
| measurement     | paraphrased   | 0       | 16      | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | distributed   | 0       | 9       | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | complex       | 19      | 48      | 19        | 1.000       | 0.396    | 0.567 | 1.000           |
| measurement     | contradictory | 9       | 15      | 7         | 0.778       | 0.467    | 0.583 | 1.000           |
| measurement     | all           | 33      | 107     | 31        | 0.939       | 0.290    | 0.443 | 1.000           |
| metric          | explicit      | 4       | 5       | 4         | 1.000       | 0.800    | 0.889 | 1.000           |
| metric          | paraphrased   | 1       | 5       | 1         | 1.000       | 0.200    | 0.333 | 0.000           |
| metric          | distributed   | 6       | 4       | 4         | 0.667       | 1.000    | 0.800 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 26      | 29      | 24        | 0.923       | 0.828    | 0.873 | 0.958           |

Facts no item matched: 126; items matching no fact: 5.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 5                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 5         | 0.200       |
| paraphrased   | 0                      | -                      | -                         | -                 | -                 | -              | 4         | 0.000       |
| distributed   | 0                      | -                      | -                         | -                 | -                 | -              | 4         | 0.000       |
| complex       | 19                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 3         | 0.000       |
| contradictory | 7                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 0.750       |
| all           | 31                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.200       |

## C. Synthesis

| system          | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | supported | mixed      | no              | 24        | 20           | 0.333                | 0.200          | 1.000               | -              | -         |
| rag-baseline    | mixed     | mixed      | yes             | 24        | 20           | 0.167                | 0.250          | 0.400               | 0.857          | 0.857     |
| agent-baseline  | mixed     | mixed      | yes             | 24        | 20           | 0.750                | 1.000          | 0.800               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit      | agent-baseline  | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit      | evidence-engine | 5         | 5            | 0.200                | 0.200          | 1.000               | -              | -         |
| explicit      | rag-baseline    | 5         | 5            | 0.200                | 0.200          | 1.000               | 1.000          | 1.000     |
| paraphrased   | agent-baseline  | 5         | 4            | 0.800                | 1.000          | 1.000               | -              | -         |
| paraphrased   | evidence-engine | 5         | 4            | 0.200                | 0.000          | -                   | -              | -         |
| paraphrased   | rag-baseline    | 5         | 4            | 0.000                | 0.250          | 0.000               | 1.000          | 1.000     |
| distributed   | agent-baseline  | 5         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed   | evidence-engine | 5         | 4            | 0.200                | 0.000          | -                   | -              | -         |
| distributed   | rag-baseline    | 5         | 4            | 0.000                | 0.250          | 0.000               | 0.500          | 0.500     |
| complex       | agent-baseline  | 5         | 3            | 0.800                | 1.000          | 1.000               | -              | -         |
| complex       | evidence-engine | 5         | 3            | 0.400                | 0.000          | -                   | -              | -         |
| complex       | rag-baseline    | 5         | 3            | 0.600                | 0.333          | 1.000               | 1.000          | 1.000     |
| contradictory | agent-baseline  | 4         | 4            | 0.000                | 1.000          | 0.000               | -              | -         |
| contradictory | evidence-engine | 4         | 4            | 0.750                | 0.750          | 1.000               | -              | -         |
| contradictory | rag-baseline    | 4         | 4            | 0.000                | 0.250          | 0.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 3    | 0    | 1    | 1.000       | 0.750    |
| evidence-engine | duplicate       | 0    | 0    | 2    | -           | 0.000    |
| evidence-engine | large_effect    | 0    | 0    | 2    | -           | 0.000    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | no                   |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit      | 5         | 1                | 5                | 4          | 0            |
| evidence-engine | paraphrased   | 5         | 1                | 5                | 4          | 0            |
| evidence-engine | distributed   | 5         | 1                | 5                | 4          | 0            |
| evidence-engine | complex       | 5         | 2                | 5                | 3          | 0            |
| evidence-engine | contradictory | 4         | 3                | 4                | 1          | 0            |
| evidence-engine | all           | 24        | 8                | 24               | 16         | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.511 [0.37, 0.63] | BCa      |
| metric          | 0.873 [0.74, 0.95] | BCa      |
| measurement     | 0.443 [0.29, 0.68] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.607 [0.52, 0.72] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.333 [0.17, 0.54]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.167 [0.04, 0.33]   | BCa      | 0.167 [-0.04, 0.38]   | BCa             | 24         |
| agent-baseline  | 0.750 [0.54, 0.92]   | BCa      | -0.417 [-0.71, -0.04] | BCa             | 24         |

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
| regex_author_claim@2#fd7877790c48 | 22      | 22              | 22     | 22             |
| regex_condition@2#0a5bf730763c    | 25      | 24              | 25     | 24             |
| regex_measurement@2#e2d17eb260ea  | 33      | 31              | 33     | 31             |
| regex_metric@2#0affe2d9ce77       | 26      | 24              | 26     | 24             |

Facts no extractor found: condition 45, measurement 76, metric 5

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 22     | 22             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 22     | 22             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 25      | 69      | 24        | 0.960       | 0.348    | 0.511 | 0.917           | -                      | 25     | 24             |
| regex_condition@2#0a5bf730763c    | all             | all     | 25      | 69      | 24        | 0.960       | 0.348    | 0.511 | 0.917           | -                      | 25     | 24             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 33      | 107     | 31        | 0.939       | 0.290    | 0.443 | 1.000           | 1.000                  | 33     | 31             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 33      | 107     | 31        | 0.939       | 0.290    | 0.443 | 1.000           | -                      | 33     | 31             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 26      | 29      | 24        | 0.923       | 0.828    | 0.873 | 0.958           | -                      | 26     | 24             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 26      | 29      | 24        | 0.923       | 0.828    | 0.873 | 0.958           | -                      | 26     | 24             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| regex_author_claim@2#fd7877790c48 | 24      | 0             | 0              | 0               | 0.213     |
| regex_condition@2#0a5bf730763c    | 24      | 0             | 0              | 0               | 0.223     |
| regex_measurement@2#e2d17eb260ea  | 24      | 0             | 0              | 0               | 0.219     |
| regex_metric@2#0affe2d9ce77       | 24      | 0             | 0              | 0               | 0.210     |
| regex_screen@1#858a6ebc69c6       | 24      | 0             | 0              | 0               | 0.224     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 80      | 3.333       |
| calls            | 120     | 5.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 2.356   | 0.098       |

## Funnel

Strategy `all` over 24 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 5.000          |
| model_calls   | 0.000          |
| input_tokens  | 0.000          |
| output_tokens | 0.000          |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 24          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 24          | 22   | 1    | 0    | 1    | 0.957       | 1.000    |

Screened out wrongly: none
