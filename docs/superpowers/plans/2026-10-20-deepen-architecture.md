# Deepen the architecture (seven candidates, two bugs) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Do all seven deepenings from the 20 Oct architecture review: a deep cached model-call module, a run-directory reader, a job plan per job kind, one prompt-file loader, a process seam under the job manager, contract scenarios shared by the backend and the frontend mock, and canonical JSON moved out of `agent/`. Fix the two likely bugs (`Recorder._run` and `truth.read_jsonl`) along the way, then push.

**Architecture:**
- Two new top-level packages: `jsonio/`, which takes over the canonical JSON code from `agent/canonical.py`, and `modelcall/`, which takes over `gold/llm.py` and adds the deep `ask`.
- `evidence/rundir.py` gains a read side, `RunDir`. Evaluation and the web app read run directories only through it.
- `webapp/evjobs.py` turns each job kind into a `JobPlan`.
- `webapp/jobs.py` gets a `Processes` seam with two adapters: POSIX for real use, a fake for tests.
- The frontend mock is checked against write-contract scenarios recorded from the real backend.

**Tech Stack:** Python 3.13, pydantic-ai 2.55 (FunctionModel for tests), FastAPI, pytest 8.4. Frontend: React, MSW, vitest, openapi-typescript. Package manager: uv.

**Spec:** `docs/superpowers/specs/2026-10-20-architecture-review.html`, candidates 1–7.

## Global Constraints

- **Cache keys stay byte-identical.** Every cache key any caller writes today must be the same after this work: the RAG/agent baselines, propose, judge, gold calls, the synth renderer, and the engine's CallCache. Caches on Slurm and the committed examples depend on them. Task 2 pins them, and those tests must pass unchanged to the end.
- **Cached values written before this work still read.** Each caller's current value shape must decode.
- **Hashed file formats do not change.** This covers:
  - the proposal files (`indent=1` JSON, LF);
  - canonical JSON plus a newline;
  - prompt text as each caller hashes it today. Propose strips the text and adds a trailing `\n`; the other callers do not strip.
- **No real HTTP and no subprocess in unit tests**, except:
  - the keep-alive HTTP test (`modelcall/tests/test_loop.py`);
  - one POSIX-only process-adapter test (skipped on Windows).
- **Every `synth/*.py` change makes `synth/examples` stale.** Rebuild them in the same commit with `uv run synth build --name rag-demo --seed 1 --studies 6 --out synth/examples` (enforced by `synth/tests/test_example.py`).
- **Full suite:** `uv run pytest -q` (WSL is the reference: 1250 passed, 1 skipped on 18 Oct). Report the new count in `docs/STATE.md`.
- **Frontend gates:** `cd webapp/web && npm run typecheck && npm run lint && npm test && npm run build`. Commit the rebuilt `dist/`.
- **Commits:** end every message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Branch:** `arch/deepen`. Push it to `origin` at the end. Do not push `main`.
- **Vocabulary:** match the surrounding code's naming and docstring style (plain sentences, the repo's terms: run directory, record cache, extractor call, proposal, card).

## Review Focus

1. **A Slurm-killed run with a half-written last line** in `events.jsonl` or the record cache: scoring and the viewer must read it, skipping only that last line. A malformed line in the middle still raises. Pinned in Task 6.
2. **A cache entry written before this work:** `ask` must return it as cached and make no model call. This holds for each legacy value shape (bare output, judge's flat fields, synth's flat tokens, `{output, usage}`). Pinned in Task 4.
3. **Two real model calls in one process through the engine's Recorder:** both must reach the server, with no "Event loop is closed". Pinned in Task 5.
4. **A prompt file checked out with CRLF:** its hash must equal the hash of the LF copy, for every loader. Pinned in Task 3.
5. **The web app restarted while a job's process still runs:** the job stays running, orphaned and cancellable. A dead process marks the job failed. Pinned in Task 8 with the fake adapter.

---

## File Structure

| Path | Responsibility |
|---|---|
| `jsonio/__init__.py` (create) | canonical JSON (`canonical`, `canonical_bytes`, `sha256_hex`, `file_sha256`, `GENESIS`, `write_json`), `write_json_atomic`, `write_text_atomic` |
| `agent/canonical.py` (delete) | moved to `jsonio` |
| `modelcall/__init__.py` (create) | the public interface: `ask`, `ask_sync`, `Answer`, `ModelCallError`, `Prompt`, `load_prompt`, `JsonlCache`, `cache_key`, `CallSettings`, `run_sync`, `on_model_loop`, `openai_model`, `Rotation`, `model_identity`, `model_name`, `redact`, pins |
| `modelcall/loop.py` | the one model event loop (`model_loop`, `run_sync`, `on_model_loop`) |
| `modelcall/gateway.py` | `base_url`, `openai_model`, `Rotation`, `CallSettings`, `model_name`, `model_identity`, pins `ORCHESTRATOR`, `SUBAGENTS`, `SUB_ALIASES`, `SUB_MODEL`, `ORCH_ALIAS`, `ORCH_MODEL` |
| `modelcall/cache.py` | `JsonlCache` (+ `items()`, `KEY_LINE`), `cache_key`, `decode` |
| `modelcall/prompt.py` | `Prompt`, `load_prompt` |
| `modelcall/call.py` | `ask`, `ask_sync`, `Answer`, `ModelCallError`, `redact` |
| `modelcall/tests/` | tests of the above; pyproject `testpaths` and `module-name` gain `modelcall`, `jsonio` |
| `gold/llm.py` (delete) | moved to `modelcall` |
| `evidence/rundir.py` (modify) | adds `RunDir`, a tolerant `read_lines` |
| `webapp/procs.py` (create) | `Processes` seam, `PosixProcesses` |
| `webapp/tests/fakes.py` (create) | `FakeProcesses` |
| `webapp/evjobs.py` (modify) | `JobPlan`, `run_group`, one submit path, `GET /run-group` |
| `webapp/tests/write_contract.py` (create) | scenarios run against the real backend, recorded to `webapp/web/src/mocks/write-contract.json` |
| `webapp/web/src/mocks/contract.test.ts` (create) | replays the recorded scenarios against the MSW mock |

