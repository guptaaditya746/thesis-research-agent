# Evaluation of run rag-tpl-hard-complex on rag-tpl-hard-24ab4663

Question: Which method achieves the lowest hallucination rate within each paper?
Question id: best-hallucination (kind best)
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 2769    | 2363    | 2204      | 0.796       | 0.933    | 0.859 | 1.000           |
| all             | all     | 2769    | 2363    | 2204      | 0.796       | 0.933    | 0.859 | 1.000           |
| condition       | complex | 313     | 332     | 313       | 1.000       | 0.943    | 0.971 | 1.000           |
| condition       | all     | 313     | 332     | 313       | 1.000       | 0.943    | 0.971 | 1.000           |
| measurement     | complex | 2009    | 1768    | 1631      | 0.812       | 0.923    | 0.864 | 1.000           |
| measurement     | all     | 2009    | 1768    | 1631      | 0.812       | 0.923    | 0.864 | 1.000           |
| metric          | complex | 447     | 263     | 260       | 0.582       | 0.989    | 0.732 | 1.000           |
| metric          | all     | 447     | 263     | 260       | 0.582       | 0.989    | 0.732 | 1.000           |

Facts no item matched: 159; items matching no fact: 565.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement.

## B. Kind assignment

| conditions   | kind_correct   | kind_accuracy   |
|--------------|----------------|-----------------|
| 313          | 313            | 1.000           |

Matched conditions whose label vocab gives a method kind, and the share the engine gave that kind.

## C. Best

| system          | winner   | expected_winner   | winner_correct   | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   |
|-----------------|----------|-------------------|------------------|------------------|----------------------|----------------|----------------------|---------------------------------|
| evidence-engine | rag      | rag               | yes              | 57               | 0.561                | 0.895          | 100                  | 0.750                           |
| rag-baseline    | rag      | rag               | yes              | 57               | 0.018                | 0.018          | 100                  | 0.440                           |
| agent-baseline  | rag      | rag               | yes              | 57               | 0.509                | 0.947          | 100                  | 0.500                           |

`winner_correct`: the winner (or the tie) is truth's; per-study accuracy of the paper's winner and tie over the studies truth can decide (a winner or a tie): a decidable paper left out or given neither is wrong, a paper with no comparison is not counted; completeness is the share of them given a winner or tie. `*_all_papers`: the old number over truth's studies not screened out and not a duplicate, where silence on a no-comparison paper is right (the engine does not leave duplicates out, which shows in its wins).

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.971 [0.96, 0.98] | BCa      |
| metric          | 0.732 [0.71, 0.76] | BCa      |
| measurement     | 0.864 [0.84, 0.89] | BCa      |
| all             | 0.859 [0.84, 0.88] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric             | interval           | method   | n   |
|-----------------|--------------------|--------------------|----------|-----|
| evidence-engine | per_study_accuracy | 0.561 [0.42, 0.68] | BCa      | 57  |
| rag-baseline    | per_study_accuracy | 0.018 [0.00, 0.11] | BCa      | 57  |
| agent-baseline  | per_study_accuracy | 0.509 [0.39, 0.63] | BCa      | 57  |

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
| abbrev_metric@1#2ec10bd35b5b        | 0       | 0               | 0      | 0              |
| gliner_metric@1#32fb264e295d        | 339     | 177             | 164    | 2              |
| llm_condition@1#2a4a65fa51fe        | 0       | 0               | 0      | 0              |
| llm_measurement@1#02bd5a7ab104      | 709     | 510             | 566    | 440            |
| llm_metric@1#41e1e53a1fc4           | 209     | 209             | 44     | 44             |
| number_measurement@1#f8148ede3708   | 378     | 196             | 235    | 126            |
| regex_condition_kind@1#0a9f7d82195a | 313     | 313             | 313    | 313            |
| regex_measurement@2#b29c53384eb5    | 1065    | 995             | 1065   | 995            |
| regex_metric@2#0e8a190b4722         | 216     | 191             | 64     | 39             |

