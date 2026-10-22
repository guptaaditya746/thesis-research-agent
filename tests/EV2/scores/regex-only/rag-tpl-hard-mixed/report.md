# Evaluation of run rag-tpl-hard-mixed on rag-tpl-hard-b1c0fdfe

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 88      | 181     | 87        | 0.989       | 0.481    | 0.647 | 1.000           |
| all             | paraphrased   | 22      | 155     | 21        | 0.955       | 0.135    | 0.237 | 1.000           |
| all             | distributed   | 57      | 159     | 57        | 1.000       | 0.358    | 0.528 | 1.000           |
| all             | complex       | 202     | 476     | 200       | 0.990       | 0.420    | 0.590 | 1.000           |
| all             | contradictory | 83      | 168     | 81        | 0.976       | 0.482    | 0.645 | 1.000           |
| all             | all           | 452     | 1139    | 446       | 0.987       | 0.392    | 0.561 | 1.000           |
| author_claim    | explicit      | 23      | 23      | 23        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 21      | 21      | 21        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 21      | 21      | 21        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 21      | 21      | 21        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 36      | 68      | 35        | 0.972       | 0.515    | 0.673 | 1.000           |
| condition       | paraphrased   | 1       | 57      | 0         | 0.000       | 0.000    | 0.000 | -               |
| condition       | distributed   | 25      | 60      | 25        | 1.000       | 0.417    | 0.588 | 1.000           |
| condition       | complex       | 33      | 67      | 32        | 0.970       | 0.478    | 0.640 | 1.000           |
| condition       | contradictory | 34      | 64      | 34        | 1.000       | 0.531    | 0.694 | 1.000           |
| condition       | all           | 129     | 316     | 126       | 0.977       | 0.399    | 0.566 | 1.000           |
| measurement     | explicit      | 15      | 67      | 15        | 1.000       | 0.224    | 0.366 | 1.000           |
| measurement     | paraphrased   | 0       | 56      | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | distributed   | 0       | 59      | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | complex       | 106     | 338     | 106       | 1.000       | 0.314    | 0.477 | 1.000           |
| measurement     | contradictory | 16      | 62      | 14        | 0.875       | 0.226    | 0.359 | 1.000           |
| measurement     | all           | 137     | 582     | 135       | 0.985       | 0.232    | 0.376 | 1.000           |
| metric          | explicit      | 14      | 23      | 14        | 1.000       | 0.609    | 0.757 | 1.000           |
| metric          | paraphrased   | 0       | 21      | 0         | 0.000       | 0.000    | 0.000 | -               |
| metric          | distributed   | 12      | 20      | 12        | 1.000       | 0.600    | 0.750 | 1.000           |
| metric          | complex       | 42      | 50      | 41        | 0.976       | 0.820    | 0.891 | 1.000           |
| metric          | contradictory | 12      | 21      | 12        | 1.000       | 0.571    | 0.727 | 1.000           |
| metric          | all           | 80      | 135     | 79        | 0.988       | 0.585    | 0.735 | 1.000           |

