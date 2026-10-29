# Evaluation of run rag-claude-s1-mixed-r2 on rag-claude-s1-ec928480

Question: Which method achieves the lowest hallucination rate within each paper?
Question id: best-hallucination (kind best)
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 37      | 34      | 30        | 0.811       | 0.882    | 0.845 | 1.000           |
| all             | paraphrased   | 18      | 30      | 14        | 0.778       | 0.467    | 0.583 | 1.000           |
| all             | distributed   | 22      | 22      | 17        | 0.773       | 0.773    | 0.773 | 1.000           |
| all             | complex       | 74      | 70      | 66        | 0.892       | 0.943    | 0.917 | 1.000           |
| all             | contradictory | 34      | 34      | 34        | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | all           | 185     | 190     | 161       | 0.870       | 0.847    | 0.859 | 1.000           |
| condition       | explicit      | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased   | 13      | 13      | 13        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all           | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | explicit      | 15      | 15      | 11        | 0.733       | 0.733    | 0.733 | 1.000           |
| measurement     | paraphrased   | 0       | 13      | 0         | n/a         | 0.000    | 0.000 | -               |
| measurement     | distributed   | 4       | 9       | 4         | 1.000       | 0.444    | 0.615 | 1.000           |
| measurement     | complex       | 46      | 50      | 46        | 1.000       | 0.920    | 0.958 | 1.000           |
| measurement     | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | all           | 80      | 102     | 76        | 0.950       | 0.745    | 0.835 | 1.000           |
| metric          | explicit      | 7       | 4       | 4         | 0.571       | 1.000    | 0.727 | 1.000           |
| metric          | paraphrased   | 5       | 4       | 1         | 0.200       | 0.250    | 0.222 | 1.000           |
| metric          | distributed   | 9       | 4       | 4         | 0.444       | 1.000    | 0.615 | 1.000           |
| metric          | complex       | 19      | 11      | 11        | 0.579       | 1.000    | 0.733 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 44      | 27      | 24        | 0.545       | 0.889    | 0.676 | 1.000           |

Facts no item matched: 29; items matching no fact: 24.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement.

## B. Kind assignment

| conditions   | kind_correct   | kind_accuracy   |
|--------------|----------------|-----------------|
| 61           | 61             | 1.000           |

Matched conditions whose label vocab gives a method kind, and the share the engine gave that kind.

## C. Best

| system          | winner   | expected_winner   | winner_correct   | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   |
|-----------------|----------|-------------------|------------------|------------------|----------------------|----------------|----------------------|---------------------------------|
| evidence-engine | rag      | rag               | yes              | 9                | 0.667                | 0.667          | 20                   | 0.850                           |

`winner_correct`: the winner (or the tie) is truth's; per-study accuracy of the paper's winner and tie over the studies truth can decide (a winner or a tie): a decidable paper left out or given neither is wrong, a paper with no comparison is not counted; completeness is the share of them given a winner or tie. `*_all_papers`: the old number over truth's studies not screened out and not a duplicate, where silence on a no-comparison paper is right (the engine does not leave duplicates out, which shows in its wins).

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 1.000 [n/a]        | -        |
| metric          | 0.676 [0.57, 0.79] | BCa      |
| measurement     | 0.835 [0.69, 0.92] | BCa      |
| all             | 0.859 [0.78, 0.91] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric             | interval           | method   | n   |
|-----------------|--------------------|--------------------|----------|-----|
| evidence-engine | per_study_accuracy | 0.667 [0.33, 0.89] | BCa      | 9   |

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
| abbrev_metric@1#2ec10bd35b5b        | 2       | 2               | 0      | 0              |
| gliner_metric@1#32fb264e295d        | 31      | 17              | 14     | 0              |
| llm_condition@1#2a4a65fa51fe        | 0       | 0               | 0      | 0              |
| llm_measurement@1#02bd5a7ab104      | 8       | 4               | 8      | 4              |
| llm_metric@1#41e1e53a1fc4           | 15      | 15              | 2      | 2              |
| number_measurement@1#f8148ede3708   | 11      | 11              | 11     | 11             |
| regex_condition_kind@1#0a9f7d82195a | 61      | 61              | 61     | 61             |
| regex_measurement@2#b29c53384eb5    | 61      | 61              | 61     | 61             |
| regex_metric@2#0e8a190b4722         | 24      | 18              | 11     | 5              |

