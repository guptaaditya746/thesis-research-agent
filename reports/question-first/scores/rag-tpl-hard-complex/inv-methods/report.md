# Evaluation of run rag-tpl-hard-complex on rag-tpl-hard-24ab4663

Question: Which methods or system variants do the papers compare?
Question id: inv-methods (kind inventory)
Levels: complex

## A. Extraction

| evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   |
|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|
| all             | complex | 332     | 332     | 332       | 1.000       | 1.000    | 1.000 | 1.000           |
| all             | all     | 332     | 332     | 332       | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | complex | 332     | 332     | 332       | 1.000       | 1.000    | 1.000 | 1.000           |
| condition       | all     | 332     | 332     | 332       | 1.000       | 1.000    | 1.000 | 1.000           |

Facts no item matched: 0; items matching no fact: 0.

Evidence types scored (the protocol's own; the `all` rows pool these only): condition.

## B. Synonym merging

| entries   | keyed_entries   | keys   | split   | merged   | clean_share   |
|-----------|-----------------|--------|---------|----------|---------------|
| 28        | 28              | 28     | 0       | 0        | 1.000         |

Each answer entry holds the truth keys of the facts its items matched in A; `split`: keys spread over more than one entry, `merged`: entries holding more than one key, `clean_share`: entries holding one key no other entry holds, of the entries with a key.

## C. Inventory

| system          | target    | entries   | expected_entries   | matched   | precision   | recall   | f1    | paper_precision   | paper_recall   | paper_f1   |
|-----------------|-----------|-----------|--------------------|-----------|-------------|----------|-------|-------------------|----------------|------------|
| evidence-engine | condition | 28        | 28                 | 28        | 1.000       | 1.000    | 1.000 | 1.000             | 1.000          | 1.000      |
| rag-baseline    | condition | 6         | 28                 | 0         | 0.000       | 0.000    | 0.000 | 0.000             | 0.000          | 0.000      |
| agent-baseline  | condition | 13        | 28                 | 8         | 0.615       | 0.286    | 0.390 | 0.934             | 0.639          | 0.758      |

Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab does not know by its folded name, else it is a false positive), and of (key, paper) pairs.

- evidence-engine: false positives none; missed none
- rag-baseline: false positives byte-level or subword approaches, index encyclopedic corpora split into short passages, pass retrieved passages to the generator as part of the prompt without changing generator weights, retrieve at the token level during decoding, train the retriever and generator jointly, use web search interfaces; missed RAG pipeline, RAG pipeline without context compression, RAG pipeline without passage deduplication, RAG pipeline without query expansion, RAG pipeline without reranking, RAG pipeline without source attribution, RAG with random passages, RAG without reranking, chain-of-thought prompting, closed-book model, fine-tuned model, no-retrieval baseline, parametric-only model, query-rewriting variant, retrieval-augmented generator, retrieval-augmented generator without context compression, retrieval-augmented generator without passage deduplication, retrieval-augmented generator without query expansion, retrieval-augmented generator without reranking, retrieval-augmented model, retrieval-augmented model without context compression, retrieval-augmented model without query expansion, retrieval-augmented model without reranking, retrieve-then-read model, retrieve-then-read model without passage deduplication, retrieve-then-read model without reranking, self-consistency decoding, vanilla LLM
- agent-baseline: false positives byte-pair encoding, jointly-trained retriever+generator, prompt-based RAG, token-level retrieval during decoding, unigram model; missed RAG pipeline without context compression, RAG pipeline without passage deduplication, RAG pipeline without query expansion, RAG pipeline without reranking, RAG pipeline without source attribution, RAG with random passages, RAG without reranking, chain-of-thought prompting, fine-tuned model, query-rewriting variant, retrieval-augmented generator without context compression, retrieval-augmented generator without passage deduplication, retrieval-augmented generator without query expansion, retrieval-augmented generator without reranking, retrieval-augmented model without context compression, retrieval-augmented model without query expansion, retrieval-augmented model without reranking, retrieve-then-read model without passage deduplication, retrieve-then-read model without reranking, self-consistency decoding

## Intervals

