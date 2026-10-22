# Extractor benchmark

Per extractor id (B11), pooled over the reports given; an item counts for every extractor in its `found_by`. Recall is against the facts of the documents and types the extractor was called on (its extractor_call events; `called`), or every fact of the type and level for a run without events (`all_facts`).

## llm_author_claim@1#be3c17081ff9

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

Pooled F1 (cluster bootstrap over parent studies): 1.000 [n/a] (-, 20 clusters).

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens    | output_tokens   | seconds         |
|---------|---------------|-----------------|-----------------|-----------------|
| 100     | 100 [1.000]   | 87804 [878.040] | 11906 [119.060] | 298.830 [2.988] |

Re-execution stability: not measured.

## llm_condition@1#45b3761c700e

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

Pooled F1 (cluster bootstrap over parent studies): 0.961 [0.93, 0.98] (BCa, 20 clusters).

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds         |
|---------|---------------|-------------------|-----------------|-----------------|
| 100     | 177 [1.770]   | 170124 [1701.240] | 30277 [302.770] | 732.590 [7.326] |

Re-execution stability: not measured.

## llm_measurement@1#02bd5a7ab104

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

Pooled F1 (cluster bootstrap over parent studies): 0.918 [0.87, 0.95] (BCa, 20 clusters).

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds           |
|---------|---------------|-------------------|-----------------|-------------------|
| 100     | 200 [2.000]   | 254136 [2541.360] | 90582 [905.820] | 2163.799 [21.638] |

Re-execution stability: not measured.

## llm_metric@1#41e1e53a1fc4

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| all             | paraphrased   | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           | -                      | 19     | 19             |
| all             | distributed   | 20      | 20      | 14        | 0.700       | 0.700    | 0.700 | 1.000           | -                      | 11     | 5              |
| all             | complex       | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| all             | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| all             | all           | 129     | 130     | 123       | 0.953       | 0.946    | 0.950 | 1.000           | -                      | 51     | 45             |
| metric          | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| metric          | paraphrased   | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           | -                      | 19     | 19             |
| metric          | distributed   | 20      | 20      | 14        | 0.700       | 0.700    | 0.700 | 1.000           | -                      | 11     | 5              |
| metric          | complex       | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| metric          | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| metric          | all           | 129     | 130     | 123       | 0.953       | 0.946    | 0.950 | 1.000           | -                      | 51     | 45             |

Pooled F1 (cluster bootstrap over parent studies): 0.950 [0.92, 0.98] (BCa, 20 clusters).

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds         |
|---------|---------------|-------------------|-----------------|-----------------|
| 100     | 116 [1.160]   | 112866 [1128.660] | 12429 [124.290] | 327.547 [3.275] |

Re-execution stability: not measured.

## llm_screen@1#41b0d6e6793f

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1   | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------|---------|---------|-----------|-------------|----------|------|-----------------|------------------------|--------|----------------|

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens    | output_tokens   | seconds         |
|---------|---------------|-----------------|-----------------|-----------------|
| 100     | 100 [1.000]   | 76704 [767.040] | 7886 [78.860]   | 212.827 [2.128] |

Re-execution stability: not measured.

## regex_author_claim@2#fd7877790c48

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

Pooled F1 (cluster bootstrap over parent studies): 1.000 [n/a] (-, 20 clusters).

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.721 [0.007] |

Re-execution stability: not measured.

## regex_condition@2#0a5bf730763c

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

Pooled F1 (cluster bootstrap over parent studies): 0.384 [0.29, 0.46] (BCa, 20 clusters).

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.718 [0.007] |

Re-execution stability: not measured.

## regex_measurement@2#e2d17eb260ea

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

Pooled F1 (cluster bootstrap over parent studies): 0.711 [0.65, 0.75] (BCa, 20 clusters).

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 1.660 [0.017] |

Re-execution stability: not measured.

## regex_metric@2#0affe2d9ce77

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| all             | paraphrased   | 0       | 20      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed   | 18      | 20      | 15        | 0.833       | 0.750    | 0.789 | 1.000           | -                      | 9      | 6              |
| all             | complex       | 48      | 50      | 43        | 0.896       | 0.860    | 0.878 | 1.000           | -                      | 5      | 0              |
| all             | contradictory | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| all             | all           | 102     | 130     | 84        | 0.824       | 0.646    | 0.724 | 1.000           | -                      | 24     | 6              |
| metric          | explicit      | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| metric          | paraphrased   | 0       | 20      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| metric          | distributed   | 18      | 20      | 15        | 0.833       | 0.750    | 0.789 | 1.000           | -                      | 9      | 6              |
| metric          | complex       | 48      | 50      | 43        | 0.896       | 0.860    | 0.878 | 1.000           | -                      | 5      | 0              |
| metric          | contradictory | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| metric          | all           | 102     | 130     | 84        | 0.824       | 0.646    | 0.724 | 1.000           | -                      | 24     | 6              |

Pooled F1 (cluster bootstrap over parent studies): 0.724 [0.58, 0.83] (BCa, 20 clusters).

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.719 [0.007] |

Re-execution stability: not measured.

## regex_screen@1#858a6ebc69c6

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1   | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------|---------|---------|-----------|-------------|----------|------|-----------------|------------------------|--------|----------------|

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.722 [0.007] |

Re-execution stability: not measured.
