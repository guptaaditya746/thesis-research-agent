# Comparison over corpora

| level   | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| mixed   | rag-llm-s1-4f53cda1 | agent-baseline  | -          | -               | -               | -                      | -           | -                    | -              | -                   | -              | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-llm-s1-4f53cda1 | agent-baseline  | -          | -               | -               | -                      | -           | -                    | -              | -                   | -              | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-llm-s1-4f53cda1 | evidence-engine | all        | -               | -               | -                      | -           | -                    | -              | -                   | -              | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-llm-s1-4f53cda1 | evidence-engine | gaps       | -               | -               | -                      | -           | -                    | -              | -                   | -              | yes             | -                    | -                     | -                  | -               |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level   | corpus_id           | system          | strategy   | extraction_f1   | direction_accuracy   | engine_minus_system   |
|---------|---------------------|-----------------|------------|-----------------|----------------------|-----------------------|
| mixed   | rag-llm-s1-4f53cda1 | agent-baseline  | -          | -               | -                    | -                     |
| mixed   | rag-llm-s1-4f53cda1 | agent-baseline  | -          | -               | -                    | -                     |
| mixed   | rag-llm-s1-4f53cda1 | evidence-engine | all        | -               | -                    | -                     |
| mixed   | rag-llm-s1-4f53cda1 | evidence-engine | gaps       | -               | -                    | -                     |
