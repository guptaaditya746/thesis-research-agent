# Extractor benchmark

Per extractor id (B11), pooled over the reports given; an item counts for every extractor in its `found_by`. Recall is against the facts of the documents and types the extractor was called on (its extractor_call events; `called`), or every fact of the type and level for a run without events (`all_facts`).

## agentic@1#0f2927b8a64c

Corpora: rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | paraphrased | 2       | 12      | 2         | 1.000       | 0.167    | 0.286 | 1.000           | -                      | 0      | 0              |
| all             | distributed | 2       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 2      | 0              |
| all             | all         | 4       | 24      | 2         | 0.500       | 0.083    | 0.143 | 1.000           | -                      | 2      | 0              |
| condition       | paraphrased | 2       | 12      | 2         | 1.000       | 0.167    | 0.286 | 1.000           | -                      | 0      | 0              |
| condition       | distributed | 2       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 2      | 0              |
| condition       | all         | 4       | 24      | 2         | 0.500       | 0.083    | 0.143 | 1.000           | -                      | 2      | 0              |

Pooled F1 (cluster bootstrap over parent studies): 0.143 [0.00, 0.50] (BCa, 5 clusters).

Cost over 2 run(s), 10 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens       | output_tokens    | seconds            |
|---------|---------------|--------------------|------------------|--------------------|
| 10      | 133 [13.300]  | 955191 [95519.100] | 46689 [4668.900] | 1634.810 [163.481] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 20      | 11          | 0.550             | 14               | 7                  | 0.500            |

## agentic@1#534f8c43c9f0

Corpora: rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | paraphrased | 1       | 5       | 1         | 1.000       | 0.200    | 0.333 | 1.000           | -                      | 0      | 0              |
| all             | distributed | 3       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 3      | 0              |
| all             | all         | 4       | 10      | 1         | 0.250       | 0.100    | 0.143 | 1.000           | -                      | 3      | 0              |
| metric          | paraphrased | 1       | 5       | 1         | 1.000       | 0.200    | 0.333 | 1.000           | -                      | 0      | 0              |
| metric          | distributed | 3       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 3      | 0              |
| metric          | all         | 4       | 10      | 1         | 0.250       | 0.100    | 0.143 | 1.000           | -                      | 3      | 0              |

Pooled F1 (cluster bootstrap over parent studies): 0.143 [0.00, 0.53] (BCa, 5 clusters).

Cost over 2 run(s), 10 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens         | output_tokens    | seconds            |
|---------|---------------|----------------------|------------------|--------------------|
| 10      | 186 [18.600]  | 1490103 [149010.300] | 56964 [5696.400] | 2042.444 [204.244] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 20      | 11          | 0.550             | 14               | 7                  | 0.500            |

## agentic@1#5eefe3bb3cec

Corpora: rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | paraphrased | 0       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed | 1       | 5       | 1         | 1.000       | 0.200    | 0.333 | 1.000           | -                      | 0      | 0              |
| all             | all         | 1       | 10      | 1         | 1.000       | 0.100    | 0.182 | 1.000           | -                      | 0      | 0              |
| author_claim    | paraphrased | 0       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| author_claim    | distributed | 1       | 5       | 1         | 1.000       | 0.200    | 0.333 | 1.000           | -                      | 0      | 0              |
| author_claim    | all         | 1       | 10      | 1         | 1.000       | 0.100    | 0.182 | 1.000           | -                      | 0      | 0              |

Pooled F1 (cluster bootstrap over parent studies): 0.182 [0.00, 0.57] (BCa, 5 clusters).

Cost over 2 run(s), 10 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens       | output_tokens    | seconds            |
|---------|---------------|--------------------|------------------|--------------------|
| 10      | 114 [11.400]  | 696437 [69643.700] | 33246 [3324.600] | 1089.052 [108.905] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 20      | 11          | 0.550             | 14               | 7                  | 0.500            |

## agentic@1#6d79f0c0b881

