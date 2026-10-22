# Comparison over corpora

| level   | corpus_id           | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|---------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| mixed   | rag-tpl-k1-9c3bbb32 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.784           | 1.000           | 0.965                  | 0.650       | 0.833                | 0.800          | 1.000               | -              | -         | yes             | 6.958                | 3855.875              | 1.000              | 1.000           |
| mixed   | rag-tpl-k1-9c3bbb32 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.784           | 1.000           | 0.965                  | 0.650       | 0.833                | 0.800          | 1.000               | -              | -         | yes             | 6.917                | 3829.375              | 1.000              | 1.000           |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id           | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|---------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-tpl-k1-9c3bbb32 | explicit      | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-tpl-k1-9c3bbb32 | paraphrased   | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-tpl-k1-9c3bbb32 | distributed   | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-tpl-k1-9c3bbb32 | complex       | 20          | 20         | 24        | 24       | none            | 1.000           |
| rag-tpl-k1-9c3bbb32 | contradictory | 20          | 20         | 24        | 24       | none            | 1.000           |

- rag-tpl-k1-9c3bbb32: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level   | corpus_id           | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------|---------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| mixed   | rag-tpl-k1-9c3bbb32 | evidence-engine | gaps       | escalate       | bfc107852891 | 0.784 [0.71, 0.86] | 24             | 0.833 [0.62, 0.96]   | 24            | -                     | -          |
| mixed   | rag-tpl-k1-9c3bbb32 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.784 [0.71, 0.86] | 24             | 0.833 [0.62, 0.96]   | 24            | -                     | -          |
