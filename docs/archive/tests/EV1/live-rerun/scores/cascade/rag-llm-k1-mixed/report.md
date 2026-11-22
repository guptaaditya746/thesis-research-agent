# Evaluation of run rag-llm-k1-mixed on rag-llm-k1-961f46a3

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 12      | 10      | 9         | 0.750       | 0.900    | 0.818 | 1.000           |
| all             | paraphrased   | 20      | 20      | 17        | 0.850       | 0.850    | 0.850 | 0.941           |
| all             | distributed   | 22      | 14      | 14        | 0.636       | 1.000    | 0.778 | 1.000           |
| all             | complex       | 49      | 38      | 36        | 0.735       | 0.947    | 0.828 | 1.000           |
| all             | contradictory | 22      | 20      | 19        | 0.864       | 0.950    | 0.905 | 1.000           |
| all             | all           | 125     | 102     | 95        | 0.760       | 0.931    | 0.837 | 0.989           |
| author_claim    | explicit      | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 5       | 4       | 3         | 0.600       | 0.750    | 0.667 | 1.000           |
| condition       | paraphrased   | 8       | 8       | 6         | 0.750       | 0.750    | 0.750 | 1.000           |
| condition       | distributed   | 8       | 5       | 5         | 0.625       | 1.000    | 0.769 | 1.000           |
| condition       | complex       | 7       | 5       | 5         | 0.714       | 1.000    | 0.833 | 1.000           |
| condition       | contradictory | 8       | 8       | 7         | 0.875       | 0.875    | 0.875 | 1.000           |
| condition       | all           | 36      | 30      | 26        | 0.722       | 0.867    | 0.788 | 1.000           |
| measurement     | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | paraphrased   | 8       | 8       | 8         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | distributed   | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | complex       | 32      | 26      | 24        | 0.750       | 0.923    | 0.828 | 1.000           |
| measurement     | contradictory | 9       | 8       | 8         | 0.889       | 1.000    | 0.941 | 1.000           |
| measurement     | all           | 58      | 51      | 49        | 0.845       | 0.961    | 0.899 | 1.000           |
| metric          | explicit      | 2       | 1       | 1         | 0.500       | 1.000    | 0.667 | 1.000           |
| metric          | paraphrased   | 2       | 2       | 1         | 0.500       | 0.500    | 0.500 | 0.000           |
| metric          | distributed   | 7       | 2       | 2         | 0.286       | 1.000    | 0.444 | 1.000           |
| metric          | complex       | 8       | 5       | 5         | 0.625       | 1.000    | 0.769 | 1.000           |
| metric          | contradictory | 3       | 2       | 2         | 0.667       | 1.000    | 0.800 | 1.000           |
| metric          | all           | 22      | 12      | 11        | 0.500       | 0.917    | 0.647 | 0.909           |

Facts no item matched: 7; items matching no fact: 30.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 4                      | 0.750                  | 0.750                     | 1.000             | 0.750             | 1.000          | 1         | 1.000       |
| paraphrased   | 8                      | 0.250                  | 0.750                     | 0.500             | 0.750             | 0.500          | 2         | 1.000       |
| distributed   | 5                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 2         | 1.000       |
| complex       | 24                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.833          | 2         | 0.000       |
| contradictory | 8                      | 0.875                  | 0.875                     | 1.000             | 0.875             | 1.000          | 2         | 1.000       |
| all           | 49                     | 0.837                  | 0.918                     | 0.918             | 0.918             | 0.837          | 9         | 0.778       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 11        | 9            | 0.909                | 1.000          | 0.889               | -              |
| rag-baseline    | mixed   | mixed      | yes             | 11        | 9            | 0.545                | 0.556          | 0.800               | 1.000          |
| agent-baseline  | mixed   | mixed      | yes             | 11        | 9            | 0.818                | 1.000          | 0.778               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | agent-baseline  | 1         | yes          | 1.000                | 1.000          | 1.000               | -              |
| explicit      | evidence-engine | 1         | yes          | 1.000                | 1.000          | 1.000               | -              |
| explicit      | rag-baseline    | 1         | yes          | 0.000                | 0.000          | -                   | -              |
| paraphrased   | agent-baseline  | 2         | 2            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | evidence-engine | 2         | 2            | 0.500                | 1.000          | 0.500               | -              |
| paraphrased   | rag-baseline    | 2         | 2            | 0.500                | 0.500          | 1.000               | 1.000          |
| distributed   | agent-baseline  | 3         | 2            | 1.000                | 1.000          | 1.000               | -              |
| distributed   | evidence-engine | 3         | 2            | 1.000                | 1.000          | 1.000               | -              |
| distributed   | rag-baseline    | 3         | 2            | 0.667                | 0.500          | 1.000               | 1.000          |
| complex       | agent-baseline  | 3         | 2            | 1.000                | 1.000          | 1.000               | -              |
| complex       | evidence-engine | 3         | 2            | 1.000                | 1.000          | 1.000               | -              |
| complex       | rag-baseline    | 3         | 2            | 1.000                | 1.000          | 1.000               | 1.000          |
| contradictory | agent-baseline  | 2         | 2            | 0.000                | 1.000          | 0.000               | -              |
| contradictory | evidence-engine | 2         | 2            | 1.000                | 1.000          | 1.000               | -              |
| contradictory | rag-baseline    | 2         | 2            | 0.000                | 0.500          | 0.000               | 1.000          |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 2    | 1    | 0    | 0.667       | 1.000    |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 1    | 0    | 0    | 1.000       | 1.000    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.788 [0.67, 0.88] | BCa      |
| metric          | 0.647 [0.48, 0.76] | BCa      |
| measurement     | 0.899 [0.84, 0.98] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.837 [0.80, 0.88] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.909 [0.56, 1.00]   | BCa      | -                     | -               |
| rag-baseline    | 0.545 [0.27, 0.82]   | BCa      | 0.364 [0.09, 0.64]    | BCa             |
| agent-baseline  | 0.818 [0.45, 1.00]   | BCa      | 0.091 [-0.18, 0.36]   | BCa             |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 23           | 23       | 1.000    |
| all             | paraphrased   | 60           | 60       | 1.000    |
| all             | distributed   | 45           | 45       | 1.000    |
| all             | complex       | 97           | 97       | 1.000    |
| all             | contradictory | 61           | 61       | 1.000    |
| all             | all           | 286          | 286      | 1.000    |
| author_claim    | explicit      | 2            | 2        | 1.000    |
| author_claim    | paraphrased   | 4            | 4        | 1.000    |
| author_claim    | distributed   | 4            | 4        | 1.000    |
| author_claim    | complex       | 4            | 4        | 1.000    |
| author_claim    | contradictory | 4            | 4        | 1.000    |
| author_claim    | all           | 18           | 18       | 1.000    |
| condition       | explicit      | 9            | 9        | 1.000    |
| condition       | paraphrased   | 32           | 32       | 1.000    |
| condition       | distributed   | 24           | 24       | 1.000    |
| condition       | complex       | 42           | 42       | 1.000    |
| condition       | contradictory | 38           | 38       | 1.000    |
| condition       | all           | 145          | 145      | 1.000    |
| measurement     | explicit      | 4            | 4        | 1.000    |
| measurement     | paraphrased   | 8            | 8        | 1.000    |
| measurement     | distributed   | 5            | 5        | 1.000    |
| measurement     | complex       | 26           | 26       | 1.000    |
| measurement     | contradictory | 8            | 8        | 1.000    |
| measurement     | all           | 51           | 51       | 1.000    |
| metric          | explicit      | 8            | 8        | 1.000    |
| metric          | paraphrased   | 16           | 16       | 1.000    |
| metric          | distributed   | 12           | 12       | 1.000    |
| metric          | complex       | 25           | 25       | 1.000    |
| metric          | contradictory | 11           | 11       | 1.000    |
| metric          | all           | 72           | 72       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 9       | 9               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 30      | 26              | 23     | 19             |
| llm_measurement@1#5212fc43026f    | 50      | 45              | 25     | 21             |
| llm_metric@1#1ca12a572ef8         | 10      | 9               | 5      | 4              |
| regex_author_claim@2#b2161f228a8c | 9       | 9               | 0      | 0              |
| regex_condition@2#80486860164a    | 13      | 7               | 6      | 0              |
| regex_measurement@2#9edb306c5b05  | 33      | 28              | 8      | 4              |
| regex_metric@2#67f41f33eff7       | 17      | 7               | 12     | 2              |