Facts no item matched: 693; items matching no fact: 6.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 15                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 22        | 0.182       |
| paraphrased   | 0                      | -                      | -                         | -                 | -                 | -              | 20        | 0.000       |
| distributed   | 0                      | -                      | -                         | -                 | -                 | -              | 19        | 0.000       |
| complex       | 106                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.000       |
| contradictory | 14                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 19        | 0.105       |
| all           | 135                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 100       | 0.060       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 112       | 100          | 0.170                | 0.110          | 0.636               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 112       | 100          | 0.116                | 0.050          | 0.400               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 112       | 100          | 0.375                | 0.380          | 0.842               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit      | agent-baseline  | 24        | 22           | 0.417                | 0.364          | 1.000               | -              | -         |
| explicit      | evidence-engine | 24        | 22           | 0.250                | 0.182          | 1.000               | -              | -         |
| explicit      | rag-baseline    | 24        | 22           | 0.125                | 0.045          | 1.000               | 1.000          | 1.000     |
| paraphrased   | agent-baseline  | 23        | 20           | 0.478                | 0.400          | 1.000               | -              | -         |
| paraphrased   | evidence-engine | 23        | 20           | 0.130                | 0.000          | -                   | -              | -         |
| paraphrased   | rag-baseline    | 23        | 20           | 0.130                | 0.000          | -                   | -              | -         |
| distributed   | agent-baseline  | 21        | 19           | 0.476                | 0.421          | 1.000               | -              | -         |
| distributed   | evidence-engine | 21        | 19           | 0.095                | 0.000          | -                   | -              | -         |
| distributed   | rag-baseline    | 21        | 19           | 0.048                | 0.000          | -                   | 1.000          | 1.000     |
| complex       | agent-baseline  | 22        | 20           | 0.455                | 0.400          | 1.000               | -              | -         |
| complex       | evidence-engine | 22        | 20           | 0.136                | 0.150          | 0.333               | -              | -         |
| complex       | rag-baseline    | 22        | 20           | 0.136                | 0.050          | 1.000               | 1.000          | 1.000     |
| contradictory | agent-baseline  | 22        | 19           | 0.045                | 0.316          | 0.000               | -              | -         |
| contradictory | evidence-engine | 22        | 19           | 0.227                | 0.211          | 0.500               | -              | -         |
| contradictory | rag-baseline    | 22        | 19           | 0.136                | 0.158          | 0.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 2    | 2    | 17   | 0.500       | 0.105    |
| evidence-engine | duplicate       | 1    | 0    | 5    | 1.000       | 0.167    |
| evidence-engine | large_effect    | 0    | 0    | 6    | -           | 0.000    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | no                   |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit      | 24        | 6                | 24               | 18         | 0            |
| evidence-engine | paraphrased   | 23        | 3                | 23               | 20         | 0            |
| evidence-engine | distributed   | 21        | 2                | 21               | 19         | 0            |
| evidence-engine | complex       | 22        | 3                | 18               | 15         | 4            |
| evidence-engine | contradictory | 22        | 5                | 22               | 17         | 0            |
| evidence-engine | all           | 112       | 19               | 108              | 89         | 4            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.566 [0.52, 0.62] | BCa      |
| metric          | 0.735 [0.66, 0.79] | BCa      |
| measurement     | 0.376 [0.31, 0.46] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.561 [0.52, 0.60] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.170 [0.11, 0.25]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.116 [0.06, 0.18]   | BCa      | 0.054 [0.02, 0.11]    | BCa             | 112        |
| agent-baseline  | 0.375 [0.29, 0.46]   | BCa      | -0.205 [-0.30, -0.10] | BCa             | 112        |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 407          | 407      | 1.000    |
| all             | paraphrased   | 330          | 330      | 1.000    |
| all             | distributed   | 359          | 359      | 1.000    |
| all             | complex       | 841          | 841      | 1.000    |
| all             | contradictory | 357          | 357      | 1.000    |
| all             | all           | 2294         | 2294     | 1.000    |
| author_claim    | explicit      | 46           | 46       | 1.000    |
| author_claim    | paraphrased   | 42           | 42       | 1.000    |
| author_claim    | distributed   | 40           | 40       | 1.000    |
| author_claim    | complex       | 42           | 42       | 1.000    |
| author_claim    | contradictory | 42           | 42       | 1.000    |
| author_claim    | all           | 212          | 212      | 1.000    |
| condition       | explicit      | 181          | 181      | 1.000    |
| condition       | paraphrased   | 155          | 155      | 1.000    |
| condition       | distributed   | 180          | 180      | 1.000    |
| condition       | complex       | 291          | 291      | 1.000    |
| condition       | contradictory | 180          | 180      | 1.000    |
| condition       | all           | 987          | 987      | 1.000    |
| measurement     | explicit      | 67           | 67       | 1.000    |
| measurement     | paraphrased   | 56           | 56       | 1.000    |
| measurement     | distributed   | 59           | 59       | 1.000    |
| measurement     | complex       | 338          | 338      | 1.000    |
| measurement     | contradictory | 62           | 62       | 1.000    |
| measurement     | all           | 582          | 582      | 1.000    |
| metric          | explicit      | 113          | 113      | 1.000    |
| metric          | paraphrased   | 77           | 77       | 1.000    |
| metric          | distributed   | 80           | 80       | 1.000    |
| metric          | complex       | 170          | 170      | 1.000    |
| metric          | contradictory | 73           | 73       | 1.000    |
| metric          | all           | 513          | 513      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| regex_author_claim@2#fd7877790c48 | 106     | 106             | 106    | 106            |
| regex_condition@2#0a5bf730763c    | 129     | 126             | 129    | 126            |
| regex_measurement@2#e2d17eb260ea  | 137     | 135             | 137    | 135            |
| regex_metric@2#0affe2d9ce77       | 80      | 79              | 80     | 79             |

Facts no extractor found: condition 190, measurement 447, metric 56

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_author_claim@2#fd7877790c48 | all             | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_condition@2#0a5bf730763c    | condition       | all     | 129     | 316     | 126       | 0.977       | 0.399    | 0.566 | 1.000           | -                      | 129    | 126            |
| regex_condition@2#0a5bf730763c    | all             | all     | 129     | 316     | 126       | 0.977       | 0.399    | 0.566 | 1.000           | -                      | 129    | 126            |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 137     | 582     | 135       | 0.985       | 0.232    | 0.376 | 1.000           | 1.000                  | 137    | 135            |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 137     | 582     | 135       | 0.985       | 0.232    | 0.376 | 1.000           | -                      | 137    | 135            |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 80      | 135     | 79        | 0.988       | 0.585    | 0.735 | 1.000           | -                      | 80     | 79             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 80      | 135     | 79        | 0.988       | 0.585    | 0.735 | 1.000           | -                      | 80     | 79             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| regex_author_claim@2#fd7877790c48 | 112     | 0             | 0              | 0               | 1.430     |
| regex_condition@2#0a5bf730763c    | 112     | 0             | 0              | 0               | 1.362     |
| regex_measurement@2#e2d17eb260ea  | 112     | 0             | 0              | 0               | 1.433     |
| regex_metric@2#0affe2d9ce77       | 112     | 0             | 0              | 0               | 1.373     |
| regex_screen@1#858a6ebc69c6       | 112     | 0             | 0              | 0               | 1.330     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 135     | 1.205       |
| calls            | 560     | 5.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 11.649  | 0.104       |

## Funnel

Strategy `all` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 5.000          |
| model_calls   | 0.000          |
| input_tokens  | 0.000          |
| output_tokens | 0.000          |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 112         |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 3    | 0    | 3    | 0.972       | 1.000    |

Screened out wrongly: none
