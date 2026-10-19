# Evaluation of run rag-tpl-k1-mixed on rag-tpl-k1-9c3bbb32

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 51      | 48      | 48        | 0.941       | 1.000    | 0.970 | 1.000           |
| all             | paraphrased   | 43      | 43      | 39        | 0.907       | 0.907    | 0.907 | 1.000           |
| all             | distributed   | 35      | 26      | 26        | 0.743       | 1.000    | 0.852 | 1.000           |
| all             | complex       | 79      | 72      | 69        | 0.873       | 0.958    | 0.914 | 1.000           |
| all             | contradictory | 40      | 38      | 38        | 0.950       | 1.000    | 0.974 | 1.000           |
| all             | all           | 248     | 227     | 220       | 0.887       | 0.969    | 0.926 | 1.000           |
| author_claim    | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 20      | 19      | 19        | 0.950       | 1.000    | 0.974 | 1.000           |
| condition       | paraphrased   | 17      | 17      | 13        | 0.765       | 0.765    | 0.765 | 1.000           |
| condition       | distributed   | 16      | 9       | 9         | 0.562       | 1.000    | 0.720 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all           | 77      | 69      | 65        | 0.844       | 0.942    | 0.890 | 1.000           |
| measurement     | explicit      | 20      | 19      | 19        | 0.950       | 1.000    | 0.974 | 1.000           |
| measurement     | paraphrased   | 16      | 16      | 16        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | complex       | 53      | 48      | 45        | 0.849       | 0.938    | 0.891 | 1.000           |
| measurement     | contradictory | 17      | 15      | 15        | 0.882       | 1.000    | 0.938 | 1.000           |
| measurement     | all           | 115     | 107     | 104       | 0.904       | 0.972    | 0.937 | 1.000           |
| metric          | explicit      | 6       | 5       | 5         | 0.833       | 1.000    | 0.909 | 1.000           |
| metric          | paraphrased   | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | distributed   | 6       | 4       | 4         | 0.667       | 1.000    | 0.800 | 1.000           |
| metric          | complex       | 13      | 11      | 11        | 0.846       | 1.000    | 0.917 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 34      | 29      | 29        | 0.853       | 1.000    | 0.921 | 1.000           |

Facts no item matched: 7; items matching no fact: 28.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 19                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.947          | 5         | 0.800       |
| paraphrased   | 16                     | 0.750                  | 0.750                     | 1.000             | 0.750             | 1.000          | 4         | 1.000       |
| distributed   | 9                      | 1.000                  | 1.000                     | 1.000             | 0.778             | 0.778          | 4         | 1.000       |
| complex       | 45                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.933          | 3         | 0.000       |
| contradictory | 15                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| all           | 104                    | 0.962                  | 0.962                     | 1.000             | 0.942             | 0.942          | 20        | 0.800       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 24        | 20           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | evidence-engine | 5         | 5            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | evidence-engine | 5         | 4            | 1.000                | 1.000          | 1.000               | -              |
| distributed   | evidence-engine | 5         | 4            | 1.000                | 1.000          | 1.000               | -              |
| complex       | evidence-engine | 5         | 3            | 1.000                | 1.000          | 1.000               | -              |
| contradictory | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 4    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 2    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | large_effect    | 2    | 0    | 0    | 1.000       | 1.000    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | yes              | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.890 [0.79, 0.95] | BCa      |
| metric          | 0.921 [0.85, 0.97] | BCa      |
| measurement     | 0.937 [0.89, 0.98] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.926 [0.89, 0.96] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 106          | 106      | 1.000    |
| all             | paraphrased   | 90           | 90       | 1.000    |
| all             | distributed   | 60           | 60       | 1.000    |
| all             | complex       | 133          | 133      | 1.000    |
| all             | contradictory | 77           | 77       | 1.000    |
| all             | all           | 466          | 466      | 1.000    |
| author_claim    | explicit      | 10           | 10       | 1.000    |
| author_claim    | paraphrased   | 10           | 10       | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 44           | 44       | 1.000    |
| condition       | explicit      | 48           | 48       | 1.000    |
| condition       | paraphrased   | 43           | 43       | 1.000    |
| condition       | distributed   | 27           | 27       | 1.000    |
| condition       | complex       | 41           | 41       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 199          | 199      | 1.000    |
| measurement     | explicit      | 19           | 19       | 1.000    |
| measurement     | paraphrased   | 16           | 16       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 48           | 48       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 107          | 107      | 1.000    |
| metric          | explicit      | 29           | 29       | 1.000    |
| metric          | paraphrased   | 21           | 21       | 1.000    |
| metric          | distributed   | 16           | 16       | 1.000    |
| metric          | complex       | 36           | 36       | 1.000    |
| metric          | contradictory | 14           | 14       | 1.000    |
| metric          | all           | 116          | 116      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | 22      | 22              | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | 69      | 63              | 52     | 46             |
| llm_measurement@1#957820ab7bd1    | 106     | 100             | 50     | 46             |
| llm_metric@1#6186147fa702         | 29      | 28              | 10     | 9              |
| regex_author_claim@2#75e32ebcdf68 | 22      | 22              | 0      | 0              |
| regex_condition@2#a0c64d9b6305    | 25      | 19              | 8      | 2              |
| regex_measurement@2#b984f16ded3b  | 65      | 58              | 9      | 4              |
| regex_metric@2#94a3000eacae       | 24      | 20              | 5      | 1              |

