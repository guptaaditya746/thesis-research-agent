# EV1 extraction research and reproducible diagnostics for Claude

Date: 2026-10-21. Scope: research and diagnostic artifacts only; no extractor, prompt,
model deployment, or dependency changes. This is a bounded primary-source review,
including 2025 publications and a current 2026-era model release, rather than a
systematic literature review. Publication suitability requires a separate evaluation;
these experiments cannot establish a top-journal claim.

The immediate engineering priority is to preserve the meaning of a measurement:
**system variant + retrieval state + metric definition + dataset + value + unit +
source spans**. Better word matching is useful only if those relationships remain
correct. A plausible number assigned to the wrong experimental condition is a more
dangerous error than an explicit abstention.

## Evidence classes and reproducibility

- **Reproduced:** actual branch code executed on handwritten adversarial microcases,
  with exact input/output in [results.json](../../tests/EV1/diagnostics/extraction-research/results.json).
- **Candidate only:** four outputs from a small phrase-scope recognizer inside the
  diagnostic script. It has no demonstrated generalization and is not product code.
- **Previously reproduced:** the sibling main worktree's EV1 review diagnostics,
  especially `screen_synonym_rescue`, `metric_rule_overlap`, `negated_condition`, and
  `blind_metric_dataset_validation`. Those findings are independent of this probe;
  do not count them as newly run LLM evaluations.
- **Research-informed proposals:** the changes below have not been implemented or
  benchmarked here. Paper results are not evidence of improvement on EV1.

Run from the branch worktree:

```bash
PYTHONPATH=. /mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/.venv/bin/python tests/EV1/diagnostics/extraction-research/probe.py
```

The environment is reused from the main worktree. All imports come from this branch
through `PYTHONPATH=.`. The script calls `terms.find_all` and actual regex-only
`engine.run` through existing CPU test helpers. No model or server is contacted.
Engine runs use temporary directories. `proposal-config.json` preserves only the
effective conditions/metrics from the recorded proposal and its original SHA-256,
so reruns do not require a sibling proposal directory. The output records the Git
HEAD and relevant source hashes. The script exits zero when it successfully records
diagnostics; the `matches_expected` fields intentionally include false results.

## What the probes establish

| Probe | Actual behavior | Engineering interpretation |
|---|---|---|
| `RAG (no retrieval)` / `RAG (without retrieval)` using proposal rules | Both `rag` and `closed_book` mentions | A single variant is treated as two roles; parenthetical scope is not represented. |
| `RAG (no reranking)` | `rag` | Parentheses evade the existing unparenthesized ablation exclusion. Under the current protocol's documented treatment of component ablations, this needs `other` or explicit review. Whether reranking ablations should count as RAG is a protocol decision. |
| `RAG without reranking` | No mention | Intentional conservative exclusion in current rules, not a regression. It differs from the parenthetical equivalent and should remain an observable abstention. |
| `The RAG model has no retrieval failures.` | `rag` and `closed_book` | `no retrieval` is matched inside `no retrieval failures`; the negated object is failures, not access to evidence. |
| RAG with unrelated negation, and two genuinely separate systems | Expected mention roles | These controls show why a global `no`/`without` veto would remove valid treatment mentions. |
| `FActScore`, `factuality score`, `accuracy` using proposal metric rules | Canonical changes after reversing rule order | Equal-length conflicting aliases are resolved by rule priority. Deterministic current behavior is not randomness; a protocol compilation/validation ambiguity remains. |
| `factual accuracy` | Stable under rule reversal | Longest full phrase wins over nested `accuracy`, providing a useful control. |
| Simple condition-row table, transposed table | Both expected values extracted | The system already has useful table-aware extraction; do not replace it with raw text matching. |
| `System | Factual accuracy (%) | Dataset` | Expected 0.75/0.60, dataset `Trivia` | Positive control for dataset resolution. |
| Equivalent `Dataset | System | Factual accuracy (%)` | Zero measurements | Actual layout sensitivity: `measure._table` finds `dataset_col` but always chooses `row[0]` as the row condition/metric, then skips the row when it is a dataset. |
| `75 out of 100` / `60 out of 100` in explicit accuracy sentences | Zero measurements | Known numeric representation limit: `_sentence` accepts percent or fractional decimal candidates, not count/denominator expressions. This is incomplete coverage, not evidence of fabricated values. |

These are 8 condition cases, 4 metric cases, and 5 engine measurement cases chosen
to expose mechanisms. They are not random samples and their pass rates must not be
reported as accuracy estimates. Measurement cases use the handwritten protocol;
role/alias cases use the saved proposal config. The treatment/control names differ
(`baseline` versus `closed_book`) by design and are identified in the JSON.

The local scope candidate returns the expected control/other classification on its
four supported ablation phrases and abstains on the remaining four. It has not been
evaluated on nested parentheses, multiple clauses, multilingual papers, or genuine
RAG variants with nonessential components removed. Its purpose is to demonstrate
that a bounded stage can express the decision, not to recommend shipping its regex.

