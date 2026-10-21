# Evaluation of run rag-tpl-s1-contradictory on rag-tpl-s1-56b0bc02

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 118     | 162     | 111       | 0.941       | 0.685    | 0.793 | 1.000           |
| all             | all           | 118     | 162     | 111       | 0.941       | 0.685    | 0.793 | 1.000           |
| author_claim    | contradictory | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           |
| author_claim    | all           | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           |
| condition       | contradictory | 38      | 61      | 38        | 1.000       | 0.623    | 0.768 | 1.000           |
| condition       | all           | 38      | 61      | 38        | 1.000       | 0.623    | 0.768 | 1.000           |
| measurement     | contradictory | 42      | 61      | 35        | 0.833       | 0.574    | 0.680 | 1.000           |
| measurement     | all           | 42      | 61      | 35        | 0.833       | 0.574    | 0.680 | 1.000           |
| metric          | contradictory | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           |
| metric          | all           | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           |

Facts no item matched: 51; items matching no fact: 7.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 35                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.800       |
| all           | 35                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.800       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.800                | 0.900          | 0.889               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| contradictory | evidence-engine | 20        | 20           | 0.800                | 0.900          | 0.889               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 16   | 0    | 4    | 1.000       | 0.800    |
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
| condition       | 0.768 [0.69, 0.84] | BCa      |
| metric          | 0.974 [0.86, 1.00] | BCa      |
| measurement     | 0.680 [0.60, 0.76] | BCa      |
| author_claim    | 0.974 [0.86, 1.00] | BCa      |
| all             | 0.793 [0.71, 0.85] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.800 [0.55, 0.95]   | BCa      | -                     | -               |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | contradictory | 343          | 327      | 0.953    |
| all             | all           | 343          | 327      | 0.953    |
| author_claim    | contradictory | 40           | 38       | 0.950    |
| author_claim    | all           | 40           | 38       | 0.950    |
| condition       | contradictory | 172          | 164      | 0.953    |
| condition       | all           | 172          | 164      | 0.953    |
| measurement     | contradictory | 61           | 58       | 0.951    |
| measurement     | all           | 61           | 58       | 0.951    |
| metric          | contradictory | 70           | 67       | 0.957    |
| metric          | all           | 70           | 67       | 0.957    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 0       | 0               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 12      | 12              | 12     | 12             |
| llm_measurement@1#5212fc43026f    | 23      | 23              | 16     | 16             |
| llm_metric@1#1ca12a572ef8         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#b2161f228a8c | 19      | 19              | 19     | 19             |
| regex_condition@2#80486860164a    | 26      | 26              | 26     | 26             |
| regex_measurement@2#9edb306c5b05  | 26      | 19              | 19     | 12             |
| regex_metric@2#67f41f33eff7       | 17      | 17              | 17     | 17             |

Facts no extractor found: author_claim 1, condition 23, measurement 26, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | all             | all     | 0       | 162     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 12      | 30      | 12        | 1.000       | 0.400    | 0.571 | 1.000           | -                      | 12     | 12             |
| llm_condition@1#134ab1a38338      | all             | all     | 12      | 30      | 12        | 1.000       | 0.400    | 0.571 | 1.000           | -                      | 12     | 12             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 23      | 36      | 23        | 1.000       | 0.639    | 0.780 | 1.000           | 1.000                  | 16     | 16             |
| llm_measurement@1#5212fc43026f    | all             | all     | 23      | 36      | 23        | 1.000       | 0.639    | 0.780 | 1.000           | -                      | 16     | 16             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 19      | 19      | 19        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 19     | 19             |
| regex_author_claim@2#b2161f228a8c | all             | all     | 19      | 19      | 19        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 19     | 19             |
| regex_condition@2#80486860164a    | condition       | all     | 26      | 58      | 26        | 1.000       | 0.448    | 0.619 | 1.000           | -                      | 26     | 26             |
| regex_condition@2#80486860164a    | all             | all     | 26      | 58      | 26        | 1.000       | 0.448    | 0.619 | 1.000           | -                      | 26     | 26             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 26      | 58      | 19        | 0.731       | 0.328    | 0.452 | 1.000           | 1.000                  | 19     | 12             |
| regex_measurement@2#9edb306c5b05  | all             | all     | 26      | 58      | 19        | 0.731       | 0.328    | 0.452 | 1.000           | -                      | 19     | 12             |
| regex_metric@2#67f41f33eff7       | metric          | all     | 17      | 19      | 17        | 1.000       | 0.895    | 0.944 | 1.000           | -                      | 17     | 17             |
| regex_metric@2#67f41f33eff7       | all             | all     | 17      | 19      | 17        | 1.000       | 0.895    | 0.944 | 1.000           | -                      | 17     | 17             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#134ab1a38338      | 10      | 19            | 16943          | 1423            | 41.913    |
| llm_measurement@1#5212fc43026f    | 11      | 22            | 23470          | 3598            | 95.849    |
| llm_metric@1#1ca12a572ef8         | 2       | 4             | 3762           | 269             | 8.044     |
| llm_screen@1#6bec6abaf6a0         | 20      | 20            | 14169          | 1434            | 0.134     |
| regex_author_claim@2#b2161f228a8c | 19      | 0             | 0              | 0               | 0.123     |
| regex_condition@2#80486860164a    | 19      | 0             | 0              | 0               | 0.128     |
| regex_measurement@2#9edb306c5b05  | 19      | 0             | 0              | 0               | 0.128     |
| regex_metric@2#67f41f33eff7       | 19      | 0             | 0              | 0               | 0.130     |
| regex_screen@1#8301b6896dc3       | 20      | 0             | 0              | 0               | 0.138     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 116     | 5.800       |
| calls            | 139     | 6.950       |
| input_tokens     | 58344   | 2917.200    |
| made_model_calls | 45      | 2.250       |
| model_calls      | 65      | 3.250       |
| output_tokens    | 6724    | 336.200     |
| seconds          | 147.699 | 7.385       |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 6.950          |
| model_calls   | 3.250          |
| input_tokens  | 2917.200       |
| output_tokens | 336.200        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 7           |
| 1               | 11          |
| exhausted       | 1           |
| skipped         | 1           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 19   | 0    | 1    | 0    | 1.000       | 0.950    |

Screened out wrongly: S013
