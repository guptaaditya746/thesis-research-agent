# Evaluation of run rag-tpl-hard-complex on rag-tpl-hard-24ab4663

Question: Does retrieval-augmented generation reduce the hallucination rate of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 2080    | 2469    | 1479      | 0.711       | 0.599    | 0.650 | 1.000           |
| all             | all     | 2080    | 2469    | 1479      | 0.711       | 0.599    | 0.650 | 1.000           |
| author_claim    | complex | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 395     | 332     | 257       | 0.651       | 0.774    | 0.707 | 1.000           |
| condition       | all     | 395     | 332     | 257       | 0.651       | 0.774    | 0.707 | 1.000           |
| measurement     | complex | 1129    | 1768    | 853       | 0.756       | 0.482    | 0.589 | 1.000           |
| measurement     | all     | 1129    | 1768    | 853       | 0.756       | 0.482    | 0.589 | 1.000           |
| metric          | complex | 450     | 263     | 263       | 0.584       | 1.000    | 0.738 | 1.000           |
| metric          | all     | 450     | 263     | 263       | 0.584       | 1.000    | 0.738 | 1.000           |

Facts no item matched: 990; items matching no fact: 601.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 853                    | 0.555                  | 0.821                     | 0.646             | 0.817             | 0.525          | 59        | 0.034       |
| all     | 853                    | 0.555                  | 0.821                     | 0.646             | 0.817             | 0.525          | 59        | 0.034       |

## C. Synthesis

| system          | label        | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|-----------------|--------------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| evidence-engine | mixed        | mixed      | yes             | 112       | 59           | 0.814                | 0.915          | 0.889               | 0.902                           | -              | -         |
| rag-baseline    | refuted      | mixed      | no              | 112       | 59           | 0.000                | 0.102          | 0.000               | 0.455                           | 1.000          | 1.000     |
| agent-baseline  | insufficient | mixed      | no              | 112       | 59           | 0.000                | 0.000          | -                   | 0.473                           | -              | -         |

