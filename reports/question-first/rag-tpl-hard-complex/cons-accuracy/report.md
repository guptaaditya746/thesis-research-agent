# Evaluation of run rag-tpl-hard-complex on rag-tpl-hard-24ab4663

Question: Do the authors' conclusions about factual accuracy agree with their reported results?
Question id: cons-accuracy (kind consistency)
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 1835    | 2469    | 1482      | 0.808       | 0.600    | 0.689 | 1.000           |
| all             | all     | 1835    | 2469    | 1482      | 0.808       | 0.600    | 0.689 | 1.000           |
| author_claim    | complex | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 394     | 332     | 257       | 0.652       | 0.774    | 0.708 | 1.000           |
| condition       | all     | 394     | 332     | 257       | 0.652       | 0.774    | 0.708 | 1.000           |
| measurement     | complex | 939     | 1768    | 856       | 0.912       | 0.484    | 0.632 | 1.000           |
| measurement     | all     | 939     | 1768    | 856       | 0.912       | 0.484    | 0.632 | 1.000           |
| metric          | complex | 396     | 263     | 263       | 0.664       | 1.000    | 0.798 | 1.000           |
| metric          | all     | 396     | 263     | 263       | 0.664       | 1.000    | 0.798 | 1.000           |

Facts no item matched: 987; items matching no fact: 353.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition, metric, measurement, author_claim.

## B. Claim to result

| claims   | claim_correct   | claim_accuracy   |
|----------|-----------------|------------------|
| 106      | 106             | 1.000            |

Author-claim items whose claim span overlaps a true claim, and the share with its direction.

Measurement linkage (no pair check: a consistency answer names no measurement pair):

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|
| complex | 856                    | 0.551                  | 0.848                     | 0.626             | 0.847             | 0.626          |
| all     | 856                    | 0.551                  | 0.848                     | 0.626             | 0.847             | 0.626          |

## C. Consistency

| system          | metric           | studies_scored   | per_study_accuracy   | completeness   | studies_all_papers   | per_study_accuracy_all_papers   | agreeing_precision   | agreeing_recall   | disagreeing_precision   | disagreeing_recall   |
|-----------------|------------------|------------------|----------------------|----------------|----------------------|---------------------------------|----------------------|-------------------|-------------------------|----------------------|
| evidence-engine | factual_accuracy | 39               | 0.641                | 0.897          | 44                   | 0.636                           | 1.000                | 0.641             | 0.000                   | -                    |
| rag-baseline    | factual_accuracy | 39               | 0.026                | 0.026          | 44                   | 0.023                           | 1.000                | 0.026             | n/a                     | -                    |
| agent-baseline  | factual_accuracy | 39               | 1.000                | 1.000          | 44                   | 0.909                           | 1.000                | 1.000             | n/a                     | -                    |

Over the studies truth can decide (its question metric is the claim metric and `agrees` is not null: duplicates and papers with missing data or no claim drop out): a decidable paper left out or called undetermined is wrong; completeness is the share given true or false; the agreeing and disagreeing sets are over the same studies. `*_all_papers`: the old number over every study truth lists, `agrees` null right when truth's is null too.

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.708 [0.69, 0.73] | BCa      |
| metric          | 0.798 [0.77, 0.83] | BCa      |
| measurement     | 0.632 [0.58, 0.68] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.689 [0.66, 0.72] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric             | interval           | method   | n   |
|-----------------|--------------------|--------------------|----------|-----|
| evidence-engine | per_study_accuracy | 0.641 [0.47, 0.79] | BCa      | 39  |
| rag-baseline    | per_study_accuracy | 0.026 [0.00, 0.10] | BCa      | 39  |
| agent-baseline  | per_study_accuracy | 1.000 [n/a]        | -        | 39  |

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
| abbrev_condition@1#eafcbe39d1a0   | 0       | 0               | 0      | 0              |
| abbrev_metric@1#dac5a8a5c84b      | 0       | 0               | 0      | 0              |
| gliner_condition@1#52e6222ffa49   | 215     | 81              | 143    | 9              |
| gliner_metric@1#0a7a21786921      | 241     | 108             | 133    | 0              |
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 119     | 119             | 56     | 56             |
| llm_measurement@1#02bd5a7ab104    | 278     | 243             | 43     | 35             |
| llm_metric@1#41e1e53a1fc4         | 147     | 147             | 47     | 47             |
| number_measurement@1#a78269e0513d | 363     | 329             | 103    | 96             |
| regex_author_claim@2#c58240a3a7a4 | 106     | 106             | 106    | 106            |
| regex_condition@2#207f8f280e4a    | 162     | 159             | 123    | 120            |
| regex_measurement@2#a65f61f0d966  | 590     | 549             | 533    | 492            |
| regex_metric@2#a5a76405f5d5       | 216     | 216             | 108    | 108            |

