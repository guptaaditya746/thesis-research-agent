# Evaluation of run (baselines only) on rag-tpl-hard-24ab4663

Question: Does retrieval-augmented generation reduce the hallucination rate of LLM-generated answers?
Levels: complex

## C. Synthesis

| system       | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|--------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| rag-baseline | mixed   | mixed      | yes             | 112       | 59           | 0.119                | 0.119          | 1.000               | 0.500                           | 0.818          | 0.818     |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level   | system       | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|---------|--------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| complex | rag-baseline | 112       | 59           | 0.119                | 0.119          | 1.000               | 0.500                           | 0.818          | 0.818     |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system       | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|--------------|----------------------|----------|-----------------------|-----------------|------------|
| rag-baseline | 0.119 [0.05, 0.22]   | BCa      | -                     | -               | -          |
