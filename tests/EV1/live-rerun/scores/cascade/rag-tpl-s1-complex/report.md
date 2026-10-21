# Evaluation of run rag-tpl-s1-complex on rag-tpl-s1-f0f5d48e

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 446     | 431     | 411       | 0.922       | 0.954    | 0.937 | 1.000           |
| all             | all     | 446     | 431     | 411       | 0.922       | 0.954    | 0.937 | 1.000           |
| author_claim    | complex | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| condition       | all     | 66      | 61      | 61        | 0.924       | 1.000    | 0.961 | 1.000           |
| measurement     | complex | 305     | 300     | 280       | 0.918       | 0.933    | 0.926 | 1.000           |
| measurement     | all     | 305     | 300     | 280       | 0.918       | 0.933    | 0.926 | 1.000           |
| metric          | complex | 55      | 50      | 50        | 0.909       | 1.000    | 0.952 | 1.000           |
| metric          | all     | 55      | 50      | 50        | 0.909       | 1.000    | 0.952 | 1.000           |

Facts no item matched: 20; items matching no fact: 35.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|
| complex | 280                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.957          | 20        | 0.000       |
| all     | 280                    | 1.000                  | 1.000                     | 1.000             | 1.000             | 0.957          | 20        | 0.000       |

## C. Synthesis

| system          | label   | expected   | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|---------|------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | mixed   | mixed      | yes             | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

Per level:

| level   | system          | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|---------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| complex | evidence-engine | 20        | 20           | 1.000                | 1.000          | 1.000               | -              |

Flags (F1; a system without `flags` is not listed):

| system          | flag            | tp   | fp   | fn   | precision   | recall   |
|-----------------|-----------------|------|------|------|-------------|----------|
| evidence-engine | claim_disagrees | 0    | 0    | 0    | -           | -        |
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
| condition       | 0.961 [0.93, 0.98] | BCa      |
| metric          | 0.952 [0.91, 0.98] | BCa      |
| measurement     | 0.926 [0.89, 0.95] | BCa      |
| author_claim    | 1.000 [n/a]        | -        |
| all             | 0.937 [0.91, 0.96] | BCa      |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | 1.000 [n/a]          | -        | -                     | -               |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 773          | 773      | 1.000    |
| all             | all     | 773          | 773      | 1.000    |
| author_claim    | complex | 40           | 40       | 1.000    |
| author_claim    | all     | 40           | 40       | 1.000    |
| condition       | complex | 263          | 263      | 1.000    |
| condition       | all     | 263          | 263      | 1.000    |
| measurement     | complex | 300          | 300      | 1.000    |
| measurement     | all     | 300          | 300      | 1.000    |
| metric          | complex | 170          | 170      | 1.000    |
| metric          | all     | 170          | 170      | 1.000    |

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | 20      | 20              | 0      | 0              |
| llm_condition@1#134ab1a38338      | 61      | 61              | 38     | 38             |
| llm_measurement@1#5212fc43026f    | 280     | 268             | 39     | 27             |
| llm_metric@1#1ca12a572ef8         | 50      | 50              | 7      | 7              |
| regex_author_claim@2#b2161f228a8c | 20      | 20              | 0      | 0              |
| regex_condition@2#80486860164a    | 28      | 23              | 5      | 0              |
| regex_measurement@2#9edb306c5b05  | 266     | 253             | 25     | 12             |
| regex_metric@2#67f41f33eff7       | 48      | 43              | 5      | 0              |

Facts no extractor found: measurement 20

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_author_claim@1#fefdf4416c50   | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_author_claim@1#fefdf4416c50   | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| llm_condition@1#134ab1a38338      | condition       | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| llm_condition@1#134ab1a38338      | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 38     | 38             |
| llm_measurement@1#5212fc43026f    | measurement     | all     | 280     | 300     | 268       | 0.957       | 0.893    | 0.924 | 1.000           | 1.000                  | 39     | 27             |
| llm_measurement@1#5212fc43026f    | all             | all     | 280     | 300     | 268       | 0.957       | 0.893    | 0.924 | 1.000           | -                      | 39     | 27             |
| llm_metric@1#1ca12a572ef8         | metric          | all     | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| llm_metric@1#1ca12a572ef8         | all             | all     | 50      | 50      | 50        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 7      | 7              |
| regex_author_claim@2#b2161f228a8c | author_claim    | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_author_claim@2#b2161f228a8c | all             | all     | 20      | 20      | 20        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 0      | 0              |
| regex_condition@2#80486860164a    | condition       | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_condition@2#80486860164a    | all             | all     | 28      | 61      | 23        | 0.821       | 0.377    | 0.517 | 1.000           | -                      | 5      | 0              |
| regex_measurement@2#9edb306c5b05  | measurement     | all     | 266     | 300     | 253       | 0.951       | 0.843    | 0.894 | 1.000           | 1.000                  | 25     | 12             |
| regex_measurement@2#9edb306c5b05  | all             | all     | 266     | 300     | 253       | 0.951       | 0.843    | 0.894 | 1.000           | -                      | 25     | 12             |
| regex_metric@2#67f41f33eff7       | metric          | all     | 48      | 50      | 43        | 0.896       | 0.860    | 0.878 | 1.000           | -                      | 5      | 0              |
| regex_metric@2#67f41f33eff7       | all             | all     | 48      | 50      | 43        | 0.896       | 0.860    | 0.878 | 1.000           | -                      | 5      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                         | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-----------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_author_claim@1#fefdf4416c50   | 20      | 20            | 19946          | 2366            | 65.150    |
| llm_condition@1#134ab1a38338      | 20      | 39            | 42327          | 6528            | 173.916   |
| llm_measurement@1#5212fc43026f    | 20      | 40            | 67471          | 44061           | 1084.462  |
| llm_metric@1#1ca12a572ef8         | 20      | 27            | 29622          | 4609            | 120.621   |
| llm_screen@1#6bec6abaf6a0         | 20      | 20            | 17726          | 1417            | 42.177    |
| regex_author_claim@2#b2161f228a8c | 20      | 0             | 0              | 0               | 0.137     |
| regex_condition@2#80486860164a    | 20      | 0             | 0              | 0               | 0.141     |
| regex_measurement@2#9edb306c5b05  | 20      | 0             | 0              | 0               | 0.386     |
| regex_metric@2#67f41f33eff7       | 20      | 0             | 0              | 0               | 0.143     |
| regex_screen@1#8301b6896dc3       | 20      | 0             | 0              | 0               | 0.138     |

## Cost

| measure          | total    | per_paper   |
|------------------|----------|-------------|
| cached_calls     | 80       | 4.000       |
| calls            | 200      | 10.000      |
| input_tokens     | 177092   | 8854.600    |
| made_model_calls | 146      | 7.300       |
| model_calls      | 146      | 7.300       |
| output_tokens    | 58981    | 2949.050    |
| seconds          | 1488.598 | 74.430      |

## Funnel

Strategy `all` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 10.000         |
| model_calls   | 7.300          |
| input_tokens  | 8854.600       |
| output_tokens | 2949.050       |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
