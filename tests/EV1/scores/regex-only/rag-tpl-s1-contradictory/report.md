# Evaluation of run rag-tpl-s1-contradictory on rag-tpl-s1-56b0bc02

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 93      | 162     | 86        | 0.925       | 0.531    | 0.675 | 1.000           |
| all             | all           | 93      | 162     | 86        | 0.925       | 0.531    | 0.675 | 1.000           |
| author_claim    | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           |
| condition       | all           | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           |
| measurement     | contradictory | 27      | 61      | 20        | 0.741       | 0.328    | 0.455 | 1.000           |
| measurement     | all           | 27      | 61      | 20        | 0.741       | 0.328    | 0.455 | 1.000           |
| metric          | contradictory | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |
| metric          | all           | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           |

Facts no item matched: 76; items matching no fact: 7.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 20                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| all           | 20                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.250                | 0.350          | 0.714               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| contradictory | evidence-engine | 20        | 20           | 0.250                | 0.350          | 0.714               | -              |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.629 [0.52, 0.73] | BCa      |
| metric          | 0.947 [0.82, 1.00] | BCa      |
| measurement     | 0.455 [0.33, 0.55] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.675 [0.60, 0.74] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.250 [0.10, 0.50]   | BCa      | -                     | -               |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | contradictory | 343          | 343      | 1.000    |
| all             | all           | 343          | 343      | 1.000    |
| author_claim    | contradictory | 40           | 40       | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
| condition       | contradictory | 172          | 172      | 1.000    |
| condition       | all           | 172          | 172      | 1.000    |
| measurement     | contradictory | 61           | 61       | 1.000    |
| measurement     | all           | 61           | 61       | 1.000    |
| metric          | contradictory | 70           | 70       | 1.000    |
| metric          | all           | 70           | 70       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| regex_author_claim@1#120eee2396ac | 20      | 20              | 20     | 20             |
| regex_condition@1#3a430bcceb1d    | 28      | 28              | 28     | 28             |
| regex_measurement@1#786857ce00b2  | 27      | 20              | 27     | 20             |
| regex_metric@1#f052f9d6cba0       | 18      | 18              | 18     | 18             |

Facts no extractor found: condition 33, measurement 41, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@1#120eee2396ac | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@1#120eee2396ac | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@1#3a430bcceb1d    | condition       | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 28     | 28             |
| regex_condition@1#3a430bcceb1d    | all             | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 1.000           | -                      | 28     | 28             |
| regex_measurement@1#786857ce00b2  | measurement     | all     | 27      | 61      | 20        | 0.741       | 0.328    | 0.455 | 1.000           | 1.000                  | 27     | 20             |
| regex_measurement@1#786857ce00b2  | all             | all     | 27      | 61      | 20        | 0.741       | 0.328    | 0.455 | 1.000           | -                      | 27     | 20             |
| regex_metric@1#f052f9d6cba0       | metric          | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |
| regex_metric@1#f052f9d6cba0       | all             | all     | 18      | 20      | 18        | 1.000       | 0.900    | 0.947 | 1.000           | -                      | 18     | 18             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| regex_author_claim@1#120eee2396ac | 20      | 0             | 0              | 0               | 0.289     |
| regex_condition@1#3a430bcceb1d    | 20      | 0             | 0              | 0               | 0.271     |
| regex_measurement@1#786857ce00b2  | 20      | 0             | 0              | 0               | 0.298     |
| regex_metric@1#f052f9d6cba0       | 20      | 0             | 0              | 0               | 0.271     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 80      | 4.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 1.929   | 0.096       |
