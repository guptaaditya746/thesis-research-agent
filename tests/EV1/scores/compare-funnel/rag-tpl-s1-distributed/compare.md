# Comparison over corpora

| level       | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| distributed | rag-tpl-s1-79207ad1 | evidence-engine | -          | 0.853           | 1.000           | 1.000                  | -           | 0.800                | 0.800          | 1.000               | -              | yes             | -                    | -                     | -                  | -               |
| distributed | rag-tpl-s1-79207ad1 | evidence-engine | gaps       | 0.884           | 1.000           | 1.000                  | -           | 1.000                | 1.000          | 1.000               | -              | yes             | 7.600                | 4367.450              | 1.000              | 1.000           |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level       | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|-------------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| distributed | rag-tpl-s1-79207ad1 | evidence-engine | -          | 0.853 [0.80, 0.89] | 0.800 [0.60, 0.95]   | -                     |
| distributed | rag-tpl-s1-79207ad1 | evidence-engine | gaps       | 0.884 [0.84, 0.93] | 1.000 [n/a]          | -                     |
