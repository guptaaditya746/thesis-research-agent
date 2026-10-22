# Evaluation of run rag-tpl-hard-mixed-escalate on rag-tpl-hard-b1c0fdfe

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 149     | 181     | 147       | 0.987       | 0.812    | 0.891 | 1.000           |
| all             | paraphrased   | 59      | 155     | 58        | 0.983       | 0.374    | 0.542 | 1.000           |
| all             | distributed   | 133     | 159     | 131       | 0.985       | 0.824    | 0.897 | 1.000           |
| all             | complex       | 202     | 476     | 200       | 0.990       | 0.420    | 0.590 | 1.000           |
| all             | contradictory | 134     | 168     | 130       | 0.970       | 0.774    | 0.861 | 1.000           |
| all             | all           | 677     | 1139    | 666       | 0.984       | 0.585    | 0.733 | 1.000           |
| author_claim    | explicit      | 23      | 23      | 23        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 21      | 21      | 21        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 21      | 21      | 21        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 21      | 21      | 21        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 53      | 68      | 51        | 0.962       | 0.750    | 0.843 | 1.000           |
| condition       | paraphrased   | 27      | 57      | 26        | 0.963       | 0.456    | 0.619 | 1.000           |
| condition       | distributed   | 48      | 60      | 46        | 0.958       | 0.767    | 0.852 | 1.000           |
| condition       | complex       | 33      | 67      | 32        | 0.970       | 0.478    | 0.640 | 1.000           |
| condition       | contradictory | 46      | 64      | 46        | 1.000       | 0.719    | 0.836 | 1.000           |
| condition       | all           | 207     | 316     | 201       | 0.971       | 0.636    | 0.769 | 1.000           |
| measurement     | explicit      | 50      | 67      | 50        | 1.000       | 0.746    | 0.855 | 1.000           |
| measurement     | paraphrased   | 8       | 56      | 8         | 1.000       | 0.143    | 0.250 | 1.000           |
| measurement     | distributed   | 45      | 59      | 45        | 1.000       | 0.763    | 0.865 | 1.000           |
| measurement     | complex       | 106     | 338     | 106       | 1.000       | 0.314    | 0.477 | 1.000           |
| measurement     | contradictory | 46      | 62      | 42        | 0.913       | 0.677    | 0.778 | 1.000           |
| measurement     | all           | 255     | 582     | 251       | 0.984       | 0.431    | 0.600 | 1.000           |
| metric          | explicit      | 23      | 23      | 23        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased   | 3       | 21      | 3         | 1.000       | 0.143    | 0.250 | 1.000           |
| metric          | distributed   | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | complex       | 42      | 50      | 41        | 0.976       | 0.820    | 0.891 | 1.000           |
| metric          | contradictory | 21      | 21      | 21        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 109     | 135     | 108       | 0.991       | 0.800    | 0.885 | 1.000           |

Facts no item matched: 473; items matching no fact: 11.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 50                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 22        | 1.000       |
| paraphrased   | 8                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.150       |
| distributed   | 45                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 19        | 1.000       |
| complex       | 106                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.000       |
| contradictory | 42                     | 0.976                  | 0.976                     | 1.000             | 0.976             | 1.000          | 19        | 0.895       |
| all           | 251                    | 0.996                  | 0.996                     | 1.000             | 0.996             | 1.000          | 100       | 0.610       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 112       | 100          | 0.661                | 0.660          | 0.939               | -              | -         |
| rag-baseline    | mixed   | mixed      | yes             | 112       | 100          | 0.116                | 0.050          | 0.400               | 1.000          | 1.000     |
| agent-baseline  | mixed   | mixed      | yes             | 112       | 100          | 0.375                | 0.380          | 0.842               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit      | agent-baseline  | 24        | 22           | 0.417                | 0.364          | 1.000               | -              | -         |
| explicit      | evidence-engine | 24        | 22           | 1.000                | 1.000          | 1.000               | -              | -         |
| explicit      | rag-baseline    | 24        | 22           | 0.125                | 0.045          | 1.000               | 1.000          | 1.000     |
| paraphrased   | agent-baseline  | 23        | 20           | 0.478                | 0.400          | 1.000               | -              | -         |
| paraphrased   | evidence-engine | 23        | 20           | 0.261                | 0.150          | 1.000               | -              | -         |
| paraphrased   | rag-baseline    | 23        | 20           | 0.130                | 0.000          | -                   | -              | -         |
| distributed   | agent-baseline  | 21        | 19           | 0.476                | 0.421          | 1.000               | -              | -         |
| distributed   | evidence-engine | 21        | 19           | 1.000                | 1.000          | 1.000               | -              | -         |
| distributed   | rag-baseline    | 21        | 19           | 0.048                | 0.000          | -                   | 1.000          | 1.000     |
| complex       | agent-baseline  | 22        | 20           | 0.455                | 0.400          | 1.000               | -              | -         |
| complex       | evidence-engine | 22        | 20           | 0.136                | 0.150          | 0.333               | -              | -         |
| complex       | rag-baseline    | 22        | 20           | 0.136                | 0.050          | 1.000               | 1.000          | 1.000     |
| contradictory | agent-baseline  | 22        | 19           | 0.045                | 0.316          | 0.000               | -              | -         |
| contradictory | evidence-engine | 22        | 19           | 0.909                | 1.000          | 0.895               | -              | -         |
| contradictory | rag-baseline    | 22        | 19           | 0.136                | 0.158          | 0.000               | 1.000          | 1.000     |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 17   | 2    | 2    | 0.895       | 0.895    |
| evidence-engine | duplicate       | 4    | 0    | 2    | 1.000       | 0.667    |
| evidence-engine | large_effect    | 5    | 0    | 1    | 1.000       | 0.833    |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | no                   |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | explicit      | 24        | 24               | 24               | 0          | 0            |
| evidence-engine | paraphrased   | 23        | 6                | 23               | 17         | 0            |
| evidence-engine | distributed   | 21        | 21               | 21               | 0          | 0            |
| evidence-engine | complex       | 22        | 3                | 18               | 15         | 4            |
| evidence-engine | contradictory | 22        | 20               | 22               | 2          | 0            |
| evidence-engine | all           | 112       | 74               | 108              | 34         | 4            |

