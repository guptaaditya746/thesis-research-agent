# Evaluation of run rag-claude-small-paraphrased on rag-claude-small-7eb8078c

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: paraphrased

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | paraphrased | 34      | 34      | 33        | 0.971       | 0.971    | 0.971 | 1.000           |
| all             | all         | 34      | 34      | 33        | 0.971       | 0.971    | 0.971 | 1.000           |
| author_claim    | paraphrased | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased | 12      | 12      | 11        | 0.917       | 0.917    | 0.917 | 1.000           |
| condition       | all         | 12      | 12      | 11        | 0.917       | 0.917    | 0.917 | 1.000           |
| measurement     | paraphrased | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | all         | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all         | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 1; items matching no fact: 1.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| paraphrased | 12                     | 0.917                  | 0.917                     | 1.000             | 0.917             | 1.000          | 5         | 1.000       |
| all         | 12                     | 0.917                  | 0.917                     | 1.000             | 0.917             | 1.000          | 5         | 1.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 5         | 5            | 1.000                | 1.000          | 1.000               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| paraphrased | agent-baseline  | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| paraphrased | evidence-engine | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| paraphrased | rag-baseline    | 5         | 5            | 1.000                | 1.000          | 1.000               | 1.000          | 1.000     |

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
| condition       | 0.917 [0.78, 1.00] | BCa      |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 1.000 [n/a]        | -        |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.971 [0.91, 1.00] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               | -          |
| rag-baseline    | 1.000 [n/a]          | -        | 0.000 [n/a]           | -               | 5          |
| agent-baseline  | 1.000 [n/a]          | -        | 0.000 [n/a]           | -               | 5          |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | paraphrased | 94           | 94       | 1.000    |
| all             | all         | 94           | 94       | 1.000    |
| author_claim    | paraphrased | 10           | 10       | 1.000    |
| author_claim    | all         | 10           | 10       | 1.000    |
| condition       | paraphrased | 55           | 55       | 1.000    |
| condition       | all         | 55           | 55       | 1.000    |
| measurement     | paraphrased | 12           | 12       | 1.000    |
| measurement     | all         | 12           | 12       | 1.000    |
| metric          | paraphrased | 17           | 17       | 1.000    |
| metric          | all         | 17           | 17       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 5       | 5               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 12      | 11              | 12     | 11             |
| llm_measurement@1#02bd5a7ab104    | 12      | 12              | 12     | 12             |
| llm_metric@1#41e1e53a1fc4         | 5       | 5               | 5      | 5              |
| regex_author_claim@2#fd7877790c48 | 5       | 5               | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 0       | 0               | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | 0       | 0               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 0       | 0               | 0      | 0              |

Facts no extractor found: condition 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 12      | 12      | 11        | 0.917       | 0.917    | 0.917 | 1.000           | -                      | 12     | 11             |
| llm_condition@1#45b3761c700e      | all             | all     | 12      | 12      | 11        | 0.917       | 0.917    | 0.917 | 1.000           | -                      | 12     | 11             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | 0.917                  | 12     | 12             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 12     | 12             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 5      | 5              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 5      | 5              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 0       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 0       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 5       | 5             | 5670           | 597             | 17.977    |
| llm_condition@1#45b3761c700e      | 5       | 9             | 10671          | 1245            | 38.082    |
| llm_measurement@1#02bd5a7ab104    | 5       | 10            | 14365          | 2898            | 86.011    |
| llm_metric@1#41e1e53a1fc4         | 5       | 5             | 6190           | 489             | 16.569    |
| llm_screen@1#41b0d6e6793f         | 5       | 5             | 5115           | 489             | 17.144    |
| regex_author_claim@2#fd7877790c48 | 5       | 0             | 0              | 0               | 0.087     |
| regex_condition@2#0a5bf730763c    | 5       | 0             | 0              | 0               | 0.072     |
| regex_measurement@2#e2d17eb260ea  | 5       | 0             | 0              | 0               | 0.089     |
| regex_metric@2#0affe2d9ce77       | 5       | 0             | 0              | 0               | 0.074     |
| regex_screen@1#858a6ebc69c6       | 5       | 0             | 0              | 0               | 0.075     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 50      | 10.000      |
| input_tokens     | 42011   | 8402.200    |
| made_model_calls | 34      | 6.800       |
| model_calls      | 34      | 6.800       |
| output_tokens    | 5718    | 1143.600    |
| seconds          | 176.534 | 35.307      |

## Funnel

Strategy `all` over 5 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.800          |
| input_tokens  | 8402.200       |
| output_tokens | 1143.600       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 5           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 5           | 5    | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
