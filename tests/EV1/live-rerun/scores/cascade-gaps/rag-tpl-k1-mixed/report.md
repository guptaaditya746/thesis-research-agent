# Evaluation of run rag-tpl-k1-mixed on rag-tpl-k1-e922861d

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 30      | 48      | 30        | 1.000       | 0.625    | 0.769 | 1.000           |
| all             | paraphrased   | 10      | 44      | 10        | 1.000       | 0.227    | 0.370 | 1.000           |
| all             | distributed   | 24      | 26      | 24        | 1.000       | 0.923    | 0.960 | 1.000           |
| all             | complex       | 49      | 72      | 48        | 0.980       | 0.667    | 0.793 | 1.000           |
| all             | contradictory | 24      | 37      | 23        | 0.958       | 0.622    | 0.754 | 1.000           |
| all             | all           | 137     | 227     | 135       | 0.985       | 0.595    | 0.742 | 1.000           |
| author_claim    | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 10      | 19      | 10        | 1.000       | 0.526    | 0.690 | 1.000           |
| condition       | paraphrased   | 5       | 17      | 5         | 1.000       | 0.294    | 0.455 | 1.000           |
| condition       | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | complex       | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | contradictory | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 1.000           |
| condition       | all           | 39      | 69      | 39        | 1.000       | 0.565    | 0.722 | 1.000           |
| measurement     | explicit      | 10      | 19      | 10        | 1.000       | 0.526    | 0.690 | 1.000           |
| measurement     | paraphrased   | 0       | 17      | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| measurement     | complex       | 26      | 48      | 25        | 0.962       | 0.521    | 0.676 | 1.000           |
| measurement     | contradictory | 8       | 14      | 7         | 0.875       | 0.500    | 0.636 | 1.000           |
| measurement     | all           | 52      | 107     | 50        | 0.962       | 0.467    | 0.629 | 1.000           |
| metric          | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased   | 0       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               |
| metric          | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 24      | 29      | 24        | 1.000       | 0.828    | 0.906 | 1.000           |

Facts no item matched: 92; items matching no fact: 2.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 10                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 5         | 1.000       |
| paraphrased   | 0                      | -                      | -                         | -                 | -                 | -              | 5         | 0.000       |
| distributed   | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| complex       | 25                     | 0.920                  | 0.920                     | 1.000             | 0.920             | 1.000          | 3         | 0.000       |
| contradictory | 7                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 3         | 1.000       |
| all           | 50                     | 0.960                  | 0.960                     | 1.000             | 0.960             | 1.000          | 20        | 0.600       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 22        | 20           | 0.773                | 0.750          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | evidence-engine | 5         | 5            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | evidence-engine | 5         | 5            | 0.000                | 0.000          | -                   | -              |
| distributed   | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| complex       | evidence-engine | 4         | 3            | 1.000                | 1.000          | 1.000               | -              |
| contradictory | evidence-engine | 4         | 3            | 1.000                | 1.000          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 3    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 1    | 0    | 1    | 1.000       | 0.500    |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | no                   |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.722 [0.65, 0.80] | BCa      |
| metric          | 0.906 [0.76, 0.97] | BCa      |
| measurement     | 0.629 [0.52, 0.77] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.742 [0.66, 0.82] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.773 [0.55, 0.91]   | BCa      | -                     | -               |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 106          | 106      | 1.000    |
| all             | paraphrased   | 93           | 93       | 1.000    |
| all             | distributed   | 60           | 60       | 1.000    |
| all             | complex       | 133          | 133      | 1.000    |
| all             | contradictory | 74           | 74       | 1.000    |
| all             | all           | 466          | 466      | 1.000    |
| author_claim    | explicit      | 10           | 10       | 1.000    |
| author_claim    | paraphrased   | 10           | 10       | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 44           | 44       | 1.000    |
| condition       | explicit      | 48           | 48       | 1.000    |
| condition       | paraphrased   | 44           | 44       | 1.000    |
| condition       | distributed   | 27           | 27       | 1.000    |
| condition       | complex       | 41           | 41       | 1.000    |
| condition       | contradictory | 39           | 39       | 1.000    |
| condition       | all           | 199          | 199      | 1.000    |
| measurement     | explicit      | 19           | 19       | 1.000    |
| measurement     | paraphrased   | 17           | 17       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 48           | 48       | 1.000    |
| measurement     | contradictory | 14           | 14       | 1.000    |
| measurement     | all           | 107          | 107      | 1.000    |
| metric          | explicit      | 29           | 29       | 1.000    |
| metric          | paraphrased   | 22           | 22       | 1.000    |
| metric          | distributed   | 16           | 16       | 1.000    |
| metric          | complex       | 36           | 36       | 1.000    |
| metric          | contradictory | 13           | 13       | 1.000    |
| metric          | all           | 116          | 116      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 0       | 0               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 16      | 16              | 15     | 15             |
| llm_measurement@1#5212fc43026f    | 29      | 29              | 24     | 24             |
| llm_metric@1#1ca12a572ef8         | 1       | 1               | 1      | 1              |
| regex_author_claim@2#b2161f228a8c | 22      | 22              | 22     | 22             |
| regex_condition@2#80486860164a    | 24      | 24              | 23     | 23             |
| regex_measurement@2#9edb306c5b05  | 28      | 26              | 23     | 21             |
| regex_metric@2#67f41f33eff7       | 23      | 23              | 23     | 23             |