Not attributed (not this oracle's counterpart): rag-baseline, agent-baseline

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.769 [0.73, 0.80] | BCa      |
| metric          | 0.885 [0.84, 0.92] | BCa      |
| measurement     | 0.600 [0.53, 0.66] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.733 [0.68, 0.77] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.661 [0.56, 0.74]   | BCa      | -                     | -               | -          |
| rag-baseline    | 0.116 [0.06, 0.18]   | BCa      | 0.545 [0.45, 0.63]    | BCa             | 112        |
| agent-baseline  | 0.375 [0.29, 0.46]   | BCa      | 0.286 [0.16, 0.40]    | BCa             | 112        |

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
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 81      | 81              | 78     | 78             |
| llm_measurement@1#02bd5a7ab104    | 131     | 130             | 118    | 117            |
| llm_metric@1#41e1e53a1fc4         | 29      | 29              | 29     | 29             |
| regex_author_claim@2#fd7877790c48 | 106     | 106             | 106    | 106            |
| regex_condition@2#0a5bf730763c    | 129     | 123             | 126    | 120            |
| regex_measurement@2#e2d17eb260ea  | 137     | 134             | 124    | 121            |
| regex_metric@2#0affe2d9ce77       | 80      | 79              | 80     | 79             |

Facts no extractor found: condition 115, measurement 331, metric 27

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 1139    | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 81      | 170     | 81        | 1.000       | 0.476    | 0.645 | 1.000           | -                      | 78     | 78             |
| llm_condition@1#45b3761c700e      | all             | all     | 81      | 170     | 81        | 1.000       | 0.476    | 0.645 | 1.000           | -                      | 78     | 78             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 131     | 223     | 130       | 0.992       | 0.583    | 0.734 | 1.000           | 1.000                  | 118    | 117            |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 131     | 223     | 130       | 0.992       | 0.583    | 0.734 | 1.000           | -                      | 118    | 117            |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 29      | 43      | 29        | 1.000       | 0.674    | 0.806 | 1.000           | -                      | 29     | 29             |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 29      | 43      | 29        | 1.000       | 0.674    | 0.806 | 1.000           | -                      | 29     | 29             |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_author_claim@2#fd7877790c48 | all             | all     | 106     | 106     | 106       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 106    | 106            |
| regex_condition@2#0a5bf730763c    | condition       | all     | 129     | 316     | 123       | 0.953       | 0.389    | 0.553 | 1.000           | -                      | 126    | 120            |
| regex_condition@2#0a5bf730763c    | all             | all     | 129     | 316     | 123       | 0.953       | 0.389    | 0.553 | 1.000           | -                      | 126    | 120            |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 137     | 582     | 134       | 0.978       | 0.230    | 0.373 | 1.000           | 0.993                  | 124    | 121            |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 137     | 582     | 134       | 0.978       | 0.230    | 0.373 | 1.000           | -                      | 124    | 121            |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 80      | 135     | 79        | 0.988       | 0.585    | 0.735 | 1.000           | -                      | 80     | 79             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 80      | 135     | 79        | 0.988       | 0.585    | 0.735 | 1.000           | -                      | 80     | 79             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 64      | 101           | 92364          | 9544            | 238.063   |
| llm_measurement@1#02bd5a7ab104    | 62      | 121           | 137896         | 24148           | 605.405   |
| llm_metric@1#41e1e53a1fc4         | 35      | 38            | 39551          | 3824            | 82.970    |
| llm_screen@1#41b0d6e6793f         | 112     | 112           | 83485          | 8405            | 186.949   |
| regex_author_claim@2#fd7877790c48 | 109     | 0             | 0              | 0               | 1.582     |
| regex_condition@2#0a5bf730763c    | 109     | 0             | 0              | 0               | 1.445     |
| regex_measurement@2#e2d17eb260ea  | 109     | 0             | 0              | 0               | 1.640     |
| regex_metric@2#0affe2d9ce77       | 109     | 0             | 0              | 0               | 1.507     |
| regex_screen@1#858a6ebc69c6       | 112     | 0             | 0              | 0               | 1.367     |

## Cost

| measure          | total    | per_paper   |
|------------------|----------|-------------|
| cached_calls     | 171      | 1.527       |
| calls            | 821      | 7.330       |
| input_tokens     | 309734   | 2765.482    |
| made_model_calls | 324      | 2.893       |
| model_calls      | 372      | 3.321       |
| output_tokens    | 41116    | 367.107     |
| seconds          | 1127.762 | 10.069      |

## Funnel

Strategy `gaps` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.330          |
| model_calls   | 3.321          |
| input_tokens  | 3154.429       |
| output_tokens | 410.009        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 11          |
| 1               | 55          |
| exhausted       | 43          |
| skipped         | 3           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 3    | 0    | 3    | 0.972       | 1.000    |

Screened out wrongly: none
