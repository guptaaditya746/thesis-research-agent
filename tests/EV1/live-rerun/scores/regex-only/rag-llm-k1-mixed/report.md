# Evaluation of run rag-llm-k1-mixed on rag-llm-k1-961f46a3

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 4       | 10      | 3         | 0.750       | 0.300    | 0.429 | 0.667           |
| all             | paraphrased   | 4       | 20      | 3         | 0.750       | 0.150    | 0.250 | 0.667           |
| all             | distributed   | 11      | 14      | 7         | 0.636       | 0.500    | 0.560 | 0.857           |
| all             | complex       | 20      | 38      | 19        | 0.950       | 0.500    | 0.655 | 0.895           |
| all             | contradictory | 14      | 20      | 12        | 0.857       | 0.600    | 0.706 | 1.000           |
| all             | all           | 53      | 102     | 44        | 0.830       | 0.431    | 0.568 | 0.886           |
| author_claim    | explicit      | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 0.500           |
| condition       | paraphrased   | 0       | 8       | 0         | 0.000       | 0.000    | 0.000 | -               |
| condition       | distributed   | 4       | 5       | 3         | 0.750       | 0.600    | 0.667 | 0.667           |
| condition       | complex       | 3       | 5       | 3         | 1.000       | 0.600    | 0.750 | 0.333           |
| condition       | contradictory | 4       | 8       | 4         | 1.000       | 0.500    | 0.667 | 1.000           |
| condition       | all           | 13      | 30      | 12        | 0.923       | 0.400    | 0.558 | 0.667           |
| measurement     | explicit      | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | paraphrased   | 0       | 8       | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | distributed   | 0       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | complex       | 9       | 26      | 9         | 1.000       | 0.346    | 0.514 | 1.000           |
| measurement     | contradictory | 5       | 8       | 4         | 0.800       | 0.500    | 0.615 | 1.000           |
| measurement     | all           | 14      | 51      | 13        | 0.929       | 0.255    | 0.400 | 1.000           |
| metric          | explicit      | 1       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               |
| metric          | paraphrased   | 2       | 2       | 1         | 0.500       | 0.500    | 0.500 | 0.000           |
| metric          | distributed   | 5       | 2       | 2         | 0.400       | 1.000    | 0.571 | 1.000           |
| metric          | complex       | 6       | 5       | 5         | 0.833       | 1.000    | 0.909 | 1.000           |
| metric          | contradictory | 3       | 2       | 2         | 0.667       | 1.000    | 0.800 | 1.000           |
| metric          | all           | 17      | 12      | 10        | 0.588       | 0.833    | 0.690 | 0.900           |

Facts no item matched: 58; items matching no fact: 9.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 0                      | -                      | -                         | -                 | -                 | -              | 1         | 0.000       |
| paraphrased   | 0                      | -                      | -                         | -                 | -                 | -              | 2         | 0.000       |
| distributed   | 0                      | -                      | -                         | -                 | -                 | -              | 2         | 0.000       |
| complex       | 9                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 2         | 0.000       |
| contradictory | 4                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 2         | 1.000       |
| all           | 13                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 9         | 0.222       |

## C. Synthesis

