# Argument Log

## 1. Setting
* **Genre:** argument paper (a critical survey of language model research).
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Issue:** Can the results of the Nozur 2021 study on arithmetic reasoning be replicated, and what is the impact of the Tedroso adapter method?
* **Thesis to defend:** The Nozur 2021 study failed to replicate earlier findings, and the Tedroso adapter method provides a gain in zero-shot arithmetic reasoning.

## 2. Sources
### Method
| Name | Short names | Details |
|---|---|---|
| Kabaso prompting | Kabaso | family: prompting |
| Tedroso adapter | Tedroso | family: fine-tuning |
| Thoradram retrieval | Thoradram | family: retrieval |

### Study
| Name | Short names | Details |
|---|---|---|
| the Nozur 2021 study | Nozur 2021 | year: 2021; model: Nodrana-70B; benchmark: the Vofal-Math benchmark; setting: zero-shot |
| the Gragol 2022 study | Gragol 2022 | year: 2022; model: Nodrana-70B; benchmark: the Vofal-Math benchmark; setting: few-shot |
| the Pegem 2021 study | Pegem 2021 | year: 2021; model: Thipom-7B; benchmark: the Donar-Code benchmark; setting: few-shot |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Nozur 2021 study | reported a gain from | Tedroso adapter |
| the Pegem 2021 study | reported a gain from | Tedroso adapter |
| the Nozur 2021 study | reported no gain from | Thoradram retrieval |
| the Pegem 2021 study | reported a gain from | Kabaso prompting |
| the Nozur 2021 study | reported no gain from | Kabaso prompting |
| the Gragol 2022 study | reported a gain from | Tedroso adapter |

## 5. Argument Plan
* Set out the issue and the relevant sources.
* Analyse the studies in time order and what each did with each source.
* Defend the thesis; then state the strongest counter-argument and answer it from the findings.

## 6. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, dates or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording; never reuse one phrase for several findings and never copy this log's wording.
* State each finding at least once and at most 3 times.
