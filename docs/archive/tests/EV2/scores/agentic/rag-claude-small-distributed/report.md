# Evaluation of run rag-claude-small-distributed on rag-claude-small-5cbb2530

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 47      | 34      | 34        | 0.723       | 1.000    | 0.840 | 1.000           |
| all             | all         | 47      | 34      | 34        | 0.723       | 1.000    | 0.840 | 1.000           |
| author_claim    | distributed | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 19      | 12      | 12        | 0.632       | 1.000    | 0.774 | 1.000           |
| condition       | all         | 19      | 12      | 12        | 0.632       | 1.000    | 0.774 | 1.000           |
| measurement     | distributed | 13      | 12      | 12        | 0.923       | 1.000    | 0.960 | 1.000           |
| measurement     | all         | 13      | 12      | 12        | 0.923       | 1.000    | 0.960 | 1.000           |
| metric          | distributed | 10      | 5       | 5         | 0.500       | 1.000    | 0.667 | 1.000           |
| metric          | all         | 10      | 5       | 5         | 0.500       | 1.000    | 0.667 | 1.000           |

Facts no item matched: 0; items matching no fact: 13.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 12                     | 1.000                  | 1.000                     | 1.000             | 0.750             | 0.500          | 5         | 0.800       |
| all         | 12                     | 1.000                  | 1.000                     | 1.000             | 0.750             | 0.500          | 5         | 0.800       |

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
| condition       | 0.774 [0.62, 0.94] | BCa      |
| metric          | 0.667 [0.56, 0.83] | BCa      |
| measurement     | 0.960 [0.87, 1.00] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.840 [0.74, 0.95] | BCa      |

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
| agentic@1#0f2927b8a64c            | 2       | 0               | 2      | 0              |
| agentic@1#534f8c43c9f0            | 3       | 0               | 3      | 0              |
| agentic@1#5eefe3bb3cec            | 1       | 1               | 0      | 0              |
| agentic@1#6d79f0c0b881            | 8       | 8               | 1      | 1              |
| llm_author_claim@1#be3c17081ff9   | 5       | 5               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 12      | 12              | 8      | 8              |
| llm_measurement@1#73fb3d141605    | 12      | 11              | 5      | 4              |
| llm_metric@1#41e1e53a1fc4         | 5       | 5               | 4      | 4              |
| regex_author_claim@2#fd7877790c48 | 5       | 5               | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 9       | 4               | 5      | 0              |
| regex_measurement@2#5388637fb767  | 0       | 0               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 3       | 1               | 2      | 0              |

