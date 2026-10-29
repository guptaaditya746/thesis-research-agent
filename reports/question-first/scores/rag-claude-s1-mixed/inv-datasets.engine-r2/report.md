# Evaluation of run rag-claude-s1-mixed-r2 on rag-claude-s1-ec928480

Question: Which datasets do the papers evaluate on?
Question id: inv-datasets (kind inventory)
Levels: complex, contradictory, distributed, explicit, paraphrased

## A. Extraction

| evidence_type   | level         | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | -               |
| all             | paraphrased   | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | -               |
| all             | distributed   | 7       | 4       | 4         | 0.571       | 1.000    | 0.727 | -               |
| all             | complex       | 10      | 8       | 8         | 0.800       | 1.000    | 0.889 | -               |
| all             | contradictory | 9       | 4       | 4         | 0.444       | 1.000    | 0.615 | -               |
| all             | all           | 35      | 24      | 24        | 0.686       | 1.000    | 0.814 | -               |
| dataset         | explicit      | 4       | 4       | 4         | 1.000       | 1.000    | 1.000 | -               |
| dataset         | paraphrased   | 5       | 4       | 4         | 0.800       | 1.000    | 0.889 | -               |
| dataset         | distributed   | 7       | 4       | 4         | 0.571       | 1.000    | 0.727 | -               |
| dataset         | complex       | 10      | 8       | 8         | 0.800       | 1.000    | 0.889 | -               |
| dataset         | contradictory | 9       | 4       | 4         | 0.444       | 1.000    | 0.615 | -               |
| dataset         | all           | 35      | 24      | 24        | 0.686       | 1.000    | 0.814 | -               |

Facts no item matched: 0; items matching no fact: 11.

Evidence types scored (the protocol's own; the `all` rows pool these only): dataset.

## B. Synonym merging

| entries   | keyed_entries   | keys   | split   | merged   | clean_share   |
|-----------|-----------------|--------|---------|----------|---------------|
| 18        | 9               | 9      | 0       | 0        | 1.000         |

Each answer entry holds the truth keys of the facts its items matched in A; `split`: keys spread over more than one entry, `merged`: entries holding more than one key, `clean_share`: entries holding one key no other entry holds, of the entries with a key.

## C. Inventory

| system          | target   | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|-----------------|----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| evidence-engine | dataset  | 18        | 9                  | 9         | 0.500       | 1.000    | 0.667 | 0.686             | 1.000          | 0.814      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- evidence-engine: false positives 1,000 questions, ROUGE-L, current news items, encyclopedic articles, reference collection, reference facts, source entries, trivia questions, two question sets; missed none

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| dataset         | 0.814 [0.72, 0.89] | BCa      |
| all             | 0.814 [0.72, 0.89] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric    | interval           | method   | n   |
|-----------------|-----------|--------------------|----------|-----|
| evidence-engine | precision | 0.500 [0.28, 0.72] | BCa      | 18  |
| evidence-engine | recall    | 1.000 [n/a]        | -        | 18  |
| evidence-engine | f1        | 0.667 [0.43, 0.84] | BCa      | 18  |

## Locate recall

| evidence_type   | level         | placements   | inside   | recall   |
|-----------------|---------------|--------------|----------|----------|
| all             | explicit      | 88           | 0        | 0.000    |
| all             | paraphrased   | 73           | 0        | 0.000    |
| all             | distributed   | 75           | 0        | 0.000    |
| all             | complex       | 159          | 0        | 0.000    |
| all             | contradictory | 88           | 0        | 0.000    |
| all             | all           | 483          | 0        | 0.000    |
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
| metric          | explicit      | 31           | 0        | 0.000    |
| metric          | paraphrased   | 22           | 0        | 0.000    |
| metric          | distributed   | 26           | 0        | 0.000    |
| metric          | complex       | 55           | 0        | 0.000    |
| metric          | contradictory | 25           | 0        | 0.000    |
| metric          | all           | 159          | 0        | 0.000    |

## Cascade contribution

| extractor                     | found   | found_matched   | only   | only_matched   |
|-------------------------------|---------|-----------------|--------|----------------|
| gliner_dataset@1#bbf10b224d67 | 35      | 24              | 11     | 0              |
| llm_dataset@1#0657dd619876    | 24      | 24              | 0      | 0              |
| regex_dataset@1#85380ccc622a  | 24      | 24              | 0      | 0              |

Facts no extractor found: none

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                     | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| gliner_dataset@1#bbf10b224d67 | dataset         | all     | 35      | 24      | 24        | 0.686       | 1.000    | 0.814 | -               | -                      | 11     | 0              |
| gliner_dataset@1#bbf10b224d67 | all             | all     | 35      | 24      | 24        | 0.686       | 1.000    | 0.814 | -               | -                      | 11     | 0              |
| llm_dataset@1#0657dd619876    | dataset         | all     | 24      | 24      | 24        | 1.000       | 1.000    | 1.000 | -               | -                      | 0      | 0              |
| llm_dataset@1#0657dd619876    | all             | all     | 24      | 24      | 24        | 1.000       | 1.000    | 1.000 | -               | -                      | 0      | 0              |
| regex_dataset@1#85380ccc622a  | dataset         | all     | 24      | 24      | 24        | 1.000       | 1.000    | 1.000 | -               | -                      | 0      | 0              |
| regex_dataset@1#85380ccc622a  | all             | all     | 24      | 24      | 24        | 1.000       | 1.000    | 1.000 | -               | -                      | 0      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                     | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-------------------------------|---------|---------------|----------------|-----------------|-----------|
| gliner_dataset@1#bbf10b224d67 | 20      | 64            | 0              | 0               | 0.141     |
| llm_dataset@1#0657dd619876    | 20      | 30            | 31182          | 2223            | 0.130     |
| llm_screen@1#41b0d6e6793f     | 20      | 20            | 18681          | 1748            | 0.131     |
| regex_dataset@1#85380ccc622a  | 20      | 0             | 0              | 0               | 0.128     |
| regex_screen@1#858a6ebc69c6   | 20      | 0             | 0              | 0               | 0.132     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 100     | 5.000       |
| input_tokens     | 49863   | 2493.150    |
| made_model_calls | 114     | 5.700       |
| model_calls      | 114     | 5.700       |
| output_tokens    | 3971    | 198.550     |
| seconds          | 48.962  | 2.448       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 20 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 5.000          |
| model_calls   | 5.700          |
| input_tokens  | 2493.150       |
| output_tokens | 198.550        |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 20          |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 20          | 20   | 0    | 0    | 0    | 1.000       | 1.000    |

Screened out wrongly: none
