# Evaluation of run rag-tpl-s1-mixed on rag-tpl-s1-6162b495

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 41      | 38      | 38        | 0.927       | 1.000    | 0.962 | 1.000           |
| all             | paraphrased   | 34      | 34      | 32        | 0.941       | 0.941    | 0.941 | 1.000           |
| all             | distributed   | 33      | 26      | 26        | 0.788       | 1.000    | 0.881 | 1.000           |
| all             | complex       | 80      | 74      | 70        | 0.875       | 0.946    | 0.909 | 1.000           |
| all             | contradictory | 40      | 38      | 38        | 0.950       | 1.000    | 0.974 | 1.000           |
| all             | all           | 228     | 210     | 204       | 0.895       | 0.971    | 0.932 | 1.000           |
| author_claim    | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | complex       | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all           | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | explicit      | 16      | 15      | 15        | 0.938       | 1.000    | 0.968 | 1.000           |
| condition       | paraphrased   | 13      | 13      | 11        | 0.846       | 0.846    | 0.846 | 1.000           |
| condition       | distributed   | 15      | 9       | 9         | 0.600       | 1.000    | 0.750 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all           | 68      | 61      | 59        | 0.868       | 0.967    | 0.915 | 1.000           |
| measurement     | explicit      | 16      | 15      | 15        | 0.938       | 1.000    | 0.968 | 1.000           |
| measurement     | paraphrased   | 13      | 13      | 13        | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | distributed   | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| measurement     | complex       | 54      | 50      | 46        | 0.852       | 0.920    | 0.885 | 1.000           |
| measurement     | contradictory | 17      | 15      | 15        | 0.882       | 1.000    | 0.938 | 1.000           |
| measurement     | all           | 109     | 102     | 98        | 0.899       | 0.961    | 0.929 | 1.000           |
| metric          | explicit      | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | paraphrased   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | distributed   | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | complex       | 13      | 11      | 11        | 0.846       | 1.000    | 0.917 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 31      | 27      | 27        | 0.871       | 1.000    | 0.931 | 1.000           |

Facts no item matched: 6; items matching no fact: 24.

## B. Integration

| level         | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| explicit      | 15                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.933          | 4         | 0.750       |
| paraphrased   | 13                     | 0.846                  | 0.846                     | 1.000             | 0.846             | 1.000          | 4         | 1.000       |
| distributed   | 9                      | 1.000                  | 1.000                     | 1.000             | 0.778             | 0.778          | 4         | 1.000       |
| complex       | 46                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.935          | 4         | 0.000       |
| contradictory | 15                     | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 4         | 1.000       |
| all           | 98                     | 0.980                  | 0.980                     | 1.000             | 0.959             | 0.939          | 20        | 0.750       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level         | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| explicit      | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| paraphrased   | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| distributed   | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| complex       | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |
| contradictory | evidence-engine | 4         | 4            | 1.000                | 1.000          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 4    | 0    | 0    | 1.000       | 1.000    |
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
| condition       | 0.915 [0.82, 0.96] | BCa      |
| metric          | 0.931 [0.87, 0.98] | BCa      |
| measurement     | 0.929 [0.88, 0.97] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.932 [0.90, 0.96] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 84           | 84       | 1.000    |
| all             | paraphrased   | 72           | 72       | 1.000    |
| all             | distributed   | 60           | 60       | 1.000    |
| all             | complex       | 138          | 138      | 1.000    |
| all             | contradictory | 77           | 77       | 1.000    |
| all             | all           | 431          | 431      | 1.000    |
| author_claim    | explicit      | 8            | 8        | 1.000    |
| author_claim    | paraphrased   | 8            | 8        | 1.000    |
| author_claim    | distributed   | 8            | 8        | 1.000    |
| author_claim    | complex       | 8            | 8        | 1.000    |
| author_claim    | contradictory | 8            | 8        | 1.000    |
| author_claim    | all           | 40           | 40       | 1.000    |
| condition       | explicit      | 38           | 38       | 1.000    |
| condition       | paraphrased   | 34           | 34       | 1.000    |
| condition       | distributed   | 27           | 27       | 1.000    |
| condition       | complex       | 43           | 43       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 182          | 182      | 1.000    |
| measurement     | explicit      | 15           | 15       | 1.000    |
| measurement     | paraphrased   | 13           | 13       | 1.000    |
| measurement     | distributed   | 9            | 9        | 1.000    |
| measurement     | complex       | 50           | 50       | 1.000    |
| measurement     | contradictory | 15           | 15       | 1.000    |
| measurement     | all           | 102          | 102      | 1.000    |
| metric          | explicit      | 23           | 23       | 1.000    |
| metric          | paraphrased   | 17           | 17       | 1.000    |
| metric          | distributed   | 16           | 16       | 1.000    |
| metric          | complex       | 37           | 37       | 1.000    |
| metric          | contradictory | 14           | 14       | 1.000    |
| metric          | all           | 107          | 107      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 20      | 20              | 0      | 0              |
| llm_condition@1#134ab1a38338      | 61      | 57              | 45     | 41             |
| llm_measurement@1#5212fc43026f    | 100     | 94              | 44     | 40             |
| llm_metric@1#1ca12a572ef8         | 27      | 26              | 9      | 8              |
| regex_author_claim@2#b2161f228a8c | 20      | 20              | 0      | 0              |
| regex_condition@2#80486860164a    | 23      | 18              | 7      | 2              |
| regex_measurement@2#9edb306c5b05  | 65      | 58              | 9      | 4              |
| regex_metric@2#67f41f33eff7       | 22      | 19              | 4      | 1              |

