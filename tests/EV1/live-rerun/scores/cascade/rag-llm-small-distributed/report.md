# Evaluation of run rag-llm-small-distributed on rag-llm-small-bd3f74c0

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 11      | 10      | 10        | 0.909       | 1.000    | 0.952 | 1.000           |
| all             | all         | 11      | 10      | 10        | 0.909       | 1.000    | 0.952 | 1.000           |
| author_claim    | distributed | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| condition       | all         | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| measurement     | distributed | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | all         | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | distributed | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all         | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 0; items matching no fact: 1.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 4                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 1         | 1.000       |
| all         | 4                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 1         | 1.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | refuted | refuted    | yes             | 1         | yes          | 1.000                | 1.000          | 1.000               | -              |
| rag-baseline    | refuted | refuted    | yes             | 1         | yes          | 1.000                | 1.000          | 1.000               | 1.000          |
| agent-baseline  | refuted | refuted    | yes             | 1         | yes          | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| distributed | agent-baseline  | 1         | yes          | 1.000                | 1.000          | 1.000               | -              |
| distributed | evidence-engine | 1         | yes          | 1.000                | 1.000          | 1.000               | -              |
| distributed | rag-baseline    | 1         | yes          | 1.000                | 1.000          | 1.000               | 1.000          |

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

| evidence_type   | f1          | method   |
|-----------------|-------------|----------|
| condition       | 0.889 [n/a] | -        |
| metric          | 1.000 [n/a] | -        |
| measurement     | 1.000 [n/a] | -        |
| author_claim    | 1.000 [n/a] | -        |
| all             | 0.952 [n/a] | -        |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |
| rag-baseline    | 1.000 [n/a]          | -        | 0.000 [n/a]           | -               |
| agent-baseline  | 1.000 [n/a]          | -        | 0.000 [n/a]           | -               |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | distributed | 43           | 43       | 1.000    |
| all             | all         | 43           | 43       | 1.000    |
| author_claim    | distributed | 2            | 2        | 1.000    |
| author_claim    | all         | 2            | 2        | 1.000    |
| condition       | distributed | 30           | 30       | 1.000    |
| condition       | all         | 30           | 30       | 1.000    |
| measurement     | distributed | 4            | 4        | 1.000    |
| measurement     | all         | 4            | 4        | 1.000    |
| metric          | distributed | 7            | 7        | 1.000    |
| metric          | all         | 7            | 7        | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 1       | 1               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 4       | 4               | 3      | 3              |
| llm_measurement@1#5212fc43026f    | 4       | 4               | 4      | 4              |
| llm_metric@1#1ca12a572ef8         | 1       | 1               | 1      | 1              |
| regex_author_claim@2#b2161f228a8c | 1       | 1               | 0      | 0              |
| regex_condition@2#80486860164a    | 2       | 1               | 1      | 0              |
| regex_measurement@2#9edb306c5b05  | 0       | 0               | 0      | 0              |
| regex_metric@2#67f41f33eff7       | 0       | 0               | 0      | 0              |

Facts no extractor found: none

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 3      | 3              |
| llm_condition@1#134ab1a38338      | all             | all     | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 3      | 3              |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           | 1.000                  | 4      | 4              |
| llm_measurement@1#5212fc43026f    | all             | all     | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 4      | 4              |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 2       | 4       | 1         | 0.500       | 0.250    | 0.333 | 1.000           | -                      | 1      | 0              |
| regex_condition@2#80486860164a    | all             | all     | 2       | 4       | 1         | 0.500       | 0.250    | 0.333 | 1.000           | -                      | 1      | 0              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#67f41f33eff7       | all             | all     | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 1       | 1             | 1061           | 121             | 3.347     |
| llm_condition@1#134ab1a38338      | 1       | 1             | 1139           | 242             | 6.272     |
| llm_measurement@1#5212fc43026f    | 1       | 2             | 2743           | 576             | 14.867    |
| llm_metric@1#1ca12a572ef8         | 1       | 1             | 1165           | 99              | 2.853     |
| llm_screen@1#6bec6abaf6a0         | 1       | 1             | 950            | 85              | 3.272     |
| regex_author_claim@2#b2161f228a8c | 1       | 0             | 0              | 0               | 0.023     |
| regex_condition@2#80486860164a    | 1       | 0             | 0              | 0               | 0.020     |
| regex_measurement@2#9edb306c5b05  | 1       | 0             | 0              | 0               | 0.020     |
| regex_metric@2#67f41f33eff7       | 1       | 0             | 0              | 0               | 0.018     |
| regex_screen@1#8301b6896dc3       | 1       | 0             | 0              | 0               | 0.026     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 10      | 10.000      |
| input_tokens     | 7058    | 7058.000    |
| made_model_calls | 6       | 6.000       |
| model_calls      | 6       | 6.000       |
| output_tokens    | 1123    | 1123.000    |
| seconds          | 30.805  | 30.805      |

## Funnel

Strategy `all` over 1 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.000          |
| input_tokens  | 7058.000       |
| output_tokens | 1123.000       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 1           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 1           | 1    | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
