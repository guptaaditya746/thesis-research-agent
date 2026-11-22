# Evaluation of run rag-tpl-k1-mixed on rag-tpl-k1-9c3bbb32

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 19      | 48      | 19        | 1.000       | 0.396    | 0.567 | 1.000           |
| all             | paraphrased   | 5       | 43      | 5         | 1.000       | 0.116    | 0.208 | 1.000           |
| all             | distributed   | 16      | 26      | 14        | 0.875       | 0.538    | 0.667 | 1.000           |
| all             | complex       | 38      | 72      | 38        | 1.000       | 0.528    | 0.691 | 1.000           |
| all             | contradictory | 24      | 38      | 22        | 0.917       | 0.579    | 0.710 | 1.000           |
| all             | all           | 102     | 227     | 98        | 0.961       | 0.432    | 0.596 | 1.000           |
| author_claim    | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 7       | 19      | 7         | 1.000       | 0.368    | 0.538 | 1.000           |
| condition       | paraphrased   | 0       | 17      | 0         | 0.000       | 0.000    | 0.000 | -               |
| condition       | distributed   | 7       | 9       | 6         | 0.857       | 0.667    | 0.750 | 1.000           |
| condition       | complex       | 4       | 9       | 4         | 1.000       | 0.444    | 0.615 | 1.000           |
| condition       | contradictory | 7       | 15      | 7         | 1.000       | 0.467    | 0.636 | 1.000           |
| condition       | all           | 25      | 69      | 24        | 0.960       | 0.348    | 0.511 | 1.000           |
| measurement     | explicit      | 3       | 19      | 3         | 1.000       | 0.158    | 0.273 | 1.000           |
| measurement     | paraphrased   | 0       | 16      | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | distributed   | 0       | 9       | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | complex       | 19      | 48      | 19        | 1.000       | 0.396    | 0.567 | 1.000           |
| measurement     | contradictory | 9       | 15      | 7         | 0.778       | 0.467    | 0.583 | 1.000           |
| measurement     | all           | 31      | 107     | 29        | 0.935       | 0.271    | 0.420 | 1.000           |
| metric          | explicit      | 4       | 5       | 4         | 1.000       | 0.800    | 0.889 | 1.000           |
| metric          | paraphrased   | 0       | 5       | 0         | 0.000       | 0.000    | 0.000 | -               |
| metric          | distributed   | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 24      | 29      | 23        | 0.958       | 0.793    | 0.868 | 1.000           |

Facts no item matched: 129; items matching no fact: 4.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 3                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 5         | 0.000       |
| paraphrased   | 0                      | -                      | -                         | -                 | -                 | -              | 4         | 0.000       |
| distributed   | 0                      | -                      | -                         | -                 | -                 | -              | 4         | 0.000       |
| complex       | 19                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 3         | 0.000       |
| contradictory | 7                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 0.750       |
| all           | 29                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.150       |

## C. Synthesis

| system          | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | supported | mixed      | no              | 24        | 20           | 0.292                | 0.150          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | evidence-engine | 5         | 5            | 0.000                | 0.000          | -                   | -              |
| paraphrased   | evidence-engine | 5         | 4            | 0.200                | 0.000          | -                   | -              |
| distributed   | evidence-engine | 5         | 4            | 0.200                | 0.000          | -                   | -              |
| complex       | evidence-engine | 5         | 3            | 0.400                | 0.000          | -                   | -              |
| contradictory | evidence-engine | 4         | 4            | 0.750                | 0.750          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 3    | 0    | 1    | 1.000       | 0.750    |
| evidence-engine | duplicate       | 0    | 0    | 2    | -           | 0.000    |
| evidence-engine | large_effect    | 0    | 0    | 2    | -           | 0.000    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | no                   |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.511 [0.37, 0.63] | BCa      |
| metric          | 0.868 [0.72, 0.95] | BCa      |
| measurement     | 0.420 [0.26, 0.66] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.596 [0.50, 0.72] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.292 [0.12, 0.50]   | BCa      | -                     | -               |

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
| regex_author_claim@2#75e32ebcdf68 | 22      | 22              | 22     | 22             |
| regex_condition@2#a0c64d9b6305    | 25      | 24              | 25     | 24             |
| regex_measurement@2#b984f16ded3b  | 31      | 29              | 31     | 29             |
| regex_metric@2#94a3000eacae       | 24      | 23              | 24     | 23             |

Facts no extractor found: condition 45, measurement 78, metric 6

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@2#75e32ebcdf68 | author_claim    | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 22     | 22             |
| regex_author_claim@2#75e32ebcdf68 | all             | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 22     | 22             |
| regex_condition@2#a0c64d9b6305    | condition       | all     | 25      | 69      | 24        | 0.960       | 0.348    | 0.511 | 1.000           | -                      | 25     | 24             |
| regex_condition@2#a0c64d9b6305    | all             | all     | 25      | 69      | 24        | 0.960       | 0.348    | 0.511 | 1.000           | -                      | 25     | 24             |
| regex_measurement@2#b984f16ded3b  | measurement     | all     | 31      | 107     | 29        | 0.935       | 0.271    | 0.420 | 1.000           | 1.000                  | 31     | 29             |
| regex_measurement@2#b984f16ded3b  | all             | all     | 31      | 107     | 29        | 0.935       | 0.271    | 0.420 | 1.000           | -                      | 31     | 29             |
| regex_metric@2#94a3000eacae       | metric          | all     | 24      | 29      | 23        | 0.958       | 0.793    | 0.868 | 1.000           | -                      | 24     | 23             |
| regex_metric@2#94a3000eacae       | all             | all     | 24      | 29      | 23        | 0.958       | 0.793    | 0.868 | 1.000           | -                      | 24     | 23             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| regex_author_claim@2#75e32ebcdf68 | 24      | 0             | 0              | 0               | 0.201     |
| regex_condition@2#a0c64d9b6305    | 24      | 0             | 0              | 0               | 0.193     |
| regex_measurement@2#b984f16ded3b  | 24      | 0             | 0              | 0               | 0.198     |
| regex_metric@2#94a3000eacae       | 24      | 0             | 0              | 0               | 0.191     |
| regex_screen@1#a2821956ee33       | 24      | 0             | 0              | 0               | 0.233     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 90      | 3.750       |
| calls            | 120     | 5.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 1.994   | 0.083       |

## Funnel

Strategy `all` over 24 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 5.000          |
| model_calls   | 0.000          |
| input_tokens  | 0.000          |
| output_tokens | 0.000          |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 24          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 24          | 22   | 1    | 0    | 1    | 0.957       | 1.000    |

Screened out wrongly: none
