# Comparison over corpora

| level       | corpus_id           | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|---------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| paraphrased | rag-llm-s1-404c0b6d | agent-baseline  | -          | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-llm-s1-404c0b6d | agent-baseline  | -          | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-llm-s1-404c0b6d | evidence-engine | all        | 0.853           | 0.963           | 0.774                  | 0.818       | 0.818                | 0.818          | 1.000               | -              | yes             | 10.000               | 10584.909             | 1.000              | 1.000           |
| paraphrased | rag-llm-s1-404c0b6d | evidence-engine | gaps       | 0.879           | 0.900           | 0.900                  | 0.909       | 0.818                | 0.909          | 0.900               | -              | yes             | 8.182                | 7998.909              | 1.000              | 1.000           |
| paraphrased | rag-llm-s1-404c0b6d | rag-baseline    | -          | -               | -               | -                      | -           | 0.455                | 0.455          | 1.000               | 1.000          | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-llm-s1-404c0b6d | rag-baseline    | -          | -               | -               | -                      | -           | 0.455                | 0.455          | 1.000               | 1.000          | yes             | -                    | -                     | -                  | -               |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level       | corpus_id           | system          | strategy   | extraction_f1      | direction_accuracy   | engine_minus_system   |
|-------------|---------------------|-----------------|------------|--------------------|----------------------|-----------------------|
| paraphrased | rag-llm-s1-404c0b6d | agent-baseline  | -          | -                  | 1.000 [n/a]          | -0.182 [-0.50, 0.00]  |
| paraphrased | rag-llm-s1-404c0b6d | agent-baseline  | -          | -                  | 1.000 [n/a]          | -0.182 [-0.55, 0.00]  |
| paraphrased | rag-llm-s1-404c0b6d | evidence-engine | all        | 0.853 [0.81, 0.90] | 0.818 [0.50, 1.00]   | -                     |
| paraphrased | rag-llm-s1-404c0b6d | evidence-engine | gaps       | 0.879 [0.78, 0.93] | 0.818 [0.45, 1.00]   | -                     |
| paraphrased | rag-llm-s1-404c0b6d | rag-baseline    | -          | -                  | 0.455 [0.18, 0.73]   | 0.364 [0.09, 0.64]    |
| paraphrased | rag-llm-s1-404c0b6d | rag-baseline    | -          | -                  | 0.455 [0.18, 0.73]   | 0.364 [-0.09, 0.73]   |
