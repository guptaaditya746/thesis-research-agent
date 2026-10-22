# Evaluation of run rag-tpl-k1-mixed on rag-tpl-k1-9c3bbb32

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 39      | 48      | 38        | 0.974       | 0.792    | 0.874 | 1.000           |
| all             | paraphrased   | 15      | 43      | 15        | 1.000       | 0.349    | 0.517 | 1.000           |
| all             | distributed   | 24      | 26      | 24        | 1.000       | 0.923    | 0.960 | 1.000           |
| all             | complex       | 49      | 72      | 48        | 0.980       | 0.667    | 0.793 | 1.000           |
| all             | contradictory | 26      | 38      | 24        | 0.923       | 0.632    | 0.750 | 1.000           |
| all             | all           | 153     | 227     | 149       | 0.974       | 0.656    | 0.784 | 1.000           |
| author_claim    | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 14      | 19      | 14        | 1.000       | 0.737    | 0.848 | 1.000           |
| condition       | paraphrased   | 7       | 17      | 7         | 1.000       | 0.412    | 0.583 | 1.000           |
| condition       | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | complex       | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | contradictory | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 1.000           |
| condition       | all           | 45      | 69      | 45        | 1.000       | 0.652    | 0.789 | 1.000           |
| measurement     | explicit      | 15      | 19      | 14        | 0.933       | 0.737    | 0.824 | 1.000           |
| measurement     | paraphrased   | 2       | 16      | 2         | 1.000       | 0.125    | 0.222 | 1.000           |
| measurement     | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| measurement     | complex       | 26      | 48      | 25        | 0.962       | 0.521    | 0.676 | 1.000           |
| measurement     | contradictory | 10      | 15      | 8         | 0.800       | 0.533    | 0.640 | 1.000           |
| measurement     | all           | 61      | 107     | 57        | 0.934       | 0.533    | 0.679 | 1.000           |
| metric          | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased   | 1       | 5       | 1         | 1.000       | 0.200    | 0.333 | 1.000           |
| metric          | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 25      | 29      | 25        | 1.000       | 0.862    | 0.926 | 1.000           |

Facts no item matched: 78; items matching no fact: 4.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 14                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 5         | 1.000       |
| paraphrased   | 2                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 0.000       |
| distributed   | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| complex       | 25                     | 0.920                  | 0.920                     | 1.000             | 0.920             | 1.000          | 3         | 0.000       |
| contradictory | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| all           | 57                     | 0.965                  | 0.965                     | 1.000             | 0.965             | 1.000          | 20        | 0.650       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 24        | 20           | 0.833                | 0.800          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit      | evidence-engine | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| paraphrased   | evidence-engine | 5         | 4            | 0.200                | 0.000          | -                   | -              | -         |
| distributed   | evidence-engine | 5         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| complex       | evidence-engine | 5         | 3            | 1.000                | 1.000          | 1.000               | -              | -         |
| contradictory | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 4    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 1    | 0    | 1    | 1.000       | 0.500    |
| evidence-engine | large_effect    | 1    | 0    | 1    | 1.000       | 0.500    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | no                   |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit      | 5         | 5                | 5                | 0          | 0            |
| evidence-engine | paraphrased   | 5         | 1                | 5                | 4          | 0            |
| evidence-engine | distributed   | 5         | 5                | 5                | 0          | 0            |
| evidence-engine | complex       | 5         | 5                | 5                | 0          | 0            |
| evidence-engine | contradictory | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | all           | 24        | 20               | 24               | 4          | 0            |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.789 [0.70, 0.86] | BCa      |
| metric          | 0.926 [0.80, 0.98] | BCa      |
| measurement     | 0.679 [0.57, 0.80] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.784 [0.71, 0.86] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.833 [0.62, 0.96]   | BCa      | -                     | -               | -          |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 106          | 106      | 1.000    |
| all             | paraphrased   | 90           | 90       | 1.000    |
| all             | distributed   | 60           | 60       | 1.000    |
| all             | complex       | 133          | 133      | 1.000    |
| all             | contradictory | 77           | 77       | 1.000    |
| all             | all           | 466          | 466      | 1.000    |
| author_claim    | explicit      | 10           | 10       | 1.000    |
| author_claim    | paraphrased   | 10           | 10       | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 44           | 44       | 1.000    |
| condition       | explicit      | 48           | 48       | 1.000    |
| condition       | paraphrased   | 43           | 43       | 1.000    |
| condition       | distributed   | 27           | 27       | 1.000    |
| condition       | complex       | 41           | 41       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 199          | 199      | 1.000    |
| measurement     | explicit      | 19           | 19       | 1.000    |
| measurement     | paraphrased   | 16           | 16       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 48           | 48       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 107          | 107      | 1.000    |
| metric          | explicit      | 29           | 29       | 1.000    |
| metric          | paraphrased   | 21           | 21       | 1.000    |
| metric          | distributed   | 16           | 16       | 1.000    |
| metric          | complex       | 36           | 36       | 1.000    |
| metric          | contradictory | 14           | 14       | 1.000    |
| metric          | all           | 116          | 116      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 24      | 24              | 21     | 21             |
| llm_measurement@1#02bd5a7ab104    | 37      | 37              | 30     | 30             |
| llm_metric@1#41e1e53a1fc4         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | 22      | 22              | 22     | 22             |
| regex_condition@2#0a5bf730763c    | 24      | 24              | 21     | 21             |
| regex_measurement@2#e2d17eb260ea  | 31      | 27              | 24     | 20             |
| regex_metric@2#0affe2d9ce77       | 23      | 23              | 23     | 23             |

