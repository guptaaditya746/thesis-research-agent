# General-run fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix what the Codex general-system Slurm run found (wrong or missing scores, checks that did not run, cost and
robustness), keep old runs replayable, and merge code plus small reports into local `main`.

**Architecture:** Scoring fixes live in `evaluation/` and `evidence/kg/truthgraph.py` and read only saved
`answer.json`/`plan.json`, so they rescore old runs with no model calls. Anything that changes what a *run* does
(name matching, map order, size checks) is behind a new `Settings` field that `evidence/replay.py:_settings` defaults
to the old behaviour when run.json lacks it. Edits to fingerprinted extractor sources go through one new compatibility
table (`evidence/compat.py`) that replay alone may use.

**Tech Stack:** Python 3.13, uv, pytest, pyoxigraph (SPARQL), DSPy, filelock 3.32.7 (already a dependency).

**Spec:** `docs/handoff-claude-general-fixes.md` (in the main checkout, untracked; copy into this worktree in Task 0),
plus the verification notes in the ledger `docs/superpowers/plans/2026-11-04-general-run-fixes-ledger.md`.

## Global Constraints

- Never touch the `llm-setup` submodule. Never push. Merging into local `main` is authorised.
- Never change gold labels, held-out splits, source data or score definitions to improve a number. A changed score
  meaning gets a ruling in `reports/general/decisions.md` (Chosen / Why / Undo, plus "Cost if wrong").
- Replay of recorded runs keeps working, or the break is explicit and versioned.
- Any prompt text change follows `docs/prompt-writing.md` (keep failing example, compare old/new on the same cases,
  version the prompt). This plan makes **no prompt text change**; planner guidance goes through validator messages.
- Tests: `uv run pytest <paths> -q -p no:cacheprovider`. On Windows, `evaluation/tests/test_agentic_agent.py`,
  `evaluation/tests/test_runner.py` and the agent tests importing POSIX signals cannot load; Codex runs them on Linux.
- No model calls in this session. Rescoring that needs `$EV/real` (SciLead release, SciREX `test.jsonl`) is Codex's.

## Review Focus

- An old saved plan that the new `check_plan` rules flag must still load and replay (rules are refusals for *new*
  plans only; `planrun.run` keeps calling `check_runnable` only).
- A run.json written before this branch (no `match`, no `budget` field) replays byte-identical to its record.
- A rank line whose metric is lower-is-better: answer text shows the real (un-negated) score.
- Two processes appending to one JSONL cache at once: no torn lines, each sees the other's entries on a miss.
- A literal with no word-list alias and no brackets renders exactly the same query as before.

---

### Task 0: Branch housekeeping

**Files:** Create `docs/handoff-claude-general-fixes.md` (copy from main checkout); already modified
`docs/runbook-question-first.md`, `docs/slurm-evidence-runbook.md` (llm-setup `4c8ccbf` → `b962edd`, item 14).

- [ ] Copy the handoff into the worktree; commit with the two runbook edits and this plan + ledger:
  `git commit -m "docs: general-run fix plan, handoff, llm-setup b962edd in runbooks"`.

### Task 1: Versioned extractor compatibility (item 9, lock test)

**Files:**
- Create: `evidence/compat.py`, `evidence/tests/test_compat.py`
- Modify: `evidence/calls.py:94-141` (replay lookup), `evidence/lockfile.py:22-50`, `evidence/replay.py:74-77`
- Fixtures: rename `evidence/tests/fixtures/locks/rag-factuality.lock.json` → `rag-factuality.v1.lock.json`; add
  `rag-factuality.v2.lock.json`; update `evidence/tests/test_plan.py:50-53`.

**Interfaces:**
- Produces: `compat.EQUIVALENT: dict[str, dict[str, tuple[str, str, str]]]` = `{extractor_name: {current_code_sha256:
  (old_code_sha256, old_commit, reason)}}`; `compat.aliases(extractor_id: str) -> list[str]` (old ids for a current id,
  same name/version/config); `compat.register(name, new_sha, old_sha, commit, reason)` for later tasks.
- Rule: aliases are tried **only** in `CallCache` replay mode, and only ids that the recorded run.json `extractors`
  lists. `run` and `reexec` never use them.

- [ ] Test `test_v1_lock_ids_resolve_through_compat`: every extractor id in the v1 fixture equals one of
  `compat.aliases(current_id)` for the matching current extractor; current ids differ from v1 ids.
- [ ] Test `test_compat_entry_is_proven`: for each entry, rebuild `old_code_sha256` from `git show <old_commit>:<file>`
  for every source file (skip with a clear message if git is unavailable) and assert it matches.
