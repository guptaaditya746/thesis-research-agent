# Evaluation of run rag-tpl-s1-complex on rag-tpl-s1-f0f5d48e

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 436     | 431     | 404       | 0.927       | 0.937    | 0.932 | 1.000           |
| all             | all     | 436     | 431     | 404       | 0.927       | 0.937    | 0.932 | 1.000           |
| author_claim    | complex | 21      | 20      | 20        | 0.952       | 1.000    | 0.976 | 1.000           |
| author_claim    | all     | 21      | 20      | 20        | 0.952       | 1.000    | 0.976 | 1.000           |
| condition       | complex | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| condition       | all     | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| measurement     | complex | 294     | 300     | 273       | 0.929       | 0.910    | 0.919 | 1.000           |
| measurement     | all     | 294     | 300     | 273       | 0.929       | 0.910    | 0.919 | 1.000           |
| metric          | complex | 55      | 50      | 50        | 0.909       | 1.000    | 0.952 | 1.000           |
| metric          | all     | 55      | 50      | 50        | 0.909       | 1.000    | 0.952 | 1.000           |

Facts no item matched: 27; items matching no fact: 32.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 273                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.938          | 0         | -           |
| all     | 273                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.938          | 0         | -           |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.750                | 0.900          | 0.833               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| complex | evidence-engine | 20        | 20           | 0.750                | 0.900          | 0.833               | -              |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.961 [0.93, 0.98] | BCa      |
| metric          | 0.952 [0.91, 0.98] | BCa      |
| measurement     | 0.919 [0.88, 0.95] | BCa      |
| author_claim    | 0.976 [0.89, 1.00] | BCa      |
| all             | 0.932 [0.90, 0.95] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.750 [0.50, 0.90]   | BCa      | -                     | -               |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 773          | 773      | 1.000    |
| all             | all     | 773          | 773      | 1.000    |
| author_claim    | complex | 40           | 40       | 1.000    |
| author_claim    | all     | 40           | 40       | 1.000    |
| condition       | complex | 263          | 263      | 1.000    |
| condition       | all     | 263          | 263      | 1.000    |
| measurement     | complex | 300          | 300      | 1.000    |
| measurement     | all     | 300          | 300      | 1.000    |
| metric          | complex | 170          | 170      | 1.000    |
| metric          | all     | 170          | 170      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#32acd8d697c8   | 20      | 19              | 1      | 0              |
| llm_condition@1#6c050a1add96      | 61      | 61              | 38     | 38             |
| llm_measurement@1#88dd1e73d7e2    | 94      | 81              | 28     | 15             |
| llm_metric@1#8c11f22c1357         | 50      | 50              | 7      | 7              |
| regex_author_claim@1#120eee2396ac | 20      | 20              | 1      | 1              |
| regex_condition@1#3a430bcceb1d    | 28      | 23              | 5      | 0              |
| regex_measurement@1#786857ce00b2  | 266     | 258             | 200    | 192            |
| regex_metric@1#f052f9d6cba0       | 48      | 43              | 5      | 0              |

Facts no extractor found: measurement 27

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#32acd8d697c8   | author_claim    | all     | 20      | 20      | 19        | 0.950       | 0.950    | 0.950 | 1.000           | -                      | 1      | 0              |
| llm_author_claim@1#32acd8d697c8   | all             | all     | 20      | 20      | 19        | 0.950       | 0.950    | 0.950 | 1.000           | -                      | 1      | 0              |
| llm_condition@1#6c050a1add96      | condition       | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| llm_condition@1#6c050a1add96      | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| llm_measurement@1#88dd1e73d7e2    | measurement     | all     | 94      | 300     | 81        | 0.862       | 0.270    | 0.411 | 1.000           | 1.000                  | 28     | 15             |
| llm_measurement@1#88dd1e73d7e2    | all             | all     | 94      | 300     | 81        | 0.862       | 0.270    | 0.411 | 1.000           | -                      | 28     | 15             |
| llm_metric@1#8c11f22c1357         | metric          | all     | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#8c11f22c1357         | all             | all     | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@1#120eee2396ac | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| regex_author_claim@1#120eee2396ac | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| regex_condition@1#3a430bcceb1d    | condition       | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_condition@1#3a430bcceb1d    | all             | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_measurement@1#786857ce00b2  | measurement     | all     | 266     | 300     | 258       | 0.970       | 0.860    | 0.912 | 1.000           | 1.000                  | 200    | 192            |
| regex_measurement@1#786857ce00b2  | all             | all     | 266     | 300     | 258       | 0.970       | 0.860    | 0.912 | 1.000           | -                      | 200    | 192            |
| regex_metric@1#f052f9d6cba0       | metric          | all     | 48      | 50      | 43        | 0.896       | 0.860    | 0.878 | 1.000           | -                      | 5      | 0              |
| regex_metric@1#f052f9d6cba0       | all             | all     | 48      | 50      | 43        | 0.896       | 0.860    | 0.878 | 1.000           | -                      | 5      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#32acd8d697c8   | 20      | 20            | 18984          | 1256            | 11.386    |
| llm_condition@1#6c050a1add96      | 20      | 40            | 41237          | 5825            | 48.510    |
| llm_measurement@1#88dd1e73d7e2    | 20      | 40            | 56573          | 16508           | 127.300   |
| llm_metric@1#8c11f22c1357         | 20      | 32            | 33167          | 4322            | 35.267    |
| regex_author_claim@1#120eee2396ac | 20      | 0             | 0              | 0               | 0.143     |
| regex_condition@1#3a430bcceb1d    | 20      | 0             | 0              | 0               | 0.144     |
| regex_measurement@1#786857ce00b2  | 20      | 0             | 0              | 0               | 0.383     |
| regex_metric@1#f052f9d6cba0       | 20      | 0             | 0              | 0               | 0.147     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 60      | 3.000       |
| calls            | 160     | 8.000       |
| input_tokens     | 149961  | 7498.050    |
| made_model_calls | 132     | 6.600       |
| model_calls      | 132     | 6.600       |
| output_tokens    | 27911   | 1395.550    |
| seconds          | 224.346 | 11.217      |