Facts no extractor found: condition 19, measurement 137, metric 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                           | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-------------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_metric@1#2ec10bd35b5b        | metric          | all     | 0       | 224     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_metric@1#2ec10bd35b5b        | all             | all     | 0       | 224     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| gliner_metric@1#32fb264e295d        | metric          | all     | 339     | 224     | 177       | 0.522       | 0.790    | 0.629 | 1.000           | -                      | 164    | 2              |
| gliner_metric@1#32fb264e295d        | all             | all     | 339     | 224     | 177       | 0.522       | 0.790    | 0.629 | 1.000           | -                      | 164    | 2              |
| llm_condition@1#2a4a65fa51fe        | all             | all     | 0       | 2363    | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_measurement@1#02bd5a7ab104      | measurement     | all     | 709     | 750     | 510       | 0.719       | 0.680    | 0.699 | 1.000           | 0.000                  | 566    | 440            |
| llm_measurement@1#02bd5a7ab104      | all             | all     | 709     | 750     | 510       | 0.719       | 0.680    | 0.699 | 1.000           | -                      | 566    | 440            |
| llm_metric@1#41e1e53a1fc4           | metric          | all     | 209     | 224     | 209       | 1.000       | 0.933    | 0.965 | 1.000           | -                      | 44     | 44             |
| llm_metric@1#41e1e53a1fc4           | all             | all     | 209     | 224     | 209       | 1.000       | 0.933    | 0.965 | 1.000           | -                      | 44     | 44             |
| number_measurement@1#f8148ede3708   | measurement     | all     | 378     | 750     | 196       | 0.519       | 0.261    | 0.348 | 1.000           | 0.000                  | 235    | 126            |
| number_measurement@1#f8148ede3708   | all             | all     | 378     | 750     | 196       | 0.519       | 0.261    | 0.348 | 1.000           | -                      | 235    | 126            |
| regex_condition_kind@1#0a9f7d82195a | condition       | all     | 313     | 332     | 313       | 1.000       | 0.943    | 0.971 | 1.000           | -                      | 313    | 313            |
| regex_condition_kind@1#0a9f7d82195a | all             | all     | 313     | 332     | 313       | 1.000       | 0.943    | 0.971 | 1.000           | -                      | 313    | 313            |
| regex_measurement@2#b29c53384eb5    | measurement     | all     | 1065    | 1768    | 995       | 0.934       | 0.563    | 0.702 | 1.000           | 0.000                  | 1065   | 995            |
| regex_measurement@2#b29c53384eb5    | all             | all     | 1065    | 1768    | 995       | 0.934       | 0.563    | 0.702 | 1.000           | -                      | 1065   | 995            |
| regex_metric@2#0e8a190b4722         | metric          | all     | 216     | 263     | 191       | 0.884       | 0.726    | 0.797 | 1.000           | -                      | 64     | 39             |
| regex_metric@2#0e8a190b4722         | all             | all     | 216     | 263     | 191       | 0.884       | 0.726    | 0.797 | 1.000           | -                      | 64     | 39             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                           | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-------------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_metric@1#2ec10bd35b5b        | 91      | 0             | 0              | 0               | 0.619     |
| gliner_metric@1#32fb264e295d        | 91      | 307           | 0              | 0               | 0.647     |
| llm_measurement@1#02bd5a7ab104      | 44      | 88            | 168807         | 114095          | 0.889     |
| llm_metric@1#41e1e53a1fc4           | 91      | 107           | 126317         | 18244           | 0.623     |
| llm_screen@1#41b0d6e6793f           | 109     | 109           | 102099         | 8138            | 0.718     |
| number_measurement@1#f8148ede3708   | 44      | 0             | 0              | 0               | 0.407     |
| regex_condition_kind@1#0a9f7d82195a | 106     | 0             | 0              | 0               | 0.724     |
| regex_measurement@2#b29c53384eb5    | 106     | 0             | 0              | 0               | 0.911     |
| regex_metric@2#0e8a190b4722         | 106     | 0             | 0              | 0               | 0.712     |
| regex_screen@1#858a6ebc69c6         | 112     | 0             | 0              | 0               | 0.732     |

## Cost

| measure          | total    | per_paper   |
|------------------|----------|-------------|
| cached_calls     | 0        | 0.000       |
| calls            | 900      | 8.036       |
| input_tokens     | 397223   | 3546.634    |
| made_model_calls | 611      | 5.455       |
| model_calls      | 611      | 5.455       |
| output_tokens    | 140477   | 1254.259    |
| seconds          | 1239.660 | 11.068      |
| workers          | 3        | -           |

## Funnel

Strategy `gaps` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 8.036          |
| model_calls   | 5.455          |
| input_tokens  | 3546.634       |
| output_tokens | 1254.259       |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 15          |
| 3               | 40          |
| exhausted       | 51          |
| skipped         | 6           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 0    | 0    | 6    | 1.000       | 1.000    |

Screened out wrongly: none
