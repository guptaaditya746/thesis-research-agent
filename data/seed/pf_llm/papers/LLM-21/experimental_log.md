# Argument Log

## 1. Setting
* **Genre:** argument paper (a critical survey of language model research).
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Issue:** The impact of decoding methods on arithmetic reasoning and code generation tasks across different evaluation settings.
* **Thesis to defend:** Decoding methods like Ragrer and Gofabran show inconsistent performance, with Ragrer failing to improve fine-tuned models on arithmetic but Gofabran showing no gain in few-shot code generation.

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
| the Lulos 2024 study | Lulos 2024 | year: 2024; model: Nodrana-70B; benchmark: the Vofal-Math benchmark; setting: few-shot |
| the Mener 2024 study | Mener 2024 | year: 2024; model: Thipom-7B; benchmark: the Vofal-Math benchmark; setting: fine-tuned |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Lulos 2024 study | reported no gain from | Ragrer decoding |
| the Mener 2024 study | reported a drop with | Gofabran decoding |
| the Lulos 2024 study | reported a gain from | Thoradram retrieval |
| the Lulos 2024 study | reported no gain from | Gofabran decoding |
| the Mener 2024 study | reported a drop with | Ragrer decoding |
| the Lulos 2024 study | reported a gain from | Tedroso adapter |

## 5. Argument Plan
* Set out the issue and the relevant sources.
* Analyse the studies in time order and what each did with each source.
* Defend the thesis; then state the strongest counter-argument and answer it from the findings.

## 6. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, dates or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording; never reuse one phrase for several findings and never copy this log's wording.
* State each finding at least once and at most 3 times.
