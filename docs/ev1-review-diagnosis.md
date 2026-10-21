# EV1 review diagnosis and handoff for Claude

Date: 21 October 2026. Scope: proposal decisions, synthetic fidelity, exclusions, evaluation validity, and prompt design. This is a diagnosis and implementation handoff. Product code, existing prompts, research decisions, and completed run outputs were not changed by this review.

The user requested atomic prompts with defined inputs and outputs, examples, workflow composition, and a separate model verifier. [Prompt writing and verification](prompt-writing.md) records that policy. Two additional research notes cover [extraction methods](research/ev1-extraction-methods.md) and [evaluation methods](research/ev1-evaluation-methods.md).

## What was executed

The diagnostic harness uses the real engine, freeze logic, regex matcher, and fidelity checker. Model calls are replaced with scripted replies for deterministic replays. It also replays a real rejected draft recovered from the live model cache. The saved build summaries describe prior live runs; these are distinct evidence sources.

```bash
PYDANTIC_AI_NO_BANNER=1 PYTHONPATH=. .venv/bin/python tests/EV1/diagnostics/review_repro.py --repeat 2 --output tests/EV1/diagnostics/review_repro.json
```

Both repetitions produced identical results. The initial pair took 4.92 seconds after imports and the repeat in the evidence branch took 4.88 seconds; cold imports on Ceph add startup time. Exit 1 means the harness found the recorded problems; this is an intentional diagnostic artifact outside the default test suite, not a newly failing product regression test. [Raw outputs](../tests/EV1/diagnostics/review_repro.json), [input hashes](../tests/EV1/diagnostics/inputs.json), and [reproduction source](../tests/EV1/diagnostics/review_repro.py) are available for readers who cannot execute it.

No fresh GPU calls were made for this diagnosis. The proposed three-model pilot below remains NOT RUN following the user's instruction to leave implementation to Claude. The offline tests establish engine behavior and failure mechanisms; they do not measure current live model reliability.

## Measured findings and proposed repairs

| Priority | Observed behavior | Engineering cause and recommended change |
| --- | --- | --- |
| P0 | A known-synonym paper is skipped; the semantic screen receives zero calls. Adding only `retrieve-then-read` to the terms makes it reach the screen. | The keyword screen's negative result stops the cascade. The model rationale claiming the LLM can rescue omitted synonyms is false under this execution policy. Compile screening aliases from the approved frame, gate synonym coverage when hard rejection is enabled, and define an explicit unknown/escalate policy for an inconclusive keyword result. Measure recall and extra cost before selecting the policy. |
| P0 | The proposed protocol accepts measurements 1.75 and 0.6 from text reporting 175% and 60% factual accuracy; the handwritten protocol rejects 1.75. | The live frame sets factual_accuracy `fraction: false`; drafting consequently omits its [0,1] bound. Give metric definitions explicit unit, scale, domain, and conversion semantics. Generate validation bounds from those definitions. Add domain-consistency checks; prompt wording alone cannot enforce this invariant. |
| P1 | Changing `critic.json` after cards are generated still allows freeze. | Freeze verifies draft hashes but does not compare `cards.critic_sha256` with the current critic's hash. Check this dependency before applying decisions. Preserve the changed critic and require regenerated cards when the dependency changed. This is an audit-trail defect, not a request for human approval. |
| P1 | `RAG (no retrieval)` produces both rag and closed_book mentions. | Separate substring matches are treated as roles without resolving negation inside the condition's label. Resolve a full condition span with its local qualifiers, abstain on unresolved conflicts, and test ablations, punctuation, tables, and multiple genuine conditions. The regex research note evaluates alternatives. |
| P1 | The blind verifier accepts a response with all correct condition/value pairs but every metric and dataset deliberately wrong. | `blind_check.matches` uses only condition and value, even though the reply schema includes metric and dataset. Compare the complete tuple, with documented aliases and units, and account explicitly for allowed relative values and decoys. This finding concerns verifier coverage; no generated paper was silently relabeled. |
| P1 | Freeze succeeds with `terms_cover_synonyms: false` and all eight decisions attributed to the model. Correcting the screen decision makes all final deterministic checks pass. | Current freeze policy deliberately gates parsing and regex enum compatibility, not every critic check. Classify findings as blocking, advisory, or explicitly waived. Make screening coverage blocking for a hard-negative prefilter. Record review status separately from frozen status; the current acceptance of model defaults is documented behavior. |
| P2 | FActScore matches patterns for both factscore and factual_accuracy. Reversing the list changes the emitted canonical. | Longest-match then rule-order precedence is deterministic, but inherited and added aliases compete. Use an approved metric registry with explicit aliases and precedence; check cross-canonical collisions on examples. This probe proves sensitivity to rule order, not random behavior or an incorrect output on every input. |
| P2 | Exhaustive locate returns the whole document, identically when top_k and chunk_chars change. | The model rationale describes selecting a few relevant chunks, but those parameters are ignored for exhaustive mode. Use strategy-specific parameter schemas and feed operational descriptions generated from the same definitions into the cards prompt. Whole-document coverage is correct for exhaustive mode. |
| P1 | Reordering an otherwise equivalent result table from System/Accuracy/Dataset to Dataset/System/Accuracy makes both measurements disappear. | The table code finds a dataset column but assumes the first cell identifies the condition or metric. Resolve semantic header roles and preserve table structure; the extraction research artifact contains exact inputs and positive controls. |
| P2 | Explicit `75 out of 100` and `60 out of 100` accuracy sentences yield zero measurements. | This numeric representation is outside the current prose parser's coverage. Add a bounded numerator/denominator representation and deterministic arithmetic with controls for years, sample sizes, deltas, and zero denominators. This is a coverage finding, not evidence of fabricated values. |

