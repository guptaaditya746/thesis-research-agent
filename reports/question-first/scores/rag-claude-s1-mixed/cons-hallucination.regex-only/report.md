# Evaluation of run rag-claude-s1-mixed on rag-claude-s1-ec928480

Question: Do the authors' conclusions about hallucination agree with their reported results?
Question id: cons-hallucination (kind consistency)
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 17      | 38      | 17        | 1.000       | 0.447    | 0.618 | 0.941           |
| all             | paraphrased   | 5       | 34      | 5         | 1.000       | 0.147    | 0.256 | 0.800           |
| all             | distributed   | 15      | 26      | 14        | 0.933       | 0.538    | 0.683 | 1.000           |
| all             | complex       | 39      | 74      | 39        | 1.000       | 0.527    | 0.690 | 1.000           |
| all             | contradictory | 24      | 38      | 22        | 0.917       | 0.579    | 0.710 | 0.955           |
| all             | all           | 100     | 210     | 97        | 0.970       | 0.462    | 0.626 | 0.969           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 6       | 15      | 6         | 1.000       | 0.400    | 0.571 | 0.833           |
| condition       | paraphrased   | 0       | 13      | 0         | n/a         | 0.000    | 0.000 | -               |
| condition       | distributed   | 6       | 9       | 6         | 1.000       | 0.667    | 0.800 | 1.000           |
| condition       | complex       | 4       | 9       | 4         | 1.000       | 0.444    | 0.615 | 1.000           |
| condition       | contradictory | 7       | 15      | 7         | 1.000       | 0.467    | 0.636 | 0.857           |
| condition       | all           | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 0.913           |
| measurement     | explicit      | 4       | 15      | 4         | 1.000       | 0.267    | 0.421 | 1.000           |
| measurement     | paraphrased   | 0       | 13      | 0         | n/a         | 0.000    | 0.000 | -               |
| measurement     | distributed   | 0       | 9       | 0         | n/a         | 0.000    | 0.000 | -               |
| measurement     | complex       | 20      | 50      | 20        | 1.000       | 0.400    | 0.571 | 1.000           |
| measurement     | contradictory | 9       | 15      | 7         | 0.778       | 0.467    | 0.583 | 1.000           |
| measurement     | all           | 33      | 102     | 31        | 0.939       | 0.304    | 0.459 | 1.000           |
| metric          | explicit      | 3       | 4       | 3         | 1.000       | 0.750    | 0.857 | 1.000           |
| metric          | paraphrased   | 1       | 4       | 1         | 1.000       | 0.250    | 0.400 | 0.000           |
| metric          | distributed   | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 24      | 27      | 23        | 0.958       | 0.852    | 0.902 | 0.957           |

Facts no item matched: 113; items matching no fact: 3.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Claim to result

| claims   | claim_correct   | claim_accuracy   |
|----------|-----------------|------------------|
| 20       | 20              | 1.000            |

Author-claim items whose claim span overlaps a true claim, and the share with its direction.

Measurement linkage (no pair check: a consistency answer names no measurement pair):

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|
| explicit      | 4                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          |
| paraphrased   | 0                      | -                      | -                         | -                 | -                 | -              |
| distributed   | 0                      | -                      | -                         | -                 | -                 | -              |
| complex       | 20                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          |
| contradictory | 7                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          |
| all           | 31                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          |

## C. Consistency

| system          | metric             | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   | agreeing_precision   | agreeing_recall   | disagreeing_precision   | disagreeing_recall   |
|-----------------|--------------------|------------------|----------------------|----------------|----------------------|---------------------------------|----------------------|-------------------|-------------------------|----------------------|
| evidence-engine | hallucination_rate | 9                | 0.222                | 0.222          | 9                    | 0.222                           | 1.000                | 0.125             | 1.000                   | 1.000                |

