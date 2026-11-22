# Argument Log

## 1. Setting
* **Genre:** argument paper (a critical survey of language model research).
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Issue:** The impact of decoding methods on large models in zero-shot settings for arithmetic and code tasks.
* **Thesis to defend:** Ragrer decoding provides a significant boost in zero-shot arithmetic reasoning for large models, whereas Gofabran decoding yields negligible results in zero-shot code generation, indicating task-specific sensitivity to decoding strategies.

## 2. Sources
### Method
| Name | Short names | Details |
|---|---|---|
| Ragrer decoding | Ragrer | family: decoding |
| Gofabran decoding | Gofabran | family: decoding |

### Study
| Name | Short names | Details |
|---|---|---|
| the Trasor 2021 study | Trasor 2021 | year: 2021; model: Nodrana-70B; benchmark: the Donar-Code benchmark; setting: zero-shot |
| the Sevos 2025 study | Sevos 2025 | year: 2025; model: Nodrana-70B; benchmark: the Vofal-Math benchmark; setting: zero-shot |
| the Totin 2025 study | Totin 2025 | year: 2025; model: Nodrana-70B; benchmark: the Donar-Code benchmark; setting: zero-shot |
| the Robidrum 2021 study | Robidrum 2021 | year: 2021; model: Nodrana-70B; benchmark: the Vofal-Math benchmark; setting: few-shot |
| the Netras 2020 study | Netras 2020 | year: 2020; model: Nimel-13B; benchmark: the Donar-Code benchmark; setting: zero-shot |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Trasor 2021 study | reported a gain from | Ragrer decoding |
| the Trasor 2021 study | reported no gain from | Gofabran decoding |
| the Sevos 2025 study | reported no gain from | Ragrer decoding |
| the Totin 2025 study | reported no gain from | Ragrer decoding |
| the Netras 2020 study | reported a gain from | Ragrer decoding |
| the Robidrum 2021 study | reported no gain from | Ragrer decoding |

## 5. Argument Plan
* Set out the issue and the relevant sources.
* Analyse the studies in time order and what each did with each source.
* Defend the thesis; then state the strongest counter-argument and answer it from the findings.

## 6. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, dates or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording; never reuse one phrase for several findings and never copy this log's wording.
* State each finding at least once and at most 3 times.
