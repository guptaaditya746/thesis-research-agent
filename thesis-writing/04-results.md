# 4 Experimental Results

## 4.1 Scope and evidence basis

This chapter reports completed measurements in `/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis-campaign-20261106T132128Z`, abbreviated **C**. Source references below are relative to C unless explicitly identified as repository code. The chapter separates synthetic fixed-protocol execution, real-data plan execution and operational artifact availability. Scores from these settings have different units and are not combined into one overall accuracy.

A read-only audit recomputed reported means from study/question rows in thirteen synthetic score reports and the two corrected real-data score reports. It also checked paper hashes for the four evaluated corpora and primary output digests for sixteen sealed real condition-runs. The latter comprise seven SciLead plans and one SciREX plan in each of two reasoning settings. Completion means that expected artifacts exist, their primary digests match, the seal is complete and recorded calls have successful status. It does not mean that the answer is correct. The audit and source digests are in `thesis-writing/audit-evidence.py` and `verified-evidence.json`.

Several campaign narrative files contain earlier statements that real execution had not occurred. Those statements are superseded by the completed `real-v1` run and score files. An additional reporting discrepancy concerns SciREX: the existing narrative and CSV call its headline recall, whereas `evaluation/wholerun_cmd.py` selects list F1. The stored numerical values agree with F1, and this chapter uses that definition. Original experimental artifacts have not been edited.

## 4.2 Dataset characteristics and evaluation coverage

Table 4.1 describes the completed evaluation scope. A synthetic study decision is not a separate natural-language research question. The mixed corpora each ask the same factuality question over twenty study records, whereas the real samples contain ten distinct question IDs per dataset.

| Dataset/configuration | Local papers | Fixed question sample | Completed engine cases per condition | Baseline coverage |
|---|---:|---|---:|---|
| Claude-rendered mixed synthetic | 20 | One factuality question, 20 study directions | 20 study decisions; three fresh-call engine runs | Global and per-paper, three recorded runs each |
| Template-rendered mixed synthetic | 20 | Same question and latent studies | 20 study decisions; three fresh-call engine runs | Global and per-paper, two recorded runs each |
| SciLead corrected sample | 31 | Ten seed-0 ranking questions | Seven; three blocked before execution | Ten questions per mode |
| SciREX sample | 40 | Ten seed-0 list questions | One; nine blocked before execution | Ten questions per mode, one undefined F1 case each |

Sources: corpus manifests, `run-manifest.json`, `scores/sample-10-corrected`, `plans/*-validation.json` and `real-v1/scores/*-v2/wholerun.json` (inventory E02, E13–E16).

The two synthetic corpora share their latent `studies` and aggregate `answer` content. Their different rendering is therefore a controlled wording condition, not an independent draw of scientific findings. Both contain four studies at each of five levels: explicit, paraphrased, distributed, complex and contradictory. No current-campaign full-set CochraneForest, SOFC-Exp or MeasEval comparison was established. The presence of dataset adapters or raw source files does not fill this coverage gap.

The initial SciLead sample was excluded after three tuning-question IDs were found. The reported sample is the approved corrected list; every system uses those same ten IDs. Historical 22-question SciLead rescoring is not pooled with this sample because its selection and contamination concerns differ.

## 4.3 Synthetic end-to-end evidence performance

### 4.3.1 Study-direction accuracy and aggregate answers

Table 4.2 presents first-run comparisons. Intervals are the recorded 95% bootstrap intervals over the same twenty study rows. The headline here is determined-study direction accuracy, rather than corpus-label accuracy or extraction F1.

| Rendering | Evidence engine | Global BM25 RAG | Per-paper BM25 RAG | Engine − global | Engine − per-paper |
|---|---|---|---|---|---|
| Claude mixed, first run | 0.900 [0.700, 1.000] | 0.200 [0.050, 0.450] | 0.800 [0.550, 0.950] | +0.700 [0.450, 0.850] | +0.100 [−0.050, 0.300] |
| Template mixed, first run | 0.800 [0.600, 0.950] | 0.200 [0.050, 0.400] | 0.750 [0.500, 0.900] | +0.600 [0.350, 0.800] | +0.050 [−0.200, 0.300] |

Sources: `scores/campaign-cascade-gaps/claude-s1-mixed-rep1/report.json`, `scores/paired-per-paper-rep1/report.json`, and `template/scores/{global,per-paper}/report.json` (E12–E14).

The evidence engine recovered eighteen correct directions on the Claude corpus and sixteen on the template corpus. The global baseline recovered four in each condition. Per-paper retrieval recovered sixteen and fifteen, respectively. The evidence engine therefore had a large observed advantage over the global retrieval configuration on this task. Its much smaller advantage over per-paper retrieval had an interval spanning zero in both conditions. This evidence does not establish a general advantage over RAG, particularly when document coverage is expanded.

