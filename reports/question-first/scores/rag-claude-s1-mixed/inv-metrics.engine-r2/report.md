# Evaluation of run rag-claude-s1-mixed-r2 on rag-claude-s1-ec928480

Question: Which evaluation metrics do the papers report?
Question id: inv-metrics (kind inventory)
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 7       | 4       | 4         | 0.571       | 1.000    | 0.727 | 1.000           |
| all             | paraphrased   | 5       | 4       | 1         | 0.200       | 0.250    | 0.222 | 1.000           |
| all             | distributed   | 15      | 4       | 4         | 0.267       | 1.000    | 0.421 | 1.000           |
| all             | complex       | 19      | 11      | 11        | 0.579       | 1.000    | 0.733 | 1.000           |
| all             | contradictory | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| all             | all           | 51      | 27      | 24        | 0.471       | 0.889    | 0.615 | 1.000           |
| metric          | explicit      | 7       | 4       | 4         | 0.571       | 1.000    | 0.727 | 1.000           |
| metric          | paraphrased   | 5       | 4       | 1         | 0.200       | 0.250    | 0.222 | 1.000           |
| metric          | distributed   | 15      | 4       | 4         | 0.267       | 1.000    | 0.421 | 1.000           |
| metric          | complex       | 19      | 11      | 11        | 0.579       | 1.000    | 0.733 | 1.000           |
| metric          | contradictory | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | 1.000           |
| metric          | all           | 51      | 27      | 24        | 0.471       | 0.889    | 0.615 | 1.000           |

Facts no item matched: 3; items matching no fact: 27.

Evidence types scored (the protocol's own; the `all` rows pool these only): metric.

## B. Synonym merging

| entries   | keyed_entries   | keys   | split   | merged   | clean_share   |
|-----------|-----------------|--------|---------|----------|---------------|
| 25        | 8               | 7      | 1       | 0        | 0.750         |

Each answer entry holds the truth keys of the facts its items matched in A; `split`: keys spread over more than one entry, `merged`: entries holding more than one key, `clean_share`: entries holding one key no other entry holds, of the entries with a key.

## C. Inventory

| system          | target   | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|-----------------|----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| evidence-engine | metric   | 21        | 7                  | 7         | 0.333       | 1.000    | 0.500 | 0.533             | 0.889          | 0.667      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- evidence-engine: false positives Accuracy, Factual Accuracy, HR (%), Performance, PopCultureQA, ROUGE-L metric, Retrieval augmentation, answer accuracy metric, fact-level accuracy metric, fluency, latency metric, one metric, outcome measure, percentage; missed none

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| metric          | 0.615 [0.52, 0.73] | BCa      |
| all             | 0.615 [0.52, 0.73] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric    | interval           | method   | n   |
|-----------------|-----------|--------------------|----------|-----|
| evidence-engine | precision | 0.333 [0.14, 0.57] | BCa      | 21  |
| evidence-engine | recall    | 1.000 [n/a]        | -        | 21  |
| evidence-engine | f1        | 0.500 [0.25, 0.73] | BCa      | 21  |

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
| abbrev_metric@1#8bc3c347fdea | 4       | 4               | 0      | 0              |
| gliner_metric@1#13cd7bab1b65 | 43      | 22              | 21     | 0              |
| llm_metric@1#41e1e53a1fc4    | 22      | 22              | 2      | 2              |
| regex_metric@2#d4eacbf703f6  | 24      | 18              | 6      | 0              |

Facts no extractor found: metric 3

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                    | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| abbrev_metric@1#8bc3c347fdea | metric          | all     | 4       | 27      | 4         | 1.000       | 0.148    | 0.258 | 1.000           | -                      | 0      | 0              |
| abbrev_metric@1#8bc3c347fdea | all             | all     | 4       | 27      | 4         | 1.000       | 0.148    | 0.258 | 1.000           | -                      | 0      | 0              |
| gliner_metric@1#13cd7bab1b65 | metric          | all     | 43      | 27      | 22        | 0.512       | 0.815    | 0.629 | 1.000           | -                      | 21     | 0              |
| gliner_metric@1#13cd7bab1b65 | all             | all     | 43      | 27      | 22        | 0.512       | 0.815    | 0.629 | 1.000           | -                      | 21     | 0              |
| llm_metric@1#41e1e53a1fc4    | metric          | all     | 22      | 27      | 22        | 1.000       | 0.815    | 0.898 | 1.000           | -                      | 2      | 2              |
| llm_metric@1#41e1e53a1fc4    | all             | all     | 22      | 27      | 22        | 1.000       | 0.815    | 0.898 | 1.000           | -                      | 2      | 2              |
| regex_metric@2#d4eacbf703f6  | metric          | all     | 24      | 27      | 18        | 0.750       | 0.667    | 0.706 | 1.000           | -                      | 6      | 0              |
| regex_metric@2#d4eacbf703f6  | all             | all     | 24      | 27      | 18        | 0.750       | 0.667    | 0.706 | 1.000           | -                      | 6      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                    | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|------------------------------|---------|---------------|----------------|-----------------|-----------|
| abbrev_metric@1#8bc3c347fdea | 20      | 0             | 0              | 0               | 0.130     |
| gliner_metric@1#13cd7bab1b65 | 20      | 64            | 0              | 0               | 0.140     |
| llm_metric@1#41e1e53a1fc4    | 20      | 22            | 25275          | 2150            | 0.134     |
| llm_screen@1#41b0d6e6793f    | 20      | 20            | 18681          | 1749            | 0.131     |
| regex_metric@2#d4eacbf703f6  | 20      | 0             | 0              | 0               | 0.133     |
| regex_screen@1#858a6ebc69c6  | 20      | 0             | 0              | 0               | 0.134     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 120     | 6.000       |
| input_tokens     | 43956   | 2197.800    |
| made_model_calls | 106     | 5.300       |
| model_calls      | 106     | 5.300       |
| output_tokens    | 3899    | 194.950     |
| seconds          | 53.265  | 2.663       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 6.000          |
| model_calls   | 5.300          |
| input_tokens  | 2197.800       |
| output_tokens | 194.950        |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
