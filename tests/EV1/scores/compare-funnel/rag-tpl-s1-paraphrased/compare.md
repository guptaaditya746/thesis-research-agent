# Comparison over corpora

| level       | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| paraphrased | rag-tpl-s1-4d15ddc4 | evidence-engine | -          | 0.994           | 1.000           | 1.000                  | -           | 1.000                | 1.000          | 1.000               | -              | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-tpl-s1-4d15ddc4 | evidence-engine | gaps       | 0.500           | 1.000           | 1.000                  | -           | 0.150                | 0.150          | 1.000               | -              | no              | 7.300                | 3380.650              | 1.000              | 1.000           |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level       | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|-------------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| paraphrased | rag-tpl-s1-4d15ddc4 | evidence-engine | -          | 0.994 [0.97, 1.00] | 1.000 [n/a]          | -                     |
| paraphrased | rag-tpl-s1-4d15ddc4 | evidence-engine | gaps       | 0.500 [0.41, 0.65] | 0.150 [0.05, 0.35]   | -                     |
