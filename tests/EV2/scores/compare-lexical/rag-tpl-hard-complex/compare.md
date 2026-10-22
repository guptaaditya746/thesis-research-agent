# Comparison over corpora

| level   | corpus_id             | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|-----------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| complex | rag-tpl-hard-24ab4663 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.946                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| complex | rag-tpl-hard-24ab4663 | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.946                | 1.000          | 1.000               | -              | -         | yes             | -                    | -                     | -                  | -               |
| complex | rag-tpl-hard-24ab4663 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.619           | 1.000           | 1.000                  | 0.000       | 0.205                | 0.170          | 0.647               | -              | -         | yes             | 6.714                | 588.875               | 0.973              | 1.000           |
| complex | rag-tpl-hard-24ab4663 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.619           | 1.000           | 1.000                  | 0.000       | 0.205                | 0.170          | 0.647               | -              | -         | yes             | 6.688                | 588.875               | 0.973              | 1.000           |
| complex | rag-tpl-hard-24ab4663 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.143                | 0.060          | 0.833               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| complex | rag-tpl-hard-24ab4663 | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.143                | 0.060          | 0.833               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id             | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|-----------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-tpl-hard-24ab4663 | explicit      | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-24ab4663 | paraphrased   | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-24ab4663 | distributed   | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-24ab4663 | complex       | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-24ab4663 | contradictory | 100         | 100        | 112       | 112      | none            | 1.000           |

- rag-tpl-hard-24ab4663: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level   | corpus_id             | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------|-----------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| complex | rag-tpl-hard-24ab4663 | agent-baseline  | -          | -              | -            | -                  | -              | 0.946 [0.89, 0.98]   | 112           | -0.741 [-0.82, -0.62] | 112        |
| complex | rag-tpl-hard-24ab4663 | agent-baseline  | -          | -              | -            | -                  | -              | 0.946 [0.89, 0.98]   | 112           | -0.741 [-0.82, -0.62] | 112        |
| complex | rag-tpl-hard-24ab4663 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.619 [0.59, 0.65] | 112            | 0.205 [0.14, 0.29]   | 112           | -                     | -          |
| complex | rag-tpl-hard-24ab4663 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.619 [0.59, 0.65] | 112            | 0.205 [0.14, 0.29]   | 112           | -                     | -          |
| complex | rag-tpl-hard-24ab4663 | rag-baseline    | -          | -              | -            | -                  | -              | 0.143 [0.09, 0.21]   | 112           | 0.062 [0.00, 0.12]    | 112        |
| complex | rag-tpl-hard-24ab4663 | rag-baseline    | -          | -              | -            | -                  | -              | 0.143 [0.09, 0.21]   | 112           | 0.062 [0.00, 0.12]    | 112        |
