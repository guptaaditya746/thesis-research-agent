# Evaluation of run (baselines only) on rag-tpl-hard-b1c0fdfe

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## C. Synthesis

| system              | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| rag-baseline        | mixed   | mixed      | yes             | 112       | 100          | 0.116                | 0.050          | 0.400               | 1.000          | 1.000     |
| rag-oracle-passages | mixed   | mixed      | yes             | 112       | 100          | 0.250                | 0.160          | 1.000               | 1.000          | 1.000     |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system              | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|---------------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit      | rag-baseline        | 24        | 22           | 0.125                | 0.045          | 1.000               | 1.000          | 1.000     |
| explicit      | rag-oracle-passages | 24        | 22           | 0.292                | 0.227          | 1.000               | 1.000          | 1.000     |
| paraphrased   | rag-baseline        | 23        | 20           | 0.130                | 0.000          | -                   | -              | -         |
| paraphrased   | rag-oracle-passages | 23        | 20           | 0.261                | 0.150          | 1.000               | 1.000          | 1.000     |
| distributed   | rag-baseline        | 21        | 19           | 0.048                | 0.000          | -                   | 1.000          | 1.000     |
| distributed   | rag-oracle-passages | 21        | 19           | 0.238                | 0.158          | 1.000               | 1.000          | 1.000     |
| complex       | rag-baseline        | 22        | 20           | 0.136                | 0.050          | 1.000               | 1.000          | 1.000     |
| complex       | rag-oracle-passages | 22        | 20           | 0.273                | 0.200          | 1.000               | 1.000          | 1.000     |
| contradictory | rag-baseline        | 22        | 19           | 0.136                | 0.158          | 0.000               | 1.000          | 1.000     |
| contradictory | rag-oracle-passages | 22        | 19           | 0.182                | 0.053          | 1.000               | 1.000          | 1.000     |

## Attribution

Wrong studies against the oracle `rag-oracle-passages`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system       | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|--------------|---------------|-----------|------------------|------------------|------------|--------------|
| rag-baseline | explicit      | 24        | 3                | 7                | 5          | 16           |
| rag-baseline | paraphrased   | 23        | 3                | 6                | 3          | 17           |
| rag-baseline | distributed   | 21        | 1                | 5                | 4          | 16           |
| rag-baseline | complex       | 22        | 3                | 6                | 4          | 15           |
| rag-baseline | contradictory | 22        | 3                | 4                | 1          | 18           |
| rag-baseline | all           | 112       | 13               | 28               | 17         | 82           |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system              | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|---------------------|----------------------|----------|-----------------------|-----------------|------------|
| rag-baseline        | 0.116 [0.06, 0.18]   | BCa      | -                     | -               | -          |
| rag-oracle-passages | 0.250 [0.18, 0.34]   | BCa      | -                     | -               | -          |