Facts no extractor found: condition 4, measurement 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#1c6d8cea16f9   | author_claim    | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#1c6d8cea16f9   | all             | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#f75a85c10bd4      | condition       | all     | 69      | 69      | 63        | 0.913       | 0.913    | 0.913 | 1.000           | -                      | 52     | 46             |
| llm_condition@1#f75a85c10bd4      | all             | all     | 69      | 69      | 63        | 0.913       | 0.913    | 0.913 | 1.000           | -                      | 52     | 46             |
| llm_measurement@1#957820ab7bd1    | measurement     | all     | 106     | 107     | 100       | 0.943       | 0.935    | 0.939 | 1.000           | 0.960                  | 50     | 46             |
| llm_measurement@1#957820ab7bd1    | all             | all     | 106     | 107     | 100       | 0.943       | 0.935    | 0.939 | 1.000           | -                      | 50     | 46             |
| llm_metric@1#6186147fa702         | metric          | all     | 29      | 29      | 28        | 0.966       | 0.966    | 0.966 | 1.000           | -                      | 10     | 9              |
| llm_metric@1#6186147fa702         | all             | all     | 29      | 29      | 28        | 0.966       | 0.966    | 0.966 | 1.000           | -                      | 10     | 9              |
| regex_author_claim@2#75e32ebcdf68 | author_claim    | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#75e32ebcdf68 | all             | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#a0c64d9b6305    | condition       | all     | 25      | 69      | 19        | 0.760       | 0.275    | 0.404 | 1.000           | -                      | 8      | 2              |
| regex_condition@2#a0c64d9b6305    | all             | all     | 25      | 69      | 19        | 0.760       | 0.275    | 0.404 | 1.000           | -                      | 8      | 2              |
| regex_measurement@2#b984f16ded3b  | measurement     | all     | 65      | 107     | 58        | 0.892       | 0.542    | 0.674 | 1.000           | 1.000                  | 9      | 4              |
| regex_measurement@2#b984f16ded3b  | all             | all     | 65      | 107     | 58        | 0.892       | 0.542    | 0.674 | 1.000           | -                      | 9      | 4              |
| regex_metric@2#94a3000eacae       | metric          | all     | 24      | 29      | 20        | 0.833       | 0.690    | 0.755 | 1.000           | -                      | 5      | 1              |
| regex_metric@2#94a3000eacae       | all             | all     | 24      | 29      | 20        | 0.833       | 0.690    | 0.755 | 1.000           | -                      | 5      | 1              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#1c6d8cea16f9   | 24      | 24            | 20593          | 2624            | 70.841    |
| llm_condition@1#f75a85c10bd4      | 24      | 41            | 39290          | 7093            | 186.098   |
| llm_measurement@1#957820ab7bd1    | 24      | 46            | 57113          | 18737           | 471.470   |
| llm_metric@1#6186147fa702         | 24      | 24            | 23089          | 2600            | 71.083    |
| llm_screen@1#a1013a736e72         | 23      | 23            | 17365          | 1793            | 13.920    |
| regex_author_claim@2#75e32ebcdf68 | 24      | 0             | 0              | 0               | 0.213     |
| regex_condition@2#a0c64d9b6305    | 24      | 0             | 0              | 0               | 0.188     |
| regex_measurement@2#b984f16ded3b  | 24      | 0             | 0              | 0               | 0.405     |
| regex_metric@2#94a3000eacae       | 24      | 0             | 0              | 0               | 0.194     |
| regex_screen@1#a2821956ee33       | 24      | 0             | 0              | 0               | 0.198     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 123     | 5.125       |
| calls            | 239     | 9.958       |
| input_tokens     | 157450  | 6560.417    |
| made_model_calls | 133     | 5.542       |
| model_calls      | 158     | 6.583       |
| output_tokens    | 32847   | 1368.625    |
| seconds          | 816.178 | 34.007      |

## Funnel

Strategy `all` over 24 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 9.958          |
| model_calls   | 6.583          |
| input_tokens  | 6560.417       |
| output_tokens | 1368.625       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 24          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 24          | 22   | 0    | 0    | 2    | 1.000       | 1.000    |

Screened out wrongly: none
