# Comparison over corpora

| level   | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| mixed   | rag-claude-k1-adf90d94 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.750                | 1.000          | 0.800               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-claude-k1-adf90d94 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.750                | 1.000          | 0.800               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-claude-k1-adf90d94 | evidence-engine | all        | reject         | 6b360bca67ce | 0.889           | 1.000           | 0.938                  | 0.750       | 0.917                | 0.900          | 1.000               | -              | -         | yes             | 9.958                | 8280.917              | 1.000              | 1.000           |
| mixed   | rag-claude-k1-adf90d94 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.851           | 0.983           | 0.936                  | 0.950       | 0.958                | 0.950          | 1.000               | -              | -         | yes             | 7.083                | 4483.167              | 1.000              | 1.000           |
| mixed   | rag-claude-k1-adf90d94 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.167                | 0.250          | 0.400               | 0.857          | 0.857     | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-claude-k1-adf90d94 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.167                | 0.250          | 0.400               | 0.857          | 0.857     | yes             | -                    | -                     | -                  | -               |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id              | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-k1-adf90d94 | explicit      | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-claude-k1-adf90d94 | paraphrased   | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-claude-k1-adf90d94 | distributed   | 20          | 20         | 24        | 24       | none            | 1.083           |
| rag-claude-k1-adf90d94 | complex       | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-claude-k1-adf90d94 | contradictory | 20          | 20         | 24        | 24       | none            | 1.000           |

- rag-claude-k1-adf90d94: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level   | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------|------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| mixed   | rag-claude-k1-adf90d94 | agent-baseline  | -          | -              | -            | -                  | -              | 0.750 [0.54, 0.92]   | 24            | 0.167 [-0.04, 0.42]   | 24         |
| mixed   | rag-claude-k1-adf90d94 | agent-baseline  | -          | -              | -            | -                  | -              | 0.750 [0.54, 0.92]   | 24            | 0.208 [0.04, 0.42]    | 24         |
| mixed   | rag-claude-k1-adf90d94 | evidence-engine | all        | reject         | 6b360bca67ce | 0.889 [0.85, 0.93] | 24             | 0.917 [0.71, 1.00]   | 24            | -                     | -          |
| mixed   | rag-claude-k1-adf90d94 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.851 [0.79, 0.90] | 24             | 0.958 [0.79, 1.00]   | 24            | -                     | -          |
| mixed   | rag-claude-k1-adf90d94 | rag-baseline    | -          | -              | -            | -                  | -              | 0.167 [0.04, 0.33]   | 24            | 0.750 [0.54, 0.92]    | 24         |
| mixed   | rag-claude-k1-adf90d94 | rag-baseline    | -          | -              | -            | -                  | -              | 0.167 [0.04, 0.33]   | 24            | 0.792 [0.58, 0.92]    | 24         |