Facts no extractor found: condition 2, measurement 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           | -                      | 45     | 41             |
| llm_condition@1#134ab1a38338      | all             | all     | 61      | 61      | 57        | 0.934       | 0.934    | 0.934 | 1.000           | -                      | 45     | 41             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 100     | 102     | 94        | 0.940       | 0.922    | 0.931 | 1.000           | 0.979                  | 44     | 40             |
| llm_measurement@1#5212fc43026f    | all             | all     | 100     | 102     | 94        | 0.940       | 0.922    | 0.931 | 1.000           | -                      | 44     | 40             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 27      | 27      | 26        | 0.963       | 0.963    | 0.963 | 1.000           | -                      | 9      | 8              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 27      | 27      | 26        | 0.963       | 0.963    | 0.963 | 1.000           | -                      | 9      | 8              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 23      | 61      | 18        | 0.783       | 0.295    | 0.429 | 1.000           | -                      | 7      | 2              |
| regex_condition@2#80486860164a    | all             | all     | 23      | 61      | 18        | 0.783       | 0.295    | 0.429 | 1.000           | -                      | 7      | 2              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 65      | 102     | 58        | 0.892       | 0.569    | 0.695 | 1.000           | 1.000                  | 9      | 4              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 65      | 102     | 58        | 0.892       | 0.569    | 0.695 | 1.000           | -                      | 9      | 4              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 22      | 27      | 19        | 0.864       | 0.704    | 0.776 | 1.000           | -                      | 4      | 1              |
| regex_metric@2#67f41f33eff7       | all             | all     | 22      | 27      | 19        | 0.864       | 0.704    | 0.776 | 1.000           | -                      | 4      | 1              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 20      | 20            | 17555          | 2367            | 12.875    |
| llm_condition@1#134ab1a38338      | 20      | 35            | 33917          | 6180            | 39.956    |
| llm_measurement@1#5212fc43026f    | 20      | 40            | 50524          | 17331           | 79.447    |
| llm_metric@1#1ca12a572ef8         | 20      | 21            | 20445          | 2436            | 10.786    |
| llm_screen@1#6bec6abaf6a0         | 20      | 20            | 15335          | 1563            | 8.744     |
| regex_author_claim@2#b2161f228a8c | 20      | 0             | 0              | 0               | 0.131     |
| regex_condition@2#80486860164a    | 20      | 0             | 0              | 0               | 0.129     |
| regex_measurement@2#9edb306c5b05  | 20      | 0             | 0              | 0               | 0.362     |
| regex_metric@2#67f41f33eff7       | 20      | 0             | 0              | 0               | 0.134     |
| regex_screen@1#8301b6896dc3       | 20      | 0             | 0              | 0               | 0.140     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 176     | 8.800       |
| calls            | 200     | 10.000      |
| input_tokens     | 137776  | 6888.800    |
| made_model_calls | 28      | 1.400       |
| model_calls      | 136     | 6.800       |
| output_tokens    | 29877   | 1493.850    |
| seconds          | 153.817 | 7.691       |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 6.800          |
| input_tokens  | 6888.800       |
| output_tokens | 1493.850       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
