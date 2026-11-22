# Whole run: scilead

left out: 28 of 140 (no open full text)
Sample: 22 questions (n=22, seed=0).
Held out for tuning: 1.

## Rows (mean headline per question)

Rows cover different questions; compare rows only through the paired means below.

| row | n | missing run | unscored | mean [95%] | mean tau | answer-key split |
|---|---|---|---|---|---|---|
| auto-confirmed/on | 22 | 0 | 0 | 0.136 [0.05, 0.35] | 0.200 | synthesis error 19, key split failed 2, extraction error 1 |
| auto-confirmed/off | 22 | 0 | 0 | 0.045 [0.00, 0.18] | -0.200 | synthesis error 19, key split failed 2, extraction error 1 |
| rag/global | 22 | 0 | 0 | 0.364 [0.18, 0.59] | 0.429 | - |
| rag/per_paper | 22 | 0 | 0 | 0.318 [0.14, 0.55] | 0.417 | - |

## Engine against RAG (paired, same questions)

| engine row | RAG row | n | missing run | wins | losses | ties | engine mean | RAG mean | mean difference [95%] |
|---|---|---|---|---|---|---|---|---|---|
| auto-confirmed/on | rag/global | 22 | 0 | 0 | 5 | 17 | 0.136 | 0.364 | -0.227 [-0.45, -0.09] |
| auto-confirmed/on | rag/per_paper | 22 | 0 | 1 | 5 | 16 | 0.136 | 0.318 | -0.182 [-0.41, 0.00] |
| auto-confirmed/off | rag/global | 22 | 0 | 0 | 7 | 15 | 0.045 | 0.364 | -0.318 [-0.55, -0.14] |
| auto-confirmed/off | rag/per_paper | 22 | 0 | 1 | 7 | 14 | 0.045 | 0.318 | -0.273 [-0.50, -0.05] |

## Answer-key split per question

| row | question | split |
|---|---|---|
| auto-confirmed/on | scilead-02 | synthesis error |
| auto-confirmed/on | scilead-03 | synthesis error |
| auto-confirmed/on | scilead-04 | synthesis error |
| auto-confirmed/on | scilead-05 | key split failed: ValueError: missing parameter(s) ['metric'] for the query (declared in its header) |
| auto-confirmed/on | scilead-06 | key split failed: ValueError: missing parameter(s) ['metric'] for the query (declared in its header) |
| auto-confirmed/on | scilead-07 | synthesis error |
| auto-confirmed/on | scilead-08 | synthesis error |
| auto-confirmed/on | scilead-09 | synthesis error |
| auto-confirmed/on | scilead-10 | synthesis error |
| auto-confirmed/on | scilead-11 | synthesis error |
| auto-confirmed/on | scilead-12 | synthesis error |
| auto-confirmed/on | scilead-13 | synthesis error |
| auto-confirmed/on | scilead-15 | synthesis error |
| auto-confirmed/on | scilead-17 | synthesis error |
| auto-confirmed/on | scilead-18 | synthesis error |
| auto-confirmed/on | scilead-19 | synthesis error |
| auto-confirmed/on | scilead-21 | synthesis error |
| auto-confirmed/on | scilead-22 | synthesis error |
| auto-confirmed/on | scilead-23 | synthesis error |
| auto-confirmed/on | scilead-24 | synthesis error |
| auto-confirmed/on | scilead-26 | synthesis error |
| auto-confirmed/on | scilead-27 | extraction error |
| auto-confirmed/off | scilead-02 | synthesis error |
| auto-confirmed/off | scilead-03 | synthesis error |
| auto-confirmed/off | scilead-04 | synthesis error |
| auto-confirmed/off | scilead-05 | key split failed: ValueError: missing parameter(s) ['metric'] for the query (declared in its header) |
| auto-confirmed/off | scilead-06 | key split failed: ValueError: missing parameter(s) ['metric'] for the query (declared in its header) |
| auto-confirmed/off | scilead-07 | synthesis error |
| auto-confirmed/off | scilead-08 | synthesis error |
| auto-confirmed/off | scilead-09 | synthesis error |
| auto-confirmed/off | scilead-10 | synthesis error |
| auto-confirmed/off | scilead-11 | synthesis error |
| auto-confirmed/off | scilead-12 | synthesis error |
| auto-confirmed/off | scilead-13 | synthesis error |
| auto-confirmed/off | scilead-15 | synthesis error |
| auto-confirmed/off | scilead-17 | synthesis error |
| auto-confirmed/off | scilead-18 | synthesis error |
| auto-confirmed/off | scilead-19 | synthesis error |
| auto-confirmed/off | scilead-21 | synthesis error |
| auto-confirmed/off | scilead-22 | synthesis error |
| auto-confirmed/off | scilead-23 | synthesis error |
| auto-confirmed/off | scilead-24 | synthesis error |
| auto-confirmed/off | scilead-26 | synthesis error |
| auto-confirmed/off | scilead-27 | extraction error |

## Fresh query or saved template

- auto-confirmed: 0 of 22 questions answered with a fresh query, 22 with a saved template.