All three systems returned the correct aggregate label, “mixed,” in both first-run comparisons. This single aggregate agreement concealed substantial differences in study coverage. On Claude, engine completeness was 0.900, global completeness 0.250 and per-paper completeness 1.000. On template text, the corresponding values were 0.800, 0.200 and 0.900. Global answers could therefore identify the overall mixture without providing correct directions for most studies. Aggregate label correctness alone would have obscured the principal difference between systems.

### 4.3.2 Extraction and integration

| Rendering/run | Matched items | Extracted items | Gold facts | Precision | Recall | Micro F1 | Span accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|
| Claude engine run 1 | 153 | 157 | 210 | 0.9745 | 0.7286 | 0.8338 | 0.9804 |
| Claude engine run 2 | 157 | 161 | 210 | 0.9752 | 0.7476 | 0.8464 | 0.9809 |
| Claude engine run 3 | 158 | 161 | 210 | 0.9814 | 0.7524 | 0.8518 | 0.9810 |
| Template engine run 1 | 135 | 137 | 210 | 0.9854 | 0.6429 | 0.7781 | 1.0000 |

Sources: `extraction.rows`, row `level=all, evidence_type=all`, in the corresponding score reports. Claude runs 2 and 3 are under `per-paper/scores/campaign-cascade-gaps/claude-s1-mixed-rep2` and `rep3/scores/campaign-cascade-gaps/claude-s1-mixed-rep3`.

Precision exceeded recall in these runs. In the first Claude run, fifty-seven gold facts were unmatched and four extracted items were unmatched. These counts indicate incomplete extraction despite high precision. Span accuracy is conditional on the relevant matching procedure; it does not establish that all required evidence was found or attached correctly.

The first Claude integration report recorded correct condition/metric associations for all sixty-five matched measurements, while its true-pair rate was 0.700 over twenty studies. The template first run likewise recorded correct associations for fifty-four matched measurements but a true-pair rate of 0.600. These results show why conditional link accuracy, pair selection and final study correctness must remain separate. A high score among matched values can coexist with missing measurements and incomplete study outcomes.

## 4.4 Real-data end-to-end performance and RAG comparison

### 4.4.1 Full-sample headline and conditional diagnostic

The real headline retains every sampled question. Blocked engine cases receive zero utility under the documented protocol without being represented as generated answers. Undefined baseline F1 is recorded and zeroed in aggregation. Table 4.4 reports the two task-specific metrics separately.

| Dataset and metric | Engine on | Engine off | Global RAG | Per-paper RAG | Conditional engine diagnostic |
|---|---:|---:|---|---|---|
| SciLead: mean top-1 correctness, n=10 | 0.000 | 0.000 | 0.600 [0.300, 0.900] | 0.200 [0.000, 0.600] | 0/7 correct, both settings |
| SciREX: mean list F1, n=10 | 0.000 | 0.000 | 0.050 [0.000, 0.200] | 0.078571 [0.000, 0.230479] | Mean F1 0.000 over one executed plan, both settings |

Sources: `real-v1/scores/{scilead,scirex}-v2/{wholerun.json,conditional-diagnostic.json}` (E16–E17). Engine bootstrap bounds are null because the observed score rows are constant; this is not a proof of zero population performance.

The real results contradict an unrestricted superiority claim for the implemented engine. On SciLead, global RAG identified the top-ranked paper on six questions and per-paper RAG on two. None of the seven executed engine plans selected the correct top-ranked paper. Consequently, removing blocked cases would not improve the engine's observed diagnostic score. SciREX is more weakly covered: only `scirex-008` executed, and it received zero F1. The full-sample engine score reflects both planning coverage and answer failure and should not be interpreted as an isolated estimate of query-execution quality.

Paired differences for SciLead engine-on were −0.600 [−0.900, −0.300] against global and −0.200 [−0.600, 0.000] against per-paper, with zero wins, six losses and four ties against global. SciREX paired differences were −0.050 [−0.200, 0.000] and −0.078571 [−0.230479, 0.000]. These pairings use identical IDs within each dataset, not the smaller successful-plan subset. They describe this implementation and sample, including its validation failures.

### 4.4.2 Question-level outcomes

In Tables 4.5–4.6, B denotes a blocked engine case with headline utility zero. Engine on/off results are identical. A dash marked U denotes an undefined baseline F1 that the scorer converted to zero in the ten-question mean; it is not silently omitted.

| SciLead question | Engine on/off top-1 | Global top-1 | Per-paper top-1 |
|---|---:|---:|---:|
| scilead-03 | 0 | 0 | 0 |
| scilead-06 | B | 0 | 0 |
| scilead-11 | 0 | 0 | 0 |
| scilead-17 | 0 | 1 | 1 |
| scilead-18 | B | 1 | 1 |
| scilead-19 | 0 | 1 | 0 |
| scilead-20 | 0 | 1 | 0 |
| scilead-21 | 0 | 1 | 0 |
| scilead-22 | 0 | 0 | 0 |
| scilead-27 | B | 1 | 0 |

