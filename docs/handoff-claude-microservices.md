# Hand-off: split the general evidence system into services, review, then a Codex runbook

For: a new Claude Code session in this repo. Read this whole file, then CLAUDE.md, AGENTS.md and
`docs/prompt-writing.md`. Follow CLAUDE.md in every reply to Aditya (short, plain words, one next action).

## Where things stand (3 Nov 2026)

- `main` holds the whole general evidence system (plan `docs/superpowers/plans/2026-11-03-general-system-parallel.md`,
  spec `docs/superpowers/specs/2026-11-02-question-planning-design.md`). Every task passed its own review. The full
  suite passed on the last integration commit: 2234 passed, 22 skipped. Two files run only on Linux:
  `evaluation/tests/test_agentic_agent.py` and `test_runner.py`.
- Build ledger with every ruling and every deferred minor:
  `.superpowers/sdd/2026-11-03-general-system-parallel/progress.md` (git-ignored, in the main checkout). Task reports
  and reviews are in the same folder.
- A final whole-branch review was started; its result is `final-review.md` in that folder. If it is not there yet, ask
  Aditya whether to wait or to run the review again (base `9e13f2a`, head `506dc6f`).
- `llm-setup` in the main checkout has Aditya's own uncommitted change. Never touch it.
- The worktrees `../thesis-gen-*` are finished build copies. Remove them only if Aditya says so.

## Step 1: final-review fixes

If `final-review.md` lists Critical or Important findings, fix them on a branch before anything else. Use
subagent-driven development: one implementer, then a scoped re-review. Merge into main only when the full suite is
green. These gaps are already known:

1. Plan runs have no "reasoning off" switch. The runbook's off row points `EV_ONTOLOGY_DIR` at an empty folder, but
   that still loads the CS fallback ontology and the QUDT subset, so the on/off comparison is not real.
2. Nothing builds `<set>/tune_examples.json`, so the three real-paper steps (recheck, map_experiments,
   claims.read_claim) cannot be tuned. The format is in the `evidence/steps/tune.py` docstring.
3. There is no chaining question and no builds-on corpus, so `evaluate links` cannot run.
4. `planner_query` is untuned, because only a weak stand-in score exists.
5. Five vitest tests in `webapp/web` failed on main before Wave 2. Find out why.

## Step 2: split into services ("as many as makes sense", Aditya)

Use the brainstorming skill first. This is a design change, so Aditya approves the design before any code. Start
from the seams that already exist:

- **Model gateway and recorder:** `modelcall/`, `evidence/calls.py`, `modelcall/dspy_lm.py`.
- **Planner:** `evidence/planner/`, `webapp/evplan.py`.
- **Words:** `evidence/words/`, `evidence/extractors/recheck.py`.
- **Ontology:** `evidence/ontology/`, `evidence/reasoner.py`.
- **Paper intake:** `evidence/arxiv.py`, `evidence/sources/`, `evidence/tables.py`, `evidence/experiments.py`.
- **Extraction engine:** `evidence/engine.py`, `evidence/planrun.py`, `evidence/stages.py`. Stages are the plug-in
  points.
- **Claims and links:** `evidence/claims.py`, `evidence/openalex.py`.
- **Records graph and SPARQL answers:** `evidence/kg/`.
- **Evaluation:** `evaluation/` (wholerun, baselines, offtemplate, leak, tune).
- **Web app:** `webapp/`, which serves as the front door to the other services.

Hard rules. The design must keep every one of them:

- Replay stays byte-identical, for old protocol runs (golden fixture) and for plan runs. A replay makes no model call
  and no network call.
- Every LLM call goes through the run's recorder. A service never calls a model provider directly.
- Everything must still run inside one Slurm job, with no Kubernetes. So each service needs an in-process mode as well
  as an HTTP mode, and the same tests run in both.
- Tests use no network and no real models. Do not add sentence transformers, embeddings or a vision model.
- One model for everything (`orch-model`), except that the word list and the paper writer stay different families.

Ask Aditya two questions in plain words before the plan:

- How far should the split go: separate packages only, HTTP services, or containers?
- Is this for the thesis or for a product? His supervisor Tim asked for "a complete vertical slice" (see the `/tim`
  skill), so a deep split may count as scope creep.

Then write the spec and a plan (writing-plans), and build with subagent-driven development: parallel worktrees where
files don't overlap, a review per task, and one final review on the most capable model.

## Step 3: review the whole result

Run a whole-branch review of the split against the hard rules above. Run the full suite in both modes. Re-check the
golden replay. Merge into main only when it is green. Aditya has allowed merges into main, but pushing to GitHub is his
call.

## Step 4: Codex hand-off

Update `docs/runbook-general-system.md` for the new layout: how to start the services in one Slurm job, plus a
health check per service. Every command must be dry-run locally on the fixtures. Then give Aditya a short message to
paste to Codex that names the runbook and the branch.
