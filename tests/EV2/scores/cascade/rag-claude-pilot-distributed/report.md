# Evaluation of run rag-claude-pilot-distributed on rag-claude-pilot-7807c6b5

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 33      | 28      | 27        | 0.818       | 0.964    | 0.885 | 1.000           |
| all             | all         | 33      | 28      | 27        | 0.818       | 0.964    | 0.885 | 1.000           |
| author_claim    | distributed | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 15      | 11      | 10        | 0.667       | 0.909    | 0.769 | 1.000           |
| condition       | all         | 15      | 11      | 10        | 0.667       | 0.909    | 0.769 | 1.000           |
| measurement     | distributed | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | all         | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | distributed | 4       | 3       | 3         | 0.750       | 1.000    | 0.857 | 1.000           |
| metric          | all         | 4       | 3       | 3         | 0.750       | 1.000    | 0.857 | 1.000           |

Facts no item matched: 1; items matching no fact: 6.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 11                     | 0.909                  | 0.909                     | 1.000             | 0.727             | 0.636          | 3         | 1.000       |
| all         | 11                     | 0.909                  | 0.909                     | 1.000             | 0.727             | 0.636          | 3         | 1.000       |

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
| condition       | 0.769 [0.57, 0.86] | BCa      |
| metric          | 0.857 [0.67, 1.00] | BCa      |
| measurement     | 1.000 [n/a]        | -        |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.885 [0.82, 0.91] | BCa      |

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
| llm_author_claim@1#be3c17081ff9   | 3       | 3               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 11      | 8               | 11     | 8              |
| llm_measurement@1#02bd5a7ab104    | 11      | 11              | 11     | 11             |
| llm_metric@1#41e1e53a1fc4         | 3       | 2               | 3      | 2              |
| regex_author_claim@2#fd7877790c48 | 3       | 3               | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 4       | 2               | 4      | 2              |
| regex_measurement@2#e2d17eb260ea  | 0       | 0               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 1       | 1               | 1      | 1              |

Facts no extractor found: condition 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 11      | 11      | 8         | 0.727       | 0.727    | 0.727 | 1.000           | -                      | 11     | 8              |
| llm_condition@1#45b3761c700e      | all             | all     | 11      | 11      | 8         | 0.727       | 0.727    | 0.727 | 1.000           | -                      | 11     | 8              |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | 0.909                  | 11     | 11             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 3       | 3       | 2         | 0.667       | 0.667    | 0.667 | 1.000           | -                      | 3      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 3       | 3       | 2         | 0.667       | 0.667    | 0.667 | 1.000           | -                      | 3      | 2              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 4       | 11      | 2         | 0.500       | 0.182    | 0.267 | 1.000           | -                      | 4      | 2              |
| regex_condition@2#0a5bf730763c    | all             | all     | 4       | 11      | 2         | 0.500       | 0.182    | 0.267 | 1.000           | -                      | 4      | 2              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 0       | 11      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 0       | 11      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 1       | 3       | 1         | 1.000       | 0.333    | 0.500 | 1.000           | -                      | 1      | 1              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 1       | 3       | 1         | 1.000       | 0.333    | 0.500 | 1.000           | -                      | 1      | 1              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 3       | 3             | 3477           | 363             | 10.128    |
| llm_condition@1#45b3761c700e      | 3       | 3             | 3711           | 781             | 20.214    |
| llm_measurement@1#02bd5a7ab104    | 3       | 6             | 8733           | 1564            | 40.853    |
| llm_metric@1#41e1e53a1fc4         | 3       | 3             | 3789           | 279             | 8.217     |
| llm_screen@1#41b0d6e6793f         | 3       | 3             | 3144           | 283             | 8.767     |
| regex_author_claim@2#fd7877790c48 | 3       | 0             | 0              | 0               | 0.049     |
| regex_condition@2#0a5bf730763c    | 3       | 0             | 0              | 0               | 0.050     |
| regex_measurement@2#e2d17eb260ea  | 3       | 0             | 0              | 0               | 0.052     |
| regex_metric@2#0affe2d9ce77       | 3       | 0             | 0              | 0               | 0.046     |
| regex_screen@1#858a6ebc69c6       | 3       | 0             | 0              | 0               | 0.047     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 30      | 10.000      |
| input_tokens     | 22854   | 7618.000    |
| made_model_calls | 18      | 6.000       |
| model_calls      | 18      | 6.000       |
| output_tokens    | 3270    | 1090.000    |
| seconds          | 88.643  | 29.548      |

## Funnel

Strategy `all` over 3 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.000          |
| input_tokens  | 7618.000       |
| output_tokens | 1090.000       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 3           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 3           | 3    | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
