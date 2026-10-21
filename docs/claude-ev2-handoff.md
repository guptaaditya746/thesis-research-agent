# Claude handoff: EV2 generator and verifier failures

## Status and scope

The user requested that the current work be committed and pushed, with this
failure diagnosis, rather than continuing to change the implementation. Treat
the protected renderer and its new verifier as experimental work with known live
failures. Do not describe this branch as a completed reliability fix.

Branch: `evidence-ev2`, based on `origin/ev3/integration` (`a37099b`). The
`llm-setup` submodule is `fc842bc`. Worktree:
`/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/evidence-ev2`.
The user's original dirty checkout at `../thesis-research-agent` was not edited.
Read `AGENTS.md` and `docs/prompt-writing.md` before changing this workflow.

## What actually failed in the original pilot

The original EV2 pilot requested three study families, seed 1, all five levels,
using `sub-model-1` to generate and `sub-model-2` for blind verification.
Corpus metadata identifies both as
`Qwen/Qwen3-30B-A3B-Instruct-2507-FP8@5a5a776`; these aliases share weights.

All three families were excluded because at least one level failed. Per-level
passes: explicit 3/3, paraphrased 3/3, complex 3/3, distributed 1/3,
contradictory 0/3. Failures in the latter two were `required_strings`.

Replaying the saved model outputs exposed the exact violations:

- S001 distributed: 29.9, 21.4 and 47.2 occurred twice. The model put a table in
  Method, then repeated its measurements in Results prose. The contract requires
  a Results table with values nowhere else.
- S001 contradictory: those measurements occurred three times, in Abstract,
  the Results table, and Results prose. The draft also interpreted the findings
  despite instructions to preserve the supplied contradictory claim sentences.
- The repair attempts kept duplicating values. A clear prompt and feedback did
  not make this model reliably follow all layout and uniqueness constraints.
- Initial drafts also used numbered lists, whose markers triggered
  `added_numbers`; some of those cases passed after repair.

The validator was correct to reject the duplicated values. Do not relax
`required_strings`, uniqueness, or the difficulty-level checks to increase
retention. Two actual drafts and their original cache keys are committed under
`synth/tests/fixtures/pilot-repeated-values.json`.

The evidence supports an instruction-following failure on these inputs. It does
not establish that model size is the sole cause: no controlled comparison with a
stronger model was run.

## Changes made

An opt-in `--assembly protected` mode was added. The default remains freeform.
It is explicitly a hybrid generator:

- `synth/protected.py` assembles factual sections with the existing deterministic
  renderer, preserving tables, claims, decoys, labels and distributed spacing.
- The model writes Introduction and Discussion independently, using
  `synth/prompts/context-v1.txt` and bounded `ProseReply.text`. It sees the section
  and dataset, not measurements or effect labels.
- Digit, heading, table and added-effect-claim checks guard these passages.
  Rejected passages get bounded, local repairs, and failed attempts are saved.
- Final placements are recomputed and all existing deterministic fidelity checks
  run on the assembled text. Exhausted prose retries still exclude the family.
- The normal Results statement-generation stage is bypassed in this mode.
- Metadata records the assembly mode, prompt/schema hashes, source hash,
  identities and call settings. Variants inherit the recorded assembly mode.

This changes the corpus's text distribution. Higher retention of hybrid papers
does not show that freeform LLM generation or downstream extraction improved.
Keep its results separate from the frozen EV1 corpus and original pilot.

## Live attempts and outcomes

All attempts used the same three development study families and five levels.
The protected runs used concurrency 1. The original pilot used its original
configuration; this is not a controlled timing comparison.

| Corpus prefix | Workflow | Retained families | Important outcome |
| --- | --- | --- | --- |
| `rag-llm-pilot` | Original freeform plus original blind verifier | 0/3 | Distributed 1/3; contradictory 0/3 |
| `rag-llm-protected-pilot` | Protected assembly plus original blind verifier | 2/3 | All levels 3/3 except complex 2/3 |
| `rag-llm-protected-reading-pilot` | First source-reading verifier | 0/3 | Every complex paper failed because `see text` was emitted as a numeric measurement |
| `rag-llm-protected-final-pilot` | Numeric schema constraints and bounded source-reading repair | 1/3 | Explicit 2/3; complex 2/3; other levels 3/3 |

Full per-level selection data, identities and hashes are in
`tests/EV2/diagnostics/pilot-comparison.json`. Pilot corpora and fidelity records
are in `tests/EV2/pilot-corpora/`; live launch logs are in `tests/EV2/logs/`.
Intermediate implementations were edited during this session and are not
separate commits. Their generated metadata and recorded outputs preserve the
observations, but the final checkout alone does not reproduce each intermediate
workflow without a code change.

### Why the original blind verifier rejected the assembly-only complex paper

S002's main result states a value 6.7 percentage points **higher** than a
baseline of 33.5%. The model returned 26.8% (0.268), subtracting instead of
adding. The intended value is 40.2% (0.402). The metric is an
unsupported-answer rate: desirability appears to have influenced the numeric
direction. That explanation is a hypothesis; the incorrect value is observed.
The fidelity record reports missing `S002.m2 (value)` and an extra
`('RAG pipeline', 0.268)`.

