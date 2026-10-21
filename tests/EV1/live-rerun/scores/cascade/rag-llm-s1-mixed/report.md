# Evaluation of run rag-llm-s1-mixed on rag-llm-s1-0278df5c

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 12      | 10      | 9         | 0.750       | 0.900    | 0.818 | 1.000           |
| all             | paraphrased   | 18      | 18      | 16        | 0.889       | 0.889    | 0.889 | 0.938           |
| all             | distributed   | 29      | 20      | 20        | 0.690       | 1.000    | 0.816 | 1.000           |
| all             | complex       | 69      | 56      | 53        | 0.768       | 0.946    | 0.848 | 1.000           |
| all             | contradictory | 22      | 20      | 19        | 0.864       | 0.950    | 0.905 | 1.000           |
| all             | all           | 150     | 124     | 117       | 0.780       | 0.944    | 0.854 | 0.991           |
| author_claim    | explicit      | 1       | 1       | 1         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 5       | 4       | 3         | 0.600       | 0.750    | 0.667 | 1.000           |
| condition       | paraphrased   | 7       | 7       | 5         | 0.714       | 0.714    | 0.714 | 1.000           |
| condition       | distributed   | 11      | 7       | 7         | 0.636       | 1.000    | 0.778 | 1.000           |
| condition       | complex       | 11      | 7       | 7         | 0.636       | 1.000    | 0.778 | 1.000           |
| condition       | contradictory | 8       | 8       | 7         | 0.875       | 0.875    | 0.875 | 1.000           |
| condition       | all           | 42      | 33      | 29        | 0.690       | 0.879    | 0.773 | 1.000           |
| measurement     | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | paraphrased   | 7       | 7       | 7         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | distributed   | 7       | 7       | 7         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | complex       | 43      | 38      | 35        | 0.814       | 0.921    | 0.864 | 1.000           |
| measurement     | contradictory | 9       | 8       | 8         | 0.889       | 1.000    | 0.941 | 1.000           |
| measurement     | all           | 70      | 64      | 61        | 0.871       | 0.953    | 0.910 | 1.000           |
| metric          | explicit      | 2       | 1       | 1         | 0.500       | 1.000    | 0.667 | 1.000           |
| metric          | paraphrased   | 2       | 2       | 2         | 1.000       | 1.000    | 1.000 | 0.500           |
| metric          | distributed   | 8       | 3       | 3         | 0.375       | 1.000    | 0.545 | 1.000           |
| metric          | complex       | 12      | 8       | 8         | 0.667       | 1.000    | 0.800 | 1.000           |
| metric          | contradictory | 3       | 2       | 2         | 0.667       | 1.000    | 0.800 | 1.000           |
| metric          | all           | 27      | 16      | 16        | 0.593       | 1.000    | 0.744 | 0.938           |

