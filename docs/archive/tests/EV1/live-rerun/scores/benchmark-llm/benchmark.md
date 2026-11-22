# Extractor benchmark

Per extractor id (B11), pooled over the reports given; an item counts for every extractor in its `found_by`. Recall is against the facts of the documents and types the extractor was called on (its extractor_call events; `called`), or every fact of the type and level for a run without events (`all_facts`).

## agentic@1#0f2927b8a64c

Corpora: rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | paraphrased | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | all         | 0       | 8       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| condition       | paraphrased | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| condition       | distributed | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| condition       | all         | 0       | 8       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |

Cost over 2 run(s), 2 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds           |
|---------|---------------|-------------------|-----------------|-------------------|
| 2       | 17 [8.500]    | 83792 [41896.000] | 7557 [3778.500] | 306.292 [153.146] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 4       | 3           | 0.750             | 0                | 0                  | -                |

## agentic@1#534f8c43c9f0

Corpora: rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | paraphrased | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | all         | 0       | 2       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| metric          | paraphrased | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| metric          | distributed | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| metric          | all         | 0       | 2       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |

Cost over 2 run(s), 2 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds          |
|---------|---------------|-------------------|-----------------|------------------|
| 2       | 21 [10.500]   | 93968 [46984.000] | 5101 [2550.500] | 162.506 [81.253] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 4       | 3           | 0.750             | 0                | 0                  | -                |

## agentic@1#5eefe3bb3cec

Corpora: rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | paraphrased | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | all         | 0       | 2       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| author_claim    | paraphrased | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| author_claim    | distributed | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| author_claim    | all         | 0       | 2       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |

Cost over 2 run(s), 2 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens        | output_tokens    | seconds           |
|---------|---------------|---------------------|------------------|-------------------|
| 2       | 43 [21.500]   | 351067 [175533.500] | 10956 [5478.000] | 312.029 [156.014] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 4       | 3           | 0.750             | 0                | 0                  | -                |

## agentic@1#6d79f0c0b881

Corpora: rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | paraphrased | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 0      | 0              |
| all             | distributed | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | all         | 2       | 8       | 2         | 1.000       | 0.250    | 0.400 | 1.000           | -                      | 0      | 0              |
| measurement     | paraphrased | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 1.000           | 1.000                  | 0      | 0              |
| measurement     | distributed | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | all         | 2       | 8       | 2         | 1.000       | 0.250    | 0.400 | 1.000           | 1.000                  | 0      | 0              |

Cost over 2 run(s), 2 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens        | output_tokens     | seconds            |
|---------|---------------|---------------------|-------------------|--------------------|
| 2       | 56 [28.000]   | 789351 [394675.500] | 41004 [20502.000] | 1168.449 [584.225] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 4       | 3           | 0.750             | 0                | 0                  | -                |

## llm_author_claim@1#fefdf4416c50

Corpora: rag-llm-s1-5848c762 (run rag-llm-s1-explicit, recall scope called), rag-llm-s1-404c0b6d (run rag-llm-s1-paraphrased, recall scope called), rag-llm-s1-d60fff2f (run rag-llm-s1-distributed, recall scope called), rag-llm-s1-a2b5bbc1 (run rag-llm-s1-complex, recall scope called), rag-llm-s1-c1d18224 (run rag-llm-s1-contradictory, recall scope called), rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | paraphrased   | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | distributed   | 13      | 12      | 12        | 0.923       | 1.000    | 0.960 | 1.000           | -                      | 1      | 0              |
| all             | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | contradictory | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | all           | 58      | 57      | 57        | 0.983       | 1.000    | 0.991 | 1.000           | -                      | 1      | 0              |
| author_claim    | explicit      | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | paraphrased   | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | distributed   | 13      | 12      | 12        | 0.923       | 1.000    | 0.960 | 1.000           | -                      | 1      | 0              |
| author_claim    | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | contradictory | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | all           | 58      | 57      | 57        | 0.983       | 1.000    | 0.991 | 1.000           | -                      | 1      | 0              |

Cost over 7 run(s), 57 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens     | output_tokens   | seconds         |
|---------|---------------|------------------|-----------------|-----------------|
| 57      | 63 [1.105]    | 79942 [1402.491] | 7057 [123.807]  | 194.803 [3.418] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 23      | 23          | 1.000             | 24               | 24                 | 1.000            |

## llm_condition@1#134ab1a38338