The first principles behind these repairs are explicit contracts, consistent units, source-backed facts, dependencies checked at boundaries, and acceptance criteria independent of a model's persuasive explanation. Early filtering is irreversible: later stages cannot recover data they never receive.

## Step 10: the exact wording failure is now reproducible

The earlier note that the failed draft was unavailable was wrong. The cache retained it. It is now copied as [step10-final-draft.md](../tests/EV1/diagnostics/step10-final-draft.md), with its source cache key and input hashes recorded.

The failing sentence is:

> The variant that reads retrieved evidence first yields 662 out of 1,000 answers judged factually correct.

The paraphrased plan requires the exact metric description `fraction of answers judged factually correct` in the same sentence as the measurement. The count expression communicates the quantity to a human but does not contain that exact phrase. Replaying the saved output produces precisely `S002.m2: its sentence names metrics [], not only S002.k1` and no other deterministic failure.

Changing only that sentence to the following makes all deterministic checks pass:

> The variant that reads retrieved evidence first has a fraction of answers judged factually correct of 662 out of 1,000.

This is a controlled repair of a captured draft, not a newly accepted live variant. The independent live verifier was not run on this repair. The original failed Step 10 remains failed.

Claude should generate atomic Results statements from typed facts, verify each against the full fact tuple, then compose the paper around accepted statements and run whole-paper checks. The composition stage must preserve the difficulty level, naturalness, and absence of extra results or claims. Constrained regions and approved surface forms can reduce fragile whole-paper repairs without turning every level into an easy explicit template. Evaluate any permitted alternative wording as a versioned contract change.

The two last live attempts returned identical drafts despite feedback. Their repeated failure is runtime evidence. Their exact causal explanation cannot be recovered from output alone; retain prompts and effective settings with future attempts rather than assuming a changed seed guarantees a correction.

## Exclusions and human review: facts that code inspection cannot supply

The live main build requested 20 studies and retained 11; the template main corpus has 20. Individual levels passed more often: explicit 19/20, paraphrased 19/20, distributed 14/20, complex 17/20, contradictory 19/20. A study failing one level is intentionally excluded everywhere to preserve a shared study set. The build's zero exit status reports a completed partial build.

| Counted ground-truth directions | Before exclusion | Retained |
| --- | ---: | ---: |
| Main: supports / neutral / contradicts | 12 / 4 / 4 | 5 / 3 / 3 |
| Knob: supports / neutral / contradicts | 12 / 3 / 3 | 5 / 2 / 2 |

The knob build has 24 records and retains 11; the counted-direction totals differ because duplicate, missing, and irrelevant records are not all counted studies. The observed main supporting share changes from 60% to about 45.5%. This demonstrates selection changes the evaluated distribution; it does not prove a population effect from such a small set.

Keep the shared-set invariant. Report generation success and downstream accuracy separately, retain every exclusion, and compare template versus LLM rendering on matched study ids. Add a declared retention requirement and a fixed failure-handling policy. Pilot every level before scaling. Avoid repeated selection of favorable regenerated corpora or silent replacement of unsuccessful runs.

The prescribed sample command selected all 11 retained mixed papers, not 30: sampling clamps to available papers. The live CSV contains 342 placement rows and zero completed three-check reviews. A generated sheet and a completed human review are different outcomes. Human checks should include numbers, association, meaning, extra claims outside placements, and hard negative cases. Add rejected attempts to a separate diagnostic audit and preserve their status; they are not accepted benchmark cases.

## Research decisions that remain unresolved

The eight model defaults are proposals. The live frame's comparator definition does not establish the same model with retrieval switched off, and the current condition schema does not identify matched checkpoints. Decide whether the study estimates a retrieval effect under matched systems or describes comparisons between arbitrary RAG and non-retrieval systems. If matched systems are required, extract and check those matching fields.

Generic accuracy, factual accuracy, hallucination rate, and FActScore require explicit operational definitions. The engine chooses the first usable metric pair in priority order and a usable dataset according to its pairing rule; this policy should be approved and tested for sensitivity. A larger list of metrics is not automatically a stronger definition of factuality.

`min_effect: 0.01` is a neutral band on normalized values. It is one percentage point, not statistical significance, a p-value, or a confidence interval. The model rationale describing a standard significance threshold is unsupported. The any-evidence label table is a declared decision rule over counts; it supplies no quality weighting or uncertainty about the substantive research claim. Fix explanations and evaluate rule sensitivity before making scientific claims.

