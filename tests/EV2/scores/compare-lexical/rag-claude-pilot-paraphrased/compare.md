# Comparison over corpora

| level       | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|---------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| paraphrased | rag-claude-pilot-d69436ff | evidence-engine | gaps       | escalate       | bfc107852891 | 0.600           | 1.000           | 1.000                  | 0.333       | 0.333                | 0.333          | 1.000               | -              | -         | no              | 7.667                | 3767.667              | 1.000              | 1.000           |
| paraphrased | rag-claude-pilot-d69436ff | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.600           | 1.000           | 1.000                  | 0.333       | 0.333                | 0.333          | 1.000               | -              | -         | no              | 7.667                | 3767.667              | 1.000              | 1.000           |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id                 | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|---------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-claude-pilot-d69436ff | explicit      | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d69436ff | paraphrased   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d69436ff | distributed   | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d69436ff | complex       | 3           | 3          | 3         | 3        | none            | 1.000           |
| rag-claude-pilot-d69436ff | contradictory | 3           | 3          | 3         | 3        | none            | 1.333           |

- rag-claude-pilot-d69436ff: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level       | corpus_id                 | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|-------------|---------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| paraphrased | rag-claude-pilot-d69436ff | evidence-engine | gaps       | escalate       | bfc107852891 | 0.600 [0.33, 1.00] | 3              | 0.333 [0.00, 1.00]   | 3             | -                     | -          |
| paraphrased | rag-claude-pilot-d69436ff | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.600 [0.33, 1.00] | 3              | 0.333 [0.00, 1.00]   | 3             | -                     | -          |
