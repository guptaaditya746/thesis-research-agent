# Comparison over corpora

| level       | corpus_id              | system          | strategy   | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|------------------------|-----------------|------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| paraphrased | rag-llm-small-efea11e7 | agent-baseline  | -          | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-llm-small-efea11e7 | agent-baseline  | -          | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | -              | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-llm-small-efea11e7 | evidence-engine | all        | 0.818           | 1.000           | 0.750                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | yes             | 14.000               | 434223.000            | 1.000              | 1.000           |
| paraphrased | rag-llm-small-efea11e7 | evidence-engine | gaps       | 0.952           | 0.900           | 1.000                  | 1.000       | 1.000                | 1.000          | 1.000               | -              | yes             | 8.000                | 6363.000              | 1.000              | 1.000           |
| paraphrased | rag-llm-small-efea11e7 | rag-baseline    | -          | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | 1.000          | yes             | -                    | -                     | -                  | -               |
| paraphrased | rag-llm-small-efea11e7 | rag-baseline    | -          | -               | -               | -                      | -           | 1.000                | 1.000          | 1.000               | 1.000          | yes             | -                    | -                     | -                  | -               |

## Intervals

95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.

| level       | corpus_id              | system          | strategy   | extraction_f1   | direction_accuracy   | engine_minus_system   |
|-------------|------------------------|-----------------|------------|-----------------|----------------------|-----------------------|
| paraphrased | rag-llm-small-efea11e7 | agent-baseline  | -          | -               | 1.000 [n/a]          | 0.000 [n/a]           |
| paraphrased | rag-llm-small-efea11e7 | agent-baseline  | -          | -               | 1.000 [n/a]          | 0.000 [n/a]           |
| paraphrased | rag-llm-small-efea11e7 | evidence-engine | all        | 0.818 [n/a]     | 1.000 [n/a]          | -                     |
| paraphrased | rag-llm-small-efea11e7 | evidence-engine | gaps       | 0.952 [n/a]     | 1.000 [n/a]          | -                     |
| paraphrased | rag-llm-small-efea11e7 | rag-baseline    | -          | -               | 1.000 [n/a]          | 0.000 [n/a]           |
| paraphrased | rag-llm-small-efea11e7 | rag-baseline    | -          | -               | 1.000 [n/a]          | 0.000 [n/a]           |
