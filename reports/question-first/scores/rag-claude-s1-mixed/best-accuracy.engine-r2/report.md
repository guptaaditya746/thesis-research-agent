# Evaluation of run rag-claude-s1-mixed-r2 on rag-claude-s1-ec928480

Question: Which method achieves the highest factual accuracy within each paper?
Question id: best-accuracy (kind best)
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 24      | 34      | 23        | 0.958       | 0.676    | 0.793 | 1.000           |
| all             | paraphrased   | 19      | 30      | 18        | 0.947       | 0.600    | 0.735 | 0.944           |
| all             | distributed   | 25      | 22      | 18        | 0.720       | 0.818    | 0.766 | 1.000           |
| all             | complex       | 66      | 70      | 66        | 1.000       | 0.943    | 0.971 | 1.000           |
| all             | contradictory | 35      | 34      | 34        | 0.971       | 1.000    | 0.986 | 1.000           |
| all             | all           | 169     | 190     | 159       | 0.941       | 0.837    | 0.886 | 0.994           |
| condition       | explicit      | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased   | 13      | 13      | 13        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all           | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | explicit      | 4       | 15      | 4         | 1.000       | 0.267    | 0.421 | 1.000           |
| measurement     | paraphrased   | 4       | 13      | 4         | 1.000       | 0.308    | 0.471 | 1.000           |
| measurement     | distributed   | 5       | 9       | 5         | 1.000       | 0.556    | 0.714 | 1.000           |
| measurement     | complex       | 46      | 50      | 46        | 1.000       | 0.920    | 0.958 | 1.000           |
| measurement     | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | all           | 74      | 102     | 74        | 1.000       | 0.725    | 0.841 | 1.000           |
| metric          | explicit      | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | paraphrased   | 2       | 4       | 1         | 0.500       | 0.250    | 0.333 | 0.000           |
| metric          | distributed   | 11      | 4       | 4         | 0.364       | 1.000    | 0.533 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | all           | 34      | 27      | 24        | 0.706       | 0.889    | 0.787 | 0.958           |

Facts no item matched: 31; items matching no fact: 10.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement.

## B. Kind assignment

| conditions   | kind_correct   | kind_accuracy   |
|--------------|----------------|-----------------|
| 61           | 61             | 1.000           |

Matched conditions whose label vocab gives a method kind, and the share the engine gave that kind.

## C. Best

| system          | winner       | expected_winner   | winner_correct   | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   |
|-----------------|--------------|-------------------|------------------|------------------|----------------------|----------------|----------------------|---------------------------------|
| evidence-engine | no-retrieval | no-retrieval      | yes              | 11               | 0.909                | 1.000          | 20                   | 0.950                           |

`winner_correct`: the winner (or the tie) is truth's; per-study accuracy of the paper's winner and tie over the studies truth can decide (a winner or a tie): a decidable paper left out or given neither is wrong, a paper with no comparison is not counted; completeness is the share of them given a winner or tie. `*_all_papers`: the old number over truth's studies not screened out and not a duplicate, where silence on a no-comparison paper is right (the engine does not leave duplicates out, which shows in its wins).

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 1.000 [n/a]        | -        |
| metric          | 0.787 [0.63, 0.91] | BCa      |
| measurement     | 0.841 [0.70, 0.93] | BCa      |
| all             | 0.886 [0.81, 0.94] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric             | interval           | method   | n   |
|-----------------|--------------------|--------------------|----------|-----|
| evidence-engine | per_study_accuracy | 0.909 [0.63, 1.00] | BCa      | 11  |

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
| abbrev_metric@1#1d39e83ec7bc        | 2       | 2               | 0      | 0              |
| gliner_metric@1#81459b8621e8        | 14      | 5               | 9      | 0              |
| llm_condition@1#2a4a65fa51fe        | 0       | 0               | 0      | 0              |
| llm_measurement@1#02bd5a7ab104      | 9       | 9               | 9      | 9              |
| llm_metric@1#41e1e53a1fc4           | 5       | 5               | 1      | 1              |
| number_measurement@1#460574ff54d0   | 4       | 4               | 4      | 4              |
| regex_condition_kind@1#2d8734025944 | 61      | 61              | 61     | 61             |
| regex_measurement@2#ad0dd5c19f1c    | 61      | 61              | 61     | 61             |
| regex_metric@2#b7c72c33bc59         | 24      | 23              | 19     | 18             |

