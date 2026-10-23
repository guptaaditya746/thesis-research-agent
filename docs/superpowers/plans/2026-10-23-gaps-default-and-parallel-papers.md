# Gaps default and parallel papers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `gaps` the default strategy everywhere, and let one `evidence run` keep several model calls in flight (one per paper, 3 by default) so all three orch replicas work, without changing any output of the run.

**Architecture:** Two passes. A *warm* pass runs every paper's funnel in a thread pool against a throw-away run directory; its only lasting effect is filling the shared record cache. Then the existing sequential loop runs unchanged and finds every call in the cache, so call ids, `events.jsonl` order, `evidence.jsonl` and every output hash are the same as a one-thread run. `CallCache` remembers which keys this process made, so the second pass still reports them as `fresh` (cost stays true) and never retries them a second time.

**Tech Stack:** Python 3.14, `concurrent.futures.ThreadPoolExecutor`, pytest, pydantic-ai `FunctionModel`; React/TS for one UI default.

**Spec:** decisions agreed with Aditya on 23 Oct 2026 (memory `question-first-redesign-23oct`): build step 1 = "gaps default everywhere" + "threads, 3–6 papers at once in one run, per-paper results written in paper order so the trace stays reproducible". Engine background: [docs/evidence-system.md](../../evidence-system.md) Part D; engine docstring [evidence/engine.py:1-36](../../../evidence/engine.py).

## Global Constraints

- Do not touch `llm-setup/` (submodule; sbatch files changed by Aditya).
- Two processes must never append to the same cache file; threads in one process share one `JsonlCache` (it has a lock, [modelcall/cache.py:36](../../../modelcall/cache.py)).
- A run with `workers=N` must produce byte-identical `run.json["outputs"]` to the same run with `workers=1` (same cache start state).
- `replay` and `reexec` stay sequential (no warm pass).
- Default workers: `3` (one per orch replica). Minimum `1`.
- Baseline before starting: `.venv/Scripts/python.exe -m pytest evidence webapp -q` passes on main `1963042`; work on a new branch `step1/gaps-threads`.

## Review Focus

1. A run with more workers than papers (e.g. 2 papers, 3 workers) works and gives the same outputs.
2. A paper whose extractor raises in the warm pass: the run fails the same way a `workers=1` run does (no hang, no half-written run directory left looking complete).
3. `--retry-errors` with workers > 1: a cached error is retried exactly once (attempt 1), never attempt 2.
4. An old `run.json` without `cost.workers` still replays.
5. A cached run (everything already in the cache) with workers > 1 makes zero model calls and reports `made_model_calls == 0`.

---

### Task 1: `gaps` is the default strategy

**Files:**
- Modify: `evidence/engine.py:15-20` (docstring: `gaps` becomes "(the default)", `all` becomes "the benchmarking mode, ask for it"), `evidence/engine.py:74`, `evidence/engine.py:405`
- Modify: `evidence/cli.py:4,18,59` (default and help text)
- Modify: `webapp/evmodels.py:586`, `webapp/evjobs.py:426`
- Modify: `webapp/web/src/components/flow/RunStep.tsx:50` (`useState<"all" | "gaps">("gaps")`)
- Modify: `docs/slurm-evidence-runbook.md:404` (text: "`--strategy all` is written out because the default is now `gaps`"); the runbook's command lines already pass `--strategy` explicitly, leave them
- Test: `evidence/tests/test_funnel.py`, `webapp/tests/` (the RunRequest test file that exists for evmodels; add there)

**Interfaces:**
- Produces: `Settings.strategy`, `engine.run(strategy=...)`, `RunRequest.strategy`, `run_group(...)` caller default all default to `"gaps"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_run_without_a_strategy_is_a_gaps_run(tmp_path: Path) -> None:
    # same setup as gaps_run but without strategy=
    root = engine.run(PROTOCOL, corpus_of(tmp_path, DOCS), tmp_path / "out", provider=provider_of(scripted(make_script([]), [])), model="scripted-alias")
    assert read(root, "run.json")["settings"]["strategy"] == "gaps"

def test_the_cli_default_strategy_is_gaps() -> None:
    assert cli.parser().parse_args(["run", "p.yaml", "c", "out"]).strategy == "gaps"

def test_a_run_request_defaults_to_gaps() -> None:
    assert RunRequest(corpus="c", protocol=ProtocolRef(source="builtin", name="rag")).strategy == "gaps"
```

