# Comparison over corpora

| level   | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| mixed   | rag-tpl-s1-6162b495 | evidence-engine | all        | 0.931           | 1.000           | 0.980                  | 0.750       | 1.000                | 1.000          | 1.000               | -              | yes             | 10.000               | 8382.650              | 1.000              | 1.000           |
| mixed   | rag-tpl-s1-6162b495 | evidence-engine | gaps       | 0.754           | 1.000           | 0.960                  | 0.600       | 0.800                | 0.800          | 1.000               | -              | yes             | 7.250                | 3674.150              | 1.000              | 1.000           |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level   | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|---------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| mixed   | rag-tpl-s1-6162b495 | evidence-engine | all        | 0.931 [0.90, 0.96] | 1.000 [n/a]          | -                     |
| mixed   | rag-tpl-s1-6162b495 | evidence-engine | gaps       | 0.754 [0.68, 0.83] | 0.800 [0.60, 0.95]   | -                     |
