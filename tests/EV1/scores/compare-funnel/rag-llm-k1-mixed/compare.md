# Comparison over corpora

| level   | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| mixed   | rag-llm-k1-e8fce53a | agent-baseline  | -          | -               | -               | -                      | -           | 0.000                | -              | -                   | -              | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-llm-k1-e8fce53a | agent-baseline  | -          | -               | -               | -                      | -           | 0.000                | -              | -                   | -              | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-llm-k1-e8fce53a | evidence-engine | all        | 0.000           | -               | -                      | -           | 1.000                | -              | -                   | -              | yes             | 9.500                | 3471.000              | -                  | -               |
| mixed   | rag-llm-k1-e8fce53a | evidence-engine | gaps       | -               | -               | -                      | -           | 1.000                | -              | -                   | -              | yes             | 1.500                | 326.000               | -                  | -               |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level   | corpus_id           | system          | strategy   | extraction_f1   | direction_accuracy   | engine_minus_system   |
|---------|---------------------|-----------------|------------|-----------------|----------------------|-----------------------|
| mixed   | rag-llm-k1-e8fce53a | agent-baseline  | -          | -               | 0.000 [n/a]          | 1.000 [n/a]           |
| mixed   | rag-llm-k1-e8fce53a | agent-baseline  | -          | -               | 0.000 [n/a]          | 1.000 [n/a]           |
| mixed   | rag-llm-k1-e8fce53a | evidence-engine | all        | 0.000 [n/a]     | 1.000 [n/a]          | -                     |
| mixed   | rag-llm-k1-e8fce53a | evidence-engine | gaps       | 0.000 [n/a]     | 1.000 [n/a]          | -                     |
