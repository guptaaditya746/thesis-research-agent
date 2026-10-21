# Evaluation of run rag-tpl-s1-contradictory on rag-tpl-s1-56b0bc02

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 200     | 162     | 162       | 0.810       | 1.000    | 0.895 | 1.000           |
| all             | all           | 200     | 162     | 162       | 0.810       | 1.000    | 0.895 | 1.000           |
| author_claim    | contradictory | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| condition       | all           | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| measurement     | contradictory | 89      | 61      | 61        | 0.685       | 1.000    | 0.813 | 1.000           |
| measurement     | all           | 89      | 61      | 61        | 0.685       | 1.000    | 0.813 | 1.000           |
| metric          | contradictory | 25      | 20      | 20        | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | all           | 25      | 20      | 20        | 0.800       | 1.000    | 0.889 | 1.000           |

Facts no item matched: 0; items matching no fact: 38.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 61                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.836          | 20        | 0.750       |
| all           | 61                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.836          | 20        | 0.750       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| contradictory | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 20   | 0    | 0    | 1.000       | 1.000    |
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
| condition       | 0.961 [0.93, 0.98] | BCa      |
| metric          | 0.889 [0.80, 0.95] | BCa      |
| measurement     | 0.813 [0.73, 0.88] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.895 [0.84, 0.93] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | contradictory | 343          | 343      | 1.000    |
| all             | all           | 343          | 343      | 1.000    |
| author_claim    | contradictory | 40           | 40       | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
| condition       | contradictory | 172          | 172      | 1.000    |
| condition       | all           | 172          | 172      | 1.000    |
| measurement     | contradictory | 61           | 61       | 1.000    |
| measurement     | all           | 61           | 61       | 1.000    |
| metric          | contradictory | 70           | 70       | 1.000    |
| metric          | all           | 70           | 70       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 20      | 20              | 0      | 0              |
| llm_condition@1#134ab1a38338      | 61      | 61              | 38     | 38             |
| llm_measurement@1#5212fc43026f    | 71      | 51              | 29     | 13             |
| llm_metric@1#1ca12a572ef8         | 20      | 20              | 7      | 7              |
| regex_author_claim@2#b2161f228a8c | 20      | 20              | 0      | 0              |
| regex_condition@2#80486860164a    | 28      | 23              | 5      | 0              |
| regex_measurement@2#9edb306c5b05  | 60      | 48              | 18     | 10             |
| regex_metric@2#67f41f33eff7       | 18      | 13              | 5      | 0              |

Facts no extractor found: none

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| llm_condition@1#134ab1a38338      | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 71      | 61      | 51        | 0.718       | 0.836    | 0.773 | 1.000           | 1.000                  | 29     | 13             |
| llm_measurement@1#5212fc43026f    | all             | all     | 71      | 61      | 51        | 0.718       | 0.836    | 0.773 | 1.000           | -                      | 29     | 13             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_condition@2#80486860164a    | all             | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 60      | 61      | 48        | 0.800       | 0.787    | 0.793 | 1.000           | 1.000                  | 18     | 10             |
| regex_measurement@2#9edb306c5b05  | all             | all     | 60      | 61      | 48        | 0.800       | 0.787    | 0.793 | 1.000           | -                      | 18     | 10             |
| regex_metric@2#67f41f33eff7       | metric          | all     | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| regex_metric@2#67f41f33eff7       | all             | all     | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 20      | 20            | 16389          | 2362            | 63.863    |
| llm_condition@1#134ab1a38338      | 20      | 40            | 36417          | 6572            | 172.767   |
| llm_measurement@1#5212fc43026f    | 20      | 40            | 44304          | 11391           | 290.913   |
| llm_metric@1#1ca12a572ef8         | 20      | 29            | 25680          | 2218            | 64.076    |
| llm_screen@1#6bec6abaf6a0         | 20      | 20            | 14169          | 1434            | 40.818    |
| regex_author_claim@2#b2161f228a8c | 20      | 0             | 0              | 0               | 0.140     |
| regex_condition@2#80486860164a    | 20      | 0             | 0              | 0               | 0.140     |
| regex_measurement@2#9edb306c5b05  | 20      | 0             | 0              | 0               | 0.319     |
| regex_metric@2#67f41f33eff7       | 20      | 0             | 0              | 0               | 0.137     |
| regex_screen@1#8301b6896dc3       | 20      | 0             | 0              | 0               | 0.142     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 80      | 4.000       |
| calls            | 200     | 10.000      |
| input_tokens     | 136959  | 6847.950    |
| made_model_calls | 149     | 7.450       |
| model_calls      | 149     | 7.450       |
| output_tokens    | 23977   | 1198.850    |
| seconds          | 634.572 | 31.729      |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 7.450          |
| input_tokens  | 6847.950       |
| output_tokens | 1198.850       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 19   | 0    | 1    | 0    | 1.000       | 0.950    |

Screened out wrongly: S013
