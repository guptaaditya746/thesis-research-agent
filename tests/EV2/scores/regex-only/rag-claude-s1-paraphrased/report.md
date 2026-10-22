# Evaluation of run rag-claude-s1-paraphrased on rag-claude-s1-c34803f0

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: paraphrased

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | paraphrased | 23      | 162     | 22        | 0.957       | 0.136    | 0.238 | 0.909           |
| all             | all         | 23      | 162     | 22        | 0.957       | 0.136    | 0.238 | 0.909           |
| author_claim    | paraphrased | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               |
| condition       | all         | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | paraphrased | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | all         | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               |
| metric          | paraphrased | 3       | 20      | 2         | 0.667       | 0.100    | 0.174 | 0.000           |
| metric          | all         | 3       | 20      | 2         | 0.667       | 0.100    | 0.174 | 0.000           |

Facts no item matched: 140; items matching no fact: 1.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| paraphrased | 0                      | -                      | -                         | -                 | -                 | -              | 20        | 0.000       |
| all         | 0                      | -                      | -                         | -                 | -                 | -              | 20        | 0.000       |

## C. Synthesis

| system          | label        | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|--------------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | insufficient | mixed      | no              | 20        | 20           | 0.000                | 0.000          | -                   | -              | -         |
| rag-baseline    | mixed        | mixed      | yes             | 20        | 20           | 0.200                | 0.400          | 0.500               | 1.000          | 1.000     |
| agent-baseline  | mixed        | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| paraphrased | agent-baseline  | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| paraphrased | evidence-engine | 20        | 20           | 0.000                | 0.000          | -                   | -              | -         |
| paraphrased | rag-baseline    | 20        | 20           | 0.200                | 0.400          | 0.500               | 1.000          | 1.000     |

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

| system          | level       | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|-------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | paraphrased | 20        | 0                | 20               | 20         | 0            |
| evidence-engine | all         | 20        | 0                | 20               | 20         | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.000 [n/a]        | -        |
| metric          | 0.174 [0.00, 0.46] | BCa      |
| measurement     | 0.000 [n/a]        | -        |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.238 [0.21, 0.28] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.000 [n/a]          | -        | -                     | -               | -          |
| rag-baseline    | 0.200 [0.05, 0.45]   | BCa      | -0.200 [-0.45, -0.05] | BCa             | 20         |
| agent-baseline  | 1.000 [n/a]          | -        | -1.000 [n/a]          | -               | 20         |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | paraphrased | 368          | 368      | 1.000    |
| all             | all         | 368          | 368      | 1.000    |
| author_claim    | paraphrased | 40           | 40       | 1.000    |
| author_claim    | all         | 40           | 40       | 1.000    |
| condition       | paraphrased | 163          | 163      | 1.000    |
| condition       | all         | 163          | 163      | 1.000    |
| measurement     | paraphrased | 61           | 61       | 1.000    |
| measurement     | all         | 61           | 61       | 1.000    |
| metric          | paraphrased | 104          | 104      | 1.000    |
| metric          | all         | 104          | 104      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 20     | 20             |
| regex_condition@2#0a5bf730763c    | 0       | 0               | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | 0       | 0               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 3       | 2               | 3      | 2              |

Facts no extractor found: condition 61, measurement 61, metric 18

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 3       | 20      | 2         | 0.667       | 0.100    | 0.174 | 0.000           | -                      | 3      | 2              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 3       | 20      | 2         | 0.667       | 0.100    | 0.174 | 0.000           | -                      | 3      | 2              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.262     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.242     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.232     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.237     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.237     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 20      | 1.000       |
| calls            | 100     | 5.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 2.020   | 0.101       |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 5.000          |
| model_calls   | 0.000          |
| input_tokens  | 0.000          |
| output_tokens | 0.000          |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
