# Improving the thesis: exhaustive scientific QA that accounts for unresolved evidence

**Research proposal, 6 November 2026.** This document proposes future work; it reports no new experiments. It uses the audited results in [Chapter 4](04-results.md), the limitations in [Chapter 5](05-discussion.md), and a targeted review of primary research. The filename follows the requested `impromement.md` spelling.

## 1. The recommended research direction

Build a system that answers two questions together:

1. **What answer does the currently supported scientific evidence justify?**
2. **Could any unresolved evidence in the supplied corpus change that answer?**

The proposed contribution is an executable method for carrying uncertainty about missing facts, ambiguous experiment associations, and conflicting measurements through a scientific query. It should compute conservative answer bounds, identify unresolved evidence that could change the result, and spend additional verification effort on those cases. When uncertainty remains consequential, it should return a partial result or abstain with an explicit reason.

**Use no embedding model, vector database, dense retriever, or embedding-based reranker.** Enumerate the supplied corpus exhaustively. Use exact identifiers, source offsets, relational joins, deterministic normalization, and lexical search for navigation. Lexical ranking may change inspection order; it must not silently remove evidence from scope. Existing generative LLMs can interpret passages and propose facts. Their internal token representations are not an additional retrieval embedding model.

A possible paper title is:

> **When Can Missing Evidence Change the Answer? Exhaustive Scientific Question Answering with Explicit Uncertainty**

The novelty hypothesis is a **query-executable representation of missing scientific facts and uncertain experiment associations, with explicit handling of fallible verification**, evaluated against equally exhaustive alternatives. Answer-directed verification is a supporting mechanism with substantial prior art. Exhaustive retrieval, a knowledge graph, citations, typed plans, and a generator/verifier pair are individually insufficient novelty claims.

This is a plausible research direction for a strong submission, not a prediction of acceptance at ICLR, ICML, or NeurIPS. The decisive evidence would be a generalizable algorithm and controlled improvements over strong alternatives, including failures of its own guarantees. A larger application with more agents would not establish that contribution.

## 2. Why this addresses the actual thesis weaknesses

| Audited observation | What it establishes | Required improvement |
|---|---|---|
| SciLead: engine top-1 0/10; 7/10 plans executed; conditional correctness 0/7. Global RAG achieved 6/10. | Planning failure is only part of the problem. | Trace the complete question → fact → relation → query → answer contract. |
| SciREX: engine mean list F1 0 over ten questions; only one plan executed. | The existing planner has poor coverage on these list questions. | Compile a small typed query language into supported operations; preserve unsupported intent explicitly. |
| All 788 SciLead and 37 SciREX evidence records had source locators, despite zero headline scores. | Addressable provenance does not establish correct scientific support. | Verify complete tuples and distinguish locator validity from semantic correctness. |
| `scilead-21`: 522 evidence records and 1,925 new model calls, yet no answer rows. | More extraction and more calls need not resolve the answer. | Measure and prioritize actions that reduce consequential uncertainty. |
| First Claude synthetic comparison: engine 0.90, global RAG 0.20, per-paper RAG 0.80; engine minus per-paper interval included zero. | Document exposure is a serious alternative explanation for the apparent gain. | Compare with full-corpus map/reduce and flat structured extraction at matched budgets. |
| Existing `locate` already supports exhaustive document scope. | Exhaustiveness is already implemented at one stage. | Account for downstream screening, omitted facts, context limits, failed calls, and uncertain joins. |

These values come from [the results chapter](04-results.md), [claim audit](claim-audit.md), and [verified evidence](verified-evidence.json). The current exhaustive scope is implemented in [locate.py](../backend/evidence/locate.py); [planrun.py](../backend/evidence/planrun.py) already selects it but also configures screening. Giving an extractor the whole document does not prove that it read or extracted every relevant fact.

The `scilead-17` apostrophe discrepancy is a useful regression case, but the recorded diagnostic concerns answer-key query replay. It does not prove that normalization alone caused the incorrect production answer. Likewise, the absent best paper for `scilead-03` needs stage-by-stage investigation. Preserve these uncertainties rather than building the new method around an unverified causal story.

