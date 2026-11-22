# Comparison over corpora

| level       | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|---------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| paraphrased | rag-claude-small-7eb8078c | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-claude-small-7eb8078c | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-claude-small-7eb8078c | evidence-engine | all        | reject         | 8fe0ed7ea0bb | 0.971           | 1.000           | 0.917                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 14.000               | 374535.200            | 1.000              | 1.000           |
| paraphrased | rag-claude-small-7eb8078c | evidence-engine | gaps       | reject         | 8fe0ed7ea0bb | 0.522           | 1.000           | 1.000                  | 0.200       | 0.200                | 0.200          | 1.000               | -              | -         | no              | 8.200                | 72632.000             | 1.000              | 1.000           |
| paraphrased | rag-claude-small-7eb8078c | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-claude-small-7eb8078c | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id                 | level       | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|---------------------------|-------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-small-7eb8078c | paraphrased | 5           | 5          | 5         | 5        | none            | 1.000           |
| rag-claude-small-7eb8078c | distributed | 5           | 5          | 5         | 5        | none            | 2.000           |

- rag-claude-small-7eb8078c: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level       | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|-------------|---------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| paraphrased | rag-claude-small-7eb8078c | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 5             | 0.000 [n/a]           | 5          |
| paraphrased | rag-claude-small-7eb8078c | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 5             | -0.800 [-1.00, -0.20] | 5          |
| paraphrased | rag-claude-small-7eb8078c | evidence-engine | all        | reject         | 8fe0ed7ea0bb | 0.971 [0.91, 1.00] | 5              | 1.000 [n/a]          | 5             | -                     | -          |
| paraphrased | rag-claude-small-7eb8078c | evidence-engine | gaps       | reject         | 8fe0ed7ea0bb | 0.522 [0.32, 0.91] | 5              | 0.200 [0.00, 0.80]   | 5             | -                     | -          |
| paraphrased | rag-claude-small-7eb8078c | rag-baseline    | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 5             | 0.000 [n/a]           | 5          |
| paraphrased | rag-claude-small-7eb8078c | rag-baseline    | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 5             | -0.800 [-1.00, -0.20] | 5          |