Corpora: rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | paraphrased | 2       | 12      | 2         | 1.000       | 0.167    | 0.286 | 1.000           | -                      | 0      | 0              |
| all             | distributed | 8       | 12      | 8         | 1.000       | 0.667    | 0.800 | 1.000           | -                      | 1      | 1              |
| all             | all         | 10      | 24      | 10        | 1.000       | 0.417    | 0.588 | 1.000           | -                      | 1      | 1              |
| measurement     | paraphrased | 2       | 12      | 2         | 1.000       | 0.167    | 0.286 | 1.000           | 1.000                  | 0      | 0              |
| measurement     | distributed | 8       | 12      | 8         | 1.000       | 0.667    | 0.800 | 1.000           | 1.000                  | 1      | 1              |
| measurement     | all         | 10      | 24      | 10        | 1.000       | 0.417    | 0.588 | 1.000           | 1.000                  | 1      | 1              |

Pooled F1 (cluster bootstrap over parent studies): 0.588 [0.18, 0.81] (BCa, 5 clusters).

Cost over 2 run(s), 10 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens         | output_tokens    | seconds            |
|---------|---------------|----------------------|------------------|--------------------|
| 10      | 141 [14.100]  | 1047693 [104769.300] | 60721 [6072.100] | 2078.186 [207.819] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 20      | 11          | 0.550             | 14               | 7                  | 0.500            |

## llm_author_claim@1#be3c17081ff9

Corpora: rag-claude-s1-eb14377d (run rag-claude-s1-explicit, recall scope called), rag-claude-s1-c34803f0 (run rag-claude-s1-paraphrased, recall scope called), rag-claude-s1-869ad7e8 (run rag-claude-s1-distributed, recall scope called), rag-claude-s1-a5fa1731 (run rag-claude-s1-complex, recall scope called), rag-claude-s1-e4e9d603 (run rag-claude-s1-contradictory, recall scope called), rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | paraphrased   | 25      | 25      | 25        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | distributed   | 25      | 25      | 25        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | complex       | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | all           | 110     | 110     | 110       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | paraphrased   | 25      | 25      | 25        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | distributed   | 25      | 25      | 25        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | complex       | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | all           | 110     | 110     | 110       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |

Pooled F1 (cluster bootstrap over parent studies): 1.000 [n/a] (-, 25 clusters).

Cost over 7 run(s), 110 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds         |
|---------|---------------|-------------------|-----------------|-----------------|
| 110     | 110 [1.000]   | 117116 [1064.691] | 13074 [118.855] | 287.202 [2.611] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 45      | 45          | 1.000             | 45               | 45                 | 1.000            |

## llm_condition@1#45b3761c700e

Corpora: rag-claude-s1-eb14377d (run rag-claude-s1-explicit, recall scope called), rag-claude-s1-c34803f0 (run rag-claude-s1-paraphrased, recall scope called), rag-claude-s1-869ad7e8 (run rag-claude-s1-distributed, recall scope called), rag-claude-s1-a5fa1731 (run rag-claude-s1-complex, recall scope called), rag-claude-s1-e4e9d603 (run rag-claude-s1-contradictory, recall scope called), rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           | -                      | 39     | 35             |
| all             | paraphrased   | 73      | 73      | 69        | 0.945       | 0.945    | 0.945 | 1.000           | -                      | 71     | 67             |
| all             | distributed   | 73      | 73      | 64        | 0.877       | 0.877    | 0.877 | 1.000           | -                      | 58     | 49             |
| all             | complex       | 61      | 61      | 58        | 0.951       | 0.951    | 0.951 | 1.000           | -                      | 38     | 35             |
| all             | contradictory | 61      | 61      | 58        | 0.951       | 0.951    | 0.951 | 1.000           | -                      | 40     | 37             |
| all             | all           | 329     | 329     | 306       | 0.930       | 0.930    | 0.930 | 1.000           | -                      | 246    | 223            |
| condition       | explicit      | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           | -                      | 39     | 35             |
| condition       | paraphrased   | 73      | 73      | 69        | 0.945       | 0.945    | 0.945 | 1.000           | -                      | 71     | 67             |
| condition       | distributed   | 73      | 73      | 64        | 0.877       | 0.877    | 0.877 | 1.000           | -                      | 58     | 49             |
| condition       | complex       | 61      | 61      | 58        | 0.951       | 0.951    | 0.951 | 1.000           | -                      | 38     | 35             |
| condition       | contradictory | 61      | 61      | 58        | 0.951       | 0.951    | 0.951 | 1.000           | -                      | 40     | 37             |
| condition       | all           | 329     | 329     | 306       | 0.930       | 0.930    | 0.930 | 1.000           | -                      | 246    | 223            |

