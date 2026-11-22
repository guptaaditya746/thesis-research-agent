# Comparison over corpora

| level       | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| paraphrased | rag-tpl-s1-4d15ddc4 | evidence-engine | all        | 0.972           | 1.000           | 0.965                  | 0.950       | 0.950                | 0.950          | 1.000               | -              | yes             | 10.000               | 8143.050              | 1.000              | 1.000           |
| paraphrased | rag-tpl-s1-4d15ddc4 | evidence-engine | gaps       | 0.500           | 1.000           | 1.000                  | 0.150       | 0.150                | 0.150          | 1.000               | -              | no              | 7.300                | 3378.450              | 1.000              | 1.000           |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level       | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|-------------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| paraphrased | rag-tpl-s1-4d15ddc4 | evidence-engine | all        | 0.972 [0.91, 1.00] | 0.950 [0.75, 1.00]   | -                     |
| paraphrased | rag-tpl-s1-4d15ddc4 | evidence-engine | gaps       | 0.500 [0.41, 0.66] | 0.150 [0.05, 0.35]   | -                     |
