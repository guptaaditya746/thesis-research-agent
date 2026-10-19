# Evaluation of run rag-tpl-s1-distributed on rag-tpl-s1-79207ad1

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 185     | 162     | 148       | 0.800       | 0.914    | 0.853 | 1.000           |
| all             | all         | 185     | 162     | 148       | 0.800       | 0.914    | 0.853 | 1.000           |
| author_claim    | distributed | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 89      | 61      | 61        | 0.685       | 1.000    | 0.813 | 1.000           |
| condition       | all         | 89      | 61      | 61        | 0.685       | 1.000    | 0.813 | 1.000           |
| measurement     | distributed | 49      | 61      | 49        | 1.000       | 0.803    | 0.891 | 1.000           |
| measurement     | all         | 49      | 61      | 49        | 1.000       | 0.803    | 0.891 | 1.000           |
| metric          | distributed | 27      | 20      | 18        | 0.667       | 0.900    | 0.766 | 1.000           |
| metric          | all         | 27      | 20      | 18        | 0.667       | 0.900    | 0.766 | 1.000           |

Facts no item matched: 14; items matching no fact: 37.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 49                     | 1.000                  | 1.000                     | 1.000             | 0.878             | 0.633          | 0         | -           |
| all         | 49                     | 1.000                  | 1.000                     | 1.000             | 0.878             | 0.633          | 0         | -           |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.800                | 0.800          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| distributed | evidence-engine | 20        | 20           | 0.800                | 0.800          | 1.000               | -              |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.813 [0.78, 0.85] | BCa      |
| metric          | 0.766 [0.68, 0.85] | BCa      |
| measurement     | 0.891 [0.73, 0.97] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.853 [0.80, 0.89] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.800 [0.60, 0.95]   | BCa      | -                     | -               |

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
| llm_author_claim@1#32acd8d697c8   | 20      | 20              | 0      | 0              |
| llm_condition@1#6c050a1add96      | 61      | 53              | 61     | 53             |
| llm_measurement@1#88dd1e73d7e2    | 49      | 49              | 49     | 49             |
| llm_metric@1#8c11f22c1357         | 9       | 1               | 9      | 1              |
| regex_author_claim@1#120eee2396ac | 20      | 20              | 0      | 0              |
| regex_condition@1#3a430bcceb1d    | 28      | 8               | 28     | 8              |
| regex_measurement@1#786857ce00b2  | 0       | 0               | 0      | 0              |
| regex_metric@1#f052f9d6cba0       | 18      | 17              | 18     | 17             |

Facts no extractor found: measurement 12, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#32acd8d697c8   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#32acd8d697c8   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#6c050a1add96      | condition       | all     | 61      | 61      | 53        | 0.869       | 0.869    | 0.869 | 1.000           | -                      | 61     | 53             |
| llm_condition@1#6c050a1add96      | all             | all     | 61      | 61      | 53        | 0.869       | 0.869    | 0.869 | 1.000           | -                      | 61     | 53             |
| llm_measurement@1#88dd1e73d7e2    | measurement     | all     | 49      | 61      | 49        | 1.000       | 0.803    | 0.891 | 1.000           | 1.000                  | 49     | 49             |
| llm_measurement@1#88dd1e73d7e2    | all             | all     | 49      | 61      | 49        | 1.000       | 0.803    | 0.891 | 1.000           | -                      | 49     | 49             |
| llm_metric@1#8c11f22c1357         | metric          | all     | 9       | 20      | 1         | 0.111       | 0.050    | 0.069 | 1.000           | -                      | 9      | 1              |
| llm_metric@1#8c11f22c1357         | all             | all     | 9       | 20      | 1         | 0.111       | 0.050    | 0.069 | 1.000           | -                      | 9      | 1              |
| regex_author_claim@1#120eee2396ac | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@1#120eee2396ac | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@1#3a430bcceb1d    | condition       | all     | 28      | 61      | 8         | 0.286       | 0.131    | 0.180 | 1.000           | -                      | 28     | 8              |
| regex_condition@1#3a430bcceb1d    | all             | all     | 28      | 61      | 8         | 0.286       | 0.131    | 0.180 | 1.000           | -                      | 28     | 8              |
| regex_measurement@1#786857ce00b2  | measurement     | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@1#786857ce00b2  | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@1#f052f9d6cba0       | metric          | all     | 18      | 20      | 17        | 0.944       | 0.850    | 0.895 | 1.000           | -                      | 18     | 17             |
| regex_metric@1#f052f9d6cba0       | all             | all     | 18      | 20      | 17        | 0.944       | 0.850    | 0.895 | 1.000           | -                      | 18     | 17             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#32acd8d697c8   | 20      | 20            | 17929          | 1139            | 10.399    |
| llm_condition@1#6c050a1add96      | 20      | 37            | 35540          | 5550            | 45.310    |
| llm_measurement@1#88dd1e73d7e2    | 20      | 40            | 47429          | 9624            | 75.711    |
| llm_metric@1#8c11f22c1357         | 20      | 40            | 37509          | 2752            | 23.903    |
| regex_author_claim@1#120eee2396ac | 20      | 0             | 0              | 0               | 0.141     |
| regex_condition@1#3a430bcceb1d    | 20      | 0             | 0              | 0               | 0.145     |
| regex_measurement@1#786857ce00b2  | 20      | 0             | 0              | 0               | 0.320     |
| regex_metric@1#f052f9d6cba0       | 20      | 0             | 0              | 0               | 0.140     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 60      | 3.000       |
| calls            | 160     | 8.000       |
| input_tokens     | 138407  | 6920.350    |
| made_model_calls | 137     | 6.850       |
| model_calls      | 137     | 6.850       |
| output_tokens    | 19065   | 953.250     |
| seconds          | 157.073 | 7.854       |
