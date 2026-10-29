# Evaluation of run rag-claude-s1-mixed on rag-claude-s1-ec928480

Question: Which method achieves the lowest hallucination rate within each paper?
Question id: best-hallucination (kind best)
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 30      | 34      | 30        | 1.000       | 0.882    | 0.938 | 1.000           |
| all             | paraphrased   | 18      | 30      | 18        | 1.000       | 0.600    | 0.750 | 1.000           |
| all             | distributed   | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | complex       | 68      | 70      | 68        | 1.000       | 0.971    | 0.986 | 1.000           |
| all             | contradictory | 35      | 34      | 34        | 0.971       | 1.000    | 0.986 | 1.000           |
| all             | all           | 173     | 190     | 172       | 0.994       | 0.905    | 0.948 | 1.000           |
| condition       | explicit      | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased   | 13      | 13      | 13        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all           | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | explicit      | 12      | 15      | 12        | 1.000       | 0.800    | 0.889 | 1.000           |
| measurement     | paraphrased   | 4       | 13      | 4         | 1.000       | 0.308    | 0.471 | 1.000           |
| measurement     | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | complex       | 48      | 50      | 48        | 1.000       | 0.960    | 0.980 | 1.000           |
| measurement     | contradictory | 16      | 15      | 15        | 0.938       | 1.000    | 0.968 | 1.000           |
| measurement     | all           | 89      | 102     | 88        | 0.989       | 0.863    | 0.921 | 1.000           |
| metric          | explicit      | 3       | 4       | 3         | 1.000       | 0.750    | 0.857 | 1.000           |
| metric          | paraphrased   | 1       | 4       | 1         | 1.000       | 0.250    | 0.400 | 1.000           |
| metric          | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           |

Facts no item matched: 18; items matching no fact: 1.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement.

## B. Kind assignment

| conditions   | kind_correct   | kind_accuracy   |
|--------------|----------------|-----------------|
| 61           | 61             | 1.000           |

Matched conditions whose label vocab gives a method kind, and the share the engine gave that kind.

## C. Best

| system          | winner   | expected_winner   | winner_correct   | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   |
|-----------------|----------|-------------------|------------------|------------------|----------------------|----------------|----------------------|---------------------------------|
| evidence-engine | rag      | rag               | yes              | 9                | 0.556                | 0.556          | 20                   | 0.800                           |

`winner_correct`: the winner (or the tie) is truth's; per-study accuracy of the paper's winner and tie over the studies truth can decide (a winner or a tie): a decidable paper left out or given neither is wrong, a paper with no comparison is not counted; completeness is the share of them given a winner or tie. `*_all_papers`: the old number over truth's studies not screened out and not a duplicate, where silence on a no-comparison paper is right (the engine does not leave duplicates out, which shows in its wins).

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 1.000 [n/a]        | -        |
| metric          | 0.920 [0.79, 0.98] | BCa      |
| measurement     | 0.921 [0.82, 0.97] | BCa      |
| all             | 0.948 [0.88, 0.98] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric             | interval           | method   | n   |
|-----------------|--------------------|--------------------|----------|-----|
| evidence-engine | per_study_accuracy | 0.556 [0.22, 0.89] | BCa      | 9   |

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

| extractor                      | found   | found_matched   | only   | only_matched   |
|--------------------------------|---------|-----------------|--------|----------------|
| llm_condition@1#2a4a65fa51fe   | 61      | 61              | 61     | 61             |
| llm_measurement@1#02bd5a7ab104 | 89      | 88              | 89     | 88             |
| llm_metric@1#41e1e53a1fc4      | 23      | 23              | 23     | 23             |

Facts no extractor found: measurement 14, metric 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                      | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|--------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_condition@1#2a4a65fa51fe   | condition       | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| llm_condition@1#2a4a65fa51fe   | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 61     | 61             |
| llm_measurement@1#02bd5a7ab104 | measurement     | all     | 89      | 102     | 88        | 0.989       | 0.863    | 0.921 | 1.000           | 0.000                  | 89     | 88             |
| llm_measurement@1#02bd5a7ab104 | all             | all     | 89      | 102     | 88        | 0.989       | 0.863    | 0.921 | 1.000           | -                      | 89     | 88             |
| llm_metric@1#41e1e53a1fc4      | metric          | all     | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           | -                      | 23     | 23             |
| llm_metric@1#41e1e53a1fc4      | all             | all     | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           | -                      | 23     | 23             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                      | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|--------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#2a4a65fa51fe   | 20      | 25            | 30473          | 5053            | 0.141     |
| llm_measurement@1#02bd5a7ab104 | 20      | 40            | 56078          | 17070           | 0.151     |
| llm_metric@1#41e1e53a1fc4      | 20      | 24            | 27035          | 2372            | 0.136     |
| llm_screen@1#41b0d6e6793f      | 20      | 20            | 18681          | 1748            | 0.133     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 80      | 4.000       |
| input_tokens     | 132267  | 6613.350    |
| made_model_calls | 109     | 5.450       |
| model_calls      | 109     | 5.450       |
| output_tokens    | 26243   | 1312.150    |
| seconds          | 295.798 | 14.790      |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 4.000          |
| model_calls   | 5.450          |
| input_tokens  | 6613.350       |
| output_tokens | 1312.150       |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 5           |
| exhausted       | 15          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
