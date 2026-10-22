# Evaluation of run rag-claude-k1-mixed-escalate on rag-claude-k1-adf90d94

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 35      | 48      | 34        | 0.971       | 0.708    | 0.819 | 0.971           |
| all             | paraphrased   | 35      | 43      | 33        | 0.943       | 0.767    | 0.846 | 0.970           |
| all             | distributed   | 25      | 26      | 24        | 0.960       | 0.923    | 0.941 | 1.000           |
| all             | complex       | 67      | 72      | 61        | 0.910       | 0.847    | 0.878 | 1.000           |
| all             | contradictory | 26      | 38      | 24        | 0.923       | 0.632    | 0.750 | 0.958           |
| all             | all           | 188     | 227     | 176       | 0.936       | 0.775    | 0.848 | 0.983           |
| author_claim    | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 12      | 19      | 12        | 1.000       | 0.632    | 0.774 | 0.917           |
| condition       | paraphrased   | 14      | 17      | 12        | 0.857       | 0.706    | 0.774 | 1.000           |
| condition       | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 8       | 15      | 8         | 1.000       | 0.533    | 0.696 | 0.875           |
| condition       | all           | 51      | 69      | 49        | 0.961       | 0.710    | 0.817 | 0.959           |
| measurement     | explicit      | 13      | 19      | 12        | 0.923       | 0.632    | 0.750 | 1.000           |
| measurement     | paraphrased   | 12      | 16      | 12        | 1.000       | 0.750    | 0.857 | 1.000           |
| measurement     | distributed   | 8       | 9       | 8         | 1.000       | 0.889    | 0.941 | 1.000           |
| measurement     | complex       | 43      | 48      | 37        | 0.860       | 0.771    | 0.813 | 1.000           |
| measurement     | contradictory | 10      | 15      | 8         | 0.800       | 0.533    | 0.640 | 1.000           |
| measurement     | all           | 86      | 107     | 77        | 0.895       | 0.720    | 0.798 | 1.000           |
| metric          | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased   | 4       | 5       | 4         | 1.000       | 0.800    | 0.889 | 0.750           |
| metric          | distributed   | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 29      | 29      | 28        | 0.966       | 0.966    | 0.966 | 0.964           |

Facts no item matched: 51; items matching no fact: 12.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 12                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 5         | 1.000       |
| paraphrased   | 12                     | 0.833                  | 0.833                     | 1.000             | 0.833             | 1.000          | 4         | 0.750       |
| distributed   | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| complex       | 37                     | 0.919                  | 0.919                     | 1.000             | 0.919             | 1.000          | 3         | 0.667       |
| contradictory | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| all           | 77                     | 0.935                  | 0.935                     | 1.000             | 0.935             | 1.000          | 20        | 0.900       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 24        | 20           | 0.958                | 0.950          | 1.000               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 24        | 20           | 0.167                | 0.250          | 0.400               | 0.857          | 0.857     |
| agent-baseline  | mixed   | mixed      | yes             | 24        | 20           | 0.750                | 1.000          | 0.800               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit      | agent-baseline  | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit      | evidence-engine | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit      | rag-baseline    | 5         | 5            | 0.200                | 0.200          | 1.000               | 1.000          | 1.000     |
| paraphrased   | agent-baseline  | 5         | 4            | 0.800                | 1.000          | 1.000               | -              | -         |
| paraphrased   | evidence-engine | 5         | 4            | 0.800                | 0.750          | 1.000               | -              | -         |
| paraphrased   | rag-baseline    | 5         | 4            | 0.000                | 0.250          | 0.000               | 1.000          | 1.000     |
| distributed   | agent-baseline  | 5         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed   | evidence-engine | 5         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed   | rag-baseline    | 5         | 4            | 0.000                | 0.250          | 0.000               | 0.500          | 0.500     |
| complex       | agent-baseline  | 5         | 3            | 0.800                | 1.000          | 1.000               | -              | -         |
| complex       | evidence-engine | 5         | 3            | 1.000                | 1.000          | 1.000               | -              | -         |
| complex       | rag-baseline    | 5         | 3            | 0.600                | 0.333          | 1.000               | 1.000          | 1.000     |
| contradictory | agent-baseline  | 4         | 4            | 0.000                | 1.000          | 0.000               | -              | -         |
| contradictory | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              | -         |
| contradictory | rag-baseline    | 4         | 4            | 0.000                | 0.250          | 0.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 4    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 2    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | large_effect    | 1    | 0    | 1    | 1.000       | 0.500    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit      | 5         | 5                | 5                | 0          | 0            |
| evidence-engine | paraphrased   | 5         | 4                | 5                | 1          | 0            |
| evidence-engine | distributed   | 5         | 5                | 5                | 0          | 0            |
| evidence-engine | complex       | 5         | 5                | 5                | 0          | 0            |
| evidence-engine | contradictory | 4         | 4                | 4                | 0          | 0            |
| evidence-engine | all           | 24        | 23               | 24               | 1          | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.817 [0.73, 0.89] | BCa      |
| metric          | 0.966 [0.88, 1.00] | BCa      |
| measurement     | 0.798 [0.70, 0.87] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.848 [0.79, 0.90] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.958 [0.79, 1.00]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.167 [0.04, 0.33]   | BCa      | 0.792 [0.58, 0.92]    | BCa             | 24         |
| agent-baseline  | 0.750 [0.54, 0.92]   | BCa      | 0.208 [0.04, 0.42]    | BCa             | 24         |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 109          | 109      | 1.000    |
| all             | paraphrased   | 94           | 94       | 1.000    |
| all             | distributed   | 72           | 72       | 1.000    |
| all             | complex       | 156          | 156      | 1.000    |
| all             | contradictory | 88           | 88       | 1.000    |
| all             | all           | 519          | 519      | 1.000    |
| author_claim    | explicit      | 10           | 10       | 1.000    |
| author_claim    | paraphrased   | 10           | 10       | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 44           | 44       | 1.000    |
| condition       | explicit      | 42           | 42       | 1.000    |
| condition       | paraphrased   | 40           | 40       | 1.000    |
| condition       | distributed   | 31           | 31       | 1.000    |
| condition       | complex       | 46           | 46       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 199          | 199      | 1.000    |
| measurement     | explicit      | 19           | 19       | 1.000    |
| measurement     | paraphrased   | 16           | 16       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 48           | 48       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 107          | 107      | 1.000    |
| metric          | explicit      | 38           | 38       | 1.000    |
| metric          | paraphrased   | 28           | 28       | 1.000    |
| metric          | distributed   | 24           | 24       | 1.000    |
| metric          | complex       | 54           | 54       | 1.000    |
| metric          | contradictory | 25           | 25       | 1.000    |
| metric          | all           | 169          | 169      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 29      | 27              | 27     | 25             |
| llm_measurement@1#02bd5a7ab104    | 59      | 56              | 53     | 50             |
| llm_metric@1#41e1e53a1fc4         | 4       | 4               | 4      | 4              |
| regex_author_claim@2#fd7877790c48 | 22      | 22              | 22     | 22             |
| regex_condition@2#0a5bf730763c    | 24      | 24              | 22     | 22             |
| regex_measurement@2#e2d17eb260ea  | 33      | 27              | 27     | 21             |
| regex_metric@2#0affe2d9ce77       | 25      | 24              | 25     | 24             |

