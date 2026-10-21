# Comparison over corpora

| level       | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| distributed | rag-llm-s1-d60fff2f | agent-baseline  | -          | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | yes             | -                    | -                     | -                  | -               |
| distributed | rag-llm-s1-d60fff2f | agent-baseline  | -          | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | yes             | -                    | -                     | -                  | -               |
| distributed | rag-llm-s1-d60fff2f | evidence-engine | all        | 0.813           | 1.000           | 0.909                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | yes             | 10.000               | 14930.273             | 1.000              | 1.000           |
| distributed | rag-llm-s1-d60fff2f | evidence-engine | gaps       | 0.844           | 0.945           | 0.923                  | 1.000       | 0.909                | 1.000          | 0.909               | -              | yes             | 7.455                | 7614.091              | 1.000              | 1.000           |
| distributed | rag-llm-s1-d60fff2f | rag-baseline    | -          | -               | -               | -                      | -           | 0.545                | 0.545          | 1.000               | 1.000          | yes             | -                    | -                     | -                  | -               |
| distributed | rag-llm-s1-d60fff2f | rag-baseline    | -          | -               | -               | -                      | -           | 0.545                | 0.545          | 1.000               | 1.000          | yes             | -                    | -                     | -                  | -               |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level       | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|-------------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| distributed | rag-llm-s1-d60fff2f | agent-baseline  | -          | -                  | 1.000 [n/a]          | 0.000 [n/a]           |
| distributed | rag-llm-s1-d60fff2f | agent-baseline  | -          | -                  | 1.000 [n/a]          | -0.091 [-0.39, 0.00]  |
| distributed | rag-llm-s1-d60fff2f | evidence-engine | all        | 0.813 [0.77, 0.85] | 1.000 [n/a]          | -                     |
| distributed | rag-llm-s1-d60fff2f | evidence-engine | gaps       | 0.844 [0.75, 0.90] | 0.909 [0.61, 1.00]   | -                     |
| distributed | rag-llm-s1-d60fff2f | rag-baseline    | -          | -                  | 0.545 [0.27, 0.82]   | 0.455 [0.18, 0.73]    |
| distributed | rag-llm-s1-d60fff2f | rag-baseline    | -          | -                  | 0.545 [0.27, 0.82]   | 0.364 [-0.09, 0.73]   |
