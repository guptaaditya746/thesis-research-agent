# Evaluation of run rag-tpl-k1-mixed on rag-tpl-k1-e922861d

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 51      | 48      | 48        | 0.941       | 1.000    | 0.970 | 1.000           |
| all             | paraphrased   | 44      | 44      | 40        | 0.909       | 0.909    | 0.909 | 1.000           |
| all             | distributed   | 33      | 26      | 26        | 0.788       | 1.000    | 0.881 | 1.000           |
| all             | complex       | 78      | 72      | 69        | 0.885       | 0.958    | 0.920 | 1.000           |
| all             | contradictory | 38      | 37      | 37        | 0.974       | 1.000    | 0.987 | 1.000           |
| all             | all           | 244     | 227     | 220       | 0.902       | 0.969    | 0.934 | 1.000           |
| author_claim    | explicit      | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 20      | 19      | 19        | 0.950       | 1.000    | 0.974 | 1.000           |
| condition       | paraphrased   | 17      | 17      | 13        | 0.765       | 0.765    | 0.765 | 1.000           |
| condition       | distributed   | 15      | 9       | 9         | 0.600       | 1.000    | 0.750 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all           | 76      | 69      | 65        | 0.855       | 0.942    | 0.897 | 1.000           |
| measurement     | explicit      | 20      | 19      | 19        | 0.950       | 1.000    | 0.974 | 1.000           |
| measurement     | paraphrased   | 17      | 17      | 17        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | complex       | 52      | 48      | 45        | 0.865       | 0.938    | 0.900 | 1.000           |
| measurement     | contradictory | 15      | 14      | 14        | 0.933       | 1.000    | 0.966 | 1.000           |
| measurement     | all           | 113     | 107     | 104       | 0.920       | 0.972    | 0.945 | 1.000           |
| metric          | explicit      | 6       | 5       | 5         | 0.833       | 1.000    | 0.909 | 1.000           |
| metric          | paraphrased   | 5       | 5       | 5         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | distributed   | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | complex       | 13      | 11      | 11        | 0.846       | 1.000    | 0.917 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 33      | 29      | 29        | 0.879       | 1.000    | 0.935 | 1.000           |

Facts no item matched: 7; items matching no fact: 24.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 19                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.947          | 5         | 0.800       |
| paraphrased   | 17                     | 0.765                  | 0.765                     | 1.000             | 0.765             | 1.000          | 5         | 1.000       |
| distributed   | 9                      | 1.000                  | 1.000                     | 1.000             | 0.778             | 0.778          | 4         | 1.000       |
| complex       | 45                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.978          | 3         | 0.000       |
| contradictory | 14                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 3         | 1.000       |
| all           | 104                    | 0.962                  | 0.962                     | 1.000             | 0.942             | 0.962          | 20        | 0.800       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 22        | 20           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | evidence-engine | 5         | 5            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | evidence-engine | 5         | 5            | 1.000                | 1.000          | 1.000               | -              |
| distributed   | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| complex       | evidence-engine | 4         | 3            | 1.000                | 1.000          | 1.000               | -              |
| contradictory | evidence-engine | 4         | 3            | 1.000                | 1.000          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 3    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | duplicate       | 2    | 0    | 0    | 1.000       | 1.000    |
| evidence-engine | large_effect    | 0    | 0    | 0    | -           | -        |

