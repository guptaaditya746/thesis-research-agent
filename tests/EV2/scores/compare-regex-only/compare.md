# Comparison over corpora

| level         | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------------|---------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| explicit      | rag-claude-pilot-c2d26fcb | evidence-engine | all        | reject         | 6b360bca67ce | 0.486           | 1.000           | 1.000                  | 0.000       | 0.000                | 0.000          | -                   | -              | -         | no              | 5.000                | 0.000                 | 1.000              | 1.000           |
| explicit      | rag-claude-s1-eb14377d    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| explicit      | rag-claude-s1-eb14377d    | evidence-engine | all        | reject         | 6b360bca67ce | 0.703           | 0.989           | 1.000                  | 0.400       | 0.400                | 0.400          | 1.000               | -              | -         | yes             | 5.000                | 0.000                 | 1.000              | 1.000           |
| explicit      | rag-claude-s1-eb14377d    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| explicit      | rag-tpl-s1-59c5118b       | evidence-engine | all        | reject         | 6b360bca67ce | 0.656           | 1.000           | 1.000                  | 0.050       | 0.050                | 0.050          | 1.000               | -              | -         | no              | 5.000                | 0.000                 | 1.000              | 1.000           |
| paraphrased   | rag-claude-pilot-d69436ff | evidence-engine | all        | reject         | 6b360bca67ce | 0.194           | 1.000           | -                      | 0.000       | 0.000                | 0.000          | -                   | -              | -         | no              | 5.000                | 0.000                 | 1.000              | 1.000           |
| paraphrased   | rag-claude-s1-c34803f0    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| paraphrased   | rag-claude-s1-c34803f0    | evidence-engine | all        | reject         | 6b360bca67ce | 0.238           | 0.909           | -                      | 0.000       | 0.000                | 0.000          | -                   | -              | -         | no              | 5.000                | 0.000                 | 1.000              | 1.000           |
| paraphrased   | rag-claude-s1-c34803f0    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.200                | 0.400          | 0.500               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| paraphrased   | rag-tpl-s1-4d15ddc4       | evidence-engine | all        | reject         | 6b360bca67ce | 0.220           | 1.000           | -                      | 0.000       | 0.000                | 0.000          | -                   | -              | -         | no              | 5.000                | 0.000                 | 1.000              | 1.000           |
| distributed   | rag-claude-pilot-7807c6b5 | evidence-engine | all        | reject         | 6b360bca67ce | 0.444           | 1.000           | -                      | 0.000       | 0.000                | 0.000          | -                   | -              | -         | no              | 5.000                | 0.000                 | 1.000              | 1.000           |
| distributed   | rag-claude-s1-869ad7e8    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| distributed   | rag-claude-s1-869ad7e8    | evidence-engine | all        | reject         | 6b360bca67ce | 0.576           | 1.000           | -                      | 0.000       | 0.000                | 0.000          | -                   | -              | -         | no              | 5.000                | 0.000                 | 1.000              | 1.000           |
| distributed   | rag-claude-s1-869ad7e8    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.300                | 0.300          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| distributed   | rag-tpl-s1-79207ad1       | evidence-engine | all        | reject         | 6b360bca67ce | 0.579           | 1.000           | -                      | 0.000       | 0.000                | 0.000          | -                   | -              | -         | no              | 5.000                | 0.000                 | 1.000              | 1.000           |
| complex       | rag-claude-pilot-d04573ee | evidence-engine | all        | reject         | 6b360bca67ce | 0.416           | 1.000           | 1.000                  | 0.000       | 0.000                | 0.000          | -                   | -              | -         | no              | 5.000                | 0.000                 | 1.000              | 1.000           |
| complex       | rag-claude-s1-a5fa1731    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| complex       | rag-claude-s1-a5fa1731    | evidence-engine | all        | reject         | 6b360bca67ce | 0.621           | 1.000           | 1.000                  | 0.000       | 0.250                | 0.250          | 1.000               | -              | -         | yes             | 5.000                | 0.000                 | 1.000              | 1.000           |
| complex       | rag-claude-s1-a5fa1731    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| complex       | rag-tpl-hard-24ab4663     | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.946                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| complex       | rag-tpl-hard-24ab4663     | evidence-engine | all        | reject         | 6b360bca67ce | 0.619           | 1.000           | 1.000                  | 0.000       | 0.205                | 0.170          | 0.647               | -              | -         | yes             | 5.000                | 0.000                 | 0.973              | 1.000           |
| complex       | rag-tpl-hard-24ab4663     | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.143                | 0.060          | 0.833               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| complex       | rag-tpl-s1-f0f5d48e       | evidence-engine | all        | reject         | 6b360bca67ce | 0.623           | 1.000           | 1.000                  | 0.000       | 0.250                | 0.250          | 1.000               | -              | -         | yes             | 5.000                | 0.000                 | 1.000              | 1.000           |
| contradictory | rag-claude-pilot-3ef3b916 | evidence-engine | all        | reject         | 6b360bca67ce | 0.444           | 1.000           | -                      | 0.000       | 0.000                | 0.000          | -                   | -              | -         | no              | 5.000                | 0.000                 | 1.000              | 1.000           |
| contradictory | rag-claude-s1-e4e9d603    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.000                | 1.000          | 0.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-claude-s1-e4e9d603    | evidence-engine | all        | reject         | 6b360bca67ce | 0.674           | 0.977           | 1.000                  | 0.250       | 0.250                | 0.350          | 0.714               | -              | -         | yes             | 5.000                | 0.000                 | 1.000              | 1.000           |
| contradictory | rag-claude-s1-e4e9d603    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.050                | 0.250          | 0.200               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-tpl-s1-56b0bc02       | evidence-engine | all        | reject         | 6b360bca67ce | 0.674           | 1.000           | 1.000                  | 0.250       | 0.250                | 0.350          | 0.714               | -              | -         | yes             | 5.000                | 0.000                 | 1.000              | 1.000           |
| mixed         | rag-claude-k1-adf90d94    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.750                | 1.000          | 0.800               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-k1-adf90d94    | evidence-engine | all        | reject         | 6b360bca67ce | 0.607           | 0.970           | 1.000                  | 0.200       | 0.333                | 0.200          | 1.000               | -              | -         | no              | 5.000                | 0.000                 | 0.957              | 1.000           |
| mixed         | rag-claude-k1-adf90d94    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.167                | 0.250          | 0.400               | 0.857          | 0.857     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-pilot-931cb13b | evidence-engine | all        | reject         | 6b360bca67ce | 0.353           | 1.000           | -                      | 0.000       | 0.000                | 0.000          | -                   | -              | -         | no              | 5.000                | 0.000                 | 1.000              | 1.000           |
| mixed         | rag-claude-s1-cf-5893772b | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.750                | 1.000          | 0.750               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-cf-5893772b | evidence-engine | all        | reject         | 6b360bca67ce | 0.626           | 0.969           | 1.000                  | 0.200       | 0.250                | 0.250          | 1.000               | -              | -         | yes             | 5.000                | 0.000                 | 1.000              | 1.000           |
| mixed         | rag-claude-s1-cf-5893772b | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.200                | 0.250          | 0.800               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-ec928480    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.800                | 1.000          | 0.800               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-ec928480    | evidence-engine | all        | reject         | 6b360bca67ce | 0.626           | 0.969           | 1.000                  | 0.200       | 0.250                | 0.250          | 1.000               | -              | -         | yes             | 5.000                | 0.000                 | 1.000              | 1.000           |
| mixed         | rag-claude-s1-ec928480    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.150                | 0.250          | 0.600               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-hard-b1c0fdfe     | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.375                | 0.380          | 0.842               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-hard-b1c0fdfe     | evidence-engine | all        | reject         | 6b360bca67ce | 0.561           | 1.000           | 1.000                  | 0.060       | 0.170                | 0.110          | 0.636               | -              | -         | yes             | 5.000                | 0.000                 | 0.973              | 1.000           |
| mixed         | rag-tpl-hard-b1c0fdfe     | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.116                | 0.050          | 0.400               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-k1-9c3bbb32       | evidence-engine | all        | reject         | 6b360bca67ce | 0.596           | 1.000           | 1.000                  | 0.150       | 0.292                | 0.150          | 1.000               | -              | -         | no              | 5.000                | 0.000                 | 0.957              | 1.000           |
| mixed         | rag-tpl-s1-6162b495       | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.650                | 1.000          | 0.650               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-s1-6162b495       | evidence-engine | all        | reject         | 6b360bca67ce | 0.614           | 1.000           | 1.000                  | 0.150       | 0.200                | 0.200          | 1.000               | -              | -         | yes             | 5.000                | 0.000                 | 1.000              | 1.000           |
| mixed         | rag-tpl-s1-6162b495       | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.150                | 0.200          | 0.750               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-s1-cf-cb85326b    | evidence-engine | all        | reject         | 6b360bca67ce | 0.614           | 1.000           | 1.000                  | 0.150       | 0.200                | 0.200          | 1.000               | -              | -         | yes             | 5.000                | 0.000                 | 1.000              | 1.000           |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id                 | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|---------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-k1-adf90d94    | explicit      | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-claude-k1-adf90d94    | paraphrased   | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-claude-k1-adf90d94    | distributed   | 20          | 20         | 24        | 24       | none            | 1.083           |
| rag-claude-k1-adf90d94    | complex       | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-claude-k1-adf90d94    | contradictory | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-claude-pilot-d04573ee | explicit      | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d04573ee | paraphrased   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d04573ee | distributed   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d04573ee | complex       | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d04573ee | contradictory | 3           | 3          | 3         | 3        | none            | 1.333           |
| rag-claude-pilot-3ef3b916 | explicit      | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-3ef3b916 | paraphrased   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-3ef3b916 | distributed   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-3ef3b916 | complex       | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-3ef3b916 | contradictory | 3           | 3          | 3         | 3        | none            | 1.333           |
| rag-claude-pilot-7807c6b5 | explicit      | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-7807c6b5 | paraphrased   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-7807c6b5 | distributed   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-7807c6b5 | complex       | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-7807c6b5 | contradictory | 3           | 3          | 3         | 3        | none            | 1.333           |
| rag-claude-pilot-c2d26fcb | explicit      | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-c2d26fcb | paraphrased   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-c2d26fcb | distributed   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-c2d26fcb | complex       | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-c2d26fcb | contradictory | 3           | 3          | 3         | 3        | none            | 1.333           |
| rag-claude-pilot-931cb13b | explicit      | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-931cb13b | paraphrased   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-931cb13b | distributed   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-931cb13b | complex       | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-931cb13b | contradictory | 3           | 3          | 3         | 3        | none            | 1.333           |
| rag-claude-pilot-d69436ff | explicit      | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d69436ff | paraphrased   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d69436ff | distributed   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d69436ff | complex       | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d69436ff | contradictory | 3           | 3          | 3         | 3        | none            | 1.333           |
| rag-claude-s1-a5fa1731    | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-a5fa1731    | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-a5fa1731    | distributed   | 20          | 20         | 20        | 20       | none            | 1.100           |
| rag-claude-s1-a5fa1731    | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-a5fa1731    | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-e4e9d603    | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-e4e9d603    | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-e4e9d603    | distributed   | 20          | 20         | 20        | 20       | none            | 1.100           |
| rag-claude-s1-e4e9d603    | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-e4e9d603    | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-869ad7e8    | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-869ad7e8    | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-869ad7e8    | distributed   | 20          | 20         | 20        | 20       | none            | 1.100           |
| rag-claude-s1-869ad7e8    | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-869ad7e8    | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-eb14377d    | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-eb14377d    | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-eb14377d    | distributed   | 20          | 20         | 20        | 20       | none            | 1.100           |
| rag-claude-s1-eb14377d    | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-eb14377d    | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-ec928480    | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-ec928480    | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-ec928480    | distributed   | 20          | 20         | 20        | 20       | none            | 1.100           |
| rag-claude-s1-ec928480    | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-ec928480    | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-cf-5893772b | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-cf-5893772b | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-cf-5893772b | distributed   | 20          | 20         | 20        | 20       | none            | 1.100           |
| rag-claude-s1-cf-5893772b | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-cf-5893772b | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-c34803f0    | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-c34803f0    | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-c34803f0    | distributed   | 20          | 20         | 20        | 20       | none            | 1.100           |
| rag-claude-s1-c34803f0    | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-c34803f0    | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-hard-24ab4663     | explicit      | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-24ab4663     | paraphrased   | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-24ab4663     | distributed   | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-24ab4663     | complex       | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-24ab4663     | contradictory | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe     | explicit      | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe     | paraphrased   | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe     | distributed   | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe     | complex       | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe     | contradictory | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-k1-9c3bbb32       | explicit      | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-tpl-k1-9c3bbb32       | paraphrased   | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-tpl-k1-9c3bbb32       | distributed   | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-tpl-k1-9c3bbb32       | complex       | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-tpl-k1-9c3bbb32       | contradictory | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-tpl-s1-f0f5d48e       | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-f0f5d48e       | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-f0f5d48e       | distributed   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-f0f5d48e       | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-f0f5d48e       | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-56b0bc02       | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-56b0bc02       | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-56b0bc02       | distributed   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-56b0bc02       | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-56b0bc02       | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-79207ad1       | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-79207ad1       | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-79207ad1       | distributed   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-79207ad1       | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-79207ad1       | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-59c5118b       | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-59c5118b       | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-59c5118b       | distributed   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-59c5118b       | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-59c5118b       | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-6162b495       | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-6162b495       | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-6162b495       | distributed   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-6162b495       | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-6162b495       | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-cf-cb85326b    | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-cf-cb85326b    | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-cf-cb85326b    | distributed   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-cf-cb85326b    | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-cf-cb85326b    | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-4d15ddc4       | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-4d15ddc4       | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-4d15ddc4       | distributed   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-4d15ddc4       | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-4d15ddc4       | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |

