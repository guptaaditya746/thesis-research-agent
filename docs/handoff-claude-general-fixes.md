# Handoff: fix what the general-system Slurm run found, then merge to main

Written 4 Nov 2026 for a fresh Claude session. Aditya wants one session to work through everything the Codex run on
`codex/general-system-run` found (limitations, bugs, improvement ideas), fix what is possible, and finish with one
merge into local `main`. After that, Codex does new datasets and small improvements.

## Rules (read first)

- `CLAUDE.md` (how to talk to Aditya: short, plain, one next action) and `AGENTS.md`. Any prompt change follows
  `docs/prompt-writing.md`: keep the failing example, compare old and new prompt on the same cases, version the prompt.
- Never touch the uncommitted `llm-setup` submodule change in this checkout. Pushing is Aditya's call. Merging into
  local `main` is authorised.
- Never change gold labels, held-out splits, source data or score definitions to make a number look better. If a
  score's meaning must change, record a ruling (what, why, cost if wrong) and say so in the report.
- Keep old runs readable: replay of recorded runs must keep working or the break must be explicit and versioned.
- Work in a worktree branched from `origin/codex/general-system-run`, with a plan and ledger
  (superpowers:writing-plans, then superpowers:subagent-driven-development). Tests: `uv run pytest` on Windows; the
  11 agent test files that import POSIX signals cannot run here (Codex runs them on Linux); `agent/tests/test_prompts.py`
  has 2 errors on main already.

## What the branch holds

- Code beyond main (16 files, about 380 lines): plain-text DSPy replies (`modelcall/call.py` `PlainTextReply`,
  `evidence/stages.py`), SOFC-Exp and MeasEval converters (`evaluation/realpapers/convert_*.py`), the `$metric` fix
  (`fix/query-params`, merged in), and a runtime shim mapping saved `kg:dataset` to `ev:setting_dataset`
  (`evidence/kg/query.py`, commit b713dea8).
- Reports: `reports/general/` — read `decisions.md`, `failures.md`, `architecture-and-artifact-review.md`,
  `improvement-review.md`, `converter-independent-review.md`, `status-so-far.md` (older), and the score files under
  `scores/full/scilead`, `scores/fixed/scirex`, `scores/offtemplate`, `scores/synthetic/*`, `scores/oracle/*`.
- About 7,800 run files under `reports/general/runs/`. Runbook §8: run folders go to a results branch, never `main`.
  Merge code and the small reports into main; leave `reports/general/runs/` (and the per-run `calls/`) out.

## Results so far (for orientation; do not quote as final)

| Set | Engine | RAG | Note |
|---|---|---|---|
| SciLead, 22 q, reasoning on / off | 0.136 / 0.045 | 0.364 global, 0.318 per paper | engine loses 5-7, wins 0-1; split says "synthesis error" 19 of 22 |
| SciREX, 15 q | 0.033 (11 of 15 unscored) | 0.047 / 0.071 | not a usable result yet |
| Off-template, 12 q | match rate 0.1, fresh share 0.4 | - | 2 not run |
| Synthetic (8 corpora) | A F1 about 0.82-0.85, B 1.0, C direction 1.0 | C 0.85-0.90 | engine strong on its own synthetic data |
| Leak test | failed to score | - | |
| Claim reading | 0.975 (40/40) | - | after the plain-text fix |

## Work list

Order: correctness first (a wrong score is worse than a missing one), then failures that stop a check from running,
then cost and robustness. Each item names where the evidence is. Verify each claim before fixing; the Codex line
numbers may be off.

**A. Scores that are wrong or unscored**

1. Rank questions are scored inconsistently: the headline uses top-1 while the answer-key split compares the whole
   ranking, and the headline reads the first answer line while the split may pick another
   (`architecture-and-artifact-review.md`). So the 19 "synthesis error" labels are not established. Make headline and
   split judge the same line and the same thing; rescore from the existing runs (no model calls).
2. scilead-05 and -06: their plans use `$metric` but have no measures, so the split fails. The planner check
   (`check_plan`) should refuse a line that needs a measure when the plan has none, and the run should say so clearly.
3. SciREX: 11 of 15 engine questions unscored even after the `kg:dataset` shim (`failures.md`, `scores/fixed/scirex`).
   Find out why (empty predictions? key mapping? 77 of 270 relations have no document). Also decide whether the shim
   stays: the root fix is at planning (the query must use predicates the graph emits; a check could refuse unknown
   predicates); keep the shim only for old saved plans.
4. Dataset names: the question says "ICSI Meeting Recorder Dialog Act Corpus (MRDA)", the graph stores "mrda";
   "Ontonotes v5 - English" vs "ontonote 5.0". In code, also match the bracketed short form; for loose variants let the
   word-list step supply aliases (a prompt change: follow docs/prompt-writing.md).
5. The answer to a "which paper is best" question says yes/no instead of naming the paper (scilead-07). The answer text
   for rank lines should name the top thing and its paper.

**B. Checks that did not run**

6. Leak test: `evaluate leak` rejects evidence type `experiment` (not registered with the validator). Fix the type
   contract so the leak split scores.
7. Off-template q06 and q10: treatment and control both resolve to role `other`, protocol validation fails. q05 failed
   at run time with a SPARQL syntax error that the plan check should have caught. Also look at why match rate is 0.1.
8. Synthetic engine steps for `paraphrased` and `complex` exited 2 (twice, `failures.md`); reports exist, cause unknown
   (logs not on the branch). Reproduce locally on `tests/EV2/corpora`.
9. Offline suite on Linux: 4 failures — `test_old_protocol_lock_unchanged` (extractor fingerprint changed because it
   hashes `modelcall/call.py`), two `test_effect_scores_unchanged` golden token counts, and the webapp run-group name
   test. Decide each with a ruling (versioned compatibility vs updated fixture), and get the suite green.

**C. Cost and robustness (improvement-review.md)**

10. Every SciLead question had a context-window failure: the experiment-map step sends whole papers (one request was
    327,338 characters) and retries the same over-limit request. Screen papers before mapping (scilead-07 mapped 31
    papers, 27 later screened out), check size before calling, and treat over-limit as permanent (no retry).
11. The extraction prompt has no total size cap (chunk limit plus prior context items). Add a total budget.
12. The JSONL cache is parsed whole per run (133 MB and 93 MB caches) and its lock is per thread, not per process.
    Index it or give it one owner; at least make cross-process writing safe.
13. OpenAlex 429s: back off and retry instead of marking links outside the set.

**D. Small leftovers**

14. Runbooks still say llm-setup `4c8ccbf`; it is `b962edd` (`docs/runbook-question-first.md`, `docs/slurm-evidence-runbook.md`).
15. Converters: keep them; SOFC frame scoring stays on hold (352 of 1,032 frames have repeated slots); MeasEval scores
    the scalar subset only and must be labelled so.

**Not in scope:** the services split (the review says stabilise replay and cache ownership first), storage migration,
new datasets (Codex later), web app display of the new scores (ask Aditya).

## Finish

- Final whole-branch review, then merge into local `main` (code + small reports, not run folders). Do not push.
- Update `docs/runbook-general-system.md` with a short Codex section: rescore what needs no model calls, rerun what the
  fixes changed (SciREX, off-template, leak, the two synthetic corpora), and the robustness additions Aditya asked for
  (all kept questions, a stronger RAG setting, 3 repeats) if they fit.
- Tell Aditya in under 8 lines what changed, what is still open, and one next action.