Use the helpers that `test_funnel.py` already has (`gaps_run` shows how the corpus and provider are built; reuse its corpus builder rather than adding one). If `cli` has no `parser()` function, test through the function `main` uses to build its parser.

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest evidence/tests/test_funnel.py -k "without_a_strategy or cli_default" -q` and the webapp test.
Expected: 3 FAIL (`"all" != "gaps"`).

- [ ] **Step 3: Change the five defaults and the help/doc text listed under Files.**

- [ ] **Step 4: Run the full suites**

Run: `.venv/Scripts/python.exe -m pytest evidence webapp -q` and `npm --prefix webapp/web test -- --run`.
Expected: the 3 new tests PASS. Any old test that now fails because it relied on the `all` default: pass `strategy="all"` (or `--strategy all`) explicitly in that test; do not change its assertions.

- [ ] **Step 5: Commit**

```bash
git commit -am "evidence: gaps is the default strategy (CLI, engine, web app, runbook text)"
```

---

### Task 2: `CallCache` remembers what this process made

**Files:**
- Modify: `evidence/calls.py:85-127` (`CallCache`)
- Test: `evidence/tests/test_engine.py` (or a new `evidence/tests/test_calls_made.py` if test_engine has no direct CallCache tests)

**Interfaces:**
- Produces: `CallCache.made: set[str]` (cache keys stored by `call()` in this process). In mode `run`, `call()` checks the latest hit's key: if it is in `made`, it returns `Outcome(..., source="fresh", attempt=n)` with the hit's result and model calls, and does **not** retry it even when `retry_errors` is on and the status is `error`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_call_made_in_this_process_is_reported_fresh_on_the_second_ask(tmp_path):
    cache = CallCache(JsonlCache(tmp_path / "c.jsonl"), "run")
    first = cache.call(ext, task, make_ctx)
    second = cache.call(ext, task, make_ctx)
    assert first.source == second.source == "fresh" and runs_of(ext) == 1
    assert second.raw == first.raw and second.model_calls == first.model_calls

def test_a_cache_hit_from_an_earlier_process_stays_cache(tmp_path):
    CallCache(JsonlCache(tmp_path / "c.jsonl"), "run").call(ext, task, make_ctx)
    again = CallCache(JsonlCache(tmp_path / "c.jsonl"), "run").call(ext, task, make_ctx)
    assert again.source == "cache" and runs_of(ext) == 1

def test_retry_errors_retries_a_made_error_only_once(tmp_path):
    # ext fails every time; cache already holds attempt 0 (error) from an earlier process
    cache = CallCache(JsonlCache(path), "run", retry_errors=True)
    a = cache.call(failing, task, make_ctx); b = cache.call(failing, task, make_ctx)
    assert (a.attempt, b.attempt) == (1, 1) and runs_of(failing) == 1
```

`ext`/`failing` are tiny test extractors counting their `extract` calls; build `task` the way existing engine tests build an `ExtractionTask` (reuse their fixture if one exists).

- [ ] **Step 2: Run to verify they fail** — Expected: first test FAIL (`"cache" != "fresh"`), third FAIL (attempt 2).

- [ ] **Step 3: Implement** — add `self.made: set[str] = set()` in `__init__`; add the key to it after `self.cache.put(...)`; in the `run` branch, before the retry check, return the fresh outcome when `cache_key(..., n) in self.made`. Module docstring: one line under `run` saying so and why (the warm pass of Task 3).

- [ ] **Step 4: Run** `.venv/Scripts/python.exe -m pytest evidence -q` — Expected: PASS.

- [ ] **Step 5: Commit** `git commit -am "evidence: CallCache reports calls made in this process as fresh"`

---

### Task 3: the warm pass (`workers`)

**Files:**
- Modify: `evidence/engine.py` — `execute_run` (:367-395), `run` (:402-412), module docstring (one paragraph "Workers")
- Modify: `evidence/cli.py` — `--workers` (int, default 3, `>= 1`, help "papers whose model calls run at once; outputs do not depend on it"), pass through in `_dispatch`
- Test: `evidence/tests/test_parallel.py` (new)

**Interfaces:**
- Consumes: `CallCache.made` (Task 2).
- Produces: `execute_run(..., workers: int = 1)`, `run(..., workers: int = 3)`, `run.json["cost"]["workers"]` (int). `Settings` is **not** changed (workers never changes a result, so replay must not depend on it).

Algorithm (put this as `_warm(...)` in engine.py, called from `execute_run` only when `mode == "run" and workers > 1`):

```python
def _warm(protocol, corpus, calls, cascades, provider, locator, strategy, workers) -> None:
    """Fill the record cache with every paper's calls, `workers` papers at once; outputs are thrown away."""
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(workers) as pool:
        def one(i, paper):
            root = Path(tmp) / str(i); root.mkdir()
            Execution(protocol, corpus, root, f"warm-{i}", calls, cascades, provider, locator, strategy).document(paper)
        for f in [pool.submit(one, i, p) for i, p in enumerate(corpus.papers)]:
            f.result()          # re-raise the first failure
```

