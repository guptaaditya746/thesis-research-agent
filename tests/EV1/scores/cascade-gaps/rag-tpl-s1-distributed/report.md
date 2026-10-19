# Evaluation of run rag-tpl-s1-distributed on rag-tpl-s1-79207ad1

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 132     | 162     | 130       | 0.985       | 0.802    | 0.884 | 1.000           |
| all             | all         | 132     | 162     | 130       | 0.985       | 0.802    | 0.884 | 1.000           |
| author_claim    | distributed | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 47      | 61      | 45        | 0.957       | 0.738    | 0.833 | 1.000           |
| condition       | all         | 47      | 61      | 45        | 0.957       | 0.738    | 0.833 | 1.000           |
| measurement     | distributed | 45      | 61      | 45        | 1.000       | 0.738    | 0.849 | 1.000           |
| measurement     | all         | 45      | 61      | 45        | 1.000       | 0.738    | 0.849 | 1.000           |
| metric          | distributed | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 32; items matching no fact: 2.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 45                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| all         | 45                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| distributed | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | yes              | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.833 [0.78, 0.90] | BCa      |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 0.849 [0.79, 0.92] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.884 [0.84, 0.93] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | distributed | 364          | 364      | 1.000    |
| all             | all         | 364          | 364      | 1.000    |
| author_claim    | distributed | 40           | 40       | 1.000    |
| author_claim    | all         | 40           | 40       | 1.000    |
| condition       | distributed | 183          | 183      | 1.000    |
| condition       | all         | 183          | 183      | 1.000    |
| measurement     | distributed | 61           | 61       | 1.000    |
| measurement     | all         | 61           | 61       | 1.000    |
| metric          | distributed | 80           | 80       | 1.000    |
| metric          | all         | 80           | 80       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | 0       | 0               | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | 19      | 19              | 19     | 19             |
| llm_measurement@1#957820ab7bd1    | 45      | 45              | 45     | 45             |
| llm_metric@1#6186147fa702         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#75e32ebcdf68 | 20      | 20              | 20     | 20             |
| regex_condition@2#a0c64d9b6305    | 28      | 26              | 28     | 26             |
| regex_measurement@2#b984f16ded3b  | 0       | 0               | 0      | 0              |
| regex_metric@2#94a3000eacae       | 18      | 18              | 18     | 18             |

Facts no extractor found: condition 16, measurement 16

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | all             | all     | 0       | 162     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | condition       | all     | 19      | 30      | 19        | 1.000       | 0.633    | 0.776 | 1.000           | -                      | 19     | 19             |
| llm_condition@1#f75a85c10bd4      | all             | all     | 19      | 30      | 19        | 1.000       | 0.633    | 0.776 | 1.000           | -                      | 19     | 19             |
| llm_measurement@1#957820ab7bd1    | measurement     | all     | 45      | 61      | 45        | 1.000       | 0.738    | 0.849 | 1.000           | 1.000                  | 45     | 45             |
| llm_measurement@1#957820ab7bd1    | all             | all     | 45      | 61      | 45        | 1.000       | 0.738    | 0.849 | 1.000           | -                      | 45     | 45             |
| llm_metric@1#6186147fa702         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#6186147fa702         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#75e32ebcdf68 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#75e32ebcdf68 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#a0c64d9b6305    | condition       | all     | 28      | 61      | 26        | 0.929       | 0.426    | 0.584 | 1.000           | -                      | 28     | 26             |
| regex_condition@2#a0c64d9b6305    | all             | all     | 28      | 61      | 26        | 0.929       | 0.426    | 0.584 | 1.000           | -                      | 28     | 26             |
| regex_measurement@2#b984f16ded3b  | measurement     | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#b984f16ded3b  | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#94a3000eacae       | metric          | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |
| regex_metric@2#94a3000eacae       | all             | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#f75a85c10bd4      | 10      | 10            | 10718          | 1170            | 32.548    |
| llm_measurement@1#957820ab7bd1    | 20      | 40            | 47650          | 6600            | 177.623   |
| llm_metric@1#6186147fa702         | 2       | 2             | 2278           | 204             | 5.833     |
| llm_screen@1#a1013a736e72         | 20      | 20            | 16650          | 2079            | 57.784    |
| regex_author_claim@2#75e32ebcdf68 | 20      | 0             | 0              | 0               | 0.308     |
| regex_condition@2#a0c64d9b6305    | 20      | 0             | 0              | 0               | 0.316     |
| regex_measurement@2#b984f16ded3b  | 20      | 0             | 0              | 0               | 0.322     |
| regex_metric@2#94a3000eacae       | 20      | 0             | 0              | 0               | 0.295     |
| regex_screen@1#a2821956ee33       | 20      | 0             | 0              | 0               | 0.297     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 152     | 7.600       |
| input_tokens     | 77296   | 3864.800    |
| made_model_calls | 72      | 3.600       |
| model_calls      | 72      | 3.600       |
| output_tokens    | 10053   | 502.650     |
| seconds          | 276.653 | 13.833      |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.600          |
| model_calls   | 3.600          |
| input_tokens  | 3864.800       |
| output_tokens | 502.650        |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