---

### Task 0: Branch and baseline

**Files:** the uncommitted working tree, which carries `run_sync` in `gold/llm.py` and its callers, a new test in `evaluation/tests/test_rag.py`, and the rebuilt `synth/examples` code hashes.

- [ ] **Step 1:** `git switch -c arch/deepen`.
- [ ] **Step 2:** Run `uv run pytest -q`. Expected: everything passes. Note the count.
- [ ] **Step 3:** Commit the work in progress as is: `git add -A evaluation evidence gold synth && git commit -m "llm: every one-off model call on one event loop (run_sync)"`.

### Task 1: `jsonio`, the canonical JSON package (candidate 7)

**Files:**
- Create: `jsonio/__init__.py`
- Create: `jsonio/tests/test_jsonio.py`
- Delete: `agent/canonical.py`
- Modify: about 50 importers (`grep -rln "agent.canonical\|from agent import canonical" --include=*.py .`)
- Modify: `webapp/files.py` (`write_json_atomic` moves here)
- Modify: `webapp/evjobs.py` (`write_text_atomic` moves here)
- Modify: `evidence/rundir.py` (`write_canonical` becomes `jsonio.write_json`)
- Modify: `pyproject.toml` (`module-name`, `testpaths`)

**Interfaces:**
- Produces:
  - `jsonio.canonical(obj) -> str`
  - `jsonio.canonical_bytes(obj) -> bytes`
  - `jsonio.sha256_hex(data: bytes) -> str`
  - `jsonio.file_sha256(path) -> str`
  - `jsonio.GENESIS`
  - `jsonio.write_json(path: Path, obj) -> str`: makes parent directories and returns the sha256 of the bytes.
  - `jsonio.write_json_atomic(path: Path, obj) -> str`: canonical, temp file plus `os.replace`, returns the sha256.
  - `jsonio.write_text_atomic(path: Path, text: str) -> None`: LF line ends.

- [ ] **Step 1: Write the failing tests** in `jsonio/tests/test_jsonio.py`:
  - `test_write_json_is_canonical_and_makes_parents`: `write_json(tmp/"a"/"b.json", {"b":1,"a":"é"})` returns `sha256_hex(b'{"a":"\xc3\xa9","b":1}\n')` and the file exists.
  - `test_write_json_atomic_leaves_no_temp_file_on_error`: an object that is not serialisable (`{1j}`) raises `TypeError`, and `list(tmp.iterdir()) == []`.
  - `test_write_text_atomic_writes_lf`: `"a\nb\n"` reads back as bytes `b"a\nb\n"` on Windows too.
- [ ] **Step 2:** Run `uv run pytest jsonio -q`. Expected: FAIL (`ModuleNotFoundError: jsonio`).
- [ ] **Step 3:** Create `jsonio/__init__.py`. Move the body of `agent/canonical.py` and the two atomic writers verbatim. `write_json` gains `path.parent.mkdir(parents=True, exist_ok=True)`.
- [ ] **Step 4:** Repoint every importer with a mechanical rewrite: `from agent.canonical import` → `from jsonio import`, and `from agent import canonical` → `import jsonio as canonical`. Then:
  - delete `agent/canonical.py`;
  - delete `evidence/rundir.write_canonical`, renaming its callers to `jsonio.write_json`;
  - delete `webapp/files.write_json_atomic` and `evjobs.write_text_atomic`, importing them from `jsonio`;
  - add `jsonio` and `modelcall` to `module-name`, and `jsonio/tests` to `testpaths`.
- [ ] **Step 5:** `grep -rn "agent.canonical\|agent import canonical" --include=*.py .` returns nothing, and `uv run pytest -q` passes with the same count plus 3.
- [ ] **Step 6:** Commit `jsonio: canonical JSON and atomic writers out of agent/`.

### Task 2: Pin every caller's cache key and value shape (characterization)

**Files:**
- Create: `modelcall/tests/test_golden_keys.py`
- Create: `modelcall/tests/__init__.py`

**Interfaces:**
- Consumes: today's call sites, unchanged.
- Produces: golden hex keys that Tasks 3–5 must keep green.

