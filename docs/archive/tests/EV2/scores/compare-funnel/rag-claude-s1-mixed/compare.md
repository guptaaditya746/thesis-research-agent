# Comparison over corpora

| level   | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| mixed   | rag-claude-s1-ec928480 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.800                | 1.000          | 0.800               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-claude-s1-ec928480 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.800                | 1.000          | 0.800               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-claude-s1-ec928480 | evidence-engine | all        | reject         | 6b360bca67ce | 0.890           | 1.000           | 0.956                  | 0.650       | 0.850                | 0.850          | 1.000               | -              | -         | yes             | 10.000               | 8843.200              | 1.000              | 1.000           |
| mixed   | rag-claude-s1-ec928480 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.825           | 0.981           | 0.927                  | 0.850       | 0.900                | 0.900          | 1.000               | -              | -         | yes             | 7.400                | 4404.500              | 1.000              | 1.000           |
| mixed   | rag-claude-s1-ec928480 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.150                | 0.250          | 0.600               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-claude-s1-ec928480 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.150                | 0.250          | 0.600               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id              | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-s1-ec928480 | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-ec928480 | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-ec928480 | distributed   | 20          | 20         | 20        | 20       | none            | 1.100           |
| rag-claude-s1-ec928480 | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-ec928480 | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |

- rag-claude-s1-ec928480: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level   | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------|------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| mixed   | rag-claude-s1-ec928480 | agent-baseline  | -          | -              | -            | -                  | -              | 0.800 [0.55, 0.95]   | 20            | 0.050 [-0.20, 0.35]   | 20         |
| mixed   | rag-claude-s1-ec928480 | agent-baseline  | -          | -              | -            | -                  | -              | 0.800 [0.55, 0.95]   | 20            | 0.100 [-0.10, 0.35]   | 20         |
| mixed   | rag-claude-s1-ec928480 | evidence-engine | all        | reject         | 6b360bca67ce | 0.890 [0.85, 0.93] | 20             | 0.850 [0.60, 0.95]   | 20            | -                     | -          |
| mixed   | rag-claude-s1-ec928480 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.825 [0.76, 0.88] | 20             | 0.900 [0.70, 1.00]   | 20            | -                     | -          |
| mixed   | rag-claude-s1-ec928480 | rag-baseline    | -          | -              | -            | -                  | -              | 0.150 [0.05, 0.35]   | 20            | 0.700 [0.45, 0.85]    | 20         |
| mixed   | rag-claude-s1-ec928480 | rag-baseline    | -          | -              | -            | -                  | -              | 0.150 [0.05, 0.35]   | 20            | 0.750 [0.55, 0.90]    | 20         |
