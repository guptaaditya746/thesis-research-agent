# Evaluation of run rag-tpl-hard-complex on rag-tpl-hard-24ab4663

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 1758    | 2469    | 1670      | 0.950       | 0.676    | 0.790 | 1.000           |
| all             | all     | 1758    | 2469    | 1670      | 0.950       | 0.676    | 0.790 | 1.000           |
| author_claim    | complex | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 232     | 332     | 231       | 0.996       | 0.696    | 0.819 | 1.000           |
| condition       | all     | 232     | 332     | 231       | 0.996       | 0.696    | 0.819 | 1.000           |
| measurement     | complex | 1157    | 1768    | 1070      | 0.925       | 0.605    | 0.732 | 1.000           |
| measurement     | all     | 1157    | 1768    | 1070      | 0.925       | 0.605    | 0.732 | 1.000           |
| metric          | complex | 263     | 263     | 263       | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all     | 263     | 263     | 263       | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 799; items matching no fact: 88.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 1070                   | 0.815                  | 0.927                     | 0.879             | 0.927             | 0.879          | 100       | 0.030       |
| all     | 1070                   | 0.815                  | 0.927                     | 0.879             | 0.927             | 0.879          | 100       | 0.030       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 112       | 100          | 0.810                | 1.000          | 0.810               | 0.830                           | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 112       | 100          | 0.050                | 0.060          | 0.833               | 0.143                           | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 112       | 100          | 1.000                | 1.000          | 1.000               | 0.893                           | -              | -         |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| complex | agent-baseline  | 112       | 100          | 1.000                | 1.000          | 1.000               | 0.893                           | -              | -         |
| complex | evidence-engine | 112       | 100          | 0.810                | 1.000          | 0.810               | 0.830                           | -              | -         |
| complex | rag-baseline    | 112       | 100          | 0.050                | 0.060          | 0.833               | 0.143                           | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 19   | 0    | 0.000       | -        |
| evidence-engine | duplicate       | 5    | 0    | 1    | 1.000       | 0.833    |
| evidence-engine | large_effect    | 4    | 7    | 2    | 0.364       | 0.667    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | no                   |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.819 [0.79, 0.85] | BCa      |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 0.732 [0.70, 0.77] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.790 [0.77, 0.81] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.810 [0.72, 0.87]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.050 [0.02, 0.11]   | BCa      | 0.760 [0.66, 0.84]    | BCa             | 100        |
| agent-baseline  | 1.000 [n/a]          | -        | -0.190 [-0.28, -0.13] | BCa             | 100        |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 4323         | 4323     | 1.000    |
| all             | all     | 4323         | 4323     | 1.000    |
| author_claim    | complex | 212          | 212      | 1.000    |
| author_claim    | all     | 212          | 212      | 1.000    |
| condition       | complex | 1454         | 1454     | 1.000    |
| condition       | all     | 1454         | 1454     | 1.000    |
| measurement     | complex | 1768         | 1768     | 1.000    |
| measurement     | all     | 1768         | 1768     | 1.000    |
| metric          | complex | 889          | 889      | 1.000    |
| metric          | all     | 889          | 889      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 84      | 84              | 70     | 70             |
| llm_measurement@1#02bd5a7ab104    | 609     | 573             | 533    | 497            |
| llm_metric@1#41e1e53a1fc4         | 98      | 98              | 47     | 47             |
| regex_author_claim@2#fd7877790c48 | 106     | 106             | 106    | 106            |
| regex_condition@2#0a5bf730763c    | 162     | 161             | 148    | 147            |
| regex_measurement@2#e2d17eb260ea  | 624     | 573             | 548    | 497            |
| regex_metric@2#0affe2d9ce77       | 216     | 216             | 165    | 165            |

Facts no extractor found: condition 101, measurement 698

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 2469    | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 84      | 137     | 84        | 1.000       | 0.613    | 0.760 | 1.000           | -                      | 70     | 70             |
| llm_condition@1#45b3761c700e      | all             | all     | 84      | 137     | 84        | 1.000       | 0.613    | 0.760 | 1.000           | -                      | 70     | 70             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 609     | 1474    | 573       | 0.941       | 0.389    | 0.550 | 1.000           | 0.914                  | 533    | 497            |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 609     | 1474    | 573       | 0.941       | 0.389    | 0.550 | 1.000           | -                      | 533    | 497            |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 98      | 116     | 98        | 1.000       | 0.845    | 0.916 | 1.000           | -                      | 47     | 47             |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 98      | 116     | 98        | 1.000       | 0.845    | 0.916 | 1.000           | -                      | 47     | 47             |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_author_claim@2#fd7877790c48 | all             | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_condition@2#0a5bf730763c    | condition       | all     | 162     | 332     | 161       | 0.994       | 0.485    | 0.652 | 1.000           | -                      | 148    | 147            |
| regex_condition@2#0a5bf730763c    | all             | all     | 162     | 332     | 161       | 0.994       | 0.485    | 0.652 | 1.000           | -                      | 148    | 147            |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 624     | 1768    | 573       | 0.918       | 0.324    | 0.479 | 1.000           | 0.740                  | 548    | 497            |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 624     | 1768    | 573       | 0.918       | 0.324    | 0.479 | 1.000           | -                      | 548    | 497            |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 216     | 263     | 216       | 1.000       | 0.821    | 0.902 | 1.000           | -                      | 165    | 165            |
| regex_metric@2#0affe2d9ce77       | all             | all     | 216     | 263     | 216       | 1.000       | 0.821    | 0.902 | 1.000           | -                      | 165    | 165            |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 46      | 80            | 91217          | 8901            | 0.310     |
| llm_measurement@1#02bd5a7ab104    | 89      | 178           | 272976         | 100705          | 0.701     |
| llm_metric@1#41e1e53a1fc4         | 47      | 61            | 74192          | 9229            | 0.325     |
| llm_screen@1#41b0d6e6793f         | 109     | 109           | 102099         | 8132            | 0.723     |
| regex_author_claim@2#fd7877790c48 | 106     | 0             | 0              | 0               | 0.686     |
| regex_condition@2#0a5bf730763c    | 106     | 0             | 0              | 0               | 0.701     |
| regex_measurement@2#e2d17eb260ea  | 106     | 0             | 0              | 0               | 0.796     |
| regex_metric@2#0affe2d9ce77       | 106     | 0             | 0              | 0               | 0.717     |
| regex_screen@1#858a6ebc69c6       | 112     | 0             | 0              | 0               | 0.745     |

## Cost

| measure          | total    | per_paper   |
|------------------|----------|-------------|
| cached_calls     | 0        | 0.000       |
| calls            | 827      | 7.384       |
| input_tokens     | 540484   | 4825.750    |
| made_model_calls | 428      | 3.821       |
| model_calls      | 428      | 3.821       |
| output_tokens    | 126967   | 1133.634    |
| seconds          | 1203.959 | 10.750      |
| workers          | 3        | -           |

## Funnel

Strategy `gaps` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.384          |
| model_calls   | 3.821          |
| input_tokens  | 4825.750       |
| output_tokens | 1133.634       |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 17          |
| 1               | 83          |
| exhausted       | 6           |
| skipped         | 6           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 0    | 0    | 6    | 1.000       | 1.000    |

Screened out wrongly: none