- [ ] **Step 1: Write the tests.** Each test drives the real caller once with a `FunctionModel` and a temporary `JsonlCache`, reads the single cache line written, and asserts its `key` equals a hex literal. Run each test once, paste in the printed key, and commit it. The literal is the pin.
  - `test_baseline_key`: `evaluation.baselines.common.cached_reply(cache, "I", "P", model=fm, model_id="orch")`.
  - `test_propose_key`: `evidence.propose.common.ask(tmp, "frame", "I", "P", AnswerLike, model=fm)`.
  - `test_judge_key`: `Judge(tmp, [fm]).support(fact, "q")` with `PROBE_FACT`.
  - `test_gold_calls_key`: `Caller(Rotation([fm]), cache).call("s", prompt, Out, "P", max_tokens=100)` via `run_sync`.
  - `test_synth_render_key`: `LlmRenderer(fm, cache)._call("I", "P", PaperReply, fm, 1)` via `run_sync`.
  - `test_engine_callcache_key`: `evidence.calls.cache_key("x@1", "t"*64, 0)`.

  Each test also asserts the stored value's top-level keys (sorted), for example `["output", "usage"]` for the baseline. That pins the legacy shapes for Task 4's decoder.
- [ ] **Step 2:** Run `uv run pytest modelcall/tests/test_golden_keys.py -q`. Expected: PASS against today's code.
- [ ] **Step 3:** Commit `modelcall tests: pin every caller's cache key and value shape`.

### Task 3: `modelcall` from `gold/llm.py`, plus one prompt loader (candidate 4, and the split of the gold.llm grab-bag)

**Files:**
- Create: `modelcall/{__init__,loop,gateway,cache,prompt}.py`
- Create: `modelcall/tests/test_prompt.py`
- Create: `modelcall/tests/test_cache.py`
- Move: `gold/tests/test_llm.py` → `modelcall/tests/test_llm.py`
- Delete: `gold/llm.py`
- Modify: the 25 importers of `gold.llm` / `from gold import llm`
- Modify: the 12 tests that `monkeypatch.setattr(... llm ...)`
- Modify: `agent/rundir.py`: import the pins from `modelcall.gateway`; `ORCHESTRATOR`/`SUBAGENTS` are defined there now
- Modify: `gold/calls.py` `load_prompt`/`PromptFile`; `gold/judge.py` `load_prompt`/`Prompt`; `evidence/extractors/llm_schema.py` `read_prompt`; `synth/render_llm.py` (`INSTRUCTIONS`, `BLIND_INSTRUCTIONS`); `evidence/propose/common.py` `prompt`
- Modify: `.gitattributes`: add `gold/prompts/** text eol=lf` under the evidence block, with a one-line comment that the judge and gold prompts are hashed into cache keys

**Interfaces:**
- Produces:
  - `modelcall.Prompt(name: str, text: str, output_type: type[BaseModel] | None)`, frozen. Properties:
    - `.sha256`: today's `prompt_sha256(text, output_type)`.
    - `.file_sha256`: sha256 of the UTF-8 text.
    - `.json() -> {"file", "file_sha256", "prompt_sha256"}`.
  - `Prompt.inline(text, output_type) -> Prompt`, with name `"inline"`.
  - `modelcall.load_prompt(path: Path, output_type=None, *, strip: bool = False) -> Prompt`. Reads bytes, decodes UTF-8 and replaces `\r\n` with `\n`. With `strip`, it applies `.strip() + "\n"` (propose only). `name` is the path relative to the repo root, POSIX form.
  - `modelcall.JsonlCache.items() -> Iterator[tuple[str, Any]]`.
  - `modelcall.cache.KEY_LINE`: the regex that `webapp/evfiles.py` uses today, moved here.
  - Everything else keeps its `gold.llm` name and signature, re-exported from `modelcall`.

- [ ] **Step 1: Write the failing tests:**
  - `test_prompt.py::test_crlf_and_lf_hash_the_same`: write the same text with `\r\n` and `\n`; `load_prompt(...).sha256` is equal.
  - `test_prompt.py::test_strip_matches_propose`: `load_prompt(p, strip=True).text == "x\n"` for a file `"\n x \r\n"`.
  - `test_prompt.py::test_every_repo_prompt_loads_as_its_caller_hashes_it`: for each prompt file under `gold/prompts`, `evidence/extractors/prompts`, `synth/prompts` and `evidence/propose/prompts`, the hash equals what the caller's old loader gave (the same expressions, inlined in the test).
  - `test_cache.py::test_key_line_matches_put`: after `put("k", {"a":1})`, `KEY_LINE.match(line)` captures `k`.
  - `test_cache.py::test_items_last_line_wins`.
- [ ] **Step 2:** Run `uv run pytest modelcall -q`. Expected: FAIL on import.
- [ ] **Step 3:** Split `gold/llm.py` into the four modules. Pins, `openai_model`, `Rotation`, `settings`, `model_name` and `model_identity` go to `gateway`. Then:
  - Rename `settings(...)` to `CallSettings`, a frozen dataclass with `temperature=0.0`, `seed=0`, `max_tokens=4096` and a `.model_settings() -> ModelSettings`. Keep a module-level `settings(**kw)` that returns `CallSettings(**kw).model_settings()` for the callers left until Task 5.
  - Replace each of the five prompt loaders with `load_prompt` (propose with `strip=True`).
  - Make `webapp/evfiles.py` import `KEY_LINE`.
