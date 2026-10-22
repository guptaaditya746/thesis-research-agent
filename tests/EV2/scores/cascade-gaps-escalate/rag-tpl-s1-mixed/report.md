# Evaluation of run rag-tpl-s1-mixed-escalate on rag-tpl-s1-6162b495

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 28      | 38      | 28        | 1.000       | 0.737    | 0.848 | 1.000           |
| all             | paraphrased   | 8       | 34      | 8         | 1.000       | 0.235    | 0.381 | 1.000           |
| all             | distributed   | 24      | 26      | 24        | 1.000       | 0.923    | 0.960 | 1.000           |
| all             | complex       | 50      | 74      | 49        | 0.980       | 0.662    | 0.790 | 1.000           |
| all             | contradictory | 26      | 38      | 24        | 0.923       | 0.632    | 0.750 | 1.000           |
| all             | all           | 136     | 210     | 133       | 0.978       | 0.633    | 0.769 | 1.000           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 10      | 15      | 10        | 1.000       | 0.667    | 0.800 | 1.000           |
| condition       | paraphrased   | 4       | 13      | 4         | 1.000       | 0.308    | 0.471 | 1.000           |
| condition       | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | complex       | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | contradictory | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 1.000           |
| condition       | all           | 38      | 61      | 38        | 1.000       | 0.623    | 0.768 | 1.000           |
| measurement     | explicit      | 10      | 15      | 10        | 1.000       | 0.667    | 0.800 | 1.000           |
| measurement     | paraphrased   | 0       | 13      | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| measurement     | complex       | 27      | 50      | 26        | 0.963       | 0.520    | 0.675 | 1.000           |
| measurement     | contradictory | 10      | 15      | 8         | 0.800       | 0.533    | 0.640 | 1.000           |
| measurement     | all           | 55      | 102     | 52        | 0.945       | 0.510    | 0.662 | 1.000           |
| metric          | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased   | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               |
| metric          | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           |

Facts no item matched: 77; items matching no fact: 3.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 10                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| paraphrased   | 0                      | -                      | -                         | -                 | -                 | -              | 4         | 0.000       |
| distributed   | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| complex       | 26                     | 0.923                  | 0.923                     | 1.000             | 0.923             | 1.000          | 4         | 0.000       |
| contradictory | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| all           | 52                     | 0.962                  | 0.962                     | 1.000             | 0.962             | 1.000          | 20        | 0.600       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.800                | 0.800          | 1.000               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 20        | 20           | 0.150                | 0.200          | 0.750               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 20        | 20           | 0.650                | 1.000          | 0.650               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit      | agent-baseline  | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit      | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit      | rag-baseline    | 4         | 4            | 0.250                | 0.250          | 1.000               | 1.000          | 1.000     |
| paraphrased   | agent-baseline  | 4         | 4            | 0.750                | 1.000          | 0.750               | -              | -         |
| paraphrased   | evidence-engine | 4         | 4            | 0.000                | 0.000          | -                   | -              | -         |
| paraphrased   | rag-baseline    | 4         | 4            | 0.000                | 0.000          | -                   | -              | -         |
| distributed   | agent-baseline  | 4         | 4            | 0.750                | 1.000          | 0.750               | -              | -         |
| distributed   | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed   | rag-baseline    | 4         | 4            | 0.000                | 0.000          | -                   | -              | -         |
| complex       | agent-baseline  | 4         | 4            | 0.750                | 1.000          | 0.750               | -              | -         |
| complex       | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| complex       | rag-baseline    | 4         | 4            | 0.250                | 0.250          | 1.000               | 1.000          | 1.000     |
| contradictory | agent-baseline  | 4         | 4            | 0.000                | 1.000          | 0.000               | -              | -         |
| contradictory | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| contradictory | rag-baseline    | 4         | 4            | 0.250                | 0.500          | 0.500               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 4    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit      | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | paraphrased   | 4         | 0                | 4                | 4          | 0            |
| evidence-engine | distributed   | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | complex       | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | contradictory | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | all           | 20        | 16               | 20               | 4          | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.768 [0.68, 0.85] | BCa      |
| metric          | 0.920 [0.80, 0.98] | BCa      |
| measurement     | 0.662 [0.55, 0.80] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.769 [0.69, 0.85] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.800 [0.60, 0.95]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.150 [0.05, 0.35]   | BCa      | 0.650 [0.40, 0.85]    | BCa             | 20         |
| agent-baseline  | 0.650 [0.45, 0.85]   | BCa      | 0.150 [-0.15, 0.45]   | BCa             | 20         |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 84           | 84       | 1.000    |
| all             | paraphrased   | 72           | 72       | 1.000    |
| all             | distributed   | 60           | 60       | 1.000    |
| all             | complex       | 138          | 138      | 1.000    |
| all             | contradictory | 77           | 77       | 1.000    |
| all             | all           | 431          | 431      | 1.000    |
| author_claim    | explicit      | 8            | 8        | 1.000    |
| author_claim    | paraphrased   | 8            | 8        | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
| condition       | explicit      | 38           | 38       | 1.000    |
| condition       | paraphrased   | 34           | 34       | 1.000    |
| condition       | distributed   | 27           | 27       | 1.000    |
| condition       | complex       | 43           | 43       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 182          | 182      | 1.000    |
| measurement     | explicit      | 15           | 15       | 1.000    |
| measurement     | paraphrased   | 13           | 13       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 50           | 50       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 102          | 102      | 1.000    |
| metric          | explicit      | 23           | 23       | 1.000    |
| metric          | paraphrased   | 17           | 17       | 1.000    |
| metric          | distributed   | 16           | 16       | 1.000    |
| metric          | complex       | 37           | 37       | 1.000    |
| metric          | contradictory | 14           | 14       | 1.000    |
| metric          | all           | 107          | 107      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 17      | 17              | 15     | 15             |
| llm_measurement@1#02bd5a7ab104    | 29      | 29              | 24     | 24             |
| llm_metric@1#41e1e53a1fc4         | 1       | 1               | 1      | 1              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 20     | 20             |
| regex_condition@2#0a5bf730763c    | 23      | 23              | 21     | 21             |
| regex_measurement@2#e2d17eb260ea  | 31      | 28              | 26     | 23             |
| regex_metric@2#0affe2d9ce77       | 22      | 22              | 22     | 22             |

