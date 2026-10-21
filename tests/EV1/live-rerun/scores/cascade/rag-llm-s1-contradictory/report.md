# Evaluation of run rag-llm-s1-contradictory on rag-llm-s1-c1d18224

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 129     | 88      | 85        | 0.659       | 0.966    | 0.783 | 1.000           |
| all             | all           | 129     | 88      | 85        | 0.659       | 0.966    | 0.783 | 1.000           |
| author_claim    | contradictory | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 41      | 33      | 30        | 0.732       | 0.909    | 0.811 | 1.000           |
| condition       | all           | 41      | 33      | 30        | 0.732       | 0.909    | 0.811 | 1.000           |
| measurement     | contradictory | 50      | 33      | 33        | 0.660       | 1.000    | 0.795 | 1.000           |
| measurement     | all           | 50      | 33      | 33        | 0.660       | 1.000    | 0.795 | 1.000           |
| metric          | contradictory | 27      | 11      | 11        | 0.407       | 1.000    | 0.579 | 1.000           |
| metric          | all           | 27      | 11      | 11        | 0.407       | 1.000    | 0.579 | 1.000           |

Facts no item matched: 3; items matching no fact: 44.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 33                     | 0.909                  | 0.909                     | 1.000             | 0.909             | 0.818          | 11        | 0.727       |
| all           | 33                     | 0.909                  | 0.909                     | 1.000             | 0.909             | 0.818          | 11        | 0.727       |

## C. Synthesis

| system          | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed     | mixed      | yes             | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| rag-baseline    | supported | mixed      | no              | 11        | 11           | 0.182                | 0.545          | 0.333               | 1.000          |
| agent-baseline  | mixed     | mixed      | yes             | 11        | 11           | 0.727                | 1.000          | 0.727               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| contradictory | agent-baseline  | 11        | 11           | 0.727                | 1.000          | 0.727               | -              |
| contradictory | evidence-engine | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| contradictory | rag-baseline    | 11        | 11           | 0.182                | 0.545          | 0.333               | 1.000          |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 11   | 0    | 0    | 1.000       | 1.000    |
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
| condition       | 0.811 [0.66, 0.89] | BCa      |
| metric          | 0.579 [0.47, 0.69] | BCa      |
| measurement     | 0.795 [0.68, 0.90] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.783 [0.69, 0.86] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |
| rag-baseline    | 0.182 [0.00, 0.45]   | BCa      | 0.818 [0.55, 1.00]    | BCa             |
| agent-baseline  | 0.727 [0.36, 0.91]   | BCa      | 0.273 [0.09, 0.64]    | BCa             |

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
| llm_author_claim@1#fefdf4416c50   | 11      | 11              | 0      | 0              |
| llm_condition@1#134ab1a38338      | 33      | 30              | 24     | 21             |
| llm_measurement@1#5212fc43026f    | 37      | 27              | 17     | 9              |
| llm_metric@1#1ca12a572ef8         | 10      | 10              | 5      | 5              |
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 0      | 0              |
| regex_condition@2#80486860164a    | 17      | 9               | 8      | 0              |
| regex_measurement@2#9edb306c5b05  | 33      | 24              | 13     | 6              |
| regex_metric@2#67f41f33eff7       | 22      | 6               | 17     | 1              |

Facts no extractor found: condition 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 33      | 33      | 30        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 24     | 21             |
| llm_condition@1#134ab1a38338      | all             | all     | 33      | 33      | 30        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 24     | 21             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 37      | 33      | 27        | 0.730       | 0.818    | 0.771 | 1.000           | 0.926                  | 17     | 9              |
| llm_measurement@1#5212fc43026f    | all             | all     | 37      | 33      | 27        | 0.730       | 0.818    | 0.771 | 1.000           | -                      | 17     | 9              |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 10      | 11      | 10        | 1.000       | 0.909    | 0.952 | 1.000           | -                      | 5      | 5              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 10      | 11      | 10        | 1.000       | 0.909    | 0.952 | 1.000           | -                      | 5      | 5              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 17      | 33      | 9         | 0.529       | 0.273    | 0.360 | 1.000           | -                      | 8      | 0              |
| regex_condition@2#80486860164a    | all             | all     | 17      | 33      | 9         | 0.529       | 0.273    | 0.360 | 1.000           | -                      | 8      | 0              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 33      | 33      | 24        | 0.727       | 0.727    | 0.727 | 1.000           | 0.917                  | 13     | 6              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 33      | 33      | 24        | 0.727       | 0.727    | 0.727 | 1.000           | -                      | 13     | 6              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 22      | 11      | 6         | 0.273       | 0.545    | 0.364 | 1.000           | -                      | 17     | 1              |
| regex_metric@2#67f41f33eff7       | all             | all     | 22      | 11      | 6         | 0.273       | 0.545    | 0.364 | 1.000           | -                      | 17     | 1              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 11      | 11            | 12693          | 1317            | 36.802    |
| llm_condition@1#134ab1a38338      | 11      | 20            | 24820          | 3314            | 89.439    |
| llm_measurement@1#5212fc43026f    | 11      | 22            | 34470          | 6745            | 175.004   |
| llm_metric@1#1ca12a572ef8         | 11      | 13            | 16319          | 1011            | 30.279    |
| llm_screen@1#6bec6abaf6a0         | 11      | 11            | 11472          | 922             | 27.505    |
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.077     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.077     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.204     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.080     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.083     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 44      | 4.000       |
| calls            | 110     | 10.000      |
| input_tokens     | 99774   | 9070.364    |
| made_model_calls | 77      | 7.000       |
| model_calls      | 77      | 7.000       |
| output_tokens    | 13309   | 1209.909    |
| seconds          | 360.299 | 32.754      |

## Funnel

Strategy `all` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 7.000          |
| input_tokens  | 9070.364       |
| output_tokens | 1209.909       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 11          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
