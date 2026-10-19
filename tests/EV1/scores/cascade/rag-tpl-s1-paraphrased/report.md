# Evaluation of run rag-tpl-s1-paraphrased on rag-tpl-s1-4d15ddc4

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: paraphrased

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | paraphrased | 162     | 162     | 161       | 0.994       | 0.994    | 0.994 | 1.000           |
| all             | all         | 162     | 162     | 161       | 0.994       | 0.994    | 0.994 | 1.000           |
| author_claim    | paraphrased | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all         | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | paraphrased | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           |
| measurement     | all         | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           |
| metric          | paraphrased | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 1; items matching no fact: 1.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| paraphrased | 60                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| all         | 60                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| paraphrased | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 1.000 [n/a]        | -        |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 0.984 [0.92, 1.00] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.994 [0.97, 1.00] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | paraphrased | 344          | 344      | 1.000    |
| all             | all         | 344          | 344      | 1.000    |
| author_claim    | paraphrased | 40           | 40       | 1.000    |
| author_claim    | all         | 40           | 40       | 1.000    |
| condition       | paraphrased | 162          | 162      | 1.000    |
| condition       | all         | 162          | 162      | 1.000    |
| measurement     | paraphrased | 61           | 61       | 1.000    |
| measurement     | all         | 61           | 61       | 1.000    |
| metric          | paraphrased | 81           | 81       | 1.000    |
| metric          | all         | 81           | 81       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#32acd8d697c8   | 20      | 20              | 0      | 0              |
| llm_condition@1#6c050a1add96      | 61      | 61              | 61     | 61             |
| llm_measurement@1#88dd1e73d7e2    | 61      | 60              | 61     | 60             |
| llm_metric@1#8c11f22c1357         | 20      | 20              | 20     | 20             |
| regex_author_claim@1#120eee2396ac | 20      | 20              | 0      | 0              |
| regex_condition@1#3a430bcceb1d    | 0       | 0               | 0      | 0              |
| regex_measurement@1#786857ce00b2  | 0       | 0               | 0      | 0              |
| regex_metric@1#f052f9d6cba0       | 0       | 0               | 0      | 0              |

Facts no extractor found: measurement 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#32acd8d697c8   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#32acd8d697c8   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#6c050a1add96      | condition       | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| llm_condition@1#6c050a1add96      | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| llm_measurement@1#88dd1e73d7e2    | measurement     | all     | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | 1.000                  | 61     | 60             |
| llm_measurement@1#88dd1e73d7e2    | all             | all     | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | -                      | 61     | 60             |
| llm_metric@1#8c11f22c1357         | metric          | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| llm_metric@1#8c11f22c1357         | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@1#120eee2396ac | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@1#120eee2396ac | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@1#3a430bcceb1d    | condition       | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_condition@1#3a430bcceb1d    | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@1#786857ce00b2  | measurement     | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@1#786857ce00b2  | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@1#f052f9d6cba0       | metric          | all     | 0       | 20      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@1#f052f9d6cba0       | all             | all     | 0       | 20      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#32acd8d697c8   | 20      | 20            | 16009          | 1177            | 12.379    |
| llm_condition@1#6c050a1add96      | 20      | 40            | 35611          | 6292            | 62.353    |
| llm_measurement@1#88dd1e73d7e2    | 20      | 40            | 45600          | 12849           | 104.383   |
| llm_metric@1#8c11f22c1357         | 20      | 40            | 33651          | 2952            | 30.213    |
| regex_author_claim@1#120eee2396ac | 20      | 0             | 0              | 0               | 0.148     |
| regex_condition@1#3a430bcceb1d    | 20      | 0             | 0              | 0               | 0.141     |
| regex_measurement@1#786857ce00b2  | 20      | 0             | 0              | 0               | 0.290     |
| regex_metric@1#f052f9d6cba0       | 20      | 0             | 0              | 0               | 0.143     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 80      | 4.000       |
| calls            | 160     | 8.000       |
| input_tokens     | 130871  | 6543.550    |
| made_model_calls | 112     | 5.600       |
| model_calls      | 140     | 7.000       |
| output_tokens    | 23270   | 1163.500    |
| seconds          | 211.095 | 10.555      |
