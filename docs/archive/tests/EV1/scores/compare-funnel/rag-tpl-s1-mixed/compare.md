# Comparison over corpora

| level   | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| mixed   | rag-tpl-s1-6162b495 | evidence-engine | -          | 0.941           | 1.000           | 1.000                  | -           | 0.900                | 0.950          | 0.947               | -              | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-tpl-s1-6162b495 | evidence-engine | gaps       | 0.769           | 1.000           | 0.962                  | -           | 0.850                | 0.850          | 1.000               | -              | yes             | 7.350                | 3870.850              | 1.000              | 1.000           |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level   | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|---------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| mixed   | rag-tpl-s1-6162b495 | evidence-engine | -          | 0.941 [0.91, 0.97] | 0.900 [0.70, 1.00]   | -                     |
| mixed   | rag-tpl-s1-6162b495 | evidence-engine | gaps       | 0.769 [0.69, 0.84] | 0.850 [0.65, 0.95]   | -                     |
