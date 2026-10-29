# Evaluation of run rag-tpl-hard-complex on rag-tpl-hard-24ab4663

Question: Do the authors' conclusions about hallucination agree with their reported results?
Question id: cons-hallucination (kind consistency)
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 2042    | 2469    | 1457      | 0.714       | 0.590    | 0.646 | 1.000           |
| all             | all     | 2042    | 2469    | 1457      | 0.714       | 0.590    | 0.646 | 1.000           |
| author_claim    | complex | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 393     | 332     | 256       | 0.651       | 0.771    | 0.706 | 1.000           |
| condition       | all     | 393     | 332     | 256       | 0.651       | 0.771    | 0.706 | 1.000           |
| measurement     | complex | 1097    | 1768    | 833       | 0.759       | 0.471    | 0.582 | 1.000           |
| measurement     | all     | 1097    | 1768    | 833       | 0.759       | 0.471    | 0.582 | 1.000           |
| metric          | complex | 446     | 263     | 262       | 0.587       | 0.996    | 0.739 | 1.000           |
| metric          | all     | 446     | 263     | 262       | 0.587       | 0.996    | 0.739 | 1.000           |

Facts no item matched: 1012; items matching no fact: 585.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Claim to result

| claims   | claim_correct   | claim_accuracy   |
|----------|-----------------|------------------|
| 106      | 106             | 1.000            |

Author-claim items whose claim span overlaps a true claim, and the share with its direction.

Measurement linkage (no pair check: a consistency answer names no measurement pair):

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|
| complex | 833                    | 0.531                  | 0.820                     | 0.621             | 0.816             | 0.497          |
| all     | 833                    | 0.531                  | 0.820                     | 0.621             | 0.816             | 0.497          |

## C. Consistency

| system          | metric             | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   | agreeing_precision   | agreeing_recall   | disagreeing_precision   | disagreeing_recall   |
|-----------------|--------------------|------------------|----------------------|----------------|----------------------|---------------------------------|----------------------|-------------------|-------------------------|----------------------|
| evidence-engine | hallucination_rate | 55               | 0.800                | 0.891          | 62                   | 0.758                           | 1.000                | 0.800             | 0.000                   | -                    |
| rag-baseline    | hallucination_rate | 55               | 0.000                | 0.000          | 62                   | 0.000                           | n/a                  | 0.000             | n/a                     | -                    |
| agent-baseline  | hallucination_rate | 55               | 0.000                | 0.000          | 62                   | 0.000                           | n/a                  | 0.000             | n/a                     | -                    |

Over the studies truth can decide (its question metric is the claim metric and `agrees` is not null: duplicates and papers with missing data or no claim drop out): a decidable paper left out or called undetermined is wrong; completeness is the share given true or false; the agreeing and disagreeing sets are over the same studies. `*_all_papers`: the old number over every study truth lists, `agrees` null right when truth's is null too.

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.706 [0.68, 0.73] | BCa      |
| metric          | 0.739 [0.72, 0.76] | BCa      |
| measurement     | 0.582 [0.54, 0.62] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.646 [0.62, 0.67] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric             | interval           | method   | n   |
|-----------------|--------------------|--------------------|----------|-----|
| evidence-engine | per_study_accuracy | 0.800 [0.69, 0.89] | BCa      | 55  |
| rag-baseline    | per_study_accuracy | 0.000 [n/a]        | -        | 55  |
| agent-baseline  | per_study_accuracy | 0.000 [n/a]        | -        | 55  |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 4323         | 4323     | 1.000    |
| all             | all     | 4323         | 4323     | 1.000    |
| author_claim    | complex | 212          | 212      | 1.000    |
| author_claim    | all     | 212          | 212      | 1.000    |
| condition       | complex | 1454         | 1454     | 1.000    |
| condition       | all     | 1454         | 1454     | 1.000    |
| measurement     | complex | 1768         | 1768     | 1.000    |
| measurement     | all     | 1768         | 1768     | 1.000    |
| metric          | complex | 889          | 889      | 1.000    |
| metric          | all     | 889          | 889      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| abbrev_condition@1#8587f7b799e0   | 0       | 0               | 0      | 0              |
| abbrev_metric@1#1c52ebcdca5c      | 0       | 0               | 0      | 0              |
| gliner_condition@1#6df192dba74f   | 215     | 81              | 144    | 10             |
| gliner_metric@1#cdbeb73388e0      | 334     | 175             | 164    | 5              |
| llm_author_claim@1#0bbf299aba25   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 117     | 117             | 55     | 55             |
| llm_measurement@1#02bd5a7ab104    | 390     | 248             | 267    | 159            |
| llm_metric@1#41e1e53a1fc4         | 189     | 189             | 46     | 46             |
| number_measurement@1#d7f39465e8e3 | 418     | 285             | 261    | 162            |
| regex_author_claim@2#f0e017f040b9 | 106     | 106             | 106    | 106            |
| regex_condition@2#dacfca378fed    | 162     | 159             | 123    | 120            |
| regex_measurement@2#8955e245e6dd  | 448     | 425             | 412    | 389            |
| regex_metric@2#ae09439dbca7       | 216     | 191             | 66     | 41             |

