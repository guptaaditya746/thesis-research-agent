# Comparison over corpora

| level         | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------------|---------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| explicit      | rag-claude-pilot-c2d26fcb | evidence-engine | gaps       | escalate       | bfc107852891 | 0.792           | 1.000           | 0.857                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 8.333                | 6809.667              | 1.000              | 1.000           |
| explicit      | rag-claude-s1-eb14377d    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| explicit      | rag-claude-s1-eb14377d    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.824           | 0.992           | 1.000                  | 0.950       | 0.950                | 0.950          | 1.000               | -              | -         | yes             | 7.150                | 3417.950              | 1.000              | 1.000           |
| explicit      | rag-claude-s1-eb14377d    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| explicit      | rag-tpl-s1-59c5118b       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.853           | 1.000           | 1.000                  | 0.850       | 0.900                | 0.900          | 1.000               | -              | -         | yes             | 7.450                | 4109.200              | 1.000              | 1.000           |
| paraphrased   | rag-claude-pilot-d69436ff | evidence-engine | gaps       | escalate       | bfc107852891 | 0.600           | 1.000           | 1.000                  | 0.333       | 0.333                | 0.333          | 1.000               | -              | -         | no              | 7.667                | 3767.667              | 1.000              | 1.000           |
| paraphrased   | rag-claude-s1-c34803f0    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| paraphrased   | rag-claude-s1-c34803f0    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.685           | 0.977           | 0.920                  | 0.450       | 0.450                | 0.450          | 1.000               | -              | -         | yes             | 7.800                | 4900.900              | 1.000              | 1.000           |
| paraphrased   | rag-claude-s1-c34803f0    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.200                | 0.400          | 0.500               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| paraphrased   | rag-tpl-s1-4d15ddc4       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.500           | 1.000           | 1.000                  | 0.150       | 0.150                | 0.150          | 1.000               | -              | -         | no              | 7.300                | 3378.750              | 1.000              | 1.000           |
| distributed   | rag-claude-pilot-7807c6b5 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.775           | 1.000           | 0.857                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 8.333                | 6171.000              | 1.000              | 1.000           |
| distributed   | rag-claude-s1-869ad7e8    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| distributed   | rag-claude-s1-869ad7e8    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.861           | 1.000           | 1.000                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 7.600                | 4905.250              | 1.000              | 1.000           |
| distributed   | rag-claude-s1-869ad7e8    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.300                | 0.300          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| distributed   | rag-tpl-s1-79207ad1       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.872           | 1.000           | 1.000                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 7.600                | 4333.100              | 1.000              | 1.000           |
| complex       | rag-claude-pilot-d04573ee | evidence-engine | gaps       | escalate       | bfc107852891 | 0.692           | 1.000           | 0.536                  | 0.333       | 0.667                | 1.000          | 0.667               | -              | -         | yes             | 8.333                | 8618.667              | 1.000              | 1.000           |
| complex       | rag-claude-s1-a5fa1731    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| complex       | rag-claude-s1-a5fa1731    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.800           | 1.000           | 0.866                  | 0.500       | 0.950                | 1.000          | 0.950               | -              | -         | yes             | 7.350                | 6086.250              | 1.000              | 1.000           |
| complex       | rag-claude-s1-a5fa1731    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| complex       | rag-tpl-hard-24ab4663     | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.946                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| complex       | rag-tpl-hard-24ab4663     | evidence-engine | gaps       | escalate       | bfc107852891 | 0.619           | 1.000           | 1.000                  | 0.000       | 0.205                | 0.170          | 0.647               | -              | -         | yes             | 6.714                | 588.875               | 0.973              | 1.000           |
| complex       | rag-tpl-hard-24ab4663     | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.143                | 0.060          | 0.833               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| complex       | rag-tpl-s1-f0f5d48e       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.770           | 1.000           | 0.825                  | 0.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 7.350                | 5244.700              | 1.000              | 1.000           |
| contradictory | rag-claude-pilot-3ef3b916 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.619           | 1.000           | 0.800                  | 0.667       | 0.667                | 0.667          | 1.000               | -              | -         | no              | 6.333                | 5354.000              | 1.000              | 0.667           |
| contradictory | rag-claude-s1-e4e9d603    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.000                | 1.000          | 0.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-claude-s1-e4e9d603    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.785           | 0.982           | 1.000                  | 0.800       | 0.800                | 0.900          | 0.889               | -              | -         | yes             | 6.750                | 3745.000              | 1.000              | 0.900           |
| contradictory | rag-claude-s1-e4e9d603    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.050                | 0.250          | 0.200               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-tpl-s1-56b0bc02       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.793           | 1.000           | 0.973                  | 0.700       | 0.750                | 0.850          | 0.882               | -              | -         | yes             | 6.650                | 3223.750              | 1.000              | 0.900           |
| mixed         | rag-claude-k1-adf90d94    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.750                | 1.000          | 0.800               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-k1-adf90d94    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.848           | 0.983           | 0.935                  | 0.900       | 0.958                | 0.950          | 1.000               | -              | -         | yes             | 7.125                | 4500.083              | 1.000              | 1.000           |
| mixed         | rag-claude-k1-adf90d94    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.167                | 0.250          | 0.400               | 0.857          | 0.857     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-pilot-931cb13b | evidence-engine | gaps       | escalate       | bfc107852891 | 0.682           | 1.000           | 0.800                  | 0.667       | 0.667                | 0.667          | 1.000               | -              | -         | no              | 8.000                | 4944.333              | 1.000              | 1.000           |
| mixed         | rag-claude-s1-cf-5893772b | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.750                | 1.000          | 0.750               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-cf-5893772b | evidence-engine | gaps       | escalate       | bfc107852891 | 0.834           | 0.981           | 0.930                  | 0.850       | 0.950                | 0.950          | 1.000               | -              | -         | yes             | 7.450                | 4608.100              | 1.000              | 1.000           |
| mixed         | rag-claude-s1-cf-5893772b | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.200                | 0.250          | 0.800               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-ec928480    | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.800                | 1.000          | 0.800               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-ec928480    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.834           | 0.981           | 0.930                  | 0.850       | 0.950                | 0.950          | 1.000               | -              | -         | yes             | 7.450                | 4563.450              | 1.000              | 1.000           |
| mixed         | rag-claude-s1-ec928480    | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.150                | 0.250          | 0.600               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-hard-b1c0fdfe     | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.375                | 0.380          | 0.842               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-hard-b1c0fdfe     | evidence-engine | gaps       | escalate       | bfc107852891 | 0.734           | 1.000           | 0.996                  | 0.610       | 0.661                | 0.660          | 0.939               | -              | -         | yes             | 7.330                | 3564.438              | 0.973              | 1.000           |
| mixed         | rag-tpl-hard-b1c0fdfe     | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.116                | 0.050          | 0.400               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-k1-9c3bbb32       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.784           | 1.000           | 0.965                  | 0.650       | 0.833                | 0.800          | 1.000               | -              | -         | yes             | 6.958                | 3855.875              | 1.000              | 1.000           |
| mixed         | rag-tpl-s1-6162b495       | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.650                | 1.000          | 0.650               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-s1-6162b495       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.769           | 1.000           | 0.962                  | 0.600       | 0.800                | 0.800          | 1.000               | -              | -         | yes             | 7.250                | 3735.200              | 1.000              | 1.000           |
| mixed         | rag-tpl-s1-6162b495       | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.150                | 0.200          | 0.750               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-s1-cf-cb85326b    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.769           | 1.000           | 0.962                  | 0.600       | 0.800                | 0.800          | 1.000               | -              | -         | yes             | 7.250                | 3736.300              | 1.000              | 1.000           |

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
| explicit      | rag-claude-pilot-c2d26fcb | evidence-engine | gaps       | escalate       | bfc107852891 | 0.792 [0.75, 0.88] | 3              | 1.000 [n/a]          | 3             | -                     | -          |
| explicit      | rag-claude-s1-eb14377d    | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | -0.050 [-0.27, 0.00]  | 20         |
| explicit      | rag-claude-s1-eb14377d    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.824 [0.78, 0.88] | 20             | 0.950 [0.73, 1.00]   | 20            | -                     | -          |
| explicit      | rag-claude-s1-eb14377d    | rag-baseline    | -          | -              | -            | -                  | -              | 0.350 [0.15, 0.60]   | 20            | 0.600 [0.35, 0.80]    | 20         |
| explicit      | rag-tpl-s1-59c5118b       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.853 [0.80, 0.91] | 20             | 0.900 [0.70, 1.00]   | 20            | -                     | -          |
| paraphrased   | rag-claude-pilot-d69436ff | evidence-engine | gaps       | escalate       | bfc107852891 | 0.600 [0.33, 1.00] | 3              | 0.333 [0.00, 1.00]   | 3             | -                     | -          |
| paraphrased   | rag-claude-s1-c34803f0    | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | -0.550 [-0.75, -0.35] | 20         |
| paraphrased   | rag-claude-s1-c34803f0    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.685 [0.53, 0.81] | 20             | 0.450 [0.25, 0.65]   | 20            | -                     | -          |
| paraphrased   | rag-claude-s1-c34803f0    | rag-baseline    | -          | -              | -            | -                  | -              | 0.200 [0.05, 0.45]   | 20            | 0.250 [0.00, 0.50]    | 20         |
| paraphrased   | rag-tpl-s1-4d15ddc4       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.500 [0.41, 0.66] | 20             | 0.150 [0.05, 0.35]   | 20            | -                     | -          |
| distributed   | rag-claude-pilot-7807c6b5 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.775 [0.75, 0.82] | 3              | 1.000 [n/a]          | 3             | -                     | -          |
| distributed   | rag-claude-s1-869ad7e8    | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | 0.000 [n/a]           | 20         |
| distributed   | rag-claude-s1-869ad7e8    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.861 [0.81, 0.91] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| distributed   | rag-claude-s1-869ad7e8    | rag-baseline    | -          | -              | -            | -                  | -              | 0.300 [0.15, 0.55]   | 20            | 0.700 [0.45, 0.85]    | 20         |
| distributed   | rag-tpl-s1-79207ad1       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.872 [0.83, 0.92] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| complex       | rag-claude-pilot-d04573ee | evidence-engine | gaps       | escalate       | bfc107852891 | 0.692 [0.44, 0.87] | 3              | 0.667 [0.00, 1.00]   | 3             | -                     | -          |
| complex       | rag-claude-s1-a5fa1731    | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | -0.050 [-0.27, 0.00]  | 20         |
| complex       | rag-claude-s1-a5fa1731    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.800 [0.73, 0.85] | 20             | 0.950 [0.73, 1.00]   | 20            | -                     | -          |
| complex       | rag-claude-s1-a5fa1731    | rag-baseline    | -          | -              | -            | -                  | -              | 0.350 [0.15, 0.60]   | 20            | 0.600 [0.30, 0.80]    | 20         |
| complex       | rag-tpl-hard-24ab4663     | agent-baseline  | -          | -              | -            | -                  | -              | 0.946 [0.89, 0.98]   | 112           | -0.741 [-0.82, -0.62] | 112        |
| complex       | rag-tpl-hard-24ab4663     | evidence-engine | gaps       | escalate       | bfc107852891 | 0.619 [0.59, 0.65] | 112            | 0.205 [0.14, 0.29]   | 112           | -                     | -          |
| complex       | rag-tpl-hard-24ab4663     | rag-baseline    | -          | -              | -            | -                  | -              | 0.143 [0.09, 0.21]   | 112           | 0.062 [0.00, 0.12]    | 112        |
| complex       | rag-tpl-s1-f0f5d48e       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.770 [0.70, 0.82] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| contradictory | rag-claude-pilot-3ef3b916 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.619 [0.00, 0.83] | 3              | 0.667 [0.00, 1.00]   | 3             | -                     | -          |
| contradictory | rag-claude-s1-e4e9d603    | agent-baseline  | -          | -              | -            | -                  | -              | 0.000 [n/a]          | 20            | 0.800 [0.60, 0.95]    | 20         |
| contradictory | rag-claude-s1-e4e9d603    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.785 [0.67, 0.85] | 20             | 0.800 [0.60, 0.95]   | 20            | -                     | -          |
| contradictory | rag-claude-s1-e4e9d603    | rag-baseline    | -          | -              | -            | -                  | -              | 0.050 [0.00, 0.25]   | 20            | 0.750 [0.44, 0.90]    | 20         |
| contradictory | rag-tpl-s1-56b0bc02       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.793 [0.70, 0.85] | 20             | 0.750 [0.50, 0.90]   | 20            | -                     | -          |
| mixed         | rag-claude-k1-adf90d94    | agent-baseline  | -          | -              | -            | -                  | -              | 0.750 [0.54, 0.92]   | 24            | 0.208 [0.04, 0.42]    | 24         |
| mixed         | rag-claude-k1-adf90d94    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.848 [0.79, 0.90] | 24             | 0.958 [0.79, 1.00]   | 24            | -                     | -          |
| mixed         | rag-claude-k1-adf90d94    | rag-baseline    | -          | -              | -            | -                  | -              | 0.167 [0.04, 0.33]   | 24            | 0.792 [0.58, 0.92]    | 24         |
| mixed         | rag-claude-pilot-931cb13b | evidence-engine | gaps       | escalate       | bfc107852891 | 0.682 [0.33, 0.83] | 3              | 0.667 [0.00, 1.00]   | 3             | -                     | -          |
| mixed         | rag-claude-s1-cf-5893772b | agent-baseline  | -          | -              | -            | -                  | -              | 0.750 [0.50, 0.90]   | 20            | 0.200 [0.00, 0.45]    | 20         |
| mixed         | rag-claude-s1-cf-5893772b | evidence-engine | gaps       | escalate       | bfc107852891 | 0.834 [0.77, 0.89] | 20             | 0.950 [0.75, 1.00]   | 20            | -                     | -          |
| mixed         | rag-claude-s1-cf-5893772b | rag-baseline    | -          | -              | -            | -                  | -              | 0.200 [0.05, 0.45]   | 20            | 0.750 [0.55, 0.90]    | 20         |
| mixed         | rag-claude-s1-ec928480    | agent-baseline  | -          | -              | -            | -                  | -              | 0.800 [0.55, 0.95]   | 20            | 0.150 [-0.05, 0.40]   | 20         |
| mixed         | rag-claude-s1-ec928480    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.834 [0.77, 0.89] | 20             | 0.950 [0.75, 1.00]   | 20            | -                     | -          |
| mixed         | rag-claude-s1-ec928480    | rag-baseline    | -          | -              | -            | -                  | -              | 0.150 [0.05, 0.35]   | 20            | 0.800 [0.55, 0.95]    | 20         |
| mixed         | rag-tpl-hard-b1c0fdfe     | agent-baseline  | -          | -              | -            | -                  | -              | 0.375 [0.29, 0.46]   | 112           | 0.286 [0.16, 0.40]    | 112        |
| mixed         | rag-tpl-hard-b1c0fdfe     | evidence-engine | gaps       | escalate       | bfc107852891 | 0.734 [0.68, 0.77] | 112            | 0.661 [0.56, 0.74]   | 112           | -                     | -          |
| mixed         | rag-tpl-hard-b1c0fdfe     | rag-baseline    | -          | -              | -            | -                  | -              | 0.116 [0.06, 0.18]   | 112           | 0.545 [0.45, 0.63]    | 112        |
| mixed         | rag-tpl-k1-9c3bbb32       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.784 [0.71, 0.86] | 24             | 0.833 [0.62, 0.96]   | 24            | -                     | -          |
| mixed         | rag-tpl-s1-6162b495       | agent-baseline  | -          | -              | -            | -                  | -              | 0.650 [0.45, 0.85]   | 20            | 0.150 [-0.15, 0.45]   | 20         |
| mixed         | rag-tpl-s1-6162b495       | evidence-engine | gaps       | escalate       | bfc107852891 | 0.769 [0.69, 0.85] | 20             | 0.800 [0.60, 0.95]   | 20            | -                     | -          |
| mixed         | rag-tpl-s1-6162b495       | rag-baseline    | -          | -              | -            | -                  | -              | 0.150 [0.05, 0.35]   | 20            | 0.650 [0.40, 0.85]    | 20         |
| mixed         | rag-tpl-s1-cf-cb85326b    | evidence-engine | gaps       | escalate       | bfc107852891 | 0.769 [0.69, 0.85] | 20             | 0.800 [0.60, 0.95]   | 20            | -                     | -          |