- [ ] **Step 4:** Repoint every importer and monkeypatch target, then delete `gold/llm.py`. `grep -rn "gold.llm\|from gold import llm" --include=*.py .` returns nothing.
- [ ] **Step 5:** `uv run pytest -q` passes, including Task 2's golden keys unchanged.
- [ ] **Step 6:** Commit `modelcall: gold.llm split into loop, gateway, cache, prompt; one prompt loader; gold prompts pinned LF`.

### Task 4: The deep `ask` (candidate 1)

**Files:**
- Create: `modelcall/call.py`
- Create: `modelcall/tests/test_ask.py`
- Create: `modelcall/tests/test_loop.py` (the keep-alive server fixture moves here from `evaluation/tests/test_rag.py`, as `keepalive_server(reply: Callable[[str], dict]) -> ContextManager[str]` yielding the base URL; `test_rag.py` imports it)

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class Answer(Generic[T]):
    output: T
    model: str                 # alias asked
    served_model: str | None
    input_tokens: int
    output_tokens: int
    cached: bool
    key: str | None            # None without a cache
    messages: list[Any]        # pydantic-ai ModelMessages of a made call; [] when cached

class ModelCallError(RuntimeError):
    reason: str                # redacted, at most 1000 characters
    cause: BaseException       # never printed by callers; for classify()
    messages: list[Any]

async def ask(prompt: Prompt, user_prompt: str, *, model: Model, settings: CallSettings = CallSettings(),
              cache: JsonlCache | None = None, key: dict[str, Any] | None = None, refresh: bool = False,
              extra: dict[str, Any] | None = None, timeout_s: float | None = None) -> Answer[T]
