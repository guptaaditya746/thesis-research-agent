# Evaluation of run rag-tpl-s1-paraphrased on rag-tpl-s1-4d15ddc4

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: paraphrased

## A. Extraction

| evidence_type   | level       | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|-------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | paraphrased | 54      | 162     | 54        | 1.000       | 0.333    | 0.500 | 1.000           |
| all             | all         | 54      | 162     | 54        | 1.000       | 0.333    | 0.500 | 1.000           |
| author_claim    | paraphrased | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all         | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | paraphrased | 24      | 61      | 24        | 1.000       | 0.393    | 0.565 | 1.000           |
| condition       | all         | 24      | 61      | 24        | 1.000       | 0.393    | 0.565 | 1.000           |
| measurement     | paraphrased | 7       | 61      | 7         | 1.000       | 0.115    | 0.206 | 1.000           |
| measurement     | all         | 7       | 61      | 7         | 1.000       | 0.115    | 0.206 | 1.000           |
| metric          | paraphrased | 3       | 20      | 3         | 1.000       | 0.150    | 0.261 | 1.000           |
| metric          | all         | 3       | 20      | 3         | 1.000       | 0.150    | 0.261 | 1.000           |

Facts no item matched: 108; items matching no fact: 0.

## B. Integration

| level       | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|-------------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| paraphrased | 7                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.150       |
| all         | 7                      | 1.000                  | 1.000                     | 1.000             | 1.000             | 1.000          | 20        | 0.150       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | refuted | mixed      | no              | 20        | 20           | 0.150                | 0.150          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level       | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| paraphrased | evidence-engine | 20        | 20           | 0.150                | 0.150          | 1.000               | -              |

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
| condition       | 0.565 [0.49, 0.70] | BCa      |
| metric          | 0.261 [0.10, 0.52] | BCa      |
| measurement     | 0.206 [0.06, 0.48] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.500 [0.41, 0.66] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 0.150 [0.05, 0.35]   | BCa      | -                     | -               |

## Locate recall

| evidence_type   | level       | placements   | inside   | recall   |
|-----------------|-------------|--------------|----------|----------|
| all             | paraphrased | 344          | 344      | 1.000    |
| all             | all         | 344          | 344      | 1.000    |
| author_claim    | paraphrased | 40           | 40       | 1.000    |
| author_claim    | all         | 40           | 40       | 1.000    |
| condition       | paraphrased | 162          | 162      | 1.000    |
| condition       | all         | 162          | 162      | 1.000    |
| measurement     | paraphrased | 61           | 61       | 1.000    |
| measurement     | all         | 61           | 61       | 1.000    |
| metric          | paraphrased | 81           | 81       | 1.000    |
| metric          | all         | 81           | 81       | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 0       | 0               | 0      | 0              |
| llm_condition@1#134ab1a38338      | 24      | 24              | 24     | 24             |
| llm_measurement@1#5212fc43026f    | 7       | 7               | 7      | 7              |
| llm_metric@1#1ca12a572ef8         | 3       | 3               | 3      | 3              |
| regex_author_claim@2#b2161f228a8c | 20      | 20              | 20     | 20             |
| regex_condition@2#80486860164a    | 0       | 0               | 0      | 0              |
| regex_measurement@2#9edb306c5b05  | 0       | 0               | 0      | 0              |
| regex_metric@2#67f41f33eff7       | 0       | 0               | 0      | 0              |

Facts no extractor found: condition 37, measurement 54, metric 17

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | all             | all     | 0       | 162     | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 24      | 61      | 24        | 1.000       | 0.393    | 0.565 | 1.000           | -                      | 24     | 24             |
| llm_condition@1#134ab1a38338      | all             | all     | 24      | 61      | 24        | 1.000       | 0.393    | 0.565 | 1.000           | -                      | 24     | 24             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 7       | 7       | 7         | 1.000       | 1.000    | 1.000 | 1.000           | 1.000                  | 7      | 7              |
| llm_measurement@1#5212fc43026f    | all             | all     | 7       | 7       | 7         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 3      | 3              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 3       | 3       | 3         | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 3      | 3              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_author_claim@2#b2161f228a8c | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 20     | 20             |
| regex_condition@2#80486860164a    | condition       | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#9edb306c5b05  | all             | all     | 0       | 61      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#67f41f33eff7       | metric          | all     | 0       | 20      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#67f41f33eff7       | all             | all     | 0       | 20      | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#134ab1a38338      | 20      | 40            | 36745          | 3180            | 76.586    |
| llm_measurement@1#5212fc43026f    | 3       | 6             | 6864           | 1612            | 41.391    |
| llm_metric@1#1ca12a572ef8         | 3       | 3             | 2844           | 267             | 7.626     |
| llm_screen@1#6bec6abaf6a0         | 20      | 20            | 14569          | 1488            | 0.131     |
| regex_author_claim@2#b2161f228a8c | 20      | 0             | 0              | 0               | 0.127     |
| regex_condition@2#80486860164a    | 20      | 0             | 0              | 0               | 0.125     |
| regex_measurement@2#9edb306c5b05  | 20      | 0             | 0              | 0               | 0.124     |
| regex_metric@2#67f41f33eff7       | 20      | 0             | 0              | 0               | 0.126     |
| regex_screen@1#8301b6896dc3       | 20      | 0             | 0              | 0               | 0.133     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 124     | 6.200       |
| calls            | 146     | 7.300       |
| input_tokens     | 61022   | 3051.100    |
| made_model_calls | 41      | 2.050       |
| model_calls      | 69      | 3.450       |
| output_tokens    | 6547    | 327.350     |
| seconds          | 127.473 | 6.374       |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 7.300          |
| model_calls   | 3.450          |
| input_tokens  | 3051.100       |
| output_tokens | 327.350        |

| stopped_after   | documents   |
|-----------------|-------------|
| 1               | 3           |
| exhausted       | 17          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
