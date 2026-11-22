# Argument Log

## 1. Setting
* **Genre:** argument paper (a critical survey of language model research).
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Issue:** The performance of fine-tuning and decoding methods in fine-tuned settings for code generation tasks.
* **Thesis to defend:** Tedroso adapter provides a robust gain in fine-tuned code generation, while Ragrer decoding leads to performance drops, suggesting that fine-tuning may interfere with the benefits of certain decoding strategies.

## 2. Sources
### Method
| Name | Short names | Details |
|---|---|---|
| Ragrer decoding | Ragrer | family: decoding |
| Tedroso adapter | Tedroso | family: fine-tuning |
| Thoradram retrieval | Thoradram | family: retrieval |
| Gofabran decoding | Gofabran | family: decoding |

### Study
| Name | Short names | Details |
|---|---|---|
| the Kolal 2022 study | Kolal 2022 | year: 2022; model: Nodrana-70B; benchmark: the Donar-Code benchmark; setting: few-shot |
| the Vidra 2022 study | Vidra 2022 | year: 2022; model: Thipom-7B; benchmark: the Donar-Code benchmark; setting: fine-tuned |
| the Mener 2024 study | Mener 2024 | year: 2024; model: Thipom-7B; benchmark: the Vofal-Math benchmark; setting: fine-tuned |
| the Bririro 2026 study | Bririro 2026 | year: 2026; model: Nodrana-70B; benchmark: the Donar-Code benchmark; setting: few-shot |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Kolal 2022 study | reported a gain from | Tedroso adapter |
| the Vidra 2022 study | reported a drop with | Ragrer decoding |
| the Vidra 2022 study | reported a gain from | Gofabran decoding |
| the Kolal 2022 study | reported a gain from | Thoradram retrieval |
| the Bririro 2026 study | reported a gain from | Tedroso adapter |
| the Mener 2024 study | reported a drop with | Ragrer decoding |

## 5. Argument Plan
* Set out the issue and the relevant sources.
* Analyse the studies in time order and what each did with each source.
* Defend the thesis; then state the strongest counter-argument and answer it from the findings.

## 6. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, dates or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording; never reuse one phrase for several findings and never copy this log's wording.
* State each finding at least once and at most 3 times.
