# Evaluation of run rag-claude-s1-mixed on rag-claude-s1-ec928480

Question: Which evaluation metrics do the papers report?
Question id: inv-metrics (kind inventory)
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 3       | 4       | 3         | 1.000       | 0.750    | 0.857 | 1.000           |
| all             | paraphrased   | 1       | 4       | 1         | 1.000       | 0.250    | 0.400 | 1.000           |
| all             | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | all           | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           |
| metric          | explicit      | 3       | 4       | 3         | 1.000       | 0.750    | 0.857 | 1.000           |
| metric          | paraphrased   | 1       | 4       | 1         | 1.000       | 0.250    | 0.400 | 1.000           |
| metric          | distributed   | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | complex       | 11      | 11      | 11        | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | contradictory | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | 1.000           |
| metric          | all           | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           |

Facts no item matched: 4; items matching no fact: 0.

Evidence types scored (the protocol's own; the `all` rows pool these only): metric.

## B. Synonym merging

| entries   | keyed_entries   | keys   | split   | merged   | clean_share   |
|-----------|-----------------|--------|---------|----------|---------------|
| 8         | 8               | 7      | 1       | 0        | 0.750         |

Each answer entry holds the truth keys of the facts its items matched in A; `split`: keys spread over more than one entry, `merged`: entries holding more than one key, `clean_share`: entries holding one key no other entry holds, of the entries with a key.

## C. Inventory

| system          | target   | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|-----------------|----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| evidence-engine | metric   | 7         | 7                  | 7         | 1.000       | 1.000    | 1.000 | 1.000             | 0.852          | 0.920      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- evidence-engine: false positives none; missed none

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| metric          | 0.920 [0.79, 0.98] | BCa      |
| all             | 0.920 [0.79, 0.98] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric    | interval    | method   | n   |
|-----------------|-----------|-------------|----------|-----|
| evidence-engine | precision | 1.000 [n/a] | -        | 7   |
| evidence-engine | recall    | 1.000 [n/a] | -        | 7   |
| evidence-engine | f1        | 1.000 [n/a] | -        | 7   |

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

| extractor                 | found   | found_matched   | only   | only_matched   |
|---------------------------|---------|-----------------|--------|----------------|
| llm_metric@1#41e1e53a1fc4 | 23      | 23              | 23     | 23             |

Facts no extractor found: metric 4

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                 | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|---------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_metric@1#41e1e53a1fc4 | metric          | all     | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           | -                      | 23     | 23             |
| llm_metric@1#41e1e53a1fc4 | all             | all     | 23      | 27      | 23        | 1.000       | 0.852    | 0.920 | 1.000           | -                      | 23     | 23             |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                 | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|---------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_metric@1#41e1e53a1fc4 | 20      | 24            | 27035          | 2372            | 0.140     |
| llm_screen@1#41b0d6e6793f | 20      | 20            | 18681          | 1747            | 0.141     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 40      | 2.000       |
| input_tokens     | 45716   | 2285.800    |
| made_model_calls | 44      | 2.200       |
| model_calls      | 44      | 2.200       |
| output_tokens    | 4119    | 205.950     |
| seconds          | 44.708  | 2.235       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 2.000          |
| model_calls   | 2.200          |
| input_tokens  | 2285.800       |
| output_tokens | 205.950        |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
