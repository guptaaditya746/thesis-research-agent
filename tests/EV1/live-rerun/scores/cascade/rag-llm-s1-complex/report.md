# Evaluation of run rag-llm-s1-complex on rag-llm-s1-a2b5bbc1

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 271     | 242     | 229       | 0.845       | 0.946    | 0.893 | 1.000           |
| all             | all     | 271     | 242     | 229       | 0.845       | 0.946    | 0.893 | 1.000           |
| author_claim    | complex | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 43      | 33      | 30        | 0.698       | 0.909    | 0.789 | 1.000           |
| condition       | all     | 43      | 33      | 30        | 0.698       | 0.909    | 0.789 | 1.000           |
| measurement     | complex | 178     | 170     | 160       | 0.899       | 0.941    | 0.920 | 1.000           |
| measurement     | all     | 178     | 170     | 160       | 0.899       | 0.941    | 0.920 | 1.000           |
| metric          | complex | 39      | 28      | 28        | 0.718       | 1.000    | 0.836 | 1.000           |
| metric          | all     | 39      | 28      | 28        | 0.718       | 1.000    | 0.836 | 1.000           |

Facts no item matched: 13; items matching no fact: 42.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 160                    | 0.900                  | 0.900                     | 1.000             | 0.900             | 0.956          | 11        | 0.091       |
| all     | 160                    | 0.900                  | 0.900                     | 1.000             | 0.900             | 0.956          | 11        | 0.091       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |
| rag-baseline    | refuted | mixed      | no              | 11        | 11           | 0.182                | 0.545          | 0.333               | 1.000          |
| agent-baseline  | mixed   | mixed      | yes             | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| complex | agent-baseline  | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| complex | evidence-engine | 11        | 11           | 0.909                | 1.000          | 0.909               | -              |
| complex | rag-baseline    | 11        | 11           | 0.182                | 0.545          | 0.333               | 1.000          |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 1    | 0    | 0.000       | -        |
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
| condition       | 0.789 [0.66, 0.86] | BCa      |
| metric          | 0.836 [0.78, 0.90] | BCa      |
| measurement     | 0.920 [0.87, 0.96] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.893 [0.85, 0.93] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.909 [0.55, 1.00]   | BCa      | -                     | -               |
| rag-baseline    | 0.182 [0.00, 0.55]   | BCa      | 0.727 [0.36, 0.91]    | BCa             |
| agent-baseline  | 1.000 [n/a]          | -        | -0.091 [-0.45, 0.00]  | BCa             |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 580          | 580      | 1.000    |
| all             | all     | 580          | 580      | 1.000    |
| author_claim    | complex | 22           | 22       | 1.000    |
| author_claim    | all     | 22           | 22       | 1.000    |
| condition       | complex | 221          | 221      | 1.000    |
| condition       | all     | 221          | 221      | 1.000    |
| measurement     | complex | 170          | 170      | 1.000    |
| measurement     | all     | 170          | 170      | 1.000    |
| metric          | complex | 167          | 167      | 1.000    |
| metric          | all     | 167          | 167      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 11      | 11              | 0      | 0              |
| llm_condition@1#134ab1a38338      | 33      | 30              | 25     | 22             |
| llm_measurement@1#5212fc43026f    | 160     | 153             | 26     | 19             |
| llm_metric@1#1ca12a572ef8         | 26      | 26              | 5      | 5              |
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 0      | 0              |
| regex_condition@2#80486860164a    | 18      | 8               | 10     | 0              |
| regex_measurement@2#9edb306c5b05  | 152     | 141             | 18     | 7              |
| regex_metric@2#67f41f33eff7       | 34      | 23              | 13     | 2              |

Facts no extractor found: condition 3, measurement 10

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 33      | 33      | 30        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 25     | 22             |
| llm_condition@1#134ab1a38338      | all             | all     | 33      | 33      | 30        | 0.909       | 0.909    | 0.909 | 1.000           | -                      | 25     | 22             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 160     | 170     | 153       | 0.956       | 0.900    | 0.927 | 1.000           | 0.902                  | 26     | 19             |
| llm_measurement@1#5212fc43026f    | all             | all     | 160     | 170     | 153       | 0.956       | 0.900    | 0.927 | 1.000           | -                      | 26     | 19             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 26      | 28      | 26        | 1.000       | 0.929    | 0.963 | 1.000           | -                      | 5      | 5              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 26      | 28      | 26        | 1.000       | 0.929    | 0.963 | 1.000           | -                      | 5      | 5              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 18      | 33      | 8         | 0.444       | 0.242    | 0.314 | 1.000           | -                      | 10     | 0              |
| regex_condition@2#80486860164a    | all             | all     | 18      | 33      | 8         | 0.444       | 0.242    | 0.314 | 1.000           | -                      | 10     | 0              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 152     | 170     | 141       | 0.928       | 0.829    | 0.876 | 1.000           | 0.908                  | 18     | 7              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 152     | 170     | 141       | 0.928       | 0.829    | 0.876 | 1.000           | -                      | 18     | 7              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 34      | 28      | 23        | 0.676       | 0.821    | 0.742 | 1.000           | -                      | 13     | 2              |
| regex_metric@2#67f41f33eff7       | all             | all     | 34      | 28      | 23        | 0.676       | 0.821    | 0.742 | 1.000           | -                      | 13     | 2              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 11      | 11            | 13748          | 1333            | 37.527    |
| llm_condition@1#134ab1a38338      | 11      | 17            | 22957          | 3101            | 83.407    |
| llm_measurement@1#5212fc43026f    | 11      | 22            | 45109          | 26073           | 644.211   |
| llm_metric@1#1ca12a572ef8         | 11      | 13            | 17711          | 2382            | 63.809    |
| llm_screen@1#6bec6abaf6a0         | 11      | 11            | 12527          | 921             | 27.825    |
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.075     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.077     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.223     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.080     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.075     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 44      | 4.000       |
| calls            | 110     | 10.000      |
| input_tokens     | 112052  | 10186.545   |
| made_model_calls | 74      | 6.727       |
| model_calls      | 74      | 6.727       |
| output_tokens    | 33810   | 3073.636    |
| seconds          | 858.070 | 78.006      |

## Funnel

Strategy `all` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.727          |
| input_tokens  | 10186.545      |
| output_tokens | 3073.636       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 11          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
