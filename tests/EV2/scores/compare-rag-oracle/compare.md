# Comparison over corpora

| level         | corpus_id                 | system                           | strategy   | lexical_miss   | protocol   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------------|---------------------------|----------------------------------|------------|----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| explicit      | rag-claude-s1-eb14377d    | rag-baseline                     | -          | -              | -          | -               | -               | -                      | -           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| explicit      | rag-claude-s1-eb14377d    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | 0.000          | 0.000     | yes             | -                    | -                     | -                  | -               |
| paraphrased   | rag-claude-s1-c34803f0    | rag-baseline                     | -          | -              | -          | -               | -               | -                      | -           | 0.200                | 0.400          | 0.500               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| paraphrased   | rag-claude-s1-c34803f0    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -               | -                      | -           | 0.950                | 0.950          | 1.000               | 0.100          | 0.100     | yes             | -                    | -                     | -                  | -               |
| distributed   | rag-claude-s1-869ad7e8    | rag-baseline                     | -          | -              | -          | -               | -               | -                      | -           | 0.300                | 0.300          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| distributed   | rag-claude-s1-869ad7e8    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -               | -                      | -           | 0.950                | 1.000          | 0.950               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| complex       | rag-claude-s1-a5fa1731    | rag-baseline                     | -          | -              | -          | -               | -               | -                      | -           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| complex       | rag-claude-s1-a5fa1731    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -               | -                      | -           | 0.800                | 1.000          | 0.800               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-claude-s1-e4e9d603    | rag-baseline                     | -          | -              | -          | -               | -               | -                      | -           | 0.050                | 0.250          | 0.200               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-claude-s1-e4e9d603    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -               | -                      | -           | 0.300                | 0.700          | 0.429               | 0.944          | 0.944     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-k1-adf90d94    | rag-baseline                     | -          | -              | -          | -               | -               | -                      | -           | 0.167                | 0.250          | 0.400               | 0.857          | 0.857     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-k1-adf90d94    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -               | -                      | -           | 0.667                | 0.900          | 0.778               | 0.619          | 0.619     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-cf-5893772b | rag-baseline                     | -          | -              | -          | -               | -               | -                      | -           | 0.200                | 0.250          | 0.800               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-cf-5893772b | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -               | -                      | -           | 0.700                | 0.800          | 0.875               | 0.708          | 0.708     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-ec928480    | rag-baseline                     | -          | -              | -          | -               | -               | -                      | -           | 0.150                | 0.250          | 0.600               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-claude-s1-ec928480    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -               | -                      | -           | 0.800                | 0.950          | 0.842               | 0.636          | 0.636     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-hard-b1c0fdfe     | rag-baseline                     | -          | -              | -          | -               | -               | -                      | -           | 0.116                | 0.050          | 0.400               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed         | rag-tpl-hard-b1c0fdfe     | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -               | -                      | -           | 0.250                | 0.160          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |

`(diagnostic)`: oracle-synthesis and rag-oracle-passages read the ground truth; they bound what extraction or retrieval could give and are not baselines.

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id                 | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|---------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-k1-adf90d94    | explicit      | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-claude-k1-adf90d94    | paraphrased   | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-claude-k1-adf90d94    | distributed   | 20          | 20         | 24        | 24       | none            | 1.083           |
| rag-claude-k1-adf90d94    | complex       | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-claude-k1-adf90d94    | contradictory | 20          | 20         | 24        | 24       | none            | 1.000           |
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
| rag-tpl-hard-b1c0fdfe     | explicit      | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe     | paraphrased   | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe     | distributed   | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe     | complex       | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe     | contradictory | 100         | 100        | 112       | 112      | none            | 1.000           |

- rag-claude-k1-adf90d94: excluded none
- rag-claude-s1-a5fa1731: excluded none
- rag-claude-s1-e4e9d603: excluded none
- rag-claude-s1-869ad7e8: excluded none
- rag-claude-s1-eb14377d: excluded none
- rag-claude-s1-ec928480: excluded none
- rag-claude-s1-cf-5893772b: excluded none
- rag-claude-s1-c34803f0: excluded none
- rag-tpl-hard-b1c0fdfe: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level         | corpus_id                 | system                           | strategy   | lexical_miss   | protocol   | extraction_f1   | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------------|---------------------------|----------------------------------|------------|----------------|------------|-----------------|----------------|----------------------|---------------|-----------------------|------------|
| explicit      | rag-claude-s1-eb14377d    | rag-baseline                     | -          | -              | -          | -               | -              | 0.350 [0.15, 0.60]   | 20            | -                     | -          |
| explicit      | rag-claude-s1-eb14377d    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -              | 1.000 [n/a]          | 20            | -                     | -          |
| paraphrased   | rag-claude-s1-c34803f0    | rag-baseline                     | -          | -              | -          | -               | -              | 0.200 [0.05, 0.45]   | 20            | -                     | -          |
| paraphrased   | rag-claude-s1-c34803f0    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -              | 0.950 [0.75, 1.00]   | 20            | -                     | -          |
| distributed   | rag-claude-s1-869ad7e8    | rag-baseline                     | -          | -              | -          | -               | -              | 0.300 [0.15, 0.55]   | 20            | -                     | -          |
| distributed   | rag-claude-s1-869ad7e8    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -              | 0.950 [0.75, 1.00]   | 20            | -                     | -          |
| complex       | rag-claude-s1-a5fa1731    | rag-baseline                     | -          | -              | -          | -               | -              | 0.350 [0.15, 0.60]   | 20            | -                     | -          |
| complex       | rag-claude-s1-a5fa1731    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -              | 0.800 [0.55, 0.95]   | 20            | -                     | -          |
| contradictory | rag-claude-s1-e4e9d603    | rag-baseline                     | -          | -              | -          | -               | -              | 0.050 [0.00, 0.25]   | 20            | -                     | -          |
| contradictory | rag-claude-s1-e4e9d603    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -              | 0.300 [0.15, 0.55]   | 20            | -                     | -          |
| mixed         | rag-claude-k1-adf90d94    | rag-baseline                     | -          | -              | -          | -               | -              | 0.167 [0.04, 0.33]   | 24            | -                     | -          |
| mixed         | rag-claude-k1-adf90d94    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -              | 0.667 [0.46, 0.83]   | 24            | -                     | -          |
| mixed         | rag-claude-s1-cf-5893772b | rag-baseline                     | -          | -              | -          | -               | -              | 0.200 [0.05, 0.45]   | 20            | -                     | -          |
| mixed         | rag-claude-s1-cf-5893772b | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -              | 0.700 [0.45, 0.90]   | 20            | -                     | -          |
| mixed         | rag-claude-s1-ec928480    | rag-baseline                     | -          | -              | -          | -               | -              | 0.150 [0.05, 0.35]   | 20            | -                     | -          |
| mixed         | rag-claude-s1-ec928480    | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -              | 0.800 [0.55, 0.95]   | 20            | -                     | -          |
| mixed         | rag-tpl-hard-b1c0fdfe     | rag-baseline                     | -          | -              | -          | -               | -              | 0.116 [0.06, 0.18]   | 112           | -                     | -          |
| mixed         | rag-tpl-hard-b1c0fdfe     | rag-oracle-passages (diagnostic) | -          | -              | -          | -               | -              | 0.250 [0.18, 0.34]   | 112           | -                     | -          |
