# Comparison over corpora

| level    | corpus_id           | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|----------|---------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| explicit | rag-tpl-s1-59c5118b | evidence-engine | gaps       | escalate       | bfc107852891 | 0.853           | 1.000           | 1.000                  | 0.850       | 0.900                | 0.900          | 1.000               | -              | -         | yes             | 7.450                | 4109.200              | 1.000              | 1.000           |
| explicit | rag-tpl-s1-59c5118b | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.853           | 1.000           | 1.000                  | 0.850       | 0.900                | 0.900          | 1.000               | -              | -         | yes             | 7.450                | 4109.200              | 1.000              | 1.000           |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id           | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|---------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-tpl-s1-59c5118b | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-59c5118b | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-59c5118b | distributed   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-59c5118b | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-59c5118b | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |

- rag-tpl-s1-59c5118b: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level    | corpus_id           | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|----------|---------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| explicit | rag-tpl-s1-59c5118b | evidence-engine | gaps       | escalate       | bfc107852891 | 0.853 [0.80, 0.91] | 20             | 0.900 [0.70, 1.00]   | 20            | -                     | -          |
| explicit | rag-tpl-s1-59c5118b | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.853 [0.80, 0.91] | 20             | 0.900 [0.70, 1.00]   | 20            | -                     | -          |
