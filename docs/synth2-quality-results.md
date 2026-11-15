# Synthetic data quality: results

15 Nov 2026. Shared as a Claude Doc: https://claude.ai/artifact/Y9Mi34XBuHUe4m6PakGJnd

The synthetic corpus is fit for the evaluation: the planted facts can be read back almost perfectly (179 of 180 sampled papers), and lazy shortcut rules cannot recover the planted answer. It is not yet indistinguishable from real papers: a word-based classifier still tells them apart, mainly by topic.

## The data

The corpus has 450 corpora with 9,090 papers in all, on one topic: retrieval-augmented vs closed-book question answering.

- **Grid:** 3 shapes of the true effect (uniform, one-sided, opposed) × 3 ways of reporting it (prose, split, table) × 10 seeds × 5 variants (base, duplicate, spun, twin, twin-neutral).
- **How a paper is built:** a real paper from a screened pool of 21 is renamed (every person, system and dataset name becomes an invented word), real retrieval-vs-no-retrieval results are cut, and code writes the planted section (counts per subset) and the planted claim into it.
- **Answer key:** every planted count, subset and claim is stored per corpus, so each check below scores against exact values.

The papers stay local because they are built from real papers; no real person or paper is presented as the source of a planted result.

## Check 1: can the planted facts be read back?

Yes: a blind reader recovers every planted fact in 179 of 180 sampled papers (95% CI 0.969–0.999).

A cheap model (Claude Haiku) read each paper alone, with no answer key, and wrote down the study label, benchmark, claim and the counts per subset. The sample is 4 papers per family and variant (180 papers, 819 facts).

| Step | Papers fully right | Note |
| --- | --- | --- |
| As read | 168 / 180 | 0.887–0.961 |
| Filing mix-ups fixed | 178 / 180 | 5 pairs of answers filed under the wrong paper (6 papers per reader); reader error, not data error |
| Reader prompt v4 | 179 / 180 | the reader had dropped the tag “, extended version” from a duplicate's label |

The one miss left (D083) is the reader's: it could not map the wording “popular entities” to the common-fact level and wrote “unknown”; the counts were right.

## Check 2: do the papers read like real ones?

Partly: with names hidden, a classifier tells synthetic from real pieces at AUC 0.73, and the main cue is topic, not style.

The test is a classifier two-sample test (C2ST): a TF-IDF logistic regression tries to tell \~1,000-word pieces of synthetic papers from pieces of 85 real held-out papers. Folds are grouped by real source, so no source is in both training and test. AUC 0.5 means it cannot tell them apart; 1.0 means it always can.

| What the classifier sees | AUC |
| --- | --- |
| All words | 0.954 |
| Words, names hidden | 0.726 |
| Function words only (the, of, which…) | 0.589 |
| Surface only (lengths, punctuation, numbers) | 0.644 |

All words are near-perfect because every synthetic paper is about retrieval and question answering while the real pieces cover many topics. Function words and surface are close to chance, so the writing style is close to real. Making the invented names sayable changed nothing measurable (masked view 0.677 before, 0.703 after, mean of 3 samples). Numbers are from the 21-source pool, 4 papers per source.

## Check 3: can a lazy rule get the answer?

No: simple shortcut rules recover the true effect in about one corpus in three, while pooling the planted counts recovers it in all.

| Rule | How it decides | Corpora where it recovers the true effect |
| --- | --- | --- |
| Answer key (pooled planted counts) | reads every subset's counts correctly | 1.00 |
| Vote | majority of the papers' claims | 0.33 |
| Lumped | adds counts across subsets, ignoring them | 0.33 |
| Trusts claims | believes each paper's stated claim | 0.31 |

The traps work as meant: the lumped rule falls for every subset trap, and the claim-trusting rule never resists a spun claim. So a system can only score well by reading the subset counts, which is what the evaluation is meant to test.

## Real results left in the papers

621 of 9,090 papers (6.8%) still carry a real retrieval-vs-none result from their source paper; each one is now listed in the answer key, so a system that reports it is not marked wrong.

Two of the 21 source papers report their own retrieval result in prose, tables and abstract, so cutting it would break the text. They are used only where that result agrees with the planted claim:

| Source | Papers built on it | Planted claim allowed | Leftovers per paper |
| --- | --- | --- | --- |
| FActScore (2305.14251) | 441 | helps | 6 (search-augmented model scores highest; 2 tables) |
| RETRO (2112.04426) | 180 | no effect | 1 (“comparable performance” with far fewer parameters) |

Two RETRO sentences that said retrieval helps were cut, as they disagreed with its no-effect claim. The leftovers can never flip the answer, but they give a lazy system a hint toward the right direction in these papers.

## Limits and next step

- **Realism:** papers are recognisable by topic. A planned rewrite loop (rewrite the pieces the classifier flags, re-check facts) is not built; it is future work.
- **Reader sample:** fact recovery is measured on 180 of 9,090 papers; the whole set would need a cluster run.
- **One topic:** all corpora are about retrieval vs closed-book question answering.

Next: run the system on the full corpus and score extraction, integration and answer separately against the answer key.

**Question:** Is a corpus that a classifier can still tell from real papers by topic (AUC 0.73 with names hidden) good enough to evaluate on, or should I build the rewrite loop first? By default I would go ahead with the evaluation and keep the rewrite loop as future work.
