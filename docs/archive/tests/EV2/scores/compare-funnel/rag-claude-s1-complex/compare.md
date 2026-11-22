# Comparison over corpora

| level   | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| complex | rag-claude-s1-a5fa1731 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| complex | rag-claude-s1-a5fa1731 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| complex | rag-claude-s1-a5fa1731 | evidence-engine | all        | reject         | 6b360bca67ce | 0.934           | 1.000           | 0.944                  | 0.150       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 12714.250             | 1.000              | 1.000           |
| complex | rag-claude-s1-a5fa1731 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.802           | 1.000           | 0.866                  | 0.550       | 0.950                | 1.000          | 0.950               | -              | -         | yes             | 7.350                | 6097.750              | 1.000              | 1.000           |
| complex | rag-claude-s1-a5fa1731 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| complex | rag-claude-s1-a5fa1731 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id              | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-s1-a5fa1731 | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-a5fa1731 | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-a5fa1731 | distributed   | 20          | 20         | 20        | 20       | none            | 1.100           |
| rag-claude-s1-a5fa1731 | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-a5fa1731 | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |

- rag-claude-s1-a5fa1731: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level   | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------|------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| complex | rag-claude-s1-a5fa1731 | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | 0.000 [n/a]           | 20         |
| complex | rag-claude-s1-a5fa1731 | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | -0.050 [-0.27, 0.00]  | 20         |
| complex | rag-claude-s1-a5fa1731 | evidence-engine | all        | reject         | 6b360bca67ce | 0.934 [0.90, 0.96] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| complex | rag-claude-s1-a5fa1731 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.802 [0.74, 0.85] | 20             | 0.950 [0.73, 1.00]   | 20            | -                     | -          |
| complex | rag-claude-s1-a5fa1731 | rag-baseline    | -          | -              | -            | -                  | -              | 0.350 [0.15, 0.60]   | 20            | 0.650 [0.40, 0.85]    | 20         |
| complex | rag-claude-s1-a5fa1731 | rag-baseline    | -          | -              | -            | -                  | -              | 0.350 [0.15, 0.60]   | 20            | 0.600 [0.30, 0.80]    | 20         |