| system          | counts_correct   | duplicates_correct   |
|-----------------|------------------|----------------------|
| evidence-engine | yes              | yes                  |

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.897 [0.79, 0.95] | BCa      |
| metric          | 0.935 [0.88, 0.98] | BCa      |
| measurement     | 0.945 [0.90, 0.98] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.934 [0.90, 0.96] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 106          | 106      | 1.000    |
| all             | paraphrased   | 93           | 93       | 1.000    |
| all             | distributed   | 60           | 60       | 1.000    |
| all             | complex       | 133          | 133      | 1.000    |
| all             | contradictory | 74           | 74       | 1.000    |
| all             | all           | 466          | 466      | 1.000    |
| author_claim    | explicit      | 10           | 10       | 1.000    |
| author_claim    | paraphrased   | 10           | 10       | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 44           | 44       | 1.000    |
| condition       | explicit      | 48           | 48       | 1.000    |
| condition       | paraphrased   | 44           | 44       | 1.000    |
| condition       | distributed   | 27           | 27       | 1.000    |
| condition       | complex       | 41           | 41       | 1.000    |
| condition       | contradictory | 39           | 39       | 1.000    |
| condition       | all           | 199          | 199      | 1.000    |
| measurement     | explicit      | 19           | 19       | 1.000    |
| measurement     | paraphrased   | 17           | 17       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 48           | 48       | 1.000    |
| measurement     | contradictory | 14           | 14       | 1.000    |
| measurement     | all           | 107          | 107      | 1.000    |
| metric          | explicit      | 29           | 29       | 1.000    |
| metric          | paraphrased   | 22           | 22       | 1.000    |
| metric          | distributed   | 16           | 16       | 1.000    |
| metric          | complex       | 36           | 36       | 1.000    |
| metric          | contradictory | 13           | 13       | 1.000    |
| metric          | all           | 116          | 116      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 22      | 22              | 0      | 0              |
| llm_condition@1#134ab1a38338      | 69      | 63              | 52     | 46             |
| llm_measurement@1#5212fc43026f    | 105     | 102             | 50     | 48             |
| llm_metric@1#1ca12a572ef8         | 29      | 28              | 10     | 9              |
| regex_author_claim@2#b2161f228a8c | 22      | 22              | 0      | 0              |
| regex_condition@2#80486860164a    | 24      | 19              | 7      | 2              |
| regex_measurement@2#9edb306c5b05  | 63      | 56              | 8      | 2              |
| regex_metric@2#67f41f33eff7       | 23      | 20              | 4      | 1              |

Facts no extractor found: condition 4, measurement 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 69      | 69      | 63        | 0.913       | 0.913    | 0.913 | 1.000           | -                      | 52     | 46             |
| llm_condition@1#134ab1a38338      | all             | all     | 69      | 69      | 63        | 0.913       | 0.913    | 0.913 | 1.000           | -                      | 52     | 46             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 105     | 107     | 102       | 0.971       | 0.953    | 0.962 | 1.000           | 0.961                  | 50     | 48             |
| llm_measurement@1#5212fc43026f    | all             | all     | 105     | 107     | 102       | 0.971       | 0.953    | 0.962 | 1.000           | -                      | 50     | 48             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 29      | 29      | 28        | 0.966       | 0.966    | 0.966 | 1.000           | -                      | 10     | 9              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 29      | 29      | 28        | 0.966       | 0.966    | 0.966 | 1.000           | -                      | 10     | 9              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 22      | 22      | 22        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 24      | 69      | 19        | 0.792       | 0.275    | 0.409 | 1.000           | -                      | 7      | 2              |
| regex_condition@2#80486860164a    | all             | all     | 24      | 69      | 19        | 0.792       | 0.275    | 0.409 | 1.000           | -                      | 7      | 2              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 63      | 107     | 56        | 0.889       | 0.523    | 0.659 | 1.000           | 1.000                  | 8      | 2              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 63      | 107     | 56        | 0.889       | 0.523    | 0.659 | 1.000           | -                      | 8      | 2              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 23      | 29      | 20        | 0.870       | 0.690    | 0.769 | 1.000           | -                      | 4      | 1              |
| regex_metric@2#67f41f33eff7       | all             | all     | 23      | 29      | 20        | 0.870       | 0.690    | 0.769 | 1.000           | -                      | 4      | 1              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 22      | 22            | 19219          | 2606            | 13.024    |
| llm_condition@1#134ab1a38338      | 22      | 39            | 37771          | 7076            | 42.904    |
| llm_measurement@1#5212fc43026f    | 22      | 44            | 56486          | 19331           | 137.236   |
| llm_metric@1#1ca12a572ef8         | 22      | 23            | 22317          | 2622            | 14.111    |
| llm_screen@1#6bec6abaf6a0         | 22      | 22            | 16777          | 1732            | 9.356     |
| regex_author_claim@2#b2161f228a8c | 22      | 0             | 0              | 0               | 0.139     |
| regex_condition@2#80486860164a    | 22      | 0             | 0              | 0               | 0.142     |
| regex_measurement@2#9edb306c5b05  | 22      | 0             | 0              | 0               | 0.189     |
| regex_metric@2#67f41f33eff7       | 22      | 0             | 0              | 0               | 0.143     |
| regex_screen@1#8301b6896dc3       | 22      | 0             | 0              | 0               | 0.144     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 196     | 8.909       |
| calls            | 220     | 10.000      |
| input_tokens     | 152570  | 6935.000    |
| made_model_calls | 28      | 1.273       |
| model_calls      | 150     | 6.818       |
| output_tokens    | 33367   | 1516.682    |
| seconds          | 218.589 | 9.936       |

## Funnel

Strategy `all` over 22 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.818          |
| input_tokens  | 6935.000       |
| output_tokens | 1516.682       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 22          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 22          | 22   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
