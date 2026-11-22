# Evaluation of run rag-llm-k1-mixed on rag-llm-k1-961f46a3

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 6       | 10      | 5         | 0.833       | 0.500    | 0.625 | 0.800           |
| all             | paraphrased   | 20      | 20      | 19        | 0.950       | 0.950    | 0.950 | 0.947           |
| all             | distributed   | 15      | 14      | 12        | 0.800       | 0.857    | 0.828 | 1.000           |
| all             | complex       | 27      | 38      | 24        | 0.889       | 0.632    | 0.738 | 0.958           |
| all             | contradictory | 14      | 20      | 12        | 0.857       | 0.600    | 0.706 | 1.000           |
| all             | all           | 82      | 102     | 72        | 0.878       | 0.706    | 0.783 | 0.958           |
| author_claim    | explicit      | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 0.500           |
| condition       | paraphrased   | 8       | 8       | 8         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed   | 5       | 5       | 4         | 0.800       | 0.800    | 0.800 | 1.000           |
| condition       | complex       | 5       | 5       | 4         | 0.800       | 0.800    | 0.800 | 0.750           |
| condition       | contradictory | 4       | 8       | 4         | 1.000       | 0.500    | 0.667 | 1.000           |
| condition       | all           | 24      | 30      | 22        | 0.917       | 0.733    | 0.815 | 0.909           |
| measurement     | explicit      | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 1.000           |
| measurement     | paraphrased   | 8       | 8       | 8         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | distributed   | 4       | 5       | 4         | 1.000       | 0.800    | 0.889 | 1.000           |
| measurement     | complex       | 14      | 26      | 13        | 0.929       | 0.500    | 0.650 | 1.000           |
| measurement     | contradictory | 5       | 8       | 4         | 0.800       | 0.500    | 0.615 | 1.000           |
| measurement     | all           | 33      | 51      | 31        | 0.939       | 0.608    | 0.738 | 1.000           |
| metric          | explicit      | 1       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               |
| metric          | paraphrased   | 2       | 2       | 1         | 0.500       | 0.500    | 0.500 | 0.000           |
| metric          | distributed   | 4       | 2       | 2         | 0.500       | 1.000    | 0.667 | 1.000           |
| metric          | complex       | 6       | 5       | 5         | 0.833       | 1.000    | 0.909 | 1.000           |
| metric          | contradictory | 3       | 2       | 2         | 0.667       | 1.000    | 0.800 | 1.000           |
| metric          | all           | 16      | 12      | 10        | 0.625       | 0.833    | 0.714 | 0.900           |

Facts no item matched: 30; items matching no fact: 10.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 2                      | 0.000                  | 1.000                     | 0.000             | 1.000             | 0.000          | 1         | 1.000       |
| paraphrased   | 8                      | 0.500                  | 1.000                     | 0.500             | 1.000             | 0.500          | 2         | 1.000       |
| distributed   | 4                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.500          | 2         | 1.000       |
| complex       | 13                     | 1.000                  | 1.000                     | 1.000             | 0.846             | 1.000          | 2         | 0.500       |
| contradictory | 4                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 2         | 1.000       |
| all           | 31                     | 0.806                  | 1.000                     | 0.806             | 0.935             | 0.742          | 9         | 0.889       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 11        | 9            | 0.818                | 1.000          | 0.778               | -              |
| rag-baseline    | mixed   | mixed      | yes             | 11        | 9            | 0.545                | 0.556          | 0.800               | 1.000          |
| agent-baseline  | mixed   | mixed      | yes             | 11        | 9            | 0.818                | 1.000          | 0.778               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | agent-baseline  | 1         | yes          | 1.000                | 1.000          | 1.000               | -              |
| explicit      | evidence-engine | 1         | yes          | 0.000                | 1.000          | 0.000               | -              |
| explicit      | rag-baseline    | 1         | yes          | 0.000                | 0.000          | -                   | -              |
| paraphrased   | agent-baseline  | 2         | 2            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | evidence-engine | 2         | 2            | 0.500                | 1.000          | 0.500               | -              |
| paraphrased   | rag-baseline    | 2         | 2            | 0.500                | 0.500          | 1.000               | 1.000          |
| distributed   | agent-baseline  | 3         | 2            | 1.000                | 1.000          | 1.000               | -              |
| distributed   | evidence-engine | 3         | 2            | 1.000                | 1.000          | 1.000               | -              |
| distributed   | rag-baseline    | 3         | 2            | 0.667                | 0.500          | 1.000               | 1.000          |
| complex       | agent-baseline  | 3         | 2            | 1.000                | 1.000          | 1.000               | -              |
| complex       | evidence-engine | 3         | 2            | 1.000                | 1.000          | 1.000               | -              |
| complex       | rag-baseline    | 3         | 2            | 1.000                | 1.000          | 1.000               | 1.000          |
| contradictory | agent-baseline  | 2         | 2            | 0.000                | 1.000          | 0.000               | -              |
| contradictory | evidence-engine | 2         | 2            | 1.000                | 1.000          | 1.000               | -              |
| contradictory | rag-baseline    | 2         | 2            | 0.000                | 0.500          | 0.000               | 1.000          |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 2    | 2    | 0    | 0.500       | 1.000    |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 1    | 0    | 0    | 1.000       | 1.000    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.815 [0.73, 0.92] | BCa      |
| metric          | 0.714 [0.44, 0.88] | BCa      |
| measurement     | 0.738 [0.62, 0.87] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.783 [0.71, 0.87] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.818 [0.45, 1.00]   | BCa      | -                     | -               |
| rag-baseline    | 0.545 [0.27, 0.82]   | BCa      | 0.273 [0.09, 0.64]    | BCa             |
| agent-baseline  | 0.818 [0.45, 1.00]   | BCa      | 0.000 [-0.36, 0.36]   | BCa             |

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
| llm_author_claim@1#fefdf4416c50   | 0       | 0               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 12      | 12              | 12     | 12             |
| llm_measurement@1#5212fc43026f    | 21      | 21              | 19     | 19             |
| llm_metric@1#1ca12a572ef8         | 0       | 0               | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | 9       | 9               | 9      | 9              |
| regex_condition@2#80486860164a    | 12      | 10              | 12     | 10             |
| regex_measurement@2#9edb306c5b05  | 14      | 12              | 12     | 10             |
| regex_metric@2#67f41f33eff7       | 16      | 10              | 16     | 10             |

