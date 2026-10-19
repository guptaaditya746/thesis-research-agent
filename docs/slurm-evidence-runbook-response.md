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
- Fix the LLM renderer/fidelity mismatch and rerun the LLM corpus comparison before making claims about
  renderer differences or extractor performance on LLM-written papers.
- Diagnose the two RAG baseline failures and rerun those cases before comparing baseline results.
- The 337-paper, multi-question study remains future work; this run tested the synthetic benchmark only.

## Request for Claude's review

Please independently assess whether the runbook has been answered accurately and whether the conclusions
are appropriately limited to the data that passed fidelity. Identify the highest-priority next technical
step. Do not infer that `insufficient` means “no effect,” and do not change the frozen proposal or protocol
as part of this review.
