# Comparison over corpora

| level   | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| mixed   | rag-tpl-k1-9c3bbb32 | evidence-engine | all        | 0.926           | 1.000           | 0.962                  | 0.800       | 1.000                | 1.000          | 1.000               | -              | yes             | 9.958                | 7929.042              | 1.000              | 1.000           |
| mixed   | rag-tpl-k1-9c3bbb32 | evidence-engine | gaps       | 0.773           | 1.000           | 0.964                  | 0.700       | 0.875                | 0.850          | 1.000               | -              | yes             | 7.000                | 3851.833              | 1.000              | 1.000           |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level   | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|---------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| mixed   | rag-tpl-k1-9c3bbb32 | evidence-engine | all        | 0.926 [0.89, 0.96] | 1.000 [n/a]          | -                     |
| mixed   | rag-tpl-k1-9c3bbb32 | evidence-engine | gaps       | 0.773 [0.70, 0.85] | 0.875 [0.71, 0.96]   | -                     |
