# Comparison over corpora

| level         | corpus_id           | system          | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | answered   | accuracy_answered   | label_correct   |
|---------------|---------------------|-----------------|-----------------|-----------------|------------------------|-------------|----------------------|------------|---------------------|-----------------|
| explicit      | rag-tpl-s1-59c5118b | evidence-engine | 0.950           | 1.000           | 0.984                  | 0.700       | 0.950                | 0.950      | 1.000               | yes             |
| paraphrased   | rag-tpl-s1-4d15ddc4 | evidence-engine | 0.994           | 1.000           | 1.000                  | 1.000       | 1.000                | 1.000      | 1.000               | yes             |
| distributed   | rag-tpl-s1-79207ad1 | evidence-engine | 0.853           | 1.000           | 1.000                  | 0.800       | 0.800                | 0.800      | 1.000               | yes             |
| complex       | rag-tpl-s1-f0f5d48e | evidence-engine | 0.932           | 1.000           | 1.000                  | 0.150       | 0.750                | 0.900      | 0.833               | yes             |
| contradictory | rag-tpl-s1-56b0bc02 | evidence-engine | 0.905           | 1.000           | 1.000                  | 0.600       | 0.900                | 1.000      | 0.900               | yes             |
| mixed         | rag-tpl-s1-6162b495 | evidence-engine | 0.941           | 1.000           | 1.000                  | 0.700       | 0.900                | 0.950      | 0.947               | yes             |
