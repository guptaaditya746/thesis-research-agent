# Evaluation of run rag-claude-s1-mixed-r2 on rag-claude-s1-ec928480

Question: Which methods or system variants do the papers compare?
Question id: inv-methods (kind inventory)
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 16      | 15      | 15        | 0.938       | 1.000    | 0.968 | 1.000           |
| all             | paraphrased   | 13      | 13      | 13        | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | distributed   | 14      | 9       | 9         | 0.643       | 1.000    | 0.783 | 1.000           |
| all             | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | all           | 67      | 61      | 61        | 0.910       | 1.000    | 0.953 | 1.000           |
| condition       | explicit      | 16      | 15      | 15        | 0.938       | 1.000    | 0.968 | 1.000           |
| condition       | paraphrased   | 13      | 13      | 13        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | distributed   | 14      | 9       | 9         | 0.643       | 1.000    | 0.783 | 1.000           |
| condition       | complex       | 9       | 9       | 9         | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | contradictory | 15      | 15      | 15        | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all           | 67      | 61      | 61        | 0.910       | 1.000    | 0.953 | 1.000           |

Facts no item matched: 0; items matching no fact: 6.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition.

## B. Synonym merging

| entries   | keyed_entries   | keys   | split   | merged   | clean_share   |
|-----------|-----------------|--------|---------|----------|---------------|
| 30        | 24              | 14     | 10      | 0        | 0.167         |

Each answer entry holds the truth keys of the facts its items matched in A; `split`: keys spread over more than one entry, `merged`: entries holding more than one key, `clean_share`: entries holding one key no other entry holds, of the entries with a key.

## C. Inventory

| system          | target    | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|-----------------|-----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| evidence-engine | condition | 20        | 14                 | 14        | 0.700       | 1.000    | 0.824 | 0.910             | 1.000          | 0.953      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- evidence-engine: false positives B, R, RAG with random passages, denoted by the code A1, The retrieval-augmented generator, denoted by the code R, The vanilla LLM, denoted by the code B, chain-of-thought prompting condition; missed none

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| condition       | 0.953 [0.87, 0.99] | BCa      |
| all             | 0.953 [0.87, 0.99] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric    | interval           | method   | n   |
|-----------------|-----------|--------------------|----------|-----|
| evidence-engine | precision | 0.700 [0.45, 0.85] | BCa      | 20  |
| evidence-engine | recall    | 1.000 [n/a]        | -        | 20  |
| evidence-engine | f1        | 0.824 [0.62, 0.92] | BCa      | 20  |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 88           | 34       | 0.386    |
| all             | paraphrased   | 73           | 30       | 0.411    |
| all             | distributed   | 75           | 32       | 0.427    |
| all             | complex       | 159          | 46       | 0.289    |
| all             | contradictory | 88           | 40       | 0.455    |
| all             | all           | 483          | 182      | 0.377    |
| author_claim    | explicit      | 8            | 0        | 0.000    |
| author_claim    | paraphrased   | 8            | 0        | 0.000    |
| author_claim    | distributed   | 8            | 0        | 0.000    |
| author_claim    | complex       | 8            | 0        | 0.000    |
| author_claim    | contradictory | 8            | 0        | 0.000    |
| author_claim    | all           | 40           | 0        | 0.000    |
| condition       | explicit      | 34           | 34       | 1.000    |
| condition       | paraphrased   | 30           | 30       | 1.000    |
| condition       | distributed   | 32           | 32       | 1.000    |
| condition       | complex       | 46           | 46       | 1.000    |
| condition       | contradictory | 40           | 40       | 1.000    |
| condition       | all           | 182          | 182      | 1.000    |
| measurement     | explicit      | 15           | 0        | 0.000    |
| measurement     | paraphrased   | 13           | 0        | 0.000    |
| measurement     | distributed   | 9            | 0        | 0.000    |
| measurement     | complex       | 50           | 0        | 0.000    |
| measurement     | contradictory | 15           | 0        | 0.000    |
| measurement     | all           | 102          | 0        | 0.000    |
| metric          | explicit      | 31           | 0        | 0.000    |
| metric          | paraphrased   | 22           | 0        | 0.000    |
| metric          | distributed   | 26           | 0        | 0.000    |
| metric          | complex       | 55           | 0        | 0.000    |
| metric          | contradictory | 25           | 0        | 0.000    |
| metric          | all           | 159          | 0        | 0.000    |

## Cascade contribution

| extractor                           | found   | found_matched   | only   | only_matched   |
|-------------------------------------|---------|-----------------|--------|----------------|
| llm_condition@1#f409ef68fc87        | 61      | 55              | 6      | 0              |
| regex_condition_kind@1#f81a9016cc8b | 61      | 61              | 6      | 6              |

Facts no extractor found: none

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                           | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-------------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_condition@1#f409ef68fc87        | condition       | all     | 61      | 61      | 55        | 0.902       | 0.902    | 0.902 | 1.000           | -                      | 6      | 0              |
| llm_condition@1#f409ef68fc87        | all             | all     | 61      | 61      | 55        | 0.902       | 0.902    | 0.902 | 1.000           | -                      | 6      | 0              |
| regex_condition_kind@1#f81a9016cc8b | condition       | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 6      | 6              |
| regex_condition_kind@1#f81a9016cc8b | all             | all     | 61      | 61      | 61        | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 6      | 6              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                           | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-------------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#f409ef68fc87        | 20      | 23            | 24689          | 4216            | 0.135     |
| llm_screen@1#41b0d6e6793f           | 20      | 20            | 18681          | 1748            | 0.135     |
| regex_condition_kind@1#f81a9016cc8b | 20      | 0             | 0              | 0               | 0.135     |
| regex_screen@1#858a6ebc69c6         | 20      | 0             | 0              | 0               | 0.130     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 80      | 4.000       |
| input_tokens     | 43370   | 2168.500    |
| made_model_calls | 43      | 2.150       |
| model_calls      | 43      | 2.150       |
| output_tokens    | 5964    | 298.200     |
| seconds          | 62.753  | 3.138       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 4.000          |
| model_calls   | 2.150          |
| input_tokens  | 2168.500       |
| output_tokens | 298.200        |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
