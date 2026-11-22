# Evaluation of run rag-tpl-s1-mixed on rag-tpl-s1-6162b495

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 15      | 38      | 15        | 1.000       | 0.395    | 0.566 | 1.000           |
| all             | paraphrased   | 4       | 34      | 4         | 1.000       | 0.118    | 0.211 | 1.000           |
| all             | distributed   | 14      | 26      | 14        | 1.000       | 0.538    | 0.700 | 1.000           |
| all             | complex       | 39      | 74      | 39        | 1.000       | 0.527    | 0.690 | 1.000           |
| all             | contradictory | 24      | 38      | 22        | 0.917       | 0.579    | 0.710 | 1.000           |
| all             | all           | 96      | 210     | 94        | 0.979       | 0.448    | 0.614 | 1.000           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 6       | 15      | 6         | 1.000       | 0.400    | 0.571 | 1.000           |
| condition       | paraphrased   | 0       | 13      | 0         | 0.000       | 0.000    | 0.000 | -               |
| condition       | distributed   | 6       | 9       | 6         | 1.000       | 0.667    | 0.800 | 1.000           |
| condition       | complex       | 4       | 9       | 4         | 1.000       | 0.444    | 0.615 | 1.000           |
| condition       | contradictory | 7       | 15      | 7         | 1.000       | 0.467    | 0.636 | 1.000           |
| condition       | all           | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 1.000           |
| measurement     | explicit      | 2       | 15      | 2         | 1.000       | 0.133    | 0.235 | 1.000           |
| measurement     | paraphrased   | 0       | 13      | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | distributed   | 0       | 9       | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | complex       | 20      | 50      | 20        | 1.000       | 0.400    | 0.571 | 1.000           |
| measurement     | contradictory | 9       | 15      | 7         | 0.778       | 0.467    | 0.583 | 1.000           |
| measurement     | all           | 31      | 102     | 29        | 0.935       | 0.284    | 0.436 | 1.000           |
| metric          | explicit      | 3       | 4       | 3         | 1.000       | 0.750    | 0.857 | 1.000           |
| metric          | paraphrased   | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               |
| metric          | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 22      | 27      | 22        | 1.000       | 0.815    | 0.898 | 1.000           |

Facts no item matched: 116; items matching no fact: 2.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 2                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| complex       | 20                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| contradictory | 7                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| all           | 29                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.200                | 0.200          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | evidence-engine | 4         | 4            | 0.000                | 0.000          | -                   | -              |
| paraphrased   | evidence-engine | 4         | 4            | 0.000                | 0.000          | -                   | -              |
| distributed   | evidence-engine | 4         | 4            | 0.000                | 0.000          | -                   | -              |
| complex       | evidence-engine | 4         | 4            | 0.250                | 0.250          | 1.000               | -              |
| contradictory | evidence-engine | 4         | 4            | 0.750                | 0.750          | 1.000               | -              |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.548 [0.41, 0.67] | BCa      |
| metric          | 0.898 [0.76, 0.97] | BCa      |
| measurement     | 0.436 [0.26, 0.68] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.614 [0.52, 0.73] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.200 [0.05, 0.40]   | BCa      | -                     | -               |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 84           | 84       | 1.000    |
| all             | paraphrased   | 72           | 72       | 1.000    |
| all             | distributed   | 60           | 60       | 1.000    |
| all             | complex       | 138          | 138      | 1.000    |
| all             | contradictory | 77           | 77       | 1.000    |
| all             | all           | 431          | 431      | 1.000    |
| author_claim    | explicit      | 8            | 8        | 1.000    |
| author_claim    | paraphrased   | 8            | 8        | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
| condition       | explicit      | 38           | 38       | 1.000    |
| condition       | paraphrased   | 34           | 34       | 1.000    |
| condition       | distributed   | 27           | 27       | 1.000    |
| condition       | complex       | 43           | 43       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 182          | 182      | 1.000    |
| measurement     | explicit      | 15           | 15       | 1.000    |
| measurement     | paraphrased   | 13           | 13       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 50           | 50       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 102          | 102      | 1.000    |
| metric          | explicit      | 23           | 23       | 1.000    |
| metric          | paraphrased   | 17           | 17       | 1.000    |
| metric          | distributed   | 16           | 16       | 1.000    |
| metric          | complex       | 37           | 37       | 1.000    |
| metric          | contradictory | 14           | 14       | 1.000    |
| metric          | all           | 107          | 107      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| regex_author_claim@1#120eee2396ac | 20      | 20              | 20     | 20             |
| regex_condition@1#3a430bcceb1d    | 23      | 23              | 23     | 23             |
| regex_measurement@1#786857ce00b2  | 31      | 29              | 31     | 29             |
| regex_metric@1#f052f9d6cba0       | 22      | 22              | 22     | 22             |

Facts no extractor found: condition 38, measurement 73, metric 5

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@1#120eee2396ac | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@1#120eee2396ac | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@1#3a430bcceb1d    | condition       | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 1.000           | -                      | 23     | 23             |
| regex_condition@1#3a430bcceb1d    | all             | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 1.000           | -                      | 23     | 23             |
| regex_measurement@1#786857ce00b2  | measurement     | all     | 31      | 102     | 29        | 0.935       | 0.284    | 0.436 | 1.000           | 1.000                  | 31     | 29             |
| regex_measurement@1#786857ce00b2  | all             | all     | 31      | 102     | 29        | 0.935       | 0.284    | 0.436 | 1.000           | -                      | 31     | 29             |
| regex_metric@1#f052f9d6cba0       | metric          | all     | 22      | 27      | 22        | 1.000       | 0.815    | 0.898 | 1.000           | -                      | 22     | 22             |
| regex_metric@1#f052f9d6cba0       | all             | all     | 22      | 27      | 22        | 1.000       | 0.815    | 0.898 | 1.000           | -                      | 22     | 22             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| regex_author_claim@1#120eee2396ac | 20      | 0             | 0              | 0               | 0.162     |
| regex_condition@1#3a430bcceb1d    | 20      | 0             | 0              | 0               | 0.175     |
| regex_measurement@1#786857ce00b2  | 20      | 0             | 0              | 0               | 0.170     |
| regex_metric@1#f052f9d6cba0       | 20      | 0             | 0              | 0               | 0.177     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 64      | 3.200       |
| calls            | 80      | 4.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 1.413   | 0.071       |
