# Argument Log

## 1. Setting
* **Genre:** argument paper (a critical survey of language model research).
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Issue:** Does the Thoradram retrieval method consistently improve performance on the Donar-Code benchmark in few-shot settings, and how does it compare to other methods?
* **Thesis to defend:** The Thoradram retrieval method yields significant gains in few-shot code generation, while the Tedroso adapter method shows no clear benefit in the same setting.

## 2. Sources
### Method
| Name | Short names | Details |
|---|---|---|
| Kabaso prompting | Kabaso | family: prompting |
| Ragrer decoding | Ragrer | family: decoding |
| Tedroso adapter | Tedroso | family: fine-tuning |
| Thoradram retrieval | Thoradram | family: retrieval |
| Gofabran decoding | Gofabran | family: decoding |

### Study
| Name | Short names | Details |
|---|---|---|
| the Nodabril 2023 study | Nodabril 2023 | year: 2023; model: Nimel-13B; benchmark: the Donar-Code benchmark; setting: few-shot |
| the Brustekru 2022 study | Brustekru 2022 | year: 2022; model: Nimel-13B; benchmark: the Mupadem-QA benchmark; setting: zero-shot |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Nodabril 2023 study | reported a gain from | Thoradram retrieval |
| the Nodabril 2023 study | reported no gain from | Tedroso adapter |
| the Brustekru 2022 study | reported a gain from | Thoradram retrieval |
| the Nodabril 2023 study | reported a gain from | Kabaso prompting |
| the Brustekru 2022 study | reported a gain from | Ragrer decoding |
| the Nodabril 2023 study | reported no gain from | Gofabran decoding |

## 5. Argument Plan
* Set out the issue and the relevant sources.
* Analyse the studies in time order and what each did with each source.
* Defend the thesis; then state the strongest counter-argument and answer it from the findings.

## 6. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, dates or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording; never reuse one phrase for several findings and never copy this log's wording.
* State each finding at least once and at most 3 times.