## 3. Closest prior work and the novelty boundary

This is a targeted literature review, not an exhaustive novelty search. Verify the closest methods again before making a submission claim, including publications appearing after this document.

| Prior work | Established overlap | What the proposed work must add or test |
|---|---|---|
| [LOTUS: Semantic Operators and Their Optimization, PVLDB 2025](https://www.vldb.org/pvldb/vol18/p4171-patel.pdf) | Natural-language operators for filtering, joins, grouping and ranking; optimized execution with accuracy guarantees relative to reference algorithms. | A distinct treatment of unresolved source evidence and final-answer sensitivity. Do not describe operator composition or accuracy guarantees as new. |
| [DocETL, PVLDB 2025](https://www.vldb.org/pvldb/vol18/p3035-shankar.pdf) | Decomposes complex document processing and rewrites pipelines to address extraction errors, with agent-guided evaluation. | Demonstrate benefits beyond decomposition and repeated validation alone. |
| [MOAR, 2026 revision](https://arxiv.org/abs/2512.02289v4) | Optimizes semantic pipelines jointly for accuracy and cost, including global rewrite search. | Compare answer-directed verification with ordinary cost/quality optimization. Cheap execution alone is insufficient novelty. |
| [SciFact: Fact or Fiction, EMNLP 2020](https://arxiv.org/abs/2004.14974) | Scientific claim verification with supporting/refuting evidence and annotated rationales. | Evaluate corpus-level ranking, lists and aggregation with unresolved evidence; do not claim to invent scientific verification. |
| [Agentic Model Checking, 2026 preprint](https://arxiv.org/abs/2605.21434) | Couples model proposals with deterministic verification and refinement in software verification. | Establish what can actually be checked when the source is scientific prose and the semantic oracle is fallible. |
| [Libkin, How to Define Certain Answers, IJCAI 2015](https://ijcai.org/proceedings/2015/609) | Formalizes query answers under incomplete information and explains why answer representation and completion semantics matter. | Define semantics separately for lists, counts and rankings; do not claim the possible-worlds principle as new. |
| [Green, Karvounarakis and Tannen, Provenance Semirings, PODS 2007](https://www.cs.ucdavis.edu/~green/papers/pods07.pdf) | Propagates algebraic provenance through relational computations, including connections to incomplete databases. | Track uncertainty about scientific interpretation in addition to computational lineage. |
| [Clarke et al., Counterexample-guided Abstraction Refinement, CAV 2000](https://web.stanford.edu/class/cs357/cegar.pdf) | Refines over-approximations using spurious counterexamples; soundness depends on containing concrete behavior. | Address the unproved semantic-oracle premise instead of presenting refinement itself as original. |
| [Karlaš et al., From Certain Answers to Certain Predictions / CPClean, PVLDB 14](https://vldb.org/pvldb/vol14/p255-karlas.pdf) | Selects incomplete data to clean according to downstream prediction uncertainty, with termination when completions agree; studies nearest-neighbor classifiers and human cleaning. | Even inspecting only answer-changing uncertainty is established. The proposed advance must concern undiscovered evidence, ambiguous scientific joins, and fallible reviewers. This citation does not propose adding a nearest-neighbor model. |
| [Proof-Carrying Certificates for LLM Pipelines, 2026 preprint](https://arxiv.org/html/2605.16407v1) | Describes conditional checking, conflict-aware grounding, partial certified outputs and abstention around LLM pipelines. | Do not claim to invent proof-carrying answers or conditional certification. Treat it as a preprint whose artifact and claims were not reproduced here. |

The central theoretical idea inherits from the incomplete-database and refinement literature above. The definition “answer remains unchanged over all admissible completions” is not itself a new result. The nearest overlap in verification selection is CPClean; the crucial difference to investigate is whether source discovery and fallible semantic closure require a materially different representation and algorithm, rather than a change of application domain.

**Candidate original contribution:** an implementable uncertainty representation that preserves unresolved source obligations through scientific measurement joins and can reopen incorrect semantic premises, with a measured relationship between conditional stability and real answer correctness. The representation must handle uncertainty about whether a row exists, what its fields mean, and which experiment it belongs to. Simply renaming missing database cells as “evidence obligations” would not suffice. This remains a hypothesis until the closest prior systems are compared directly.

**Reasons to abandon or narrow the novelty claim:** an existing method already offers the same uncertainty representation and verification policy; equally exhaustive flat processing performs as well at the same cost; the proposed certificates are usually vacuous; or incorrect semantic closures make the certificates unreliable. A useful negative result can still improve the thesis without supporting the proposed stronger claim.

## 4. Specify a small, executable scientific question contract

Begin with two tasks already represented in the real evaluation: **best-performing-paper selection** and **listing matching papers or experiments**. Add counts and other aggregates only after their semantics are explicit. Free-form synthesis, causal chaining, and every ontology relation should not be the first implementation target.

The model proposes a typed contract, rather than arbitrary SPARQL. Code compiles it into a restricted operator tree. Required fields are:

- Exact question ID and text hash, corpus manifest hash, and output unit: paper, experiment, method, or measurement.
- Task, dataset and split, metric, unit, optimization direction, and comparability constraints.
- Operator: initially `filter`, `project`, `join`, `distinct`, and `argmax`/`argmin` with declared tie handling.
- Evidence fields needed by every operator, including source selectors and experiment identity.
- Alias rules, inclusion policy, and explicit unresolved research-policy choices.
- Output type, unsupported-condition behavior, and the uncertainty assumptions permitted for a stability claim.

The compiler should reject a ranking without a metric or direction, a join without a defined relation, and a comparison across incompatible evaluation splits. It should emit an explanation linking each query restriction to the question or an explicitly recorded policy decision. A valid program can still misinterpret a question, so contract fidelity needs its own evaluation.

Do not default a missing metric to a scientifically meaningful substitute. Do not use gold answers to choose among interpretations. When intent remains ambiguous, retain the alternatives or request a genuine research-policy decision. Automatic system decisions must remain labeled as such.

This improves the existing [planner](../backend/evidence/planner/plan.py) and [plan execution](../backend/evidence/planrun.py) interfaces without treating every syntactically valid query as a sound experimental method.

## 5. Build a ledger of both evidence and unresolved obligations

### 5.1 Exhaustive source accounting

For every paper, enumerate all available text blocks, table rows, captions, and required shared headers from the ingested representation. Record original file hashes and offsets. Chunk by explicit context budgets with overlap and stable identities. Detect uncovered ranges, truncation, parser failures, missing supplements, and unreadable tables.

Scope the word **exhaustive** precisely: all enumerated units in the frozen supplied corpus. It does not mean all papers in the literature, all information in an unavailable PDF, or complete semantic understanding.

Use separate coverage fields for `enumerated`, `submitted`, `successfully_processed`, and `reviewed`. An unsuccessful model call does not mark a unit processed. A “no match” model response marks a review outcome; it does not establish that no relevant fact exists. Preserve at least one open discovery obligation wherever relevant evidence might still have been missed.

Retain cross-block obligations for table headers, footnotes and experiment descriptions. Enumerating isolated rows is inadequate if their interpretation depends on another passage. A learned or lexical relevance judgment can prioritize work, but must not erase an unresolved obligation.

### 5.2 Facts carry complete scientific context

Represent a measurement as a tuple such as:

```text
(paper, experiment, method, task, dataset, split,
 metric, value, unit, direction, conditions, source selectors)
```

Keep the original string, parsed value, normalization rule, and all alternative interpretations. Use Unicode and whitespace normalization for presentation differences only when semantics are preserved. Do not merge datasets, language pairs, percentages, or experiment settings simply because their labels look similar.

Represent alternative method/metric/experiment attachments as explicit competing tuples. A value of 30.1 attached to the wrong experiment is an error, even when the numeric span is correct. Exact duplicates may share storage, but conflicting records and source identities must survive.

### 5.3 Separate process status from truth status

Each obligation records a source unit, needed fields, current alternatives, supporting selectors, checks, attempts and remaining uncertainty. Process statuses may include:

| Status | Meaning |
|---|---|
| `unread` / `failed` | No usable interpretation is available. |
| `candidate` | A model or rule proposed one or more interpretations. |
| `supported_under_assumptions` | Checks passed, with semantic assumptions explicitly attached. |
| `ambiguous` / `conflicting` | Multiple interpretations or sources remain consequential. |
| `reviewed_no_match` | A review found no match; a semantic negative is not automatically proved. |
| `excluded_by_contract` | An explicit contract predicate excludes this record under recorded premises. |

A spelling check, source hash, or second model agreement cannot upgrade semantic uncertainty into mathematical certainty. All closures must identify whether they follow from deterministic source structure, human annotation, or a fallible model judgment.

### 5.4 The concrete representation to investigate

Prototype a state `(R, A, O, C, P)`:

- `R`: source-anchored candidate rows, each with a presence variable and typed value domains.
- `A`: alternative attachment variables linking values to methods, metrics and experiments.
- `O`: open discovery obligations indexed by source unit and required evidence relation; these allow additional rows rather than only filling known cells.
- `C`: explicit compatibility constraints, such as mutually exclusive interpretations of one table cell. Preserve shared-variable dependencies across rows.
- `P`: premises that justify narrowing a domain or closing an obligation, with checker identity, source scope, version and dependent outputs.

Its meaning is the set of evidence tables satisfying these constraints, including rows permitted by `O`. Filtering must retain unknown predicate outcomes; joining must propagate compatible attachment alternatives; projection/distinct must account for uncertain identity. An unresolved obligation must survive each operation whenever a row it permits could affect the output.

This representation makes the candidate contribution implementable and falsifiable. Compare it with ordinary intervals on extracted rows, which omit discovery, and with independent cell alternatives, which omit shared experiment constraints. Test whether the extra structure yields tighter valid bounds or prevents false stability enough to justify its cost. Theoretical worst-case complexity may remain exponential; report runtime and conservative fallback rates rather than promising efficient exact reasoning for arbitrary queries.

## 6. Propagate uncertainty to the answer

### 6.1 Conditional semantics

Let `S` be the ledger and `Γ(S)` the set of complete evidence tables consistent with its alternatives, open discovery obligations, and declared assumptions. Let `Q` be the compiled query. Define:

```text
PossibleAnswers(Q, S) = { Q(T) : T belongs to Γ(S) }.
```

An answer is **stable under the recorded assumptions** when this set contains exactly one output. If `Γ(S)` is empty because the constraints conflict, report inconsistency; never interpret the empty set as a successful proof.

The complete-table universe must allow additional relevant rows whenever discovery remains unresolved. Restricting it to already extracted facts would assume away the very omission problem the method is meant to address. If an unresolved block has no justified cardinality or value bound, preserve an unbounded alternative. A finite chunk does not by itself supply a scientifically justified measurement bound.

Full enumeration will often be infeasible. Implement a conservative abstraction that contains every possible query result under the premises. A singleton over-approximation supports conditional stability; a non-singleton result may merely reflect a loose abstraction. Solver timeout means unknown, not stable.

### 6.2 Start with operators whose bounds are understandable

| Query | Conservative output |
|---|---|
| List matching papers | Papers present in every admissible result, plus papers that may be present. A complete list is stable only when these coincide. |
| Count distinct matching papers | Lower and upper bounds over corpus paper identities; unresolved membership contributes to the upper bound. |
| Best score / best paper | Candidate score intervals, eligibility alternatives, possible winner set, and tie policy. Include possible undiscovered competitors. |
| Join measurement to experiment | All supported and unresolved compatible assignments; never force a single attachment merely to obtain rows. |

For a maximization query with justified score bounds `[L_i, U_i]`, guaranteed eligibility of candidate `w`, and a complete representation of competitors, the sufficient condition `L_w > max(U_j, j != w)` gives a unique winner. Unknown eligibility or unknown competitors must be included. Reverse the relation for minimization. Equality requires the declared tie semantics.

An empty query result is stable only if all admissible completions also give that result. Distinguish “no match in the current graph,” “no supporting evidence established,” and “no eligible item under the declared corpus assumptions.” These have different meanings.

### 6.3 What can be proved, and what must be measured

The initial formal target is modest:

> If the complete evidence table is included in `Γ(S)`, the question contract is correct, and every abstract operator conservatively contains the concrete operator's result, then a singleton abstract answer equals the concrete answer for that table.

Prove the operator cases and their composition for the restricted language. Exhaustively enumerate small finite tables to test the implementation against a concrete evaluator. This is a conditional soundness result, not a theorem that LLM extraction understands papers correctly. The difficult premise is whether the true evidence is retained by the uncertainty representation.

Use two explicitly separated modes:

- **Conservative mode:** keep unresolved semantic negatives and uncertain facts open. It may abstain frequently; report that limitation.
- **Empirical closure mode:** permit a preregistered reviewer or calibrated rule to close selected semantic obligations. Every stability statement is conditional on those closures; measure false stability against independent labels.

Do not manufacture tight numerical bounds from LLM confidence. Agreement across identical Qwen replicas is correlated evidence. Adaptive selection can invalidate naive calibration assumptions, so calibrate and evaluate the entire frozen decision procedure at question level, with separate data and explicit distribution assumptions. Do not claim conformal or statistical coverage merely because a confidence threshold was added.

## 7. Verify the unresolved evidence that could change the answer

The controller should ask for an **alternative admissible answer**, then identify which unresolved facts or associations allow it. This is a counterexample to current answer stability, not an invented scientific observation. A hypothetical score never enters the evidence graph as a reported measurement.

For each unresolved obligation, estimate how many competing answers it influences, or how much it could tighten the current output bounds. Divide by estimated verification cost and prioritize the largest value. Initial priorities can use deterministic operator dependencies and previous token counts; no embedding model is needed. Treat this scheduling rule as a heuristic until its properties are established.

```text
compile and validate the question contract
enumerate source units and initialize open obligations
perform an initial full-corpus evidence pass
repeat within the recorded budget:
    propagate conservative answer bounds
    if constraints are inconsistent: return an explicit conflict
    if the answer is stable under declared premises: return answer + audit bundle
    find unresolved obligations permitting a different answer
    select one obligation by influence and estimated cost
    interpret or verify its source context
    validate the output; preserve all attempts and disagreements
    update the ledger and dependent bounds
return partial answer + unresolved obligations + exhaustion reason
```

The initial full-corpus pass is part of the cost. Adaptivity changes verification effort after that pass; it is not an excuse to describe a top-k reader as exhaustive. Under a strict conservative policy, unresolved discovery elsewhere may prevent termination even after the apparent winner is verified. That is an informative failure mode, not something to hide.

Use distinct atomic model tasks for contract interpretation, tuple extraction, tuple verification, and ambiguity resolution. Follow [the repository prompt policy](../docs/prompt-writing.md): typed inputs/outputs, normal/ambiguous/missing-information examples, exact source material, deterministic acceptance checks, and bounded repairs. A verifier sees the task, proposal and source, without the generator's persuasive rationale. Keep arithmetic, joins, normalization, stopping logic, and artifact hashes in code.

A reviewer correction that contradicts an earlier accepted premise must reopen it and invalidate dependent stability statements. Within a fixed sound premise set, refinement should only remove possible completions; premise repair is a separate, versioned operation that can widen them again. Log both.

### Illustrative example, not an experimental result

A development fixture asks which method has the highest score on a fixed dataset/split. Candidate A has 30.0, candidate B has an unresolved table association allowing either 28.0 or 33.0, and candidate C has 29.0. A further source block remains unread.

Reporting A would be premature: B may win, and the unread block may contain another competitor. The controller requests the table header needed to resolve B and accounts for the unread block. If B is established as 28.0 and the remaining block is excluded under defensible recorded premises, A becomes conditionally stable. If either issue remains unresolved, return the candidate set and the reason. Numbers here demonstrate the algorithm only; they are not new dataset labels or claimed scores.

## 8. The experiment that would establish a contribution

### 8.1 Separate development from a new held-out test

The existing SciLead/SciREX failures are now inspected development evidence. Preserve their original results and use them as regression cases, not as untouched evidence for a new method's generalization. Keep their original ten-question denominators in historical reporting.

Before optimization, lock a new test selection with exact question texts, corpus hashes and paper/study-family groups. Recheck paper overlap and the SciREX ID-generation dependency on corpus filtering. If the remaining data cannot supply an independent test, explicitly record that blocker and obtain a legitimate additional release or authentic annotations. Do not simply rename an old question or paraphrase it into a new test case.

Use all eligible held-out questions where feasible. Select the evaluation size through a prospective power/precision assessment and available independent units; ten questions per set are useful for a pilot but weak support for broad superiority. Three model repetitions characterize execution variation, not three independent datasets.

Prioritize real SciLead ranking and SciREX lists. SOFC-Exp or MeasEval are later candidates only after corpus, rights and label-to-contract mappings are validated. Existing synthetic results remain completed historical evidence and need not be rerun. Algorithmic toy tables are unit tests, not a replacement synthetic thesis campaign. New robustness data would require a separately specified, versioned protocol.

### 8.2 Necessary systems and ablations

All proposed comparisons below use the same pinned generator, source documents, question IDs, metric definitions, and output-scoring interface. No system requires a retrieval embedding model.

| Condition | Status today | Purpose |
|---|---|---|
| Existing global BM25 RAG | Implemented; historical results exist | Continuity with the thesis. |
| Existing per-paper BM25 RAG | Implemented; historical results exist | Stronger document-exposure baseline, still passage-limited. |
| Full-corpus map/reduce | Proposed implementation | Read every unit and merge source-linked outputs; test whether exposure explains improvement. |
| Full-corpus flat tuples + deterministic query | Proposed implementation | Same extraction representation without a graph or uncertainty controller; test representation necessity. |
| Contract compiler + full-corpus tuples | Proposed ablation | Isolate improved planner/executor alignment. |
| Full proposed method, fixed-order verification | Proposed ablation | Isolate uncertainty semantics from scheduling. |
| Full method, random verification order | Proposed ablation, fixed seeds | Test whether answer influence beats an equally budgeted ordering. |
| Full method, disagreement-only verification | Proposed ablation | Test whether final-answer dependencies add value beyond selecting model disagreements. |
| Adapted downstream-uncertainty selection | Proposed conceptual baseline | Apply a CPClean-inspired selection objective to the same structured QA state; label it an adaptation, not the original classifier algorithm. |
| Full method, verify every obligation | Proposed ablation | Measure savings relative to uniform verification. |
| Full method, answer-directed verification | Proposed main method | Test risk/coverage/cost improvements. |
| Full method with flat versus RDF storage | Proposed controlled ablation | Determine whether graph storage itself adds value. |

Include a compatible DocETL or LOTUS-style semantic-processing baseline if feasible after a source-level compatibility check. Published optimized configurations can use embeddings; do not silently enable those paths. An embedding-free reimplementation must be labeled an adaptation, with its differences documented. If absent, report the resulting comparison limitation.

For each main comparison, report both unrestricted cost and matched token/call budgets. Match source exposure for the exhaustive conditions. Include verifier calls, planning, failed attempts, query computation, preprocessing and cold/warm cache distinctions. Use identical evidence snapshots for pure query-semantics ablations; use fresh calls for independent full-pipeline repetitions. The old cached ontology-off runs do not satisfy that role.

Do not make ontology reasoning the central novelty claim. Saved templates do not exercise its hierarchy. Any future ontology ablation must show that the evaluated query actually uses the changed reasoning treatment. Do not add a human-confirmed condition without authentic reviewers.

The essential representation ablations are: remove open discovery obligations; remove alternative experiment attachments; and prevent previously accepted premises from reopening. Run these on the same initial extraction snapshots. Their purpose is to identify where apparently confident wrong answers arise, not to maximize a score by deleting safeguards. Small controlled omissions and attachment errors can be tested on separate versioned developer fixtures; never corrupt the original corpus or labels. Existing real failures remain the primary motivating evidence.

### 8.3 Preregister falsifiable hypotheses

1. **Contract alignment:** compiling the typed contract improves executable-plan coverage without reducing semantic fidelity, compared with the existing planner.
2. **Reliability:** at matched answer coverage and source exposure, uncertainty propagation reduces incorrect complete answers relative to flat exhaustive extraction.
3. **Efficiency:** at matched answer quality or conditional error, answer-directed verification uses fewer new tokens/calls than fixed, random, or uniform verification.
4. **Generalization:** the effect persists across both ranking and list tasks and independent study families; it is not confined to inspected normalization failures.

Preregister minimum practically useful differences from development data and resource constraints before viewing held-out outcomes. A confidence interval spanning zero is not evidence of improvement. If the controller adds cost without a reliability or coverage benefit, reject the corresponding hypothesis.

## 9. Metrics and failure analysis

### Existing metrics to preserve

Use SciLead top-1 correctness and SciREX **list F1**, with the existing documented full-sample treatment of unsuccessful cases. Keep blocked IDs and model failures visible. Conditional scores over completed or answered cases remain diagnostics. Do not relabel SciREX F1 as recall or replace the denominator with successful plans.

The current code already records model calls/tokens and exposes source artifacts. See [whole-run scoring](../backend/evaluation/wholerun.py), [aggregation](../backend/evaluation/wholerun_cmd.py), and [statistics](../backend/evaluation/stats.py). New measures below need implementation and validation; they are not current findings.

### Proposed measures

| Measure | Definition and required evidence |
|---|---|
| Contract fidelity | Agreement of typed intent with an independently established interpretation; parse success is separate. |
| Source processing coverage | Successfully processed enumerated units / all required units, with failed and missing-source counts. This is not semantic recall. |
| Full-tuple evidence precision/recall | Match method, experiment, metric, context, value and source support against compatible gold; unavailable without adequate labels. |
| Answer coverage | Complete answers / all sampled questions. Partial answers and abstentions reported separately. |
| Selective error | Incorrect complete answers / complete answers, at declared coverage or budget. Undefined when no answers are returned. |
| False stability rate | Incorrect outputs marked stable / outputs marked stable, against independent gold and the stated assumptions. Undefined with zero stable outputs. |
| Interval or candidate-set validity | Fraction of labeled truths contained in reported bounds/sets; report widths and set sizes so trivial unbounded outputs cannot look useful. |
| Verification efficiency | New calls/tokens and wall time to reach a specified quality/coverage operating point. Include the initial exhaustive pass. |
| Provenance correctness | Valid selector resolution and independently checked support for the entire associated scientific fact, reported separately. |

A stable but wrong answer is a first-class failure. Classify it as contract misinterpretation, incomplete source enumeration, missed evidence falsely closed, wrong tuple accepted, unsupported normalization, incorrect join, unsound bound, compiler/operator error, or scoring mismatch. Preserve unknown causes rather than forcing every failure into a convenient stage.

Use paired comparisons on identical questions and resample at an independent paper/study-family level when questions share evidence. Report repeated-run variability separately. For small or all-zero error counts, show denominators and an appropriate uncertainty interval; zero observed errors do not establish zero risk. Select thresholds on development/calibration data, then freeze them. A risk/coverage curve computed after seeing test labels is descriptive, not a deployed guarantee.

For no-evidence tasks, require genuine labels establishing the expected behavior in the defined corpus. An abstention caused by uncertainty is different from a correct no-evidence answer. A partial correct list is not a certified complete list.

## 10. Implementation sequence with decision gates

This document authorizes no implementation or new model run. A future implementation should use new versioned outputs and preserve current services, data, labels and original runs.

| Milestone | Concrete deliverable | Gate before expanding |
|---|---|---|
| 1. Diagnose the contract boundary | Replay/inspect source → extraction → graph → query for a few existing development failures; trace missing and rejected bindings. | Identify observed failure stages; do not confuse scorer replay issues with production causes. |
| 2. Build the strong exhaustive baseline | Full-corpus flat tuples, deterministic query, identical scoring and cost accounting. | It must execute ranking and list development cases; assess whether it already solves the problem cheaply. |
| 3. Add the small contract compiler | Typed intent, deterministic compilation, explicit ambiguity, invalid-operation fixtures. | Demonstrate semantic fidelity as well as validation coverage. |
| 4. Implement uncertainty semantics offline | Ledger, open discovery, interval/set propagation, concrete evaluator and finite exhaustive tests. | No false stability on the finite test universe; all assumptions documented. |
| 5. Connect bounded verification | Atomic source-grounded calls, premise versions, budget caps, immutable audit bundle. | Resolve consequential ambiguity without silently converting model confidence into proof. |
| 6. Pilot on real development data | Matched exhaustive baselines and fixed/random/uniform scheduler ablations. | Continue only if useful coverage and reliability justify overhead. |
| 7. Freeze and evaluate | Untouched split, protocol, implementation hashes, thresholds, budgets and all systems fixed. | Complete held-out runs with every failure counted before claiming improvement. |

Likely integration points are [contract.py](../backend/evidence/contract.py), [checks.py](../backend/evidence/checks.py), [engine.py](../backend/evidence/engine.py), [planner/plan.py](../backend/evidence/planner/plan.py), [planrun.py](../backend/evidence/planrun.py), [kg/build.py](../backend/evidence/kg/build.py), and [kg/query.py](../backend/evidence/kg/query.py). Keep the new uncertainty evaluator separate from production until its semantics and regression cases are validated. Reuse [recording](../backend/evidence/recording.py), [sealing](../backend/evidence/seal.py), and [replay](../backend/evidence/replay.py).

The future audit bundle should include the question contract; corpus/unit manifest; proposed and rejected tuples; unresolved obligations; bounds at each step; witnesses for possible alternative answers; premise changes; verification prompts/responses; source selectors; compiler/version hashes; per-stage costs; final answer status; and scorer version. The UI should expose the current answer, remaining uncertainty, and the source needed to resolve it. A polished UI is a delivery mechanism, not the scientific contribution.

Keep Ampere-only deployment, pinned models and cluster-provided Hugging Face cache settings. Reuse the established launch/logging workflow and bounded sequential workload. This research proposal does not require dependency upgrades, model substitutions, new services, or rerunning completed synthetic experiments.

## 11. What would make this a stronger publication

Organize a future paper around a narrow question: **Can explicit unresolved evidence improve the reliability–coverage–cost trade-off of exhaustive scientific QA?**

The strongest contribution package would contain:

1. A precise uncertainty representation for incomplete scientific evidence, including open discovery and ambiguous experiment joins.
2. A restricted executable query semantics with a conditional soundness argument and independently testable checker.
3. An effective verification policy whose benefit survives comparisons with equally exhaustive, equally budgeted alternatives.
4. Real-data evidence of improved end-to-end performance or lower error at matched coverage, plus honest failure and abstention analysis.
5. Reproducible artifacts and a clear separation between mathematical guarantees, empirical semantic reliability, and unavailable annotations.

For an ML venue, the generalizable inference/control method and empirical evidence need to carry the paper. Merely wrapping LLM extraction in a database is unlikely to distinguish it from the cited work. Do not add a learned component solely for venue branding; a justified algorithm with strong experiments is preferable to unnecessary training. If the main result is a useful database execution system rather than a general inference contribution, position the work accordingly instead of overstating its ML novelty.

The first practical investment should be **an equally exhaustive flat baseline and a small uncertainty evaluator**, not a larger collection of agents. These directly test whether the proposed contribution is necessary. If the baseline eliminates the observed gap, report that finding and revise the research claim before spending another large model budget.

## 12. Evidence and scope of this document

- Local basis: [methodology](03-methodology.md), [results](04-results.md), [discussion](05-discussion.md), [evidence inventory](evidence-inventory.md), [claim audit](claim-audit.md), and [missing evidence](missing-evidence.md).
- Implementation basis: the linked source files, [architecture](../docs/architecture.md), [prompt policy](../docs/prompt-writing.md), and [Slurm runbook](../docs/runbook-slurm.md).
- Checkout inspected: root `645c8b0e2a11e99c25114900366902d025de713f`; `llm-setup` `07762fe8fec53d2f5a4c58277934b9fc98be8f25`. These are writing-time revisions, not replacements for historical campaign revisions.
- External sources are linked beside the claims they support. The proposed algorithm, hypotheses, metrics and gates are recommendations, not results from those sources or completed repository functionality.
- Only this Markdown proposal was created for this task. No production code, models, datasets, gold labels, experimental results, running services or remote branches were changed.
