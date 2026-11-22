# Argument Log

## 1. Setting
* **Genre:** argument paper (a critical survey of language model research).
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Issue:** Disagreement between recent fine-tuned and historical few-shot studies regarding the impact of Ragrer decoding on Thipom-7B.
* **Thesis to defend:** The Dugrudis 2026 study reported a drop with Ragrer decoding, while the Sakem 2020 study reported a gain from Ragrer decoding, creating a direct conflict in the literature.

## 2. Sources
### Method
| Name | Short names | Details |
|---|---|---|
| Kabaso prompting | Kabaso | family: prompting |
| Thetran prompting | Thetran | family: prompting |
| Ragrer decoding | Ragrer | family: decoding |
| Gofabran decoding | Gofabran | family: decoding |

### Study
| Name | Short names | Details |
|---|---|---|
| the Dugrudis 2026 study | Dugrudis 2026 | year: 2026; model: Thipom-7B; benchmark: the Mupadem-QA benchmark; setting: fine-tuned |
| the Sakem 2020 study | Sakem 2020 | year: 2020; model: Thipom-7B; benchmark: the Donar-Code benchmark; setting: few-shot |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Dugrudis 2026 study | reported a drop with | Ragrer decoding |
| the Sakem 2020 study | reported a gain from | Ragrer decoding |
| the Dugrudis 2026 study | reported a gain from | Kabaso prompting |
| the Dugrudis 2026 study | reported a drop with | Gofabran decoding |
| the Sakem 2020 study | reported a gain from | Gofabran decoding |
| the Dugrudis 2026 study | reported a gain from | Thetran prompting |

## 5. Argument Plan
* Set out the issue and the relevant sources.
* Analyse the studies in time order and what each did with each source.
* Defend the thesis; then state the strongest counter-argument and answer it from the findings.

## 6. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, dates or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording; never reuse one phrase for several findings and never copy this log's wording.
* State each finding at least once and at most 3 times.
