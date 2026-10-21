# Evaluation of run rag-llm-small-distributed on rag-llm-small-bd3f74c0

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | distributed | 6       | 10      | 6         | 1.000       | 0.600    | 0.750 | 0.833           |
| all             | all         | 6       | 10      | 6         | 1.000       | 0.600    | 0.750 | 0.833           |
| author_claim    | distributed | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 0.500           |
| condition       | all         | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 0.500           |
| measurement     | distributed | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 1.000           |
| measurement     | all         | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 1.000           |
| metric          | distributed | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all         | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 4; items matching no fact: 0.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| distributed | 2                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 1         | 1.000       |
| all         | 2                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 1         | 1.000       |

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
| condition       | 0.667 [n/a] | -        |
| metric          | 1.000 [n/a] | -        |
| measurement     | 0.667 [n/a] | -        |
| author_claim    | 1.000 [n/a] | -        |
| all             | 0.750 [n/a] | -        |

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
| agentic@1#0f2927b8a64c            | 0       | 0               | 0      | 0              |
| agentic@1#534f8c43c9f0            | 0       | 0               | 0      | 0              |
| agentic@1#5eefe3bb3cec            | 0       | 0               | 0      | 0              |
| agentic@1#6d79f0c0b881            | 0       | 0               | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | 0       | 0               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 0       | 0               | 0      | 0              |
| llm_measurement@1#31b14e5f404d    | 2       | 2               | 2      | 2              |
| llm_metric@1#1ca12a572ef8         | 1       | 1               | 1      | 1              |
| regex_author_claim@2#b2161f228a8c | 1       | 1               | 1      | 1              |
| regex_condition@2#80486860164a    | 2       | 2               | 2      | 2              |
| regex_measurement@2#a70020d1afcc  | 0       | 0               | 0      | 0              |
| regex_metric@2#67f41f33eff7       | 0       | 0               | 0      | 0              |

Facts no extractor found: condition 2, measurement 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| agentic@1#0f2927b8a64c            | all             | all     | 0       | 10      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| agentic@1#534f8c43c9f0            | all             | all     | 0       | 10      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| agentic@1#5eefe3bb3cec            | all             | all     | 0       | 10      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| agentic@1#6d79f0c0b881            | all             | all     | 0       | 10      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 0       | 10      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | all             | all     | 0       | 10      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_measurement@1#31b14e5f404d    | measurement     | all     | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 1.000           | 1.000                  | 2      | 2              |
| llm_measurement@1#31b14e5f404d    | all             | all     | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| regex_condition@2#80486860164a    | condition       | all     | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 0.500           | -                      | 2      | 2              |
| regex_condition@2#80486860164a    | all             | all     | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 0.500           | -                      | 2      | 2              |
| regex_measurement@2#a70020d1afcc  | measurement     | all     | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#a70020d1afcc  | all             | all     | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#67f41f33eff7       | all             | all     | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_measurement@1#31b14e5f404d    | 1       | 2             | 2609           | 332             | 8.995     |
| llm_metric@1#1ca12a572ef8         | 1       | 1             | 1220           | 99              | 3.901     |
| llm_screen@1#6bec6abaf6a0         | 1       | 1             | 950            | 85              | 0.007     |
| regex_author_claim@2#b2161f228a8c | 1       | 0             | 0              | 0               | 0.007     |
| regex_condition@2#80486860164a    | 1       | 0             | 0              | 0               | 0.007     |
| regex_measurement@2#a70020d1afcc  | 1       | 0             | 0              | 0               | 0.022     |
| regex_metric@2#67f41f33eff7       | 1       | 0             | 0              | 0               | 0.007     |
| regex_screen@1#8301b6896dc3       | 1       | 0             | 0              | 0               | 0.006     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 5       | 5.000       |
| calls            | 8       | 8.000       |
| input_tokens     | 4779    | 4779.000    |
| made_model_calls | 3       | 3.000       |
| model_calls      | 4       | 4.000       |
| output_tokens    | 516     | 516.000     |
| seconds          | 13.042  | 13.042      |

## Funnel

Strategy `gaps` over 1 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 8.000          |
| model_calls   | 4.000          |
| input_tokens  | 4779.000       |
| output_tokens | 516.000        |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 1           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 1           | 1    | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
