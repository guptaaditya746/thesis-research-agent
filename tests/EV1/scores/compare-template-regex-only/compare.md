# Comparison over corpora

| level         | corpus_id           | system          | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | answered   | accuracy_answered   | label_correct   |
|---------------|---------------------|-----------------|-----------------|-----------------|------------------------|-------------|----------------------|------------|---------------------|-----------------|
| explicit      | rag-tpl-s1-59c5118b | evidence-engine | 0.656           | 1.000           | 1.000                  | 0.050       | 0.050                | 0.050      | 1.000               | no              |
| paraphrased   | rag-tpl-s1-4d15ddc4 | evidence-engine | 0.220           | 1.000           | -                      | 0.000       | 0.000                | 0.000      | -                   | no              |
| distributed   | rag-tpl-s1-79207ad1 | evidence-engine | 0.579           | 1.000           | -                      | 0.000       | 0.000                | 0.000      | -                   | no              |
| complex       | rag-tpl-s1-f0f5d48e | evidence-engine | 0.623           | 1.000           | 1.000                  | 0.000       | 0.250                | 0.250      | 1.000               | yes             |
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | 0.674           | 1.000           | 1.000                  | 0.250       | 0.250                | 0.350      | 0.714               | yes             |
| mixed         | rag-tpl-s1-6162b495 | evidence-engine | 0.614           | 1.000           | 1.000                  | 0.150       | 0.200                | 0.200      | 1.000               | yes             |
