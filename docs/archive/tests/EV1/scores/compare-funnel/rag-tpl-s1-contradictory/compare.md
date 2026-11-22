# Comparison over corpora

| level         | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | -          | 0.905           | 1.000           | 1.000                  | -           | 0.900                | 1.000          | 0.900               | -              | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | gaps       | 0.781           | 1.000           | 0.971                  | -           | 0.750                | 0.850          | 0.882               | -              | yes             | 6.650                | 3102.050              | 1.000              | 0.900           |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level         | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|---------------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | -          | 0.905 [0.86, 0.94] | 0.900 [0.70, 1.00]   | -                     |
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | gaps       | 0.781 [0.69, 0.84] | 0.750 [0.50, 0.90]   | -                     |
