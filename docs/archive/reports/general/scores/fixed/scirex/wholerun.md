# Whole run: scirex

left out: 77 of 270 relations (document not in the corpus)
Sample: 15 questions (n=15, seed=0).
Held out for tuning: 4.

## Rows (mean headline per question)

Rows cover different questions; compare rows only through the paired means below.

| row | n | missing run | unscored | mean [95%] | mean tau | answer-key split |
|---|---|---|---|---|---|---|
| auto-confirmed/on | 15 | 0 | 11 | 0.033 [0.00, 0.17] | - | synthesis error 3, extraction error 12 |
| auto-confirmed/off | 15 | 0 | 11 | 0.033 [0.00, 0.17] | - | synthesis error 3, extraction error 12 |
| rag/global | 15 | 0 | 1 | 0.047 [0.00, 0.17] | - | - |
| rag/per_paper | 15 | 0 | 3 | 0.071 [0.02, 0.19] | - | - |

## Engine against RAG (paired, same questions)

| engine row | RAG row | n | missing run | wins | losses | ties | engine mean | RAG mean | mean difference [95%] |
|---|---|---|---|---|---|---|---|---|---|
| auto-confirmed/on | rag/global | 15 | 0 | 1 | 2 | 12 | 0.033 | 0.047 | -0.013 [-0.11, 0.10] |
| auto-confirmed/on | rag/per_paper | 15 | 0 | 1 | 2 | 12 | 0.033 | 0.071 | -0.038 [-0.14, 0.01] |
| auto-confirmed/off | rag/global | 15 | 0 | 1 | 2 | 12 | 0.033 | 0.047 | -0.013 [-0.11, 0.10] |
| auto-confirmed/off | rag/per_paper | 15 | 0 | 1 | 2 | 12 | 0.033 | 0.071 | -0.038 [-0.14, 0.01] |

## Answer-key split per question

| row | question | split |
|---|---|---|
| auto-confirmed/on | scirex-001 | synthesis error |
| auto-confirmed/on | scirex-003 | extraction error |
| auto-confirmed/on | scirex-004 | extraction error |
| auto-confirmed/on | scirex-005 | extraction error |
| auto-confirmed/on | scirex-006 | extraction error |
| auto-confirmed/on | scirex-007 | extraction error |
| auto-confirmed/on | scirex-008 | synthesis error |
| auto-confirmed/on | scirex-010 | extraction error |
| auto-confirmed/on | scirex-011 | synthesis error |
| auto-confirmed/on | scirex-012 | extraction error |
| auto-confirmed/on | scirex-015 | extraction error |
| auto-confirmed/on | scirex-016 | extraction error |
| auto-confirmed/on | scirex-017 | extraction error |
| auto-confirmed/on | scirex-018 | extraction error |
| auto-confirmed/on | scirex-019 | extraction error |
| auto-confirmed/off | scirex-001 | synthesis error |
| auto-confirmed/off | scirex-003 | extraction error |
| auto-confirmed/off | scirex-004 | extraction error |
| auto-confirmed/off | scirex-005 | extraction error |
| auto-confirmed/off | scirex-006 | extraction error |
| auto-confirmed/off | scirex-007 | extraction error |
| auto-confirmed/off | scirex-008 | synthesis error |
| auto-confirmed/off | scirex-010 | extraction error |
| auto-confirmed/off | scirex-011 | synthesis error |
| auto-confirmed/off | scirex-012 | extraction error |
| auto-confirmed/off | scirex-015 | extraction error |
| auto-confirmed/off | scirex-016 | extraction error |
| auto-confirmed/off | scirex-017 | extraction error |
| auto-confirmed/off | scirex-018 | extraction error |
| auto-confirmed/off | scirex-019 | extraction error |

## Fresh query or saved template

- auto-confirmed: 0 of 15 questions answered with a fresh query, 15 with a saved template.