Facts no extractor found: measurement 28, metric 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                           | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-------------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_metric@1#1d39e83ec7bc        | metric          | all     | 2       | 9       | 2         | 1.000       | 0.222    | 0.364 | 1.000           | -                      | 0      | 0              |
| abbrev_metric@1#1d39e83ec7bc        | all             | all     | 2       | 9       | 2         | 1.000       | 0.222    | 0.364 | 1.000           | -                      | 0      | 0              |
| gliner_metric@1#81459b8621e8        | metric          | all     | 14      | 9       | 5         | 0.357       | 0.556    | 0.435 | 1.000           | -                      | 9      | 0              |
| gliner_metric@1#81459b8621e8        | all             | all     | 14      | 9       | 5         | 0.357       | 0.556    | 0.435 | 1.000           | -                      | 9      | 0              |
| llm_condition@1#2a4a65fa51fe        | all             | all     | 0       | 190     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_measurement@1#02bd5a7ab104      | measurement     | all     | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           | 0.000                  | 9      | 9              |
| llm_measurement@1#02bd5a7ab104      | all             | all     | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 9      | 9              |
| llm_metric@1#41e1e53a1fc4           | metric          | all     | 5       | 9       | 5         | 1.000       | 0.556    | 0.714 | 1.000           | -                      | 1      | 1              |
| llm_metric@1#41e1e53a1fc4           | all             | all     | 5       | 9       | 5         | 1.000       | 0.556    | 0.714 | 1.000           | -                      | 1      | 1              |
| number_measurement@1#460574ff54d0   | measurement     | all     | 4       | 13      | 4         | 1.000       | 0.308    | 0.471 | 1.000           | 0.000                  | 4      | 4              |
| number_measurement@1#460574ff54d0   | all             | all     | 4       | 13      | 4         | 1.000       | 0.308    | 0.471 | 1.000           | -                      | 4      | 4              |
| regex_condition_kind@1#2d8734025944 | condition       | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| regex_condition_kind@1#2d8734025944 | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| regex_measurement@2#ad0dd5c19f1c    | measurement     | all     | 61      | 102     | 61        | 1.000       | 0.598    | 0.748 | 1.000           | 0.000                  | 61     | 61             |
| regex_measurement@2#ad0dd5c19f1c    | all             | all     | 61      | 102     | 61        | 1.000       | 0.598    | 0.748 | 1.000           | -                      | 61     | 61             |
| regex_metric@2#b7c72c33bc59         | metric          | all     | 24      | 27      | 23        | 0.958       | 0.852    | 0.902 | 0.957           | -                      | 19     | 18             |
| regex_metric@2#b7c72c33bc59         | all             | all     | 24      | 27      | 23        | 0.958       | 0.852    | 0.902 | 0.957           | -                      | 19     | 18             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                           | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-------------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_metric@1#1d39e83ec7bc        | 9       | 0             | 0              | 0               | 0.058     |
| gliner_metric@1#81459b8621e8        | 9       | 28            | 0              | 0               | 0.061     |
| llm_measurement@1#02bd5a7ab104      | 3       | 6             | 8185           | 1419            | 0.021     |
| llm_metric@1#41e1e53a1fc4           | 9       | 11            | 12077          | 699             | 0.059     |
| llm_screen@1#41b0d6e6793f           | 20      | 20            | 18681          | 1739            | 0.130     |
| number_measurement@1#460574ff54d0   | 4       | 0             | 0              | 0               | 0.027     |
| regex_condition_kind@1#2d8734025944 | 20      | 0             | 0              | 0               | 0.133     |
| regex_measurement@2#ad0dd5c19f1c    | 20      | 0             | 0              | 0               | 0.137     |
| regex_metric@2#b7c72c33bc59         | 20      | 0             | 0              | 0               | 0.131     |
| regex_screen@1#858a6ebc69c6         | 20      | 0             | 0              | 0               | 0.129     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 134     | 6.700       |
| input_tokens     | 38943   | 1947.150    |
| made_model_calls | 65      | 3.250       |
| model_calls      | 65      | 3.250       |
| output_tokens    | 3857    | 192.850     |
| seconds          | 40.201  | 2.010       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 6.700          |
| model_calls   | 3.250          |
| input_tokens  | 1947.150       |
| output_tokens | 192.850        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 7           |
| 1               | 1           |
| 2               | 3           |
| exhausted       | 9           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
