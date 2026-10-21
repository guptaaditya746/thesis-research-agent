# Comparison over corpora

| level   | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| complex | rag-tpl-s1-f0f5d48e | evidence-engine | all        | 0.937           | 1.000           | 1.000                  | 0.000       | 1.000                | 1.000          | 1.000               | -              | yes             | 10.000               | 11803.650             | 1.000              | 1.000           |
| complex | rag-tpl-s1-f0f5d48e | evidence-engine | gaps       | 0.769           | 1.000           | 0.813                  | 0.000       | 1.000                | 1.000          | 1.000               | -              | yes             | 7.350                | 5197.650              | 1.000              | 1.000           |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level   | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|---------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| complex | rag-tpl-s1-f0f5d48e | evidence-engine | all        | 0.937 [0.91, 0.96] | 1.000 [n/a]          | -                     |
| complex | rag-tpl-s1-f0f5d48e | evidence-engine | gaps       | 0.769 [0.70, 0.82] | 1.000 [n/a]          | -                     |
