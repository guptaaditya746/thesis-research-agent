# Comparison over corpora

| level       | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|---------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| distributed | rag-claude-pilot-7807c6b5 | evidence-engine | all        | reject         | 6b360bca67ce | 0.885           | 1.000           | 0.909                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 8708.000              | 1.000              | 1.000           |
| distributed | rag-claude-pilot-7807c6b5 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.775           | 1.000           | 0.857                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 8.333                | 6171.000              | 1.000              | 1.000           |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id                 | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|---------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-pilot-7807c6b5 | explicit      | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-7807c6b5 | paraphrased   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-7807c6b5 | distributed   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-7807c6b5 | complex       | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-7807c6b5 | contradictory | 3           | 3          | 3         | 3        | none            | 1.333           |

- rag-claude-pilot-7807c6b5: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level       | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|-------------|---------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| distributed | rag-claude-pilot-7807c6b5 | evidence-engine | all        | reject         | 6b360bca67ce | 0.885 [0.82, 0.91] | 3              | 1.000 [n/a]          | 3             | -                     | -          |
| distributed | rag-claude-pilot-7807c6b5 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.775 [0.75, 0.82] | 3              | 1.000 [n/a]          | 3             | -                     | -          |
