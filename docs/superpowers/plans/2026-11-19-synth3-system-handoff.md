# synth3 system answers the questions (plan 4 of 5): handoff

Finished 19 Nov 2026 on branch `synth3-system` (from synth3-questions @ af1f43b1 to e8da1e8e). Not pushed or merged.

## State
- 17 tasks done, each reviewed. Tasks 9-16 ran in three parallel lanes (Aditya's "go"); lanes B (web API) and C
  (pages) were built in their own worktrees and merged back locally (48e4c44d, 61b47e3c); the API schema was
  regenerated after the join (da362db9). Worktrees and lane branches are removed.
- Final whole-branch review (0 critical, 4 important, 5 minor); one fix pass (14 commits, 21b0a30f..e8da1e8e); a
  re-check found every item addressed, no residuals.
- Tests after the fix pass: synth3 + evidence + webapp 1863 passed, 20 skipped (3 load-flaky tests pass alone);
  whole backend suite before it 3705 passed; frontend 191 tests, typecheck and lint clean.
- New commands: `synth3 system-plan`, `synth3 system-run`; `synth3 collect` reads plan runs. New page `/system`
  (boxes 1-5); `/plan` has a sub-question box and opens batch plans (`/plan?batch=<domain>/<qid>`).
- No plan, run or system answer exists yet. Nothing ran on the cluster.

## What it does, in one breath
`system-plan` has orch-model draft one plan per question (question + sub-questions); Aditya confirms each on /plan
(or runs with `--confirm-as-system`); `system-run` runs every confirmed plan on every folder as a recorded, replayable
plan run; a "written" question gets a short answer written by orch-model from the pulled facts and checked by code
(every sentence cites listed facts and copies its numbers from them); fixed kinds (effect, consistency, inventory,
best) are answered by code as plain-word lines; the answers are collected for plan 3's judge as system `system`,
blind (no system name, sub-question, protocol id or thing id in the answer text); the report says who confirmed the
plans and how many answers had facts left out.

## Judgement calls (from the ledger, with their cost if wrong)
- A plan runs only when a person confirmed it, unless `--confirm-as-system` (a separate copy in `plans/<d>/auto/`, the
  draft untouched; records and report say so) — cost: one flag.
- A written answer that fails its checks is asked again with a fresh key (try 1 and 2 at temperature 0.3, seed = try),
  then counts as empty; a failed model call is never scored and is rerun with retry. A retry reuses every paper's
  extraction and asks only the writer again (final-review fix) — cost: a few answers scored differently.
- Kind lines name things by the plan's first word-list name; a reason that would show an id is rebuilt with the
  name (Task 8 and final-review fixes) — cost: none.
- The writer sees the main question only, never sub-questions — cost: one input line.
- Plan files are written atomically (LF line endings, same bytes as the /plan page writes); a `--redo` drafts first
  and moves the old plan aside only after a good draft — cost: none.

## Small issues left for later (parked by the final review)
- Pulled facts reach judges A/B with the plan's thing ids in `fields.role` (as plan 3's engine records do): a design
  note, not a rule break.
- A crashed run restarts at writer try 0 (a few extra calls); a stale question file is read on each /plan view.
- `plan_domain` catches only model, value and runtime errors while drafting; another error type stops the loop.
- On a writer retry the protocol id (`plan-<sha>`) no longer equals the run's plan hash; nothing compares them today.
- UI polish: an unknown kind in a question file shows as "written"; Combine/Answer fact buttons only select.

## For Aditya, in order (the plan does not wait)
1. After his questions exist: on the cluster `uv run synth3 system-plan --domain medicine` (drafts one plan per
   question; nothing is confirmed).
2. Decide: review the plans yourself (open each on `/plan?batch=medicine/<qid>` or from `/system`, edit, confirm), or
   run with `--confirm-as-system` (the report then counts answers that ran on plans no person confirmed, as a
   limitation of spec §8).
3. On the cluster: `uv run synth3 system-run --domain medicine --workers N [--confirm-as-system]` (125 runs of 40
   papers, heavy). Run it again until it reports no failures; it keeps every complete good run.
4. Then plan 3's steps: `synth3 judge --domain medicine`, `judge-sample`, hand marks, `report`.
5. Click through `/system` once on one folder and `/plan` with sub-questions and a batch plan (never clicked in a
   browser with a real model); keep `$EV` outside the repo or git-ignored (runs copy quotes of renamed papers).
Repeat 1-4 for law, materials and RAG once their worlds are built.
Notes: (a) editing a question's kind asks for the system's answer again, never the baseline's; (b) a `best` question
is only as good as the plan's names for its things; (c) on the blind judge-test page a system answer can be told by
its form (sentences ending in `(S003, S010).`, or kind lines), as the baseline by its `[S003, ...]` marks;
(d) writer retries use temperature 0.3 (docs/prompt-writing.md: the same request at 0 is no repair) — say if you
prefer 0; (e) `data/synth3/plans/` is not git-ignored yet — your call.
