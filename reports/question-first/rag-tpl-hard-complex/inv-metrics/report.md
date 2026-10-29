# Evaluation of run rag-tpl-hard-complex on rag-tpl-hard-24ab4663

Question: Which evaluation metrics do the papers report?
Question id: inv-metrics (kind inventory)
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 476     | 263     | 263       | 0.553       | 1.000    | 0.712 | 1.000           |
| all             | all     | 476     | 263     | 263       | 0.553       | 1.000    | 0.712 | 1.000           |
| metric          | complex | 476     | 263     | 263       | 0.553       | 1.000    | 0.712 | 1.000           |
| metric          | all     | 476     | 263     | 263       | 0.553       | 1.000    | 0.712 | 1.000           |

Facts no item matched: 0; items matching no fact: 213.

Evidence types scored (the protocol's own; the `all` rows pool these only): metric.

## B. Synonym merging

| entries   | keyed_entries   | keys   | split   | merged   | clean_share   |
|-----------|-----------------|--------|---------|----------|---------------|
| 20        | 8               | 8      | 0       | 0        | 1.000         |

Each answer entry holds the truth keys of the facts its items matched in A; `split`: keys spread over more than one entry, `merged`: entries holding more than one key, `clean_share`: entries holding one key no other entry holds, of the entries with a key.

## C. Inventory

| system          | target   | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|-----------------|----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| evidence-engine | metric   | 20        | 8                  | 8         | 0.400       | 1.000    | 0.571 | 0.613             | 1.000          | 0.760      |
| rag-baseline    | metric   | 5         | 8                  | 5         | 1.000       | 0.625    | 0.769 | 1.000             | 0.023          | 0.045      |
| agent-baseline  | metric   | 8         | 8                  | 8         | 1.000       | 1.000    | 1.000 | 1.000             | 0.806          | 0.893      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- evidence-engine: false positives BLEU (%), RAG without reranking, ROUGE-L (%), Retrieval quality, accuracy, answer accuracy (%), benchmark, hallucination frequency (%), latency (s), no-retrieval baseline, public benchmark, unsupported-answer rate (%); missed none
- rag-baseline: false positives none; missed hallucination frequency, hallucination rate, unsupported-answer rate
- agent-baseline: false positives none; missed none

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| metric          | 0.712 [0.69, 0.73] | BCa      |
| all             | 0.712 [0.69, 0.73] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric    | interval           | method     | n   |
|-----------------|-----------|--------------------|------------|-----|
| evidence-engine | precision | 0.400 [0.20, 0.65] | BCa        | 20  |
| evidence-engine | recall    | 1.000 [n/a]        | -          | 20  |
| evidence-engine | f1        | 0.571 [0.33, 0.79] | BCa        | 20  |
| rag-baseline    | precision | 1.000 [1.00, 1.00] | percentile | 8   |
| rag-baseline    | recall    | 0.625 [0.25, 0.88] | BCa        | 8   |
| rag-baseline    | f1        | 0.769 [0.40, 0.93] | BCa        | 8   |
| agent-baseline  | precision | 1.000 [n/a]        | -          | 8   |
| agent-baseline  | recall    | 1.000 [n/a]        | -          | 8   |
| agent-baseline  | f1        | 1.000 [n/a]        | -          | 8   |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 4323         | 889      | 0.206    |
| all             | all     | 4323         | 889      | 0.206    |
| author_claim    | complex | 212          | 0        | 0.000    |
| author_claim    | all     | 212          | 0        | 0.000    |
| condition       | complex | 1454         | 0        | 0.000    |
| condition       | all     | 1454         | 0        | 0.000    |
| measurement     | complex | 1768         | 0        | 0.000    |
| measurement     | all     | 1768         | 0        | 0.000    |
| metric          | complex | 889          | 889      | 1.000    |
| metric          | all     | 889          | 889      | 1.000    |

## Cascade contribution

| extractor                    | found   | found_matched   | only   | only_matched   |
|------------------------------|---------|-----------------|--------|----------------|
| abbrev_metric@1#8bc3c347fdea | 0       | 0               | 0      | 0              |
| gliner_metric@1#13cd7bab1b65 | 404     | 216             | 188    | 0              |
| llm_metric@1#41e1e53a1fc4    | 263     | 263             | 47     | 47             |
| regex_metric@2#d4eacbf703f6  | 216     | 191             | 25     | 0              |

Facts no extractor found: none

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                    | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_metric@1#8bc3c347fdea | metric          | all     | 0       | 263     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| abbrev_metric@1#8bc3c347fdea | all             | all     | 0       | 263     | 0         | n/a         | 0.000    | 0.000 | -               | -                      | 0      | 0              |
| gliner_metric@1#13cd7bab1b65 | metric          | all     | 404     | 263     | 216       | 0.535       | 0.821    | 0.648 | 1.000           | -                      | 188    | 0              |
| gliner_metric@1#13cd7bab1b65 | all             | all     | 404     | 263     | 216       | 0.535       | 0.821    | 0.648 | 1.000           | -                      | 188    | 0              |
| llm_metric@1#41e1e53a1fc4    | metric          | all     | 263     | 263     | 263       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 47     | 47             |
| llm_metric@1#41e1e53a1fc4    | all             | all     | 263     | 263     | 263       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 47     | 47             |
| regex_metric@2#d4eacbf703f6  | metric          | all     | 216     | 263     | 191       | 0.884       | 0.726    | 0.797 | 1.000           | -                      | 25     | 0              |
| regex_metric@2#d4eacbf703f6  | all             | all     | 216     | 263     | 191       | 0.884       | 0.726    | 0.797 | 1.000           | -                      | 25     | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                    | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_metric@1#8bc3c347fdea | 106     | 0             | 0              | 0               | 0.681     |
| gliner_metric@1#13cd7bab1b65 | 106     | 356           | 0              | 0               | 0.757     |
| llm_metric@1#41e1e53a1fc4    | 106     | 125           | 147401         | 22864           | 0.792     |
| llm_screen@1#41b0d6e6793f    | 109     | 109           | 102099         | 8138            | 0.719     |
| regex_metric@2#d4eacbf703f6  | 106     | 0             | 0              | 0               | 0.721     |
| regex_screen@1#858a6ebc69c6  | 112     | 0             | 0              | 0               | 0.732     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 645     | 5.759       |
| input_tokens     | 249500  | 2227.679    |
| made_model_calls | 590     | 5.268       |
| model_calls      | 590     | 5.268       |
| output_tokens    | 31027   | 277.027     |
| seconds          | 330.786 | 2.953       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 5.759          |
| model_calls   | 5.268          |
| input_tokens  | 2227.679       |
| output_tokens | 276.804        |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 106         |
| skipped         | 6           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 0    | 0    | 6    | 1.000       | 1.000    |

Screened out wrongly: none
