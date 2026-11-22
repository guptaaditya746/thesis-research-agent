# Comparison over corpora

| level    | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|----------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| explicit | rag-tpl-s1-59c5118b | evidence-engine | all        | 0.950           | 1.000           | 0.984                  | 0.750       | 1.000                | 1.000          | 1.000               | -              | yes             | 10.000               | 7515.850              | 1.000              | 1.000           |
| explicit | rag-tpl-s1-59c5118b | evidence-engine | gaps       | 0.837           | 1.000           | 1.000                  | 0.850       | 0.900                | 0.900          | 1.000               | -              | yes             | 7.450                | 4045.850              | 1.000              | 1.000           |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level    | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|----------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| explicit | rag-tpl-s1-59c5118b | evidence-engine | all        | 0.950 [0.91, 0.97] | 1.000 [n/a]          | -                     |
| explicit | rag-tpl-s1-59c5118b | evidence-engine | gaps       | 0.837 [0.78, 0.89] | 0.900 [0.70, 1.00]   | -                     |
