# Comparison over corpora

| level       | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| distributed | rag-tpl-s1-79207ad1 | evidence-engine | all        | 0.900           | 1.000           | 1.000                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | yes             | 10.000               | 7204.950              | 1.000              | 1.000           |
| distributed | rag-tpl-s1-79207ad1 | evidence-engine | gaps       | 0.884           | 1.000           | 1.000                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | yes             | 7.600                | 4364.950              | 1.000              | 1.000           |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level       | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|-------------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| distributed | rag-tpl-s1-79207ad1 | evidence-engine | all        | 0.900 [0.88, 0.92] | 1.000 [n/a]          | -                     |
| distributed | rag-tpl-s1-79207ad1 | evidence-engine | gaps       | 0.884 [0.84, 0.93] | 1.000 [n/a]          | -                     |
