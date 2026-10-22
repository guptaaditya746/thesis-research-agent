# Comparison over corpora

| level       | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| paraphrased | rag-claude-s1-c34803f0 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-claude-s1-c34803f0 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-claude-s1-c34803f0 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.685           | 0.977           | 0.920                  | 0.450       | 0.450                | 0.450          | 1.000               | -              | -         | yes             | 7.800                | 4900.900              | 1.000              | 1.000           |
| paraphrased | rag-claude-s1-c34803f0 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.696           | 0.977           | 0.920                  | 0.450       | 0.450                | 0.450          | 1.000               | -              | -         | yes             | 7.850                | 4986.400              | 1.000              | 1.000           |
| paraphrased | rag-claude-s1-c34803f0 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.200                | 0.400          | 0.500               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-claude-s1-c34803f0 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.200                | 0.400          | 0.500               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id              | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-s1-c34803f0 | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-c34803f0 | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-c34803f0 | distributed   | 20          | 20         | 20        | 20       | none            | 1.100           |
| rag-claude-s1-c34803f0 | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-c34803f0 | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |

- rag-claude-s1-c34803f0: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level       | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|-------------|------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| paraphrased | rag-claude-s1-c34803f0 | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | -0.550 [-0.75, -0.35] | 20         |
| paraphrased | rag-claude-s1-c34803f0 | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | -0.550 [-0.75, -0.35] | 20         |
| paraphrased | rag-claude-s1-c34803f0 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.685 [0.53, 0.81] | 20             | 0.450 [0.25, 0.65]   | 20            | -                     | -          |
| paraphrased | rag-claude-s1-c34803f0 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.696 [0.54, 0.82] | 20             | 0.450 [0.25, 0.65]   | 20            | -                     | -          |
| paraphrased | rag-claude-s1-c34803f0 | rag-baseline    | -          | -              | -            | -                  | -              | 0.200 [0.05, 0.45]   | 20            | 0.250 [0.00, 0.50]    | 20         |
| paraphrased | rag-claude-s1-c34803f0 | rag-baseline    | -          | -              | -            | -                  | -              | 0.200 [0.05, 0.45]   | 20            | 0.250 [0.00, 0.50]    | 20         |
