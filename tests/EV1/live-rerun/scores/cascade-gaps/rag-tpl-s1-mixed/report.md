# Evaluation of run rag-tpl-s1-mixed on rag-tpl-s1-6162b495

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 24      | 38      | 24        | 1.000       | 0.632    | 0.774 | 1.000           |
| all             | paraphrased   | 8       | 34      | 8         | 1.000       | 0.235    | 0.381 | 1.000           |
| all             | distributed   | 24      | 26      | 24        | 1.000       | 0.923    | 0.960 | 1.000           |
| all             | complex       | 50      | 74      | 49        | 0.980       | 0.662    | 0.790 | 1.000           |
| all             | contradictory | 26      | 38      | 24        | 0.923       | 0.632    | 0.750 | 1.000           |
| all             | all           | 132     | 210     | 129       | 0.977       | 0.614    | 0.754 | 1.000           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 1.000           |
| condition       | paraphrased   | 4       | 13      | 4         | 1.000       | 0.308    | 0.471 | 1.000           |
| condition       | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | complex       | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | contradictory | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 1.000           |
| condition       | all           | 36      | 61      | 36        | 1.000       | 0.590    | 0.742 | 1.000           |
| measurement     | explicit      | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 1.000           |
| measurement     | paraphrased   | 0       | 13      | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| measurement     | complex       | 27      | 50      | 26        | 0.963       | 0.520    | 0.675 | 1.000           |
| measurement     | contradictory | 10      | 15      | 8         | 0.800       | 0.533    | 0.640 | 1.000           |
| measurement     | all           | 53      | 102     | 50        | 0.943       | 0.490    | 0.645 | 1.000           |
| metric          | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased   | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               |
| metric          | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           |

Facts no item matched: 81; items matching no fact: 3.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| paraphrased   | 0                      | -                      | -                         | -                 | -                 | -              | 4         | 0.000       |
| distributed   | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| complex       | 26                     | 0.923                  | 0.923                     | 1.000             | 0.923             | 1.000          | 4         | 0.000       |
| contradictory | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| all           | 50                     | 0.960                  | 0.960                     | 1.000             | 0.960             | 1.000          | 20        | 0.600       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.800                | 0.800          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | evidence-engine | 4         | 4            | 0.000                | 0.000          | -                   | -              |
| distributed   | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| complex       | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| contradictory | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 4    | 0    | 0    | 1.000       | 1.000    |
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
| condition       | 0.742 [0.67, 0.82] | BCa      |
| metric          | 0.920 [0.80, 0.98] | BCa      |
| measurement     | 0.645 [0.54, 0.79] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.754 [0.68, 0.83] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.800 [0.60, 0.95]   | BCa      | -                     | -               |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 84           | 84       | 1.000    |
| all             | paraphrased   | 72           | 72       | 1.000    |
| all             | distributed   | 60           | 60       | 1.000    |
| all             | complex       | 138          | 138      | 1.000    |
| all             | contradictory | 77           | 77       | 1.000    |
| all             | all           | 431          | 431      | 1.000    |
| author_claim    | explicit      | 8            | 8        | 1.000    |
| author_claim    | paraphrased   | 8            | 8        | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
| condition       | explicit      | 38           | 38       | 1.000    |
| condition       | paraphrased   | 34           | 34       | 1.000    |
| condition       | distributed   | 27           | 27       | 1.000    |
| condition       | complex       | 43           | 43       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 182          | 182      | 1.000    |
| measurement     | explicit      | 15           | 15       | 1.000    |
| measurement     | paraphrased   | 13           | 13       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 50           | 50       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 102          | 102      | 1.000    |
| metric          | explicit      | 23           | 23       | 1.000    |
| metric          | paraphrased   | 17           | 17       | 1.000    |
| metric          | distributed   | 16           | 16       | 1.000    |
| metric          | complex       | 37           | 37       | 1.000    |
| metric          | contradictory | 14           | 14       | 1.000    |
| metric          | all           | 107          | 107      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 0       | 0               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 14      | 14              | 13     | 13             |
| llm_measurement@1#5212fc43026f    | 27      | 27              | 22     | 22             |
| llm_metric@1#1ca12a572ef8         | 1       | 1               | 1      | 1              |
| regex_author_claim@2#b2161f228a8c | 20      | 20              | 20     | 20             |
| regex_condition@2#80486860164a    | 23      | 23              | 22     | 22             |
| regex_measurement@2#9edb306c5b05  | 31      | 28              | 26     | 23             |
| regex_metric@2#67f41f33eff7       | 22      | 22              | 22     | 22             |

Facts no extractor found: condition 25, measurement 52, metric 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | all             | all     | 0       | 210     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 14      | 36      | 14        | 1.000       | 0.389    | 0.560 | 1.000           | -                      | 13     | 13             |
| llm_condition@1#134ab1a38338      | all             | all     | 14      | 36      | 14        | 1.000       | 0.389    | 0.560 | 1.000           | -                      | 13     | 13             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 27      | 66      | 27        | 1.000       | 0.409    | 0.581 | 1.000           | 1.000                  | 22     | 22             |
| llm_measurement@1#5212fc43026f    | all             | all     | 27      | 66      | 27        | 1.000       | 0.409    | 0.581 | 1.000           | -                      | 22     | 22             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#b2161f228a8c | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#80486860164a    | condition       | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 1.000           | -                      | 22     | 22             |
| regex_condition@2#80486860164a    | all             | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 1.000           | -                      | 22     | 22             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 31      | 102     | 28        | 0.903       | 0.275    | 0.421 | 1.000           | 0.929                  | 26     | 23             |
| regex_measurement@2#9edb306c5b05  | all             | all     | 31      | 102     | 28        | 0.903       | 0.275    | 0.421 | 1.000           | -                      | 26     | 23             |
| regex_metric@2#67f41f33eff7       | metric          | all     | 22      | 27      | 22        | 1.000       | 0.815    | 0.898 | 1.000           | -                      | 22     | 22             |
| regex_metric@2#67f41f33eff7       | all             | all     | 22      | 27      | 22        | 1.000       | 0.815    | 0.898 | 1.000           | -                      | 22     | 22             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#134ab1a38338      | 12      | 22            | 21217          | 1627            | 16.639    |
| llm_measurement@1#5212fc43026f    | 12      | 24            | 28033          | 4618            | 0.080     |
| llm_metric@1#1ca12a572ef8         | 1       | 1             | 998            | 92              | 0.006     |
| llm_screen@1#6bec6abaf6a0         | 20      | 20            | 15335          | 1563            | 0.129     |
| regex_author_claim@2#b2161f228a8c | 20      | 0             | 0              | 0               | 0.127     |
| regex_condition@2#80486860164a    | 20      | 0             | 0              | 0               | 0.128     |
| regex_measurement@2#9edb306c5b05  | 20      | 0             | 0              | 0               | 0.131     |
| regex_metric@2#67f41f33eff7       | 20      | 0             | 0              | 0               | 0.133     |
| regex_screen@1#8301b6896dc3       | 20      | 0             | 0              | 0               | 0.130     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 141     | 7.050       |
| calls            | 145     | 7.250       |
| input_tokens     | 65583   | 3279.150    |
| made_model_calls | 8       | 0.400       |
| model_calls      | 67      | 3.350       |
| output_tokens    | 7900    | 395.000     |
| seconds          | 18.594  | 0.930       |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.250          |
| model_calls   | 3.350          |
| input_tokens  | 3279.150       |
| output_tokens | 395.000        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 4           |
| 1               | 12          |
| exhausted       | 4           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
