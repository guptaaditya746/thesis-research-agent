# Comparison over corpora

| level         | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| contradictory | rag-llm-s1-c1d18224 | agent-baseline  | -          | -               | -               | -                      | -           | 0.727                | 1.000          | 0.727               | -              | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-llm-s1-c1d18224 | agent-baseline  | -          | -               | -               | -                      | -           | 0.727                | 1.000          | 0.727               | -              | yes             | -                    | -                     | -                  | -               |
| contradictory | rag-llm-s1-c1d18224 | evidence-engine | all        | 0.783           | 1.000           | 0.909                  | 0.727       | 1.000                | 1.000          | 1.000               | -              | yes             | 10.000               | 10280.273             | 1.000              | 1.000           |
| contradictory | rag-llm-s1-c1d18224 | evidence-engine | gaps       | 0.775           | 0.955           | 1.000                  | 0.909       | 0.909                | 1.000          | 0.909               | -              | yes             | 7.182                | 4678.727              | 1.000              | 1.000           |
| contradictory | rag-llm-s1-c1d18224 | rag-baseline    | -          | -               | -               | -                      | -           | 0.182                | 0.545          | 0.333               | 1.000          | no              | -                    | -                     | -                  | -               |
| contradictory | rag-llm-s1-c1d18224 | rag-baseline    | -          | -               | -               | -                      | -           | 0.182                | 0.545          | 0.333               | 1.000          | no              | -                    | -                     | -                  | -               |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level         | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|---------------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| contradictory | rag-llm-s1-c1d18224 | agent-baseline  | -          | -                  | 0.727 [0.36, 0.91]   | 0.273 [0.09, 0.64]    |
| contradictory | rag-llm-s1-c1d18224 | agent-baseline  | -          | -                  | 0.727 [0.36, 0.91]   | 0.182 [-0.18, 0.55]   |
| contradictory | rag-llm-s1-c1d18224 | evidence-engine | all        | 0.783 [0.69, 0.86] | 1.000 [n/a]          | -                     |
| contradictory | rag-llm-s1-c1d18224 | evidence-engine | gaps       | 0.775 [0.73, 0.84] | 0.909 [0.59, 1.00]   | -                     |
| contradictory | rag-llm-s1-c1d18224 | rag-baseline    | -          | -                  | 0.182 [0.00, 0.45]   | 0.818 [0.55, 1.00]    |
| contradictory | rag-llm-s1-c1d18224 | rag-baseline    | -          | -                  | 0.182 [0.00, 0.45]   | 0.727 [0.18, 1.00]    |
