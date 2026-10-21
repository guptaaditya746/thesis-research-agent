# Evaluation of run rag-tpl-s1-explicit on rag-tpl-s1-59c5118b

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: explicit

## A. Extraction

| evidence_type   | level    | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|----------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit | 177     | 162     | 161       | 0.910       | 0.994    | 0.950 | 1.000           |
| all             | all      | 177     | 162     | 161       | 0.910       | 0.994    | 0.950 | 1.000           |
| author_claim    | explicit | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all      | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit | 66      | 61      | 60        | 0.909       | 0.984    | 0.945 | 1.000           |
| condition       | all      | 66      | 61      | 60        | 0.909       | 0.984    | 0.945 | 1.000           |
| measurement     | explicit | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| measurement     | all      | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| metric          | explicit | 25      | 20      | 20        | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | all      | 25      | 20      | 20        | 0.800       | 1.000    | 0.889 | 1.000           |

Facts no item matched: 1; items matching no fact: 16.

## B. Integration

| level    | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|----------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit | 61                     | 0.984                  | 0.984                     | 1.000             | 0.951             | 0.934          | 20        | 0.750       |
| all      | 61                     | 0.984                  | 0.984                     | 1.000             | 0.951             | 0.934          | 20        | 0.750       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level    | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|----------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

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
| condition       | 0.945 [0.88, 0.98] | BCa      |
| metric          | 0.889 [0.80, 0.95] | BCa      |
| measurement     | 0.961 [0.93, 0.98] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.950 [0.91, 0.97] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |

## Locate recall

| evidence_type   | level    | placements   | inside   | recall   |
|-----------------|----------|--------------|----------|----------|
| all             | explicit | 364          | 364      | 1.000    |
| all             | all      | 364          | 364      | 1.000    |
| author_claim    | explicit | 40           | 40       | 1.000    |
| author_claim    | all      | 40           | 40       | 1.000    |
| condition       | explicit | 162          | 162      | 1.000    |
| condition       | all      | 162          | 162      | 1.000    |
| measurement     | explicit | 61           | 61       | 1.000    |
| measurement     | all      | 61           | 61       | 1.000    |
| metric          | explicit | 101          | 101      | 1.000    |
| metric          | all      | 101          | 101      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 20      | 20              | 0      | 0              |
| llm_condition@1#134ab1a38338      | 61      | 60              | 38     | 37             |
| llm_measurement@1#5212fc43026f    | 61      | 56              | 53     | 48             |
| llm_metric@1#1ca12a572ef8         | 20      | 20              | 7      | 7              |
| regex_author_claim@2#b2161f228a8c | 20      | 20              | 0      | 0              |
| regex_condition@2#80486860164a    | 28      | 23              | 5      | 0              |
| regex_measurement@2#9edb306c5b05  | 13      | 13              | 5      | 5              |
| regex_metric@2#67f41f33eff7       | 18      | 13              | 5      | 0              |

Facts no extractor found: condition 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | -                      | 38     | 37             |
| llm_condition@1#134ab1a38338      | all             | all     | 61      | 61      | 60        | 0.984       | 0.984    | 0.984 | 1.000           | -                      | 38     | 37             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 61      | 61      | 56        | 0.918       | 0.918    | 0.918 | 1.000           | 0.982                  | 53     | 48             |
| llm_measurement@1#5212fc43026f    | all             | all     | 61      | 61      | 56        | 0.918       | 0.918    | 0.918 | 1.000           | -                      | 53     | 48             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_condition@2#80486860164a    | all             | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | 1.000                  | 5      | 5              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 13      | 61      | 13        | 1.000       | 0.213    | 0.351 | 1.000           | -                      | 5      | 5              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |
| regex_metric@2#67f41f33eff7       | all             | all     | 18      | 20      | 13        | 0.722       | 0.650    | 0.684 | 1.000           | -                      | 5      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 20      | 20            | 15810          | 2374            | 63.775    |
| llm_condition@1#134ab1a38338      | 20      | 37            | 32201          | 6171            | 161.415   |
| llm_measurement@1#5212fc43026f    | 20      | 40            | 45880          | 12354           | 314.534   |
| llm_metric@1#1ca12a572ef8         | 20      | 21            | 18682          | 1890            | 53.466    |
| llm_screen@1#6bec6abaf6a0         | 20      | 20            | 13590          | 1365            | 38.940    |
| regex_author_claim@2#b2161f228a8c | 20      | 0             | 0              | 0               | 0.142     |
| regex_condition@2#80486860164a    | 20      | 0             | 0              | 0               | 0.144     |
| regex_measurement@2#9edb306c5b05  | 20      | 0             | 0              | 0               | 0.306     |
| regex_metric@2#67f41f33eff7       | 20      | 0             | 0              | 0               | 0.142     |
| regex_screen@1#8301b6896dc3       | 20      | 0             | 0              | 0               | 0.149     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 80      | 4.000       |
| calls            | 200     | 10.000      |
| input_tokens     | 126163  | 6308.150    |
| made_model_calls | 138     | 6.900       |
| model_calls      | 138     | 6.900       |
| output_tokens    | 24154   | 1207.700    |
| seconds          | 634.297 | 31.715      |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.900          |
| input_tokens  | 6308.150       |
| output_tokens | 1207.700       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