Facts no extractor found: condition 76, measurement 935, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_condition@1#8587f7b799e0   | condition       | all     | 0       | 137     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_condition@1#8587f7b799e0   | all             | all     | 0       | 137     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_metric@1#1c52ebcdca5c      | metric          | all     | 0       | 221     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_metric@1#1c52ebcdca5c      | all             | all     | 0       | 221     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| gliner_condition@1#6df192dba74f   | condition       | all     | 215     | 137     | 81        | 0.377       | 0.591    | 0.460 | 1.000           | -                      | 144    | 10             |
| gliner_condition@1#6df192dba74f   | all             | all     | 215     | 137     | 81        | 0.377       | 0.591    | 0.460 | 1.000           | -                      | 144    | 10             |
| gliner_metric@1#cdbeb73388e0      | metric          | all     | 334     | 221     | 175       | 0.524       | 0.792    | 0.631 | 1.000           | -                      | 164    | 5              |
| gliner_metric@1#cdbeb73388e0      | all             | all     | 334     | 221     | 175       | 0.524       | 0.792    | 0.631 | 1.000           | -                      | 164    | 5              |
| llm_author_claim@1#0bbf299aba25   | all             | all     | 0       | 2469    | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 117     | 137     | 117       | 1.000       | 0.854    | 0.921 | 1.000           | -                      | 55     | 55             |
| llm_condition@1#45b3761c700e      | all             | all     | 117     | 137     | 117       | 1.000       | 0.854    | 0.921 | 1.000           | -                      | 55     | 55             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 390     | 912     | 248       | 0.636       | 0.272    | 0.381 | 1.000           | 0.887                  | 267    | 159            |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 390     | 912     | 248       | 0.636       | 0.272    | 0.381 | 1.000           | -                      | 267    | 159            |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 189     | 221     | 189       | 1.000       | 0.855    | 0.922 | 1.000           | -                      | 46     | 46             |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 189     | 221     | 189       | 1.000       | 0.855    | 0.922 | 1.000           | -                      | 46     | 46             |
| number_measurement@1#d7f39465e8e3 | measurement     | all     | 418     | 936     | 285       | 0.682       | 0.304    | 0.421 | 1.000           | 0.632                  | 261    | 162            |
| number_measurement@1#d7f39465e8e3 | all             | all     | 418     | 936     | 285       | 0.682       | 0.304    | 0.421 | 1.000           | -                      | 261    | 162            |
| regex_author_claim@2#f0e017f040b9 | author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_author_claim@2#f0e017f040b9 | all             | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_condition@2#dacfca378fed    | condition       | all     | 162     | 332     | 159       | 0.981       | 0.479    | 0.644 | 1.000           | -                      | 123    | 120            |
| regex_condition@2#dacfca378fed    | all             | all     | 162     | 332     | 159       | 0.981       | 0.479    | 0.644 | 1.000           | -                      | 123    | 120            |
| regex_measurement@2#8955e245e6dd  | measurement     | all     | 448     | 1768    | 425       | 0.949       | 0.240    | 0.384 | 1.000           | 0.372                  | 412    | 389            |
| regex_measurement@2#8955e245e6dd  | all             | all     | 448     | 1768    | 425       | 0.949       | 0.240    | 0.384 | 1.000           | -                      | 412    | 389            |
| regex_metric@2#ae09439dbca7       | metric          | all     | 216     | 263     | 191       | 0.884       | 0.726    | 0.797 | 1.000           | -                      | 66     | 41             |
| regex_metric@2#ae09439dbca7       | all             | all     | 216     | 263     | 191       | 0.884       | 0.726    | 0.797 | 1.000           | -                      | 66     | 41             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_condition@1#8587f7b799e0   | 46      | 0             | 0              | 0               | 0.296     |
| abbrev_metric@1#1c52ebcdca5c      | 90      | 0             | 0              | 0               | 0.583     |
| gliner_condition@1#6df192dba74f   | 46      | 149           | 0              | 0               | 0.339     |
| gliner_metric@1#cdbeb73388e0      | 90      | 304           | 0              | 0               | 0.640     |
| llm_condition@1#45b3761c700e      | 46      | 79            | 91608          | 11733           | 0.316     |
| llm_measurement@1#02bd5a7ab104    | 54      | 108           | 177955         | 64908           | 0.431     |
| llm_metric@1#41e1e53a1fc4         | 90      | 107           | 129645         | 16809           | 0.608     |
| llm_screen@1#41b0d6e6793f         | 109     | 109           | 102099         | 8152            | 0.722     |
| number_measurement@1#d7f39465e8e3 | 55      | 0             | 0              | 0               | 0.478     |
| regex_author_claim@2#f0e017f040b9 | 106     | 0             | 0              | 0               | 0.690     |
| regex_condition@2#dacfca378fed    | 106     | 0             | 0              | 0               | 0.706     |
| regex_measurement@2#8955e245e6dd  | 106     | 0             | 0              | 0               | 0.788     |
| regex_metric@2#ae09439dbca7       | 106     | 0             | 0              | 0               | 0.716     |
| regex_screen@1#858a6ebc69c6       | 112     | 0             | 0              | 0               | 0.728     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 1162    | 10.375      |
| input_tokens     | 501307  | 4475.955    |
| made_model_calls | 856     | 7.643       |
| model_calls      | 856     | 7.643       |
| output_tokens    | 101602  | 907.161     |
| seconds          | 937.216 | 8.368       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.375         |
| model_calls   | 7.643          |
| input_tokens  | 4475.955       |
| output_tokens | 907.161        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 6           |
| 2               | 1           |
| 3               | 46          |
| exhausted       | 53          |
| skipped         | 6           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 0    | 0    | 6    | 1.000       | 1.000    |

Screened out wrongly: none
