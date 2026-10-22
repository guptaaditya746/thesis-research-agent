# Evaluation of run (baselines only) on rag-claude-s1-869ad7e8

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## C. Synthesis

| system              | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| rag-baseline        | mixed   | mixed      | yes             | 20        | 20           | 0.300                | 0.300          | 1.000               | 1.000          | 1.000     |
| rag-oracle-passages | mixed   | mixed      | yes             | 20        | 20           | 0.950                | 1.000          | 0.950               | 1.000          | 1.000     |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system              | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-------------|---------------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| distributed | rag-baseline        | 20        | 20           | 0.300                | 0.300          | 1.000               | 1.000          | 1.000     |
| distributed | rag-oracle-passages | 20        | 20           | 0.950                | 1.000          | 0.950               | 1.000          | 1.000     |

## Attribution

Wrong studies against the oracle `rag-oracle-passages`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system       | level       | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|--------------|-------------|-----------|------------------|------------------|------------|--------------|
| rag-baseline | distributed | 20        | 6                | 19               | 13         | 1            |
| rag-baseline | all         | 20        | 6                | 19               | 13         | 1            |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system              | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|---------------------|----------------------|----------|-----------------------|-----------------|------------|
| rag-baseline        | 0.300 [0.15, 0.55]   | BCa      | -                     | -               | -          |
| rag-oracle-passages | 0.950 [0.75, 1.00]   | BCa      | -                     | -               | -          |
