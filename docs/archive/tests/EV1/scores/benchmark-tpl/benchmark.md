# Extractor benchmark

Per extractor id (B11), pooled over the reports given; an item counts for every extractor in its `found_by`. Recall is against the facts of the documents and types the extractor was called on (its extractor_call events; `called`), or every fact of the type and level for a run without events (`all_facts`).

## llm_author_claim@1#32acd8d697c8

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | paraphrased   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | distributed   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | complex       | 20      | 20      | 19        | 0.950       | 0.950    | 0.950 | 1.000           | -                      | 1      | 0              |
| all             | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | all           | 100     | 100     | 99        | 0.990       | 0.990    | 0.990 | 1.000           | -                      | 1      | 0              |
| author_claim    | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | paraphrased   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | distributed   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | complex       | 20      | 20      | 19        | 0.950       | 0.950    | 0.950 | 1.000           | -                      | 1      | 0              |
| author_claim    | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | all           | 100     | 100     | 99        | 0.990       | 0.990    | 0.990 | 1.000           | -                      | 1      | 0              |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens    | output_tokens   | seconds        |
|---------|---------------|-----------------|-----------------|----------------|
| 100     | 100 [1.000]   | 83440 [834.400] | 5825 [58.250]   | 54.582 [0.546] |

Re-execution stability: not measured.

## llm_condition@1#6c050a1add96

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | -                      | 38     | 37             |
| all             | paraphrased   | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| all             | distributed   | 61      | 61      | 53        | 0.869       | 0.869    | 0.869 | 1.000           | -                      | 61     | 53             |
| all             | complex       | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| all             | contradictory | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| all             | all           | 305     | 305     | 296       | 0.970       | 0.970    | 0.970 | 1.000           | -                      | 236    | 227            |
| condition       | explicit      | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | -                      | 38     | 37             |
| condition       | paraphrased   | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| condition       | distributed   | 61      | 61      | 53        | 0.869       | 0.869    | 0.869 | 1.000           | -                      | 61     | 53             |
| condition       | complex       | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| condition       | contradictory | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| condition       | all           | 305     | 305     | 296       | 0.970       | 0.970    | 0.970 | 1.000           | -                      | 236    | 227            |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds         |
|---------|---------------|-------------------|-----------------|-----------------|
| 100     | 197 [1.970]   | 179962 [1799.620] | 29389 [293.890] | 251.551 [2.516] |

Re-execution stability: not measured.

## llm_measurement@1#88dd1e73d7e2

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 61      | 61      | 56        | 0.918       | 0.918    | 0.918 | 1.000           | -                      | 53     | 48             |
| all             | paraphrased   | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | -                      | 61     | 60             |
| all             | distributed   | 49      | 61      | 49        | 1.000       | 0.803    | 0.891 | 1.000           | -                      | 49     | 49             |
| all             | complex       | 94      | 300     | 81        | 0.862       | 0.270    | 0.411 | 1.000           | -                      | 28     | 15             |
| all             | contradictory | 56      | 61      | 45        | 0.804       | 0.738    | 0.769 | 1.000           | -                      | 24     | 13             |
| all             | all           | 321     | 544     | 291       | 0.907       | 0.535    | 0.673 | 1.000           | -                      | 215    | 185            |
| measurement     | explicit      | 61      | 61      | 56        | 0.918       | 0.918    | 0.918 | 1.000           | 0.982                  | 53     | 48             |
| measurement     | paraphrased   | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | 1.000                  | 61     | 60             |
| measurement     | distributed   | 49      | 61      | 49        | 1.000       | 0.803    | 0.891 | 1.000           | 1.000                  | 49     | 49             |
| measurement     | complex       | 94      | 300     | 81        | 0.862       | 0.270    | 0.411 | 1.000           | 1.000                  | 28     | 15             |
| measurement     | contradictory | 56      | 61      | 45        | 0.804       | 0.738    | 0.769 | 1.000           | 1.000                  | 24     | 13             |
| measurement     | all           | 321     | 544     | 291       | 0.907       | 0.535    | 0.673 | 1.000           | 0.997                  | 215    | 185            |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds         |
|---------|---------------|-------------------|-----------------|-----------------|
| 100     | 200 [2.000]   | 235967 [2359.670] | 59941 [599.410] | 470.838 [4.708] |

Re-execution stability: not measured.

