# Evaluation of run rag-llm-s1-contradictory on rag-llm-s1-c1d18224

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 85      | 88      | 67        | 0.788       | 0.761    | 0.775 | 0.955           |
| all             | all           | 85      | 88      | 67        | 0.788       | 0.761    | 0.775 | 0.955           |
| author_claim    | contradictory | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 24      | 33      | 23        | 0.958       | 0.697    | 0.807 | 0.870           |
| condition       | all           | 24      | 33      | 23        | 0.958       | 0.697    | 0.807 | 0.870           |
| measurement     | contradictory | 27      | 33      | 22        | 0.815       | 0.667    | 0.733 | 1.000           |
| measurement     | all           | 27      | 33      | 22        | 0.815       | 0.667    | 0.733 | 1.000           |
| metric          | contradictory | 23      | 11      | 11        | 0.478       | 1.000    | 0.647 | 1.000           |
| metric          | all           | 23      | 11      | 11        | 0.478       | 1.000    | 0.647 | 1.000           |

Facts no item matched: 21; items matching no fact: 18.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 22                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.909          | 11        | 0.909       |
| all           | 22                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.909          | 11        | 0.909       |

## C. Synthesis

| system          | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed     | mixed      | yes             | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |
| rag-baseline    | supported | mixed      | no              | 11        | 11           | 0.182                | 0.545          | 0.333               | 1.000          |
| agent-baseline  | mixed     | mixed      | yes             | 11        | 11           | 0.727                | 1.000          | 0.727               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| contradictory | agent-baseline  | 11        | 11           | 0.727                | 1.000          | 0.727               | -              |
| contradictory | evidence-engine | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |
| contradictory | rag-baseline    | 11        | 11           | 0.182                | 0.545          | 0.333               | 1.000          |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 10   | 0    | 1    | 1.000       | 0.909    |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.807 [0.73, 0.90] | BCa      |
| metric          | 0.647 [0.54, 0.76] | BCa      |
| measurement     | 0.733 [0.65, 0.85] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.775 [0.73, 0.84] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.909 [0.59, 1.00]   | BCa      | -                     | -               |
| rag-baseline    | 0.182 [0.00, 0.45]   | BCa      | 0.727 [0.18, 1.00]    | BCa             |
| agent-baseline  | 0.727 [0.36, 0.91]   | BCa      | 0.182 [-0.18, 0.55]   | BCa             |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | contradictory | 304          | 304      | 1.000    |
| all             | all           | 304          | 304      | 1.000    |
| author_claim    | contradictory | 22           | 22       | 1.000    |
| author_claim    | all           | 22           | 22       | 1.000    |
| condition       | contradictory | 173          | 173      | 1.000    |
| condition       | all           | 173          | 173      | 1.000    |
| measurement     | contradictory | 33           | 33       | 1.000    |
| measurement     | all           | 33           | 33       | 1.000    |
| metric          | contradictory | 76           | 76       | 1.000    |
| metric          | all           | 76           | 76       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 0       | 0               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 7       | 7               | 7      | 7              |
| llm_measurement@1#5212fc43026f    | 16      | 15              | 12     | 12             |
| llm_metric@1#1ca12a572ef8         | 1       | 1               | 1      | 1              |
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 11     | 11             |
| regex_condition@2#80486860164a    | 17      | 16              | 17     | 16             |
| regex_measurement@2#9edb306c5b05  | 15      | 10              | 11     | 7              |
| regex_metric@2#67f41f33eff7       | 22      | 10              | 22     | 10             |

Facts no extractor found: condition 10, measurement 11

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | all             | all     | 0       | 88      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 7       | 14      | 7         | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 7      | 7              |
| llm_condition@1#134ab1a38338      | all             | all     | 7       | 14      | 7         | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 7      | 7              |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 16      | 21      | 15        | 0.938       | 0.714    | 0.811 | 1.000           | 1.000                  | 12     | 12             |
| llm_measurement@1#5212fc43026f    | all             | all     | 16      | 21      | 15        | 0.938       | 0.714    | 0.811 | 1.000           | -                      | 12     | 12             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_condition@2#80486860164a    | condition       | all     | 17      | 33      | 16        | 0.941       | 0.485    | 0.640 | 0.812           | -                      | 17     | 16             |
| regex_condition@2#80486860164a    | all             | all     | 17      | 33      | 16        | 0.941       | 0.485    | 0.640 | 0.812           | -                      | 17     | 16             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 15      | 33      | 10        | 0.667       | 0.303    | 0.417 | 1.000           | 1.000                  | 11     | 7              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 15      | 33      | 10        | 0.667       | 0.303    | 0.417 | 1.000           | -                      | 11     | 7              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 22      | 11      | 10        | 0.455       | 0.909    | 0.606 | 1.000           | -                      | 22     | 10             |
| regex_metric@2#67f41f33eff7       | all             | all     | 22      | 11      | 10        | 0.455       | 0.909    | 0.606 | 1.000           | -                      | 22     | 10             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#134ab1a38338      | 5       | 10            | 12611          | 808             | 25.069    |
| llm_measurement@1#5212fc43026f    | 7       | 14            | 21321          | 2956            | 79.122    |
| llm_metric@1#1ca12a572ef8         | 1       | 1             | 1280           | 96              | 2.822     |
| llm_screen@1#6bec6abaf6a0         | 11      | 11            | 11472          | 922             | 0.071     |
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.072     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.073     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.072     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.074     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.073     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 66      | 6.000       |
| calls            | 79      | 7.182       |
| input_tokens     | 46684   | 4244.000    |
| made_model_calls | 25      | 2.273       |
| model_calls      | 36      | 3.273       |
| output_tokens    | 4782    | 434.727     |
| seconds          | 108.106 | 9.828       |

## Funnel

Strategy `gaps` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.182          |
| model_calls   | 3.273          |
| input_tokens  | 4244.000       |
| output_tokens | 434.727        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 4           |
| 1               | 7           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
