# Comparison over corpora

| level         | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------------|---------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| explicit      | rag-claude-pilot-c2d26fcb | evidence-engine | all        | reject         | 6b360bca67ce | 0.931           | 1.000           | 0.909                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 9314.333              | 1.000              | 1.000           |
| explicit      | rag-claude-s1-eb14377d    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| explicit      | rag-claude-s1-eb14377d    | evidence-engine | all        | reject         | 6b360bca67ce | 0.911           | 1.000           | 0.934                  | 0.750       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 8168.450              | 1.000              | 1.000           |
| explicit      | rag-claude-s1-eb14377d    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| explicit      | rag-tpl-s1-59c5118b       | evidence-engine | all        | reject         | 6b360bca67ce | 0.950           | 1.000           | 0.984                  | 0.750       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 7522.350              | 1.000              | 1.000           |
| paraphrased   | rag-claude-pilot-d69436ff | evidence-engine | all        | reject         | 6b360bca67ce | 0.766           | 1.000           | 0.750                  | 0.333       | 0.333                | 0.333          | 1.000               | -              | -         | no              | 10.000               | 8539.667              | 1.000              | 1.000           |
| paraphrased   | rag-claude-s1-c34803f0    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| paraphrased   | rag-claude-s1-c34803f0    | evidence-engine | all        | reject         | 6b360bca67ce | 0.853           | 1.000           | 0.914                  | 0.600       | 0.600                | 0.600          | 1.000               | -              | -         | yes             | 10.000               | 8939.200              | 1.000              | 1.000           |
| paraphrased   | rag-claude-s1-c34803f0    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.200                | 0.400          | 0.500               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| paraphrased   | rag-claude-small-7eb8078c | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| paraphrased   | rag-claude-small-7eb8078c | evidence-engine | all        | reject         | 6b360bca67ce | 0.971           | 1.000           | 0.917                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 9545.800              | 1.000              | 1.000           |
| paraphrased   | rag-claude-small-7eb8078c | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| paraphrased   | rag-tpl-s1-4d15ddc4       | evidence-engine | all        | reject         | 6b360bca67ce | 0.972           | 1.000           | 0.965                  | 0.950       | 0.950                | 0.950          | 1.000               | -              | -         | yes             | 10.000               | 8138.550              | 1.000              | 1.000           |
| distributed   | rag-claude-pilot-7807c6b5 | evidence-engine | all        | reject         | 6b360bca67ce | 0.885           | 1.000           | 0.909                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 8708.000              | 1.000              | 1.000           |
| distributed   | rag-claude-s1-869ad7e8    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| distributed   | rag-claude-s1-869ad7e8    | evidence-engine | all        | reject         | 6b360bca67ce | 0.905           | 1.000           | 0.934                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 8279.200              | 1.000              | 1.000           |
| distributed   | rag-claude-s1-869ad7e8    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.300                | 0.300          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| distributed   | rag-claude-small-5cbb2530 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| distributed   | rag-claude-small-5cbb2530 | evidence-engine | all        | reject         | 6b360bca67ce | 0.667           | 0.882           | -                      | 0.000       | 0.000                | 0.000          | -                   | -              | -         | no              | 10.000               | 5151.400              | 1.000              | 1.000           |
| distributed   | rag-claude-small-5cbb2530 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.800                | 0.800          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| distributed   | rag-tpl-s1-79207ad1       | evidence-engine | all        | reject         | 6b360bca67ce | 0.902           | 1.000           | 1.000                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 7203.800              | 1.000              | 1.000           |
| complex       | rag-claude-pilot-d04573ee | evidence-engine | all        | reject         | 6b360bca67ce | 0.962           | 1.000           | 0.891                  | 0.000       | 0.667                | 1.000          | 0.667               | -              | -         | yes             | 10.000               | 13424.667             | 1.000              | 1.000           |
| complex       | rag-claude-s1-a5fa1731    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| complex       | rag-claude-s1-a5fa1731    | evidence-engine | all        | reject         | 6b360bca67ce | 0.934           | 1.000           | 0.944                  | 0.150       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 12714.250             | 1.000              | 1.000           |
| complex       | rag-claude-s1-a5fa1731    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| complex       | rag-tpl-hard-24ab4663     | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.946                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| complex       | rag-tpl-hard-24ab4663     | evidence-engine | all        | reject         | 6b360bca67ce | 0.709           | 1.000           | 0.981                  | 0.000       | 0.321                | 0.340          | 0.706               | -              | -         | yes             | 9.973                | 3256.286              | 0.973              | 1.000           |
| complex       | rag-tpl-hard-24ab4663     | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.143                | 0.060          | 0.833               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| complex       | rag-tpl-s1-f0f5d48e       | evidence-engine | all        | reject         | 6b360bca67ce | 0.937           | 1.000           | 1.000                  | 0.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 11822.300             | 1.000              | 1.000           |
| contradictory | rag-claude-pilot-3ef3b916 | evidence-engine | all        | reject         | 6b360bca67ce | 0.846           | 1.000           | 0.857                  | 0.667       | 0.667                | 0.667          | 1.000               | -              | -         | no              | 10.000               | 9599.000              | 1.000              | 0.667           |
| contradictory | rag-claude-s1-e4e9d603    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.000                | 1.000          | 0.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-claude-s1-e4e9d603    | evidence-engine | all        | reject         | 6b360bca67ce | 0.876           | 1.000           | 0.951                  | 0.850       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 8626.250              | 1.000              | 0.900           |
| contradictory | rag-claude-s1-e4e9d603    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.050                | 0.250          | 0.200               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-tpl-s1-56b0bc02       | evidence-engine | all        | reject         | 6b360bca67ce | 0.895           | 1.000           | 1.000                  | 0.750       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 8048.700              | 1.000              | 0.950           |
| mixed         | rag-claude-k1-adf90d94    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.750                | 1.000          | 0.800               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-k1-adf90d94    | evidence-engine | all        | reject         | 6b360bca67ce | 0.889           | 1.000           | 0.938                  | 0.750       | 0.917                | 0.900          | 1.000               | -              | -         | yes             | 9.958                | 8280.917              | 1.000              | 1.000           |
| mixed         | rag-claude-k1-adf90d94    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.167                | 0.250          | 0.400               | 0.857          | 0.857     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-pilot-931cb13b | evidence-engine | all        | reject         | 6b360bca67ce | 0.830           | 1.000           | 0.857                  | 0.667       | 0.667                | 0.667          | 1.000               | -              | -         | no              | 10.000               | 8342.000              | 1.000              | 1.000           |
| mixed         | rag-claude-s1-cf-5893772b | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.750                | 1.000          | 0.750               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-cf-5893772b | evidence-engine | all        | reject         | 6b360bca67ce | 0.890           | 1.000           | 0.956                  | 0.650       | 0.850                | 0.850          | 1.000               | -              | -         | yes             | 10.000               | 8912.450              | 1.000              | 1.000           |
| mixed         | rag-claude-s1-cf-5893772b | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.200                | 0.250          | 0.800               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-ec928480    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.800                | 1.000          | 0.800               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-ec928480    | evidence-engine | all        | reject         | 6b360bca67ce | 0.890           | 1.000           | 0.956                  | 0.650       | 0.850                | 0.850          | 1.000               | -              | -         | yes             | 10.000               | 8843.200              | 1.000              | 1.000           |
| mixed         | rag-claude-s1-ec928480    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.150                | 0.250          | 0.600               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-hard-b1c0fdfe     | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.375                | 0.380          | 0.842               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-hard-b1c0fdfe     | evidence-engine | all        | reject         | 6b360bca67ce | 0.930           | 1.000           | 0.991                  | 0.690       | 0.929                | 0.960          | 0.958               | -              | -         | yes             | 9.973                | 8233.188              | 1.000              | 1.000           |
| mixed         | rag-tpl-hard-b1c0fdfe     | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.116                | 0.050          | 0.400               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-k1-9c3bbb32       | evidence-engine | all        | reject         | 6b360bca67ce | 0.926           | 1.000           | 0.962                  | 0.800       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 9.958                | 7964.583              | 1.000              | 1.000           |
| mixed         | rag-tpl-s1-6162b495       | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.650                | 1.000          | 0.650               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-s1-6162b495       | evidence-engine | all        | reject         | 6b360bca67ce | 0.931           | 1.000           | 0.980                  | 0.750       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 8381.300              | 1.000              | 1.000           |
| mixed         | rag-tpl-s1-6162b495       | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.150                | 0.200          | 0.750               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-s1-cf-cb85326b    | evidence-engine | all        | reject         | 6b360bca67ce | 0.931           | 1.000           | 0.980                  | 0.750       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 8380.450              | 1.000              | 1.000           |

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
| rag-claude-small-5cbb2530 | paraphrased   | 5           | 5          | 5         | 5        | none            | 1.000           |
| rag-claude-small-5cbb2530 | distributed   | 5           | 5          | 5         | 5        | none            | 2.000           |
| rag-claude-small-7eb8078c | paraphrased   | 5           | 5          | 5         | 5        | none            | 1.000           |
| rag-claude-small-7eb8078c | distributed   | 5           | 5          | 5         | 5        | none            | 2.000           |
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
- rag-claude-small-5cbb2530: excluded none
- rag-claude-small-7eb8078c: excluded none
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
| explicit      | rag-claude-pilot-c2d26fcb | evidence-engine | all        | reject         | 6b360bca67ce | 0.931 [0.89, 1.00] | 3              | 1.000 [n/a]          | 3             | -                     | -          |
| explicit      | rag-claude-s1-eb14377d    | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | 0.000 [n/a]           | 20         |
| explicit      | rag-claude-s1-eb14377d    | evidence-engine | all        | reject         | 6b360bca67ce | 0.911 [0.86, 0.94] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| explicit      | rag-claude-s1-eb14377d    | rag-baseline    | -          | -              | -            | -                  | -              | 0.350 [0.15, 0.60]   | 20            | 0.650 [0.40, 0.85]    | 20         |
| explicit      | rag-tpl-s1-59c5118b       | evidence-engine | all        | reject         | 6b360bca67ce | 0.950 [0.91, 0.97] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| paraphrased   | rag-claude-pilot-d69436ff | evidence-engine | all        | reject         | 6b360bca67ce | 0.766 [0.67, 0.90] | 3              | 0.333 [0.00, 1.00]   | 3             | -                     | -          |
| paraphrased   | rag-claude-s1-c34803f0    | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | -0.400 [-0.65, -0.20] | 20         |
| paraphrased   | rag-claude-s1-c34803f0    | evidence-engine | all        | reject         | 6b360bca67ce | 0.853 [0.79, 0.92] | 20             | 0.600 [0.35, 0.80]   | 20            | -                     | -          |
| paraphrased   | rag-claude-s1-c34803f0    | rag-baseline    | -          | -              | -            | -                  | -              | 0.200 [0.05, 0.45]   | 20            | 0.400 [0.20, 0.65]    | 20         |
| paraphrased   | rag-claude-small-7eb8078c | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 5             | 0.000 [n/a]           | 5          |
| paraphrased   | rag-claude-small-7eb8078c | evidence-engine | all        | reject         | 6b360bca67ce | 0.971 [0.91, 1.00] | 5              | 1.000 [n/a]          | 5             | -                     | -          |
| paraphrased   | rag-claude-small-7eb8078c | rag-baseline    | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 5             | 0.000 [n/a]           | 5          |
| paraphrased   | rag-tpl-s1-4d15ddc4       | evidence-engine | all        | reject         | 6b360bca67ce | 0.972 [0.91, 1.00] | 20             | 0.950 [0.75, 1.00]   | 20            | -                     | -          |
| distributed   | rag-claude-pilot-7807c6b5 | evidence-engine | all        | reject         | 6b360bca67ce | 0.885 [0.82, 0.91] | 3              | 1.000 [n/a]          | 3             | -                     | -          |
| distributed   | rag-claude-s1-869ad7e8    | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | 0.000 [n/a]           | 20         |
| distributed   | rag-claude-s1-869ad7e8    | evidence-engine | all        | reject         | 6b360bca67ce | 0.905 [0.86, 0.93] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| distributed   | rag-claude-s1-869ad7e8    | rag-baseline    | -          | -              | -            | -                  | -              | 0.300 [0.15, 0.55]   | 20            | 0.700 [0.45, 0.85]    | 20         |
| distributed   | rag-claude-small-5cbb2530 | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 5             | -1.000 [n/a]          | 5          |
| distributed   | rag-claude-small-5cbb2530 | evidence-engine | all        | reject         | 6b360bca67ce | 0.667 [0.53, 0.80] | 5              | 0.000 [n/a]          | 5             | -                     | -          |
| distributed   | rag-claude-small-5cbb2530 | rag-baseline    | -          | -              | -            | -                  | -              | 0.800 [0.20, 1.00]   | 5             | -0.800 [-1.00, -0.20] | 5          |
| distributed   | rag-tpl-s1-79207ad1       | evidence-engine | all        | reject         | 6b360bca67ce | 0.902 [0.88, 0.92] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| complex       | rag-claude-pilot-d04573ee | evidence-engine | all        | reject         | 6b360bca67ce | 0.962 [0.94, 0.97] | 3              | 0.667 [0.00, 1.00]   | 3             | -                     | -          |
| complex       | rag-claude-s1-a5fa1731    | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | 0.000 [n/a]           | 20         |
| complex       | rag-claude-s1-a5fa1731    | evidence-engine | all        | reject         | 6b360bca67ce | 0.934 [0.90, 0.96] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| complex       | rag-claude-s1-a5fa1731    | rag-baseline    | -          | -              | -            | -                  | -              | 0.350 [0.15, 0.60]   | 20            | 0.650 [0.40, 0.85]    | 20         |
| complex       | rag-tpl-hard-24ab4663     | agent-baseline  | -          | -              | -            | -                  | -              | 0.946 [0.89, 0.98]   | 112           | -0.625 [-0.73, -0.51] | 112        |
| complex       | rag-tpl-hard-24ab4663     | evidence-engine | all        | reject         | 6b360bca67ce | 0.709 [0.67, 0.75] | 112            | 0.321 [0.23, 0.41]   | 112           | -                     | -          |
| complex       | rag-tpl-hard-24ab4663     | rag-baseline    | -          | -              | -            | -                  | -              | 0.143 [0.09, 0.21]   | 112           | 0.179 [0.10, 0.26]    | 112        |
| complex       | rag-tpl-s1-f0f5d48e       | evidence-engine | all        | reject         | 6b360bca67ce | 0.937 [0.91, 0.96] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| contradictory | rag-claude-pilot-3ef3b916 | evidence-engine | all        | reject         | 6b360bca67ce | 0.846 [0.67, 0.93] | 3              | 0.667 [0.00, 1.00]   | 3             | -                     | -          |
| contradictory | rag-claude-s1-e4e9d603    | agent-baseline  | -          | -              | -            | -                  | -              | 0.000 [n/a]          | 20            | 1.000 [n/a]           | 20         |
| contradictory | rag-claude-s1-e4e9d603    | evidence-engine | all        | reject         | 6b360bca67ce | 0.876 [0.82, 0.92] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| contradictory | rag-claude-s1-e4e9d603    | rag-baseline    | -          | -              | -            | -                  | -              | 0.050 [0.00, 0.25]   | 20            | 0.950 [0.75, 1.00]    | 20         |
| contradictory | rag-tpl-s1-56b0bc02       | evidence-engine | all        | reject         | 6b360bca67ce | 0.895 [0.84, 0.93] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| mixed         | rag-claude-k1-adf90d94    | agent-baseline  | -          | -              | -            | -                  | -              | 0.750 [0.54, 0.92]   | 24            | 0.167 [-0.04, 0.42]   | 24         |
| mixed         | rag-claude-k1-adf90d94    | evidence-engine | all        | reject         | 6b360bca67ce | 0.889 [0.85, 0.93] | 24             | 0.917 [0.71, 1.00]   | 24            | -                     | -          |
| mixed         | rag-claude-k1-adf90d94    | rag-baseline    | -          | -              | -            | -                  | -              | 0.167 [0.04, 0.33]   | 24            | 0.750 [0.54, 0.92]    | 24         |
| mixed         | rag-claude-pilot-931cb13b | evidence-engine | all        | reject         | 6b360bca67ce | 0.830 [0.67, 0.90] | 3              | 0.667 [0.00, 1.00]   | 3             | -                     | -          |
| mixed         | rag-claude-s1-cf-5893772b | agent-baseline  | -          | -              | -            | -                  | -              | 0.750 [0.50, 0.90]   | 20            | 0.100 [-0.20, 0.40]   | 20         |
| mixed         | rag-claude-s1-cf-5893772b | evidence-engine | all        | reject         | 6b360bca67ce | 0.890 [0.85, 0.93] | 20             | 0.850 [0.60, 0.95]   | 20            | -                     | -          |
| mixed         | rag-claude-s1-cf-5893772b | rag-baseline    | -          | -              | -            | -                  | -              | 0.200 [0.05, 0.45]   | 20            | 0.650 [0.40, 0.85]    | 20         |
| mixed         | rag-claude-s1-ec928480    | agent-baseline  | -          | -              | -            | -                  | -              | 0.800 [0.55, 0.95]   | 20            | 0.050 [-0.20, 0.35]   | 20         |
| mixed         | rag-claude-s1-ec928480    | evidence-engine | all        | reject         | 6b360bca67ce | 0.890 [0.85, 0.93] | 20             | 0.850 [0.60, 0.95]   | 20            | -                     | -          |
| mixed         | rag-claude-s1-ec928480    | rag-baseline    | -          | -              | -            | -                  | -              | 0.150 [0.05, 0.35]   | 20            | 0.700 [0.45, 0.85]    | 20         |
| mixed         | rag-tpl-hard-b1c0fdfe     | agent-baseline  | -          | -              | -            | -                  | -              | 0.375 [0.29, 0.46]   | 112           | 0.554 [0.45, 0.64]    | 112        |
| mixed         | rag-tpl-hard-b1c0fdfe     | evidence-engine | all        | reject         | 6b360bca67ce | 0.930 [0.91, 0.94] | 112            | 0.929 [0.87, 0.96]   | 112           | -                     | -          |
| mixed         | rag-tpl-hard-b1c0fdfe     | rag-baseline    | -          | -              | -            | -                  | -              | 0.116 [0.06, 0.18]   | 112           | 0.812 [0.74, 0.88]    | 112        |
| mixed         | rag-tpl-k1-9c3bbb32       | evidence-engine | all        | reject         | 6b360bca67ce | 0.926 [0.89, 0.96] | 24             | 1.000 [n/a]          | 24            | -                     | -          |
| mixed         | rag-tpl-s1-6162b495       | agent-baseline  | -          | -              | -            | -                  | -              | 0.650 [0.45, 0.85]   | 20            | 0.350 [0.15, 0.55]    | 20         |
| mixed         | rag-tpl-s1-6162b495       | evidence-engine | all        | reject         | 6b360bca67ce | 0.931 [0.90, 0.96] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| mixed         | rag-tpl-s1-6162b495       | rag-baseline    | -          | -              | -            | -                  | -              | 0.150 [0.05, 0.35]   | 20            | 0.850 [0.65, 0.95]    | 20         |
| mixed         | rag-tpl-s1-cf-cb85326b    | evidence-engine | all        | reject         | 6b360bca67ce | 0.931 [0.90, 0.96] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
