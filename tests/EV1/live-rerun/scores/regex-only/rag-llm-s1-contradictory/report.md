# Evaluation of run rag-llm-s1-contradictory on rag-llm-s1-c1d18224

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 65      | 88      | 49        | 0.754       | 0.557    | 0.641 | 0.918           |
| all             | all           | 65      | 88      | 49        | 0.754       | 0.557    | 0.641 | 0.918           |
| author_claim    | contradictory | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 17      | 33      | 17        | 1.000       | 0.515    | 0.680 | 0.765           |
| condition       | all           | 17      | 33      | 17        | 1.000       | 0.515    | 0.680 | 0.765           |
| measurement     | contradictory | 15      | 33      | 11        | 0.733       | 0.333    | 0.458 | 1.000           |
| measurement     | all           | 15      | 33      | 11        | 0.733       | 0.333    | 0.458 | 1.000           |
| metric          | contradictory | 22      | 11      | 10        | 0.455       | 0.909    | 0.606 | 1.000           |
| metric          | all           | 22      | 11      | 10        | 0.455       | 0.909    | 0.606 | 1.000           |

Facts no item matched: 39; items matching no fact: 16.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 11                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 11        | 0.273       |
| all           | 11                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 11        | 0.273       |

## C. Synthesis

| system          | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed     | mixed      | yes             | 11        | 11           | 0.273                | 0.364          | 0.750               | -              |
| rag-baseline    | supported | mixed      | no              | 11        | 11           | 0.182                | 0.545          | 0.333               | 1.000          |
| agent-baseline  | mixed     | mixed      | yes             | 11        | 11           | 0.727                | 1.000          | 0.727               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| contradictory | agent-baseline  | 11        | 11           | 0.727                | 1.000          | 0.727               | -              |
| contradictory | evidence-engine | 11        | 11           | 0.273                | 0.364          | 0.750               | -              |
| contradictory | rag-baseline    | 11        | 11           | 0.182                | 0.545          | 0.333               | 1.000          |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 3    | 0    | 8    | 1.000       | 0.273    |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.680 [0.59, 0.78] | BCa      |
| metric          | 0.606 [0.50, 0.71] | BCa      |
| measurement     | 0.458 [0.26, 0.60] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.641 [0.55, 0.72] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.273 [0.09, 0.55]   | BCa      | -                     | -               |
| rag-baseline    | 0.182 [0.00, 0.45]   | BCa      | 0.091 [-0.27, 0.45]   | BCa             |
| agent-baseline  | 0.727 [0.36, 0.91]   | BCa      | -0.455 [-0.73, -0.18] | BCa             |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | contradictory | 304          | 304      | 1.000    |
| all             | all           | 304          | 304      | 1.000    |
| author_claim    | contradictory | 22           | 22       | 1.000    |
| author_claim    | all           | 22           | 22       | 1.000    |
| condition       | contradictory | 173          | 173      | 1.000    |
| condition       | all           | 173          | 173      | 1.000    |
| measurement     | contradictory | 33           | 33       | 1.000    |
| measurement     | all           | 33           | 33       | 1.000    |
| metric          | contradictory | 76           | 76       | 1.000    |
| metric          | all           | 76           | 76       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 11     | 11             |
| regex_condition@2#80486860164a    | 17      | 17              | 17     | 17             |
| regex_measurement@2#9edb306c5b05  | 15      | 11              | 15     | 11             |
| regex_metric@2#67f41f33eff7       | 22      | 10              | 22     | 10             |

Facts no extractor found: condition 16, measurement 22, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 11     | 11             |
| regex_condition@2#80486860164a    | condition       | all     | 17      | 33      | 17        | 1.000       | 0.515    | 0.680 | 0.765           | -                      | 17     | 17             |
| regex_condition@2#80486860164a    | all             | all     | 17      | 33      | 17        | 1.000       | 0.515    | 0.680 | 0.765           | -                      | 17     | 17             |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 15      | 33      | 11        | 0.733       | 0.333    | 0.458 | 1.000           | 1.000                  | 15     | 11             |
| regex_measurement@2#9edb306c5b05  | all             | all     | 15      | 33      | 11        | 0.733       | 0.333    | 0.458 | 1.000           | -                      | 15     | 11             |
| regex_metric@2#67f41f33eff7       | metric          | all     | 22      | 11      | 10        | 0.455       | 0.909    | 0.606 | 1.000           | -                      | 22     | 10             |
| regex_metric@2#67f41f33eff7       | all             | all     | 22      | 11      | 10        | 0.455       | 0.909    | 0.606 | 1.000           | -                      | 22     | 10             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.166     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.153     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.177     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.157     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.146     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 55      | 5.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 1.284   | 0.117       |

## Funnel

Strategy `all` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 5.000          |
| model_calls   | 0.000          |
| input_tokens  | 0.000          |
| output_tokens | 0.000          |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 11          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
