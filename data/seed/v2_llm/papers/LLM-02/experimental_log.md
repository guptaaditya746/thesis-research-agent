# Experimental Log

## 1. Setting
* **Paper type:** a re-analysis of published evaluation results.
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Question:** Does the Gredapos prompting method consistently improve topic classification performance, or are earlier gains artifacts of small sample sizes?
* **Main conclusion to support:** The initial reported gain from Gredapos prompting in the Netras 2021 study is not robust; a full-scale re-evaluation in the Brastom 2023 study shows no significant improvement, suggesting the method's effectiveness is context-dependent or negligible.

## 2. Sources
### Method
| Name | Short names | Details |
|---|---|---|
| Gredapos prompting | Gredapos | family: prompting; summary: instructs the model to identify the main themes in a document and assign a probability score to each theme before generating the final topic list |
| Bruke retrieval | Bruke | family: retrieval; summary: retrieves similar documents from a corpus to provide context for the model to infer the underlying topics of the target text |
| Brulum decoding | Brulum | family: decoding; summary: uses a constrained decoding strategy that forces the model to output only words from a predefined vocabulary of topic labels |

### Study
| Name | Short names | Details |
|---|---|---|
| the Netras 2021 study | Netras 2021 | year: 2021; model: Dogres-7B; benchmark: the Tilutron-Topic benchmark; setting: zero-shot; summary: evaluates the effectiveness of theme probability scoring on a small subset of the topic classification benchmark |
| the Brastom 2023 study | Brastom 2023 | year: 2023; model: Dogres-7B; benchmark: the Tilutron-Topic benchmark; setting: zero-shot; summary: re-evaluates the theme probability scoring method on the full test set, finding no significant improvement over the baseline |
| the Nozur 2026 study | Nozur 2026 | year: 2026; model: Sakem-13B; benchmark: the Vokosti-Theme benchmark; setting: zero-shot; summary: attempts to replicate the findings of the 2022 study on retrieval-augmented theme extraction but fails to observe the same performance gains |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Netras 2021 study | reported a gain from | Gredapos prompting |
| the Brastom 2023 study | reported no gain from | Gredapos prompting |
| the Brastom 2023 study | failed to replicate | the Netras 2021 study |
| the Netras 2021 study | reported a gain from | Bruke retrieval |
| the Brastom 2023 study | reported no gain from | Brulum decoding |
| the Nozur 2026 study | reported no gain from | Gredapos prompting |

## 4. Numbers (data; every value exactly as written, in its placement)
| Row id | Item | Value | Unit | Placement |
|---|---|---|---|---|
| R-llm-02-01 | the Netras 2021 study: seeds | 1 | n | table |
| R-llm-02-02 | the Netras 2021 study: test items | 1550 | n | table |
| R-llm-02-03 | the Brastom 2023 study: seeds | 5 | n | table |
| R-llm-02-04 | the Brastom 2023 study: test items | 4000 | n | table |
| R-llm-02-05 | the Nozur 2026 study: seeds | 3 | n | table |
| R-llm-02-06 | the Nozur 2026 study: test items | 1150 | n | table |
| R-llm-02-07 | the Netras 2021 study / Gredapos prompting: baseline accuracy | 62.7 | % | table |
| R-llm-02-08 | the Netras 2021 study / Gredapos prompting: accuracy with the method | 67.6 | % | table |
| R-llm-02-09 | the Netras 2021 study / Gredapos prompting: accuracy | 4.9 | % | table |
| R-llm-02-10 | the Netras 2021 study / Gredapos prompting: 95% CI lower bound | 4.2 | % | table |
| R-llm-02-11 | the Netras 2021 study / Gredapos prompting: 95% CI upper bound | 5.6 | % | table |
| R-llm-02-12 | the Brastom 2023 study / Gredapos prompting: baseline accuracy | 37.3 | % | table |
| R-llm-02-13 | the Brastom 2023 study / Gredapos prompting: accuracy with the method | 36.8 | % | table |
| R-llm-02-14 | the Brastom 2023 study / Gredapos prompting: accuracy | -0.5 | % | table |
| R-llm-02-15 | the Brastom 2023 study / Gredapos prompting: 95% CI lower bound | -1.2 | % | table |
| R-llm-02-16 | the Brastom 2023 study / Gredapos prompting: 95% CI upper bound | 0.2 | % | table |
| R-llm-02-17 | the Netras 2021 study / Bruke retrieval: baseline accuracy | 55.0 | % | table |
| R-llm-02-18 | the Netras 2021 study / Bruke retrieval: accuracy with the method | 62.6 | % | table |
| R-llm-02-19 | the Netras 2021 study / Bruke retrieval: accuracy | 7.6 | % | table |
| R-llm-02-20 | the Netras 2021 study / Bruke retrieval: 95% CI lower bound | 6.7 | % | table |
| R-llm-02-21 | the Netras 2021 study / Bruke retrieval: 95% CI upper bound | 8.6 | % | table |
| R-llm-02-22 | the Brastom 2023 study / Brulum decoding: baseline accuracy | 71.4 | % | table |
| R-llm-02-23 | the Brastom 2023 study / Brulum decoding: accuracy with the method | 71.3 | % | table |
| R-llm-02-24 | the Brastom 2023 study / Brulum decoding: accuracy | -0.1 | % | table |
| R-llm-02-25 | the Brastom 2023 study / Brulum decoding: 95% CI lower bound | -1.2 | % | table |
| R-llm-02-26 | the Brastom 2023 study / Brulum decoding: 95% CI upper bound | 1.1 | % | table |
| R-llm-02-27 | the Nozur 2026 study / Gredapos prompting: baseline accuracy | 48.8 | % | table |
| R-llm-02-28 | the Nozur 2026 study / Gredapos prompting: accuracy with the method | 48.7 | % | table |
| R-llm-02-29 | the Nozur 2026 study / Gredapos prompting: accuracy | -0.1 | % | table |
| R-llm-02-30 | the Nozur 2026 study / Gredapos prompting: 95% CI lower bound | -1.3 | % | table |
| R-llm-02-31 | the Nozur 2026 study / Gredapos prompting: 95% CI upper bound | 1.0 | % | table |
| R-llm-02-32 | mean gain (inverse-variance) for Gredapos prompting (3 studies): estimate | 1.8 | % | table |
| R-llm-02-33 | mean gain (inverse-variance) for Gredapos prompting (3 studies): 95% CI lower bound | 1.4 | % | table |
| R-llm-02-34 | mean gain (inverse-variance) for Gredapos prompting (3 studies): 95% CI upper bound | 2.3 | % | table |
| R-llm-02-35 | mean gain (inverse-variance) for Gredapos prompting (3 studies): heterogeneity I² | 98.4 | % | table |

## 5. Tables to build
* Table 1: Setup of each study (one row per study). Numbers rows ending in: 01, 02, 03, 04, 05, 06.
* Table 2: Effects (accuracy, 95% CI) and pooled values. Numbers rows ending in: 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35.
* Values marked 'state in a sentence' go in the text, not in a table.
* Row ids are for you only: never print a row id in the paper.

## 6. Plan
* State the question and why the studies disagree or leave it open.
* Describe how the studies were set up (the first table).
* Report the effects and the pooled values (the second table) and say what they show.
* Discuss the disagreements and how far the evidence goes, from the findings.

## 7. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, numbers, dates, designs or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording.
* State each finding at least once and at most 3 times.
* Copy every number exactly as the Numbers table gives it; pooled values are already computed.
