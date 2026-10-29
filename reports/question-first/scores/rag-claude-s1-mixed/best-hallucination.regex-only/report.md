# Evaluation of run rag-claude-s1-mixed on rag-claude-s1-ec928480

Question: Which method achieves the lowest hallucination rate within each paper?
Question id: best-hallucination (kind best)
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 25      | 34      | 25        | 1.000       | 0.735    | 0.847 | 1.000           |
| all             | paraphrased   | 14      | 30      | 14        | 1.000       | 0.467    | 0.636 | 0.929           |
| all             | distributed   | 15      | 22      | 13        | 0.867       | 0.591    | 0.703 | 1.000           |
| all             | complex       | 66      | 70      | 66        | 1.000       | 0.943    | 0.971 | 1.000           |
| all             | contradictory | 34      | 34      | 34        | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | all           | 154     | 190     | 152       | 0.987       | 0.800    | 0.884 | 0.993           |
| condition       | explicit      | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased   | 13      | 13      | 13        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all           | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | explicit      | 7       | 15      | 7         | 1.000       | 0.467    | 0.636 | 1.000           |
| measurement     | paraphrased   | 0       | 13      | 0         | n/a         | 0.000    | 0.000 | -               |
| measurement     | distributed   | 0       | 9       | 0         | n/a         | 0.000    | 0.000 | -               |
| measurement     | complex       | 46      | 50      | 46        | 1.000       | 0.920    | 0.958 | 1.000           |
| measurement     | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | all           | 68      | 102     | 68        | 1.000       | 0.667    | 0.800 | 1.000           |
| metric          | explicit      | 3       | 4       | 3         | 1.000       | 0.750    | 0.857 | 1.000           |
| metric          | paraphrased   | 1       | 4       | 1         | 1.000       | 0.250    | 0.400 | 0.000           |
| metric          | distributed   | 6       | 4       | 4         | 0.667       | 1.000    | 0.800 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 25      | 27      | 23        | 0.920       | 0.852    | 0.885 | 0.957           |

Facts no item matched: 38; items matching no fact: 2.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement.

## B. Kind assignment

| conditions   | kind_correct   | kind_accuracy   |
|--------------|----------------|-----------------|
| 61           | 61             | 1.000           |

Matched conditions whose label vocab gives a method kind, and the share the engine gave that kind.

## C. Best

| system          | winner   | expected_winner   | winner_correct   | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   |
|-----------------|----------|-------------------|------------------|------------------|----------------------|----------------|----------------------|---------------------------------|
| evidence-engine | -        | rag               | no               | 9                | 0.333                | 0.333          | 20                   | 0.700                           |

`winner_correct`: the winner (or the tie) is truth's; per-study accuracy of the paper's winner and tie over the studies truth can decide (a winner or a tie): a decidable paper left out or given neither is wrong, a paper with no comparison is not counted; completeness is the share of them given a winner or tie. `*_all_papers`: the old number over truth's studies not screened out and not a duplicate, where silence on a no-comparison paper is right (the engine does not leave duplicates out, which shows in its wins).

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 1.000 [n/a]        | -        |
| metric          | 0.885 [0.75, 0.96] | BCa      |
| measurement     | 0.800 [0.61, 0.91] | BCa      |
| all             | 0.884 [0.81, 0.94] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric             | interval           | method   | n   |
|-----------------|--------------------|--------------------|----------|-----|
| evidence-engine | per_study_accuracy | 0.333 [0.11, 0.67] | BCa      | 9   |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 88           | 80       | 0.909    |
| all             | paraphrased   | 73           | 65       | 0.890    |
| all             | distributed   | 75           | 67       | 0.893    |
| all             | complex       | 159          | 151      | 0.950    |
| all             | contradictory | 88           | 80       | 0.909    |
| all             | all           | 483          | 443      | 0.917    |
| author_claim    | explicit      | 8            | 0        | 0.000    |
| author_claim    | paraphrased   | 8            | 0        | 0.000    |
| author_claim    | distributed   | 8            | 0        | 0.000    |
| author_claim    | complex       | 8            | 0        | 0.000    |
| author_claim    | contradictory | 8            | 0        | 0.000    |
| author_claim    | all           | 40           | 0        | 0.000    |
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

| extractor                           | found   | found_matched   | only   | only_matched   |
|-------------------------------------|---------|-----------------|--------|----------------|
| abbrev_metric@1#2ec10bd35b5b        | 2       | 2               | 1      | 1              |
| number_measurement@1#f8148ede3708   | 7       | 7               | 7      | 7              |
| regex_condition_kind@1#0a9f7d82195a | 61      | 61              | 61     | 61             |
| regex_measurement@2#b29c53384eb5    | 61      | 61              | 61     | 61             |
| regex_metric@2#0e8a190b4722         | 24      | 22              | 23     | 21             |

Facts no extractor found: measurement 34, metric 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                           | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-------------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_metric@1#2ec10bd35b5b        | metric          | all     | 2       | 22      | 2         | 1.000       | 0.091    | 0.167 | 1.000           | -                      | 1      | 1              |
| abbrev_metric@1#2ec10bd35b5b        | all             | all     | 2       | 22      | 2         | 1.000       | 0.091    | 0.167 | 1.000           | -                      | 1      | 1              |
| number_measurement@1#f8148ede3708   | measurement     | all     | 7       | 11      | 7         | 1.000       | 0.636    | 0.778 | 1.000           | 0.000                  | 7      | 7              |
| number_measurement@1#f8148ede3708   | all             | all     | 7       | 11      | 7         | 1.000       | 0.636    | 0.778 | 1.000           | -                      | 7      | 7              |
| regex_condition_kind@1#0a9f7d82195a | condition       | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| regex_condition_kind@1#0a9f7d82195a | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| regex_measurement@2#b29c53384eb5    | measurement     | all     | 61      | 102     | 61        | 1.000       | 0.598    | 0.748 | 1.000           | 0.000                  | 61     | 61             |
| regex_measurement@2#b29c53384eb5    | all             | all     | 61      | 102     | 61        | 1.000       | 0.598    | 0.748 | 1.000           | -                      | 61     | 61             |
| regex_metric@2#0e8a190b4722         | metric          | all     | 24      | 27      | 22        | 0.917       | 0.815    | 0.863 | 0.955           | -                      | 23     | 21             |
| regex_metric@2#0e8a190b4722         | all             | all     | 24      | 27      | 22        | 0.917       | 0.815    | 0.863 | 0.955           | -                      | 23     | 21             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                           | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-------------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_metric@1#2ec10bd35b5b        | 15      | 0             | 0              | 0               | 0.217     |
| number_measurement@1#f8148ede3708   | 4       | 0             | 0              | 0               | 0.070     |
| regex_condition_kind@1#0a9f7d82195a | 20      | 0             | 0              | 0               | 0.315     |
| regex_measurement@2#b29c53384eb5    | 20      | 0             | 0              | 0               | 0.316     |
| regex_metric@2#0e8a190b4722         | 20      | 0             | 0              | 0               | 0.272     |
| regex_screen@1#858a6ebc69c6         | 20      | 0             | 0              | 0               | 0.262     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 99      | 4.950       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 2.342   | 0.117       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 4.950          |
| model_calls   | 0.000          |
| input_tokens  | 0.000          |
| output_tokens | 0.000          |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 1           |
| 1               | 2           |
| exhausted       | 17          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