Pooled F1 (cluster bootstrap over parent studies): 0.930 [0.83, 0.97] (BCa, 25 clusters).

Cost over 7 run(s), 110 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds         |
|---------|---------------|-------------------|-----------------|-----------------|
| 110     | 151 [1.373]   | 171637 [1560.336] | 28030 [254.818] | 597.294 [5.430] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 45      | 43          | 0.956             | 134              | 134                | 1.000            |

## llm_measurement@1#02bd5a7ab104

Corpora: rag-claude-s1-eb14377d (run rag-claude-s1-explicit, recall scope called), rag-claude-s1-c34803f0 (run rag-claude-s1-paraphrased, recall scope called), rag-claude-s1-869ad7e8 (run rag-claude-s1-distributed, recall scope called), rag-claude-s1-a5fa1731 (run rag-claude-s1-complex, recall scope called), rag-claude-s1-e4e9d603 (run rag-claude-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 61      | 61      | 56        | 0.918       | 0.918    | 0.918 | 1.000           | -                      | 45     | 40             |
| all             | paraphrased   | 35      | 61      | 35        | 1.000       | 0.574    | 0.729 | 1.000           | -                      | 35     | 35             |
| all             | distributed   | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| all             | complex       | 287     | 300     | 276       | 0.962       | 0.920    | 0.940 | 1.000           | -                      | 46     | 35             |
| all             | contradictory | 68      | 61      | 53        | 0.779       | 0.869    | 0.822 | 1.000           | -                      | 28     | 15             |
| all             | all           | 512     | 544     | 481       | 0.939       | 0.884    | 0.911 | 1.000           | -                      | 215    | 186            |
| measurement     | explicit      | 61      | 61      | 56        | 0.918       | 0.918    | 0.918 | 1.000           | 0.929                  | 45     | 40             |
| measurement     | paraphrased   | 35      | 61      | 35        | 1.000       | 0.574    | 0.729 | 1.000           | 0.914                  | 35     | 35             |
| measurement     | distributed   | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | 0.934                  | 61     | 61             |
| measurement     | complex       | 287     | 300     | 276       | 0.962       | 0.920    | 0.940 | 1.000           | 0.949                  | 46     | 35             |
| measurement     | contradictory | 68      | 61      | 53        | 0.779       | 0.869    | 0.822 | 1.000           | 0.943                  | 28     | 15             |
| measurement     | all           | 512     | 544     | 481       | 0.939       | 0.884    | 0.911 | 1.000           | 0.942                  | 215    | 186            |

Pooled F1 (cluster bootstrap over parent studies): 0.911 [0.88, 0.94] (BCa, 20 clusters).

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds           |
|---------|---------------|-------------------|-----------------|-------------------|
| 100     | 200 [2.000]   | 288397 [2883.970] | 90711 [907.110] | 1805.661 [18.057] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 40      | 40          | 1.000             | 122              | 122                | 1.000            |

## llm_measurement@1#73fb3d141605

Corpora: rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | paraphrased | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 10     | 10             |
| all             | distributed | 12      | 12      | 11        | 0.917       | 0.917    | 0.917 | 1.000           | -                      | 5      | 4              |
| all             | all         | 24      | 24      | 23        | 0.958       | 0.958    | 0.958 | 1.000           | -                      | 15     | 14             |
| measurement     | paraphrased | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | 0.917                  | 10     | 10             |
| measurement     | distributed | 12      | 12      | 11        | 0.917       | 0.917    | 0.917 | 1.000           | 1.000                  | 5      | 4              |
| measurement     | all         | 24      | 24      | 23        | 0.958       | 0.958    | 0.958 | 1.000           | 0.957                  | 15     | 14             |

Pooled F1 (cluster bootstrap over parent studies): 0.958 [0.85, 1.00] (BCa, 5 clusters).

Cost over 2 run(s), 10 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens     | output_tokens   | seconds          |
|---------|---------------|------------------|-----------------|------------------|
| 10      | 20 [2.000]    | 29295 [2929.500] | 5670 [567.000]  | 204.743 [20.474] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 5       | 2           | 0.400             | 12               | 4                  | 0.333            |

## llm_metric@1#41e1e53a1fc4

Corpora: rag-claude-s1-eb14377d (run rag-claude-s1-explicit, recall scope called), rag-claude-s1-c34803f0 (run rag-claude-s1-paraphrased, recall scope called), rag-claude-s1-869ad7e8 (run rag-claude-s1-distributed, recall scope called), rag-claude-s1-a5fa1731 (run rag-claude-s1-complex, recall scope called), rag-claude-s1-e4e9d603 (run rag-claude-s1-contradictory, recall scope called), rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           | -                      | 7      | 7              |
| all             | paraphrased   | 17      | 25      | 17        | 1.000       | 0.680    | 0.810 | 1.000           | -                      | 16     | 16             |
| all             | distributed   | 25      | 25      | 23        | 0.920       | 0.920    | 0.920 | 1.000           | -                      | 13     | 11             |
| all             | complex       | 49      | 50      | 49        | 1.000       | 0.980    | 0.990 | 1.000           | -                      | 7      | 7              |
| all             | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| all             | all           | 130     | 140     | 128       | 0.985       | 0.914    | 0.948 | 1.000           | -                      | 50     | 48             |
| metric          | explicit      | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           | -                      | 7      | 7              |
| metric          | paraphrased   | 17      | 25      | 17        | 1.000       | 0.680    | 0.810 | 1.000           | -                      | 16     | 16             |
| metric          | distributed   | 25      | 25      | 23        | 0.920       | 0.920    | 0.920 | 1.000           | -                      | 13     | 11             |
| metric          | complex       | 49      | 50      | 49        | 1.000       | 0.980    | 0.990 | 1.000           | -                      | 7      | 7              |
| metric          | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| metric          | all           | 130     | 140     | 128       | 0.985       | 0.914    | 0.948 | 1.000           | -                      | 50     | 48             |

Pooled F1 (cluster bootstrap over parent studies): 0.948 [0.91, 0.97] (BCa, 25 clusters).

Cost over 7 run(s), 110 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds         |
|---------|---------------|-------------------|-----------------|-----------------|
| 110     | 131 [1.191]   | 151768 [1379.709] | 13286 [120.782] | 302.548 [2.750] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 45      | 45          | 1.000             | 44               | 44                 | 1.000            |

## llm_screen@1#41b0d6e6793f

Corpora: rag-claude-s1-eb14377d (run rag-claude-s1-explicit, recall scope called), rag-claude-s1-c34803f0 (run rag-claude-s1-paraphrased, recall scope called), rag-claude-s1-869ad7e8 (run rag-claude-s1-distributed, recall scope called), rag-claude-s1-a5fa1731 (run rag-claude-s1-complex, recall scope called), rag-claude-s1-e4e9d603 (run rag-claude-s1-contradictory, recall scope called), rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1   | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------|---------|---------|-----------|-------------|----------|------|-----------------|------------------------|--------|----------------|

Cost over 7 run(s), 110 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens     | output_tokens   | seconds         |
|---------|---------------|------------------|-----------------|-----------------|
| 110     | 110 [1.000]   | 106982 [972.564] | 11039 [100.355] | 260.956 [2.372] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 45      | 38          | 0.844             | 45               | 39                 | 0.867            |

## regex_author_claim@2#fd7877790c48

Corpora: rag-claude-s1-eb14377d (run rag-claude-s1-explicit, recall scope called), rag-claude-s1-c34803f0 (run rag-claude-s1-paraphrased, recall scope called), rag-claude-s1-869ad7e8 (run rag-claude-s1-distributed, recall scope called), rag-claude-s1-a5fa1731 (run rag-claude-s1-complex, recall scope called), rag-claude-s1-e4e9d603 (run rag-claude-s1-contradictory, recall scope called), rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | paraphrased   | 25      | 25      | 25        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | distributed   | 25      | 25      | 25        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | complex       | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | all           | 110     | 110     | 110       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | explicit      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | paraphrased   | 25      | 25      | 25        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | distributed   | 25      | 25      | 25        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | complex       | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | all           | 110     | 110     | 110       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |

Pooled F1 (cluster bootstrap over parent studies): 1.000 [n/a] (-, 25 clusters).

Cost over 7 run(s), 110 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 110     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.901 [0.008] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 45      | 45          | 1.000             | 45               | 45                 | 1.000            |

## regex_condition@2#0a5bf730763c

Corpora: rag-claude-s1-eb14377d (run rag-claude-s1-explicit, recall scope called), rag-claude-s1-c34803f0 (run rag-claude-s1-paraphrased, recall scope called), rag-claude-s1-869ad7e8 (run rag-claude-s1-distributed, recall scope called), rag-claude-s1-a5fa1731 (run rag-claude-s1-complex, recall scope called), rag-claude-s1-e4e9d603 (run rag-claude-s1-contradictory, recall scope called), rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 28      | 61      | 22        | 0.786       | 0.361    | 0.494 | 1.000           | -                      | 6      | 0              |
| all             | paraphrased   | 0       | 73      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed   | 37      | 73      | 20        | 0.541       | 0.274    | 0.364 | 1.000           | -                      | 22     | 5              |
| all             | complex       | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| all             | contradictory | 28      | 61      | 21        | 0.750       | 0.344    | 0.472 | 1.000           | -                      | 7      | 0              |
| all             | all           | 121     | 329     | 86        | 0.711       | 0.261    | 0.382 | 1.000           | -                      | 40     | 5              |
| condition       | explicit      | 28      | 61      | 22        | 0.786       | 0.361    | 0.494 | 1.000           | -                      | 6      | 0              |
| condition       | paraphrased   | 0       | 73      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| condition       | distributed   | 37      | 73      | 20        | 0.541       | 0.274    | 0.364 | 1.000           | -                      | 22     | 5              |
| condition       | complex       | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| condition       | contradictory | 28      | 61      | 21        | 0.750       | 0.344    | 0.472 | 1.000           | -                      | 7      | 0              |
| condition       | all           | 121     | 329     | 86        | 0.711       | 0.261    | 0.382 | 1.000           | -                      | 40     | 5              |

Pooled F1 (cluster bootstrap over parent studies): 0.382 [0.29, 0.48] (BCa, 25 clusters).

Cost over 7 run(s), 110 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 110     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.859 [0.008] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 45      | 45          | 1.000             | 65               | 65                 | 1.000            |

## regex_measurement@2#5388637fb767

Corpora: rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | paraphrased | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | all         | 0       | 24      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | paraphrased | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | distributed | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | all         | 0       | 24      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |

Pooled F1 (cluster bootstrap over parent studies): 0.000 [n/a] (-, 5 clusters).

Cost over 2 run(s), 10 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 10      | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.174 [0.017] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 5       | 5           | 1.000             | 0                | 0                  | -                |

## regex_measurement@2#e2d17eb260ea

Corpora: rag-claude-s1-eb14377d (run rag-claude-s1-explicit, recall scope called), rag-claude-s1-c34803f0 (run rag-claude-s1-paraphrased, recall scope called), rag-claude-s1-869ad7e8 (run rag-claude-s1-distributed, recall scope called), rag-claude-s1-a5fa1731 (run rag-claude-s1-complex, recall scope called), rag-claude-s1-e4e9d603 (run rag-claude-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 24      | 61      | 21        | 0.875       | 0.344    | 0.494 | 1.000           | -                      | 8      | 5              |
| all             | paraphrased   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | complex       | 266     | 300     | 251       | 0.944       | 0.837    | 0.887 | 1.000           | -                      | 25     | 10             |
| all             | contradictory | 60      | 61      | 46        | 0.767       | 0.754    | 0.760 | 1.000           | -                      | 20     | 8              |
| all             | all           | 350     | 544     | 318       | 0.909       | 0.585    | 0.711 | 1.000           | -                      | 53     | 23             |
| measurement     | explicit      | 24      | 61      | 21        | 0.875       | 0.344    | 0.494 | 1.000           | 1.000                  | 8      | 5              |
| measurement     | paraphrased   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | distributed   | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | complex       | 266     | 300     | 251       | 0.944       | 0.837    | 0.887 | 1.000           | 0.944                  | 25     | 10             |
| measurement     | contradictory | 60      | 61      | 46        | 0.767       | 0.754    | 0.760 | 1.000           | 0.957                  | 20     | 8              |
| measurement     | all           | 350     | 544     | 318       | 0.909       | 0.585    | 0.711 | 1.000           | 0.950                  | 53     | 23             |

Pooled F1 (cluster bootstrap over parent studies): 0.711 [0.65, 0.76] (BCa, 20 clusters).

Cost over 5 run(s), 100 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 100     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 1.555 [0.016] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 40      | 40          | 1.000             | 24               | 24                 | 1.000            |

## regex_metric@2#0affe2d9ce77

Corpora: rag-claude-s1-eb14377d (run rag-claude-s1-explicit, recall scope called), rag-claude-s1-c34803f0 (run rag-claude-s1-paraphrased, recall scope called), rag-claude-s1-869ad7e8 (run rag-claude-s1-distributed, recall scope called), rag-claude-s1-a5fa1731 (run rag-claude-s1-complex, recall scope called), rag-claude-s1-e4e9d603 (run rag-claude-s1-contradictory, recall scope called), rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 22      | 20      | 13        | 0.591       | 0.650    | 0.619 | 1.000           | -                      | 10     | 1              |
| all             | paraphrased   | 3       | 25      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 3      | 0              |
| all             | distributed   | 22      | 25      | 14        | 0.636       | 0.560    | 0.596 | 1.000           | -                      | 10     | 2              |
| all             | complex       | 50      | 50      | 43        | 0.860       | 0.860    | 0.860 | 1.000           | -                      | 8      | 1              |
| all             | contradictory | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| all             | all           | 115     | 140     | 83        | 0.722       | 0.593    | 0.651 | 1.000           | -                      | 36     | 4              |
| metric          | explicit      | 22      | 20      | 13        | 0.591       | 0.650    | 0.619 | 1.000           | -                      | 10     | 1              |
| metric          | paraphrased   | 3       | 25      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 3      | 0              |
| metric          | distributed   | 22      | 25      | 14        | 0.636       | 0.560    | 0.596 | 1.000           | -                      | 10     | 2              |
| metric          | complex       | 50      | 50      | 43        | 0.860       | 0.860    | 0.860 | 1.000           | -                      | 8      | 1              |
| metric          | contradictory | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| metric          | all           | 115     | 140     | 83        | 0.722       | 0.593    | 0.651 | 1.000           | -                      | 36     | 4              |

Pooled F1 (cluster bootstrap over parent studies): 0.651 [0.51, 0.76] (BCa, 25 clusters).

Cost over 7 run(s), 110 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 110     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.878 [0.008] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 45      | 45          | 1.000             | 44               | 44                 | 1.000            |

## regex_screen@1#858a6ebc69c6

Corpora: rag-claude-s1-eb14377d (run rag-claude-s1-explicit, recall scope called), rag-claude-s1-c34803f0 (run rag-claude-s1-paraphrased, recall scope called), rag-claude-s1-869ad7e8 (run rag-claude-s1-distributed, recall scope called), rag-claude-s1-a5fa1731 (run rag-claude-s1-complex, recall scope called), rag-claude-s1-e4e9d603 (run rag-claude-s1-contradictory, recall scope called), rag-claude-small-5cbb2530 (run rag-claude-small-distributed, recall scope called), rag-claude-small-7eb8078c (run rag-claude-small-paraphrased, recall scope called)

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1   | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------|---------|---------|-----------|-------------|----------|------|-----------------|------------------------|--------|----------------|

Cost over 7 run(s), 110 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 110     | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.853 [0.008] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 45      | 45          | 1.000             | 45               | 45                 | 1.000            |