Facts no extractor found: condition 30, measurement 57, metric 5

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | all             | all     | 0       | 227     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 16      | 44      | 16        | 1.000       | 0.364    | 0.533 | 1.000           | -                      | 15     | 15             |
| llm_condition@1#134ab1a38338      | all             | all     | 16      | 44      | 16        | 1.000       | 0.364    | 0.533 | 1.000           | -                      | 15     | 15             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 29      | 71      | 29        | 1.000       | 0.408    | 0.580 | 1.000           | 1.000                  | 24     | 24             |
| llm_measurement@1#5212fc43026f    | all             | all     | 29      | 71      | 29        | 1.000       | 0.408    | 0.580 | 1.000           | -                      | 24     | 24             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 22     | 22             |
| regex_author_claim@2#b2161f228a8c | all             | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 22     | 22             |
| regex_condition@2#80486860164a    | condition       | all     | 24      | 69      | 24        | 1.000       | 0.348    | 0.516 | 1.000           | -                      | 23     | 23             |
| regex_condition@2#80486860164a    | all             | all     | 24      | 69      | 24        | 1.000       | 0.348    | 0.516 | 1.000           | -                      | 23     | 23             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 28      | 107     | 26        | 0.929       | 0.243    | 0.385 | 1.000           | 0.923                  | 23     | 21             |
| regex_measurement@2#9edb306c5b05  | all             | all     | 28      | 107     | 26        | 0.929       | 0.243    | 0.385 | 1.000           | -                      | 23     | 21             |
| regex_metric@2#67f41f33eff7       | metric          | all     | 23      | 29      | 23        | 1.000       | 0.793    | 0.885 | 1.000           | -                      | 23     | 23             |
| regex_metric@2#67f41f33eff7       | all             | all     | 23      | 29      | 23        | 1.000       | 0.793    | 0.885 | 1.000           | -                      | 23     | 23             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#134ab1a38338      | 14      | 25            | 24038          | 1849            | 11.197    |
| llm_measurement@1#5212fc43026f    | 14      | 28            | 32245          | 5097            | 25.658    |
| llm_metric@1#1ca12a572ef8         | 1       | 1             | 998            | 92              | 0.007     |
| llm_screen@1#6bec6abaf6a0         | 22      | 22            | 16777          | 1732            | 0.142     |
| regex_author_claim@2#b2161f228a8c | 22      | 0             | 0              | 0               | 0.141     |
| regex_condition@2#80486860164a    | 22      | 0             | 0              | 0               | 0.142     |
| regex_measurement@2#9edb306c5b05  | 22      | 0             | 0              | 0               | 0.143     |
| regex_metric@2#67f41f33eff7       | 22      | 0             | 0              | 0               | 0.141     |
| regex_screen@1#8301b6896dc3       | 22      | 0             | 0              | 0               | 0.144     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 155     | 7.045       |
| calls            | 161     | 7.318       |
| input_tokens     | 74058   | 3366.273    |
| made_model_calls | 11      | 0.500       |
| model_calls      | 76      | 3.455       |
| output_tokens    | 8770    | 398.636     |
| seconds          | 38.919  | 1.769       |

## Funnel

Strategy `gaps` over 22 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.318          |
| model_calls   | 3.455          |
| input_tokens  | 3366.273       |
| output_tokens | 398.636        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 3           |
| 1               | 12          |
| exhausted       | 7           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 22          | 22   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