Facts no extractor found: condition 4, measurement 2, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 30      | 30      | 26        | 0.867       | 0.867    | 0.867 | 1.000           | -                      | 23     | 19             |
| llm_condition@1#134ab1a38338      | all             | all     | 30      | 30      | 26        | 0.867       | 0.867    | 0.867 | 1.000           | -                      | 23     | 19             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 50      | 51      | 45        | 0.900       | 0.882    | 0.891 | 1.000           | 0.822                  | 25     | 21             |
| llm_measurement@1#5212fc43026f    | all             | all     | 50      | 51      | 45        | 0.900       | 0.882    | 0.891 | 1.000           | -                      | 25     | 21             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 10      | 12      | 9         | 0.900       | 0.750    | 0.818 | 1.000           | -                      | 5      | 4              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 10      | 12      | 9         | 0.900       | 0.750    | 0.818 | 1.000           | -                      | 5      | 4              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 13      | 30      | 7         | 0.538       | 0.233    | 0.326 | 1.000           | -                      | 6      | 0              |
| regex_condition@2#80486860164a    | all             | all     | 13      | 30      | 7         | 0.538       | 0.233    | 0.326 | 1.000           | -                      | 6      | 0              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 33      | 51      | 28        | 0.848       | 0.549    | 0.667 | 1.000           | 0.964                  | 8      | 4              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 33      | 51      | 28        | 0.848       | 0.549    | 0.667 | 1.000           | -                      | 8      | 4              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 17      | 12      | 7         | 0.412       | 0.583    | 0.483 | 0.857           | -                      | 12     | 2              |
| regex_metric@2#67f41f33eff7       | all             | all     | 17      | 12      | 7         | 0.412       | 0.583    | 0.483 | 0.857           | -                      | 12     | 2              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 11      | 11            | 11805          | 1119            | 4.493     |
| llm_condition@1#134ab1a38338      | 11      | 17            | 20165          | 2879            | 13.213    |
| llm_measurement@1#5212fc43026f    | 11      | 20            | 30735          | 8774            | 25.109    |
| llm_metric@1#1ca12a572ef8         | 11      | 14            | 16542          | 1048            | 1.941     |
| llm_screen@1#6bec6abaf6a0         | 10      | 10            | 10020          | 793             | 4.942     |
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.073     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.072     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.227     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.075     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.072     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 94      | 8.545       |
| calls            | 109     | 9.909       |
| input_tokens     | 89267   | 8115.182    |
| made_model_calls | 16      | 1.455       |
| model_calls      | 72      | 6.545       |
| output_tokens    | 14613   | 1328.455    |
| seconds          | 50.849  | 4.623       |

## Funnel

Strategy `all` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 9.909          |
| model_calls   | 6.545          |
| input_tokens  | 8115.182       |
| output_tokens | 1328.455       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 11          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 9    | 0    | 0    | 2    | 1.000       | 1.000    |

Screened out wrongly: none
