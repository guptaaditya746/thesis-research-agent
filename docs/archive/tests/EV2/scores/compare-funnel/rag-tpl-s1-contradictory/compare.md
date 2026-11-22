# Comparison over corpora

| level         | corpus_id           | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------------|---------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | all        | reject         | 6b360bca67ce | 0.895           | 1.000           | 1.000                  | 0.750       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 8048.700              | 1.000              | 0.950           |
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.804           | 1.000           | 1.000                  | 0.800       | 0.800                | 0.900          | 0.889               | -              | -         | yes             | 6.950                | 3384.750              | 1.000              | 0.950           |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id           | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|---------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-tpl-s1-56b0bc02 | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-56b0bc02 | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-56b0bc02 | distributed   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-56b0bc02 | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-56b0bc02 | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |

- rag-tpl-s1-56b0bc02: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level         | corpus_id           | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------------|---------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | all        | reject         | 6b360bca67ce | 0.895 [0.84, 0.93] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.804 [0.73, 0.86] | 20             | 0.800 [0.55, 0.95]   | 20            | -                     | -          |