Facts no extractor found: condition 75, measurement 912

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_condition@1#eafcbe39d1a0   | condition       | all     | 0       | 137     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_condition@1#eafcbe39d1a0   | all             | all     | 0       | 137     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_metric@1#dac5a8a5c84b      | metric          | all     | 0       | 155     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_metric@1#dac5a8a5c84b      | all             | all     | 0       | 155     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| gliner_condition@1#52e6222ffa49   | condition       | all     | 215     | 137     | 81        | 0.377       | 0.591    | 0.460 | 1.000           | -                      | 143    | 9              |
| gliner_condition@1#52e6222ffa49   | all             | all     | 215     | 137     | 81        | 0.377       | 0.591    | 0.460 | 1.000           | -                      | 143    | 9              |
| gliner_metric@1#0a7a21786921      | metric          | all     | 241     | 155     | 108       | 0.448       | 0.697    | 0.545 | 1.000           | -                      | 133    | 0              |
| gliner_metric@1#0a7a21786921      | all             | all     | 241     | 155     | 108       | 0.448       | 0.697    | 0.545 | 1.000           | -                      | 133    | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 2469    | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 119     | 137     | 119       | 1.000       | 0.869    | 0.930 | 1.000           | -                      | 56     | 56             |
| llm_condition@1#45b3761c700e      | all             | all     | 119     | 137     | 119       | 1.000       | 0.869    | 0.930 | 1.000           | -                      | 56     | 56             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 278     | 480     | 243       | 0.874       | 0.506    | 0.641 | 1.000           | 0.901                  | 43     | 35             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 278     | 480     | 243       | 0.874       | 0.506    | 0.641 | 1.000           | -                      | 43     | 35             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 147     | 155     | 147       | 1.000       | 0.948    | 0.974 | 1.000           | -                      | 47     | 47             |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 147     | 155     | 147       | 1.000       | 0.948    | 0.974 | 1.000           | -                      | 47     | 47             |
| number_measurement@1#a78269e0513d | measurement     | all     | 363     | 520     | 329       | 0.906       | 0.633    | 0.745 | 1.000           | 0.945                  | 103    | 96             |
| number_measurement@1#a78269e0513d | all             | all     | 363     | 520     | 329       | 0.906       | 0.633    | 0.745 | 1.000           | -                      | 103    | 96             |
| regex_author_claim@2#c58240a3a7a4 | author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_author_claim@2#c58240a3a7a4 | all             | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_condition@2#207f8f280e4a    | condition       | all     | 162     | 332     | 159       | 0.981       | 0.479    | 0.644 | 1.000           | -                      | 123    | 120            |
| regex_condition@2#207f8f280e4a    | all             | all     | 162     | 332     | 159       | 0.981       | 0.479    | 0.644 | 1.000           | -                      | 123    | 120            |
| regex_measurement@2#a65f61f0d966  | measurement     | all     | 590     | 1768    | 549       | 0.931       | 0.311    | 0.466 | 1.000           | 0.350                  | 533    | 492            |
| regex_measurement@2#a65f61f0d966  | all             | all     | 590     | 1768    | 549       | 0.931       | 0.311    | 0.466 | 1.000           | -                      | 533    | 492            |
| regex_metric@2#a5a76405f5d5       | metric          | all     | 216     | 263     | 216       | 1.000       | 0.821    | 0.902 | 1.000           | -                      | 108    | 108            |
| regex_metric@2#a5a76405f5d5       | all             | all     | 216     | 263     | 216       | 1.000       | 0.821    | 0.902 | 1.000           | -                      | 108    | 108            |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_condition@1#eafcbe39d1a0   | 46      | 0             | 0              | 0               | 0.296     |
| abbrev_metric@1#dac5a8a5c84b      | 62      | 0             | 0              | 0               | 0.396     |
| gliner_condition@1#52e6222ffa49   | 46      | 149           | 0              | 0               | 0.338     |
| gliner_metric@1#0a7a21786921      | 62      | 208           | 0              | 0               | 0.440     |
| llm_condition@1#45b3761c700e      | 46      | 79            | 91775          | 11927           | 0.317     |
| llm_measurement@1#02bd5a7ab104    | 31      | 62            | 101592         | 46853           | 0.252     |
| llm_metric@1#41e1e53a1fc4         | 62      | 79            | 95709          | 13270           | 0.422     |
| llm_screen@1#41b0d6e6793f         | 109     | 109           | 102099         | 8177            | 0.717     |
| number_measurement@1#a78269e0513d | 33      | 0             | 0              | 0               | 0.291     |
| regex_author_claim@2#c58240a3a7a4 | 106     | 0             | 0              | 0               | 0.685     |
| regex_condition@2#207f8f280e4a    | 106     | 0             | 0              | 0               | 0.699     |
| regex_measurement@2#a65f61f0d966  | 106     | 0             | 0              | 0               | 0.783     |
| regex_metric@2#a5a76405f5d5       | 106     | 0             | 0              | 0               | 0.712     |
| regex_screen@1#858a6ebc69c6       | 112     | 0             | 0              | 0               | 0.724     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 1033    | 9.223       |
| input_tokens     | 391175  | 3492.634    |
| made_model_calls | 686     | 6.125       |
| model_calls      | 686     | 6.125       |
| output_tokens    | 80227   | 716.312     |
| seconds          | 757.207 | 6.761       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 9.223          |
| model_calls   | 6.125          |
| input_tokens  | 3492.634       |
| output_tokens | 716.312        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 11          |
| 2               | 9           |
| 3               | 17          |
| exhausted       | 69          |
| skipped         | 6           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 0    | 0    | 6    | 1.000       | 1.000    |

Screened out wrongly: none