Corpora: rag-llm-s1-5848c762 (run rag-llm-s1-explicit, recall scope called), rag-llm-s1-404c0b6d (run rag-llm-s1-paraphrased, recall scope called), rag-llm-s1-d60fff2f (run rag-llm-s1-distributed, recall scope called), rag-llm-s1-a2b5bbc1 (run rag-llm-s1-complex, recall scope called), rag-llm-s1-c1d18224 (run rag-llm-s1-contradictory, recall scope called), rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 33      | 33      | 29        | 0.879       | 0.879    | 0.879 | 1.000           | -                      | 23     | 19             |
| all             | paraphrased   | 37      | 37      | 33        | 0.892       | 0.892    | 0.892 | 1.000           | -                      | 37     | 33             |
| all             | distributed   | 43      | 37      | 32        | 0.744       | 0.865    | 0.800 | 1.000           | -                      | 36     | 25             |
| all             | complex       | 33      | 33      | 30        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 25     | 22             |
| all             | contradictory | 33      | 33      | 30        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 24     | 21             |
| all             | all           | 179     | 173     | 154       | 0.860       | 0.890    | 0.875 | 1.000           | -                      | 145    | 120            |
| condition       | explicit      | 33      | 33      | 29        | 0.879       | 0.879    | 0.879 | 1.000           | -                      | 23     | 19             |
| condition       | paraphrased   | 37      | 37      | 33        | 0.892       | 0.892    | 0.892 | 1.000           | -                      | 37     | 33             |
| condition       | distributed   | 43      | 37      | 32        | 0.744       | 0.865    | 0.800 | 1.000           | -                      | 36     | 25             |
| condition       | complex       | 33      | 33      | 30        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 25     | 22             |
| condition       | contradictory | 33      | 33      | 30        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 24     | 21             |
| condition       | all           | 179     | 173     | 154       | 0.860       | 0.890    | 0.875 | 1.000           | -                      | 145    | 120            |

Cost over 7 run(s), 57 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds         |
|---------|---------------|-------------------|-----------------|-----------------|
| 57      | 95 [1.667]    | 129575 [2273.246] | 16894 [296.386] | 433.728 [7.609] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 23      | 23          | 1.000             | 76               | 76                 | 1.000            |

## llm_measurement@1#31b14e5f404d

Corpora: rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | paraphrased | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| all             | distributed | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 4      | 4              |
| all             | all         | 8       | 8       | 8         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 6      | 6              |
| measurement     | paraphrased | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           | 0.750                  | 2      | 2              |
| measurement     | distributed | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           | 1.000                  | 4      | 4              |
| measurement     | all         | 8       | 8       | 8         | 1.000       | 1.000    | 1.000 | 1.000           | 0.875                  | 6      | 6              |

Cost over 2 run(s), 2 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens    | output_tokens   | seconds         |
|---------|---------------|-----------------|-----------------|-----------------|
| 2       | 4 [2.000]     | 5420 [2710.000] | 1471 [735.500]  | 37.396 [18.698] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 1       | 0           | 0.000             | 4                | 0                  | 0.000            |

## llm_measurement@1#5212fc43026f