### What the new blind verifier does

`synth/blind_reading.py` and `synth/prompts/blind-reading-v1.txt` ask for direct
source numbers/units and explicit relative comparisons with verbatim quotes.
Code anchors quotes, checks numeric tokens, normalizes percentages/counts and
computes signed percentage-point differences using Decimal. No plan or private
expected facts are given to this reader or its repair prompts. Its normalized
output is still checked against private truth by the existing `blind_check`.
Freeform mode retains its original blind-verification path.

This removes arithmetic from the model, but the larger extraction schema created
new instruction-following failures. Decimal unit tests are not evidence that
the model reliably fills this schema.

### Current unresolved failures: final pilot

1. **Explicit S003: invented relative comparisons and source quotes.** The paper
   states direct percentages. The model returns these correctly, then invents
   comparative sentences with 7.7, 9.3 and 8.2 percentage-point differences.
   Those sentences are not in the source. Quote anchoring rejects them. Bounded
   repairs continue returning the invented comparisons, so the final check is
   `model_call: not_found: the quote does not occur in the file`.
2. **Complex S001: wrong attribution / extra measurement.** The final fidelity
   record contains `blind_extra: extra [('retrieve-then-read model', 0.472)]`.
   A real numeric token can be anchored while assigned to the wrong condition.
   Inspect the saved reading and source table before choosing a correction.
3. **Intermediate schema failure:** the model represented a `see text` cell as
   `number: "see text"`, unit percent. Numeric schema constraints now reject
   that form; its earlier failed output is preserved for diagnosis.

The final source-reading verifier is a regression relative to the assembly-only
attempt (1/3 retained versus 2/3). It is experimental and must not silently
replace the working baseline. The final pilot's CLI exit was 0 despite excluding
two families: the default retention floor permits a nonempty corpus. Read
selection/fidelity, not just process success. Use `--min-retained` when enforcing
a quality gate.

Further implementation limits to inspect:

- Anchoring a numeric quote does not independently prove that every output field
  refers to its correct row, column and unit. The private-truth check catches
  measured errors on this synthetic development corpus.
- Generic `AnchorError` feedback names neither the offending reading nor quote,
  making a whole-reading repair harder for this model.
- `_blind` retries source/schema errors, but a normalized output that disagrees
  with private truth remains rejected. Do not reveal private answers to repair it.
- `PaperFidelity.attempts` tracks prose rounds; blind-reading repairs are in
  history. Do not interpret it as total model calls. Cached outputs include usage.
- Shared-weight writer/verifier agreement is correlated evidence.

## Validation performed

- Original Linux setup: 1,537 passed, 1 skipped, 1 warning in 2380.69 seconds.
- Final synth suite: **269 passed in 88.26 seconds**, including the new tests.
- New tests cover captured duplicate-value failures, all five assembled levels,
  final anchors, local prose repair, caching, exhausted attempts, independent
  rejection, signed arithmetic, source tokens, numeric schema and source repair.
- The first full synth run found stale example `corpus.json` code hashes. The
  examples were regenerated; their only tracked changes are source hashes.
- The final full suite passed. These are deterministic tests with scripted model
  replies; the live pilot still fails as described above.
- No stronger-model comparison, held-out live study families, optimizer, or
  external library experiment was run.

To rerun without overwriting these observations, choose a new corpus name:

```bash
"$EV/launch.sh" 1-protected-followup uv run synth build \
  --name rag-llm-protected-followup --seed 1 --studies 3 \
  --renderer llm --assembly protected --levels all \
  --model sub-model-1 --verify-model sub-model-2 --concurrency 1 \
  --min-retained 0.5 --out "$CORPORA" \
  --cache "$EV/cache/synth-protected.jsonl"
```

Use the runbook environment; do not commit it or print its secrets. The source
cache stays on Ceph. Selected verifier outputs, cache keys and usage are copied
to `tests/EV2/diagnostics/verifier-readings.json` for offline inspection.

## Original overnight EV2 work still outstanding

Setup and smoke checks completed. The existing 11-paper EV1 corpus was used for
two successful engine runs: cascade `all` and cascade `gaps` reject. Their full
folders are copied to `tests/EV2/ui-case/runs/`, with the original corpus under
`tests/EV2/ui-case/corpora/rag-llm-s1-mixed/`.

Not run yet: gaps escalate arm, RAG baseline, engine oracle, RAG oracle, scoring,
`compare-cascade`, and `compare-lexical`. There are no final EV2 comparison
numbers. Resume those sequentially via `launch.sh` on the unchanged EV1 corpus;
do not substitute this new hybrid pilot. The escalate protocol file also needs
to be created per runbook step 0.6 before that arm runs.

Ceph run root: `/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-ev2`.
The last observed Slurm allocation was job 7609 on gammaweb07; check it before
resuming. The doctor complained that existing listeners/GPU allocations were
unowned, while smoke checks and real model calls worked. This and transient
Slurm step socket retries are in `tests/EV2/failures.md` and launch logs.
Neither symptom explains the captured document-content failures.

The user confirmed that both the UI and pipeline HTML work. Leave the tunnels
alone. `tests/EV1/` and `main` were not changed by this work. Human fidelity
review and scientific acceptance remain outstanding.
