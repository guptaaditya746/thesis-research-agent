# Comparison over corpora

| level         | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------------|------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| contradictory | rag-claude-s1-e4e9d603 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.000                | 1.000          | 0.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-claude-s1-e4e9d603 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.000                | 1.000          | 0.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-claude-s1-e4e9d603 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.785           | 0.982           | 1.000                  | 0.800       | 0.800                | 0.900          | 0.889               | -              | -         | yes             | 6.750                | 3745.000              | 1.000              | 0.900           |
| contradictory | rag-claude-s1-e4e9d603 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.785           | 0.982           | 1.000                  | 0.800       | 0.800                | 0.900          | 0.889               | -              | -         | yes             | 6.750                | 3745.000              | 1.000              | 0.900           |
| contradictory | rag-claude-s1-e4e9d603 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.050                | 0.250          | 0.200               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-claude-s1-e4e9d603 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.050                | 0.250          | 0.200               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id              | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-s1-e4e9d603 | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-e4e9d603 | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-e4e9d603 | distributed   | 20          | 20         | 20        | 20       | none            | 1.100           |
| rag-claude-s1-e4e9d603 | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-e4e9d603 | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |

- rag-claude-s1-e4e9d603: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level         | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------------|------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| contradictory | rag-claude-s1-e4e9d603 | agent-baseline  | -          | -              | -            | -                  | -              | 0.000 [n/a]          | 20            | 0.800 [0.60, 0.95]    | 20         |
| contradictory | rag-claude-s1-e4e9d603 | agent-baseline  | -          | -              | -            | -                  | -              | 0.000 [n/a]          | 20            | 0.800 [0.60, 0.95]    | 20         |
| contradictory | rag-claude-s1-e4e9d603 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.785 [0.67, 0.85] | 20             | 0.800 [0.60, 0.95]   | 20            | -                     | -          |
| contradictory | rag-claude-s1-e4e9d603 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.785 [0.67, 0.85] | 20             | 0.800 [0.60, 0.95]   | 20            | -                     | -          |
| contradictory | rag-claude-s1-e4e9d603 | rag-baseline    | -          | -              | -            | -                  | -              | 0.050 [0.00, 0.25]   | 20            | 0.750 [0.44, 0.90]    | 20         |
| contradictory | rag-claude-s1-e4e9d603 | rag-baseline    | -          | -              | -            | -                  | -              | 0.050 [0.00, 0.25]   | 20            | 0.750 [0.44, 0.90]    | 20         |
