# Experimental Log

## 1. Setting
* **Paper type:** a position paper backed by pooled evidence.
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Question:** Inconsistencies in the reported effectiveness of neural keyword extraction methods across different models and evaluation settings.
* **Main conclusion to support:** The performance of neural keyword extraction methods is unstable, with recent studies failing to replicate earlier gains and reporting no significant improvement over baselines.

## 2. Sources
### Method
| Name | Short names | Details |
|---|---|---|
| Trasor extraction | Trasor | family: graph-based; summary: builds a co-occurrence graph of terms in a document and ranks them by centrality to select keywords |
| Steferis extraction | Steferis | family: neural; summary: uses a transformer encoder to score each token for its likelihood of being a keyword based on context |

### Study
| Name | Short names | Details |
|---|---|---|
| the Braliram 2021 study | Braliram 2021 | year: 2021; model: Kolal-7B; benchmark: the Togobe-KW benchmark; setting: zero-shot; summary: evaluates the graph-based method on keyword extraction, finding it outperforms the baseline by 4% F1 |
| the Lomakra 2022 study | Lomakra 2022 | year: 2022; model: Stosa-13B; benchmark: the Togobe-KW benchmark; setting: few-shot, 5 examples; summary: tests the neural method on keyword extraction, reporting a significant gain over the zero-shot baseline |
| the Grovim 2024 study | Grovim 2024 | year: 2024; model: Stosa-13B; benchmark: the Togobe-KW benchmark; setting: zero-shot; summary: re-evaluates the neural method on keyword extraction, finding no clear difference from the baseline score |
| the Nodabril 2026 study | Nodabril 2026 | year: 2026; model: Stosa-13B; benchmark: the Togobe-KW benchmark; setting: zero-shot; summary: attempts to replicate the results of the 2022 study on the neural method but fails to observe the reported gain |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Grovim 2024 study | reported no gain from | Steferis extraction |
| the Nodabril 2026 study | failed to replicate | the Lomakra 2022 study |
| the Nodabril 2026 study | reported no gain from | Steferis extraction |
| the Lomakra 2022 study | reported a gain from | Steferis extraction |
| the Grovim 2024 study | reported no gain from | Trasor extraction |
| the Nodabril 2026 study | failed to replicate | the Braliram 2021 study |

## 4. Numbers (data; every value exactly as written, in its placement)
| Row id | Item | Value | Unit | Placement |
|---|---|---|---|---|
| R-llm-04-01 | the Grovim 2024 study: seeds | 3 | n | table |
| R-llm-04-02 | the Grovim 2024 study: test items | 4950 | n | table |
| R-llm-04-03 | the Nodabril 2026 study: seeds | 5 | n | table |
| R-llm-04-04 | the Nodabril 2026 study: test items | 6900 | n | table |
| R-llm-04-05 | the Lomakra 2022 study: seeds | 1 | n | table |
| R-llm-04-06 | the Lomakra 2022 study: test items | 7550 | n | table |
| R-llm-04-07 | the Braliram 2021 study: seeds | 1 | n | table |
| R-llm-04-08 | the Braliram 2021 study: test items | 6800 | n | table |
| R-llm-04-09 | the Grovim 2024 study / Steferis extraction: baseline accuracy | 51.1 | % | table |
| R-llm-04-10 | the Grovim 2024 study / Steferis extraction: accuracy with the method | 51.4 | % | table |
| R-llm-04-11 | the Grovim 2024 study / Steferis extraction: accuracy | 0.3 | % | table |
| R-llm-04-12 | the Grovim 2024 study / Steferis extraction: 95% CI lower bound | -0.9 | % | table |
| R-llm-04-13 | the Grovim 2024 study / Steferis extraction: 95% CI upper bound | 1.4 | % | table |
| R-llm-04-14 | the Nodabril 2026 study / Steferis extraction: baseline accuracy | 38.8 | % | table |
| R-llm-04-15 | the Nodabril 2026 study / Steferis extraction: accuracy with the method | 39.2 | % | table |
| R-llm-04-16 | the Nodabril 2026 study / Steferis extraction: accuracy | 0.4 | % | table |
| R-llm-04-17 | the Nodabril 2026 study / Steferis extraction: 95% CI lower bound | -0.1 | % | table |
| R-llm-04-18 | the Nodabril 2026 study / Steferis extraction: 95% CI upper bound | 0.8 | % | table |
| R-llm-04-19 | the Lomakra 2022 study / Steferis extraction: baseline accuracy | 76.4 | % | table |
| R-llm-04-20 | the Lomakra 2022 study / Steferis extraction: accuracy with the method | 84.6 | % | table |
| R-llm-04-21 | the Lomakra 2022 study / Steferis extraction: accuracy | 8.2 | % | table |
| R-llm-04-22 | the Lomakra 2022 study / Steferis extraction: 95% CI lower bound | 7.4 | % | table |
| R-llm-04-23 | the Lomakra 2022 study / Steferis extraction: 95% CI upper bound | 9.0 | % | table |
| R-llm-04-24 | the Grovim 2024 study / Trasor extraction: baseline accuracy | 33.3 | % | table |
| R-llm-04-25 | the Grovim 2024 study / Trasor extraction: accuracy with the method | 33.2 | % | table |
| R-llm-04-26 | the Grovim 2024 study / Trasor extraction: accuracy | -0.1 | % | table |
| R-llm-04-27 | the Grovim 2024 study / Trasor extraction: 95% CI lower bound | -1.1 | % | table |
| R-llm-04-28 | the Grovim 2024 study / Trasor extraction: 95% CI upper bound | 0.8 | % | table |
| R-llm-04-29 | mean gain (inverse-variance) for Steferis extraction (3 studies): estimate | 2.1 | % | table |
| R-llm-04-30 | mean gain (inverse-variance) for Steferis extraction (3 studies): 95% CI lower bound | 1.7 | % | table |
| R-llm-04-31 | mean gain (inverse-variance) for Steferis extraction (3 studies): 95% CI upper bound | 2.4 | % | table |
| R-llm-04-32 | mean gain (inverse-variance) for Steferis extraction (3 studies): heterogeneity I² | 99.3 | % | table |

## 5. Tables to build
* Table 1: Setup of each study (one row per study). Numbers rows ending in: 01, 02, 03, 04, 05, 06, 07, 08.
* Table 2: Effects (accuracy, 95% CI) and pooled values. Numbers rows ending in: 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32.
* Values marked 'state in a sentence' go in the text, not in a table.
* Row ids are for you only: never print a row id in the paper.

## 6. Conflict
* the Grovim 2024 study (reported no gain from) and the Lomakra 2022 study (reported a gain from) disagree about Steferis extraction.

## 7. Plan
* State the question and why the studies disagree or leave it open.
* Describe how the studies were set up (the first table).
* Report the effects and the pooled values (the second table) and say what they show.
* Discuss the disagreements and how far the evidence goes, from the findings.

## 8. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, numbers, dates, designs or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording.
* State each finding at least once and at most 3 times.
* Copy every number exactly as the Numbers table gives it; pooled values are already computed.