| system          | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | supported | mixed      | no              | 11        | 9            | 0.364                | 0.222          | 1.000               | -              |
| rag-baseline    | mixed     | mixed      | yes             | 11        | 9            | 0.545                | 0.556          | 0.800               | 1.000          |
| agent-baseline  | mixed     | mixed      | yes             | 11        | 9            | 0.818                | 1.000          | 0.778               | -              |

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
| distributed   | agent-baseline  | 3         | 2            | 1.000                | 1.000          | 1.000               | -              |
| distributed   | evidence-engine | 3         | 2            | 0.333                | 0.000          | -                   | -              |
| distributed   | rag-baseline    | 3         | 2            | 0.667                | 0.500          | 1.000               | 1.000          |
| complex       | agent-baseline  | 3         | 2            | 1.000                | 1.000          | 1.000               | -              |
| complex       | evidence-engine | 3         | 2            | 0.333                | 0.000          | -                   | -              |
| complex       | rag-baseline    | 3         | 2            | 1.000                | 1.000          | 1.000               | 1.000          |
| contradictory | agent-baseline  | 2         | 2            | 0.000                | 1.000          | 0.000               | -              |
| contradictory | evidence-engine | 2         | 2            | 1.000                | 1.000          | 1.000               | -              |
| contradictory | rag-baseline    | 2         | 2            | 0.000                | 0.500          | 0.000               | 1.000          |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 2    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 1    | -           | 0.000    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.558 [0.31, 0.69] | BCa      |
| metric          | 0.690 [0.44, 0.86] | BCa      |
| measurement     | 0.400 [0.17, 0.51] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.568 [0.43, 0.65] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.364 [0.09, 0.64]   | BCa      | -                     | -               |
| rag-baseline    | 0.545 [0.27, 0.82]   | BCa      | -0.182 [-0.55, 0.27]  | BCa             |
| agent-baseline  | 0.818 [0.45, 1.00]   | BCa      | -0.455 [-0.82, 0.18]  | BCa             |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 23           | 23       | 1.000    |
| all             | paraphrased   | 60           | 60       | 1.000    |
| all             | distributed   | 45           | 45       | 1.000    |
| all             | complex       | 97           | 97       | 1.000    |
| all             | contradictory | 61           | 61       | 1.000    |
| all             | all           | 286          | 286      | 1.000    |
| author_claim    | explicit      | 2            | 2        | 1.000    |
| author_claim    | paraphrased   | 4            | 4        | 1.000    |
| author_claim    | distributed   | 4            | 4        | 1.000    |
| author_claim    | complex       | 4            | 4        | 1.000    |
| author_claim    | contradictory | 4            | 4        | 1.000    |
| author_claim    | all           | 18           | 18       | 1.000    |
| condition       | explicit      | 9            | 9        | 1.000    |
| condition       | paraphrased   | 32           | 32       | 1.000    |
| condition       | distributed   | 24           | 24       | 1.000    |
| condition       | complex       | 42           | 42       | 1.000    |
| condition       | contradictory | 38           | 38       | 1.000    |
| condition       | all           | 145          | 145      | 1.000    |
| measurement     | explicit      | 4            | 4        | 1.000    |
| measurement     | paraphrased   | 8            | 8        | 1.000    |
| measurement     | distributed   | 5            | 5        | 1.000    |
| measurement     | complex       | 26           | 26       | 1.000    |
| measurement     | contradictory | 8            | 8        | 1.000    |
| measurement     | all           | 51           | 51       | 1.000    |
| metric          | explicit      | 8            | 8        | 1.000    |
| metric          | paraphrased   | 16           | 16       | 1.000    |
| metric          | distributed   | 12           | 12       | 1.000    |
| metric          | complex       | 25           | 25       | 1.000    |
| metric          | contradictory | 11           | 11       | 1.000    |
| metric          | all           | 72           | 72       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| regex_author_claim@2#b2161f228a8c | 9       | 9               | 9      | 9              |
| regex_condition@2#80486860164a    | 13      | 12              | 13     | 12             |
| regex_measurement@2#9edb306c5b05  | 14      | 13              | 14     | 13             |
| regex_metric@2#67f41f33eff7       | 17      | 10              | 17     | 10             |

Facts no extractor found: condition 18, measurement 38, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 9      | 9              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 9      | 9              |
| regex_condition@2#80486860164a    | condition       | all     | 13      | 30      | 12        | 0.923       | 0.400    | 0.558 | 0.667           | -                      | 13     | 12             |
| regex_condition@2#80486860164a    | all             | all     | 13      | 30      | 12        | 0.923       | 0.400    | 0.558 | 0.667           | -                      | 13     | 12             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 14      | 51      | 13        | 0.929       | 0.255    | 0.400 | 1.000           | 1.000                  | 14     | 13             |
| regex_measurement@2#9edb306c5b05  | all             | all     | 14      | 51      | 13        | 0.929       | 0.255    | 0.400 | 1.000           | -                      | 14     | 13             |
| regex_metric@2#67f41f33eff7       | metric          | all     | 17      | 12      | 10        | 0.588       | 0.833    | 0.690 | 0.900           | -                      | 17     | 10             |
| regex_metric@2#67f41f33eff7       | all             | all     | 17      | 12      | 10        | 0.588       | 0.833    | 0.690 | 0.900           | -                      | 17     | 10             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.097     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.106     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.096     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.094     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.110     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 40      | 3.636       |
| calls            | 55      | 5.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 0.968   | 0.088       |

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
| 11          | 9    | 1    | 0    | 1    | 0.900       | 1.000    |

Screened out wrongly: none
