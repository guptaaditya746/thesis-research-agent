# Evaluation of run rag-claude-s1-mixed on rag-claude-s1-ec928480

Question: Which evaluation metrics do the papers report?
Question id: inv-metrics (kind inventory)
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 3       | 4       | 3         | 1.000       | 0.750    | 0.857 | 1.000           |
| all             | paraphrased   | 1       | 4       | 1         | 1.000       | 0.250    | 0.400 | 0.000           |
| all             | distributed   | 6       | 4       | 4         | 0.667       | 1.000    | 0.800 | 1.000           |
| all             | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | all           | 25      | 27      | 23        | 0.920       | 0.852    | 0.885 | 0.957           |
| metric          | explicit      | 3       | 4       | 3         | 1.000       | 0.750    | 0.857 | 1.000           |
| metric          | paraphrased   | 1       | 4       | 1         | 1.000       | 0.250    | 0.400 | 0.000           |
| metric          | distributed   | 6       | 4       | 4         | 0.667       | 1.000    | 0.800 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 25      | 27      | 23        | 0.920       | 0.852    | 0.885 | 0.957           |

Facts no item matched: 4; items matching no fact: 2.

Evidence types scored (the protocol's own; the `all` rows pool these only): metric.

## B. Synonym merging

| entries   | keyed_entries   | keys   | split   | merged   | clean_share   |
|-----------|-----------------|--------|---------|----------|---------------|
| 9         | 8               | 6      | 1       | 0        | 0.625         |

Each answer entry holds the truth keys of the facts its items matched in A; `split`: keys spread over more than one entry, `merged`: entries holding more than one key, `clean_share`: entries holding one key no other entry holds, of the entries with a key.

## C. Inventory

| system          | target   | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|-----------------|----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| evidence-engine | metric   | 9         | 7                  | 6         | 0.667       | 0.857    | 0.750 | 0.760             | 0.704          | 0.731      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- evidence-engine: false positives Accuracy, Factual Accuracy, fluency; missed hallucination frequency

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| metric          | 0.885 [0.75, 0.96] | BCa      |
| all             | 0.885 [0.75, 0.96] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric    | interval           | method   | n   |
|-----------------|-----------|--------------------|----------|-----|
| evidence-engine | precision | 0.667 [0.30, 0.90] | BCa      | 10  |
| evidence-engine | recall    | 0.857 [0.34, 1.00] | BCa      | 10  |
| evidence-engine | f1        | 0.750 [0.46, 0.95] | BCa      | 10  |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 88           | 31       | 0.352    |
| all             | paraphrased   | 73           | 22       | 0.301    |
| all             | distributed   | 75           | 26       | 0.347    |
| all             | complex       | 159          | 55       | 0.346    |
| all             | contradictory | 88           | 25       | 0.284    |
| all             | all           | 483          | 159      | 0.329    |
| author_claim    | explicit      | 8            | 0        | 0.000    |
| author_claim    | paraphrased   | 8            | 0        | 0.000    |
| author_claim    | distributed   | 8            | 0        | 0.000    |
| author_claim    | complex       | 8            | 0        | 0.000    |
| author_claim    | contradictory | 8            | 0        | 0.000    |
| author_claim    | all           | 40           | 0        | 0.000    |
| condition       | explicit      | 34           | 0        | 0.000    |
| condition       | paraphrased   | 30           | 0        | 0.000    |
| condition       | distributed   | 32           | 0        | 0.000    |
| condition       | complex       | 46           | 0        | 0.000    |
| condition       | contradictory | 40           | 0        | 0.000    |
| condition       | all           | 182          | 0        | 0.000    |
| measurement     | explicit      | 15           | 0        | 0.000    |
| measurement     | paraphrased   | 13           | 0        | 0.000    |
| measurement     | distributed   | 9            | 0        | 0.000    |
| measurement     | complex       | 50           | 0        | 0.000    |
| measurement     | contradictory | 15           | 0        | 0.000    |
| measurement     | all           | 102          | 0        | 0.000    |
| metric          | explicit      | 31           | 31       | 1.000    |
| metric          | paraphrased   | 22           | 22       | 1.000    |
| metric          | distributed   | 26           | 26       | 1.000    |
| metric          | complex       | 55           | 55       | 1.000    |
| metric          | contradictory | 25           | 25       | 1.000    |
| metric          | all           | 159          | 159      | 1.000    |

## Cascade contribution

| extractor                    | found   | found_matched   | only   | only_matched   |
|------------------------------|---------|-----------------|--------|----------------|
| abbrev_metric@1#8bc3c347fdea | 4       | 4               | 1      | 1              |
| regex_metric@2#d4eacbf703f6  | 24      | 22              | 21     | 19             |

Facts no extractor found: metric 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                    | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_metric@1#8bc3c347fdea | metric          | all     | 4       | 27      | 4         | 1.000       | 0.148    | 0.258 | 1.000           | -                      | 1      | 1              |
| abbrev_metric@1#8bc3c347fdea | all             | all     | 4       | 27      | 4         | 1.000       | 0.148    | 0.258 | 1.000           | -                      | 1      | 1              |
| regex_metric@2#d4eacbf703f6  | metric          | all     | 24      | 27      | 22        | 0.917       | 0.815    | 0.863 | 0.955           | -                      | 21     | 19             |
| regex_metric@2#d4eacbf703f6  | all             | all     | 24      | 27      | 22        | 0.917       | 0.815    | 0.863 | 0.955           | -                      | 21     | 19             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                    | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_metric@1#8bc3c347fdea | 20      | 0             | 0              | 0               | 0.347     |
| regex_metric@2#d4eacbf703f6  | 20      | 0             | 0              | 0               | 0.260     |
| regex_screen@1#858a6ebc69c6  | 20      | 0             | 0              | 0               | 0.248     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 60      | 3.000       |
| input_tokens     | 0       | 0.000       |
| made_model_calls | 0       | 0.000       |
| model_calls      | 0       | 0.000       |
| output_tokens    | 0       | 0.000       |
| seconds          | 1.428   | 0.071       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 3.000          |
| model_calls   | 0.000          |
| input_tokens  | 0.000          |
| output_tokens | 0.000          |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