Facts no extractor found: condition 24, measurement 50, metric 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 227     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 24      | 44      | 24        | 1.000       | 0.545    | 0.706 | 1.000           | -                      | 21     | 21             |
| llm_condition@1#45b3761c700e      | all             | all     | 24      | 44      | 24        | 1.000       | 0.545    | 0.706 | 1.000           | -                      | 21     | 21             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 37      | 82      | 37        | 1.000       | 0.451    | 0.622 | 1.000           | 1.000                  | 30     | 30             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 37      | 82      | 37        | 1.000       | 0.451    | 0.622 | 1.000           | -                      | 30     | 30             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 22     | 22             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 22     | 22             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 24      | 69      | 24        | 1.000       | 0.348    | 0.516 | 1.000           | -                      | 21     | 21             |
| regex_condition@2#0a5bf730763c    | all             | all     | 24      | 69      | 24        | 1.000       | 0.348    | 0.516 | 1.000           | -                      | 21     | 21             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 31      | 107     | 27        | 0.871       | 0.252    | 0.391 | 1.000           | 0.926                  | 24     | 20             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 31      | 107     | 27        | 0.871       | 0.252    | 0.391 | 1.000           | -                      | 24     | 20             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 23      | 29      | 23        | 1.000       | 0.793    | 0.885 | 1.000           | -                      | 23     | 23             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 23      | 29      | 23        | 1.000       | 0.793    | 0.885 | 1.000           | -                      | 23     | 23             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 14      | 26            | 25392          | 2671            | 39.297    |
| llm_measurement@1#02bd5a7ab104    | 15      | 30            | 35834          | 6673            | 71.657    |
| llm_metric@1#41e1e53a1fc4         | 2       | 2             | 1966           | 189             | 2.696     |
| llm_screen@1#41b0d6e6793f         | 23      | 23            | 17365          | 1815            | 0.152     |
| regex_author_claim@2#fd7877790c48 | 22      | 0             | 0              | 0               | 0.140     |
| regex_condition@2#0a5bf730763c    | 22      | 0             | 0              | 0               | 0.140     |
| regex_measurement@2#e2d17eb260ea  | 22      | 0             | 0              | 0               | 0.142     |
| regex_metric@2#0affe2d9ce77       | 22      | 0             | 0              | 0               | 0.140     |
| regex_screen@1#858a6ebc69c6       | 24      | 0             | 0              | 0               | 0.154     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 155     | 6.458       |
| calls            | 166     | 6.917       |
| input_tokens     | 80557   | 3356.542    |
| made_model_calls | 21      | 0.875       |
| model_calls      | 81      | 3.375       |
| output_tokens    | 11348   | 472.833     |
| seconds          | 115.776 | 4.824       |

## Funnel

Strategy `gaps` over 24 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 6.917          |
| model_calls   | 3.375          |
| input_tokens  | 3356.542       |
| output_tokens | 472.833        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 3           |
| 1               | 13          |
| exhausted       | 6           |
| skipped         | 2           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 24          | 22   | 0    | 0    | 2    | 1.000       | 1.000    |

Screened out wrongly: none
