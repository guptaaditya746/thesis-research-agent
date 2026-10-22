# Evaluation of run rag-claude-pilot-contradictory on rag-claude-pilot-3ef3b916

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: contradictory

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | contradictory | 24      | 28      | 22        | 0.917       | 0.786    | 0.846 | 1.000           |
| all             | all           | 24      | 28      | 22        | 0.917       | 0.786    | 0.846 | 1.000           |
| author_claim    | contradictory | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 12      | 11      | 10        | 0.833       | 0.909    | 0.870 | 1.000           |
| condition       | all           | 12      | 11      | 10        | 0.833       | 0.909    | 0.870 | 1.000           |
| measurement     | contradictory | 7       | 11      | 7         | 1.000       | 0.636    | 0.778 | 1.000           |
| measurement     | all           | 7       | 11      | 7         | 1.000       | 0.636    | 0.778 | 1.000           |
| metric          | contradictory | 2       | 3       | 2         | 1.000       | 0.667    | 0.800 | 1.000           |
| metric          | all           | 2       | 3       | 2         | 1.000       | 0.667    | 0.800 | 1.000           |

Facts no item matched: 6; items matching no fact: 2.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| contradictory | 7                      | 0.857                  | 0.857                     | 1.000             | 0.857             | 1.000          | 3         | 0.667       |
| all           | 7                      | 0.857                  | 0.857                     | 1.000             | 0.857             | 1.000          | 3         | 0.667       |

## C. Synthesis

| system          | label     | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|-----------------|-----------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| evidence-engine | supported | mixed      | no              | 3         | 3            | 0.667                | 0.667          | 1.000               | -              | -         |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted as untraced (span overlap only: not "same study or condition", not entailment; the passage need not support the claim); overlap is the lenient share, over a placement of any role, a condition label included (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   | overlap   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|-----------|
| contradictory | evidence-engine | 3         | 3            | 0.667                | 0.667          | 1.000               | -              | -         |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 2    | 0    | 1    | 1.000       | 0.667    |
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
| condition       | 0.870 [0.67, 1.00] | BCa      |
| metric          | 0.800 [0.00, 1.00] | BCa      |
| measurement     | 0.778 [0.00, 1.00] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.846 [0.67, 0.93] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in both systems):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   | paired_n   |
|-----------------|----------------------|----------|-----------------------|-----------------|------------|
| evidence-engine | 0.667 [0.00, 1.00]   | BCa      | -                     | -               | -          |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | contradictory | 66           | 66       | 1.000    |
| all             | all           | 66           | 66       | 1.000    |
| author_claim    | contradictory | 6            | 6        | 1.000    |
| author_claim    | all           | 6            | 6        | 1.000    |
| condition       | contradictory | 31           | 31       | 1.000    |
| condition       | all           | 31           | 31       | 1.000    |
| measurement     | contradictory | 11           | 11       | 1.000    |
| measurement     | all           | 11           | 11       | 1.000    |
| metric          | contradictory | 18           | 18       | 1.000    |
| metric          | all           | 18           | 18       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | 3       | 3               | 0      | 0              |
| llm_condition@1#45b3761c700e      | 11      | 10              | 8      | 7              |
| llm_measurement@1#02bd5a7ab104    | 7       | 7               | 3      | 3              |
| llm_metric@1#41e1e53a1fc4         | 2       | 2               | 1      | 1              |
| regex_author_claim@2#fd7877790c48 | 3       | 3               | 0      | 0              |
| regex_condition@2#0a5bf730763c    | 4       | 3               | 1      | 0              |
| regex_measurement@2#e2d17eb260ea  | 4       | 4               | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | 1       | 1               | 0      | 0              |

Facts no extractor found: condition 1, measurement 4, metric 1

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#be3c17081ff9   | author_claim    | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#be3c17081ff9   | all             | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#45b3761c700e      | condition       | all     | 11      | 11      | 10        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 8      | 7              |
| llm_condition@1#45b3761c700e      | all             | all     | 11      | 11      | 10        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 8      | 7              |
| llm_measurement@1#02bd5a7ab104    | measurement     | all     | 7       | 11      | 7         | 1.000       | 0.636    | 0.778 | 1.000           | 0.857                  | 3      | 3              |
| llm_measurement@1#02bd5a7ab104    | all             | all     | 7       | 11      | 7         | 1.000       | 0.636    | 0.778 | 1.000           | -                      | 3      | 3              |
| llm_metric@1#41e1e53a1fc4         | metric          | all     | 2       | 3       | 2         | 1.000       | 0.667    | 0.800 | 1.000           | -                      | 1      | 1              |
| llm_metric@1#41e1e53a1fc4         | all             | all     | 2       | 3       | 2         | 1.000       | 0.667    | 0.800 | 1.000           | -                      | 1      | 1              |
| regex_author_claim@2#fd7877790c48 | author_claim    | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#fd7877790c48 | all             | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#0a5bf730763c    | condition       | all     | 4       | 11      | 3         | 0.750       | 0.273    | 0.400 | 1.000           | -                      | 1      | 0              |
| regex_condition@2#0a5bf730763c    | all             | all     | 4       | 11      | 3         | 0.750       | 0.273    | 0.400 | 1.000           | -                      | 1      | 0              |
| regex_measurement@2#e2d17eb260ea  | measurement     | all     | 4       | 11      | 4         | 1.000       | 0.364    | 0.533 | 1.000           | 1.000                  | 0      | 0              |
| regex_measurement@2#e2d17eb260ea  | all             | all     | 4       | 11      | 4         | 1.000       | 0.364    | 0.533 | 1.000           | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | metric          | all     | 1       | 3       | 1         | 1.000       | 0.333    | 0.500 | 1.000           | -                      | 0      | 0              |
| regex_metric@2#0affe2d9ce77       | all             | all     | 1       | 3       | 1         | 1.000       | 0.333    | 0.500 | 1.000           | -                      | 0      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#be3c17081ff9   | 3       | 3             | 3405           | 356             | 9.936     |
| llm_condition@1#45b3761c700e      | 3       | 5             | 6121           | 969             | 25.665    |
| llm_measurement@1#02bd5a7ab104    | 3       | 6             | 8855           | 1829            | 47.247    |
| llm_metric@1#41e1e53a1fc4         | 3       | 3             | 3717           | 188             | 6.002     |
| llm_screen@1#41b0d6e6793f         | 3       | 3             | 3072           | 285             | 8.730     |
| regex_author_claim@2#fd7877790c48 | 3       | 0             | 0              | 0               | 0.050     |
| regex_condition@2#0a5bf730763c    | 3       | 0             | 0              | 0               | 0.043     |
| regex_measurement@2#e2d17eb260ea  | 3       | 0             | 0              | 0               | 0.051     |
| regex_metric@2#0affe2d9ce77       | 3       | 0             | 0              | 0               | 0.043     |
| regex_screen@1#858a6ebc69c6       | 3       | 0             | 0              | 0               | 0.049     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 30      | 10.000      |
| input_tokens     | 25170   | 8390.000    |
| made_model_calls | 20      | 6.667       |
| model_calls      | 20      | 6.667       |
| output_tokens    | 3627    | 1209.000    |
| seconds          | 98.029  | 32.676      |

## Funnel

Strategy `all` over 3 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.667          |
| input_tokens  | 8390.000       |
| output_tokens | 1209.000       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 3           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 3           | 2    | 0    | 1    | 0    | 1.000       | 0.667    |

Screened out wrongly: S002
