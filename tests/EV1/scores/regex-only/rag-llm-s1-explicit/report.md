# Evaluation of run rag-llm-s1-explicit on rag-llm-s1-4f53cda1

Question: Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?
Levels:

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1   | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|------|-----------------|

Facts no item matched: 0; items matching no fact: 0.

## B. Integration

| level   | matched_measurements   | association_accuracy   | condition_role_accuracy   | metric_accuracy   | condition_exact   | metric_exact   | studies   | true_pair   |
|---------|------------------------|------------------------|---------------------------|-------------------|-------------------|----------------|-----------|-------------|

## C. Synthesis

| system          | label        | expected     | label_correct   | studies   | determined   | direction_accuracy   | completeness   | accuracy_answered   | traceability   |
|-----------------|--------------|--------------|-----------------|-----------|--------------|----------------------|----------------|---------------------|----------------|
| evidence-engine | insufficient | insufficient | yes             | -         | -            | -                    | -              | -                   | -              |
| rag-baseline    | insufficient | insufficient | yes             | -         | -            | -                    | -              | -                   | -              |
| agent-baseline  | insufficient | insufficient | yes             | -         | -            | -                    | -              | -                   | -              |

direction_accuracy is over all scored studies: a study whose expected direction is undetermined (missing information, an irrelevant paper) is right when the system says undetermined or leaves it out, a determined study is wrong then. completeness (the supervisor's word: the share of the `determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) are over the determined studies only, so a baseline that cites only some papers, or guesses on undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced (none for the engine: its spans are scored in A).

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

| evidence_type   | f1   | method   |
|-----------------|------|----------|
| condition       | -    | -        |
| metric          | -    | -        |
| measurement     | -    | -        |
| author_claim    | -    | -        |
| all             | -    | -        |

Direction accuracy, and the paired difference engine minus system (per study):

| system          | direction_accuracy   | method   | engine_minus_system   | paired_method   |
|-----------------|----------------------|----------|-----------------------|-----------------|
| evidence-engine | -                    | -        | -                     | -               |
| rag-baseline    | -                    | -        | -                     | -               |
| agent-baseline  | -                    | -        | -                     | -               |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|

## Cascade contribution

| extractor                         | found   | found_matched   | only   | only_matched   |
|-----------------------------------|---------|-----------------|--------|----------------|
| regex_author_claim@2#75e32ebcdf68 | 0       | 0               | 0      | 0              |
| regex_condition@2#a0c64d9b6305    | 0       | 0               | 0      | 0              |
| regex_measurement@2#b984f16ded3b  | 0       | 0               | 0      | 0              |
| regex_metric@2#94a3000eacae       | 0       | 0               | 0      | 0              |

Facts no extractor found: none

## Per extractor

An item counts for every extractor in its `found_by`; recall is against every fact of the type (the run has no events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                         | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-----------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| regex_author_claim@2#75e32ebcdf68 | all             | all     | 0       | 0       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_condition@2#a0c64d9b6305    | all             | all     | 0       | 0       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_measurement@2#b984f16ded3b  | all             | all     | 0       | 0       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| regex_metric@2#94a3000eacae       | all             | all     | 0       | 0       | 0         | 0.000       | 0.000    | 0.000 | -               | -                      | 0      | 0              |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | -           |
| calls            | 0       | -           |
| input_tokens     | 0       | -           |
| made_model_calls | 0       | -           |
| model_calls      | 0       | -           |
| output_tokens    | 0       | -           |
| seconds          | 0.029   | -           |

## Funnel

Strategy `all` over 0 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | -              |
| model_calls   | -              |
| input_tokens  | -              |
| output_tokens | -              |

| stopped_after   | documents   |
|-----------------|-------------|
