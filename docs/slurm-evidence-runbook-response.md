# Response to the Slurm evidence runbook

This is a review brief for the live pass described in [`slurm-evidence-runbook.md`](slurm-evidence-runbook.md).
The run was on Slurm job 7488, node `gammaweb08`, on 18–19 Oct 2026. The full step-by-step record and
numbers are in [`tests/RESULTS.md`](../tests/RESULTS.md) under EV1; copied artifacts are in `tests/EV1/`,
and the full Ceph artifacts and `failures.md` are under `$EV`.

## Result

The pass is **partial**. The template-rendered synthetic corpora produced usable papers and known-answer
results. With the full cascade, the system returned the expected corpus label on all seven template sets
run. Paper-level direction accuracy was lower on some styles (80% distributed, 75% complex). With the
`gaps` strategy, the expected label was correct on six of seven template sets; the paraphrased set was
missed. This supports the pipeline on these controlled examples, but does not establish accuracy on real
papers.

The LLM-rendered corpus experiment did not produce a comparable dataset: the main set retained 1/20 papers
for explicit and 0/20 for each other level; the knobbed set retained 2–3/24 per level. The fidelity checks
rejected generated attempts because required numeric strings were ambiguous or repeated. Empty corpora
therefore yield `insufficient`; that label is not evidence for or against RAG. No valid mixed corpus was
available for the planned counterfactual variant or shift analysis.

Saved replay outputs matched their source hashes and event chains on 42/42 engine runs. Two RAG baseline
runs failed with `RuntimeError: Event loop is closed`; the agent baseline completed, but its answers on the
empty LLM corpora were `insufficient`. No protocol, prompt, fidelity threshold, or scoring rule was changed
during this pass.

## Open items

- The user has not yet reviewed the eight frozen proposal cards. The proposal remains unchanged and its
  review is recorded as `NOT RUN (USER)` until that discussion happens.
- A hand review of generated LLM paper fidelity could not be done for the prescribed mixed sample because
  it contains zero accepted papers.
- Diagnose the LLM renderer/fidelity mismatch under the runbook's frozen-component rules; review and record
  any proposed change separately before rerunning the LLM corpus comparison.
- Diagnose the two RAG baseline failures and rerun those cases before comparing baseline results.
- The 337-paper, multi-question study remains future work; this run tested the synthetic benchmark only.

## Independent assessment for Claude

The recorded conclusions match the runbook's evidence and should remain bounded to this synthetic pass:

- The template corpora show that the pipeline can recover the planted labels for these generated examples:
  cascade was correct on 16/16 runs, while `gaps` was correct on 13/14. The missed paraphrased case means
  the funnel strategy is not uniformly reliable even on this benchmark.
- The LLM-rendered corpus results do not support a renderer comparison or a meaningful LLM-corpus extraction
  comparison. The main build retained 1/20 explicit studies and none in the other levels; the knob build
  retained only 2–3/24 per level. Most agentic runs consequently had no papers to extract. Their
  `insufficient` labels describe missing usable evidence in those inputs; they do not mean “no effect.”
- The replay checks establish integrity of the saved run records (42/42 engine replays and event chains), not
  correctness of extraction or answer quality. Likewise, the template label results do not establish
  performance on real research papers.
- The two missing RAG baseline outputs make those corpus comparisons incomplete. The agent baseline
  completed, but its `insufficient` results on the empty LLM inputs cannot be compared as evidence about
  system quality.
- The proposal flow completed and its protocol passed validation, but the eight cards remain unreviewed by
  the user. Fidelity hand review could not use the prescribed sample because the mixed LLM corpus has no
  accepted papers; shift analysis could not run without the planned counterfactual variant.

### Recommended next technical step

First reproduce and trace the LLM fidelity rejection from the saved attempt records in `fidelity.json`,
through the `required_strings` check, and identify whether the ambiguity comes from paper rendering, the
fidelity check's input, or the generated study data. The runbook explicitly freezes the renderer prompts,
fidelity checks, level definitions, and thresholds during this pass. Keep this diagnosis read-only; if it
shows one of those frozen components must change, record a proposed change for supervisor review and run it
as a separately approved experiment rather than revising EV1 results. Once an allowed fix is identified,
rebuild the LLM corpora and repeat the dependent engine, baseline, score, benchmark, and variant steps.

Then diagnose and rerun the two failed RAG baseline cases (`rag-llm-s1-mixed` and `rag-llm-k1-mixed`). This
is a separate repair because it does not explain the corpus fidelity failures. Do not make claims about
LLM-renderer performance, the planned shift, or real-paper accuracy until the relevant inputs and runs
exist.

## Request for Claude's review

Please independently assess whether the runbook has been answered accurately and whether the conclusions
are appropriately limited to the data that passed fidelity. Identify the highest-priority next technical
step. Do not infer that `insufficient` means “no effect,” and do not change the frozen proposal or protocol
as part of this review.
