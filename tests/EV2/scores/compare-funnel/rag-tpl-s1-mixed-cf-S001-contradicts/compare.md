# Comparison over corpora

| level   | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1   | span_accuracy   | association_accuracy   | true_pair   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   | label_correct   | calls_per_document   | tokens_per_document   | screen_precision   | screen_recall   |
|---------|------------------------|-----------------|------------|----------------|--------------|-----------------|-----------------|------------------------|-------------|----------------------|----------------|---------------------|----------------|-----------|-----------------|----------------------|-----------------------|--------------------|-----------------|
| mixed   | rag-tpl-s1-cf-cb85326b | evidence-engine | all        | reject         | 6b360bca67ce | 0.931           | 1.000           | 0.980                  | 0.750       | 1.000                | 1.000          | 1.000               | -              | -         | yes             | 10.000               | 8380.450              | 1.000              | 1.000           |
| mixed   | rag-tpl-s1-cf-cb85326b | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.769           | 1.000           | 0.962                  | 0.600       | 0.800                | 0.800          | 1.000               | -              | -         | yes             | 7.250                | 3736.300              | 1.000              | 1.000           |

## Selection

Studies requested and retained after the fidelity gate (corpus.json `selection`; a corpus built before it is not listed); per level the papers passed, the checks that failed the final attempt of the failed ones and the mean attempts.

| corpus_id              | level         | requested   | retained   | records   | passed   | failed_checks   | mean_attempts   |
|------------------------|---------------|-------------|------------|-----------|----------|-----------------|-----------------|
| rag-tpl-s1-cf-cb85326b | explicit      | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-cf-cb85326b | paraphrased   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-cf-cb85326b | distributed   | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-cf-cb85326b | complex       | 20          | 20         | 20        | 20       | none            | 1.000           |
| rag-tpl-s1-cf-cb85326b | contradictory | 20          | 20         | 20        | 20       | none            | 1.000           |

- rag-tpl-s1-cf-cb85326b: excluded none

## Intervals

95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. `extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies were resampled), `paired_n` the studies both systems scored.

| level   | corpus_id              | system          | strategy   | lexical_miss   | protocol     | extraction_f1      | extraction_n   | direction_accuracy   | direction_n   | engine_minus_system   | paired_n   |
|---------|------------------------|-----------------|------------|----------------|--------------|--------------------|----------------|----------------------|---------------|-----------------------|------------|
| mixed   | rag-tpl-s1-cf-cb85326b | evidence-engine | all        | reject         | 6b360bca67ce | 0.931 [0.90, 0.96] | 20             | 1.000 [n/a]          | 20            | -                     | -          |
| mixed   | rag-tpl-s1-cf-cb85326b | evidence-engine | gaps       | reject         | 6b360bca67ce | 0.769 [0.69, 0.85] | 20             | 0.800 [0.60, 0.95]   | 20            | -                     | -          |
