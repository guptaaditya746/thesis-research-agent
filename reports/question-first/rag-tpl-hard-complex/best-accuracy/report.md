# Evaluation of run rag-tpl-hard-complex on rag-tpl-hard-24ab4663

Question: Which method achieves the highest factual accuracy within each paper?
Question id: best-accuracy (kind best)
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 2062    | 2363    | 1929      | 0.935       | 0.816    | 0.872 | 1.000           |
| all             | all     | 2062    | 2363    | 1929      | 0.935       | 0.816    | 0.872 | 1.000           |
| condition       | complex | 313     | 332     | 313       | 1.000       | 0.943    | 0.971 | 1.000           |
| condition       | all     | 313     | 332     | 313       | 1.000       | 0.943    | 0.971 | 1.000           |
| measurement     | complex | 1355    | 1768    | 1355      | 1.000       | 0.766    | 0.868 | 1.000           |
| measurement     | all     | 1355    | 1768    | 1355      | 1.000       | 0.766    | 0.868 | 1.000           |
| metric          | complex | 394     | 263     | 261       | 0.662       | 0.992    | 0.795 | 1.000           |
| metric          | all     | 394     | 263     | 261       | 0.662       | 0.992    | 0.795 | 1.000           |

Facts no item matched: 434; items matching no fact: 133.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement.

## B. Kind assignment

| conditions   | kind_correct   | kind_accuracy   |
|--------------|----------------|-----------------|
| 313          | 313            | 1.000           |

Matched conditions whose label vocab gives a method kind, and the share the engine gave that kind.

## C. Best

| system          | winner   | expected_winner   | winner_correct   | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   |
|-----------------|----------|-------------------|------------------|------------------|----------------------|----------------|----------------------|---------------------------------|
| evidence-engine | rag      | rag               | yes              | 40               | 0.650                | 1.000          | 100                  | 0.860                           |
| rag-baseline    | rag      | rag               | yes              | 40               | 0.000                | 0.000          | 100                  | 0.590                           |
| agent-baseline  | -        | rag               | no               | 40               | 0.000                | 0.000          | 100                  | 0.600                           |

`winner_correct`: the winner (or the tie) is truth's; per-study accuracy of the paper's winner and tie over the studies truth can decide (a winner or a tie): a decidable paper left out or given neither is wrong, a paper with no comparison is not counted; completeness is the share of them given a winner or tie. `*_all_papers`: the old number over truth's studies not screened out and not a duplicate, where silence on a no-comparison paper is right (the engine does not leave duplicates out, which shows in its wins).

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.971 [0.96, 0.98] | BCa      |
| metric          | 0.795 [0.76, 0.83] | BCa      |
| measurement     | 0.868 [0.84, 0.89] | BCa      |
| all             | 0.872 [0.85, 0.89] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric             | interval           | method   | n   |
|-----------------|--------------------|--------------------|----------|-----|
| evidence-engine | per_study_accuracy | 0.650 [0.50, 0.80] | BCa      | 40  |
| rag-baseline    | per_study_accuracy | 0.000 [n/a]        | -        | 40  |
| agent-baseline  | per_study_accuracy | 0.000 [n/a]        | -        | 40  |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 4323         | 4111     | 0.951    |
| all             | all     | 4323         | 4111     | 0.951    |
| author_claim    | complex | 212          | 0        | 0.000    |
| author_claim    | all     | 212          | 0        | 0.000    |
| condition       | complex | 1454         | 1454     | 1.000    |
| condition       | all     | 1454         | 1454     | 1.000    |
| measurement     | complex | 1768         | 1768     | 1.000    |
| measurement     | all     | 1768         | 1768     | 1.000    |
| metric          | complex | 889          | 889      | 1.000    |
| metric          | all     | 889          | 889      | 1.000    |

## Cascade contribution

| extractor                           | found   | found_matched   | only   | only_matched   |
|-------------------------------------|---------|-----------------|--------|----------------|
| abbrev_metric@1#1d39e83ec7bc        | 0       | 0               | 0      | 0              |
| gliner_metric@1#81459b8621e8        | 241     | 108             | 133    | 0              |
| llm_condition@1#2a4a65fa51fe        | 0       | 0               | 0      | 0              |
| llm_measurement@1#02bd5a7ab104      | 12      | 12              | 0      | 0              |
| llm_metric@1#41e1e53a1fc4           | 149     | 149             | 45     | 45             |
| number_measurement@1#460574ff54d0   | 12      | 12              | 0      | 0              |
| regex_condition_kind@1#2d8734025944 | 313     | 313             | 313    | 313            |
| regex_measurement@2#ad0dd5c19f1c    | 1355    | 1355            | 1343   | 1343           |
| regex_metric@2#b7c72c33bc59         | 216     | 216             | 108    | 108            |

