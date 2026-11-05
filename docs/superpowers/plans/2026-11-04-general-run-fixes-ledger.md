# General-run fixes ledger

Plan: `2026-11-04-general-run-fixes.md`. Handoff items 1-15 → task, what verification found (4 Nov, read-only, no
model calls), status.

| # | Item | Verified finding | Task | Status |
|---|---|---|---|---|
| 1 | Rank scoring | Confirmed both halves. Headline top-1 vs split full order; headline falls through to a later line (scilead-17, -27 lucky). **New:** key store spells metrics as the release ("F1"), plans use measure ids ("f1"), so metric-filtered lines always get an empty key answer → most "synthesis error" labels are artefacts. Line fix alone: on 0.136 → 0.045 (3/22 → 1/22), off 1/22 → 0/22. | 3 | done 10b0bc83 (rescore on Slurm: runbook 9.2) |
| 2 | `$metric` without measures | Confirmed (scilead-05/06; -19 via `$metrics`). `check_plan` never runs in the batch path. | 4 | done a941cf5c (check_plan + plan-runs exit 1; re-plan: 9.3) |
| 3 | SciREX 11/15 unscored | All 11 have **empty predictions**; gold mapping fine; 77 absent-doc relations play no part. Causes: task wording (003, 005, 016, 018), bracket form (011), experiments carry no task (006, 007, 010, 015, 017, 019 — need re-extraction). `kg:dataset` came from QuerySig filling `$list_field`. | 4, 6 | partly: plan check refuses kg:dataset (a941cf5c), names v2 (2a72c7b9); 6 questions need re-extraction (task not on experiments) |
| 4 | Dataset names | MRDA/OntoNotes are SciLead (-27, -10). Word list already holds exact aliases ("MRDA", "OntoNotes 5.0") — code-only fix, no prompt change. | 6 | done 2a72c7b9 (plan_version v2, no prompt change) |
| 5 | Rank answer yes/no | Confirmed, `lines.py:51-55`; rows carry arXiv id only (no title). | 5 | done 2a72c7b9 (v2 answer text) |
| 6 | Leak `experiment` unregistered | Reproduced: `evaluate leak` never imports `evidence.records`. After the fix recall may stay low: scorer skips conditions nested in experiment records (hypothesis, q01). | 7 | type error fixed d7f6902f; nested-condition scoring left open (hypothesis, runbook 9.4) |
| 7 | Off-template | q06/q10: plan names only measures → both sides `other`. q05: unplanned empty line; scorer runs `""`. Match 0.1 mostly plumbing (key store side roles vs plan side ids; `same_rows` too strict; denominators skip q06/q10), partly planner (generic nouns as things). | 4, 8 | q06/q10 protocol, q05 check, scoring plumbing done (a941cf5c, 17adcffb, 2a72c7b9); match 1/10 to 2/12 on recorded runs; rest is planner (prompt work) |
| 8 | Synthetic exit 2 | Deliberate "engine errors" exit: 3 `llm_measurement` calls with invalid JSON (whitespace loop to max_tokens; quote loop), labelled `model_call` like an outage. Second exit 2 likely `RunDirExists` on rerun (hypothesis). | 9 | exit 2 fixed (bad replies warn) 2a72c7b9; whitespace loop itself open (vLLM option, runbook 9.4) |
| 9 | Offline suite | Lock test: new regression (call.py in fingerprint) → versioned compat. Golden tests: machine-dependent (reads cluster cache path) → fix test. evjobs: stale since 750cd25e → fix test. Golden + evjobs also fail on main on Linux. | 1, 2 | done a11fa88d: lock fixture v1/v2 + CodeChanged (explicit break, no alias table); golden + evjobs fixtures |
| 10 | Map before screen / over-limit | Map runs before screen; over-limit repeats come from `--retry-errors` (attempt 16 seen). Classifier exists in `gold/calls.py`. | 10 | done 2a72c7b9 (v2: map after screen, size check) + permanent errors not retried |
| 11 | Extraction prompt size | All context items added on top of `chunk_chars`. | 10 | deferred: needs llm.py/llm_schema.py edits, which change extractor ids again; do with the next extractor version bump |
| 12 | JSONL cache | Parsed whole per construction; thread lock only; `filelock` already a dependency. | 11 | done 8d5b44ab (filelock + O_APPEND + catch-up; no index) |
| 13 | OpenAlex 429 | Any HTTP error fails the URL for the run; breaker after 3. | 12 | done 225ae3bb |
| 14 | Runbooks llm-setup | `4c8ccbf` → `b962edd` (child commit: distinct replica ports). | 0 | done 79c966eb |
| 15 | Converters | Keep; SOFC frames on hold; MeasEval scalar subset label. | 13 | done: MeasEval score names the subset and excluded count; SOFC frames stay on hold |

Baseline suite on Windows before changes: 1 failed (old lock test), 2322 passed, 22 skipped, 2 POSIX-only files not loadable.
Process note: Aditya stopped the TDD + subagent loop after Task 1 started (too expensive); the fixes were made inline.