Then the existing sequential loop runs as now; set `ex.cost["workers"] = workers`.

- [ ] **Step 1: Write the failing tests**

```python
def test_workers_change_no_output(tmp_path):
    one = engine.run(PROTOCOL, corpus, tmp_path / "a", cache=tmp_path / "ca", provider=p1, model="scripted-alias", workers=1)
    three = engine.run(PROTOCOL, corpus, tmp_path / "b", cache=tmp_path / "cb", provider=p3, model="scripted-alias", workers=3)
    ra, rb = read(one, "run.json"), read(three, "run.json")
    assert ra["outputs"] == rb["outputs"]
    assert {k: ra["cost"][k] for k in ("calls", "model_calls", "made_model_calls")} == \
           {k: rb["cost"][k] for k in ("calls", "model_calls", "made_model_calls")}
    assert rb["cost"]["workers"] == 3

def test_workers_keep_several_calls_in_flight(tmp_path):
    # async FunctionModel: in_flight += 1; peak = max(peak, in_flight); await asyncio.sleep(0.05); in_flight -= 1
    engine.run(..., provider=provider_of(slow_model), workers=3)   # corpus of >= 3 papers
    assert peak >= 2

def test_more_workers_than_papers(tmp_path):            # Review Focus 1
    root = engine.run(..., corpus=two_papers, workers=3)
    assert read(root, "run.json")["outputs"] == read(engine.run(..., corpus=two_papers, workers=1), "run.json")["outputs"]

def test_a_fully_cached_run_with_workers_makes_no_model_call(tmp_path):   # Review Focus 5
    engine.run(..., cache=c, workers=3); seen.clear()
    root = engine.run(..., cache=c, workers=3)
    assert seen == [] and read(root, "run.json")["cost"]["made_model_calls"] == 0

def test_replay_of_a_parallel_run_reproduces_every_hash(tmp_path):        # Review Focus 4 + replay
    root = engine.run(..., workers=3)
    # replay the way test_funnel.test_replay_and_reexec_of_a_gaps_run does; assert its success condition

def test_a_crash_in_the_warm_pass_fails_the_run(tmp_path, monkeypatch):      # Review Focus 2
    # monkeypatch Execution.document to raise RuntimeError("boom") for the second paper only
    with pytest.raises(RuntimeError, match="boom"):
        engine.run(..., workers=3)
    assert not any((tmp_path / "out").glob("*/run.json"))   # no run.json: the run never looks complete

def test_the_cli_workers_flag():
    assert cli.parser().parse_args(["run", "p.yaml", "c", "out"]).workers == 3
    with pytest.raises(SystemExit): cli.parser().parse_args(["run", "p.yaml", "c", "out", "--workers", "0"])
```

Build the corpus and scripted provider with the helpers in `test_funnel.py` (`make_script`, `scripted`, `provider_of`) and a 4-paper `docs` dict; the run uses the default strategy (`gaps`). For the in-flight test use an `async def` reply function for `FunctionModel`; a sync one blocks the shared model loop and would hide the concurrency.

- [ ] **Step 2: Run to verify they fail** — `.venv/Scripts/python.exe -m pytest evidence/tests/test_parallel.py -q` — Expected: FAIL (`unexpected keyword argument 'workers'`).

- [ ] **Step 3: Implement** `_warm`, the `workers` parameter on `execute_run`/`run`, `cost["workers"]`, the CLI flag (argparse `type` that rejects `< 1`), and the docstring paragraph: why two passes (call ids and event order stay those of paper order; the second pass reads every call from the cache).

- [ ] **Step 4: Run** `.venv/Scripts/python.exe -m pytest evidence webapp -q` — Expected: PASS. Then one real check needs no model: `.venv/Scripts/python.exe -m evidence run <protocol> <a tests/EV2 corpus> <tmp out> --extractors regex-only --workers 3` prints a run with the same `label`/`counts` as `--workers 1`.

- [ ] **Step 5: Commit** `git commit -am "evidence: --workers runs papers' model calls at once; outputs unchanged"`

---

### Task 4: hand-off note for Codex

**Files:**
- Modify: `docs/slurm-evidence-runbook.md` — in the lanes section (:347-353) one paragraph: engine runs now default to `--workers 3`, so one lane keeps up to 3 calls in flight; with 3 lanes the gateway sees up to 9 at once, about 3 per replica under least-busy routing. Read the limits of the `orch-3x40` profile in `llm-setup/` (read only, do not edit) and write the number it allows into the paragraph. No other runbook change.

- [ ] **Step 1:** write the paragraph. **Step 2:** commit `git commit -am "runbook: note --workers"`.