| SciREX question | Engine on/off F1 | Global F1 | Per-paper F1 |
|---|---:|---:|---:|
| scirex-001 | B | 0 | 0 |
| scirex-004 | B | 0 | 0 |
| scirex-005 | B | 0 | 0 |
| scirex-006 | B | 0.500000 | 0.500000 |
| scirex-008 | 0 | 0 | 0 |
| scirex-010 | B | 0 | 0 |
| scirex-011 | B | 0 | 0 |
| scirex-017 | B | 0 | 0.285714 |
| scirex-018 | B | 0 | 0 |
| scirex-019 | B | U → 0 | U → 0 |

Sources: `rows` in the two real `wholerun.json` files and `real-v1/scores/question-level.csv`. The nonzero per-paper score on `scirex-017` is F1 2/7: precision is 1/4 and recall is 1/3. This directly demonstrates the metric-label error in the earlier report. The zero score for an empty output on `scirex-019` reflects an undefined F1 convention because predicted precision has no denominator; it is not evidence that the question lacks gold answers.

## 4.5 Planning success and failure

| Dataset | Valid plans | Missing required metric | Missing query | Generation/parse failure | Blocked total |
|---|---:|---:|---:|---:|---:|
| SciLead, n=10 | 7 | 1 | 1 | 1 | 3 |
| SciREX, n=10 | 1 | 0 | 8 | 1 | 9 |

Sources: `plans/{scilead,scirex}-validation.json` and associated planner logs (E18). Counts refer to affected questions, not individual error messages: `scilead-06` has two lines missing a required measure but contributes one failed plan.

SciLead plan validation succeeded for `03, 11, 17, 19, 20, 21, 22`. Question `06` named no measure despite queries requiring `$metric`; question `18` had no query for line l2; question `27` failed structured response parsing before a plan was saved. On SciREX, `001, 004, 005, 010, 011, 017, 018, 019` lacked a query on l1, while `006` failed generation parsing. Only `008` passed.

Historical SciREX plans had used unsupported `kg:dataset`, whereas the graph represents dataset settings through other properties. This historical finding must not be substituted for a diagnosis of every fresh no-query failure. The retained fresh artifacts establish that a query was absent, but do not prove why the planner failed to produce it. No rejected plan was manually repaired or approved as a human-reviewed plan.

## 4.6 Generalization, ablations and repeated-run variability

### 4.6.1 Variation by synthetic evidence arrangement

| Mixed-corpus subset, four studies each | Claude engine run 1 | Claude global RAG | Template engine run 1 | Template global RAG |
|---|---:|---:|---:|---:|
| Explicit | 1.000 | 0.250 | 1.000 | 0.250 |
| Paraphrased | 0.500 | 0.000 | 0.000 | 0.000 |
| Distributed | 1.000 | 0.250 | 1.000 | 0.000 |
| Complex | 1.000 | 0.500 | 1.000 | 0.250 |
| Contradictory | 1.000 | 0.000 | 1.000 | 0.500 |

Sources: per-level synthesis rows in the first Claude and template global score reports (E21). These are twenty study decisions partitioned by text arrangement. They are not a comprehensive comparison of inventory, aggregation, ranking and contradiction questions.

Paraphrased cases account for the engine's missing directions in these first runs. The result indicates sensitivity to how evidence is expressed, even with identical latent studies. It cannot identify a universal ranking of evidence difficulty from four cases per level. No completed current-campaign leak-split or validated fresh off-template benchmark was established, so unseen terminology recall and off-template match rate are not reported as new measured achievements.

### 4.6.2 Repetition and ablation coverage

| Configuration | Recorded score sequence | Interpretation |
|---|---|---|
| Claude engine | 0.90, 0.95, 0.95 | Three runs with new model calls; identical corpus/question |
| Claude global RAG | 0.20, 0.20, 0.20 | Three recorded baseline executions |
| Claude per-paper RAG | 0.80, 0.80, 0.80 | Three recorded baseline executions |
| Template engine | 0.80, 0.80, 0.80 | Three runs with new model calls |
| Template global RAG | 0.20, 0.20 | Two executions; third engine comparison reuses first answer |
| Template per-paper RAG | 0.75, 0.75 | Two executions; third engine comparison reuses first answer |

Sources: the reports enumerated in `verified-evidence.json` and execution records in `run-manifest.json`. Identical scores do not demonstrate byte-identical outputs. The Claude engine's higher later scores reflect improved paraphrased completeness, while extraction F1 also varies. These repetitions assess serving/pipeline variability under fixed data and settings, not replication across independent datasets.

