# Comparison over corpora

| level       | corpus_id           | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|-------------|---------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| paraphrased | rag-tpl-s1-4d15ddc4 | evidence-engine | all        | reject         | 6b360bca67ce | 0.972           | 1.000           | 0.965                  | 0.950       | 0.950                | 0.950          | 1.000               | -              | -         | yes             | 10.000               | 8138.550              | 1.000              | 1.000           |
| paraphrased | rag-tpl-s1-4d15ddc4 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.500           | 1.000           | 1.000                  | 0.150       | 0.150                | 0.150          | 1.000               | -              | -         | no              | 7.300                | 3378.750              | 1.000              | 1.000           |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id           | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|---------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-tpl-s1-4d15ddc4 | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-4d15ddc4 | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-4d15ddc4 | distributed   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-4d15ddc4 | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-4d15ddc4 | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |

- rag-tpl-s1-4d15ddc4: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level       | corpus_id           | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|-------------|---------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| paraphrased | rag-tpl-s1-4d15ddc4 | evidence-engine | all        | reject         | 6b360bca67ce | 0.972 [0.91, 1.00] | 20             | 0.950 [0.75, 1.00]   | 20            | -                     | -          |
| paraphrased | rag-tpl-s1-4d15ddc4 | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.500 [0.41, 0.66] | 20             | 0.150 [0.05, 0.35]   | 20            | -                     | -          |
