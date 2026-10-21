# Evaluation of run rag-llm-s1-mixed on rag-llm-s1-0278df5c

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 4       | 10      | 3         | 0.750       | 0.300    | 0.429 | 0.667           |
| all             | paraphrased   | 3       | 18      | 3         | 1.000       | 0.167    | 0.286 | 0.667           |
| all             | distributed   | 14      | 20      | 11        | 0.786       | 0.550    | 0.647 | 0.818           |
| all             | complex       | 38      | 56      | 36        | 0.947       | 0.643    | 0.766 | 0.889           |
| all             | contradictory | 14      | 20      | 12        | 0.857       | 0.600    | 0.706 | 1.000           |
| all             | all           | 73      | 124     | 65        | 0.890       | 0.524    | 0.660 | 0.877           |
| author_claim    | explicit      | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 0.500           |
| condition       | paraphrased   | 0       | 7       | 0         | 0.000       | 0.000    | 0.000 | -               |
| condition       | distributed   | 5       | 7       | 5         | 1.000       | 0.714    | 0.833 | 0.600           |
| condition       | complex       | 5       | 7       | 5         | 1.000       | 0.714    | 0.833 | 0.200           |
| condition       | contradictory | 4       | 8       | 4         | 1.000       | 0.500    | 0.667 | 1.000           |
| condition       | all           | 16      | 33      | 16        | 1.000       | 0.485    | 0.653 | 0.562           |
| measurement     | explicit      | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | paraphrased   | 0       | 7       | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | distributed   | 0       | 7       | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | complex       | 20      | 38      | 20        | 1.000       | 0.526    | 0.690 | 1.000           |
| measurement     | contradictory | 5       | 8       | 4         | 0.800       | 0.500    | 0.615 | 1.000           |
| measurement     | all           | 25      | 64      | 24        | 0.960       | 0.375    | 0.539 | 1.000           |
| metric          | explicit      | 1       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               |
| metric          | paraphrased   | 1       | 2       | 1         | 1.000       | 0.500    | 0.667 | 0.000           |
| metric          | distributed   | 6       | 3       | 3         | 0.500       | 1.000    | 0.667 | 1.000           |
| metric          | complex       | 10      | 8       | 8         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | contradictory | 3       | 2       | 2         | 0.667       | 1.000    | 0.800 | 1.000           |
| metric          | all           | 21      | 16      | 14        | 0.667       | 0.875    | 0.757 | 0.929           |

