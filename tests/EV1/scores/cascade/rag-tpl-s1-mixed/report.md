# Evaluation of run rag-tpl-s1-mixed on rag-tpl-s1-6162b495

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 41      | 38      | 38        | 0.927       | 1.000    | 0.962 | 1.000           |
| all             | paraphrased   | 34      | 34      | 34        | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | distributed   | 32      | 26      | 25        | 0.781       | 0.962    | 0.862 | 1.000           |
| all             | complex       | 79      | 74      | 71        | 0.899       | 0.959    | 0.928 | 1.000           |
| all             | contradictory | 42      | 38      | 38        | 0.905       | 1.000    | 0.950 | 1.000           |
| all             | all           | 228     | 210     | 206       | 0.904       | 0.981    | 0.941 | 1.000           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 16      | 15      | 15        | 0.938       | 1.000    | 0.968 | 1.000           |
| condition       | paraphrased   | 13      | 13      | 13        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed   | 15      | 9       | 9         | 0.600       | 1.000    | 0.750 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all           | 68      | 61      | 61        | 0.897       | 1.000    | 0.946 | 1.000           |
| measurement     | explicit      | 16      | 15      | 15        | 0.938       | 1.000    | 0.968 | 1.000           |
| measurement     | paraphrased   | 13      | 13      | 13        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| measurement     | complex       | 53      | 50      | 47        | 0.887       | 0.940    | 0.913 | 1.000           |
| measurement     | contradictory | 18      | 15      | 15        | 0.833       | 1.000    | 0.909 | 1.000           |
| measurement     | all           | 108     | 102     | 98        | 0.907       | 0.961    | 0.933 | 1.000           |
| metric          | explicit      | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | distributed   | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | complex       | 13      | 11      | 11        | 0.846       | 1.000    | 0.917 | 1.000           |
| metric          | contradictory | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | all           | 32      | 27      | 27        | 0.844       | 1.000    | 0.915 | 1.000           |

Facts no item matched: 4; items matching no fact: 22.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 15                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.933          | 0         | -           |
| paraphrased   | 13                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 0         | -           |
| distributed   | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.750          | 0         | -           |
| complex       | 47                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.872          | 0         | -           |
| contradictory | 15                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.933          | 0         | -           |
| all           | 98                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.898          | 0         | -           |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.900                | 0.950          | 0.947               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| distributed   | evidence-engine | 4         | 4            | 0.750                | 0.750          | 1.000               | -              |
| complex       | evidence-engine | 4         | 4            | 0.750                | 1.000          | 0.750               | -              |
| contradictory | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.946 [0.89, 0.98] | BCa      |
| metric          | 0.915 [0.85, 0.97] | BCa      |
| measurement     | 0.933 [0.89, 0.97] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.941 [0.91, 0.97] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.900 [0.70, 1.00]   | BCa      | -                     | -               |

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
| llm_author_claim@1#32acd8d697c8   | 20      | 20              | 0      | 0              |
| llm_condition@1#6c050a1add96      | 61      | 60              | 45     | 44             |
| llm_measurement@1#88dd1e73d7e2    | 66      | 61              | 43     | 38             |
| llm_metric@1#8c11f22c1357         | 25      | 23              | 10     | 8              |
| regex_author_claim@1#120eee2396ac | 20      | 20              | 0      | 0              |
| regex_condition@1#3a430bcceb1d    | 23      | 17              | 7      | 1              |
| regex_measurement@1#786857ce00b2  | 65      | 60              | 42     | 37             |
| regex_metric@1#f052f9d6cba0       | 22      | 19              | 7      | 4              |

Facts no extractor found: measurement 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#32acd8d697c8   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#32acd8d697c8   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#6c050a1add96      | condition       | all     | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | -                      | 45     | 44             |
| llm_condition@1#6c050a1add96      | all             | all     | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | -                      | 45     | 44             |
| llm_measurement@1#88dd1e73d7e2    | measurement     | all     | 66      | 102     | 61        | 0.924       | 0.598    | 0.726 | 1.000           | 1.000                  | 43     | 38             |
| llm_measurement@1#88dd1e73d7e2    | all             | all     | 66      | 102     | 61        | 0.924       | 0.598    | 0.726 | 1.000           | -                      | 43     | 38             |
| llm_metric@1#8c11f22c1357         | metric          | all     | 25      | 27      | 23        | 0.920       | 0.852    | 0.885 | 1.000           | -                      | 10     | 8              |
| llm_metric@1#8c11f22c1357         | all             | all     | 25      | 27      | 23        | 0.920       | 0.852    | 0.885 | 1.000           | -                      | 10     | 8              |
| regex_author_claim@1#120eee2396ac | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@1#120eee2396ac | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@1#3a430bcceb1d    | condition       | all     | 23      | 61      | 17        | 0.739       | 0.279    | 0.405 | 1.000           | -                      | 7      | 1              |
| regex_condition@1#3a430bcceb1d    | all             | all     | 23      | 61      | 17        | 0.739       | 0.279    | 0.405 | 1.000           | -                      | 7      | 1              |
| regex_measurement@1#786857ce00b2  | measurement     | all     | 65      | 102     | 60        | 0.923       | 0.588    | 0.719 | 1.000           | 1.000                  | 42     | 37             |
| regex_measurement@1#786857ce00b2  | all             | all     | 65      | 102     | 60        | 0.923       | 0.588    | 0.719 | 1.000           | -                      | 42     | 37             |
| regex_metric@1#f052f9d6cba0       | metric          | all     | 22      | 27      | 19        | 0.864       | 0.704    | 0.776 | 1.000           | -                      | 7      | 4              |
| regex_metric@1#f052f9d6cba0       | all             | all     | 22      | 27      | 19        | 0.864       | 0.704    | 0.776 | 1.000           | -                      | 7      | 4              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#32acd8d697c8   | 20      | 20            | 16689          | 1136            | 2.170     |
| llm_condition@1#6c050a1add96      | 20      | 40            | 36649          | 5935            | 11.483    |
| llm_measurement@1#88dd1e73d7e2    | 20      | 40            | 47399          | 12677           | 22.441    |
| llm_metric@1#8c11f22c1357         | 20      | 36            | 31986          | 3388            | 4.987     |
| regex_author_claim@1#120eee2396ac | 20      | 0             | 0              | 0               | 0.134     |
| regex_condition@1#3a430bcceb1d    | 20      | 0             | 0              | 0               | 0.137     |
| regex_measurement@1#786857ce00b2  | 20      | 0             | 0              | 0               | 0.184     |
| regex_metric@1#f052f9d6cba0       | 20      | 0             | 0              | 0               | 0.138     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 140     | 7.000       |
| calls            | 160     | 8.000       |
| input_tokens     | 132723  | 6636.150    |
| made_model_calls | 28      | 1.400       |
| model_calls      | 136     | 6.800       |
| output_tokens    | 23136   | 1156.800    |
| seconds          | 42.641  | 2.132       |