Facts no extractor found: condition 20, measurement 30, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 227     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 29      | 44      | 27        | 0.931       | 0.614    | 0.740 | 1.000           | -                      | 27     | 25             |
| llm_condition@1#45b3761c700e      | all             | all     | 29      | 44      | 27        | 0.931       | 0.614    | 0.740 | 1.000           | -                      | 27     | 25             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 59      | 89      | 56        | 0.949       | 0.629    | 0.757 | 1.000           | 0.964                  | 53     | 50             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 59      | 89      | 56        | 0.949       | 0.629    | 0.757 | 1.000           | -                      | 53     | 50             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 4      | 4              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 4      | 4              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 22     | 22             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 22     | 22             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 24      | 69      | 24        | 1.000       | 0.348    | 0.516 | 0.917           | -                      | 22     | 22             |
| regex_condition@2#0a5bf730763c    | all             | all     | 24      | 69      | 24        | 1.000       | 0.348    | 0.516 | 0.917           | -                      | 22     | 22             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 33      | 107     | 27        | 0.818       | 0.252    | 0.386 | 1.000           | 0.889                  | 27     | 21             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 33      | 107     | 27        | 0.818       | 0.252    | 0.386 | 1.000           | -                      | 27     | 21             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 25      | 29      | 24        | 0.960       | 0.828    | 0.889 | 0.958           | -                      | 25     | 24             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 25      | 29      | 24        | 0.960       | 0.828    | 0.889 | 0.958           | -                      | 25     | 24             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 14      | 16            | 18895          | 2203            | 21.697    |
| llm_measurement@1#02bd5a7ab104    | 17      | 34            | 47081          | 10147           | 66.558    |
| llm_metric@1#41e1e53a1fc4         | 4       | 5             | 5734           | 412             | 6.827     |
| llm_screen@1#41b0d6e6793f         | 24      | 24            | 21532          | 1998            | 18.026    |
| regex_author_claim@2#fd7877790c48 | 22      | 0             | 0              | 0               | 0.193     |
| regex_condition@2#0a5bf730763c    | 22      | 0             | 0              | 0               | 0.197     |
| regex_measurement@2#e2d17eb260ea  | 22      | 0             | 0              | 0               | 0.198     |
| regex_metric@2#0affe2d9ce77       | 22      | 0             | 0              | 0               | 0.189     |
| regex_screen@1#858a6ebc69c6       | 24      | 0             | 0              | 0               | 0.222     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 120     | 5.000       |
| calls            | 171     | 7.125       |
| input_tokens     | 93242   | 3885.083    |
| made_model_calls | 25      | 1.042       |
| model_calls      | 79      | 3.292       |
| output_tokens    | 14760   | 615.000     |
| seconds          | 115.420 | 4.809       |

## Funnel

Strategy `gaps` over 24 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.125          |
| model_calls   | 3.292          |
| input_tokens  | 3885.083       |
| output_tokens | 615.000        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 4           |
| 1               | 15          |
| exhausted       | 3           |
| skipped         | 2           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 24          | 22   | 0    | 0    | 2    | 1.000       | 1.000    |

Screened out wrongly: none