Facts no extractor found: condition 19, measurement 413, metric 2

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                           | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-------------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_metric@1#1d39e83ec7bc        | metric          | all     | 0       | 155     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_metric@1#1d39e83ec7bc        | all             | all     | 0       | 155     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| gliner_metric@1#81459b8621e8        | metric          | all     | 241     | 155     | 108       | 0.448       | 0.697    | 0.545 | 1.000           | -                      | 133    | 0              |
| gliner_metric@1#81459b8621e8        | all             | all     | 241     | 155     | 108       | 0.448       | 0.697    | 0.545 | 1.000           | -                      | 133    | 0              |
| llm_condition@1#2a4a65fa51fe        | all             | all     | 0       | 2363    | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_measurement@1#02bd5a7ab104      | measurement     | all     | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | 0.000                  | 0      | 0              |
| llm_measurement@1#02bd5a7ab104      | all             | all     | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_metric@1#41e1e53a1fc4           | metric          | all     | 149     | 155     | 149       | 1.000       | 0.961    | 0.980 | 1.000           | -                      | 45     | 45             |
| llm_metric@1#41e1e53a1fc4           | all             | all     | 149     | 155     | 149       | 1.000       | 0.961    | 0.980 | 1.000           | -                      | 45     | 45             |
| number_measurement@1#460574ff54d0   | measurement     | all     | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | 0.000                  | 0      | 0              |
| number_measurement@1#460574ff54d0   | all             | all     | 12      | 12      | 12        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition_kind@1#2d8734025944 | condition       | all     | 313     | 332     | 313       | 1.000       | 0.943    | 0.971 | 1.000           | -                      | 313    | 313            |
| regex_condition_kind@1#2d8734025944 | all             | all     | 313     | 332     | 313       | 1.000       | 0.943    | 0.971 | 1.000           | -                      | 313    | 313            |
| regex_measurement@2#ad0dd5c19f1c    | measurement     | all     | 1355    | 1768    | 1355      | 1.000       | 0.766    | 0.868 | 1.000           | 0.000                  | 1343   | 1343           |
| regex_measurement@2#ad0dd5c19f1c    | all             | all     | 1355    | 1768    | 1355      | 1.000       | 0.766    | 0.868 | 1.000           | -                      | 1343   | 1343           |
| regex_metric@2#b7c72c33bc59         | metric          | all     | 216     | 263     | 216       | 1.000       | 0.821    | 0.902 | 1.000           | -                      | 108    | 108            |
| regex_metric@2#b7c72c33bc59         | all             | all     | 216     | 263     | 216       | 1.000       | 0.821    | 0.902 | 1.000           | -                      | 108    | 108            |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                           | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-------------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_metric@1#1d39e83ec7bc        | 62      | 0             | 0              | 0               | 0.402     |
| gliner_metric@1#81459b8621e8        | 62      | 208           | 0              | 0               | 0.452     |
| llm_measurement@1#02bd5a7ab104      | 2       | 4             | 5050           | 1914            | 0.015     |
| llm_metric@1#41e1e53a1fc4           | 62      | 83            | 98339          | 13839           | 0.423     |
| llm_screen@1#41b0d6e6793f           | 109     | 109           | 102099         | 8191            | 0.718     |
| number_measurement@1#460574ff54d0   | 2       | 0             | 0              | 0               | 0.015     |
| regex_condition_kind@1#2d8734025944 | 106     | 0             | 0              | 0               | 0.713     |
| regex_measurement@2#ad0dd5c19f1c    | 106     | 0             | 0              | 0               | 0.920     |
| regex_metric@2#b7c72c33bc59         | 106     | 0             | 0              | 0               | 0.717     |
| regex_screen@1#858a6ebc69c6         | 112     | 0             | 0              | 0               | 0.730     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 729     | 6.509       |
| input_tokens     | 205488  | 1834.714    |
| made_model_calls | 404     | 3.607       |
| model_calls      | 404     | 3.607       |
| output_tokens    | 23944   | 213.786     |
| seconds          | 240.362 | 2.146       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 6.509          |
| model_calls   | 3.607          |
| input_tokens  | 1834.714       |
| output_tokens | 213.786        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 42          |
| exhausted       | 64          |
| skipped         | 6           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 0    | 0    | 6    | 1.000       | 1.000    |

Screened out wrongly: none
