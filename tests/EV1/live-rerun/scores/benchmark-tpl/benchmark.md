# Extractor benchmark

Per extractor id (B11), pooled over the reports given; an item counts for every extractor in its `found_by`. Recall is against the facts of the documents and types the extractor was called on (its extractor_call events; `called`), or every fact of the type and level for a run without events (`all_facts`).

## llm_author_claim@1#fefdf4416c50

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | paraphrased   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | distributed   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | complex       | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | all           | 100     | 100     | 100       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | paraphrased   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | distributed   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | complex       | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | all           | 100     | 100     | 100       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens    | output_tokens   | seconds         |
|---------|---------------|-----------------|-----------------|-----------------|
| 100     | 100 [1.000]   | 87804 [878.040] | 11830 [118.300] | 308.613 [3.086] |

Re-execution stability: not measured.

## llm_condition@1#134ab1a38338

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | -                      | 38     | 37             |
| all             | paraphrased   | 61      | 61      | 59        | 0.967       | 0.967    | 0.967 | 1.000           | -                      | 61     | 59             |
| all             | distributed   | 61      | 61      | 52        | 0.852       | 0.852    | 0.852 | 1.000           | -                      | 59     | 50             |
| all             | complex       | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| all             | contradictory | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| all             | all           | 305     | 305     | 293       | 0.961       | 0.961    | 0.961 | 1.000           | -                      | 234    | 222            |
| condition       | explicit      | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | -                      | 38     | 37             |
| condition       | paraphrased   | 61      | 61      | 59        | 0.967       | 0.967    | 0.967 | 1.000           | -                      | 61     | 59             |
| condition       | distributed   | 61      | 61      | 52        | 0.852       | 0.852    | 0.852 | 1.000           | -                      | 59     | 50             |
| condition       | complex       | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| condition       | contradictory | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| condition       | all           | 305     | 305     | 293       | 0.961       | 0.961    | 0.961 | 1.000           | -                      | 234    | 222            |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds         |
|---------|---------------|-------------------|-----------------|-----------------|
| 100     | 176 [1.760]   | 168924 [1689.240] | 30178 [301.780] | 753.897 [7.539] |

Re-execution stability: not measured.

## llm_measurement@1#5212fc43026f

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 61      | 61      | 56        | 0.918       | 0.918    | 0.918 | 1.000           | -                      | 53     | 48             |
| all             | paraphrased   | 57      | 61      | 57        | 1.000       | 0.934    | 0.966 | 1.000           | -                      | 57     | 57             |
| all             | distributed   | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| all             | complex       | 280     | 300     | 268       | 0.957       | 0.893    | 0.924 | 1.000           | -                      | 39     | 27             |
| all             | contradictory | 71      | 61      | 51        | 0.718       | 0.836    | 0.773 | 1.000           | -                      | 29     | 13             |
| all             | all           | 530     | 544     | 493       | 0.930       | 0.906    | 0.918 | 1.000           | -                      | 239    | 206            |
| measurement     | explicit      | 61      | 61      | 56        | 0.918       | 0.918    | 0.918 | 1.000           | 0.982                  | 53     | 48             |
| measurement     | paraphrased   | 57      | 61      | 57        | 1.000       | 0.934    | 0.966 | 1.000           | 0.965                  | 57     | 57             |
| measurement     | distributed   | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | 1.000                  | 61     | 61             |
| measurement     | complex       | 280     | 300     | 268       | 0.957       | 0.893    | 0.924 | 1.000           | 1.000                  | 39     | 27             |
| measurement     | contradictory | 71      | 61      | 51        | 0.718       | 0.836    | 0.773 | 1.000           | 1.000                  | 29     | 13             |
| measurement     | all           | 530     | 544     | 493       | 0.930       | 0.906    | 0.918 | 1.000           | 0.994                  | 239    | 206            |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds           |
|---------|---------------|-------------------|-----------------|-------------------|
| 100     | 200 [2.000]   | 254212 [2542.120] | 90601 [906.010] | 2195.853 [21.959] |

Re-execution stability: not measured.

## llm_metric@1#1ca12a572ef8

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| all             | paraphrased   | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           | -                      | 19     | 19             |
| all             | distributed   | 20      | 20      | 13        | 0.650       | 0.650    | 0.650 | 1.000           | -                      | 12     | 5              |
| all             | complex       | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| all             | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| all             | all           | 129     | 130     | 122       | 0.946       | 0.938    | 0.942 | 1.000           | -                      | 52     | 45             |
| metric          | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| metric          | paraphrased   | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           | -                      | 19     | 19             |
| metric          | distributed   | 20      | 20      | 13        | 0.650       | 0.650    | 0.650 | 1.000           | -                      | 12     | 5              |
| metric          | complex       | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| metric          | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| metric          | all           | 129     | 130     | 122       | 0.946       | 0.938    | 0.942 | 1.000           | -                      | 52     | 45             |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds         |
|---------|---------------|-------------------|-----------------|-----------------|
| 100     | 117 [1.170]   | 113803 [1138.030] | 12495 [124.950] | 335.120 [3.351] |

