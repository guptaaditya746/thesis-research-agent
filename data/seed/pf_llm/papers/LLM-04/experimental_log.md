# Argument Log

## 1. Setting
* **Genre:** argument paper (a critical survey of language model research).
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Issue:** The stability of retrieval and decoding method impacts across different evaluation settings.
* **Thesis to defend:** There is a direct conflict in the literature regarding the impact of retrieval methods, with one study reporting a gain and another reporting no gain for the same method on the same benchmark.

## 2. Sources
### Method
| Name | Short names | Details |
|---|---|---|
| Ragrer decoding | Ragrer | family: decoding |
| Thoradram retrieval | Thoradram | family: retrieval |

### Study
| Name | Short names | Details |
|---|---|---|
| the Tekos 2025 study | Tekos 2025 | year: 2025; model: Thipom-7B; benchmark: the Mupadem-QA benchmark; setting: zero-shot |
| the Rokrar 2025 study | Rokrar 2025 | year: 2025; model: Thipom-7B; benchmark: the Vofal-Math benchmark; setting: zero-shot |
| the Vomobral 2025 study | Vomobral 2025 | year: 2025; model: Thipom-7B; benchmark: the Donar-Code benchmark; setting: zero-shot |
| the Mopel 2025 study | Mopel 2025 | year: 2025; model: Thipom-7B; benchmark: the Mupadem-QA benchmark; setting: few-shot |
| the Grugofel 2025 study | Grugofel 2025 | year: 2025; model: Thipom-7B; benchmark: the Donar-Code benchmark; setting: few-shot |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Tekos 2025 study | reported a gain from | Thoradram retrieval |
| the Grugofel 2025 study | reported no gain from | Thoradram retrieval |
| the Tekos 2025 study | reported a drop with | Ragrer decoding |
| the Vomobral 2025 study | reported a gain from | Thoradram retrieval |
| the Mopel 2025 study | reported no gain from | Thoradram retrieval |
| the Rokrar 2025 study | reported a drop with | Ragrer decoding |

## 5. Argument Plan
* Set out the issue and the relevant sources.
* Analyse the studies in time order and what each did with each source.
* Defend the thesis; then state the strongest counter-argument and answer it from the findings.

## 6. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, dates or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording; never reuse one phrase for several findings and never copy this log's wording.
* State each finding at least once and at most 3 times.