Over the studies truth can decide (its question metric is the claim metric and `agrees` is not null: duplicates and papers with missing data or no claim drop out): a decidable paper left out or called undetermined is wrong; completeness is the share given true or false; the agreeing and disagreeing sets are over the same studies. `*_all_papers`: the old number over every study truth lists, `agrees` null right when truth's is null too.

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.548 [0.41, 0.67] | BCa      |
| metric          | 0.902 [0.77, 0.97] | BCa      |
| measurement     | 0.459 [0.29, 0.69] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.626 [0.54, 0.74] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric             | interval           | method   | n   |
|-----------------|--------------------|--------------------|----------|-----|
| evidence-engine | per_study_accuracy | 0.222 [0.00, 0.60] | BCa      | 9   |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 88           | 88       | 1.000    |
| all             | paraphrased   | 73           | 73       | 1.000    |
| all             | distributed   | 75           | 75       | 1.000    |
| all             | complex       | 159          | 159      | 1.000    |
| all             | contradictory | 88           | 88       | 1.000    |
| all             | all           | 483          | 483      | 1.000    |
| author_claim    | explicit      | 8            | 8        | 1.000    |
| author_claim    | paraphrased   | 8            | 8        | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
| condition       | explicit      | 34           | 34       | 1.000    |
| condition       | paraphrased   | 30           | 30       | 1.000    |
| condition       | distributed   | 32           | 32       | 1.000    |
| condition       | complex       | 46           | 46       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 182          | 182      | 1.000    |
| measurement     | explicit      | 15           | 15       | 1.000    |
| measurement     | paraphrased   | 13           | 13       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 50           | 50       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 102          | 102      | 1.000    |
| metric          | explicit      | 31           | 31       | 1.000    |
| metric          | paraphrased   | 22           | 22       | 1.000    |
| metric          | distributed   | 26           | 26       | 1.000    |
| metric          | complex       | 55           | 55       | 1.000    |
| metric          | contradictory | 25           | 25       | 1.000    |
| metric          | all           | 159          | 159      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| abbrev_condition@1#8587f7b799e0   | 2       | 2               | 0      | 0              |
| abbrev_metric@1#1c52ebcdca5c      | 1       | 1               | 0      | 0              |
| number_measurement@1#d7f39465e8e3 | 0       | 0               | 0      | 0              |
| regex_author_claim@2#f0e017f040b9 | 20      | 20              | 20     | 20             |
| regex_condition@2#dacfca378fed    | 23      | 23              | 21     | 21             |
| regex_measurement@2#8955e245e6dd  | 33      | 31              | 33     | 31             |
| regex_metric@2#ae09439dbca7       | 24      | 23              | 23     | 22             |

Facts no extractor found: condition 38, measurement 71, metric 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_condition@1#8587f7b799e0   | condition       | all     | 2       | 36      | 2         | 1.000       | 0.056    | 0.105 | 1.000           | -                      | 0      | 0              |
| abbrev_condition@1#8587f7b799e0   | all             | all     | 2       | 36      | 2         | 1.000       | 0.056    | 0.105 | 1.000           | -                      | 0      | 0              |
| abbrev_metric@1#1c52ebcdca5c      | metric          | all     | 1       | 7       | 1         | 1.000       | 0.143    | 0.250 | 1.000           | -                      | 0      | 0              |
| abbrev_metric@1#1c52ebcdca5c      | all             | all     | 1       | 7       | 1         | 1.000       | 0.143    | 0.250 | 1.000           | -                      | 0      | 0              |
| number_measurement@1#d7f39465e8e3 | measurement     | all     | 0       | 2       | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| number_measurement@1#d7f39465e8e3 | all             | all     | 0       | 2       | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_author_claim@2#f0e017f040b9 | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#f0e017f040b9 | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#dacfca378fed    | condition       | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 0.913           | -                      | 21     | 21             |
| regex_condition@2#dacfca378fed    | all             | all     | 23      | 61      | 23        | 1.000       | 0.377    | 0.548 | 0.913           | -                      | 21     | 21             |
| regex_measurement@2#8955e245e6dd  | measurement     | all     | 33      | 102     | 31        | 0.939       | 0.304    | 0.459 | 1.000           | 1.000                  | 33     | 31             |
| regex_measurement@2#8955e245e6dd  | all             | all     | 33      | 102     | 31        | 0.939       | 0.304    | 0.459 | 1.000           | -                      | 33     | 31             |
| regex_metric@2#ae09439dbca7       | metric          | all     | 24      | 27      | 23        | 0.958       | 0.852    | 0.902 | 0.957           | -                      | 23     | 22             |
| regex_metric@2#ae09439dbca7       | all             | all     | 24      | 27      | 23        | 0.958       | 0.852    | 0.902 | 0.957           | -                      | 23     | 22             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_condition@1#8587f7b799e0   | 12      | 0             | 0              | 0               | 0.171     |
| abbrev_metric@1#1c52ebcdca5c      | 5       | 0             | 0              | 0               | 0.071     |
| number_measurement@1#d7f39465e8e3 | 1       | 0             | 0              | 0               | 0.016     |
| regex_author_claim@2#f0e017f040b9 | 20      | 0             | 0              | 0               | 0.283     |
| regex_condition@2#dacfca378fed    | 20      | 0             | 0              | 0               | 0.267     |
| regex_measurement@2#8955e245e6dd  | 20      | 0             | 0              | 0               | 0.301     |
| regex_metric@2#ae09439dbca7       | 20      | 0             | 0              | 0               | 0.268     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.256     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 118     | 5.900       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 2.645   | 0.132       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 5.900          |
| model_calls   | 0.000          |
| input_tokens  | 0.000          |
| output_tokens | 0.000          |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 2           |
| exhausted       | 18          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
