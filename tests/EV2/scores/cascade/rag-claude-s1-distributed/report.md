# Evaluation of run rag-claude-s1-distributed on rag-claude-s1-869ad7e8

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 187     | 162     | 158       | 0.845       | 0.975    | 0.905 | 1.000           |
| all             | all         | 187     | 162     | 158       | 0.845       | 0.975    | 0.905 | 1.000           |
| author_claim    | distributed | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 78      | 61      | 57        | 0.731       | 0.934    | 0.820 | 1.000           |
| condition       | all         | 78      | 61      | 57        | 0.731       | 0.934    | 0.820 | 1.000           |
| measurement     | distributed | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | all         | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | distributed | 28      | 20      | 20        | 0.714       | 1.000    | 0.833 | 1.000           |
| metric          | all         | 28      | 20      | 20        | 0.714       | 1.000    | 0.833 | 1.000           |

Facts no item matched: 4; items matching no fact: 29.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 61                     | 0.934                  | 0.934                     | 1.000             | 0.852             | 0.902          | 20        | 1.000       |
| all         | 61                     | 0.934                  | 0.934                     | 1.000             | 0.852             | 0.902          | 20        | 1.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 20        | 20           | 0.300                | 0.300          | 1.000               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| distributed | agent-baseline  | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed | rag-baseline    | 20        | 20           | 0.300                | 0.300          | 1.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | yes              | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level       | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|-------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | distributed | 20        | 20               | 20               | 0          | 0            |
| evidence-engine | all         | 20        | 20               | 20               | 0          | 0            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.820 [0.73, 0.88] | BCa      |
| metric          | 0.833 [0.75, 0.91] | BCa      |
| measurement     | 1.000 [n/a]        | -        |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.905 [0.86, 0.93] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               | -          |
| rag-baseline    | 0.300 [0.15, 0.55]   | BCa      | 0.700 [0.45, 0.85]    | BCa             | 20         |
| agent-baseline  | 1.000 [n/a]          | -        | 0.000 [n/a]           | -               | 20         |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | distributed | 418          | 418      | 1.000    |
| all             | all         | 418          | 418      | 1.000    |
| author_claim    | distributed | 40           | 40       | 1.000    |
| author_claim    | all         | 40           | 40       | 1.000    |
| condition       | distributed | 199          | 199      | 1.000    |
| condition       | all         | 199          | 199      | 1.000    |
| measurement     | distributed | 61           | 61       | 1.000    |
| measurement     | all         | 61           | 61       | 1.000    |
| metric          | distributed | 118          | 118      | 1.000    |
| metric          | all         | 118          | 118      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20              | 0      | 0              |
| llm_condition@1#45b3761c700e      | 61      | 52              | 50     | 41             |
| llm_measurement@1#02bd5a7ab104    | 61      | 61              | 61     | 61             |
| llm_metric@1#41e1e53a1fc4         | 20      | 18              | 9      | 7              |
| regex_author_claim@2#fd7877790c48 | 20      | 20              | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 28      | 16              | 17     | 5              |
| regex_measurement@2#e2d17eb260ea  | 0       | 0               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 19      | 13              | 8      | 2              |

Facts no extractor found: condition 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 61      | 61      | 52        | 0.852       | 0.852    | 0.852 | 1.000           | -                      | 50     | 41             |
| llm_condition@1#45b3761c700e      | all             | all     | 61      | 61      | 52        | 0.852       | 0.852    | 0.852 | 1.000           | -                      | 50     | 41             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | 0.934                  | 61     | 61             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 20      | 20      | 18        | 0.900       | 0.900    | 0.900 | 1.000           | -                      | 9      | 7              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 20      | 20      | 18        | 0.900       | 0.900    | 0.900 | 1.000           | -                      | 9      | 7              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 28      | 61      | 16        | 0.571       | 0.262    | 0.360 | 1.000           | -                      | 17     | 5              |
| regex_condition@2#0a5bf730763c    | all             | all     | 28      | 61      | 16        | 0.571       | 0.262    | 0.360 | 1.000           | -                      | 17     | 5              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 19      | 20      | 13        | 0.684       | 0.650    | 0.667 | 1.000           | -                      | 8      | 2              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 19      | 20      | 13        | 0.684       | 0.650    | 0.667 | 1.000           | -                      | 8      | 2              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 20      | 20            | 22390          | 2394            | 53.263    |
| llm_condition@1#45b3761c700e      | 20      | 20            | 23950          | 4404            | 99.231    |
| llm_measurement@1#02bd5a7ab104    | 20      | 40            | 55000          | 8771            | 195.930   |
| llm_metric@1#41e1e53a1fc4         | 20      | 20            | 24470          | 2002            | 46.027    |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 20170          | 2033            | 45.655    |
| regex_author_claim@2#fd7877790c48 | 20      | 0             | 0              | 0               | 0.153     |
| regex_condition@2#0a5bf730763c    | 20      | 0             | 0              | 0               | 0.146     |
| regex_measurement@2#e2d17eb260ea  | 20      | 0             | 0              | 0               | 0.310     |
| regex_metric@2#0affe2d9ce77       | 20      | 0             | 0              | 0               | 0.148     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.144     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 104     | 5.200       |
| calls            | 200     | 10.000      |
| input_tokens     | 145980  | 7299.000    |
| made_model_calls | 96      | 4.800       |
| model_calls      | 120     | 6.000       |
| output_tokens    | 19616   | 980.800     |
| seconds          | 442.302 | 22.115      |

## Re-execution stability

| extractor          | calls   | identical   | identical_share   | item_stability   |
|--------------------|---------|-------------|-------------------|------------------|
| llm_author_claim   | 20      | 20          | 1.000             | 1.000            |
| llm_condition      | 20      | 18          | 0.900             | 1.000            |
| llm_measurement    | 20      | 20          | 1.000             | 1.000            |
| llm_metric         | 20      | 20          | 1.000             | 1.000            |
| llm_screen         | 20      | 15          | 0.750             | 0.800            |
| regex_author_claim | 20      | 20          | 1.000             | 1.000            |
| regex_condition    | 20      | 20          | 1.000             | 1.000            |
| regex_measurement  | 20      | 20          | 1.000             | -                |
| regex_metric       | 20      | 20          | 1.000             | 1.000            |
| regex_screen       | 20      | 20          | 1.000             | 1.000            |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.000          |
| input_tokens  | 7299.000       |
| output_tokens | 980.200        |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
