# Comparison over corpora

| level   | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| mixed   | rag-llm-s1-0278df5c | agent-baseline  | -          | -               | -               | -                      | -           | 0.818                | 1.000          | 0.818               | -              | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-llm-s1-0278df5c | agent-baseline  | -          | -               | -               | -                      | -           | 0.818                | 1.000          | 0.818               | -              | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-llm-s1-0278df5c | evidence-engine | all        | 0.854           | 0.992           | 0.934                  | 0.727       | 1.000                | 1.000          | 1.000               | -              | yes             | 10.000               | 10617.636             | 1.000              | 1.000           |
| mixed   | rag-llm-s1-0278df5c | evidence-engine | gaps       | 0.789           | 0.932           | 0.950                  | 0.727       | 0.818                | 0.909          | 0.900               | -              | yes             | 7.000                | 4267.636              | 1.000              | 1.000           |
| mixed   | rag-llm-s1-0278df5c | rag-baseline    | -          | -               | -               | -                      | -           | 0.545                | 0.545          | 1.000               | 1.000          | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-llm-s1-0278df5c | rag-baseline    | -          | -               | -               | -                      | -           | 0.545                | 0.545          | 1.000               | 1.000          | yes             | -                    | -                     | -                  | -               |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level   | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|---------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| mixed   | rag-llm-s1-0278df5c | agent-baseline  | -          | -                  | 0.818 [0.55, 1.00]   | 0.182 [0.00, 0.45]    |
| mixed   | rag-llm-s1-0278df5c | agent-baseline  | -          | -                  | 0.818 [0.55, 1.00]   | 0.000 [-0.36, 0.36]   |
| mixed   | rag-llm-s1-0278df5c | evidence-engine | all        | 0.854 [0.82, 0.89] | 1.000 [n/a]          | -                     |
| mixed   | rag-llm-s1-0278df5c | evidence-engine | gaps       | 0.789 [0.70, 0.88] | 0.818 [0.45, 1.00]   | -                     |
| mixed   | rag-llm-s1-0278df5c | rag-baseline    | -          | -                  | 0.545 [0.27, 0.82]   | 0.455 [0.18, 0.73]    |
| mixed   | rag-llm-s1-0278df5c | rag-baseline    | -          | -                  | 0.545 [0.27, 0.82]   | 0.273 [-0.09, 0.55]   |