## Code mechanisms Claude should inspect

1. `evidence/extractors/terms.py:18` defines condition phrases; the RAG lookahead
   forbids a directly following `with/without`, but not `(`. The control phrase
   lacks a check that `no retrieval` actually describes the system's retrieval state.
2. `terms.py:91` resolves overlapping matches by earliest start, longest span, then
   pattern order. That policy cannot reconcile identical spans assigned two canonical
   metrics. The proposal inserts new aliases alongside incompatible defaults.
3. `evidence/extractors/measure.py:100` handles normal and transposed Markdown tables.
   Its use of `row[0]` at lines 109, 110, 127, and 128 assumes the semantic label is
   the first column. Reordering dataset metadata violates that assumption.
4. `measure.py:153` ignores integer candidates without a percent sign; adding integer
   support alone would confuse counts, years, denominators, sample sizes, and values.
5. `evidence/engine.py:196` stops screening after any extractor returns irrelevant.
   Thus a regex negative prevents the semantic screen from rescuing synonyms. The
   earlier offline scripted-provider probe showed a known frame synonym was skipped
   without a semantic call. Code inspection establishes the mechanism; that saved
   probe establishes the concrete miss. A hard filter's recall upper-bounds pipeline
   recall: later models cannot recover a paper they never receive.

## Primary research and bounded transfer to this system