Re-execution stability: not measured.

## llm_screen@1#6bec6abaf6a0

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1   | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------|---------|---------|-----------|-------------|----------|------|-----------------|------------------------|--------|----------------|

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens    | output_tokens   | seconds         |
|---------|---------------|-----------------|-----------------|-----------------|
| 100     | 100 [1.000]   | 76704 [767.040] | 7735 [77.350]   | 212.899 [2.129] |

Re-execution stability: not measured.

## regex_author_claim@2#b2161f228a8c

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | paraphrased   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | distributed   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | complex       | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | all           | 100     | 100     | 100       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | paraphrased   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | distributed   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | complex       | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | all           | 100     | 100     | 100       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.699 [0.007] |

Re-execution stability: not measured.

## regex_condition@2#80486860164a

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| all             | paraphrased   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed   | 28      | 61      | 11        | 0.393       | 0.180    | 0.247 | 1.000           | -                      | 26     | 9              |
| all             | complex       | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| all             | contradictory | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| all             | all           | 112     | 305     | 80        | 0.714       | 0.262    | 0.384 | 1.000           | -                      | 41     | 9              |
| condition       | explicit      | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| condition       | paraphrased   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| condition       | distributed   | 28      | 61      | 11        | 0.393       | 0.180    | 0.247 | 1.000           | -                      | 26     | 9              |
| condition       | complex       | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| condition       | contradictory | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| condition       | all           | 112     | 305     | 80        | 0.714       | 0.262    | 0.384 | 1.000           | -                      | 41     | 9              |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.697 [0.007] |

Re-execution stability: not measured.

## regex_measurement@2#9edb306c5b05

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | -                      | 5      | 5              |
| all             | paraphrased   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | complex       | 266     | 300     | 253       | 0.951       | 0.843    | 0.894 | 1.000           | -                      | 25     | 12             |
| all             | contradictory | 60      | 61      | 48        | 0.800       | 0.787    | 0.793 | 1.000           | -                      | 18     | 10             |
| all             | all           | 339     | 544     | 314       | 0.926       | 0.577    | 0.711 | 1.000           | -                      | 48     | 27             |
| measurement     | explicit      | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | 1.000                  | 5      | 5              |
| measurement     | paraphrased   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | distributed   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | complex       | 266     | 300     | 253       | 0.951       | 0.843    | 0.894 | 1.000           | 1.000                  | 25     | 12             |
| measurement     | contradictory | 60      | 61      | 48        | 0.800       | 0.787    | 0.793 | 1.000           | 1.000                  | 18     | 10             |
| measurement     | all           | 339     | 544     | 314       | 0.926       | 0.577    | 0.711 | 1.000           | 1.000                  | 48     | 27             |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 1.608 [0.016] |

Re-execution stability: not measured.

## regex_metric@2#67f41f33eff7

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| all             | paraphrased   | 0       | 20      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed   | 18      | 20      | 15        | 0.833       | 0.750    | 0.789 | 1.000           | -                      | 10     | 7              |
| all             | complex       | 48      | 50      | 43        | 0.896       | 0.860    | 0.878 | 1.000           | -                      | 5      | 0              |
| all             | contradictory | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| all             | all           | 102     | 130     | 84        | 0.824       | 0.646    | 0.724 | 1.000           | -                      | 25     | 7              |
| metric          | explicit      | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| metric          | paraphrased   | 0       | 20      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| metric          | distributed   | 18      | 20      | 15        | 0.833       | 0.750    | 0.789 | 1.000           | -                      | 10     | 7              |
| metric          | complex       | 48      | 50      | 43        | 0.896       | 0.860    | 0.878 | 1.000           | -                      | 5      | 0              |
| metric          | contradictory | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| metric          | all           | 102     | 130     | 84        | 0.824       | 0.646    | 0.724 | 1.000           | -                      | 25     | 7              |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.701 [0.007] |

Re-execution stability: not measured.

## regex_screen@1#8301b6896dc3

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1   | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------|---------|---------|-----------|-------------|----------|------|-----------------|------------------------|--------|----------------|

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.709 [0.007] |

Re-execution stability: not measured.