- rag-claude-k1-adf90d94: excluded none
- rag-claude-pilot-d04573ee: excluded none
- rag-claude-pilot-3ef3b916: excluded none
- rag-claude-pilot-7807c6b5: excluded none
- rag-claude-pilot-c2d26fcb: excluded none
- rag-claude-pilot-931cb13b: excluded none
- rag-claude-pilot-d69436ff: excluded none
- rag-claude-s1-a5fa1731: excluded none
- rag-claude-s1-e4e9d603: excluded none
- rag-claude-s1-869ad7e8: excluded none
- rag-claude-s1-eb14377d: excluded none
- rag-claude-s1-ec928480: excluded none
- rag-claude-s1-cf-5893772b: excluded none
- rag-claude-s1-c34803f0: excluded none
- rag-tpl-hard-24ab4663: excluded none
- rag-tpl-hard-b1c0fdfe: excluded none
- rag-tpl-k1-9c3bbb32: excluded none
- rag-tpl-s1-f0f5d48e: excluded none
- rag-tpl-s1-56b0bc02: excluded none
- rag-tpl-s1-79207ad1: excluded none
- rag-tpl-s1-59c5118b: excluded none
- rag-tpl-s1-6162b495: excluded none
- rag-tpl-s1-cf-cb85326b: excluded none
- rag-tpl-s1-4d15ddc4: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level         | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------------|---------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| explicit      | rag-claude-pilot-c2d26fcb | evidence-engine | all        | reject         | 6b360bca67ce | 0.486 [0.42, 0.57] | 3              | 0.000 [n/a]          | 3             | -                     | -          |
| explicit      | rag-claude-s1-eb14377d    | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | -0.600 [-0.80, -0.35] | 20         |
| explicit      | rag-claude-s1-eb14377d    | evidence-engine | all        | reject         | 6b360bca67ce | 0.703 [0.63, 0.79] | 20             | 0.400 [0.20, 0.65]   | 20            | -                     | -          |
| explicit      | rag-claude-s1-eb14377d    | rag-baseline    | -          | -              | -            | -                  | -              | 0.350 [0.15, 0.60]   | 20            | 0.050 [-0.20, 0.30]   | 20         |
| explicit      | rag-tpl-s1-59c5118b       | evidence-engine | all        | reject         | 6b360bca67ce | 0.656 [0.59, 0.73] | 20             | 0.050 [0.00, 0.25]   | 20            | -                     | -          |
| paraphrased   | rag-claude-pilot-d69436ff | evidence-engine | all        | reject         | 6b360bca67ce | 0.194 [0.18, 0.22] | 3              | 0.000 [n/a]          | 3             | -                     | -          |
| paraphrased   | rag-claude-s1-c34803f0    | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | -1.000 [n/a]          | 20         |
| paraphrased   | rag-claude-s1-c34803f0    | evidence-engine | all        | reject         | 6b360bca67ce | 0.238 [0.21, 0.28] | 20             | 0.000 [n/a]          | 20            | -                     | -          |
| paraphrased   | rag-claude-s1-c34803f0    | rag-baseline    | -          | -              | -            | -                  | -              | 0.200 [0.05, 0.45]   | 20            | -0.200 [-0.45, -0.05] | 20         |
| paraphrased   | rag-tpl-s1-4d15ddc4       | evidence-engine | all        | reject         | 6b360bca67ce | 0.220 [0.20, 0.24] | 20             | 0.000 [n/a]          | 20            | -                     | -          |
| distributed   | rag-claude-pilot-7807c6b5 | evidence-engine | all        | reject         | 6b360bca67ce | 0.444 [0.40, 0.46] | 3              | 0.000 [n/a]          | 3             | -                     | -          |
| distributed   | rag-claude-s1-869ad7e8    | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | -1.000 [n/a]          | 20         |
| distributed   | rag-claude-s1-869ad7e8    | evidence-engine | all        | reject         | 6b360bca67ce | 0.576 [0.53, 0.63] | 20             | 0.000 [n/a]          | 20            | -                     | -          |
| distributed   | rag-claude-s1-869ad7e8    | rag-baseline    | -          | -              | -            | -                  | -              | 0.300 [0.15, 0.55]   | 20            | -0.300 [-0.55, -0.15] | 20         |
| distributed   | rag-tpl-s1-79207ad1       | evidence-engine | all        | reject         | 6b360bca67ce | 0.579 [0.53, 0.64] | 20             | 0.000 [n/a]          | 20            | -                     | -          |
| complex       | rag-claude-pilot-d04573ee | evidence-engine | all        | reject         | 6b360bca67ce | 0.416 [0.27, 0.51] | 3              | 0.000 [n/a]          | 3             | -                     | -          |
| complex       | rag-claude-s1-a5fa1731    | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | -0.750 [-0.90, -0.50] | 20         |
| complex       | rag-claude-s1-a5fa1731    | evidence-engine | all        | reject         | 6b360bca67ce | 0.621 [0.53, 0.70] | 20             | 0.250 [0.10, 0.50]   | 20            | -                     | -          |
| complex       | rag-claude-s1-a5fa1731    | rag-baseline    | -          | -              | -            | -                  | -              | 0.350 [0.15, 0.60]   | 20            | -0.100 [-0.35, 0.15]  | 20         |
| complex       | rag-tpl-hard-24ab4663     | agent-baseline  | -          | -              | -            | -                  | -              | 0.946 [0.89, 0.98]   | 112           | -0.741 [-0.82, -0.62] | 112        |
| complex       | rag-tpl-hard-24ab4663     | evidence-engine | all        | reject         | 6b360bca67ce | 0.619 [0.59, 0.65] | 112            | 0.205 [0.14, 0.29]   | 112           | -                     | -          |
| complex       | rag-tpl-hard-24ab4663     | rag-baseline    | -          | -              | -            | -                  | -              | 0.143 [0.09, 0.21]   | 112           | 0.062 [0.00, 0.12]    | 112        |
| complex       | rag-tpl-s1-f0f5d48e       | evidence-engine | all        | reject         | 6b360bca67ce | 0.623 [0.53, 0.70] | 20             | 0.250 [0.10, 0.50]   | 20            | -                     | -          |
| contradictory | rag-claude-pilot-3ef3b916 | evidence-engine | all        | reject         | 6b360bca67ce | 0.444 [0.40, 0.46] | 3              | 0.000 [n/a]          | 3             | -                     | -          |
| contradictory | rag-claude-s1-e4e9d603    | agent-baseline  | -          | -              | -            | -                  | -              | 0.000 [n/a]          | 20            | 0.250 [0.10, 0.50]    | 20         |
| contradictory | rag-claude-s1-e4e9d603    | evidence-engine | all        | reject         | 6b360bca67ce | 0.674 [0.60, 0.74] | 20             | 0.250 [0.10, 0.50]   | 20            | -                     | -          |
| contradictory | rag-claude-s1-e4e9d603    | rag-baseline    | -          | -              | -            | -                  | -              | 0.050 [0.00, 0.25]   | 20            | 0.200 [0.00, 0.45]    | 20         |
| contradictory | rag-tpl-s1-56b0bc02       | evidence-engine | all        | reject         | 6b360bca67ce | 0.674 [0.60, 0.74] | 20             | 0.250 [0.10, 0.50]   | 20            | -                     | -          |
| mixed         | rag-claude-k1-adf90d94    | agent-baseline  | -          | -              | -            | -                  | -              | 0.750 [0.54, 0.92]   | 24            | -0.417 [-0.71, -0.04] | 24         |
| mixed         | rag-claude-k1-adf90d94    | evidence-engine | all        | reject         | 6b360bca67ce | 0.607 [0.52, 0.72] | 24             | 0.333 [0.17, 0.54]   | 24            | -                     | -          |
| mixed         | rag-claude-k1-adf90d94    | rag-baseline    | -          | -              | -            | -                  | -              | 0.167 [0.04, 0.33]   | 24            | 0.167 [-0.04, 0.38]   | 24         |
| mixed         | rag-claude-pilot-931cb13b | evidence-engine | all        | reject         | 6b360bca67ce | 0.353 [0.18, 0.44] | 3              | 0.000 [n/a]          | 3             | -                     | -          |
| mixed         | rag-claude-s1-cf-5893772b | agent-baseline  | -          | -              | -            | -                  | -              | 0.750 [0.50, 0.90]   | 20            | -0.500 [-0.80, -0.10] | 20         |
| mixed         | rag-claude-s1-cf-5893772b | evidence-engine | all        | reject         | 6b360bca67ce | 0.626 [0.54, 0.74] | 20             | 0.250 [0.10, 0.50]   | 20            | -                     | -          |
| mixed         | rag-claude-s1-cf-5893772b | rag-baseline    | -          | -              | -            | -                  | -              | 0.200 [0.05, 0.45]   | 20            | 0.050 [-0.20, 0.30]   | 20         |
| mixed         | rag-claude-s1-ec928480    | agent-baseline  | -          | -              | -            | -                  | -              | 0.800 [0.55, 0.95]   | 20            | -0.550 [-0.80, -0.15] | 20         |
| mixed         | rag-claude-s1-ec928480    | evidence-engine | all        | reject         | 6b360bca67ce | 0.626 [0.54, 0.74] | 20             | 0.250 [0.10, 0.50]   | 20            | -                     | -          |
| mixed         | rag-claude-s1-ec928480    | rag-baseline    | -          | -              | -            | -                  | -              | 0.150 [0.05, 0.35]   | 20            | 0.100 [-0.12, 0.35]   | 20         |
| mixed         | rag-tpl-hard-b1c0fdfe     | agent-baseline  | -          | -              | -            | -                  | -              | 0.375 [0.29, 0.46]   | 112           | -0.205 [-0.30, -0.10] | 112        |
| mixed         | rag-tpl-hard-b1c0fdfe     | evidence-engine | all        | reject         | 6b360bca67ce | 0.561 [0.52, 0.60] | 112            | 0.170 [0.11, 0.25]   | 112           | -                     | -          |
| mixed         | rag-tpl-hard-b1c0fdfe     | rag-baseline    | -          | -              | -            | -                  | -              | 0.116 [0.06, 0.18]   | 112           | 0.054 [0.02, 0.11]    | 112        |
| mixed         | rag-tpl-k1-9c3bbb32       | evidence-engine | all        | reject         | 6b360bca67ce | 0.596 [0.50, 0.72] | 24             | 0.292 [0.12, 0.50]   | 24            | -                     | -          |
| mixed         | rag-tpl-s1-6162b495       | agent-baseline  | -          | -              | -            | -                  | -              | 0.650 [0.45, 0.85]   | 20            | -0.450 [-0.70, -0.05] | 20         |
| mixed         | rag-tpl-s1-6162b495       | evidence-engine | all        | reject         | 6b360bca67ce | 0.614 [0.52, 0.73] | 20             | 0.200 [0.05, 0.40]   | 20            | -                     | -          |
| mixed         | rag-tpl-s1-6162b495       | rag-baseline    | -          | -              | -            | -                  | -              | 0.150 [0.05, 0.35]   | 20            | 0.050 [-0.10, 0.25]   | 20         |
| mixed         | rag-tpl-s1-cf-cb85326b    | evidence-engine | all        | reject         | 6b360bca67ce | 0.614 [0.52, 0.73] | 20             | 0.200 [0.05, 0.40]   | 20            | -                     | -          |
