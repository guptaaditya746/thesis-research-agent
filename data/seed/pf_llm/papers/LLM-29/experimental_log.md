# Argument Log

## 1. Setting
* **Genre:** argument paper (a critical survey of language model research).
* **Setting:** Invented methods for large language models, tested on invented models and invented benchmarks in invented evaluation studies. Tasks, metrics and evaluation settings (zero-shot, few-shot, fine-tuned) are real concepts; model names, method names, benchmark names, authors and results are invented.
* **Issue:** The contradictory findings regarding the effectiveness of prompting and decoding methods in zero-shot multi-hop question answering.
* **Thesis to defend:** There is a direct conflict in the literature regarding the utility of Kabaso prompting and Ragrer decoding in zero-shot QA, with some studies reporting gains and others reporting no gain or drops, highlighting the instability of these methods in this setting.

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
| the Vitraran 2024 study | Vitraran 2024 | year: 2024; model: Thipom-7B; benchmark: the Donar-Code benchmark; setting: fine-tuned |
| the Vives 2024 study | Vives 2024 | year: 2024; model: Nodrana-70B; benchmark: the Mupadem-QA benchmark; setting: zero-shot |

## 3. Findings (data; state each in your own words)
Result meanings: reported a gain from = the study reports that the method raised the model's score on the benchmark over the baseline; reported no gain from = the study reports no clear difference from the baseline score on the benchmark for the method; reported a drop with = the study reports that the method lowered the model's score on the benchmark below the baseline; failed to replicate = the study re-ran an earlier study's setup and did not get its reported result.

| Study | Result | Source |
|---|---|---|
| the Vitraran 2024 study | reported a gain from | Kabaso prompting |
| the Vives 2024 study | reported no gain from | Kabaso prompting |
| the Vives 2024 study | reported a gain from | Ragrer decoding |
| the Vitraran 2024 study | reported a gain from | Thetran prompting |
| the Vives 2024 study | reported no gain from | Thetran prompting |
| the Vives 2024 study | reported a gain from | Gofabran decoding |

## 4. Conflict
* the Vitraran 2024 study (reported a gain from) and the Vives 2024 study (reported no gain from) disagree about Kabaso prompting.

## 5. Argument Plan
* Set out the issue and the relevant sources.
* Analyse the studies in time order and what each did with each source.
* Defend the thesis; then state the strongest counter-argument and answer it from the findings.

## 6. Rules
* Do not invent evaluation studies and the methods and earlier studies they assess, findings, dates or quotations.
* Keep the meaning of every result exact, but phrase it in your own words and vary the wording; never reuse one phrase for several findings and never copy this log's wording.
* State each finding at least once and at most 3 times.
