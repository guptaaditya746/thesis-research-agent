# Comparison over corpora

| level         | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | all        | 0.895           | 1.000           | 1.000                  | 0.750       | 1.000                | 1.000          | 1.000               | -              | yes             | 10.000               | 8046.800              | 1.000              | 0.950           |
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | gaps       | 0.793           | 1.000           | 1.000                  | 0.800       | 0.800                | 0.900          | 0.889               | -              | yes             | 6.950                | 3253.400              | 1.000              | 0.950           |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level         | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|---------------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | all        | 0.895 [0.84, 0.93] | 1.000 [n/a]          | -                     |
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | gaps       | 0.793 [0.71, 0.85] | 0.800 [0.55, 0.95]   | -                     |
