# Comparison over corpora

| level   | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| mixed   | rag-llm-k1-961f46a3 | agent-baseline  | -          | -               | -               | -                      | -           | 0.818                | 1.000          | 0.778               | -              | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-llm-k1-961f46a3 | agent-baseline  | -          | -               | -               | -                      | -           | 0.818                | 1.000          | 0.778               | -              | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-llm-k1-961f46a3 | evidence-engine | all        | 0.837           | 0.990           | 0.837                  | 0.778       | 0.909                | 1.000          | 0.889               | -              | yes             | 9.909                | 9443.636              | 1.000              | 1.000           |
| mixed   | rag-llm-k1-961f46a3 | evidence-engine | gaps       | 0.783           | 0.958           | 0.806                  | 0.889       | 0.818                | 1.000          | 0.778               | -              | yes             | 6.182                | 4199.364              | 1.000              | 1.000           |
| mixed   | rag-llm-k1-961f46a3 | rag-baseline    | -          | -               | -               | -                      | -           | 0.545                | 0.556          | 0.800               | 1.000          | yes             | -                    | -                     | -                  | -               |
| mixed   | rag-llm-k1-961f46a3 | rag-baseline    | -          | -               | -               | -                      | -           | 0.545                | 0.556          | 0.800               | 1.000          | yes             | -                    | -                     | -                  | -               |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level   | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|---------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| mixed   | rag-llm-k1-961f46a3 | agent-baseline  | -          | -                  | 0.818 [0.45, 1.00]   | 0.091 [-0.18, 0.36]   |
| mixed   | rag-llm-k1-961f46a3 | agent-baseline  | -          | -                  | 0.818 [0.45, 1.00]   | 0.000 [-0.36, 0.36]   |
| mixed   | rag-llm-k1-961f46a3 | evidence-engine | all        | 0.837 [0.80, 0.88] | 0.909 [0.56, 1.00]   | -                     |
| mixed   | rag-llm-k1-961f46a3 | evidence-engine | gaps       | 0.783 [0.71, 0.87] | 0.818 [0.45, 1.00]   | -                     |
| mixed   | rag-llm-k1-961f46a3 | rag-baseline    | -          | -                  | 0.545 [0.27, 0.82]   | 0.364 [0.09, 0.64]    |
| mixed   | rag-llm-k1-961f46a3 | rag-baseline    | -          | -                  | 0.545 [0.27, 0.82]   | 0.273 [0.09, 0.64]    |