95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), `point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate sample (fewer than two papers, or no spread), the point value only.

Extraction F1 (all levels):

| evidence_type   | f1          | method   |
|-----------------|-------------|----------|
| condition       | 1.000 [n/a] | -        |
| all             | 1.000 [n/a] | -        |

C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the answer's):

| system          | metric    | interval           | method   | n   |
|-----------------|-----------|--------------------|----------|-----|
| evidence-engine | precision | 1.000 [n/a]        | -        | 28  |
| evidence-engine | recall    | 1.000 [n/a]        | -        | 28  |
| evidence-engine | f1        | 1.000 [n/a]        | -        | 28  |
| rag-baseline    | precision | 0.000 [n/a]        | -        | 34  |
| rag-baseline    | recall    | 0.000 [n/a]        | -        | 34  |
| rag-baseline    | f1        | 0.000 [n/a]        | -        | 34  |
| agent-baseline  | precision | 0.615 [0.33, 0.88] | BCa      | 33  |
| agent-baseline  | recall    | 0.286 [0.14, 0.48] | BCa      | 33  |
| agent-baseline  | f1        | 0.390 [0.22, 0.60] | BCa      | 33  |

## Locate recall

| evidence_type   | level   | placements   | inside   | recall   |
|-----------------|---------|--------------|----------|----------|
| all             | complex | 4323         | 1454     | 0.336    |
| all             | all     | 4323         | 1454     | 0.336    |
| author_claim    | complex | 212          | 0        | 0.000    |
| author_claim    | all     | 212          | 0        | 0.000    |
| condition       | complex | 1454         | 1454     | 1.000    |
| condition       | all     | 1454         | 1454     | 1.000    |
| measurement     | complex | 1768         | 0        | 0.000    |
| measurement     | all     | 1768         | 0        | 0.000    |
| metric          | complex | 889          | 0        | 0.000    |
| metric          | all     | 889          | 0        | 0.000    |

## Cascade contribution

| extractor                           | found   | found_matched   | only   | only_matched   |
|-------------------------------------|---------|-----------------|--------|----------------|
| llm_condition@1#f409ef68fc87        | 332     | 332             | 19     | 19             |
| regex_condition_kind@1#f81a9016cc8b | 313     | 313             | 0      | 0              |

Facts no extractor found: none

## Per extractor

An item counts for every extractor in its `found_by`; recall is against the facts of the documents and types the extractor was called on (its extractor_call events). `evaluate benchmark` pools these rows per level over corpora.

| extractor                           | evidence_type   | level   | items   | facts   | matched   | precision   | recall   | f1    | span_accuracy   | association_accuracy   | only   | only_matched   |
|-------------------------------------|-----------------|---------|---------|---------|-----------|-------------|----------|-------|-----------------|------------------------|--------|----------------|
| llm_condition@1#f409ef68fc87        | condition       | all     | 332     | 332     | 332       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 19     | 19             |
| llm_condition@1#f409ef68fc87        | all             | all     | 332     | 332     | 332       | 1.000       | 1.000    | 1.000 | 1.000           | -                      | 19     | 19             |
| regex_condition_kind@1#f81a9016cc8b | condition       | all     | 313     | 332     | 313       | 1.000       | 0.943    | 0.971 | 1.000           | -                      | 0      | 0              |
| regex_condition_kind@1#f81a9016cc8b | all             | all     | 313     | 332     | 313       | 1.000       | 0.943    | 0.971 | 1.000           | -                      | 0      | 0              |

Cost per extractor (tokens need the record cache, seconds the events):

| extractor                           | calls   | model_calls   | input_tokens   | output_tokens   | seconds   |
|-------------------------------------|---------|---------------|----------------|-----------------|-----------|
| llm_condition@1#f409ef68fc87        | 106     | 131           | 142479         | 25593           | 0.721     |
| llm_screen@1#41b0d6e6793f           | 109     | 109           | 102099         | 8138            | 0.713     |
| regex_condition_kind@1#f81a9016cc8b | 106     | 0             | 0              | 0               | 0.701     |
| regex_screen@1#858a6ebc69c6         | 112     | 0             | 0              | 0               | 0.728     |

## Cost

| measure          | total   | per_paper   |
|------------------|---------|-------------|
| cached_calls     | 0       | 0.000       |
| calls            | 433     | 3.866       |
| input_tokens     | 244578  | 2183.732    |
| made_model_calls | 240     | 2.143       |
| model_calls      | 240     | 2.143       |
| output_tokens    | 33781   | 301.616     |
| seconds          | 339.690 | 3.033       |
| workers          | 3       | -           |

## Funnel

Strategy `gaps` over 112 documents (docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.

| measure       | per_document   |
|---------------|----------------|
| calls         | 3.866          |
| model_calls   | 2.143          |
| input_tokens  | 2183.732       |
| output_tokens | 301.170        |

| stopped_after   | documents   |
|-----------------|-------------|
| exhausted       | 106         |
| skipped         | 6           |

Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the relevant papers kept):

| documents   | tp   | fp   | fn   | tn   | precision   | recall   |
|-------------|------|------|------|------|-------------|----------|
| 112         | 106  | 0    | 0    | 6    | 1.000       | 1.000    |

Screened out wrongly: none