The gaps strategy stops once required evidence is present. Presence and schema validity do not guarantee correct or complete extraction, so the rationale promising no coverage loss requires evidence from paired all-versus-gaps experiments. Human policy choices remain distinct from model recommendations or majority agreement.

Generator truth and engine synthesis share `evidence/rules.py`. This is good for consistency but does not independently validate those rules. Add separately specified reference cases and human gold. Independent blind re-extraction is also a fallible model measurement: evaluate its false accepts and false rejects on adjudicated cases.

The evaluation research replay confirmed that current paper-level and paired bootstrap calculations reproduce the saved intervals. The saved mixed RAG baseline answers six of eleven retained papers correctly and abstains on five; reporting only answered-case accuracy would hide those five. All six difficulty views reuse eleven parent studies, so pooling their 66 renderings as independent observations would overstate sample size. The research note's clustering demonstration is an illustrative simulation, not a recomputed EV1 interval. It also reproduces two metric-boundary issues: a broad citation overlapping only a condition label is counted as traced without entailment checking, and an empty malformed gold fixture can yield `label_correct: true` from `None == None`. Each is classified with its scope and controls in the research note.

The template counterfactual was created after the first engine pass. Recovery targeted only the failed LLM variant path, so template scores were unavailable to the shift step. The recovery path also omitted the output suffix `-contradicts`; even a successful default variant would not be found at that constructed path. Use returned artifact paths or one manifest to drive corpus → engine → score → shift. Propagate child failures instead of treating printed `FAIL` lines as successful stage completion.

## Proposed generation and verification workflow — NOT RUN

Use orch-model to generate one atomic output at a time. Use sub-model-1 to verify against the task contract and source; sub-model-2 can run an independent second check. For blind fact extraction, withhold the private rendering plan and compare returned facts in code. For reviewing a recommendation, show the candidate and its source requirements but withhold the generator's rationale. Record both verifier answers and escalate disagreement into a bounded repair or human review.

Both sub-model aliases serve the same model family and weights, so parallel agreement is not independent scientific validation. Different prompts or sampling draws do not remove that correlation. Calibrate verifier errors against human adjudication and include seeded wrong-number, wrong-role, wrong-metric, wrong-dataset, and unsupported-claim cases.

Start with the recorded failure cases and a small set of fresh held-out cases. Compare the original prompt, an atomic prompt with examples, and atomic generation plus verification under the same call/token budget. Record full-tuple correctness, abstentions, repair rate, false acceptance, token use, and latency. Do not use model agreement alone as the pass criterion. Archive prompt/schema hashes, model identities, settings, each attempt, and evidence quotes.

## DSPy: suitable after the contracts and metrics are fixed

DSPy can optimize instructions and examples against a supplied metric. MIPROv2 searches instructions and demonstrations; GEPA can consume textual feedback on failed outputs. These make a reasonable controlled prompt-development experiment once the deterministic contract is sound. [MIPROv2 documentation](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/api/optimizers/MIPROv2.md), [GEPA implementation and feedback contract](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/gepa/gepa.py).

The existing LiteLLM endpoint is compatible in principle with DSPy's documented OpenAI-compatible endpoint interface. The adapter would use `openai/orch-model`, the configured base URL, and the API key from the environment. Preserve this repository's model identities, prompt hashes, redacted errors, and provenance when adding an adapter; compatibility has not been exercised here. [DSPy language model documentation](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/learn/programming/language_models.md).

An initial pilot should optimize one bounded task, such as condition classification or full-tuple extraction, after establishing a plain few-shot baseline. Test GEPA when the validator produces useful textual failure feedback; MIPROv2 provides a comparator for instruction/example search. Pin the chosen dependency version in an isolated experiment and cap calls and concurrency. No DSPy dependency was installed and no optimizer was run during this review.

Keep train, development, and untouched test sets separate, grouped by complete study family across renderings, duplicates, and counterfactuals. DSPy's own guidance warns that prompt optimization can overfit small datasets. The 11 surviving studies are a diagnostic set, not adequate evidence for broad optimization gains. Optimize against adjudicated tuple correctness and independent error checks; a JSON-valid output or a satisfied self-judge is insufficient. [DSPy optimization guidance](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/learn/optimization/overview.md).

## Implementation order for Claude

1. Fix metric domain consistency and the critic→cards freshness check; lock the observed failures into focused regressions.
2. Resolve screening and role ambiguity with executable invariants and the extraction research recommendations. Make the rationale reflect actual execution.
3. Check full tuples in the blind verifier and separate proposal state from human review state.
4. Refactor only the affected prompts into small typed stages with examples and bounded repair. Run the proposed live writer/verifier experiment.
5. Establish matched evaluation sets, independent human gold, appropriate sampling units and uncertainty, external validation, and controlled ablations before scaling or optimizing prompts.
6. Consider the isolated DSPy pilot after those metrics and evaluation splits are fixed. Preserve the original EV1 results and record new experiments separately.

The research notes refine these recommendations. Strong venues require a clear research contribution and credible evidence beyond engineering fixes; publication cannot be inferred from a repaired pipeline or this diagnostic run.
