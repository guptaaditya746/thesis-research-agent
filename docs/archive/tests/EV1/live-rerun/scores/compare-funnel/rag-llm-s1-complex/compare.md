# Comparison over corpora

| level   | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| complex | rag-llm-s1-a2b5bbc1 | agent-baseline  | -          | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | yes             | -                    | -                     | -                  | -               |
| complex | rag-llm-s1-a2b5bbc1 | agent-baseline  | -          | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | yes             | -                    | -                     | -                  | -               |
| complex | rag-llm-s1-a2b5bbc1 | evidence-engine | all        | 0.893           | 1.000           | 0.900                  | 0.091       | 0.909                | 1.000          | 0.909               | -              | yes             | 10.000               | 13260.182             | 1.000              | 1.000           |
| complex | rag-llm-s1-a2b5bbc1 | evidence-engine | gaps       | 0.791           | 0.970           | 0.962                  | 0.455       | 0.909                | 1.000          | 0.909               | -              | yes             | 7.091                | 5586.182              | 1.000              | 1.000           |
| complex | rag-llm-s1-a2b5bbc1 | rag-baseline    | -          | -               | -               | -                      | -           | 0.182                | 0.545          | 0.333               | 1.000          | no              | -                    | -                     | -                  | -               |
| complex | rag-llm-s1-a2b5bbc1 | rag-baseline    | -          | -               | -               | -                      | -           | 0.182                | 0.545          | 0.333               | 1.000          | no              | -                    | -                     | -                  | -               |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level   | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|---------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| complex | rag-llm-s1-a2b5bbc1 | agent-baseline  | -          | -                  | 1.000 [n/a]          | -0.091 [-0.45, 0.00]  |
| complex | rag-llm-s1-a2b5bbc1 | agent-baseline  | -          | -                  | 1.000 [n/a]          | -0.091 [-0.39, 0.00]  |
| complex | rag-llm-s1-a2b5bbc1 | evidence-engine | all        | 0.893 [0.85, 0.93] | 0.909 [0.55, 1.00]   | -                     |
| complex | rag-llm-s1-a2b5bbc1 | evidence-engine | gaps       | 0.791 [0.70, 0.89] | 0.909 [0.61, 1.00]   | -                     |
| complex | rag-llm-s1-a2b5bbc1 | rag-baseline    | -          | -                  | 0.182 [0.00, 0.55]   | 0.727 [0.36, 0.91]    |
| complex | rag-llm-s1-a2b5bbc1 | rag-baseline    | -          | -                  | 0.182 [0.00, 0.55]   | 0.727 [0.45, 0.91]    |
