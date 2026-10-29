# Evaluation of run (baselines only) on rag-claude-s1-ec928480

Question: Does retrieval-augmented generation reduce the hallucination rate of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## C. Synthesis

| system       | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|--------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| rag-baseline | supported | mixed      | no              | 20        | 9            | 0.444                | 0.556          | 0.800               | 0.750                           | 1.000          | 1.000     |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system       | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|---------------|--------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| explicit      | rag-baseline | 4         | 3            | 1.000                | 1.000          | 1.000               | 1.000                           | 1.000          | 1.000     |
| paraphrased   | rag-baseline | 4         | 3            | 0.000                | 0.000          | -                   | 0.250                           | -              | -         |
| distributed   | rag-baseline | 4         | 2            | 0.500                | 0.500          | 1.000               | 0.750                           | 1.000          | 1.000     |
| complex       | rag-baseline | 4         | 0            | -                    | -              | -                   | 1.000                           | -              | -         |
| contradictory | rag-baseline | 4         | 1            | 0.000                | 1.000          | 0.000               | 0.750                           | 1.000          | 1.000     |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system       | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|--------------|----------------------|----------|-----------------------|-----------------|------------|
| rag-baseline | 0.444 [0.11, 0.78]   | BCa      | -                     | -               | -          |