| Source | Supported finding | Suitable transfer and limit |
|---|---|---|
| [Shi et al., Negation Triplet Extraction, COLING 2024](https://arxiv.org/abs/2404.09830) | Models negation subject, cue, and scope together and uses syntactic dependencies. | Represent which system and property the negation modifies. Its experiments concern Chinese review text, not English scientific result extraction; do not assume its model or reported gains transfer. |
| [Zhuang et al., ReSel, EMNLP 2022](https://aclanthology.org/2022.emnlp-main.46/) | Decomposes scientific N-ary relation extraction into paragraph/table retrieval and target selection, modeling structural relations. | Use a candidate region stage followed by relation extraction while preserving table structure. This is an architectural precedent, not evidence that its trained architecture is necessary here. |
| [Lou et al., S2abEL, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.186/) | Scientific table linking often needs surrounding prose; provides 8,429 labeled cells from 732 tables. | Evaluate alias definitions in captions/text plus table headers; simple row/column matches are insufficient for all papers. Dataset labels are entity links, not a ready-made gold set for RAG effects. |
| [Park et al., Flexible and Efficient Grammar-Constrained Decoding, ICML 2025](https://proceedings.mlr.press/v267/park25l.html) | Grammar constraints guarantee the specified output syntax through token masking. | Keep small typed outputs for each atomic step. Grammatical JSON does not guarantee correct condition/value links, completeness, or factuality. Decoder efficiency improvements do not address those failures. |
| [Schall and de Melo, Hidden Cost of Structure, RANLP 2025](https://aclanthology.org/2025.ranlp-1.124/) | Finds task/model-dependent performance effects under constraints and benefits from adapted prompts and demonstrations. | Compare constrained and unconstrained extraction on the same labeled examples; use schema-matched examples. It does not prove more examples or constraints always help our local models. |
| [Sakota and West, BoostCD, EMNLP 2025](https://aclanthology.org/2025.emnlp-main.926/) | Combines constrained/unconstrained predictions using a learned boosted model for closed IE. | Error diversity can be more useful than repeating one identical prompt. Its learned combination is not equivalent to a free-form second-model vote and would require training/evaluation. |
| [Angelopoulos et al., Conformal Risk Control, latest revision 2025](https://arxiv.org/abs/2208.02814) | Controls expected monotone loss using calibration under the method's assumptions. | Consider calibrated escalation/abstention after acquiring independent calibration labels. A confidence score from an LLM is not a guarantee; selected synthetic survivors and distribution shift challenge calibration validity. |
| [NuMind, NuExtract3 official model card, accessed 2026-10-21](https://huggingface.co/numind/NuExtract3) | Offers a specialized 4B model with text/image plus typed JSON template, verbatim fields, optional examples, null/empty for absence. | Worth a future small-model baseline, especially for real PDF tables. Vendor results use an internal document benchmark and are not independent evidence for scientific evidence synthesis; no installation or model test was performed here. |

ReSel and S2abEL are included because they address our actual scientific-table
relationships more directly than a generic recent chat-model leaderboard. The newer
decoding research addresses output structure, while the current NuExtract release
provides a concrete specialized baseline to evaluate. None replaces a gold relation
dataset or a human audit.

## Recommended workflow and atomic prompt contracts

These are proposed contracts for Claude to implement and evaluate, not installed
prompts. Keep source text untrusted and explicitly delimit it as data.

| Stage | Defined input | Defined output | Example and rejection rule |
|---|---|---|---|
| Region candidate selection | Document spans, section/table IDs, question terms | List of region IDs, no synthesized facts | A result table plus its caption and alias-defining paragraph; do not discard a document solely for missing literal synonyms. |
| System identity/retrieval state | One region, local alias definitions, declared protocol role policy | `system_id`, verbatim label, retrieval state (`enabled/disabled/unclear`), ablation target, evidence quotes | `RAG (no retrieval)` => disabled; `no retrieval failures` => no control claim. `RAG without reranking` retains its variant identity and is adjudicated by protocol. |
| Metric identity | Metric header/name plus definition and unit | Verbatim name, canonical or `unresolved`, unit, direction, quote | `accuracy` without a factuality definition is unresolved/generic; do not assume QA exact match and atomic factual precision are interchangeable. |
| Measurement relation | One table/paragraph plus resolved IDs | Tuples of system ID, metric ID, dataset, raw value, unit, value quote, label/header quotes | `75 out of 100` preserves numerator/denominator and delegates division to code; no invented dataset or silently inferred pair. |
| Independent verification | Source region, protocol definitions; verifier initially blinded to candidate answer | Its own tuples and a complete disagreement list after deterministic comparison | Same value with wrong metric or dataset must fail comparison; empty output is an observable omission, not approval. |
| Deterministic validation | Candidate and verifier tuples plus spans | Accepted/rejected/unresolved with reason codes | Check offsets, numeric parsing, range, unit, compatible dataset/system pairing and alias conflicts. |

Use one ordinary positive example, one difficult negative, and one abstention example
for each atomic step. Keep outputs short and typed, forbid inferring absent facts,
and version the input/output schema, examples, model revision, decoder and rules in
cache/provenance identities. More workflow stages are a hypothesis: measure their
error propagation and cost against a single-call baseline.

The user's proposed three-model arrangement can be evaluated as `orch-model`
writer/extractor, `sub-model-1` blind verifier A, and `sub-model-2` blind verifier B.
Compare their independently extracted complete tuples deterministically, then send
disagreements to explicit adjudication. Separate endpoints do not imply independent
errors: if both submodels use the same weights, agreement may repeat a shared blind
spot. Record served model/weight revision, prompt, decoding settings, and disagreement
type; estimate missed errors against human labels. This experiment was not run.

## Prioritized engineering changes for Claude

| Priority | Proposed change | Acceptance evidence |
|---|---|---|
| P0 | Compile a single metric registry and reject incompatible aliases mapping the same surface span to different canonicals; explicitly override defaults when extending vocabularies. | The three order-sensitive examples become order-invariant or produce a validation error; preserve full-phrase matching and record protocol semantics. |
| P0 | Add explicit condition identity and local retrieval-state/ablation resolution; abstain when scope is uncertain. | Parenthetical and unparenthesized variants produce consistent semantic results; unrelated negation remains valid; count incorrect-role assertions separately from abstentions. |
| P0 | Replace literal-negative screening with candidate/uncertain/confirmed-irrelevant routing, or at least route lexical misses to semantic screening during evaluation. | Seeded known synonyms reach the model; report document recall and number/cost of rescued negatives on independently labeled relevant/irrelevant papers. |
| P0 | Verify all measurement tuple fields, not only condition/value. | Seeded wrong metric, dataset, direction, unit, and omitted-result cases are detected; valid formatting alone cannot pass. |
| P1 | Resolve table columns semantically rather than assuming the first column; preserve headers/captions and raw spans. | Dataset-first and dataset-last controls yield identical tuples, while simple/transposed controls keep working; ambiguous multiheader tables escalate. |
| P1 | Add bounded count/denominator parsing with unit checks and code arithmetic. | Both ratio prose cases produce 0.75/0.60; adversarial years/sample sizes/deltas never become result values; include denominator zero and rounding cases. |
| P1 | Compare regex-only, typed small-model extraction, and hybrid escalation under one frozen annotation protocol. | Report tuple precision/recall, correct links and document coverage, plus escalation rate, abstention, tokens, latency, and failures with uncertainty. |
| P2 | Explore calibrated routing and a specialized 4B extraction baseline only after a separate calibration/development set exists. | Use frozen held-out real papers and independent human adjudication; report calibration assumptions and domain shift; do not tune on final test failures. |

Safe regex improvements are bounded lexical normalization, curated aliases, exact
number/unit parsing, and explicit local patterns with counterexamples. Dependency
parsing may help scope but adds model/runtime errors and should compete against a
small typed classifier. Do not grow one regex into a universal scientific grammar.

Repairing alias ambiguity, broken column assumptions, and invalid tuple acceptance
is engineering correctness. A publishable research contribution would require a
clearly stated extraction/verification question, credible independent gold data,
strong baselines and ablations, and evidence of generalization beyond generated
papers or these hand-picked examples.
