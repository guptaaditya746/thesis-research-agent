# Comparison over corpora

| level       | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| distributed | rag-claude-s1-869ad7e8 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| distributed | rag-claude-s1-869ad7e8 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| distributed | rag-claude-s1-869ad7e8 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.861           | 1.000           | 1.000                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 7.600                | 4905.250              | 1.000              | 1.000           |
| distributed | rag-claude-s1-869ad7e8 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.861           | 1.000           | 1.000                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 7.600                | 4905.250              | 1.000              | 1.000           |
| distributed | rag-claude-s1-869ad7e8 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.300                | 0.300          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| distributed | rag-claude-s1-869ad7e8 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.300                | 0.300          | 1.000               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id              | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-s1-869ad7e8 | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-869ad7e8 | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-869ad7e8 | distributed   | 20          | 20         | 20        | 20       | none            | 1.100           |
| rag-claude-s1-869ad7e8 | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-claude-s1-869ad7e8 | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |

- rag-claude-s1-869ad7e8: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level       | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|-------------|------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| distributed | rag-claude-s1-869ad7e8 | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | 0.000 [n/a]           | 20         |
| distributed | rag-claude-s1-869ad7e8 | agent-baseline  | -          | -              | -            | -                  | -              | 1.000 [n/a]          | 20            | 0.000 [n/a]           | 20         |
| distributed | rag-claude-s1-869ad7e8 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.861 [0.81, 0.91] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| distributed | rag-claude-s1-869ad7e8 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.861 [0.81, 0.91] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| distributed | rag-claude-s1-869ad7e8 | rag-baseline    | -          | -              | -            | -                  | -              | 0.300 [0.15, 0.55]   | 20            | 0.700 [0.45, 0.85]    | 20         |
| distributed | rag-claude-s1-869ad7e8 | rag-baseline    | -          | -              | -            | -                  | -              | 0.300 [0.15, 0.55]   | 20            | 0.700 [0.45, 0.85]    | 20         |
