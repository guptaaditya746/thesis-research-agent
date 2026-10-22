# Evaluation of run rag-claude-pilot-distributed on rag-claude-pilot-7807c6b5

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 21      | 28      | 19        | 0.905       | 0.679    | 0.776 | 1.000           |
| all             | all         | 21      | 28      | 19        | 0.905       | 0.679    | 0.776 | 1.000           |
| author_claim    | distributed | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 8       | 11      | 6         | 0.750       | 0.545    | 0.632 | 1.000           |
| condition       | all         | 8       | 11      | 6         | 0.750       | 0.545    | 0.632 | 1.000           |
| measurement     | distributed | 7       | 11      | 7         | 1.000       | 0.636    | 0.778 | 1.000           |
| measurement     | all         | 7       | 11      | 7         | 1.000       | 0.636    | 0.778 | 1.000           |
| metric          | distributed | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all         | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 9; items matching no fact: 2.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 7                      | 0.857                  | 0.857                     | 1.000             | 0.714             | 1.000          | 3         | 1.000       |
| all         | 7                      | 0.857                  | 0.857                     | 1.000             | 0.714             | 1.000          | 3         | 1.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 3         | 3            | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| distributed | evidence-engine | 3         | 3            | 1.000                | 1.000          | 1.000               | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | yes              | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.632 [0.57, 0.67] | BCa      |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 0.778 [0.67, 1.00] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.776 [0.75, 0.82] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               | -          |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | distributed | 70           | 70       | 1.000    |
| all             | all         | 70           | 70       | 1.000    |
| author_claim    | distributed | 6            | 6        | 1.000    |
| author_claim    | all         | 6            | 6        | 1.000    |
| condition       | distributed | 33           | 33       | 1.000    |
| condition       | all         | 33           | 33       | 1.000    |
| measurement     | distributed | 11           | 11       | 1.000    |
| measurement     | all         | 11           | 11       | 1.000    |
| metric          | distributed | 20           | 20       | 1.000    |
| metric          | all         | 20           | 20       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 4       | 2               | 4      | 2              |
| llm_measurement@1#02bd5a7ab104    | 7       | 7               | 7      | 7              |
| llm_metric@1#41e1e53a1fc4         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | 3       | 3               | 3      | 3              |
| regex_condition@2#0a5bf730763c    | 4       | 4               | 4      | 4              |
| regex_measurement@2#e2d17eb260ea  | 0       | 0               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 1       | 1               | 1      | 1              |

Facts no extractor found: condition 5, measurement 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 28      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 4       | 7       | 2         | 0.500       | 0.286    | 0.364 | 1.000           | -                      | 4      | 2              |
| llm_condition@1#45b3761c700e      | all             | all     | 4       | 7       | 2         | 0.500       | 0.286    | 0.364 | 1.000           | -                      | 4      | 2              |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 7       | 11      | 7         | 1.000       | 0.636    | 0.778 | 1.000           | 0.857                  | 7      | 7              |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 7       | 11      | 7         | 1.000       | 0.636    | 0.778 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 3      | 3              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 3      | 3              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 4       | 11      | 4         | 1.000       | 0.364    | 0.533 | 1.000           | -                      | 4      | 4              |
| regex_condition@2#0a5bf730763c    | all             | all     | 4       | 11      | 4         | 1.000       | 0.364    | 0.533 | 1.000           | -                      | 4      | 4              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 0       | 11      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 0       | 11      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 1       | 3       | 1         | 1.000       | 0.333    | 0.500 | 1.000           | -                      | 1      | 1              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 1       | 3       | 1         | 1.000       | 0.333    | 0.500 | 1.000           | -                      | 1      | 1              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 2       | 2             | 2447           | 270             | 7.472     |
| llm_measurement@1#02bd5a7ab104    | 3       | 6             | 8505           | 1022            | 27.774    |
| llm_metric@1#41e1e53a1fc4         | 2       | 2             | 2662           | 180             | 5.381     |
| llm_screen@1#41b0d6e6793f         | 3       | 3             | 3144           | 283             | 8.781     |
| regex_author_claim@2#fd7877790c48 | 3       | 0             | 0              | 0               | 0.049     |
| regex_condition@2#0a5bf730763c    | 3       | 0             | 0              | 0               | 0.044     |
| regex_measurement@2#e2d17eb260ea  | 3       | 0             | 0              | 0               | 0.043     |
| regex_metric@2#0affe2d9ce77       | 3       | 0             | 0              | 0               | 0.043     |
| regex_screen@1#858a6ebc69c6       | 3       | 0             | 0              | 0               | 0.045     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 25      | 8.333       |
| input_tokens     | 16758   | 5586.000    |
| made_model_calls | 13      | 4.333       |
| model_calls      | 13      | 4.333       |
| output_tokens    | 1755    | 585.000     |
| seconds          | 49.873  | 16.624      |

## Funnel

Strategy `gaps` over 3 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 8.333          |
| model_calls   | 4.333          |
| input_tokens  | 5586.000       |
| output_tokens | 585.000        |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 3           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 3           | 3    | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
