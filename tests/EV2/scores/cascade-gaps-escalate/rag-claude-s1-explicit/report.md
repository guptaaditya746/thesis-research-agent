# Evaluation of run rag-claude-s1-explicit-escalate on rag-claude-s1-eb14377d

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: explicit

## A. Extraction

| evidence_type   | level    | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|----------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit | 122     | 162     | 117       | 0.959       | 0.722    | 0.824 | 0.991           |
| all             | all      | 122     | 162     | 117       | 0.959       | 0.722    | 0.824 | 0.991           |
| author_claim    | explicit | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit | 39      | 61      | 39        | 1.000       | 0.639    | 0.780 | 0.974           |
| condition       | all      | 39      | 61      | 39        | 1.000       | 0.639    | 0.780 | 0.974           |
| measurement     | explicit | 39      | 61      | 38        | 0.974       | 0.623    | 0.760 | 1.000           |
| measurement     | all      | 39      | 61      | 38        | 0.974       | 0.623    | 0.760 | 1.000           |
| metric          | explicit | 24      | 20      | 20        | 0.833       | 1.000    | 0.909 | 1.000           |
| metric          | all      | 24      | 20      | 20        | 0.833       | 1.000    | 0.909 | 1.000           |

Facts no item matched: 45; items matching no fact: 5.

## B. Integration

| level    | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|----------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit | 38                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.950       |
| all      | 38                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.950       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.950                | 0.950          | 1.000               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 20        | 20           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level    | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|----------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit | agent-baseline  | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit | evidence-engine | 20        | 20           | 0.950                | 0.950          | 1.000               | -              | -         |
| explicit | rag-baseline    | 20        | 20           | 0.350                | 0.350          | 1.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level    | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|----------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit | 20        | 19               | 20               | 1          | 0            |
| evidence-engine | all      | 20        | 19               | 20               | 1          | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.780 [0.72, 0.85] | BCa      |
| metric          | 0.909 [0.82, 0.98] | BCa      |
| measurement     | 0.760 [0.68, 0.83] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.824 [0.78, 0.88] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.950 [0.73, 1.00]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.350 [0.15, 0.60]   | BCa      | 0.600 [0.35, 0.80]    | BCa             | 20         |
| agent-baseline  | 1.000 [n/a]          | -        | -0.050 [-0.27, 0.00]  | BCa             | 20         |

## Locate recall

| evidence_type   | level    | placements   | inside   | recall   |
|-----------------|----------|--------------|----------|----------|
| all             | explicit | 417          | 417      | 1.000    |
| all             | all      | 417          | 417      | 1.000    |
| author_claim    | explicit | 40           | 40       | 1.000    |
| author_claim    | all      | 40           | 40       | 1.000    |
| condition       | explicit | 172          | 172      | 1.000    |
| condition       | all      | 172          | 172      | 1.000    |
| measurement     | explicit | 61           | 61       | 1.000    |
| measurement     | all      | 61           | 61       | 1.000    |
| metric          | explicit | 144          | 144      | 1.000    |
| metric          | all      | 144          | 144      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 12      | 12              | 11     | 11             |
| llm_measurement@1#02bd5a7ab104    | 22      | 22              | 15     | 15             |
| llm_metric@1#41e1e53a1fc4         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 20     | 20             |
| regex_condition@2#0a5bf730763c    | 28      | 28              | 27     | 27             |
| regex_measurement@2#e2d17eb260ea  | 24      | 23              | 17     | 16             |
| regex_metric@2#0affe2d9ce77       | 22      | 18              | 22     | 18             |

Facts no extractor found: condition 22, measurement 23

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 162     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 12      | 30      | 12        | 1.000       | 0.400    | 0.571 | 1.000           | -                      | 11     | 11             |
| llm_condition@1#45b3761c700e      | all             | all     | 12      | 30      | 12        | 1.000       | 0.400    | 0.571 | 1.000           | -                      | 11     | 11             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 22      | 35      | 22        | 1.000       | 0.629    | 0.772 | 1.000           | 1.000                  | 15     | 15             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 22      | 35      | 22        | 1.000       | 0.629    | 0.772 | 1.000           | -                      | 15     | 15             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 0.964           | -                      | 27     | 27             |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 28        | 1.000       | 0.459    | 0.629 | 0.964           | -                      | 27     | 27             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 24      | 61      | 23        | 0.958       | 0.377    | 0.541 | 1.000           | 1.000                  | 17     | 16             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 24      | 61      | 23        | 0.958       | 0.377    | 0.541 | 1.000           | -                      | 17     | 16             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 22      | 20      | 18        | 0.818       | 0.900    | 0.857 | 1.000           | -                      | 22     | 18             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 22      | 20      | 18        | 0.818       | 0.900    | 0.857 | 1.000           | -                      | 22     | 18             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 10      | 13            | 14042          | 1084            | 28.139    |
| llm_measurement@1#02bd5a7ab104    | 11      | 22            | 27831          | 4573            | 92.071    |
| llm_metric@1#41e1e53a1fc4         | 2       | 2             | 2188           | 166             | 2.509     |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 16924          | 1551            | 41.549    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.259     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.254     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.273     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.254     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.422     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 30      | 1.500       |
| calls            | 143     | 7.150       |
| input_tokens     | 60985   | 3049.250    |
| made_model_calls | 44      | 2.200       |
| model_calls      | 57      | 2.850       |
| output_tokens    | 7374    | 368.700     |
| seconds          | 166.865 | 8.343       |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.150          |
| model_calls   | 2.850          |
| input_tokens  | 3049.250       |
| output_tokens | 368.700        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 8           |
| 1               | 11          |
| exhausted       | 1           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
