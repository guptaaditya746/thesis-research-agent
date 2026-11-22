# Argument Log

## 1. Setting
* **Genre:** argument paper (a critical survey of language model research).
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Issue:** The reproducibility of zero-shot prompting results in code generation and arithmetic reasoning.
* **Thesis to defend:** Zero-shot prompting methods like Kabaso show significant variability, with some studies failing to replicate earlier gains, suggesting high sensitivity to model size and task complexity.

## 2. Sources
### Method
| Name | Short names | Details |
|---|---|---|
| Kabaso prompting | Kabaso | family: prompting |

### Study
| Name | Short names | Details |
|---|---|---|
| the Brastom 2021 study | Brastom 2021 | year: 2021; model: Nimel-13B; benchmark: the Vofal-Math benchmark; setting: few-shot |
| the Dedrola 2021 study | Dedrola 2021 | year: 2021; model: Nimel-13B; benchmark: the Donar-Code benchmark; setting: few-shot |
| the Grodrokris 2021 study | Grodrokris 2021 | year: 2021; model: Nodrana-70B; benchmark: the Mupadem-QA benchmark; setting: zero-shot |
| the Braliram 2023 study | Braliram 2023 | year: 2023; model: Thipom-7B; benchmark: the Mupadem-QA benchmark; setting: zero-shot |
| the Lomakra 2023 study | Lomakra 2023 | year: 2023; model: Thipom-7B; benchmark: the Vofal-Math benchmark; setting: zero-shot |
| the Netras 2020 study | Netras 2020 | year: 2020; model: Nimel-13B; benchmark: the Donar-Code benchmark; setting: zero-shot |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Dedrola 2021 study | reported a gain from | Kabaso prompting |
| the Lomakra 2023 study | reported no gain from | Kabaso prompting |
| the Dedrola 2021 study | failed to replicate | the Netras 2020 study |
| the Brastom 2021 study | reported a gain from | Kabaso prompting |
| the Braliram 2023 study | reported no gain from | Kabaso prompting |
| the Grodrokris 2021 study | failed to replicate | the Netras 2020 study |

## 5. Argument Plan
* Set out the issue and the relevant sources.
* Analyse the studies in time order and what each did with each source.
* Defend the thesis; then state the strongest counter-argument and answer it from the findings.

## 6. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, dates or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording; never reuse one phrase for several findings and never copy this log's wording.
* State each finding at least once and at most 3 times.
