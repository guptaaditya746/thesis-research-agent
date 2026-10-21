# Evaluation of run rag-llm-s1-paraphrased on rag-llm-s1-404c0b6d

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: paraphrased

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | paraphrased | 102     | 88      | 81        | 0.794       | 0.920    | 0.853 | 0.963           |
| all             | all         | 102     | 88      | 81        | 0.794       | 0.920    | 0.853 | 0.963           |
| author_claim    | paraphrased | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased | 41      | 33      | 30        | 0.732       | 0.909    | 0.811 | 1.000           |
| condition       | all         | 41      | 33      | 30        | 0.732       | 0.909    | 0.811 | 1.000           |
| measurement     | paraphrased | 31      | 33      | 31        | 1.000       | 0.939    | 0.969 | 1.000           |
| measurement     | all         | 31      | 33      | 31        | 1.000       | 0.939    | 0.969 | 1.000           |
| metric          | paraphrased | 19      | 11      | 9         | 0.474       | 0.818    | 0.600 | 0.667           |
| metric          | all         | 19      | 11      | 9         | 0.474       | 0.818    | 0.600 | 0.667           |

Facts no item matched: 7; items matching no fact: 21.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| paraphrased | 31                     | 0.774                  | 0.903                     | 0.871             | 0.903             | 0.871          | 11        | 0.818       |
| all         | 31                     | 0.774                  | 0.903                     | 0.871             | 0.903             | 0.871          | 11        | 0.818       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 11        | 11           | 0.818                | 0.818          | 1.000               | -              |
| rag-baseline    | mixed   | mixed      | yes             | 11        | 11           | 0.455                | 0.455          | 1.000               | 1.000          |
| agent-baseline  | mixed   | mixed      | yes             | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| paraphrased | agent-baseline  | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| paraphrased | evidence-engine | 11        | 11           | 0.818                | 0.818          | 1.000               | -              |
| paraphrased | rag-baseline    | 11        | 11           | 0.455                | 0.455          | 1.000               | 1.000          |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
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
| condition       | 0.811 [0.70, 0.89] | BCa      |
| metric          | 0.600 [0.44, 0.76] | BCa      |
| measurement     | 0.969 [0.81, 1.00] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.853 [0.81, 0.90] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.818 [0.50, 1.00]   | BCa      | -                     | -               |
| rag-baseline    | 0.455 [0.18, 0.73]   | BCa      | 0.364 [0.09, 0.64]    | BCa             |
| agent-baseline  | 1.000 [n/a]          | -        | -0.182 [-0.50, 0.00]  | BCa             |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | paraphrased | 257          | 257      | 1.000    |
| all             | all         | 257          | 257      | 1.000    |
| author_claim    | paraphrased | 22           | 22       | 1.000    |
| author_claim    | all         | 22           | 22       | 1.000    |
| condition       | paraphrased | 138          | 138      | 1.000    |
| condition       | all         | 138          | 138      | 1.000    |
| measurement     | paraphrased | 33           | 33       | 1.000    |
| measurement     | all         | 33           | 33       | 1.000    |
| metric          | paraphrased | 64           | 64       | 1.000    |
| metric          | all         | 64           | 64       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 11      | 11              | 0      | 0              |
| llm_condition@1#134ab1a38338      | 33      | 30              | 33     | 30             |
| llm_measurement@1#5212fc43026f    | 31      | 31              | 31     | 31             |
| llm_metric@1#1ca12a572ef8         | 6       | 6               | 6      | 6              |
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 0      | 0              |
| regex_condition@2#80486860164a    | 8       | 0               | 8      | 0              |
| regex_measurement@2#9edb306c5b05  | 0       | 0               | 0      | 0              |
| regex_metric@2#67f41f33eff7       | 13      | 3               | 13     | 3              |

Facts no extractor found: condition 3, measurement 2, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 33      | 33      | 30        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 33     | 30             |
| llm_condition@1#134ab1a38338      | all             | all     | 33      | 33      | 30        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 33     | 30             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 31      | 33      | 31        | 1.000       | 0.939    | 0.969 | 1.000           | 0.774                  | 31     | 31             |
| llm_measurement@1#5212fc43026f    | all             | all     | 31      | 33      | 31        | 1.000       | 0.939    | 0.969 | 1.000           | -                      | 31     | 31             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 6       | 11      | 6         | 1.000       | 0.545    | 0.706 | 1.000           | -                      | 6      | 6              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 6       | 11      | 6         | 1.000       | 0.545    | 0.706 | 1.000           | -                      | 6      | 6              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 8       | 33      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 8      | 0              |
| regex_condition@2#80486860164a    | all             | all     | 8       | 33      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 8      | 0              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 0       | 33      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 0       | 33      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 13      | 11      | 3         | 0.231       | 0.273    | 0.250 | 0.000           | -                      | 13     | 3              |
| regex_metric@2#67f41f33eff7       | all             | all     | 13      | 11      | 3         | 0.231       | 0.273    | 0.250 | 0.000           | -                      | 13     | 3              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 11      | 11            | 13483          | 1329            | 30.693    |
| llm_condition@1#134ab1a38338      | 11      | 20            | 26488          | 3670            | 76.451    |
| llm_measurement@1#5212fc43026f    | 11      | 22            | 35517          | 7578            | 153.930   |
| llm_metric@1#1ca12a572ef8         | 11      | 11            | 14627          | 619             | 17.006    |
| llm_screen@1#6bec6abaf6a0         | 11      | 11            | 12262          | 861             | 21.354    |
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.079     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.077     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.156     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.075     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.079     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 56      | 5.091       |
| calls            | 110     | 10.000      |
| input_tokens     | 102377  | 9307.000    |
| made_model_calls | 61      | 5.545       |
| model_calls      | 75      | 6.818       |
| output_tokens    | 14057   | 1277.909    |
| seconds          | 300.604 | 27.328      |

## Funnel

Strategy `all` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.818          |
| input_tokens  | 9307.000       |
| output_tokens | 1277.909       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 11          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
