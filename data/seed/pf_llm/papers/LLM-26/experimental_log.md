# Argument Log

## 1. Setting
* **Genre:** argument paper (a critical survey of language model research).
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Issue:** The inconsistent effectiveness of fine-tuning and retrieval strategies on the Donar-Code benchmark across different model scales and evaluation settings.
* **Thesis to defend:** While Tedroso adapter shows promise in few-shot settings for mid-sized models, Thoradram retrieval fails to provide consistent gains in fine-tuned settings for smaller models, suggesting a trade-off between parameter efficiency and task-specific adaptation.

## 2. Sources
### Method
| Name | Short names | Details |
|---|---|---|
| Tedroso adapter | Tedroso | family: fine-tuning |
| Thoradram retrieval | Thoradram | family: retrieval |

### Study
| Name | Short names | Details |
|---|---|---|
| the Trigras 2024 study | Trigras 2024 | year: 2024; model: Thipom-7B; benchmark: the Mupadem-QA benchmark; setting: fine-tuned |
| the Vitraran 2024 study | Vitraran 2024 | year: 2024; model: Thipom-7B; benchmark: the Donar-Code benchmark; setting: fine-tuned |
| the Bivam 2026 study | Bivam 2026 | year: 2026; model: Nodrana-70B; benchmark: the Vofal-Math benchmark; setting: few-shot |
| the Bifel 2023 study | Bifel 2023 | year: 2023; model: Nimel-13B; benchmark: the Donar-Code benchmark; setting: few-shot |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Trigras 2024 study | reported a gain from | Tedroso adapter |
| the Trigras 2024 study | reported no gain from | Thoradram retrieval |
| the Bifel 2023 study | reported a gain from | Thoradram retrieval |
| the Vitraran 2024 study | reported a gain from | Tedroso adapter |
| the Bifel 2023 study | reported a gain from | Tedroso adapter |
| the Bivam 2026 study | reported no gain from | Thoradram retrieval |

## 5. Argument Plan
* Set out the issue and the relevant sources.
* Analyse the studies in time order and what each did with each source.
* Defend the thesis; then state the strongest counter-argument and answer it from the findings.

## 6. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, dates or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording; never reuse one phrase for several findings and never copy this log's wording.
* State each finding at least once and at most 3 times.
