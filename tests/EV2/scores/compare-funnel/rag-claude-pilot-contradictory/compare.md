# Comparison over corpora

| level         | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------------|---------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| contradictory | rag-claude-pilot-3ef3b916 | evidence-engine | all        | reject         | 6b360bca67ce | 0.846           | 1.000           | 0.857                  | 0.667       | 0.667                | 0.667          | 1.000               | -              | -         | no              | 10.000               | 9599.000              | 1.000              | 0.667           |
| contradictory | rag-claude-pilot-3ef3b916 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.619           | 1.000           | 0.800                  | 0.667       | 0.667                | 0.667          | 1.000               | -              | -         | no              | 6.333                | 5354.000              | 1.000              | 0.667           |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id                 | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|---------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-pilot-3ef3b916 | explicit      | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-3ef3b916 | paraphrased   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-3ef3b916 | distributed   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-3ef3b916 | complex       | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-3ef3b916 | contradictory | 3           | 3          | 3         | 3        | none            | 1.333           |

- rag-claude-pilot-3ef3b916: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level         | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------------|---------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| contradictory | rag-claude-pilot-3ef3b916 | evidence-engine | all        | reject         | 6b360bca67ce | 0.846 [0.67, 0.93] | 3              | 0.667 [0.00, 1.00]   | 3             | -                     | -          |
| contradictory | rag-claude-pilot-3ef3b916 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.619 [0.00, 0.83] | 3              | 0.667 [0.00, 1.00]   | 3             | -                     | -          |
