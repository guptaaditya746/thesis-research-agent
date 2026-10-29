# Evaluation of run rag-tpl-hard-complex on rag-tpl-hard-24ab4663

Question: Which datasets do the papers evaluate on?
Question id: inv-datasets (kind inventory)
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 259     | 212     | 212       | 0.819       | 1.000    | 0.900 | -               |
| all             | all     | 259     | 212     | 212       | 0.819       | 1.000    | 0.900 | -               |
| dataset         | complex | 259     | 212     | 212       | 0.819       | 1.000    | 0.900 | -               |
| dataset         | all     | 259     | 212     | 212       | 0.819       | 1.000    | 0.900 | -               |

Facts no item matched: 0; items matching no fact: 47.

Evidence types scored (the protocol's own; the `all` rows pool these only): dataset.

## B. Synonym merging

| entries   | keyed_entries   | keys   | split   | merged   | clean_share   |
|-----------|-----------------|--------|---------|----------|---------------|
| 16        | 10              | 10     | 0       | 0        | 1.000         |

Each answer entry holds the truth keys of the facts its items matched in A; `split`: keys spread over more than one entry, `merged`: entries holding more than one key, `clean_share`: entries holding one key no other entry holds, of the entries with a key.

## C. Inventory

| system          | target   | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|-----------------|----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| evidence-engine | dataset  | 16        | 10                 | 10        | 0.625       | 1.000    | 0.769 | 0.819             | 1.000          | 0.900      |
| rag-baseline    | dataset  | 4         | 10                 | 4         | 1.000       | 0.400    | 0.571 | 0.250             | 0.019          | 0.035      |
| agent-baseline  | dataset  | 10        | 10                 | 10        | 1.000       | 1.000    | 1.000 | 1.000             | 1.000          | 1.000      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- evidence-engine: false positives Our prompts, document collection, encyclopedic corpus, external document collection, external documents, retrieved documents; missed none
- rag-baseline: false positives none; missed BioClaimQA, GeoFacts, HistoryQuest, LawFactQA, MedAnswerSet, NewsTruthQA
- agent-baseline: false positives none; missed none

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1                 | method   |
|-----------------|--------------------|----------|
| dataset         | 0.900 [0.88, 0.92] | BCa      |
| all             | 0.900 [0.88, 0.92] | BCa      |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric    | interval           | method     | n   |
|-----------------|-----------|--------------------|------------|-----|
| evidence-engine | precision | 0.625 [0.38, 0.81] | BCa        | 16  |
| evidence-engine | recall    | 1.000 [n/a]        | -          | 16  |
| evidence-engine | f1        | 0.769 [0.55, 0.90] | BCa        | 16  |
| rag-baseline    | precision | 1.000 [1.00, 1.00] | percentile | 10  |
| rag-baseline    | recall    | 0.400 [0.10, 0.70] | BCa        | 10  |
| rag-baseline    | f1        | 0.571 [0.18, 0.82] | BCa        | 10  |
| agent-baseline  | precision | 1.000 [n/a]        | -          | 10  |
| agent-baseline  | recall    | 1.000 [n/a]        | -          | 10  |
| agent-baseline  | f1        | 1.000 [n/a]        | -          | 10  |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 4323         | 0        | 0.000    |
| all             | all     | 4323         | 0        | 0.000    |
| author_claim    | complex | 212          | 0        | 0.000    |
| author_claim    | all     | 212          | 0        | 0.000    |
| condition       | complex | 1454         | 0        | 0.000    |
| condition       | all     | 1454         | 0        | 0.000    |
| measurement     | complex | 1768         | 0        | 0.000    |
| measurement     | all     | 1768         | 0        | 0.000    |
| metric          | complex | 889          | 0        | 0.000    |
| metric          | all     | 889          | 0        | 0.000    |

## Cascade contribution

| extractor                     | found   | found_matched   | only   | only_matched   |
|-------------------------------|---------|-----------------|--------|----------------|
| gliner_dataset@1#bbf10b224d67 | 254     | 207             | 47     | 0              |
| llm_dataset@1#0657dd619876    | 212     | 212             | 0      | 0              |
| regex_dataset@1#85380ccc622a  | 212     | 212             | 0      | 0              |

Facts no extractor found: none

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                     | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| gliner_dataset@1#bbf10b224d67 | dataset         | all     | 254     | 212     | 207       | 0.815       | 0.976    | 0.888 | -               | -                      | 47     | 0              |
| gliner_dataset@1#bbf10b224d67 | all             | all     | 254     | 212     | 207       | 0.815       | 0.976    | 0.888 | -               | -                      | 47     | 0              |
| llm_dataset@1#0657dd619876    | dataset         | all     | 212     | 212     | 212       | 1.000       | 1.000    | 1.000 | -               | -                      | 0      | 0              |
| llm_dataset@1#0657dd619876    | all             | all     | 212     | 212     | 212       | 1.000       | 1.000    | 1.000 | -               | -                      | 0      | 0              |
| regex_dataset@1#85380ccc622a  | dataset         | all     | 212     | 212     | 212       | 1.000       | 1.000    | 1.000 | -               | -                      | 0      | 0              |
| regex_dataset@1#85380ccc622a  | all             | all     | 212     | 212     | 212       | 1.000       | 1.000    | 1.000 | -               | -                      | 0      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                     | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-------------------------------|---------|---------------|----------------|-----------------|-----------|
| gliner_dataset@1#bbf10b224d67 | 106     | 356           | 0              | 0               | 0.747     |
| llm_dataset@1#0657dd619876    | 106     | 107           | 114543         | 13170           | 0.701     |
| llm_screen@1#41b0d6e6793f     | 109     | 109           | 102099         | 8168            | 0.716     |
| regex_dataset@1#85380ccc622a  | 106     | 0             | 0              | 0               | 0.688     |
| regex_screen@1#858a6ebc69c6   | 112     | 0             | 0              | 0               | 0.724     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 539     | 4.812       |
| input_tokens     | 216642  | 1934.304    |
| made_model_calls | 572     | 5.107       |
| model_calls      | 572     | 5.107       |
| output_tokens    | 21338   | 190.518     |
| seconds          | 236.692 | 2.113       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 4.812          |
| model_calls   | 5.107          |
| input_tokens  | 1934.304       |
| output_tokens | 190.518        |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 106         |
| skipped         | 6           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 0    | 0    | 6    | 1.000       | 1.000    |

Screened out wrongly: none