def ask_sync(...same...) -> Answer[T]          # run_sync(ask(...))
def default_key(prompt: Prompt, user_prompt: str, model: Model, settings: CallSettings) -> dict[str, Any]
def decode(value: Any, output_type: type[T]) -> tuple[T, str | None, str | None, int, int]  # in cache.py
```

- Behaviour:
  - Using a cache requires `key`: the caller's existing recipe, or `default_key(...)` for new callers, which is `{"prompt_sha256", "model": model_identity([model]), "input_sha256", "settings": asdict(settings)}`.
  - The cache key is `cache_key(key)`.
  - A hit (unless `refresh`) is decoded with `decode` and returns `cached=True`.
  - A miss runs `structured_reply` on the model loop (`on_model_loop`) under `capture_run_messages`, with `asyncio.wait_for` when `timeout_s` is set.
  - Any exception becomes `ModelCallError(redact(f"{type}: {exc}")[:1000], cause, messages)`.
  - On success it stores `{"output", "model", "served_model", "usage": {"input_tokens", "output_tokens"}, **extra}`.
  - `decode` accepts that new shape and every legacy shape pinned in Task 2:
    - a value without `"output"` is the output's own fields, read as `{k: value[k] for k in output_type.model_fields if k in value}` (judge, propose);
    - tokens come from `value["usage"]` or from the value's top level (synth);
    - `served_model` comes from the top level or from `usage` (baselines).
  - `structured` and `structured_reply` collapse into one private `_reply` in `call.py`.

- [ ] **Step 1: Write the failing tests** in `test_ask.py`, using pydantic-ai `FunctionModel`:
  - `test_miss_calls_and_stores_new_shape`: one model call; the stored value's keys are `["model","output","served_model","usage"]`.
  - `test_hit_makes_no_call`: a second `ask` has `cached=True` and the call counter is unchanged.
  - `test_refresh_calls_again_and_last_line_wins`.
  - `test_cache_without_key_raises_value_error`.
  - `test_error_is_redacted`: with `LITELLM_MASTER_KEY=sk-secret123` and a model that raises `RuntimeError("bad sk-secret123")`, `reason` holds no `secret123` and `cause` is the `RuntimeError`.
  - `test_timeout_raises_model_call_error`: a model that sleeps 1 s with `timeout_s=0.05`; `cause` is a `TimeoutError`.
  - `test_decode_legacy_shapes`: parametrized over the four legacy values from Task 2's pinned shapes; each returns `cached=True` with the right output, served model and tokens.
  - `test_ask_from_another_running_loop`: `asyncio.run(ask(...))` works; `ask_sync` from inside the model loop raises `RuntimeError`.

  In `test_loop.py`:
  - `test_two_ask_sync_over_keepalive_share_one_loop`: two `ask_sync` calls against `openai_model(url=server)` both reach the server.
- [ ] **Step 2:** Run `uv run pytest modelcall -q`. Expected: FAIL (`ask` undefined).
- [ ] **Step 3:** Implement `modelcall/call.py` and `cache.decode`, and export them from `modelcall/__init__.py`.
- [ ] **Step 4:** `uv run pytest modelcall evaluation/tests/test_rag.py -q` passes.
- [ ] **Step 5:** Commit `modelcall: ask, one cached and redacted structured call on the model loop`.

### Task 5: Six callers onto `ask`, and the Recorder bug

**Files:**
- Modify: `evaluation/baselines/common.py` `cached_reply`
- Modify: `evidence/propose/common.py` `ask`
- Modify: `gold/judge.py` `_ask_here`/`_call`/`_verdict`
- Modify: `gold/calls.py` `Caller.call`/`_ask`/`classify` (classify takes `ModelCallError.cause, .messages`)
- Modify: `synth/render_llm.py` `_call`, `render_all`
- Modify: `evidence/recording.py` `Recorder.structured`, and delete `_run`
- Modify: `gold/build.py:~849`, `gold/triage.py:~183` (`asyncio.run` → `run_sync`)
- Rebuild: `synth/examples`
- Test: `evidence/tests/test_recording_live.py` (create)

**Interfaces:**
- Consumes: Task 4's `ask`, `ask_sync`, `Answer`, `ModelCallError`, `Prompt.inline`.
- Each caller passes its current key recipe as `key=` verbatim. The caller-specific extras go in `extra=`:
  - judge: `task, input, model, alias, prompt_sha256, user_prompt_sha256, settings, created_at`
  - gold calls: `prompt_sha256, at`
- Keep in the callers:
  - judge: the in-flight dedup and its semaphore;
  - gold calls: counters, `accept`, the rotation and too-long negative caching;
  - propose: `ProposalError` with `REDO` for a cached reply that does not validate (catch the `ValidationError` from `decode`).
- Recorder records `request`, `response`, `usage` and `messages` exactly as today (the record layout is part of the engine's cache values). On `ModelCallError` it records `exc.reason[:300]`.

- [ ] **Step 1: Write the failing test** `evidence/tests/test_recording_live.py::test_two_llm_extractor_calls_over_keepalive`. Use `keepalive_server` (Task 4) with a reply function returning a valid output for the extractor prompt. Build `Recorder(provider=lambda alias: openai_model(alias, url=url))` and call `structured` twice in one process. Assert that both records have `response` and no `error`.
- [ ] **Step 2:** Run it. Expected: FAIL, with the second record holding `"Event loop is closed"`. That is the live bug, reproduced.
- [ ] **Step 3:** Port the six callers. Each one's body shrinks to building its key and extras, calling `ask`/`ask_sync`, and mapping `Answer` to its own return type. Then:
  - delete `Recorder._run` and the `ThreadPoolExecutor` import;
  - `render_all` ends with `run_sync(run())`;
  - rebuild `synth/examples`.
- [ ] **Step 4:** `uv run pytest -q` passes. That includes the new live test, Task 2's golden keys unchanged, and every existing caller test.
- [ ] **Step 5:** Commit `callers on modelcall.ask; Recorder no longer opens a loop per call (live keep-alive bug)`.

### Task 6: `RunDir`, the run directory read side (candidate 2, and the truth bug)

**Files:**
- Modify: `evidence/rundir.py`
- Modify: `evaluation/truth.py` (`Run.load`, `read_jsonl`, `cache_file`, `read_usage`, its `CACHE_FILE` copy)
- Modify: `evidence/replay.py` `_attempts`
- Modify: `evidence/agentic/runner.py` literals
- Modify: `evidence/calls.py` `CallCache._check_version` (use `JsonlCache.items()`, not `_data`)
- Test: `evidence/tests/test_rundir_read.py`

**Interfaces:**
- Produces in `evidence/rundir.py`:

```python
ENGINE_MARKERS = (EVENTS_FILE, PROTOCOL_FILE, FUNNEL_FILE, CALLS_DIR)
REEXEC_GLOB = "{name}-reexec-*"
def read_lines(path: Path) -> list[Any]          # skips an unparsable LAST line with no trailing newline; any other bad line raises ValueError naming path:line
class RunDir:
    def __init__(self, root: Path) -> None
    root: Path
    kind: Literal["engine", "baseline"] | None       # engine: run.json or any marker; baseline: answer.json with "system"; else None
    complete: bool                                    # run.json exists
    def file(self, name: str) -> Path                 # root / name
    def json(self, name: str) -> Any | None           # optional canonical file (run.json, answer.json, funnel.json, locate.json, reexec.json, graph.json)
    def items(self) -> list[Item]                     # evidence.jsonl, [] when absent
    def events(self) -> list[dict] | None             # every events.jsonl record, None when absent
    def events_of(self, subtype: str) -> list[dict] | None
    def calls(self) -> list[dict] | None              # calls/*.json sorted by name
    def error_calls(self) -> int
    def cache_file(self) -> Path | None               # from run.json settings.cache (dir or file)
    def usage(self) -> dict[str, dict[str, int]] | None
    def latest_reexec(self) -> Path | None            # newest sibling <name>-reexec-*/reexec.json, no symlinks
    def watched(self) -> tuple[Path, ...]             # run.json, answer.json and the markers: what a reader's cache keys on
