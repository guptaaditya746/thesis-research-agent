# Evaluation of run rag-claude-small-distributed on rag-claude-small-5cbb2530

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 30      | 34      | 30        | 1.000       | 0.882    | 0.938 | 0.933           |
| all             | all         | 30      | 34      | 30        | 1.000       | 0.882    | 0.938 | 0.933           |
| author_claim    | distributed | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 10      | 12      | 10        | 1.000       | 0.833    | 0.909 | 0.800           |
| condition       | all         | 10      | 12      | 10        | 1.000       | 0.833    | 0.909 | 0.800           |
| measurement     | distributed | 10      | 12      | 10        | 1.000       | 0.833    | 0.909 | 1.000           |
| measurement     | all         | 10      | 12      | 10        | 1.000       | 0.833    | 0.909 | 1.000           |
| metric          | distributed | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all         | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 4; items matching no fact: 0.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 10                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 5         | 1.000       |
| all         | 10                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 5         | 1.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 5         | 5            | 0.800                | 0.800          | 1.000               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| distributed | agent-baseline  | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed | evidence-engine | 5         | 5            | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed | rag-baseline    | 5         | 5            | 0.800                | 0.800          | 1.000               | 1.000          | 1.000     |

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
| condition       | 0.909 [0.71, 1.00] | BCa      |
| metric          | 1.000 [n/a]        | -        |
| measurement     | 0.909 [0.71, 1.00] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.938 [0.79, 1.00] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               | -          |
| rag-baseline    | 0.800 [0.20, 1.00]   | BCa      | 0.200 [0.00, 0.80]    | BCa             | 5          |
| agent-baseline  | 1.000 [n/a]          | -        | 0.000 [n/a]           | -               | 5          |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | distributed | 118          | 118      | 1.000    |
| all             | all         | 118          | 118      | 1.000    |
| author_claim    | distributed | 10           | 10       | 1.000    |
| author_claim    | all         | 10           | 10       | 1.000    |
| condition       | distributed | 69           | 69       | 1.000    |
| condition       | all         | 69           | 69       | 1.000    |
| measurement     | distributed | 12           | 12       | 1.000    |
| measurement     | all         | 12           | 12       | 1.000    |
| metric          | distributed | 27           | 27       | 1.000    |
| metric          | all         | 27           | 27       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| agentic@1#0f2927b8a64c            | 0       | 0               | 0      | 0              |
| agentic@1#534f8c43c9f0            | 0       | 0               | 0      | 0              |
| agentic@1#5eefe3bb3cec            | 0       | 0               | 0      | 0              |
| agentic@1#6d79f0c0b881            | 0       | 0               | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 2       | 2               | 1      | 1              |
| llm_measurement@1#73fb3d141605    | 10      | 10              | 10     | 10             |
| llm_metric@1#41e1e53a1fc4         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | 5       | 5               | 5      | 5              |
| regex_condition@2#0a5bf730763c    | 9       | 9               | 8      | 8              |
| regex_measurement@2#5388637fb767  | 0       | 0               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 3       | 3               | 3      | 3              |

Facts no extractor found: condition 2, measurement 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| agentic@1#0f2927b8a64c            | all             | all     | 0       | 34      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| agentic@1#534f8c43c9f0            | all             | all     | 0       | 34      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| agentic@1#5eefe3bb3cec            | all             | all     | 0       | 34      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| agentic@1#6d79f0c0b881            | all             | all     | 0       | 34      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 34      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| llm_condition@1#45b3761c700e      | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| llm_measurement@1#73fb3d141605    | measurement     | all     | 10      | 12      | 10        | 1.000       | 0.833    | 0.909 | 1.000           | 1.000                  | 10     | 10             |
| llm_measurement@1#73fb3d141605    | all             | all     | 10      | 12      | 10        | 1.000       | 0.833    | 0.909 | 1.000           | -                      | 10     | 10             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 5      | 5              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 5      | 5              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 9       | 12      | 9         | 1.000       | 0.750    | 0.857 | 0.778           | -                      | 8      | 8              |
| regex_condition@2#0a5bf730763c    | all             | all     | 9       | 12      | 9         | 1.000       | 0.750    | 0.857 | 0.778           | -                      | 8      | 8              |
| regex_measurement@2#5388637fb767  | measurement     | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#5388637fb767  | all             | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 3       | 5       | 3         | 1.000       | 0.600    | 0.750 | 1.000           | -                      | 3      | 3              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 3       | 5       | 3         | 1.000       | 0.600    | 0.750 | 1.000           | -                      | 3      | 3              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 1       | 2             | 2439           | 250             | 7.582     |
| llm_measurement@1#73fb3d141605    | 5       | 10            | 13805          | 1704            | 51.210    |
| llm_metric@1#41e1e53a1fc4         | 2       | 2             | 2627           | 214             | 6.730     |
| llm_screen@1#41b0d6e6793f         | 5       | 5             | 5167           | 501             | 0.036     |
| regex_author_claim@2#fd7877790c48 | 5       | 0             | 0              | 0               | 0.035     |
| regex_condition@2#0a5bf730763c    | 5       | 0             | 0              | 0               | 0.037     |
| regex_measurement@2#5388637fb767  | 5       | 0             | 0              | 0               | 0.086     |
| regex_metric@2#0affe2d9ce77       | 5       | 0             | 0              | 0               | 0.035     |
| regex_screen@1#858a6ebc69c6       | 5       | 0             | 0              | 0               | 0.038     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 25      | 5.000       |
| calls            | 38      | 7.600       |
| input_tokens     | 24038   | 4807.600    |
| made_model_calls | 14      | 2.800       |
| model_calls      | 19      | 3.800       |
| output_tokens    | 2669    | 533.800     |
| seconds          | 66.149  | 13.230      |

## Funnel

Strategy `gaps` over 5 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.600          |
| model_calls   | 3.800          |
| input_tokens  | 4807.600       |
| output_tokens | 533.800        |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 5           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 5           | 5    | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