Facts no item matched: 59; items matching no fact: 8.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 0                      | -                      | -                         | -                 | -                 | -              | 1         | 0.000       |
| paraphrased   | 0                      | -                      | -                         | -                 | -                 | -              | 2         | 0.000       |
| distributed   | 0                      | -                      | -                         | -                 | -                 | -              | 3         | 0.000       |
| complex       | 20                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 3         | 0.000       |
| contradictory | 4                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 2         | 1.000       |
| all           | 24                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 11        | 0.182       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 11        | 11           | 0.273                | 0.273          | 1.000               | -              |
| rag-baseline    | mixed   | mixed      | yes             | 11        | 11           | 0.545                | 0.545          | 1.000               | 1.000          |
| agent-baseline  | mixed   | mixed      | yes             | 11        | 11           | 0.818                | 1.000          | 0.818               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | agent-baseline  | 1         | yes          | 1.000                | 1.000          | 1.000               | -              |
| explicit      | evidence-engine | 1         | yes          | 0.000                | 0.000          | -                   | -              |
| explicit      | rag-baseline    | 1         | yes          | 0.000                | 0.000          | -                   | -              |
| paraphrased   | agent-baseline  | 2         | 2            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | evidence-engine | 2         | 2            | 0.000                | 0.000          | -                   | -              |
| paraphrased   | rag-baseline    | 2         | 2            | 0.500                | 0.500          | 1.000               | 1.000          |
| distributed   | agent-baseline  | 3         | 3            | 1.000                | 1.000          | 1.000               | -              |
| distributed   | evidence-engine | 3         | 3            | 0.000                | 0.000          | -                   | -              |
| distributed   | rag-baseline    | 3         | 3            | 0.667                | 0.667          | 1.000               | 1.000          |
| complex       | agent-baseline  | 3         | 3            | 1.000                | 1.000          | 1.000               | -              |
| complex       | evidence-engine | 3         | 3            | 0.333                | 0.333          | 1.000               | -              |
| complex       | rag-baseline    | 3         | 3            | 1.000                | 1.000          | 1.000               | 1.000          |
| contradictory | agent-baseline  | 2         | 2            | 0.000                | 1.000          | 0.000               | -              |
| contradictory | evidence-engine | 2         | 2            | 1.000                | 1.000          | 1.000               | -              |
| contradictory | rag-baseline    | 2         | 2            | 0.000                | 0.000          | -                   | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 2    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.653 [0.43, 0.77] | BCa      |
| metric          | 0.757 [0.56, 0.86] | BCa      |
| measurement     | 0.539 [0.32, 0.80] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.660 [0.56, 0.81] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.273 [0.09, 0.55]   | BCa      | -                     | -               |
| rag-baseline    | 0.545 [0.27, 0.82]   | BCa      | -0.273 [-0.64, 0.18]  | BCa             |
| agent-baseline  | 0.818 [0.55, 1.00]   | BCa      | -0.545 [-0.91, 0.09]  | BCa             |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 23           | 23       | 1.000    |
| all             | paraphrased   | 55           | 55       | 1.000    |
| all             | distributed   | 64           | 64       | 1.000    |
| all             | complex       | 139          | 139      | 1.000    |
| all             | contradictory | 61           | 61       | 1.000    |
| all             | all           | 342          | 342      | 1.000    |
| author_claim    | explicit      | 2            | 2        | 1.000    |
| author_claim    | paraphrased   | 4            | 4        | 1.000    |
| author_claim    | distributed   | 6            | 6        | 1.000    |
| author_claim    | complex       | 6            | 6        | 1.000    |
| author_claim    | contradictory | 4            | 4        | 1.000    |
| author_claim    | all           | 22           | 22       | 1.000    |
| condition       | explicit      | 9            | 9        | 1.000    |
| condition       | paraphrased   | 30           | 30       | 1.000    |
| condition       | distributed   | 34           | 34       | 1.000    |
| condition       | complex       | 56           | 56       | 1.000    |
| condition       | contradictory | 38           | 38       | 1.000    |
| condition       | all           | 167          | 167      | 1.000    |
| measurement     | explicit      | 4            | 4        | 1.000    |
| measurement     | paraphrased   | 7            | 7        | 1.000    |
| measurement     | distributed   | 7            | 7        | 1.000    |
| measurement     | complex       | 38           | 38       | 1.000    |
| measurement     | contradictory | 8            | 8        | 1.000    |
| measurement     | all           | 64           | 64       | 1.000    |
| metric          | explicit      | 8            | 8        | 1.000    |
| metric          | paraphrased   | 14           | 14       | 1.000    |
| metric          | distributed   | 17           | 17       | 1.000    |
| metric          | complex       | 39           | 39       | 1.000    |
| metric          | contradictory | 11           | 11       | 1.000    |
| metric          | all           | 89           | 89       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 11     | 11             |
| regex_condition@2#80486860164a    | 16      | 16              | 16     | 16             |
| regex_measurement@2#9edb306c5b05  | 25      | 24              | 25     | 24             |
| regex_metric@2#67f41f33eff7       | 21      | 14              | 21     | 14             |

Facts no extractor found: condition 17, measurement 40, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_condition@2#80486860164a    | condition       | all     | 16      | 33      | 16        | 1.000       | 0.485    | 0.653 | 0.562           | -                      | 16     | 16             |
| regex_condition@2#80486860164a    | all             | all     | 16      | 33      | 16        | 1.000       | 0.485    | 0.653 | 0.562           | -                      | 16     | 16             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 25      | 64      | 24        | 0.960       | 0.375    | 0.539 | 1.000           | 1.000                  | 25     | 24             |
| regex_measurement@2#9edb306c5b05  | all             | all     | 25      | 64      | 24        | 0.960       | 0.375    | 0.539 | 1.000           | -                      | 25     | 24             |
| regex_metric@2#67f41f33eff7       | metric          | all     | 21      | 16      | 14        | 0.667       | 0.875    | 0.757 | 0.929           | -                      | 21     | 14             |
| regex_metric@2#67f41f33eff7       | all             | all     | 21      | 16      | 14        | 0.667       | 0.875    | 0.757 | 0.929           | -                      | 21     | 14             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.091     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.095     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.088     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.087     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.101     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 45      | 4.091       |
| calls            | 55      | 5.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 0.933   | 0.085       |

## Funnel

Strategy `all` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 5.000          |
| model_calls   | 0.000          |
| input_tokens  | 0.000          |
| output_tokens | 0.000          |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 11          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