Both real reasoning conditions produced the same headline scores. However, the generality report classifies all seven scored SciLead main queries and the single scored SciREX main query as saved-template queries. The off runs also made no new model calls. These rows therefore do not establish the value or absence of ontology-dependent fresh querying, nor are they independent repeated model experiments. Human-confirmation and matched component-removal ablations were not evaluated.

## 4.7 Evidence and provenance

| Real dataset, reasoning on | Completed runs | Evidence records | With spans and complete file/offset/hash selectors | N-Quad lines | Cited RAG questions, global/per-paper |
|---|---:|---:|---:|---:|---|
| SciLead | 7 | 788 | 788 | 7,341 | 10/10; 10/10 |
| SciREX | 1 | 37 | 37 | 191 | 10/10; 10/10 |

Source: `real-v1/scores/provenance-availability.json`, cross-checked against run artifacts (E19). Counts sum artifacts across question runs; repeated facts across questions are not necessarily distinct scientific findings. RAG retained twenty/twenty-three global citations and seventeen/twenty-one per-paper citations for SciLead/SciREX, respectively.

Every audited real evidence record had a source span and the required locator fields. This is useful provenance availability despite zero engine headline performance. It does not establish gold-evidence coverage, correct relations or support for a generated claim. For example, `scilead-21` contained 522 evidence records while its answer lines returned no rows. Artifact volume alone was insufficient for a useful answer.

On the first Claude synthetic comparison, global RAG citation traceability was 1.000 over six citations and per-paper traceability was 0.950 over twenty. These measure overlap with particular gold source placements, not entailment. High overlap alongside low study-direction accuracy demonstrates that a cited passage can be locatable without establishing a complete or correct scientific synthesis.

## 4.8 Error analysis

The first Claude engine run left S007 undetermined because no question metric was found and S017 undetermined because no control condition was found. The scorer's confusion table records no incorrect determined directions: the two losses were missing determinations. This is a task failure given the available synthetic truth, rather than a model-call service error.

For the seven completed SciLead on runs, automated answer-key analysis labeled three cases extraction errors and four synthesis errors. The single SciREX run was labeled a synthesis error. These are scorer-derived categories based on counterfactual answer-key graph execution, not independent human diagnoses. They require caution because the counterfactual graph must encode names and contexts compatibly with the saved query.

`real-v1/query-replay-20261106.md` documents a concrete limitation for `scilead-17`. The saved query used a straight apostrophe in `WMT'14 EN-DE`, while the answer-key graph used a curly apostrophe. A diagnostic in-memory substitution produced five answer-key rows and the expected best paper, `2008.07772v2` with BLEU 30.1. The actual engine output ranked `1911.09483v1` at 29.9. This confirms a formatting issue in error attribution but does not establish the cause of the actual extraction/query result. The official score remains zero.

For `scilead-03`, answer-key query execution ranked `1906.05012v1` at 36.87, while the engine returned `2001.04063v3` at 36.69 and `1905.03197v3` at 35.75. The best gold paper was absent from the returned rows. Available evidence does not uniquely assign that omission to screening, extraction, normalization or graph construction. The failure is established; its precise causal stage remains unresolved.

## 4.9 Efficiency and computational effort

| Execution aggregate | New model calls | Input tokens | Output tokens | Recorded seconds |
|---|---:|---:|---:|---:|
| Claude engine run 1, 20 studies | 64 | 80,808 | 14,213 | 199.572 |
| Template engine run 1, 20 studies | 67 | 68,164 | 9,925 | 103.468 |
| SciLead engine on, seven runs | 2,361 | 7,560,498 | 149,877 | 3,753.028 |
| SciLead engine off, seven cached runs | 0 | 2,452,578 | 139,598 | 111.361 |
| SciREX engine on, one run | 83 | 196,869 | 8,029 | 144.998 |
| SciREX engine off, one cached run | 0 | 195,371 | 7,983 | 14.301 |

Sources: synthetic report `cost.total` and real per-question `run.json` files. Token fields describe recorded run consumption and can include reused work; the new-call column explicitly distinguishes additional model requests. Summed run seconds are not a measurement of complete campaign wall-clock time.

The first Claude global and per-paper baselines used two calls each, with 4,773 and 16,048 total recorded tokens. This substantial difference from the engine's 95,021 tokens reflects a different computation budget as well as different results. The comparison is not a cost-controlled demonstration of architectural superiority.

SciLead question `scilead-21` dominated recorded real engine-on effort with 1,925 new model calls and 2,934.405 seconds, despite receiving zero score and no returned answer rows. This identifies an expensive failure case suitable for targeted investigation. Reasoning-off timings benefit from cache reuse and cannot be interpreted as evidence that disabling reasoning makes fresh model processing equivalently faster. No monetary, energy or full-workflow amortization result was measured.