direction_accuracy, completeness and accuracy_answered are over the determined studies only (the studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, and a study whose expected direction is undetermined (missing information, an irrelevant paper) is not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is the old number over all scored studies, where silence on an undetermined study counts as right. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | direction_accuracy_all_papers   | traceability   | overlap   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|---------------------------------|----------------|-----------|
| complex | agent-baseline  | 112       | 59           | 0.000                | 0.000          | -                   | 0.473                           | -              | -         |
| complex | evidence-engine | 112       | 59           | 0.814                | 0.915          | 0.889               | 0.902                           | -              | -         |
| complex | rag-baseline    | 112       | 59           | 0.000                | 0.102          | 0.000               | 0.455                           | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 6    | 0    | 0.000       | -        |
| evidence-engine | duplicate       | 4    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | large_effect    | 2    | 2    | 0    | 0.500       | 1.000    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.707 [0.69, 0.73] | BCa      |
| metric          | 0.738 [0.71, 0.76] | BCa      |
| measurement     | 0.589 [0.54, 0.63] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.650 [0.62, 0.68] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.814 [0.69, 0.90]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.000 [n/a]          | -        | 0.814 [0.69, 0.90]    | BCa             | 59         |
| agent-baseline  | 0.000 [n/a]          | -        | 0.814 [0.69, 0.90]    | BCa             | 59         |

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
| abbrev_condition@1#8587f7b799e0   | 0       | 0               | 0      | 0              |
| abbrev_metric@1#1c52ebcdca5c      | 0       | 0               | 0      | 0              |
| gliner_condition@1#6df192dba74f   | 215     | 80              | 142    | 7              |
| gliner_metric@1#cdbeb73388e0      | 339     | 177             | 167    | 5              |
| llm_author_claim@1#0bbf299aba25   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 122     | 122             | 57     | 57             |
| llm_measurement@1#02bd5a7ab104    | 402     | 257             | 274    | 164            |
| llm_metric@1#41e1e53a1fc4         | 189     | 189             | 47     | 47             |
| number_measurement@1#d7f39465e8e3 | 439     | 299             | 277    | 172            |
| regex_author_claim@2#f0e017f040b9 | 106     | 106             | 106    | 106            |
| regex_condition@2#dacfca378fed    | 162     | 159             | 123    | 120            |
| regex_measurement@2#8955e245e6dd  | 452     | 426             | 416    | 390            |
| regex_metric@2#ae09439dbca7       | 216     | 191             | 64     | 39             |

Facts no extractor found: condition 75, measurement 915

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_condition@1#8587f7b799e0   | condition       | all     | 0       | 137     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_condition@1#8587f7b799e0   | all             | all     | 0       | 137     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_metric@1#1c52ebcdca5c      | metric          | all     | 0       | 224     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_metric@1#1c52ebcdca5c      | all             | all     | 0       | 224     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| gliner_condition@1#6df192dba74f   | condition       | all     | 215     | 137     | 80        | 0.372       | 0.584    | 0.455 | 1.000           | -                      | 142    | 7              |
| gliner_condition@1#6df192dba74f   | all             | all     | 215     | 137     | 80        | 0.372       | 0.584    | 0.455 | 1.000           | -                      | 142    | 7              |
| gliner_metric@1#cdbeb73388e0      | metric          | all     | 339     | 224     | 177       | 0.522       | 0.790    | 0.629 | 1.000           | -                      | 167    | 5              |
| gliner_metric@1#cdbeb73388e0      | all             | all     | 339     | 224     | 177       | 0.522       | 0.790    | 0.629 | 1.000           | -                      | 167    | 5              |
| llm_author_claim@1#0bbf299aba25   | all             | all     | 0       | 2469    | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 122     | 137     | 122       | 1.000       | 0.891    | 0.942 | 1.000           | -                      | 57     | 57             |
| llm_condition@1#45b3761c700e      | all             | all     | 122     | 137     | 122       | 1.000       | 0.891    | 0.942 | 1.000           | -                      | 57     | 57             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 402     | 930     | 257       | 0.639       | 0.276    | 0.386 | 1.000           | 0.883                  | 274    | 164            |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 402     | 930     | 257       | 0.639       | 0.276    | 0.386 | 1.000           | -                      | 274    | 164            |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 189     | 224     | 189       | 1.000       | 0.844    | 0.915 | 1.000           | -                      | 47     | 47             |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 189     | 224     | 189       | 1.000       | 0.844    | 0.915 | 1.000           | -                      | 47     | 47             |
| number_measurement@1#d7f39465e8e3 | measurement     | all     | 439     | 954     | 299       | 0.681       | 0.313    | 0.429 | 1.000           | 0.649                  | 277    | 172            |
| number_measurement@1#d7f39465e8e3 | all             | all     | 439     | 954     | 299       | 0.681       | 0.313    | 0.429 | 1.000           | -                      | 277    | 172            |
| regex_author_claim@2#f0e017f040b9 | author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_author_claim@2#f0e017f040b9 | all             | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_condition@2#dacfca378fed    | condition       | all     | 162     | 332     | 159       | 0.981       | 0.479    | 0.644 | 1.000           | -                      | 123    | 120            |
| regex_condition@2#dacfca378fed    | all             | all     | 162     | 332     | 159       | 0.981       | 0.479    | 0.644 | 1.000           | -                      | 123    | 120            |
| regex_measurement@2#8955e245e6dd  | measurement     | all     | 452     | 1768    | 426       | 0.942       | 0.241    | 0.384 | 1.000           | 0.404                  | 416    | 390            |
| regex_measurement@2#8955e245e6dd  | all             | all     | 452     | 1768    | 426       | 0.942       | 0.241    | 0.384 | 1.000           | -                      | 416    | 390            |
| regex_metric@2#ae09439dbca7       | metric          | all     | 216     | 263     | 191       | 0.884       | 0.726    | 0.797 | 1.000           | -                      | 64     | 39             |
| regex_metric@2#ae09439dbca7       | all             | all     | 216     | 263     | 191       | 0.884       | 0.726    | 0.797 | 1.000           | -                      | 64     | 39             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_condition@1#8587f7b799e0   | 46      | 0             | 0              | 0               | 0.295     |
| abbrev_metric@1#1c52ebcdca5c      | 91      | 0             | 0              | 0               | 0.589     |
| gliner_condition@1#6df192dba74f   | 46      | 149           | 0              | 0               | 0.331     |
| gliner_metric@1#cdbeb73388e0      | 91      | 307           | 0              | 0               | 0.651     |
| llm_condition@1#45b3761c700e      | 46      | 79            | 91994          | 12238           | 0.320     |
| llm_measurement@1#02bd5a7ab104    | 55      | 110           | 181751         | 66893           | 0.427     |
| llm_metric@1#41e1e53a1fc4         | 91      | 108           | 131156         | 16841           | 0.603     |
| llm_screen@1#41b0d6e6793f         | 109     | 109           | 102099         | 8160            | 0.709     |
| number_measurement@1#d7f39465e8e3 | 56      | 0             | 0              | 0               | 0.476     |
| regex_author_claim@2#f0e017f040b9 | 106     | 0             | 0              | 0               | 0.677     |
| regex_condition@2#dacfca378fed    | 106     | 0             | 0              | 0               | 0.702     |
| regex_measurement@2#8955e245e6dd  | 106     | 0             | 0              | 0               | 0.782     |
| regex_metric@2#ae09439dbca7       | 106     | 0             | 0              | 0               | 0.712     |
| regex_screen@1#858a6ebc69c6       | 112     | 0             | 0              | 0               | 0.718     |

## Cost

| measure          | total    | per_paper   |
|------------------|----------|-------------|
| cached_calls     | 0        | 0.000       |
| calls            | 1167     | 10.420      |
| input_tokens     | 507000   | 4526.786    |
| made_model_calls | 862      | 7.696       |
| model_calls      | 862      | 7.696       |
| output_tokens    | 104132   | 929.750     |
| seconds          | 1020.830 | 9.115       |
| workers          | 3        | -           |

## Funnel

Strategy `gaps` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.420         |
| model_calls   | 7.696          |
| input_tokens  | 4526.786       |
| output_tokens | 929.750        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 6           |
| 2               | 1           |
| 3               | 47          |
| exhausted       | 52          |
| skipped         | 6           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 0    | 0    | 6    | 1.000       | 1.000    |

Screened out wrongly: none
