# Comparison over corpora

| level   | corpus_id             | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|-----------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| mixed   | rag-tpl-hard-b1c0fdfe | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.375                | 0.380          | 0.842               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-tpl-hard-b1c0fdfe | agent-baseline  | -          | -              | -            | -               | -               | -                      | -           | 0.375                | 0.380          | 0.842               | -              | -         | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-tpl-hard-b1c0fdfe | evidence-engine | gaps       | escalate       | bfc107852891 | 0.734           | 1.000           | 0.996                  | 0.610       | 0.661                | 0.660          | 0.939               | -              | -         | yes             | 7.330                | 3564.438              | 0.973              | 1.000           |
| mixed   | rag-tpl-hard-b1c0fdfe | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.801           | 1.000           | 0.900                  | 0.620       | 0.804                | 0.830          | 0.940               | -              | -         | yes             | 7.330                | 4320.107              | 1.000              | 1.000           |
| mixed   | rag-tpl-hard-b1c0fdfe | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.116                | 0.050          | 0.400               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-tpl-hard-b1c0fdfe | rag-baseline    | -          | -              | -            | -               | -               | -                      | -           | 0.116                | 0.050          | 0.400               | 1.000          | 1.000     | yes             | -                    | -                     | -                  | -               |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id             | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|-----------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-tpl-hard-b1c0fdfe | explicit      | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe | paraphrased   | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe | distributed   | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe | complex       | 100         | 100        | 112       | 112      | none            | 1.000           |
| rag-tpl-hard-b1c0fdfe | contradictory | 100         | 100        | 112       | 112      | none            | 1.000           |

- rag-tpl-hard-b1c0fdfe: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level   | corpus_id             | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------|-----------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| mixed   | rag-tpl-hard-b1c0fdfe | agent-baseline  | -          | -              | -            | -                  | -              | 0.375 [0.29, 0.46]   | 112           | 0.429 [0.32, 0.54]    | 112        |
| mixed   | rag-tpl-hard-b1c0fdfe | agent-baseline  | -          | -              | -            | -                  | -              | 0.375 [0.29, 0.46]   | 112           | 0.286 [0.16, 0.40]    | 112        |
| mixed   | rag-tpl-hard-b1c0fdfe | evidence-engine | gaps       | escalate       | bfc107852891 | 0.734 [0.68, 0.77] | 112            | 0.661 [0.56, 0.74]   | 112           | -                     | -          |
| mixed   | rag-tpl-hard-b1c0fdfe | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.801 [0.77, 0.83] | 112            | 0.804 [0.72, 0.87]   | 112           | -                     | -          |
| mixed   | rag-tpl-hard-b1c0fdfe | rag-baseline    | -          | -              | -            | -                  | -              | 0.116 [0.06, 0.18]   | 112           | 0.688 [0.60, 0.77]    | 112        |
| mixed   | rag-tpl-hard-b1c0fdfe | rag-baseline    | -          | -              | -            | -                  | -              | 0.116 [0.06, 0.18]   | 112           | 0.545 [0.45, 0.63]    | 112        |