Facts no extractor found: condition 23, measurement 50, metric 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 210     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 17      | 36      | 17        | 1.000       | 0.472    | 0.642 | 1.000           | -                      | 15     | 15             |
| llm_condition@1#45b3761c700e      | all             | all     | 17      | 36      | 17        | 1.000       | 0.472    | 0.642 | 1.000           | -                      | 15     | 15             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 29      | 66      | 29        | 1.000       | 0.439    | 0.611 | 1.000           | 1.000                  | 24     | 24             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 29      | 66      | 29        | 1.000       | 0.439    | 0.611 | 1.000           | -                      | 24     | 24             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 1.000           | -                      | 21     | 21             |
| regex_condition@2#0a5bf730763c    | all             | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 1.000           | -                      | 21     | 21             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 31      | 102     | 28        | 0.903       | 0.275    | 0.421 | 1.000           | 0.929                  | 26     | 23             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 31      | 102     | 28        | 0.903       | 0.275    | 0.421 | 1.000           | -                      | 26     | 23             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 22      | 27      | 22        | 1.000       | 0.815    | 0.898 | 1.000           | -                      | 22     | 22             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 22      | 27      | 22        | 1.000       | 0.815    | 0.898 | 1.000           | -                      | 22     | 22             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 12      | 22            | 21363          | 1893            | 54.195    |
| llm_measurement@1#02bd5a7ab104    | 12      | 24            | 28416          | 5010            | 131.465   |
| llm_metric@1#41e1e53a1fc4         | 1       | 1             | 998            | 94              | 2.677     |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 15335          | 1595            | 45.303    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.285     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.290     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.303     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.285     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.273     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 145     | 7.250       |
| input_tokens     | 66112   | 3305.600    |
| made_model_calls | 67      | 3.350       |
| model_calls      | 67      | 3.350       |
| output_tokens    | 8592    | 429.600     |
| seconds          | 236.277 | 11.814      |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.250          |
| model_calls   | 3.350          |
| input_tokens  | 3305.600       |
| output_tokens | 429.600        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 4           |
| 1               | 12          |
| exhausted       | 4           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
