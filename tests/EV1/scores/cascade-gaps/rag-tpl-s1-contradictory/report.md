# Evaluation of run rag-tpl-s1-contradictory on rag-tpl-s1-56b0bc02

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 117     | 162     | 109       | 0.932       | 0.673    | 0.781 | 1.000           |
| all             | all           | 117     | 162     | 109       | 0.932       | 0.673    | 0.781 | 1.000           |
| author_claim    | contradictory | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |
| author_claim    | all           | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |
| condition       | contradictory | 38      | 61      | 38        | 1.000       | 0.623    | 0.768 | 1.000           |
| condition       | all           | 38      | 61      | 38        | 1.000       | 0.623    | 0.768 | 1.000           |
| measurement     | contradictory | 43      | 61      | 35        | 0.814       | 0.574    | 0.673 | 1.000           |
| measurement     | all           | 43      | 61      | 35        | 0.814       | 0.574    | 0.673 | 1.000           |
| metric          | contradictory | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |
| metric          | all           | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |

Facts no item matched: 53; items matching no fact: 8.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 35                     | 0.971                  | 0.971                     | 1.000             | 0.971             | 1.000          | 0         | -           |
| all           | 35                     | 0.971                  | 0.971                     | 1.000             | 0.971             | 1.000          | 0         | -           |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.750                | 0.850          | 0.882               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| contradictory | evidence-engine | 20        | 20           | 0.750                | 0.850          | 0.882               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 15   | 0    | 0.000       | -        |
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
| condition       | 0.768 [0.67, 0.85] | BCa      |
| metric          | 0.947 [0.82, 1.00] | BCa      |
| measurement     | 0.673 [0.59, 0.76] | BCa      |
| author_claim    | 0.947 [0.82, 1.00] | BCa      |
| all             | 0.781 [0.69, 0.84] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.750 [0.50, 0.90]   | BCa      | -                     | -               |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | contradictory | 343          | 314      | 0.915    |
| all             | all           | 343          | 314      | 0.915    |
| author_claim    | contradictory | 40           | 36       | 0.900    |
| author_claim    | all           | 40           | 36       | 0.900    |
| condition       | contradictory | 172          | 158      | 0.919    |
| condition       | all           | 172          | 158      | 0.919    |
| measurement     | contradictory | 61           | 56       | 0.918    |
| measurement     | all           | 61           | 56       | 0.918    |
| metric          | contradictory | 70           | 64       | 0.914    |
| metric          | all           | 70           | 64       | 0.914    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | 0       | 0               | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | 14      | 14              | 13     | 13             |
| llm_measurement@1#957820ab7bd1    | 23      | 22              | 18     | 17             |
| llm_metric@1#6186147fa702         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#75e32ebcdf68 | 18      | 18              | 18     | 18             |
| regex_condition@2#a0c64d9b6305    | 25      | 25              | 24     | 24             |
| regex_measurement@2#b984f16ded3b  | 25      | 18              | 20     | 13             |
| regex_metric@2#94a3000eacae       | 16      | 16              | 16     | 16             |

Facts no extractor found: author_claim 2, condition 23, measurement 26, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | all             | all     | 0       | 162     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | condition       | all     | 14      | 28      | 14        | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 13     | 13             |
| llm_condition@1#f75a85c10bd4      | all             | all     | 14      | 28      | 14        | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 13     | 13             |
| llm_measurement@1#957820ab7bd1    | measurement     | all     | 23      | 34      | 22        | 0.957       | 0.647    | 0.772 | 1.000           | 1.000                  | 18     | 17             |
| llm_measurement@1#957820ab7bd1    | all             | all     | 23      | 34      | 22        | 0.957       | 0.647    | 0.772 | 1.000           | -                      | 18     | 17             |
| llm_metric@1#6186147fa702         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#6186147fa702         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#75e32ebcdf68 | author_claim    | all     | 18      | 18      | 18        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 18     | 18             |
| regex_author_claim@2#75e32ebcdf68 | all             | all     | 18      | 18      | 18        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 18     | 18             |
| regex_condition@2#a0c64d9b6305    | condition       | all     | 25      | 56      | 25        | 1.000       | 0.446    | 0.617 | 1.000           | -                      | 24     | 24             |
| regex_condition@2#a0c64d9b6305    | all             | all     | 25      | 56      | 25        | 1.000       | 0.446    | 0.617 | 1.000           | -                      | 24     | 24             |
| regex_measurement@2#b984f16ded3b  | measurement     | all     | 25      | 56      | 18        | 0.720       | 0.321    | 0.444 | 1.000           | 0.944                  | 20     | 13             |
| regex_measurement@2#b984f16ded3b  | all             | all     | 25      | 56      | 18        | 0.720       | 0.321    | 0.444 | 1.000           | -                      | 20     | 13             |
| regex_metric@2#94a3000eacae       | metric          | all     | 16      | 18      | 16        | 1.000       | 0.889    | 0.941 | 1.000           | -                      | 16     | 16             |
| regex_metric@2#94a3000eacae       | all             | all     | 16      | 18      | 16        | 1.000       | 0.889    | 0.941 | 1.000           | -                      | 16     | 16             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#f75a85c10bd4      | 9       | 17            | 15494          | 1600            | 44.904    |
| llm_measurement@1#957820ab7bd1    | 10      | 20            | 21719          | 3574            | 94.619    |
| llm_metric@1#6186147fa702         | 2       | 4             | 3762           | 270             | 8.066     |
| llm_screen@1#a1013a736e72         | 20      | 20            | 14169          | 1453            | 41.311    |
| regex_author_claim@2#75e32ebcdf68 | 18      | 0             | 0              | 0               | 0.272     |
| regex_condition@2#a0c64d9b6305    | 18      | 0             | 0              | 0               | 0.268     |
| regex_measurement@2#b984f16ded3b  | 18      | 0             | 0              | 0               | 0.288     |
| regex_metric@2#94a3000eacae       | 18      | 0             | 0              | 0               | 0.259     |
| regex_screen@1#a2821956ee33       | 20      | 0             | 0              | 0               | 0.283     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 133     | 6.650       |
| input_tokens     | 55144   | 2757.200    |
| made_model_calls | 61      | 3.050       |
| model_calls      | 61      | 3.050       |
| output_tokens    | 6897    | 344.850     |
| seconds          | 191.386 | 9.569       |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 6.650          |
| model_calls   | 3.050          |
| input_tokens  | 2757.200       |
| output_tokens | 344.850        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 7           |
| 1               | 10          |
| exhausted       | 1           |
| skipped         | 2           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 18   | 0    | 2    | 0    | 1.000       | 0.900    |

Screened out wrongly: S009, S013