Facts no extractor found: measurement 26, metric 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                           | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-------------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_metric@1#2ec10bd35b5b        | metric          | all     | 2       | 22      | 2         | 1.000       | 0.091    | 0.167 | 1.000           | -                      | 0      | 0              |
| abbrev_metric@1#2ec10bd35b5b        | all             | all     | 2       | 22      | 2         | 1.000       | 0.091    | 0.167 | 1.000           | -                      | 0      | 0              |
| gliner_metric@1#32fb264e295d        | metric          | all     | 31      | 22      | 17        | 0.548       | 0.773    | 0.642 | 1.000           | -                      | 14     | 0              |
| gliner_metric@1#32fb264e295d        | all             | all     | 31      | 22      | 17        | 0.548       | 0.773    | 0.642 | 1.000           | -                      | 14     | 0              |
| llm_condition@1#2a4a65fa51fe        | all             | all     | 0       | 190     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_measurement@1#02bd5a7ab104      | measurement     | all     | 8       | 8       | 4         | 0.500       | 0.500    | 0.500 | 1.000           | 0.000                  | 8      | 4              |
| llm_measurement@1#02bd5a7ab104      | all             | all     | 8       | 8       | 4         | 0.500       | 0.500    | 0.500 | 1.000           | -                      | 8      | 4              |
| llm_metric@1#41e1e53a1fc4           | metric          | all     | 15      | 22      | 15        | 1.000       | 0.682    | 0.811 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4           | all             | all     | 15      | 22      | 15        | 1.000       | 0.682    | 0.811 | 1.000           | -                      | 2      | 2              |
| number_measurement@1#f8148ede3708   | measurement     | all     | 11      | 15      | 11        | 1.000       | 0.733    | 0.846 | 1.000           | 0.000                  | 11     | 11             |
| number_measurement@1#f8148ede3708   | all             | all     | 11      | 15      | 11        | 1.000       | 0.733    | 0.846 | 1.000           | -                      | 11     | 11             |
| regex_condition_kind@1#0a9f7d82195a | condition       | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| regex_condition_kind@1#0a9f7d82195a | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| regex_measurement@2#b29c53384eb5    | measurement     | all     | 61      | 102     | 61        | 1.000       | 0.598    | 0.748 | 1.000           | 0.000                  | 61     | 61             |
| regex_measurement@2#b29c53384eb5    | all             | all     | 61      | 102     | 61        | 1.000       | 0.598    | 0.748 | 1.000           | -                      | 61     | 61             |
| regex_metric@2#0e8a190b4722         | metric          | all     | 24      | 27      | 18        | 0.750       | 0.667    | 0.706 | 1.000           | -                      | 11     | 5              |
| regex_metric@2#0e8a190b4722         | all             | all     | 24      | 27      | 18        | 0.750       | 0.667    | 0.706 | 1.000           | -                      | 11     | 5              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                           | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-------------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_metric@1#2ec10bd35b5b        | 15      | 0             | 0              | 0               | 0.094     |
| gliner_metric@1#32fb264e295d        | 15      | 49            | 0              | 0               | 0.102     |
| llm_measurement@1#02bd5a7ab104      | 3       | 6             | 7861           | 1399            | 0.022     |
| llm_metric@1#41e1e53a1fc4           | 15      | 15            | 17905          | 1362            | 0.098     |
| llm_screen@1#41b0d6e6793f           | 20      | 20            | 18681          | 1747            | 0.130     |
| number_measurement@1#f8148ede3708   | 5       | 0             | 0              | 0               | 0.035     |
| regex_condition_kind@1#0a9f7d82195a | 20      | 0             | 0              | 0               | 0.134     |
| regex_measurement@2#b29c53384eb5    | 20      | 0             | 0              | 0               | 0.137     |
| regex_metric@2#0e8a190b4722         | 20      | 0             | 0              | 0               | 0.130     |
| regex_screen@1#858a6ebc69c6         | 20      | 0             | 0              | 0               | 0.128     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 153     | 7.650       |
| input_tokens     | 44447   | 2222.350    |
| made_model_calls | 90      | 4.500       |
| model_calls      | 90      | 4.500       |
| output_tokens    | 4508    | 225.400     |
| seconds          | 53.399  | 2.670       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.650          |
| model_calls   | 4.500          |
| input_tokens  | 2222.350       |
| output_tokens | 225.400        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 1           |
| 1               | 2           |
| 2               | 2           |
| 3               | 1           |
| exhausted       | 14          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