- [ ] Test `test_replay_of_v1_run_uses_aliases`: a tiny recorded run whose cache keys use a v1 id replays with no
  `NotRecorded`, writes a lock equal to the recorded one; the same run in `run` mode misses the cache.
- [ ] Implement; register the `modelcall/call.py` PlainTextReply change (commit 7ca21081, reason "adds a branch the
  typed extractor path never takes") for every llm_* extractor and the LLM screen.
- [ ] Replay locks with the recorded ids when every alias resolved (`lockfile.lock(..., ids=...)`).
- [ ] Run `uv run pytest evidence/tests/test_compat.py evidence/tests/test_plan.py evidence/tests/test_replay*.py -q`;
  PASS. Ruling in decisions.md: "versioned extractor compatibility" (replaces "Preserve extractor fingerprint
  integrity"). Commit.

### Task 2: Stale test fixtures (item 9, other three)

**Files:** `evaluation/tests/test_score_kinds.py:269-283`, `webapp/tests/test_evjobs.py:146,156`.

- [ ] `test_effect_scores_unchanged`: monkeypatch `RunDir.cache_file` to return `None` so the test no longer reads the
  absolute cluster cache path in run.json; golden files unchanged.
- [ ] `test_run_jobs_with_the_runbooks_groups`: expect `proposal-rag-factuality-cascade-gaps~{corpus}` (gaps is the
  default strategy since 750cd25e) at both lines.
- [ ] Run both files (evjobs is POSIX-only: skipped here, Codex confirms). Ruling line: "stale fixtures, behaviour
  unchanged". Commit.

### Task 3: Rank scoring — same line, same thing (item 1)

**Files:**
- Modify: `evaluation/wholerun.py:130-178` (`from_run`, `_rank`), `evaluation/wholerun_cmd.py:92-120` (`main_line`,
  `error_split`), `evidence/kg/truthgraph.py:83-107` (`matches`/`split`)
- Test: `evaluation/tests/test_wholerun_from_run.py` (line 30 asserts "first answered line": change it),
  `evaluation/tests/test_wholerun.py`, `evaluation/tests/test_cli_wholerun.py:378-395`

**Interfaces:**
- Produces: `wholerun.scored_line(plan: Plan) -> PlanLine` — first non-oversell line whose template is `rank` or
  `best`, else the existing `main_line` choice. Both `from_run` and `error_split` call it.
- Produces: `truthgraph.matches(..., mode: Literal["all", "top1"] = "all")`; rank questions use `"top1"`: first
  distinct value of the `paper` column equals gold[0], on both our rows and the key-store rows.

- [ ] Tests: scilead-17-like fixture (l1 rank empty, l2 list has rows) → headline 0 and the split judges l1;
  scilead-24-like (top1 right, full order wrong) → split label is not "synthesis error"; failed main line →
  `"synthesis error: plan: line l1 failed"`.
- [ ] Test `test_key_store_metric_names_follow_plan_measures`: key records named in release spelling ("F1",
  "ROGUE-1") are renamed to the plan measure id they clean to (`names.clean`, "_" read as space, or a
  `plan.words.things[m]` alias) before the key store is built; an unmatched metric keeps its name.
- [ ] Implement; no fallthrough to a later line when the scored line is empty.
- [ ] Run the three test files; PASS. Ruling: headline and split both judge top-1 on the scored line; the split's
  key store uses the plan's measure ids (a plumbing fix, gold values untouched). Commit.

### Task 4: Plan checks for new plans (items 2, 3-root, 7-q05/q06/q10)

**Files:** Modify `evidence/planner/plan.py:317-362` (`query_problem`, `check_plan`), `scripts/plan-runs.py:58-82`
(`plan_all`). Test: `evidence/tests/test_planner.py`.

**Interfaces:**
- Produces: `plan.KNOWN_PREDICATES: frozenset[str]` (the `ev:` properties in `evidence/vocab/ev.ttl`, the fixed `kg:`
  names `context contextKey side position inTable higherIsBetter`, rdf/rdfs terms) plus patterns `ev:setting_\w+`,
  `kg:key_\w+`. `query_problem` returns `"unknown predicate kg:dataset; the graph emits ev:setting_<key> for a
  setting value and kg:key_<key> for its cleaned key"` for anything else (feeds the existing repair loop).
- `check_plan` adds: line needs `$metric`/`$metrics` but `plan.measures` is empty → `"line {id}: its query needs a
  measure ($metric) but the plan names no measure"`; a line with an empty query → `"line {id}: could not be planned"`;
  no `words.things` besides measures → `"the plan names no compared thing besides its measures"`.

- [ ] Tests: each new message on a minimal plan; `kg:dataset` refused; every saved plan under
  `reports/general/plans/` still loads (`Plan.model_validate`) — flagged ones are listed, not raised.
- [ ] `plan_all` calls `check_plan(plan, saved_templates())` after planning and prints `plan problems <qid>: ...`;
  it does not delete or rewrite the plan.
- [ ] Keep the `kg:dataset` shim in `evidence/kg/query.py` for old saved plans; add a comment saying so.
- [ ] Run `evidence/tests/test_planner.py evidence/tests/test_plan_run.py`; PASS. Commit.

### Task 5: Rank answer names the winner (item 5)

**Files:** `evidence/planner/lines.py:39-57`. Tests: `evidence/tests/test_lines_independent.py`,
`evidence/tests/test_plan_run.py:139,179`.

- [ ] Test: rank rows `[{paper, score, thing}, ...]` → text starts `"Best: <thing> in <paper> (score <s>)"`, ties on
  the top score all listed; lower-is-better metric (query emits `-best`) shows the positive score; `best`-template
  rows → `"Best: <thing> (<count> wins)"`; the existing yes/no part, `"missing:"` text and `rule_met` unchanged.
- [ ] Implement; run tests; commit.

### Task 6: Name matching by aliases and bracket forms (items 3, 4)

**Files:** `evidence/kg/query.py:90-101` (`_clean_keys`), `evidence/planrun.py:356-366,466` (`line_params`),
`evidence/engine.py:152` (`Settings.match`), `evidence/replay.py:41-56`. Test: `evidence/tests/test_query*.py`,
`evidence/tests/test_plan_run.py`.

**Interfaces:**
- `Settings.match: Literal["exact", "aliases"] = "aliases"`; replay default `s.get("match", "exact")`.
- `query.render(..., aliases: dict[str, list[str]] | None)`; key = cleaned literal. With aliases, a
  `kg:key_x "lit"` or `kg:contextKey "lit"` triple becomes a fresh variable plus `VALUES` over the cleaned literal, its
  bracket parts (`"A (B)"` → `A (B)`, `A`, `B`), and the cleaned id and aliases of the word-list thing whose id or any
  alias cleans equal to the literal. No containment matching.

- [ ] Tests: "ICSI Meeting Recorder Dialog Act Corpus (MRDA)" matches a graph key "mrda"; "Ontonotes v5 - English"
  with alias "OntoNotes 5.0" matches "ontonote 5.0"; a literal with no alias/brackets renders the identical query
  string to `match="exact"`; an old run.json without `match` replays unchanged.
- [ ] Implement; run tests; commit. Note in ledger: SciREX 006/007/010/015/017/019 need re-extraction (experiments
  carry no task) — out of reach without model calls.

### Task 7: Leak test scores (item 6)

**Files:** `evidence/__init__.py`; `evaluation/score.py:~1694` (`score_extraction_only`). Test:
`evaluation/tests/test_leak*.py` (or the nearest existing leak test).

- [ ] Test: `evaluate leak` on a run whose items are `experiment` records loads (no "not registered").
- [ ] Add `from . import records  # noqa: F401` after the `evidence_types` import.
- [ ] Test + implement: `score_extraction_only` also reads the condition/metric/dataset facts nested in `experiment`
  records (dedupe with plain items). Ruling: the scorer reads a record type it previously skipped; gold untouched.
- [ ] Verify on `reports/general/runs/offtemplate/q01` with `tests/EV2/corpora/rag-claude-s1-mixed`; record recall
  before/after in the ledger. Commit.

### Task 8: Off-template plumbing (item 7)

**Files:** `evidence/planrun.py:65-69,97-99,130-132` (`compare_sides`, `sides`, `protocol_for`),
`evaluation/offtemplate/check.py:75,100-127`, `evaluation/wholerun_cmd.py:284-291`, `evidence/kg/truthgraph.py:73-78`.

- [ ] Fewer than two non-measure sides → treatment `any`, control `other` (add `any` to `roles`); test that
  q06-shaped plans validate.
- [ ] `fresh` counts only lines with `template is None and bool(line.query)`; questions without a plan or with no
  runnable line count in the denominator as not matched.
- [ ] Key store for off-template: map each plan side id to the pack role it names (word-list thing → pack role), so
  `VALUES ?s { $sides }` filters work on the key.
- [ ] `same_rows`: gold count-only columns are optional when absent from ours; names compared via `names.clean`.
- [ ] Rerun `uv run evaluate offtemplate ...` (command in `docs/runbook-general-system.md` §7) locally into the
  scratchpad; record old/new match rate and fresh share in the ledger. Rulings for denominators and `same_rows`.
  Commit.

### Task 9: Model output failures are not outages (item 8)

**Files:** `evidence/extractors/llm.py:99-126`, `evidence/rundir.py:49-60`; compat entry via Task 1.

- [ ] Test: an extractor call ending in `UnexpectedModelBehavior: Exceeded maximum output retries` is recorded with
  `reason="model_output"`; `failed_calls()` ignores it; `evidence run` warns and exits 0. A gateway error still exits 2.
- [ ] Implement; `compat.register` the new `llm.py` hash for each llm_* extractor (behaviour equal for every successful
  call). Note in ledger: whitespace/quote loops seen in paraphrased t000061/t000171 and complex t000317; the vLLM
  option is unverified — Codex checks on the stack. Commit.

### Task 10: Cheaper, bounded model calls (items 10, 11)

**Files:** `evidence/engine.py:385-396,714,752` (map order, `_structured`, `stage_ask`),
`evidence/experiments.py:126-142`, `evidence/calls.py:184-191`, move `gold/calls.py:45,84-96` `classify` →
`modelcall/errors.py`, `evidence/extractors/llm.py:85`, `evidence/extractors/llm_schema.py:105-116`.

**Interfaces:**
- `Settings.budget: Literal["off", "on"] = "on"`; replay default `"off"`. With `on`: no `map-experiments` in
  `before_extract`; `after_document` returns `[]` for skipped papers; `stage_ask`/`_map` skip a request whose
  `len(text) / CHARS_PER_TOKEN` exceeds `pins.context_tokens` with note `unchecked: too_long`.
- Error records get `"permanent": "too_long"` when `classify` says so; `CallCache.recorded` never re-asks those, in
  any mode.
- Extractor config key `prompt_chars` (opt-in; absent → id unchanged); `llm_schema.fit_context(items, budget) ->
  list` keeps link-target types first.

- [ ] Tests for each bullet, including: run.json without `budget` replays with the old stage list; scilead-07-shaped
  corpus maps only papers the screen keeps.
- [ ] Implement; compat entries for llm.py/llm_schema.py edits; commit.

### Task 11: Cross-process cache (item 12)

**Files:** `modelcall/cache.py:26-65`. Test: `modelcall/tests/test_cache*.py`.

- [ ] Test: two `multiprocessing` writers append 200 entries each of 1-64 KB; every line parses; a third reader's
  `get` miss catches up and finds the other writer's key.
- [ ] `put` holds `FileLock(path + ".lock")`, writes encoded bytes via `os.write` on `O_WRONLY|O_APPEND` in a loop;
  `self._offset` tracks parsed bytes; a `get` miss and each `put` first parse from `_offset` to EOF. File format
  unchanged. If `cache.py` is in an extractor fingerprint, add compat entries. Commit.

### Task 12: OpenAlex backoff (item 13)

**Files:** `evidence/openalex.py:35,99-107,162-187`. Test: `evidence/tests/test_openalex*.py`.

- [ ] Test with an injected clock/sleep: 429 then 200 → resolved, one entry not in `openalex-failed.jsonl`;
  `Retry-After` honoured; 4 tries max, ~30 s cap; 429 does not count toward `BREAK_AFTER`.
- [ ] Wrap only the default `_urlopen`; ~5 requests/s process-wide. Commit.

### Task 13: Labels, rulings, runbook (items 15, finish)

- [ ] MeasEval score output and report say "MeasEval scalar subset (226 of 499 quantities)"; SOFC frame scoring stays
  on hold (ledger + decisions.md).
- [ ] `docs/runbook-general-system.md`: short Codex section — rescore with no model calls (SciLead
  `wholerun --system engine`, off-template, leak), rerun what changed (SciREX, off-template q05/q06/q10, leak, synthetic
  paraphrased + complex), Linux suite incl. POSIX tests, then the robustness additions (all kept questions, a stronger
  RAG setting, 3 repeats) if time allows.
- [ ] Whole-branch review (superpowers:requesting-code-review), fix findings.
- [ ] Merge into local `main` as a squash of code + small reports: `git merge --squash fix/general-run`, then
  `git rm -r --cached reports/general/runs` (and any per-run `calls/`), check `git diff --cached --stat` has no file
  over ~5 MB, commit. Do not push.