Facts no extractor found: condition 8, measurement 20, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | all             | all     | 0       | 102     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 12     | 12             |
| llm_condition@1#134ab1a38338      | all             | all     | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 12     | 12             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 21      | 43      | 21        | 1.000       | 0.488    | 0.656 | 1.000           | 0.714                  | 19     | 19             |
| llm_measurement@1#5212fc43026f    | all             | all     | 21      | 43      | 21        | 1.000       | 0.488    | 0.656 | 1.000           | -                      | 19     | 19             |
| llm_metric@1#1ca12a572ef8         | all             | all     | 0       | 102     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 9      | 9              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 9      | 9              |
| regex_condition@2#80486860164a    | condition       | all     | 12      | 30      | 10        | 0.833       | 0.333    | 0.476 | 0.800           | -                      | 12     | 10             |
| regex_condition@2#80486860164a    | all             | all     | 12      | 30      | 10        | 0.833       | 0.333    | 0.476 | 0.800           | -                      | 12     | 10             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 14      | 51      | 12        | 0.857       | 0.235    | 0.369 | 1.000           | 1.000                  | 12     | 10             |
| regex_measurement@2#9edb306c5b05  | all             | all     | 14      | 51      | 12        | 0.857       | 0.235    | 0.369 | 1.000           | -                      | 12     | 10             |
| regex_metric@2#67f41f33eff7       | metric          | all     | 16      | 12      | 10        | 0.625       | 0.833    | 0.714 | 0.900           | -                      | 16     | 10             |
| regex_metric@2#67f41f33eff7       | all             | all     | 16      | 12      | 10        | 0.625       | 0.833    | 0.714 | 0.900           | -                      | 16     | 10             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#134ab1a38338      | 4       | 7             | 8814           | 1229            | 12.663    |
| llm_measurement@1#5212fc43026f    | 7       | 14            | 21430          | 3907            | 24.044    |
| llm_screen@1#6bec6abaf6a0         | 10      | 10            | 10020          | 793             | 0.064     |
| regex_author_claim@2#b2161f228a8c | 9       | 0             | 0              | 0               | 0.058     |
| regex_condition@2#80486860164a    | 9       | 0             | 0              | 0               | 0.059     |
| regex_measurement@2#9edb306c5b05  | 9       | 0             | 0              | 0               | 0.059     |
| regex_metric@2#67f41f33eff7       | 9       | 0             | 0              | 0               | 0.060     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.074     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 66      | 6.000       |
| calls            | 68      | 6.182       |
| input_tokens     | 40264   | 3660.364    |
| made_model_calls | 4       | 0.364       |
| model_calls      | 31      | 2.818       |
| output_tokens    | 5929    | 539.000     |
| seconds          | 37.638  | 3.422       |

## Funnel

Strategy `gaps` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 6.182          |
| model_calls   | 2.818          |
| input_tokens  | 3660.364       |
| output_tokens | 539.000        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 2           |
| 1               | 7           |
| skipped         | 2           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 9    | 0    | 0    | 2    | 1.000       | 1.000    |

Screened out wrongly: none
