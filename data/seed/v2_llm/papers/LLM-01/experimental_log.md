# Experimental Log

## 1. Setting
* **Paper type:** an empirical comparison of reported results.
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Question:** The reliability of part-of-speech prompting in low-resource translation and the consistency of zero-shot tagging performance across different model architectures.
* **Main conclusion to support:** While the Vofal 2024 study demonstrates that the Thoradram-13B model achieves a gain in part-of-speech tagging accuracy using the Kabaso prompting method, the Donar 2025 study fails to replicate the earlier positive findings of the Nodrana 2022 study regarding the same method's impact on translation quality.

## 2. Sources
### Method
| Name | Short names | Details |
|---|---|---|
| Kabaso prompting | Kabaso | family: prompting; summary: instructs the model to output the part-of-speech tag for each token in a sentence before generating the translation |
| Thetran decoding | Thetran | family: decoding; summary: uses a constrained beam search that enforces valid dependency structures during the generation of the target language sentence |
| Ragrer adapter | Ragrer | family: fine-tuning; summary: inserts small trainable layers into the encoder to capture morphological features of low-resource languages without updating the main weights |

### Study
| Name | Short names | Details |
|---|---|---|
| the Nimel 2021 study | Nimel 2021 | year: 2021; model: Tedroso-7B; benchmark: the Gofabran-MT benchmark; setting: zero-shot; summary: evaluates the baseline translation performance of the 7B encoder-decoder model on low-resource pairs without any auxiliary methods |
| the Nodrana 2022 study | Nodrana 2022 | year: 2022; model: Tedroso-7B; benchmark: the Gofabran-MT benchmark; setting: few-shot, 5 examples; summary: tests whether prompting the model to output part-of-speech tags before translation improves BLEU scores on the low-resource benchmark |
| the Vofal 2024 study | Vofal 2024 | year: 2024; model: Thoradram-13B; benchmark: the Thipom-POS benchmark; setting: zero-shot; summary: assesses the accuracy of the 13B model in assigning part-of-speech tags to morphologically rich languages without any specific prompting strategy |
| the Donar 2025 study | Donar 2025 | year: 2025; model: Tedroso-7B; benchmark: the Gofabran-MT benchmark; setting: few-shot, 5 examples; summary: re-runs the setup from the 2022 study to check if the part-of-speech prompting method still yields a gain on the same model and benchmark |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Vofal 2024 study | reported a gain from | Kabaso prompting |
| the Donar 2025 study | failed to replicate | the Nodrana 2022 study |
| the Donar 2025 study | reported no gain from | Kabaso prompting |
| the Vofal 2024 study | reported a gain from | Thetran decoding |
| the Donar 2025 study | failed to replicate | the Nimel 2021 study |
| the Donar 2025 study | reported no gain from | Ragrer adapter |

## 4. Numbers (data; every value exactly as written, in its placement)
| Row id | Item | Value | Unit | Placement |
|---|---|---|---|---|
| R-llm-01-01 | the Vofal 2024 study: seeds | 5 | n | table |
| R-llm-01-02 | the Vofal 2024 study: test items | 3250 | n | table |
| R-llm-01-03 | the Donar 2025 study: seeds | 3 | n | table |
| R-llm-01-04 | the Donar 2025 study: test items | 7750 | n | table |
| R-llm-01-05 | the Nodrana 2022 study: seeds | 5 | n | table |
| R-llm-01-06 | the Nodrana 2022 study: test items | 3100 | n | table |
| R-llm-01-07 | the Nimel 2021 study: seeds | 3 | n | table |
| R-llm-01-08 | the Nimel 2021 study: test items | 8550 | n | table |
| R-llm-01-09 | the Vofal 2024 study / Kabaso prompting: baseline accuracy | 62.1 | % | table |
| R-llm-01-10 | the Vofal 2024 study / Kabaso prompting: accuracy with the method | 67.1 | % | table |
| R-llm-01-11 | the Vofal 2024 study / Kabaso prompting: accuracy | 5.0 | % | table |
| R-llm-01-12 | the Vofal 2024 study / Kabaso prompting: 95% CI lower bound | 4.1 | % | table |
| R-llm-01-13 | the Vofal 2024 study / Kabaso prompting: 95% CI upper bound | 6.0 | % | table |
| R-llm-01-14 | the Donar 2025 study / Kabaso prompting: baseline accuracy | 53.6 | % | table |
| R-llm-01-15 | the Donar 2025 study / Kabaso prompting: accuracy with the method | 53.8 | % | table |
| R-llm-01-16 | the Donar 2025 study / Kabaso prompting: accuracy | 0.2 | % | table |
| R-llm-01-17 | the Donar 2025 study / Kabaso prompting: 95% CI lower bound | -0.8 | % | table |
| R-llm-01-18 | the Donar 2025 study / Kabaso prompting: 95% CI upper bound | 1.2 | % | table |
| R-llm-01-19 | the Vofal 2024 study / Thetran decoding: baseline accuracy | 43.0 | % | table |
| R-llm-01-20 | the Vofal 2024 study / Thetran decoding: accuracy with the method | 47.1 | % | table |
| R-llm-01-21 | the Vofal 2024 study / Thetran decoding: accuracy | 4.1 | % | table |
| R-llm-01-22 | the Vofal 2024 study / Thetran decoding: 95% CI lower bound | 3.1 | % | table |
| R-llm-01-23 | the Vofal 2024 study / Thetran decoding: 95% CI upper bound | 5.2 | % | table |
| R-llm-01-24 | the Donar 2025 study / Ragrer adapter: baseline accuracy | 81.4 | % | table |
| R-llm-01-25 | the Donar 2025 study / Ragrer adapter: accuracy with the method | 80.8 | % | table |
| R-llm-01-26 | the Donar 2025 study / Ragrer adapter: accuracy | -0.6 | % | table |
| R-llm-01-27 | the Donar 2025 study / Ragrer adapter: 95% CI lower bound | -1.8 | % | table |
| R-llm-01-28 | the Donar 2025 study / Ragrer adapter: 95% CI upper bound | 0.7 | % | table |
| R-llm-01-29 | mean gain (inverse-variance) for Kabaso prompting (2 studies): estimate | 2.7 | % | table |
| R-llm-01-30 | mean gain (inverse-variance) for Kabaso prompting (2 studies): 95% CI lower bound | 2.0 | % | table |
| R-llm-01-31 | mean gain (inverse-variance) for Kabaso prompting (2 studies): 95% CI upper bound | 3.4 | % | table |
| R-llm-01-32 | mean gain (inverse-variance) for Kabaso prompting (2 studies): heterogeneity I² | 97.9 | % | table |

## 5. Tables to build
* Table 1: Setup of each study (one row per study). Numbers rows ending in: 01, 02, 03, 04, 05, 06, 07, 08.
* Table 2: Effects (accuracy, 95% CI) and pooled values. Numbers rows ending in: 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32.
* Values marked 'state in a sentence' go in the text, not in a table.
* Row ids are for you only: never print a row id in the paper.

## 6. Conflict
* the Vofal 2024 study (reported a gain from) and the Donar 2025 study (reported no gain from) disagree about Kabaso prompting.

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