Corpora: rag-llm-s1-5848c762 (run rag-llm-s1-explicit, recall scope called), rag-llm-s1-404c0b6d (run rag-llm-s1-paraphrased, recall scope called), rag-llm-s1-d60fff2f (run rag-llm-s1-distributed, recall scope called), rag-llm-s1-a2b5bbc1 (run rag-llm-s1-complex, recall scope called), rag-llm-s1-c1d18224 (run rag-llm-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 33      | 33      | 29        | 0.879       | 0.879    | 0.879 | 1.000           | -                      | 25     | 21             |
| all             | paraphrased   | 31      | 33      | 31        | 1.000       | 0.939    | 0.969 | 1.000           | -                      | 31     | 31             |
| all             | distributed   | 33      | 33      | 33        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 33     | 33             |
| all             | complex       | 160     | 170     | 153       | 0.956       | 0.900    | 0.927 | 1.000           | -                      | 26     | 19             |
| all             | contradictory | 37      | 33      | 27        | 0.730       | 0.818    | 0.771 | 1.000           | -                      | 17     | 9              |
| all             | all           | 294     | 302     | 273       | 0.929       | 0.904    | 0.916 | 1.000           | -                      | 132    | 113            |
| measurement     | explicit      | 33      | 33      | 29        | 0.879       | 0.879    | 0.879 | 1.000           | 0.862                  | 25     | 21             |
| measurement     | paraphrased   | 31      | 33      | 31        | 1.000       | 0.939    | 0.969 | 1.000           | 0.774                  | 31     | 31             |
| measurement     | distributed   | 33      | 33      | 33        | 1.000       | 1.000    | 1.000 | 1.000           | 0.909                  | 33     | 33             |
| measurement     | complex       | 160     | 170     | 153       | 0.956       | 0.900    | 0.927 | 1.000           | 0.902                  | 26     | 19             |
| measurement     | contradictory | 37      | 33      | 27        | 0.730       | 0.818    | 0.771 | 1.000           | 0.926                  | 17     | 9              |
| measurement     | all           | 294     | 302     | 273       | 0.929       | 0.904    | 0.916 | 1.000           | 0.886                  | 132    | 113            |

Cost over 5 run(s), 55 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens      | output_tokens   | seconds           |
|---------|---------------|-------------------|-----------------|-------------------|
| 55      | 115 [2.091]   | 195658 [3557.418] | 51851 [942.745] | 1278.971 [23.254] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 22      | 22          | 1.000             | 66               | 66                 | 1.000            |

## llm_metric@1#1ca12a572ef8

Corpora: rag-llm-s1-5848c762 (run rag-llm-s1-explicit, recall scope called), rag-llm-s1-404c0b6d (run rag-llm-s1-paraphrased, recall scope called), rag-llm-s1-d60fff2f (run rag-llm-s1-distributed, recall scope called), rag-llm-s1-a2b5bbc1 (run rag-llm-s1-complex, recall scope called), rag-llm-s1-c1d18224 (run rag-llm-s1-contradictory, recall scope called), rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 5      | 5              |
| all             | paraphrased   | 7       | 12      | 7         | 1.000       | 0.583    | 0.737 | 1.000           | -                      | 7      | 7              |
| all             | distributed   | 13      | 12      | 11        | 0.846       | 0.917    | 0.880 | 1.000           | -                      | 8      | 6              |
| all             | complex       | 26      | 28      | 26        | 1.000       | 0.929    | 0.963 | 1.000           | -                      | 5      | 5              |
| all             | contradictory | 10      | 11      | 10        | 1.000       | 0.909    | 0.952 | 1.000           | -                      | 5      | 5              |
| all             | all           | 67      | 74      | 65        | 0.970       | 0.878    | 0.922 | 1.000           | -                      | 30     | 28             |
| metric          | explicit      | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 5      | 5              |
| metric          | paraphrased   | 7       | 12      | 7         | 1.000       | 0.583    | 0.737 | 1.000           | -                      | 7      | 7              |
| metric          | distributed   | 13      | 12      | 11        | 0.846       | 0.917    | 0.880 | 1.000           | -                      | 8      | 6              |
| metric          | complex       | 26      | 28      | 26        | 1.000       | 0.929    | 0.963 | 1.000           | -                      | 5      | 5              |
| metric          | contradictory | 10      | 11      | 10        | 1.000       | 0.909    | 0.952 | 1.000           | -                      | 5      | 5              |
| metric          | all           | 67      | 74      | 65        | 0.970       | 0.878    | 0.922 | 1.000           | -                      | 30     | 28             |

Cost over 7 run(s), 57 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens     | output_tokens   | seconds         |
|---------|---------------|------------------|-----------------|-----------------|
| 57      | 71 [1.246]    | 97401 [1708.789] | 6723 [117.947]  | 194.235 [3.408] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 23      | 23          | 1.000             | 24               | 24                 | 1.000            |

## llm_screen@1#6bec6abaf6a0

Corpora: rag-llm-s1-5848c762 (run rag-llm-s1-explicit, recall scope called), rag-llm-s1-404c0b6d (run rag-llm-s1-paraphrased, recall scope called), rag-llm-s1-d60fff2f (run rag-llm-s1-distributed, recall scope called), rag-llm-s1-a2b5bbc1 (run rag-llm-s1-complex, recall scope called), rag-llm-s1-c1d18224 (run rag-llm-s1-contradictory, recall scope called), rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1   | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------|---------|---------|-----------|-------------|----------|------|-----------------|------------------------|--------|----------------|

Cost over 7 run(s), 57 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens     | output_tokens   | seconds         |
|---------|---------------|------------------|-----------------|-----------------|
| 57      | 57 [1.000]    | 66132 [1160.211] | 4946 [86.772]   | 144.628 [2.537] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 23      | 23          | 1.000             | 23               | 23                 | 1.000            |

## regex_author_claim@2#b2161f228a8c

Corpora: rag-llm-s1-5848c762 (run rag-llm-s1-explicit, recall scope called), rag-llm-s1-404c0b6d (run rag-llm-s1-paraphrased, recall scope called), rag-llm-s1-d60fff2f (run rag-llm-s1-distributed, recall scope called), rag-llm-s1-a2b5bbc1 (run rag-llm-s1-complex, recall scope called), rag-llm-s1-c1d18224 (run rag-llm-s1-contradictory, recall scope called), rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | paraphrased   | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | distributed   | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | contradictory | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| all             | all           | 57      | 57      | 57        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | explicit      | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | paraphrased   | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | distributed   | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | contradictory | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| author_claim    | all           | 57      | 57      | 57        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |

Cost over 7 run(s), 57 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 57      | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.425 [0.007] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 23      | 23          | 1.000             | 23               | 23                 | 1.000            |

## regex_condition@2#80486860164a

Corpora: rag-llm-s1-5848c762 (run rag-llm-s1-explicit, recall scope called), rag-llm-s1-404c0b6d (run rag-llm-s1-paraphrased, recall scope called), rag-llm-s1-d60fff2f (run rag-llm-s1-distributed, recall scope called), rag-llm-s1-a2b5bbc1 (run rag-llm-s1-complex, recall scope called), rag-llm-s1-c1d18224 (run rag-llm-s1-contradictory, recall scope called), rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 18      | 33      | 10        | 0.556       | 0.303    | 0.392 | 1.000           | -                      | 8      | 0              |
| all             | paraphrased   | 8       | 37      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 8      | 0              |
| all             | distributed   | 19      | 37      | 9         | 0.474       | 0.243    | 0.321 | 1.000           | -                      | 12     | 2              |
| all             | complex       | 18      | 33      | 8         | 0.444       | 0.242    | 0.314 | 1.000           | -                      | 10     | 0              |
| all             | contradictory | 17      | 33      | 9         | 0.529       | 0.273    | 0.360 | 1.000           | -                      | 8      | 0              |
| all             | all           | 80      | 173     | 36        | 0.450       | 0.208    | 0.285 | 1.000           | -                      | 46     | 2              |
| condition       | explicit      | 18      | 33      | 10        | 0.556       | 0.303    | 0.392 | 1.000           | -                      | 8      | 0              |
| condition       | paraphrased   | 8       | 37      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 8      | 0              |
| condition       | distributed   | 19      | 37      | 9         | 0.474       | 0.243    | 0.321 | 1.000           | -                      | 12     | 2              |
| condition       | complex       | 18      | 33      | 8         | 0.444       | 0.242    | 0.314 | 1.000           | -                      | 10     | 0              |
| condition       | contradictory | 17      | 33      | 9         | 0.529       | 0.273    | 0.360 | 1.000           | -                      | 8      | 0              |
| condition       | all           | 80      | 173     | 36        | 0.450       | 0.208    | 0.285 | 1.000           | -                      | 46     | 2              |

Cost over 7 run(s), 57 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 57      | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.568 [0.010] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 23      | 23          | 1.000             | 37               | 37                 | 1.000            |

## regex_measurement@2#9edb306c5b05

Corpora: rag-llm-s1-5848c762 (run rag-llm-s1-explicit, recall scope called), rag-llm-s1-404c0b6d (run rag-llm-s1-paraphrased, recall scope called), rag-llm-s1-d60fff2f (run rag-llm-s1-distributed, recall scope called), rag-llm-s1-a2b5bbc1 (run rag-llm-s1-complex, recall scope called), rag-llm-s1-c1d18224 (run rag-llm-s1-contradictory, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 14      | 33      | 12        | 0.857       | 0.364    | 0.511 | 1.000           | -                      | 6      | 4              |
| all             | paraphrased   | 0       | 33      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed   | 0       | 33      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | complex       | 152     | 170     | 141       | 0.928       | 0.829    | 0.876 | 1.000           | -                      | 18     | 7              |
| all             | contradictory | 33      | 33      | 24        | 0.727       | 0.727    | 0.727 | 1.000           | -                      | 13     | 6              |
| all             | all           | 199     | 302     | 177       | 0.889       | 0.586    | 0.707 | 1.000           | -                      | 37     | 17             |
| measurement     | explicit      | 14      | 33      | 12        | 0.857       | 0.364    | 0.511 | 1.000           | 1.000                  | 6      | 4              |
| measurement     | paraphrased   | 0       | 33      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | distributed   | 0       | 33      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | complex       | 152     | 170     | 141       | 0.928       | 0.829    | 0.876 | 1.000           | 0.908                  | 18     | 7              |
| measurement     | contradictory | 33      | 33      | 24        | 0.727       | 0.727    | 0.727 | 1.000           | 0.917                  | 13     | 6              |
| measurement     | all           | 199     | 302     | 177       | 0.889       | 0.586    | 0.707 | 1.000           | 0.915                  | 37     | 17             |

Cost over 5 run(s), 55 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 55      | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.997 [0.018] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 22      | 22          | 1.000             | 14               | 14                 | 1.000            |

## regex_measurement@2#a70020d1afcc

Corpora: rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | paraphrased | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | distributed | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| all             | all         | 0       | 8       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | paraphrased | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | distributed | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| measurement     | all         | 0       | 8       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |

Cost over 2 run(s), 2 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 2       | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.317 [0.159] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 1       | 1           | 1.000             | 0                | 0                  | -                |

## regex_metric@2#67f41f33eff7

Corpora: rag-llm-s1-5848c762 (run rag-llm-s1-explicit, recall scope called), rag-llm-s1-404c0b6d (run rag-llm-s1-paraphrased, recall scope called), rag-llm-s1-d60fff2f (run rag-llm-s1-distributed, recall scope called), rag-llm-s1-a2b5bbc1 (run rag-llm-s1-complex, recall scope called), rag-llm-s1-c1d18224 (run rag-llm-s1-contradictory, recall scope called), rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| all             | explicit      | 20      | 11      | 6         | 0.300       | 0.545    | 0.387 | 1.000           | -                      | 14     | 0              |
| all             | paraphrased   | 15      | 12      | 3         | 0.200       | 0.250    | 0.222 | 0.000           | -                      | 15     | 3              |
| all             | distributed   | 19      | 12      | 6         | 0.316       | 0.500    | 0.387 | 1.000           | -                      | 14     | 1              |
| all             | complex       | 34      | 28      | 23        | 0.676       | 0.821    | 0.742 | 1.000           | -                      | 13     | 2              |
| all             | contradictory | 22      | 11      | 6         | 0.273       | 0.545    | 0.364 | 1.000           | -                      | 17     | 1              |
| all             | all           | 110     | 74      | 44        | 0.400       | 0.595    | 0.478 | 0.932           | -                      | 73     | 7              |
| metric          | explicit      | 20      | 11      | 6         | 0.300       | 0.545    | 0.387 | 1.000           | -                      | 14     | 0              |
| metric          | paraphrased   | 15      | 12      | 3         | 0.200       | 0.250    | 0.222 | 0.000           | -                      | 15     | 3              |
| metric          | distributed   | 19      | 12      | 6         | 0.316       | 0.500    | 0.387 | 1.000           | -                      | 14     | 1              |
| metric          | complex       | 34      | 28      | 23        | 0.676       | 0.821    | 0.742 | 1.000           | -                      | 13     | 2              |
| metric          | contradictory | 22      | 11      | 6         | 0.273       | 0.545    | 0.364 | 1.000           | -                      | 17     | 1              |
| metric          | all           | 110     | 74      | 44        | 0.400       | 0.595    | 0.478 | 0.932           | -                      | 73     | 7              |

Cost over 7 run(s), 57 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 57      | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.428 [0.008] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 23      | 23          | 1.000             | 39               | 39                 | 1.000            |

## regex_screen@1#8301b6896dc3

Corpora: rag-llm-s1-5848c762 (run rag-llm-s1-explicit, recall scope called), rag-llm-s1-404c0b6d (run rag-llm-s1-paraphrased, recall scope called), rag-llm-s1-d60fff2f (run rag-llm-s1-distributed, recall scope called), rag-llm-s1-a2b5bbc1 (run rag-llm-s1-complex, recall scope called), rag-llm-s1-c1d18224 (run rag-llm-s1-contradictory, recall scope called), rag-llm-small-bd3f74c0 (run rag-llm-small-distributed, recall scope called), rag-llm-small-efea11e7 (run rag-llm-small-paraphrased, recall scope called)

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1   | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------|---------|---------|---------|-----------|-------------|----------|------|-----------------|------------------------|--------|----------------|

Cost over 7 run(s), 57 calls (per call in brackets; `-`: not recorded):

| calls   | model_calls   | input_tokens   | output_tokens   | seconds       |
|---------|---------------|----------------|-----------------|---------------|
| 57      | 0 [0.000]     | 0 [0.000]      | 0 [0.000]       | 0.435 [0.008] |

Re-execution stability:

| calls   | identical   | identical_share   | items_original   | items_reproduced   | item_stability   |
|---------|-------------|-------------------|------------------|--------------------|------------------|
| 23      | 23          | 1.000             | 23               | 23                 | 1.000            |