Facts no item matched: 7; items matching no fact: 33.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 4                      | 0.750                  | 0.750                     | 1.000             | 0.750             | 1.000          | 1         | 1.000       |
| paraphrased   | 7                      | 0.714                  | 0.714                     | 1.000             | 0.714             | 1.000          | 2         | 1.000       |
| distributed   | 7                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 3         | 1.000       |
| complex       | 35                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.886          | 3         | 0.000       |
| contradictory | 8                      | 0.875                  | 0.875                     | 1.000             | 0.875             | 1.000          | 2         | 1.000       |
| all           | 61                     | 0.934                  | 0.934                     | 1.000             | 0.934             | 0.934          | 11        | 0.727       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 11        | 11           | 1.000                | 1.000          | 1.000               | -              |
| rag-baseline    | mixed   | mixed      | yes             | 11        | 11           | 0.545                | 0.545          | 1.000               | 1.000          |
| agent-baseline  | mixed   | mixed      | yes             | 11        | 11           | 0.818                | 1.000          | 0.818               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | agent-baseline  | 1         | yes          | 1.000                | 1.000          | 1.000               | -              |
| explicit      | evidence-engine | 1         | yes          | 1.000                | 1.000          | 1.000               | -              |
| explicit      | rag-baseline    | 1         | yes          | 0.000                | 0.000          | -                   | -              |
| paraphrased   | agent-baseline  | 2         | 2            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | evidence-engine | 2         | 2            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | rag-baseline    | 2         | 2            | 0.500                | 0.500          | 1.000               | 1.000          |
| distributed   | agent-baseline  | 3         | 3            | 1.000                | 1.000          | 1.000               | -              |
| distributed   | evidence-engine | 3         | 3            | 1.000                | 1.000          | 1.000               | -              |
| distributed   | rag-baseline    | 3         | 3            | 0.667                | 0.667          | 1.000               | 1.000          |
| complex       | agent-baseline  | 3         | 3            | 1.000                | 1.000          | 1.000               | -              |
| complex       | evidence-engine | 3         | 3            | 1.000                | 1.000          | 1.000               | -              |
| complex       | rag-baseline    | 3         | 3            | 1.000                | 1.000          | 1.000               | 1.000          |
| contradictory | agent-baseline  | 2         | 2            | 0.000                | 1.000          | 0.000               | -              |
| contradictory | evidence-engine | 2         | 2            | 1.000                | 1.000          | 1.000               | -              |
| contradictory | rag-baseline    | 2         | 2            | 0.000                | 0.000          | -                   | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 2    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 0    | 0    | 0    | -           | -        |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | yes              | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.773 [0.68, 0.86] | BCa      |
| metric          | 0.744 [0.62, 0.82] | BCa      |
| measurement     | 0.910 [0.86, 0.97] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.854 [0.82, 0.89] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |
| rag-baseline    | 0.545 [0.27, 0.82]   | BCa      | 0.455 [0.18, 0.73]    | BCa             |
| agent-baseline  | 0.818 [0.55, 1.00]   | BCa      | 0.182 [0.00, 0.45]    | BCa             |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 23           | 23       | 1.000    |
| all             | paraphrased   | 55           | 55       | 1.000    |
| all             | distributed   | 64           | 64       | 1.000    |
| all             | complex       | 139          | 139      | 1.000    |
| all             | contradictory | 61           | 61       | 1.000    |
| all             | all           | 342          | 342      | 1.000    |
| author_claim    | explicit      | 2            | 2        | 1.000    |
| author_claim    | paraphrased   | 4            | 4        | 1.000    |
| author_claim    | distributed   | 6            | 6        | 1.000    |
| author_claim    | complex       | 6            | 6        | 1.000    |
| author_claim    | contradictory | 4            | 4        | 1.000    |
| author_claim    | all           | 22           | 22       | 1.000    |
| condition       | explicit      | 9            | 9        | 1.000    |
| condition       | paraphrased   | 30           | 30       | 1.000    |
| condition       | distributed   | 34           | 34       | 1.000    |
| condition       | complex       | 56           | 56       | 1.000    |
| condition       | contradictory | 38           | 38       | 1.000    |
| condition       | all           | 167          | 167      | 1.000    |
| measurement     | explicit      | 4            | 4        | 1.000    |
| measurement     | paraphrased   | 7            | 7        | 1.000    |
| measurement     | distributed   | 7            | 7        | 1.000    |
| measurement     | complex       | 38           | 38       | 1.000    |
| measurement     | contradictory | 8            | 8        | 1.000    |
| measurement     | all           | 64           | 64       | 1.000    |
| metric          | explicit      | 8            | 8        | 1.000    |
| metric          | paraphrased   | 14           | 14       | 1.000    |
| metric          | distributed   | 17           | 17       | 1.000    |
| metric          | complex       | 39           | 39       | 1.000    |
| metric          | contradictory | 11           | 11       | 1.000    |
| metric          | all           | 89           | 89       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 11      | 11              | 0      | 0              |
| llm_condition@1#134ab1a38338      | 33      | 29              | 26     | 22             |
| llm_measurement@1#5212fc43026f    | 62      | 57              | 26     | 22             |
| llm_metric@1#1ca12a572ef8         | 15      | 14              | 6      | 5              |
| regex_author_claim@2#b2161f228a8c | 11      | 11              | 0      | 0              |
| regex_condition@2#80486860164a    | 16      | 7               | 9      | 0              |
| regex_measurement@2#9edb306c5b05  | 44      | 39              | 8      | 4              |
| regex_metric@2#67f41f33eff7       | 21      | 11              | 12     | 2              |