```

- [ ] **Step 1: Write the failing tests** in `test_rundir_read.py`:
  - `test_torn_last_line_is_skipped`: events.jsonl holds two good lines plus `{"task_id": "t3", "sub` with no newline; `events()` has length 2.
  - `test_bad_middle_line_raises`: a bad line 2 of 3 raises `ValueError` matching `events.jsonl:2`.
  - `test_kind`: parametrized over engine marker / run.json / baseline answer / empty dir, giving engine / engine / baseline / None.
  - `test_usage_reads_torn_cache`: a record cache whose last line is cut still gives usage for the complete lines (it goes through `JsonlCache`).
  - `test_latest_reexec_picks_newest_and_ignores_symlinks` (the symlink case is skipped on Windows when symlinks cannot be made).
  - `test_error_calls_counts_status_error`.

  In `evaluation/tests/test_truth.py`:
  - `test_run_load_survives_torn_events_line`: `Run.load` on such a dir does not raise.
- [ ] **Step 2:** Run the tests. Expected: FAIL (`RunDir` undefined; `Run.load` raises `JSONDecodeError`).
- [ ] **Step 3:** Implement `RunDir`. `Run.load` becomes a thin reader over it, with the fields unchanged. Delete `truth.read_jsonl`, `truth.CACHE_FILE`, `cache_file` and the body of `read_usage`; replace their callers. Replace the layout literals in `replay.py` and `agentic/runner.py` with the `rundir` constants.
- [ ] **Step 4:** `uv run pytest evidence evaluation -q` passes.
- [ ] **Step 5:** Commit `rundir: RunDir reads what the engine writes; scoring tolerates a torn last line`.

### Task 7: The web app reads runs through `RunDir`

**Files:**
- Modify: `webapp/evfiles.py`: `_run_info`, `_run_summary`, `run_dir`, `_calls`, `run`, `run_paper`, `run_graph`, `run_protocol`, `_cache_file`, `error_calls`; delete `CACHE_FILE` and `ENGINE_MARKERS`; `STEP_FILES` comes from `evidence.propose.common` names
- Modify: `webapp/app.py` `check_job` (failed calls via `RunDir.error_calls`)
- Modify: `webapp/evjobs.py` `score` (`RunDir.latest_reexec`)
- Rename: `EvidenceFiles._run_summary` → `run_summary`, `_score_dir` → `score_dir`, `_decisions` → `decisions_of`
- Test: `webapp/tests/test_evidence_api.py`, `webapp/tests/evidence_world.py`

**Interfaces:**
- Consumes: Task 6's `RunDir`, `ENGINE_MARKERS`, `RunDir.watched()`.
- Produces: the public `EvidenceFiles.run_summary(path) -> EvRunSummary | None`, `score_dir(score_id, file) -> tuple[Path, ...]` (the current return, unchanged) and `decisions_of(directory, cards) -> tuple[dict, list[str]]`, for Task 9.

- [ ] **Step 1: Write the failing test** `test_evidence_api.py::test_run_with_torn_events_line_lists_and_opens`: in a copy of the world, append a cut line to a run's events.jsonl. `GET /api/ev/runs` lists the run, and `GET /api/ev/runs/{id}` answers 200.
- [ ] **Step 2:** Run it. Expected: FAIL (500, or the run missing).
- [ ] **Step 3:** Port `evfiles` to `RunDir`. The `_cached` signatures use `RunDir.watched()`. `grep -n '"run.json"\|"events.jsonl"\|"calls"\|"funnel.json"\|reexec-' webapp/*.py` returns nothing.
- [ ] **Step 4:** `uv run pytest webapp -q` passes. The mock fixtures are unchanged: regenerate with `uv run python -m webapp.tests.evidence_world <tmp> --mocks webapp/web/src/mocks/ev-fixtures.json`, and `git diff --stat` on the fixtures shows no change.
- [ ] **Step 5:** Commit `webapp: runs read through evidence.rundir.RunDir; EvidenceFiles' shared readers public`.

### Task 8: The process seam under `JobManager` (candidate 5)

**Files:**
- Create: `webapp/procs.py`
- Create: `webapp/tests/fakes.py`
- Modify: `webapp/jobs.py` (delete `process_start`, `alive`, `signal_group`; `JobManager.__init__` takes `processes`)
- Modify: `webapp/app.py` (pass `PosixProcesses()`)
- Modify: `webapp/tests/test_jobs.py`
- Create: `webapp/tests/test_procs_posix.py`

**Interfaces:**

```python
class Proc(Protocol):
    pid: int
    returncode: int | None
    async def wait(self) -> int: ...
class Processes(Protocol):
    async def start(self, argv: list[str], *, log: BinaryIO, cwd: Path, env: dict[str, str]) -> Proc: ...  # own session/group; OSError when it cannot start
    def start_token(self, pid: int) -> str | None: ...      # identity of a live process (/proc starttime); None when gone
    def signal(self, pid: int, how: Literal["term", "kill"]) -> None: ...   # to the whole group; a gone group is ignored
class PosixProcesses: ...                                    # today's code, moved
# webapp/tests/fakes.py
class FakeProcesses:
    started: list[list[str]]; signals: list[tuple[int, str]]
    def finish(self, pid: int, code: int = 0) -> None        # ends that fake process
    def set_alive(self, pid: int, token: str | None) -> None  # what start_token answers (orphan tests)
```

- `JobManager(settings, after=None, processes: Processes | None = None)`. The default is `PosixProcesses()`.
- `alive(step)` becomes a method: `self.processes.start_token(step.pid) == step.pid_start`.
- A fake `signal("term")` finishes the process with code `-15`, as a real SIGTERM would.

- [ ] **Step 1: Write the failing tests.** Rewrite `test_jobs.py` on `FakeProcesses`: no `sleep`, and no `skipif(os.name == "nt")` except in the POSIX file. Cases:
  - `test_model_lane_runs_one_at_a_time`
  - `test_needs_missing_skips_step`
  - `test_failed_optional_step_warns`
  - `test_cancel_queued_ends_at_once`
  - `test_cancel_running_sends_term_and_skips_rest`
  - `test_restart_keeps_live_orphan_and_watches_it`: `set_alive(pid, token)`, then `load()`; the job is `orphaned` and running. `set_alive(pid, None)` then fails it with the "exit status unknown" error.
  - `test_restart_fails_dead_job`
  - `test_shutdown_kills_after_grace`: monkeypatch `STOP_GRACE_S=0`; the signals are `[term, kill]`.

  `test_procs_posix.py` (skipped on Windows) keeps one real case: a `sh -c "sleep 30 & sleep 30"` group dies on `signal("term")`, and `start_token` returns None afterwards.
- [ ] **Step 2:** Run `uv run pytest webapp/tests/test_jobs.py -q`. Expected: FAIL (`JobManager` takes no `processes`).
- [ ] **Step 3:** Move the process code into `webapp/procs.py` and inject it.
- [ ] **Step 4:** `uv run pytest webapp -q` passes. `test_jobs.py` runs on Windows and finishes in under 5 s.
- [ ] **Step 5:** Commit `webapp jobs: Processes seam (POSIX adapter, fake in tests); job tests run on any OS without sleeps`.

### Task 9: A job plan per job kind (candidate 3)

**Files:**
- Modify: `webapp/evjobs.py` (`JobPlan`, `run_group`, `Commands.*` return plans, one `_start` in the router, `GET /run-group`; `PROPOSE_STEPS` built from `evidence.propose.common` names)
- Modify: `webapp/evmodels.py` (`RunGroup` response model)
- Regenerate: `webapp/web/openapi.json` and `src/api/schema.d.ts`
- Modify: `webapp/web/src/api/ev.ts` (`useRunGroup` hook)
- Modify: `webapp/web/src/components/flow/RunStep.tsx` (use the hook)
- Modify: `webapp/web/src/components/flow/CorpusStep.tsx` (use `job.refs.corpus`, not `${name}-mixed`)
- Modify: `webapp/web/src/lib/jobs.ts` and `jobs.test.ts` (delete `runGroup`)
- Test: `webapp/tests/test_evjobs_plans.py` (create; no HTTP, no subprocess)

**Interfaces:**

```python
@dataclass(frozen=True)
class JobPlan:
    kind: str                       # synth, run, rag-baseline, agent-baseline, score, compare, propose, freeze
    steps: list[JobStep]
    refs: dict[str, str]
    lane: Lane
    needs_gateway: bool
def run_group(protocol: ProtocolRef, extractors: str, strategy: str) -> str   # today's Commands.group body
# Commands.synth/run/rag_baseline/agent_baseline/score/compare/propose/freeze(request) -> JobPlan
# GET /api/ev/run-group?source=repo&name=rag-factuality&extractors=cascade&strategy=all -> {"group": "cascade"}
```

- `run` with `extractors == "regex-only"` has lane `cpu` and `needs_gateway=False`. Every other model kind has lane `model` and `needs_gateway=True`.
- The router's eight POST handlers each become `return await _start(c.<kind>(request), request)`. `_start` checks the gateway when `plan.needs_gateway`, then calls `jobs.submit(plan.kind, request.model_dump(), plan.steps, lane=plan.lane, refs=plan.refs)`.
- `Commands` calls only public `EvidenceFiles` methods (Task 7).

- [ ] **Step 1: Write the failing tests** in `test_evjobs_plans.py`. Build `Commands` over a copied evidence world with a `JobManager(processes=FakeProcesses())`.
  - `test_run_group_table`: the seven rows of today's `jobs.test.ts` `runGroup` cases, same inputs and same outputs.
  - `test_run_plan_argv`: `plan.steps[0].argv[3:]` equals `["evidence","run","--protocol",…,"--run-id","<corpus>"]`, with paths under the world. Also `plan.refs == {"run": "cascade~<corpus>", "corpus": "<corpus>"}`, `lane == "model"` and `needs_gateway`.
  - `test_regex_only_run_is_cpu_without_gateway`.
  - `test_score_plan_takes_latest_reexec_and_both_baselines`.
  - `test_propose_plan_resumes_after_existing_frame`: the steps are `["propose draft","propose critic","propose cards"]`, each needing the previous file.
  - `test_synth_plan_refs`: `{"corpus_set": n, "corpus": f"{n}-mixed"}`.
  - `test_get_run_group_endpoint` (TestClient): returns `{"group": "agentic-gaps"}` for the agentic protocol with gaps.
- [ ] **Step 2:** Run `uv run pytest webapp/tests/test_evjobs_plans.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement the Python side. Then run `uv run webapp openapi -o webapp/web/openapi.json && cd webapp/web && npm run gen:api`.
- [ ] **Step 4:** Frontend changes:
  - `useRunGroup(protocol, extractors, strategy)`, a react-query hook over `GET /api/ev/run-group`, used by `RunStep` to show where the run will appear;
  - `CorpusStep` takes the corpus from `job.refs.corpus`;
  - delete `runGroup` and its test;
  - in the mock, `handlers.ts` answers `/api/ev/run-group` from the recorded table (Task 10); until Task 10 lands, it answers from `EV_FIXTURES["/api/ev/run-group"]`, which `evidence_world.mock_paths` now records for every combination of the two repo protocols × `regex-only|cascade` × `all|gaps`.
- [ ] **Step 5:** `uv run pytest webapp -q` and `cd webapp/web && npm run typecheck && npm run lint && npm test` pass.
- [ ] **Step 6:** Commit `webapp: a JobPlan per job kind; run group named by the backend only (GET /run-group)`.

### Task 10: Write-contract scenarios shared by the backend and the mock (candidate 6)

**Files:**
- Create: `webapp/tests/write_contract.py` (scenarios plus a recorder)
- Create: `webapp/tests/test_write_contract.py`
- Create: `webapp/web/src/mocks/write-contract.json` (generated)
- Create: `webapp/web/src/mocks/contract.test.ts`
- Modify: `webapp/web/src/mocks/handlers.ts` (drop the rules it duplicates where the contract shows the backend's answer is reachable from recorded data: run-group from fixtures; conflict and refusal messages unchanged in the text but now checked)
- Modify: `webapp/tests/evidence_world.py` (`--mocks` also writes write-contract.json)

**Interfaces:**
- A scenario is `{"name": str, "method": "POST"|"PUT", "path": str, "body": dict, "status": int, "response": dict}`.
- `status` and `response` are recorded from the real backend. The world for this is a fresh `evidence_world.build`, a `JobManager(processes=FakeProcesses())`, and `gateway_problem` monkeypatched to `None`.
- Before comparing, `response` is normalised: job `id`, every `*_at` field, `pid`, `pid_start` and argv paths are replaced by `"*"`. The mock is compared on the fields both produce: `status`, `detail`, `refs`, `lane`, `kind`, `problems`.
- `SCENARIOS` (Python list, in this order):
  1. synth with a new name, 202;
  2. synth reusing the world's corpus set name, 409;
  3. run cascade on the world's mixed corpus with a new name, 202;
  4. run on an existing run name, 409;
  5. run on an unknown corpus, 404;
  6. rag-baseline on a corpus that already has an answer, 409;
  7. propose on the frozen proposal, 409;
  8. propose with a new name, 202;
  9. PUT decisions on the world's unfrozen proposal with one missing reason, one non-default choice by `model`, one unknown choice, and one `custom` without a value, 200 with those four `problems`;
  10. freeze on a proposal with problems, 409.

  The contract runs scenarios in order on one world, so 8 creates what 9 and 10 need. In the mock, the test ends scenario 8's job with `finishJob` before running 9.

- [ ] **Step 1: Write the failing tests.**
  - `test_write_contract.py::test_recorded_contract_is_current`: running the scenarios on a fresh world gives exactly `write-contract.json`. The failure message says `regenerate: uv run python -m webapp.tests.evidence_world <tmp> --mocks webapp/web/src/mocks/ev-fixtures.json`.
  - `contract.test.ts`: for each scenario, `fetch` against the MSW mock (after `resetDb()` once, in order). Assert status, `detail`, `refs`, `lane`, `kind` and `problems` equal the recorded ones.
- [ ] **Step 2:** Generate the file and run both tests. Expected: the Python test passes. vitest FAILs on every scenario where the mock's rules drifted from the backend: that drift is what this task exists to find.
- [ ] **Step 3:** Fix `handlers.ts` until `contract.test.ts` passes. Change only the mock: the backend is the reference. Delete any mock rule that no scenario or flow test needs.
- [ ] **Step 4:** Run `uv run pytest webapp -q`, `cd webapp/web && npm test && npm run build`. All pass; commit the rebuilt `dist/`.
- [ ] **Step 5:** Commit `webapp: write-contract scenarios recorded from the backend; the mock checked against them`.

### Task 11: Docs, full verification, push

**Files:**
- Modify: `docs/STATE.md` (the test count; a short "Architecture (20 Oct)" note naming `jsonio`, `modelcall`, `RunDir`, `JobPlan`, `Processes`, the write contract)
- Modify: `README.md` (where `gold/llm.py` or `agent/canonical.py` is named)
- Modify: `docs/slurm-evidence-runbook.md` (one step for Codex: rerun the RAG baseline and one cascade run against the live gateway, and confirm no "Event loop is closed" in `calls/*.json` errors and that cached reruns make 0 model calls)

- [ ] **Step 1:** Run `uv run pytest -q` and `cd webapp/web && npm run typecheck && npm run lint && npm test && npm run build`. Expected: all pass. Record the count.
- [ ] **Step 2:** Run `grep -rn "gold.llm\|agent.canonical\|asyncio.run(" --include=*.py evidence evaluation gold synth webapp modelcall`. Expected: only CLI entry points' `asyncio.run` of non-model coroutines, if any. List each one left and why.
- [ ] **Step 3:** Update the docs and commit `docs: architecture deepening (20 Oct), test count, runbook live check`.
- [ ] **Step 4:** `git push -u origin arch/deepen`. Expected: the branch is on origin. Report the URL.