Facts no extractor found: none

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| agentic@1#0f2927b8a64c            | condition       | all     | 2       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 2      | 0              |
| agentic@1#0f2927b8a64c            | all             | all     | 2       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 2      | 0              |
| agentic@1#534f8c43c9f0            | metric          | all     | 3       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 3      | 0              |
| agentic@1#534f8c43c9f0            | all             | all     | 3       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 3      | 0              |
| agentic@1#5eefe3bb3cec            | author_claim    | all     | 1       | 5       | 1         | 1.000       | 0.200    | 0.333 | 1.000           | -                      | 0      | 0              |
| agentic@1#5eefe3bb3cec            | all             | all     | 1       | 5       | 1         | 1.000       | 0.200    | 0.333 | 1.000           | -                      | 0      | 0              |
| agentic@1#6d79f0c0b881            | measurement     | all     | 8       | 12      | 8         | 1.000       | 0.667    | 0.800 | 1.000           | 1.000                  | 1      | 1              |
| agentic@1#6d79f0c0b881            | all             | all     | 8       | 12      | 8         | 1.000       | 0.667    | 0.800 | 1.000           | -                      | 1      | 1              |
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 8      | 8              |
| llm_condition@1#45b3761c700e      | all             | all     | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 8      | 8              |
| llm_measurement@1#73fb3d141605    | measurement     | all     | 12      | 12      | 11        | 0.917       | 0.917    | 0.917 | 1.000           | 1.000                  | 5      | 4              |
| llm_measurement@1#73fb3d141605    | all             | all     | 12      | 12      | 11        | 0.917       | 0.917    | 0.917 | 1.000           | -                      | 5      | 4              |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 4      | 4              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 4      | 4              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 9       | 12      | 4         | 0.444       | 0.333    | 0.381 | 1.000           | -                      | 5      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 9       | 12      | 4         | 0.444       | 0.333    | 0.381 | 1.000           | -                      | 5      | 0              |
| regex_measurement@2#5388637fb767  | measurement     | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#5388637fb767  | all             | all     | 0       | 12      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 3       | 5       | 1         | 0.333       | 0.200    | 0.250 | 1.000           | -                      | 2      | 0              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 3       | 5       | 1         | 0.333       | 0.200    | 0.250 | 1.000           | -                      | 2      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| agentic@1#0f2927b8a64c            | 5       | 72            | 611107         | 27902           | 840.926   |
| agentic@1#534f8c43c9f0            | 5       | 96            | 793080         | 29262           | 847.381   |
| agentic@1#5eefe3bb3cec            | 5       | 50            | 241576         | 12916           | 411.342   |
| agentic@1#6d79f0c0b881            | 5       | 88            | 803942         | 43951           | 1434.409  |
| llm_author_claim@1#be3c17081ff9   | 5       | 5             | 5722           | 597             | 16.746    |
| llm_condition@1#45b3761c700e      | 5       | 6             | 7259           | 1045            | 27.994    |
| llm_measurement@1#73fb3d141605    | 5       | 10            | 14043          | 2020            | 54.726    |
| llm_metric@1#41e1e53a1fc4         | 5       | 5             | 6242           | 494             | 14.384    |
| llm_screen@1#41b0d6e6793f         | 5       | 5             | 5167           | 501             | 15.863    |
| regex_author_claim@2#fd7877790c48 | 5       | 0             | 0              | 0               | 0.084     |
| regex_condition@2#0a5bf730763c    | 5       | 0             | 0              | 0               | 0.065     |
| regex_measurement@2#5388637fb767  | 5       | 0             | 0              | 0               | 0.088     |
| regex_metric@2#0affe2d9ce77       | 5       | 0             | 0              | 0               | 0.065     |
| regex_screen@1#858a6ebc69c6       | 5       | 0             | 0              | 0               | 0.066     |

## Cost

| measure          | total    | per_paper   |
|------------------|----------|-------------|
| cached_calls     | 3        | 0.600       |
| calls            | 70       | 14.000      |
| input_tokens     | 2488138  | 497627.600  |
| made_model_calls | 337      | 67.400      |
| model_calls      | 337      | 67.400      |
| output_tokens    | 118688   | 23737.600   |
| seconds          | 3664.568 | 732.914     |

## Re-execution stability

| extractor          | calls   | identical   | identical_share   | item_stability   |
|--------------------|---------|-------------|-------------------|------------------|
| agentic            | 20      | 11          | 0.550             | 0.500            |
| llm_author_claim   | 5       | 5           | 1.000             | 1.000            |
| llm_condition      | 5       | 5           | 1.000             | 1.000            |
| llm_measurement    | 5       | 2           | 0.400             | 0.333            |
| llm_metric         | 5       | 5           | 1.000             | 1.000            |
| llm_screen         | 5       | 5           | 1.000             | 1.000            |
| regex_author_claim | 5       | 5           | 1.000             | 1.000            |
| regex_condition    | 5       | 5           | 1.000             | 1.000            |
| regex_measurement  | 5       | 5           | 1.000             | -                |
| regex_metric       | 5       | 5           | 1.000             | 1.000            |
| regex_screen       | 5       | 5           | 1.000             | 1.000            |

## Funnel

Strategy `all` over 5 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 14.000         |
| model_calls   | 67.400         |
| input_tokens  | 497627.600     |
| output_tokens | 23737.600      |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 5           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 5           | 5    | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
