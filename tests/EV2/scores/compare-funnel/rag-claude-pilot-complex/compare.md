# Comparison over corpora

| level   | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|---------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| complex | rag-claude-pilot-d04573ee | evidence-engine | all        | reject         | 6b360bca67ce | 0.962           | 1.000           | 0.891                  | 0.000       | 0.667                | 1.000          | 0.667               | -              | -         | yes             | 10.000               | 13424.667             | 1.000              | 1.000           |
| complex | rag-claude-pilot-d04573ee | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.692           | 1.000           | 0.536                  | 0.333       | 0.667                | 1.000          | 0.667               | -              | -         | yes             | 8.333                | 8618.667              | 1.000              | 1.000           |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id                 | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|---------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-pilot-d04573ee | explicit      | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d04573ee | paraphrased   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d04573ee | distributed   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d04573ee | complex       | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d04573ee | contradictory | 3           | 3          | 3         | 3        | none            | 1.333           |

- rag-claude-pilot-d04573ee: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level   | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------|---------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| complex | rag-claude-pilot-d04573ee | evidence-engine | all        | reject         | 6b360bca67ce | 0.962 [0.94, 0.97] | 3              | 0.667 [0.00, 1.00]   | 3             | -                     | -          |
| complex | rag-claude-pilot-d04573ee | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.692 [0.44, 0.87] | 3              | 0.667 [0.00, 1.00]   | 3             | -                     | -          |
