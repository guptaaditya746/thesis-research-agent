# Evaluation of run rag-claude-pilot-mixed-escalate on rag-claude-pilot-931cb13b

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit    | 8       | 8       | 7         | 0.875       | 0.875    | 0.875 | 1.000           |
| all             | paraphrased | 2       | 10      | 2         | 1.000       | 0.200    | 0.333 | 1.000           |
| all             | distributed | 6       | 10      | 6         | 1.000       | 0.600    | 0.750 | 1.000           |
| all             | all         | 16      | 28      | 15        | 0.938       | 0.536    | 0.682 | 1.000           |
| author_claim    | explicit    | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit    | 3       | 3       | 2         | 0.667       | 0.667    | 0.667 | 1.000           |
| condition       | paraphrased | 1       | 4       | 1         | 1.000       | 0.250    | 0.400 | 1.000           |
| condition       | distributed | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 1.000           |
| condition       | all         | 6       | 11      | 5         | 0.833       | 0.455    | 0.588 | 1.000           |
| measurement     | explicit    | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | paraphrased | 0       | 4       | 0         | 0.000       | 0.000    | 0.000 | -               |
| measurement     | distributed | 2       | 4       | 2         | 1.000       | 0.500    | 0.667 | 1.000           |
| measurement     | all         | 5       | 11      | 5         | 1.000       | 0.455    | 0.625 | 1.000           |
| metric          | explicit    | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | paraphrased | 0       | 1       | 0         | 0.000       | 0.000    | 0.000 | -               |
| metric          | distributed | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all         | 2       | 3       | 2         | 1.000       | 0.667    | 0.800 | 1.000           |

Facts no item matched: 13; items matching no fact: 1.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit    | 3                      | 0.667                  | 0.667                     | 1.000             | 0.667             | 1.000          | 1         | 1.000       |
| paraphrased | 0                      | -                      | -                         | -                 | -                 | -              | 1         | 0.000       |
| distributed | 2                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 1         | 1.000       |
| all         | 5                      | 0.800                  | 0.800                     | 1.000             | 0.800             | 1.000          | 3         | 0.667       |

## C. Synthesis

| system          | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | supported | mixed      | no              | 3         | 3            | 0.667                | 0.667          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| explicit    | evidence-engine | 1         | yes          | 1.000                | 1.000          | 1.000               | -              | -         |
| paraphrased | evidence-engine | 1         | yes          | 0.000                | 0.000          | -                   | -              | -         |
| distributed | evidence-engine | 1         | yes          | 1.000                | 1.000          | 1.000               | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
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
| condition       | 0.588 [0.40, 0.67] | BCa      |
| metric          | 0.800 [0.00, 1.00] | BCa      |
| measurement     | 0.625 [0.00, 1.00] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.682 [0.33, 0.83] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.667 [0.00, 1.00]   | BCa      | -                     | -               | -          |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | explicit    | 18           | 18       | 1.000    |
| all             | paraphrased | 20           | 20       | 1.000    |
| all             | distributed | 24           | 24       | 1.000    |
| all             | all         | 62           | 62       | 1.000    |
| author_claim    | explicit    | 2            | 2        | 1.000    |
| author_claim    | paraphrased | 2            | 2        | 1.000    |
| author_claim    | distributed | 2            | 2        | 1.000    |
| author_claim    | all         | 6            | 6        | 1.000    |
| condition       | explicit    | 7            | 7        | 1.000    |
| condition       | paraphrased | 8            | 8        | 1.000    |
| condition       | distributed | 12           | 12       | 1.000    |
| condition       | all         | 27           | 27       | 1.000    |
| measurement     | explicit    | 3            | 3        | 1.000    |
| measurement     | paraphrased | 4            | 4        | 1.000    |
| measurement     | distributed | 4            | 4        | 1.000    |
| measurement     | all         | 11           | 11       | 1.000    |
| metric          | explicit    | 6            | 6        | 1.000    |
| metric          | paraphrased | 6            | 6        | 1.000    |
| metric          | distributed | 6            | 6        | 1.000    |
| metric          | all         | 18           | 18       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 0       | 0               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 5       | 4               | 4      | 3              |
| llm_measurement@1#02bd5a7ab104    | 5       | 5               | 5      | 5              |
| llm_metric@1#41e1e53a1fc4         | 1       | 1               | 1      | 1              |
| regex_author_claim@2#fd7877790c48 | 3       | 3               | 3      | 3              |
| regex_condition@2#0a5bf730763c    | 2       | 2               | 1      | 1              |
| regex_measurement@2#e2d17eb260ea  | 0       | 0               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 1       | 1               | 1      | 1              |

Facts no extractor found: condition 6, measurement 6, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | all             | all     | 0       | 28      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 5       | 11      | 4         | 0.800       | 0.364    | 0.500 | 1.000           | -                      | 4      | 3              |
| llm_condition@1#45b3761c700e      | all             | all     | 5       | 11      | 4         | 0.800       | 0.364    | 0.500 | 1.000           | -                      | 4      | 3              |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 5       | 7       | 5         | 1.000       | 0.714    | 0.833 | 1.000           | 0.800                  | 5      | 5              |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 5       | 7       | 5         | 1.000       | 0.714    | 0.833 | 1.000           | -                      | 5      | 5              |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 1      | 1              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 3      | 3              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 3      | 3              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 2       | 11      | 2         | 1.000       | 0.182    | 0.308 | 1.000           | -                      | 1      | 1              |
| regex_condition@2#0a5bf730763c    | all             | all     | 2       | 11      | 2         | 1.000       | 0.182    | 0.308 | 1.000           | -                      | 1      | 1              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 0       | 11      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 0       | 11      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 1       | 3       | 1         | 1.000       | 0.333    | 0.500 | 1.000           | -                      | 1      | 1              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 1       | 3       | 1         | 1.000       | 0.333    | 0.500 | 1.000           | -                      | 1      | 1              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#45b3761c700e      | 3       | 3             | 3615           | 369             | 0.022     |
| llm_measurement@1#02bd5a7ab104    | 2       | 4             | 5500           | 935             | 0.013     |
| llm_metric@1#41e1e53a1fc4         | 1       | 1             | 1134           | 90              | 0.006     |
| llm_screen@1#41b0d6e6793f         | 3       | 3             | 2897           | 293             | 0.021     |
| regex_author_claim@2#fd7877790c48 | 3       | 0             | 0              | 0               | 0.018     |
| regex_condition@2#0a5bf730763c    | 3       | 0             | 0              | 0               | 0.018     |
| regex_measurement@2#e2d17eb260ea  | 3       | 0             | 0              | 0               | 0.018     |
| regex_metric@2#0affe2d9ce77       | 3       | 0             | 0              | 0               | 0.018     |
| regex_screen@1#858a6ebc69c6       | 3       | 0             | 0              | 0               | 0.019     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 24      | 8.000       |
| calls            | 24      | 8.000       |
| input_tokens     | 13146   | 4382.000    |
| made_model_calls | 0       | 0.000       |
| model_calls      | 11      | 3.667       |
| output_tokens    | 1687    | 562.333     |
| seconds          | 0.345   | 0.115       |

## Funnel

Strategy `gaps` over 3 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 8.000          |
| model_calls   | 3.667          |
| input_tokens  | 4382.000       |
| output_tokens | 562.333        |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 2           |
| exhausted       | 1           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 3           | 3    | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
