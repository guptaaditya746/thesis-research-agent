# Argument Log

## 1. Setting
* **Genre:** argument paper (a critical survey of language model research).
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Issue:** Whether fine-tuning or few-shot prompting is more effective for retrieval-based methods.
* **Thesis to defend:** Thoradram retrieval yields gains in few-shot QA but fails to improve fine-tuned arithmetic performance.

## 2. Sources
### Method
| Name | Short names | Details |
|---|---|---|
| Kabaso prompting | Kabaso | family: prompting |
| Thoradram retrieval | Thoradram | family: retrieval |

### Study
| Name | Short names | Details |
|---|---|---|
| the Togobe 2022 study | Togobe 2022 | year: 2022; model: Thipom-7B; benchmark: the Vofal-Math benchmark; setting: fine-tuned |
| the Braliram 2023 study | Braliram 2023 | year: 2023; model: Thipom-7B; benchmark: the Mupadem-QA benchmark; setting: zero-shot |
| the Vomobral 2025 study | Vomobral 2025 | year: 2025; model: Thipom-7B; benchmark: the Donar-Code benchmark; setting: zero-shot |
| the Rothihen 2023 study | Rothihen 2023 | year: 2023; model: Nimel-13B; benchmark: the Mupadem-QA benchmark; setting: few-shot |
| the Mopel 2025 study | Mopel 2025 | year: 2025; model: Thipom-7B; benchmark: the Mupadem-QA benchmark; setting: few-shot |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Togobe 2022 study | reported no gain from | Thoradram retrieval |
| the Rothihen 2023 study | reported a gain from | Thoradram retrieval |
| the Rothihen 2023 study | reported no gain from | Kabaso prompting |
| the Braliram 2023 study | reported no gain from | Kabaso prompting |
| the Mopel 2025 study | reported no gain from | Thoradram retrieval |
| the Vomobral 2025 study | reported a gain from | Thoradram retrieval |

## 5. Argument Plan
* Set out the issue and the relevant sources.
* Analyse the studies in time order and what each did with each source.
* Defend the thesis; then state the strongest counter-argument and answer it from the findings.

## 6. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, dates or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording; never reuse one phrase for several findings and never copy this log's wording.
* State each finding at least once and at most 3 times.
