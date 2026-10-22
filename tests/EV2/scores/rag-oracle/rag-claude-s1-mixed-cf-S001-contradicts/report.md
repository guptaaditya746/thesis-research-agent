# Evaluation of run (baselines only) on rag-claude-s1-cf-5893772b

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## C. Synthesis

| system              | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| rag-baseline        | mixed   | mixed      | yes             | 20        | 20           | 0.200                | 0.250          | 0.800               | 1.000          | 1.000     |
| rag-oracle-passages | mixed   | mixed      | yes             | 20        | 20           | 0.700                | 0.800          | 0.875               | 0.708          | 0.708     |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system              | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|---------------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit      | rag-baseline        | 4         | 4            | 0.250                | 0.250          | 1.000               | 1.000          | 1.000     |
| explicit      | rag-oracle-passages | 4         | 4            | 1.000                | 1.000          | 1.000               | 0.429          | 0.429     |
| paraphrased   | rag-baseline        | 4         | 4            | 0.000                | 0.000          | -                   | -              | -         |
| paraphrased   | rag-oracle-passages | 4         | 4            | 0.500                | 0.500          | 1.000               | 0.333          | 0.333     |
| distributed   | rag-baseline        | 4         | 4            | 0.250                | 0.250          | 1.000               | 1.000          | 1.000     |
| distributed   | rag-oracle-passages | 4         | 4            | 0.750                | 0.750          | 1.000               | 1.000          | 1.000     |
| complex       | rag-baseline        | 4         | 4            | 0.500                | 0.500          | 1.000               | 1.000          | 1.000     |
| complex       | rag-oracle-passages | 4         | 4            | 0.750                | 0.750          | 1.000               | 0.750          | 0.750     |
| contradictory | rag-baseline        | 4         | 4            | 0.000                | 0.250          | 0.000               | 1.000          | 1.000     |
| contradictory | rag-oracle-passages | 4         | 4            | 0.500                | 1.000          | 0.500               | 1.000          | 1.000     |

## Attribution

Wrong studies against the oracle `rag-oracle-passages`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system       | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|--------------|---------------|-----------|------------------|------------------|------------|--------------|
| rag-baseline | explicit      | 4         | 1                | 4                | 3          | 0            |
| rag-baseline | paraphrased   | 4         | 0                | 2                | 2          | 2            |
| rag-baseline | distributed   | 4         | 1                | 3                | 2          | 1            |
| rag-baseline | complex       | 4         | 2                | 3                | 1          | 1            |
| rag-baseline | contradictory | 4         | 0                | 2                | 2          | 2            |
| rag-baseline | all           | 20        | 4                | 14               | 10         | 6            |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system              | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|---------------------|----------------------|----------|-----------------------|-----------------|------------|
| rag-baseline        | 0.200 [0.05, 0.45]   | BCa      | -                     | -               | -          |
| rag-oracle-passages | 0.700 [0.45, 0.90]   | BCa      | -                     | -               | -          |