Facts no extractor found: condition 4, measurement 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 33      | 33      | 29        | 0.879       | 0.879    | 0.879 | 1.000           | -                      | 26     | 22             |
| llm_condition@1#134ab1a38338      | all             | all     | 33      | 33      | 29        | 0.879       | 0.879    | 0.879 | 1.000           | -                      | 26     | 22             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 62      | 64      | 57        | 0.919       | 0.891    | 0.905 | 1.000           | 0.930                  | 26     | 22             |
| llm_measurement@1#5212fc43026f    | all             | all     | 62      | 64      | 57        | 0.919       | 0.891    | 0.905 | 1.000           | -                      | 26     | 22             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 15      | 16      | 14        | 0.933       | 0.875    | 0.903 | 1.000           | -                      | 6      | 5              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 15      | 16      | 14        | 0.933       | 0.875    | 0.903 | 1.000           | -                      | 6      | 5              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 16      | 33      | 7         | 0.438       | 0.212    | 0.286 | 1.000           | -                      | 9      | 0              |
| regex_condition@2#80486860164a    | all             | all     | 16      | 33      | 7         | 0.438       | 0.212    | 0.286 | 1.000           | -                      | 9      | 0              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 44      | 64      | 39        | 0.886       | 0.609    | 0.722 | 1.000           | 0.974                  | 8      | 4              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 44      | 64      | 39        | 0.886       | 0.609    | 0.722 | 1.000           | -                      | 8      | 4              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 21      | 16      | 11        | 0.524       | 0.688    | 0.595 | 0.909           | -                      | 12     | 2              |
| regex_metric@2#67f41f33eff7       | all             | all     | 21      | 16      | 11        | 0.524       | 0.688    | 0.595 | 0.909           | -                      | 12     | 2              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 11      | 11            | 12954          | 1339            | 6.773     |
| llm_condition@1#134ab1a38338      | 11      | 17            | 21410          | 3086            | 22.043    |
| llm_measurement@1#5212fc43026f    | 11      | 22            | 35656          | 10564           | 41.596    |
| llm_metric@1#1ca12a572ef8         | 11      | 14            | 17691          | 1454            | 3.770     |
| llm_screen@1#6bec6abaf6a0         | 11      | 11            | 11733          | 907             | 5.671     |
| regex_author_claim@2#b2161f228a8c | 11      | 0             | 0              | 0               | 0.068     |
| regex_condition@2#80486860164a    | 11      | 0             | 0              | 0               | 0.073     |
| regex_measurement@2#9edb306c5b05  | 11      | 0             | 0              | 0               | 0.102     |
| regex_metric@2#67f41f33eff7       | 11      | 0             | 0              | 0               | 0.074     |
| regex_screen@1#8301b6896dc3       | 11      | 0             | 0              | 0               | 0.072     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 98      | 8.909       |
| calls            | 110     | 10.000      |
| input_tokens     | 99444   | 9040.364    |
| made_model_calls | 14      | 1.273       |
| model_calls      | 75      | 6.818       |
| output_tokens    | 17350   | 1577.273    |
| seconds          | 80.875  | 7.352       |

## Funnel

Strategy `all` over 11 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.818          |
| input_tokens  | 9040.364       |
| output_tokens | 1577.273       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 11          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 11          | 11   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