## llm_metric@1#8c11f22c1357

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| all             | paraphrased   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| all             | distributed   | 9       | 20      | 1         | 0.111       | 0.050    | 0.069 | 1.000           | -                      | 9      | 1              |
| all             | complex       | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| all             | contradictory | 21      | 20      | 20        | 0.952       | 1.000    | 0.976 | 1.000           | -                      | 8      | 7              |
| all             | all           | 120     | 130     | 111       | 0.925       | 0.854    | 0.888 | 1.000           | -                      | 51     | 42             |
| metric          | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| metric          | paraphrased   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| metric          | distributed   | 9       | 20      | 1         | 0.111       | 0.050    | 0.069 | 1.000           | -                      | 9      | 1              |
| metric          | complex       | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| metric          | contradictory | 21      | 20      | 20        | 0.952       | 1.000    | 0.976 | 1.000           | -                      | 8      | 7              |
| metric          | all           | 120     | 130     | 111       | 0.925       | 0.854    | 0.888 | 1.000           | -                      | 51     | 42             |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds         |
|---------|---------------|-------------------|-----------------|-----------------|
| 100     | 180 [1.800]   | 159559 [1595.590] | 15671 [156.710] | 136.896 [1.369] |

Re-execution stability: not measured.

## regex_author_claim@1#120eee2396ac

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | paraphrased   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | distributed   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | complex       | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| all             | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | all           | 100     | 100     | 100       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| author_claim    | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | paraphrased   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | distributed   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | complex       | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| author_claim    | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | all           | 100     | 100     | 100       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.722 [0.007] |

Re-execution stability: not measured.

## regex_condition@1#3a430bcceb1d

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| all             | paraphrased   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed   | 28      | 61      | 8         | 0.286       | 0.131    | 0.180 | 1.000           | -                      | 28     | 8              |
| all             | complex       | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| all             | contradictory | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| all             | all           | 112     | 305     | 77        | 0.688       | 0.252    | 0.369 | 1.000           | -                      | 43     | 8              |
| condition       | explicit      | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| condition       | paraphrased   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| condition       | distributed   | 28      | 61      | 8         | 0.286       | 0.131    | 0.180 | 1.000           | -                      | 28     | 8              |
| condition       | complex       | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| condition       | contradictory | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| condition       | all           | 112     | 305     | 77        | 0.688       | 0.252    | 0.369 | 1.000           | -                      | 43     | 8              |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.717 [0.007] |

Re-execution stability: not measured.

## regex_measurement@1#786857ce00b2

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | -                      | 5      | 5              |
| all             | paraphrased   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | complex       | 266     | 300     | 258       | 0.970       | 0.860    | 0.912 | 1.000           | -                      | 200    | 192            |
| all             | contradictory | 60      | 61      | 48        | 0.800       | 0.787    | 0.793 | 1.000           | -                      | 28     | 16             |
| all             | all           | 339     | 544     | 319       | 0.941       | 0.586    | 0.723 | 1.000           | -                      | 233    | 213            |
| measurement     | explicit      | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | 1.000                  | 5      | 5              |
| measurement     | paraphrased   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | distributed   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | complex       | 266     | 300     | 258       | 0.970       | 0.860    | 0.912 | 1.000           | 1.000                  | 200    | 192            |
| measurement     | contradictory | 60      | 61      | 48        | 0.800       | 0.787    | 0.793 | 1.000           | 1.000                  | 28     | 16             |
| measurement     | all           | 339     | 544     | 319       | 0.941       | 0.586    | 0.723 | 1.000           | 1.000                  | 233    | 213            |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 1.641 [0.016] |

Re-execution stability: not measured.

## regex_metric@1#f052f9d6cba0

Corpora: rag-tpl-s1-59c5118b (run rag-tpl-s1-explicit, recall scope called), rag-tpl-s1-4d15ddc4 (run rag-tpl-s1-paraphrased, recall scope called), rag-tpl-s1-79207ad1 (run rag-tpl-s1-distributed, recall scope called), rag-tpl-s1-f0f5d48e (run rag-tpl-s1-complex, recall scope called), rag-tpl-s1-56b0bc02 (run rag-tpl-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| all             | paraphrased   | 0       | 20      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed   | 18      | 20      | 17        | 0.944       | 0.850    | 0.895 | 1.000           | -                      | 18     | 17             |
| all             | complex       | 48      | 50      | 43        | 0.896       | 0.860    | 0.878 | 1.000           | -                      | 5      | 0              |
| all             | contradictory | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| all             | all           | 102     | 130     | 86        | 0.843       | 0.662    | 0.741 | 1.000           | -                      | 33     | 17             |
| metric          | explicit      | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| metric          | paraphrased   | 0       | 20      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| metric          | distributed   | 18      | 20      | 17        | 0.944       | 0.850    | 0.895 | 1.000           | -                      | 18     | 17             |
| metric          | complex       | 48      | 50      | 43        | 0.896       | 0.860    | 0.878 | 1.000           | -                      | 5      | 0              |
| metric          | contradictory | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| metric          | all           | 102     | 130     | 86        | 0.843       | 0.662    | 0.741 | 1.000           | -                      | 33     | 17             |

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.721 [0.007] |

Re-execution stability: not measured.
