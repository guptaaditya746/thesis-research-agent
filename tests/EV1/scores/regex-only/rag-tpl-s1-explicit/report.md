# Evaluation of run rag-tpl-s1-explicit on rag-tpl-s1-59c5118b

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: explicit

## A. Extraction

| evidence_type   | level    | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|----------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit | 79      | 162     | 79        | 1.000       | 0.488    | 0.656 | 1.000           |
| all             | all      | 79      | 162     | 79        | 1.000       | 0.488    | 0.656 | 1.000           |
| author_claim    | explicit | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           |
| condition       | all      | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           |
| measurement     | explicit | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           |
| measurement     | all      | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           |
| metric          | explicit | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |
| metric          | all      | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |

Facts no item matched: 83; items matching no fact: 0.

## B. Integration

| level    | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|----------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit | 13                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| all      | 13                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |

## C. Synthesis

| system          | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | supported | mixed      | no              | 20        | 20           | 0.050                | 0.050          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level    | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|----------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit | evidence-engine | 20        | 20           | 0.050                | 0.050          | 1.000               | -              |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.629 [0.52, 0.73] | BCa      |
| metric          | 0.947 [0.82, 1.00] | BCa      |
| measurement     | 0.351 [0.23, 0.46] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.656 [0.59, 0.73] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.050 [0.00, 0.25]   | BCa      | -                     | -               |

## Locate recall

| evidence_type   | level    | placements   | inside   | recall   |
|-----------------|----------|--------------|----------|----------|
| all             | explicit | 364          | 364      | 1.000    |
| all             | all      | 364          | 364      | 1.000    |
| author_claim    | explicit | 40           | 40       | 1.000    |
| author_claim    | all      | 40           | 40       | 1.000    |
| condition       | explicit | 162          | 162      | 1.000    |
| condition       | all      | 162          | 162      | 1.000    |
| measurement     | explicit | 61           | 61       | 1.000    |
| measurement     | all      | 61           | 61       | 1.000    |
| metric          | explicit | 101          | 101      | 1.000    |
| metric          | all      | 101          | 101      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| regex_author_claim@1#120eee2396ac | 20      | 20              | 20     | 20             |
| regex_condition@1#3a430bcceb1d    | 28      | 28              | 28     | 28             |
| regex_measurement@1#786857ce00b2  | 13      | 13              | 13     | 13             |
| regex_metric@1#f052f9d6cba0       | 18      | 18              | 18     | 18             |

Facts no extractor found: condition 33, measurement 48, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@1#120eee2396ac | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@1#120eee2396ac | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@1#3a430bcceb1d    | condition       | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 28     | 28             |
| regex_condition@1#3a430bcceb1d    | all             | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 28     | 28             |
| regex_measurement@1#786857ce00b2  | measurement     | all     | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | 1.000                  | 13     | 13             |
| regex_measurement@1#786857ce00b2  | all             | all     | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | -                      | 13     | 13             |
| regex_metric@1#f052f9d6cba0       | metric          | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |
| regex_metric@1#f052f9d6cba0       | all             | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| regex_author_claim@1#120eee2396ac | 20      | 0             | 0              | 0               | 0.276     |
| regex_condition@1#3a430bcceb1d    | 20      | 0             | 0              | 0               | 0.255     |
| regex_measurement@1#786857ce00b2  | 20      | 0             | 0              | 0               | 0.285     |
| regex_metric@1#f052f9d6cba0       | 20      | 0             | 0              | 0               | 0.261     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 80      | 4.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 1.762   | 0.088       |
