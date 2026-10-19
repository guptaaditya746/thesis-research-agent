# Evaluation of run rag-tpl-s1-contradictory on rag-tpl-s1-56b0bc02

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 196     | 162     | 162       | 0.827       | 1.000    | 0.905 | 1.000           |
| all             | all           | 196     | 162     | 162       | 0.827       | 1.000    | 0.905 | 1.000           |
| author_claim    | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| condition       | all           | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| measurement     | contradictory | 84      | 61      | 61        | 0.726       | 1.000    | 0.841 | 1.000           |
| measurement     | all           | 84      | 61      | 61        | 0.726       | 1.000    | 0.841 | 1.000           |
| metric          | contradictory | 26      | 20      | 20        | 0.769       | 1.000    | 0.870 | 1.000           |
| metric          | all           | 26      | 20      | 20        | 0.769       | 1.000    | 0.870 | 1.000           |

Facts no item matched: 0; items matching no fact: 34.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 61                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.803          | 0         | -           |
| all           | 61                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.803          | 0         | -           |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.900                | 1.000          | 0.900               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| contradictory | evidence-engine | 20        | 20           | 0.900                | 1.000          | 0.900               | -              |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.961 [0.93, 0.98] | BCa      |
| metric          | 0.870 [0.80, 0.95] | BCa      |
| measurement     | 0.841 [0.77, 0.91] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.905 [0.86, 0.94] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.900 [0.70, 1.00]   | BCa      | -                     | -               |

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
| llm_author_claim@1#32acd8d697c8   | 20      | 20              | 0      | 0              |
| llm_condition@1#6c050a1add96      | 61      | 61              | 38     | 38             |
| llm_measurement@1#88dd1e73d7e2    | 56      | 45              | 24     | 13             |
| llm_metric@1#8c11f22c1357         | 21      | 20              | 8      | 7              |
| regex_author_claim@1#120eee2396ac | 20      | 20              | 0      | 0              |
| regex_condition@1#3a430bcceb1d    | 28      | 23              | 5      | 0              |
| regex_measurement@1#786857ce00b2  | 60      | 48              | 28     | 16             |
| regex_metric@1#f052f9d6cba0       | 18      | 13              | 5      | 0              |

Facts no extractor found: none

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#32acd8d697c8   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#32acd8d697c8   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#6c050a1add96      | condition       | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| llm_condition@1#6c050a1add96      | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| llm_measurement@1#88dd1e73d7e2    | measurement     | all     | 56      | 61      | 45        | 0.804       | 0.738    | 0.769 | 1.000           | 1.000                  | 24     | 13             |
| llm_measurement@1#88dd1e73d7e2    | all             | all     | 56      | 61      | 45        | 0.804       | 0.738    | 0.769 | 1.000           | -                      | 24     | 13             |
| llm_metric@1#8c11f22c1357         | metric          | all     | 21      | 20      | 20        | 0.952       | 1.000    | 0.976 | 1.000           | -                      | 8      | 7              |
| llm_metric@1#8c11f22c1357         | all             | all     | 21      | 20      | 20        | 0.952       | 1.000    | 0.976 | 1.000           | -                      | 8      | 7              |
| regex_author_claim@1#120eee2396ac | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@1#120eee2396ac | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@1#3a430bcceb1d    | condition       | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_condition@1#3a430bcceb1d    | all             | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_measurement@1#786857ce00b2  | measurement     | all     | 60      | 61      | 48        | 0.800       | 0.787    | 0.793 | 1.000           | 1.000                  | 28     | 16             |
| regex_measurement@1#786857ce00b2  | all             | all     | 60      | 61      | 48        | 0.800       | 0.787    | 0.793 | 1.000           | -                      | 28     | 16             |
| regex_metric@1#f052f9d6cba0       | metric          | all     | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| regex_metric@1#f052f9d6cba0       | all             | all     | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#32acd8d697c8   | 20      | 20            | 15488          | 1122            | 10.178    |
| llm_condition@1#6c050a1add96      | 20      | 40            | 34245          | 5856            | 47.736    |
| llm_measurement@1#88dd1e73d7e2    | 20      | 40            | 43178          | 9676            | 75.747    |
| llm_metric@1#8c11f22c1357         | 20      | 38            | 30906          | 2323            | 20.348    |
| regex_author_claim@1#120eee2396ac | 20      | 0             | 0              | 0               | 0.148     |
| regex_condition@1#3a430bcceb1d    | 20      | 0             | 0              | 0               | 0.146     |
| regex_measurement@1#786857ce00b2  | 20      | 0             | 0              | 0               | 0.339     |
| regex_metric@1#f052f9d6cba0       | 20      | 0             | 0              | 0               | 0.143     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 60      | 3.000       |
| calls            | 160     | 8.000       |
| input_tokens     | 123817  | 6190.850    |
| made_model_calls | 138     | 6.900       |
| model_calls      | 138     | 6.900       |
| output_tokens    | 18977   | 948.850     |
| seconds          | 155.774 | 7.789       |
