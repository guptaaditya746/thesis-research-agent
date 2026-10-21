# Comparison over corpora

| level    | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|----------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| explicit | rag-llm-s1-5848c762 | agent-baseline  | -          | -               | -               | -                      | -           | 0.909                | 1.000          | 0.909               | -              | yes             | -                    | -                     | -                  | -               |
| explicit | rag-llm-s1-5848c762 | agent-baseline  | -          | -               | -               | -                      | -           | 0.909                | 1.000          | 0.909               | -              | yes             | -                    | -                     | -                  | -               |
| explicit | rag-llm-s1-5848c762 | evidence-engine | all        | 0.824           | 1.000           | 0.879                  | 0.636       | 1.000                | 1.000          | 1.000               | -              | yes             | 10.000               | 9742.091              | 1.000              | 1.000           |
| explicit | rag-llm-s1-5848c762 | evidence-engine | gaps       | 0.783           | 0.923           | 0.909                  | 1.000       | 0.909                | 1.000          | 0.909               | -              | yes             | 6.909                | 3676.454              | 1.000              | 1.000           |
| explicit | rag-llm-s1-5848c762 | rag-baseline    | -          | -               | -               | -                      | -           | 0.273                | 0.273          | 1.000               | 1.000          | no              | -                    | -                     | -                  | -               |
| explicit | rag-llm-s1-5848c762 | rag-baseline    | -          | -               | -               | -                      | -           | 0.273                | 0.273          | 1.000               | 1.000          | no              | -                    | -                     | -                  | -               |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level    | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|----------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| explicit | rag-llm-s1-5848c762 | agent-baseline  | -          | -                  | 0.909 [0.63, 1.00]   | 0.091 [0.00, 0.37]    |
| explicit | rag-llm-s1-5848c762 | agent-baseline  | -          | -                  | 0.909 [0.63, 1.00]   | 0.000 [-0.27, 0.27]   |
| explicit | rag-llm-s1-5848c762 | evidence-engine | all        | 0.824 [0.77, 0.88] | 1.000 [n/a]          | -                     |
| explicit | rag-llm-s1-5848c762 | evidence-engine | gaps       | 0.783 [0.72, 0.86] | 0.909 [0.61, 1.00]   | -                     |
| explicit | rag-llm-s1-5848c762 | rag-baseline    | -          | -                  | 0.273 [0.09, 0.64]   | 0.727 [0.36, 0.91]    |
| explicit | rag-llm-s1-5848c762 | rag-baseline    | -          | -                  | 0.273 [0.09, 0.64]   | 0.636 [0.27, 0.91]    |
