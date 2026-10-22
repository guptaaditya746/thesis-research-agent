# Evaluation of run rag-tpl-s1-contradictory on rag-tpl-s1-56b0bc02

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 124     | 162     | 115       | 0.927       | 0.710    | 0.804 | 1.000           |
| all             | all           | 124     | 162     | 115       | 0.927       | 0.710    | 0.804 | 1.000           |
| author_claim    | contradictory | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           |
| author_claim    | all           | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           |
| condition       | contradictory | 41      | 61      | 40        | 0.976       | 0.656    | 0.784 | 1.000           |
| condition       | all           | 41      | 61      | 40        | 0.976       | 0.656    | 0.784 | 1.000           |
| measurement     | contradictory | 45      | 61      | 37        | 0.822       | 0.607    | 0.698 | 1.000           |
| measurement     | all           | 45      | 61      | 37        | 0.822       | 0.607    | 0.698 | 1.000           |
| metric          | contradictory | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           |
| metric          | all           | 19      | 20      | 19        | 1.000       | 0.950    | 0.974 | 1.000           |

Facts no item matched: 47; items matching no fact: 9.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 37                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.800       |
| all           | 37                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.800       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 0.800                | 0.900          | 0.889               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| contradictory | evidence-engine | 20        | 20           | 0.800                | 0.900          | 0.889               | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 16   | 0    | 4    | 1.000       | 0.800    |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | no               | yes                  |

## Attribution

Wrong studies against the oracle `oracle-synthesis`: upstream when the oracle is right (extraction or retrieval), downstream when it is wrong too (synthesis or reasoning).

| system          | level         | studies   | system_correct   | oracle_correct   | upstream   | downstream   |
|-----------------|---------------|-----------|------------------|------------------|------------|--------------|
| evidence-engine | contradictory | 20        | 16               | 20               | 4          | 0            |
| evidence-engine | all           | 20        | 16               | 20               | 4          | 0            |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.784 [0.70, 0.85] | BCa      |
| metric          | 0.974 [0.86, 1.00] | BCa      |
| measurement     | 0.698 [0.62, 0.77] | BCa      |
| author_claim    | 0.974 [0.86, 1.00] | BCa      |
| all             | 0.804 [0.73, 0.86] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.800 [0.55, 0.95]   | BCa      | -                     | -               | -          |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | contradictory | 343          | 327      | 0.953    |
| all             | all           | 343          | 327      | 0.953    |
| author_claim    | contradictory | 40           | 38       | 0.950    |
| author_claim    | all           | 40           | 38       | 0.950    |
| condition       | contradictory | 172          | 164      | 0.953    |
| condition       | all           | 172          | 164      | 0.953    |
| measurement     | contradictory | 61           | 58       | 0.951    |
| measurement     | all           | 61           | 58       | 0.951    |
| metric          | contradictory | 70           | 67       | 0.957    |
| metric          | all           | 70           | 67       | 0.957    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 15      | 15              | 15     | 15             |
| llm_measurement@1#02bd5a7ab104    | 26      | 25              | 19     | 18             |
| llm_metric@1#41e1e53a1fc4         | 2       | 2               | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | 19      | 19              | 19     | 19             |
| regex_condition@2#0a5bf730763c    | 26      | 25              | 26     | 25             |
| regex_measurement@2#e2d17eb260ea  | 26      | 19              | 19     | 12             |
| regex_metric@2#0affe2d9ce77       | 17      | 17              | 17     | 17             |

Facts no extractor found: author_claim 1, condition 21, measurement 24, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 162     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 15      | 30      | 15        | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 15     | 15             |
| llm_condition@1#45b3761c700e      | all             | all     | 15      | 30      | 15        | 1.000       | 0.500    | 0.667 | 1.000           | -                      | 15     | 15             |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 26      | 36      | 25        | 0.962       | 0.694    | 0.806 | 1.000           | 1.000                  | 19     | 18             |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 26      | 36      | 25        | 0.962       | 0.694    | 0.806 | 1.000           | -                      | 19     | 18             |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 2      | 2              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 19      | 19      | 19        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 19     | 19             |
| regex_author_claim@2#fd7877790c48 | all             | all     | 19      | 19      | 19        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 19     | 19             |
| regex_condition@2#0a5bf730763c    | condition       | all     | 26      | 58      | 25        | 0.962       | 0.431    | 0.595 | 1.000           | -                      | 26     | 25             |
| regex_condition@2#0a5bf730763c    | all             | all     | 26      | 58      | 25        | 0.962       | 0.431    | 0.595 | 1.000           | -                      | 26     | 25             |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 26      | 58      | 19        | 0.731       | 0.328    | 0.452 | 1.000           | 1.000                  | 19     | 12             |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 26      | 58      | 19        | 0.731       | 0.328    | 0.452 | 1.000           | -                      | 19     | 12             |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 17      | 19      | 17        | 1.000       | 0.895    | 0.944 | 1.000           | -                      | 17     | 17             |
| regex_metric@2#0affe2d9ce77       | all             | all     | 17      | 19      | 17        | 1.000       | 0.895    | 0.944 | 1.000           | -                      | 17     | 17             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 10      | 20            | 18049          | 1947            | 50.983    |
| llm_measurement@1#02bd5a7ab104    | 11      | 22            | 23908          | 4116            | 108.737   |
| llm_metric@1#41e1e53a1fc4         | 2       | 4             | 3762           | 269             | 8.018     |
| llm_screen@1#41b0d6e6793f         | 20      | 20            | 14169          | 1475            | 0.158     |
| regex_author_claim@2#fd7877790c48 | 19      | 0             | 0              | 0               | 0.146     |
| regex_condition@2#0a5bf730763c    | 19      | 0             | 0              | 0               | 0.144     |
| regex_measurement@2#e2d17eb260ea  | 19      | 0             | 0              | 0               | 0.145     |
| regex_metric@2#0affe2d9ce77       | 19      | 0             | 0              | 0               | 0.149     |
| regex_screen@1#858a6ebc69c6       | 20      | 0             | 0              | 0               | 0.159     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 116     | 5.800       |
| calls            | 139     | 6.950       |
| input_tokens     | 59888   | 2994.400    |
| made_model_calls | 46      | 2.300       |
| model_calls      | 66      | 3.300       |
| output_tokens    | 7632    | 381.600     |
| seconds          | 169.795 | 8.490       |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 6.950          |
| model_calls   | 3.300          |
| input_tokens  | 2994.400       |
| output_tokens | 390.350        |

| stopped_after   | documents   |
|-----------------|-------------|
| 0               | 7           |
| 1               | 11          |
| exhausted       | 1           |
| skipped         | 1           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 19   | 0    | 1    | 0    | 1.000       | 0.950    |

Screened out wrongly: S013
