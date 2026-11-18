# synth3 Replay (plan 5 of 5): the readable evidence program and the 5-re-run measurement

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** every finished run of the system downloads as one readable Python file that rebuilds its answer (every
fixed kind and the written answer) from the facts it used, with no papers, no AI and no repo; and one folder's runs
are re-run 5 times with no cache, and a report gives the share of identical model calls, item stability and whether
the final answer stays the same, the LLM extractors and the agentic extractor apart.

**Architecture:**
- **Reading a run's answer** (`evidence/readable/runview.py`): one place says which runs can be rebuilt, what the
  recorded answer text is (the fixed kinds' plain-word lines, `kindtext.kind_lines`; the written answer's text) and a
  projection of the recorded answer (`checked_view`) that a rebuild must equal. The web page, the generator and the
  measurement all read it.
- **The rules, copied** (`evidence/readable/rules/*.py`): stdlib-only modules, one per kind (effect and consistency
  share one), that rebuild the answer from the facts the rules used and write the plain-word lines. They are real
  modules (unit-tested by import) and their text is pasted into each program, so the program carries its own copy
  (spec §9, builder's call: no import from the repo). Drift tests pin every copied constant to the engine's.
- **The program** (`evidence/readable/program.py`): from a run folder, the facts the kind's rules used become values
  (`FACTS_USED`), each with a comment naming its paper, section and exact quote; the per-paper choices of the engine
  (`PAPERS`), the rule settings, any model-written text (`MODEL_TEXT`, marked as such), two recorded sha256s (answer
  text, rebuilt values), the pasted rules and a `main` that prints the answer and checks it. `evidence program RUN
  --out FILE` writes it; the `/system` page downloads it.
- **No cache, every call** (`evidence reexec --all-calls`): the existing re-execution, with every extractor bypassed
  and the run's own stage calls (the writer, the re-check, the claims, ...) asked again. Fresh replies never enter the
  record cache; the re-run keeps its own `calls.jsonl`, so each model call's request and reply can be compared.
- **The measure** (`evidence/stability.py`, `synth3 reexec`): reads each model-call record by its shape (engine or
  agentic), pairs the re-run's calls with the original's by slot, then by request; counts identical replies per group
  (LLM extractors, agentic extractor, stages, names check) with their temperatures and served models; item stability
  over `evidence.jsonl` and by extractor kind (from `reexec.json`); same final answer text and same headline. The
  synth3 command re-runs one folder's kept system runs 5 times under `data/synth3/results/<d>/reexec/` (git-ignored).

**Tech Stack:** Python >= 3.13 for the repo (the program itself: Python 3.9+, standard library only), pydantic,
pydantic-ai `FunctionModel` fakes, FastAPI `TestClient`; React 19 + TanStack Query + Vitest + MSW. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-16-multi-domain-benchmark-design.md` (§2 "a downloadable, readable program
per run", §9 "Evidence as a program" with its Measurement, §10 "how the readable program is generated", §10b "the
readable program rebuilds rule-based answers fully and carries model-written text as recorded text", §11). Read with
it: plan 4 `docs/superpowers/plans/2026-11-19-synth3-system.md` (its decision 2: the written answer is a recorded run
stage so this plan can read it) and its handoff `docs/superpowers/plans/2026-11-19-synth3-system-handoff.md`.

**The five plans:** 1 worlds (merged); 2 real papers (`synth3-real`); 3 questions, sheets, judge (`synth3-questions`);
4 the system (`synth3-system`); **5 this plan** (branch `synth3-replay`, cut from `synth3-system` @ e8da1e8e).

## Global Constraints

- **Git:** work on the existing branch `synth3-replay`; never switch, merge or push. Stage files by name only; never
  stage `backend/agent/tests/test_prompts.py`. End every commit message with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **No cluster run, no new LLM, no new prompt:** every model call in a test is a fake (`provider_of(FunctionModel)` as
  `evidence/tests/test_plan_run.py`, `writer_model` of `evidence/tests/test_written_stage.py`, `system_model` of
  `synth3/tests/systemrun.py`); no test opens a socket. Re-runs ask the prompts the runs already used. Every real run
  command goes on Aditya's list (Task 11).
- **Human gates and blindness (plans 3-4) unchanged:** nothing here writes a question, plan, sheet, answer record or
  mark; re-runs go under `data/synth3/results/<d>/reexec/`, never under `results/<d>/runs/`, so `collect`, `judge`
  and `system-run` never see them; no program text reaches a judge. A test proves `load_answers` is unchanged and the
  original run folder is byte-identical after a measurement (Task 8).
- **Data stays local:** never commit anything under `data/synth3/built/`, `data/synth3/pools/`, `data/synth3/results/`,
  nor any generated program (it quotes renamed real papers). Tests write only under `tmp_path`.
- **Hashed files (`backend/README.md`, "Hashed files: never edit"):** untouched. This plan edits `evidence/calls.py`,
  `evidence/engine.py`, `evidence/replay.py`, `evidence/cli.py` (none listed) by small additions; new behaviour is in
  new modules. `backend/synth2` is read-only.
- **Boundaries:** `evidence` never imports `synth3` or `webapp` (`tests/test_boundaries.py`); `synth3` may import
  `evidence`; `webapp` may import both. Source under `evidence/`, `webapp/`, `frontend/` holds no domain word
  (`evidence/tests/test_no_topic_words.py`): rule texts and program texts use generic words only.
- **The program's claim (spec §9, exact meaning):** "replayable and checkable": the same recorded facts always rebuild
  the same answer, and every fact points to exact text in a paper; the tools are fixed functions, the agent's choice of
  tool calls is not fixed, but every call is recorded. No text, docstring or report line claims that the same question
  always gives the same answer, that extraction is deterministic or that tool use is deterministic.
- **Model-written text (spec §9, builder's call):** carried as pasted text marked "written by a model from the results
  above, not rebuilt by this file".
- **The program file:** standard library only (`python -I -S` runs it), UTF-8, LF line ends, no import from the repo,
  deterministic bytes for one run folder (no date, no absolute path of this machine), prints the same bytes every time
  (`sys.stdout.reconfigure(encoding="utf-8", newline="\n")`).
- **Prompt policy (`docs/prompt-writing.md`):** no prompt changes. The measurement records what the policy asks of an
  evaluation: settings (temperature), served model identities, attempts (calls), and keeps every re-run folder.
- **Commands:** backend tests from `backend/`: `uv run pytest -q <files>`; the whole suite from `backend/`:
  `uv run pytest -q --ignore evaluation/tests/test_agentic_agent.py --ignore evaluation/tests/test_runner.py` (the 10
  `agent/tests` import errors on Windows are known). Frontend from `frontend/`: `uv run --group frontend npm test`,
  `uv run --group frontend npm run typecheck`, `uv run --group frontend npm run lint`, `uv run --group frontend npm run
  build`. API types: from the repo root `uv run webapp openapi -o frontend/openapi.json`, then from `frontend/`
  `uv run --group frontend npm run gen:api`; commit `frontend/openapi.json` and `frontend/src/api/schema.d.ts` when an
  API model changes; stage `frontend/dist` by path when the frontend changes.
- **Text files:** every read and write passes `encoding="utf-8"`; JSON written by synth3 with
  `jsonio.write_json_atomic`.
- **No `...` in tests:** every test below is written out, or its assertions are named in words.

## Review Focus

- **Odd characters in names and quotes breaking the program:** a quote holding a newline, `"""`, a backslash, or a
  label with `≥` must leave every comment on one line, the file valid Python, and the output printable on a Windows
  console (Task 5 test `test_odd_text_stays_on_one_line_and_prints_anywhere`).
- **Numbers that print differently:** an int value `10`, a float `1e-05`, values equal after rounding to 3 decimals; the
  rebuilt lines and values must equal the engine's byte for byte, and a best value `45` must be compared as the
  engine stores it, `45.0` (Task 2 test `test_numbers_keep_their_form`, Task 3 test
  `test_best_whole_number_values_are_compared_as_the_engine_stores_them`, Task 4 test
  `test_fact_texts_rebuild_from_values`, Task 5 test `test_whole_number_best_values_pass_the_check`).
- **A program edited by hand:** a changed fact or sentence must make the program say `Check FAILED` and exit 1, never
  print a different answer as if it were the run's (Task 5 test `test_a_changed_fact_fails_the_check`).
- **The original run replaced after a measurement started:** `system-run` reran `d01`; earlier re-runs of the old `d01`
  must be moved aside, never mixed into the new report (Task 8 test `test_a_replaced_run_moves_old_reruns_aside`).
- **A run that cannot be measured or rebuilt:** no `calls.jsonl`, a failed writer call, a lines plan, a run still being
  written: each gets a named reason and the rest go on (Task 1, Task 7, Task 8 tests).

---

## File structure

| File | Responsibility |
|---|---|
| `backend/evidence/readable/__init__.py` | exports `read_run`, `read_refusal`, `refusal`, `inputs_of`, `answer_text`, `checked_view`, `headline`, `program_of_run`, `NotRebuilt` |
| `backend/evidence/readable/runview.py` | which runs can be rebuilt; the recorded answer text, view and headline |
| `backend/evidence/readable/inputs.py` | per kind: the facts used, the per-paper choices and settings, from a `RunAnswer` |
| `backend/evidence/readable/rules/common.py` | stdlib: shared texts, reason text, line cut, sha256s, `main` |
| `backend/evidence/readable/rules/effect.py` | stdlib: effect and consistency rebuild and lines |
| `backend/evidence/readable/rules/best.py` | stdlib: best rebuild and lines |
| `backend/evidence/readable/rules/inventory.py` | stdlib: inventory rebuild and lines |
| `backend/evidence/readable/rules/written.py` | stdlib: fact texts, the code checks, the accepted reply, the paper ids |
| `backend/evidence/readable/program.py` | the program text from inputs; `program_of_run` |
| `backend/evidence/stability.py` | the re-run measure of one run and its rendering |
| `backend/synth3/remeasure.py`, `backend/synth3/rcli.py` | `synth3 reexec`: one folder, N re-runs, the report |
| `backend/webapp/evsystem.py` | `GET /system/runs/{rid}/program`; `SystemSteps.program_refused` |
| `frontend/src/routes/system/AnswerBox.tsx` | the download link |

---

### Task 1: Reading a run's answer

**Files:**
- Create: `backend/evidence/readable/__init__.py`, `backend/evidence/readable/runview.py`,
  `backend/evidence/tests/test_readable_runview.py`

**Interfaces:**
- Consumes: `RunDir` (state, record, settings, items, register_pack, roles), `PaperIndex.of_corpus`, `Corpus`,
  `evidence.protocol.parse`, `load_plan`, `PLAN_FILE`, `PROTOCOL_FILE`, `ANSWER_FILE`; `kindtext.kind_lines`,
  `kindtext.plan_names`; `written.STAGE`; `reasoner.from_json`, `REASON_FILE`.
- Produces in `runview.py`:
  - `KINDS = ("effect", "consistency", "inventory", "best", "written")`; `class NotRebuilt(ValueError)`.
  - Refusal texts (exact copy): `NOT_COMPLETE = "the run is not complete (state {state})"`;
    `NO_RULES = "the run has no protocol.yaml (a baseline run): there are no rules to rebuild"`;
    `LINES = "a plan answered by its lines (the plan page's own answer) is not rebuilt by a readable program yet;
    choose a fixed kind or a written answer"`; `KIND_NOT_REBUILT = "the kind {kind} is not rebuilt by a readable
    program yet"`; `SUBSETS = "an answer by subsets (the protocol's moderators) is not rebuilt by a readable program
    yet"`; `NAME_GROUPS = "a {kind} run with the names step on is not rebuilt by a readable program yet (its rules read
    the name groups)"`; `NO_WRITTEN = "the run has no written answer"`; `WRITER_FAILED = "the written answer's model
    call failed: {reason}; run it again with retry"`; `NOT_FOUND_AGAIN = "the {what} the run used for {paper} could
    not be found again"` (raised by Tasks 2-3's inputs).
  - `@dataclass(frozen=True) class RunAnswer`: `run: Path`, `kind: str` (one of `KINDS`), `protocol: Protocol`,
    `roles: RoleMap`, `plan: Plan | None`, `names: dict[str, str]` (`plan_names(plan)`, `{}` for a protocol run),
    `answer: dict` (the kind's answer: answer.json `synthesis` of a plan run, answer.json of a protocol run;
    `written-answer.json` for `written`), `items: dict[str, list[Item]]` (by paper, manifest order),
    `texts: dict[str, str] | None` (paper id -> text when the corpus is readable, else None), `record: dict`
    (run.json), `outputs: dict[str, str]` (run.json `outputs`), `inferred: Any | None = None` (the reasoner's
    inferences, below).
  - `read_run(run: Path | str, corpus: Path | str | None = None, *, texts: bool = True) -> RunAnswer`: refusals
    checked in this order: `RunDir.state != "complete"` → `NOT_COMPLETE`; no protocol.yaml → `NO_RULES`; a plan run
    with `answer_by == "lines"` → `LINES`; protocol kind not in effect/consistency/inventory/best →
    `KIND_NOT_REBUILT`; effect or consistency with `synthesis.moderators` → `SUBSETS`; best or inventory with settings
    `names == "on"` → `NAME_GROUPS`; written with no `written-answer.json` → `NO_WRITTEN`, with `{"failed": r}` →
    `WRITER_FAILED`. `inferred` is `reasoner.from_json(<reason.json>)` when the run has `reason.json` (reason on),
    else None: Tasks 2-3 pass it to the engine's study functions when they find each paper's pair or values again, as
    the engine did (review I2: this keeps reasoned runs rebuildable with one argument, smaller than a refusal and its
    tests; the program itself never needs the inferences, since each paper's measure and values are recorded in
    `PAPERS`). `corpus` defaults to run.json
    settings' corpus; when it has no readable `manifest.json` the items are grouped by their first span's file stem
    (in evidence.jsonl order; this assumes the stem is the paper id, as every corpus the engine writes names its
    papers `papers/<id>.md`) and `texts` is None. `texts=False` never reads the paper texts (`texts` None): the
    measurement (Task 7) needs only the answer.
  - `read_refusal(run, corpus=None) -> str | None`: the `NotRebuilt` text of `read_run`, or None. (Task 3 adds
    `refusal`, which also builds the program's inputs.)
  - `view_of(kind: str, answer: dict) -> dict`, the projection a rebuild must equal (item ids left out):
    - effect: `{label, counts, supporting, contradicting, neutral, undetermined, duplicates, flags, studies: [{document,
      direction, delta, metric, treatment_value, control_value, claim, claim_agrees, reason, flags, duplicate_of}]}`
      (`treatment_value` = `treatment.value` or None; `claim` = `author_claim.direction` or None; `claim_agrees` =
      `author_claim.agrees_with_data` or None; `reason` the entry's reason dict or None);
    - consistency: `{metric, agreeing, disagreeing, undetermined, studies: [{document, claim, direction, agrees,
      reason}]}`;
    - best: `{metric, wins, winner, tied, studies: [{document, winner, tied, values, reason}]}`;
    - inventory: `{target, entries: [{name, aliases, papers}]}`;
    - written: `{status, answer_text, tries: [<problems of each try>], sentences, fact_texts: [<each fact's text>]}`.
  - `checked_view(ra: RunAnswer) -> dict` = `view_of(ra.kind, ra.answer)`.
  - `answer_text(ra: RunAnswer) -> str`: written → `answer["answer_text"]`; a fixed kind →
    `"\n".join(l.text for l in kind_lines(ra.protocol, ra.answer, ra.names))` (the text plan 4 gives the judge, before
    its 12,000-character cut).
  - `headline(ra: RunAnswer) -> str`: effect → the label; consistency → `"agreeing <a>, disagreeing <d>"`; best → the
    winner, `"tie: <a>, <b>"`, or `"none"`; inventory → the entry names joined by `", "`; written → the status.

- [ ] **Step 1: Write the failing tests** (`plan_run`, `make_plan` from `evidence.tests.test_plan_run`;
  `written_run` from `evidence.tests.test_written_stage`; `with_answer` from `evidence.plan`):

```python
GOOD = lambda p: {"sentences": [{"text": "Retrieval helped.", "says": "finding", "facts": [1]}]}

@pytest.mark.parametrize("by, target", [("effect", None), ("consistency", None), ("inventory", "condition"),
                                        ("inventory", "metric"), ("best", None)])
def test_a_fixed_kind_run_reads_as_its_lines(tmp_path, by, target):
    root = plan_run(tmp_path, with_answer(make_plan(), by, target))
    ra = read_run(root)
    answer = json.loads((root / "answer.json").read_text(encoding="utf-8"))["synthesis"]
    protocol = parse((root / "protocol.yaml").read_text(encoding="utf-8"))
    assert ra.kind == by and ra.answer == answer and ra.names == plan_names(make_plan())
    assert answer_text(ra) == "\n".join(l.text for l in kind_lines(protocol, answer, ra.names))
    assert list(ra.items) == list(DOCS) and ra.texts is not None   # DOCS of evidence/tests/conftest.py

def test_a_written_run_reads_as_its_text(tmp_path):
    root = written_run(tmp_path, GOOD)
    out = json.loads((root / "written-answer.json").read_text(encoding="utf-8"))
    ra = read_run(root)
    assert ra.kind == "written" and answer_text(ra) == out["answer_text"] and headline(ra) == "ok"
    assert checked_view(ra) == {"status": "ok", "answer_text": out["answer_text"],
                                "tries": [t["problems"] for t in out["tries"]], "sentences": out["sentences"],
                                "fact_texts": [f["text"] for f in out["facts"]]}

def test_runs_that_cannot_be_rebuilt_say_why(tmp_path):
    assert read_refusal(plan_run(tmp_path / "a")) == LINES
    failed = written_run(tmp_path / "b", lambda p: RuntimeError("gateway down"))
    assert read_refusal(failed).startswith("the written answer's model call failed: ")
    assert read_refusal(failed).endswith("; run it again with retry")
    gone = plan_run(tmp_path / "c", with_answer(make_plan(), "effect", None))
    (gone / "run.json").unlink()
    assert read_refusal(gone) == "the run is not complete (state unsealed)"
    with pytest.raises(NotRebuilt, match="not complete"):
        read_run(gone)

def test_a_reasoned_run_carries_its_inferences_and_texts_can_be_skipped(tmp_path):
    root = plan_run(tmp_path, with_answer(make_plan(), "consistency", None))   # plan_run reasons (reason on)
    assert (root / "reason.json").is_file() and read_run(root).inferred is not None
    assert read_run(root, texts=False).texts is None

def test_without_the_corpus_items_group_by_file_and_texts_are_none(tmp_path):
    root = plan_run(tmp_path, with_answer(make_plan(), "effect", None))
    shutil.rmtree(tmp_path / "corpus")
    ra = read_run(root)
    assert ra.texts is None and set(ra.items) <= set(DOCS) and answer_text(ra)

def test_views_leave_ids_out_and_headlines_name_the_result():
    best = {"metric": "accuracy", "wins": {"rag": 2}, "winner": "rag", "tied": [], "studies": [
        {"document": "S001", "winner": "rag", "tied": [], "values": {"rag": 0.6, "closed_book": 0.5}, "reason": None}]}
    assert view_of("best", best) == best
    inv = {"target": "condition", "entries": [{"name": "A", "aliases": ["a"], "papers": ["S001"],
                                               "items": ["condition-0123456789abcdef"]}]}
    assert view_of("inventory", inv) == {"target": "condition", "entries": [{"name": "A", "aliases": ["a"],
                                                                              "papers": ["S001"]}]}
```

  plus `test_headlines`: effect `{"label": "supported", ...}` → `"supported"`; consistency with 2 agreeing, 1
  disagreeing → `"agreeing 2, disagreeing 1"`; best tied `["a", "b"]`, winner None → `"tie: a, b"`; best with neither →
  `"none"`; inventory entries A, B → `"A, B"` (build `RunAnswer` directly with `run=Path("x")`, `texts=None`,
  `record={}`, `outputs={}`).
- [ ] **Step 2: Run** `uv run pytest -q evidence/tests/test_readable_runview.py`. Expected: FAIL (`ModuleNotFoundError:
  evidence.readable`).
- [ ] **Step 3: Implement** `runview.py` and `__init__.py` (re-exporting the names above).
- [ ] **Step 4: Run** the test file and `uv run pytest -q tests/test_boundaries.py evidence/tests/test_no_topic_words.py`.
  Expected: PASS.
- [ ] **Step 5: Commit** the three files: `evidence: read a run's answer for rebuilding (kinds, text, view, refusals)`.

### Task 2: The rules, copied: common texts, effect and consistency

**Files:**
- Create: `backend/evidence/readable/rules/__init__.py` (empty), `rules/common.py`, `rules/effect.py`,
  `backend/evidence/readable/inputs.py` (this task: effect and consistency), `backend/evidence/tests/readable_cases.py`
  (test builders), `backend/evidence/tests/test_readable_effect.py`

**Interfaces:**
- Consumes: Task 1 (`RunAnswer`, `view_of`, `answer_text`); `synthesis.Types`, `synthesis.study`,
  `synthesis.experiment_key`; `kinds.of`; `rules.*`; `kindtext.*`; `kinds.consistency.NO_CLAIM`.
- **Rule-file convention** (every file in `rules/`; the generator relies on it): a docstring; then the import lines
  (standard library only; a line ending in `# program: drop` is a test-only relative import, e.g.
  `from .common import cut_lines  # program: drop`); then a line exactly `# --- rules ---`; then the body. No other
  import anywhere. Long plain names; one short step per line; a docstring on every function.
- Produces in `rules/common.py` (constants are exact copies of the engine's, pinned by tests):
  `CANT_TELL_LINE`, `MAX_KIND_LINES`, `SAYS`, `LABEL_TEXT`, `GROUPS`, `INVENTORY_TARGETS` (= `kindtext`'s);
  `REASON_TEMPLATES` (= `synthesis.REASONS`); `BEST_REASON_TEMPLATES` (= `kinds.best.REASONS`);
  `CHECK_OK = "Check: this is the answer the run recorded."`;
  `CHECK_FAILED = "Check FAILED: this is not the answer the run recorded."`;
  `NOTE_WRITTEN = "The sentences were written by a model from the facts above, not rebuilt by this file; this file
  re-ran the code checks and added the paper ids."`; `FAILED_NOTE = "The model's answer failed its checks: {problems}"`;
  functions `fold(name) -> str`, `join_words(words) -> str` (`", ".join`), `number_text(value) -> str` (`f"{value:.10g}"`),
  `reason_text(reason, settings, names) -> str` (kindtext `_reason`, reading `settings["kind"]`, `settings["treatment"]`,
  `settings["control"]`, `settings["measure"]` instead of the protocol), `cut_lines(lines: list[str]) -> list[str]`
  (`MAX_KIND_LINES`, then `... and <n> more.`), `text_sha256(text) -> str`, `values_sha256(view) -> str` (sha256 of
  `json.dumps(view, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` in UTF-8), and
  `main(argv: list[str], data: dict) -> int` (Task 5 fills its output; this task defines it as below).
  `main`: `view = data["rebuild_answer"](data["RULE_SETTINGS"], data["FACTS_USED"], data["PAPERS"], data["MODEL_TEXT"])`;
  `text = "\n".join(data["answer_lines"](data["RULE_SETTINGS"], view, data["NAMES_OF_THINGS"]))`; reconfigure stdout
  (Global Constraints); `--json` prints `json.dumps({"kind": data["KIND"], "answer": view, "text": text},
  ensure_ascii=False, sort_keys=True)` and returns 0. Otherwise the check is made first: when `text_sha256(text) ==
  data["RECORDED_ANSWER_SHA256"]` and `values_sha256(view) == data["RECORDED_VALUES_SHA256"]` it prints `text`, an
  empty line, the notes (`data["notes_of"](view)`, Task 4; `[]` for fixed kinds), then `CHECK_OK`, and returns 0;
  else it prints `CHECK_FAILED` first (so no reader takes the changed text for the run's answer), an empty line,
  `text`, the notes, and returns 1 (review M14).
- Produces in `rules/effect.py` (`settings["kind"]` is `effect` or `consistency`):
  `direction_and_difference(treatment_value, control_value, higher_is_better, smallest_real_difference) -> tuple[str,
  float]` (= `rules.effect`); `claim_agrees(claim, direction, claim_map) -> bool`; `label_from_counts(counts,
  label_rows) -> str` (= `rules.label`, rows as `[{"when": {...}, "then": ...}]`); `VALUE_DECIMALS = 3`;
  `repeated_studies(studies) -> dict[str, str]` (= `rules.duplicates`); `large_effect_papers(differences, factor,
  min_studies, smallest_real_difference) -> list[str]` (= `rules.large_effects`, `statistics.median`);
  `NO_CLAIM` (= `consistency.NO_CLAIM`); `rebuild_answer(settings, facts, papers, model_text) -> dict` (the Task 1 view
  of the kind); `answer_lines(settings, view, names) -> list[str]` (= kindtext `_effect` / `_consistency`, cut);
  `notes_of(view) -> list[str]` (`[]`: a fixed kind prints no note; every rule file but common defines it).
- Produces in `inputs.py`: `@dataclass class ProgramInputs`: `kind: str`, `question: str`, `settings: dict`
  (`RULE_SETTINGS`), `facts: dict[str, dict]` (`FACTS_USED`, keys `F1`, `F2`, ... in order of first use), `papers:
  list[dict]` (`PAPERS`), `model_text: list` (`MODEL_TEXT`), `names: dict[str, str]`, `spans: dict[str, list[dict]]`
  (fact key -> `[{paper, role, start, exact}]`, for the comments only). `effect_inputs(ra: RunAnswer) -> ProgramInputs`
  (both kinds):
  - settings: `{kind, treatment, control, metrics: [{canonical, higher_is_better}], measure: <first canonical>,
    smallest_real_difference: min_effect, claim_map, label_rows: [{when, then}], flags: {duplicates, large_effect:
    {factor, min_studies}}}`;
  - facts: a measured value `{paper, item, type: "measured value", value, dataset, thing: F, measure: F}`, a compared
    thing `{paper, item, type: "compared thing", label, side}`, a measure `{paper, item, type: "measure", name,
    canonical}`, an author claim `{paper, item, type: "author claim", direction}`; fields read by pack role
    (`synthesis.Types.of(ra.protocol, ra.roles)`), values as recorded (an int stays an int);
  - papers, in the recorded studies' order: a determined study `{paper, measure: <entry metric>, treatment_value: F,
    control_value: F, claim: F | None, experiment_setting: synthesis.experiment_key(entry, items) }`; an undetermined
    one `{paper, could_not_be_read: <entry reason>, claim: F | None}`. For consistency (whose answer holds no pair) the
    pair comes from `synthesis.study(protocol, doc, items, None, roles=roles, inferred=ra.inferred)` for each study
    whose recorded direction is not `undetermined`; when that study's direction differs from the recorded one,
    `NotRebuilt(NOT_FOUND_AGAIN.format(what="pair", paper=doc))`.
- Produces in `tests/readable_cases.py`: `NAMES = plan_names(make_plan())`;
  `case_protocol(by="effect", target=None, direction="higher") -> Protocol` (`parse(kind_protocol(with_answer(
  make_plan(direction=direction), by, target)).decode("utf-8"))`); `item(type, fields, links=None, paper="S001",
  exact="0.5", start=0, role="value")` (as `test_written.item`); `study_items(paper, t, c, *, claim=None,
  dataset=None, t_label="Method K", c_label="Usual method", start=0) -> list[Item]` (a `rag` condition, a
  `closed_book` condition, metric `accuracy` named "Yield" higher-is-better, two measurements, optionally an author
  claim; `t=None` leaves out the treatment value and condition, `c=None` the control's); `case_answer(protocol,
  by_paper, kind, names=NAMES) -> RunAnswer` (runs `kinds.of(protocol).answer(protocol, list(by_paper), by_paper,
  roles=protocol.roles())` and wraps it with `run=Path("case")`, `plan=None`, `names=names`, `texts=None`,
  `record={}`, `outputs={}`, `inferred=None`); `stdlib_only(path: Path) -> set[str]`: the top-level modules a rule file imports once its
  `# program: drop` lines are removed (AST walk over `Import` and level-0 `ImportFrom`), after asserting the file holds
  exactly one `# --- rules ---` line.

- [ ] **Step 1: Write the failing tests:**

```python
from evidence.readable.rules import common, effect as rules_effect

ALLOWED = set(sys.stdlib_module_names) | {"__future__"}

def rebuilt(ra):
    i = effect_inputs(ra)
    view = rules_effect.rebuild_answer(i.settings, i.facts, i.papers, i.model_text)
    return view, rules_effect.answer_lines(i.settings, view, i.names)

def test_effect_rebuilds_label_counts_flags_and_lines():
    p = case_protocol()
    by_paper = {"S001": study_items("S001", 0.62, 0.50, claim="improves"),
                "S002": study_items("S002", 0.40, 0.55, claim="improves"),    # the claim disagrees
                "S003": study_items("S003", 0.62, 0.50),                      # repeats S001
                "S004": study_items("S004", 0.505, 0.50),                     # inside the neutral band
                "S005": study_items("S005", 0.70, None),                      # no control
                "S006": study_items("S006", 1.40, 0.50)}                      # a large effect
    ra = case_answer(p, by_paper, "effect")
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and "\n".join(lines) == answer_text(ra)
    assert view["duplicates"] == ["S003"] and view["undetermined"] == ["S005"]
    assert view["flags"]["claim_disagrees"] == ["S002"] and view["flags"]["large_effect"] == ["S006"]

def test_numbers_keep_their_form():
    p = case_protocol(direction="lower")
    ra = case_answer(p, {"S001": study_items("S001", 10, 12), "S002": study_items("S002", 1e-05, 2e-05),
                         "S003": study_items("S003", 0.1234564, 0.1234561)}, "effect")
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and "\n".join(lines) == answer_text(ra)
    assert common.values_sha256(view) == common.values_sha256(checked_view(ra))   # 10 stays 10, never 10.0

def test_no_readable_paper_says_cant_tell():
    ra = case_answer(case_protocol(), {"S001": study_items("S001", None, 0.5)}, "effect")
    view, lines = rebuilt(ra)
    assert view["label"] == "insufficient" and lines[0] == common.CANT_TELL_LINE and view == checked_view(ra)

def test_consistency_rebuilds_agreement_and_no_claim():
    p = case_protocol("consistency")
    ra = case_answer(p, {"S001": study_items("S001", 0.62, 0.5, claim="improves"),
                         "S002": study_items("S002", 0.40, 0.55, claim="improves"),
                         "S003": study_items("S003", 0.62, 0.4),
                         "S004": study_items("S004", None, 0.5, claim="worsens")}, "consistency")
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and "\n".join(lines) == answer_text(ra)
    assert view["agreeing"] == ["S001"] and view["disagreeing"] == ["S002"]
    assert view["studies"][2]["reason"] == {"code": "no_claim", "text": "no author claim found"}

def test_repeats_use_the_experiment_setting():
    rows = [("S1", "a", 1.0, 2.0, "x"), ("S2", "a", 1.0, 2.0, "y"), ("S3", "a", 1.0004, 2.0, "x"), ("S4", "a", 1, 2, None)]
    assert rules_effect.repeated_studies(rows) == rules.duplicates(rows) == {"S3": "S1"}

def test_the_copies_match_the_engine():
    assert common.REASON_TEMPLATES == synthesis.REASONS and common.BEST_REASON_TEMPLATES == best.REASONS
    assert (common.CANT_TELL_LINE, common.MAX_KIND_LINES) == (kindtext.CANT_TELL_LINE, kindtext.MAX_KIND_LINES)
    assert (common.SAYS, common.LABEL_TEXT, common.GROUPS, common.INVENTORY_TARGETS) == (
        kindtext.SAYS, kindtext.LABEL_TEXT, kindtext.GROUPS, kindtext.INVENTORY_TARGETS)
    assert rules_effect.NO_CLAIM == consistency.NO_CLAIM and rules_effect.VALUE_DECIMALS == rules.VALUE_DECIMALS

@pytest.mark.parametrize("name", ["common", "effect"])
def test_a_rule_file_imports_only_the_standard_library(name):
    assert stdlib_only(Path(evidence.readable.rules.__file__).parent / f"{name}.py") <= ALLOWED
```

- [ ] **Step 2: Run** `uv run pytest -q evidence/tests/test_readable_effect.py`. Expected: FAIL (`ImportError`).
- [ ] **Step 3: Implement** `common.py`, `effect.py` (the bodies follow `synthesis.answer`, `synthesis.flag`,
  `consistency.answer` and `kindtext._effect`/`_consistency` on the values above: a determined study's direction and
  difference from its two values with its measure's `higher_is_better` and `smallest_real_difference`; repeats over
  determined studies as `(paper, measure, treatment value, control value, experiment_setting)` when
  `flags.duplicates`; large effects over determined non-repeated differences; `claim_disagrees` where the claim
  disagrees; groups, counts, label), `inputs.py` (`ProgramInputs`, `effect_inputs`) and `readable_cases.py`.
- [ ] **Step 4: Run** the test file. Expected: PASS.
- [ ] **Step 5: Commit** the six files: `evidence: the readable program's rules for effect and consistency, copied and pinned`.

### Task 3: The rules, copied: best and inventory

**Files:**
- Create: `backend/evidence/readable/rules/best.py`, `rules/inventory.py`, `backend/evidence/tests/test_readable_best_inventory.py`
- Modify: `backend/evidence/readable/inputs.py` (`best_inputs`, `inventory_inputs`, `inputs_of`, `refusal`),
  `backend/evidence/readable/__init__.py` (export `refusal`, `inputs_of`)

**Interfaces:**
- Consumes: Tasks 1-2 (`ProgramInputs`, rule-file convention, `common`, `readable_cases`); `kinds.best.study`,
  `kinds.best.tally`; `kinds.inventory.study`, `name_field`, `name_of`.
- Produces in `rules/best.py`: `kind_of_thing(thing_fact, kinds) -> str | None` (= `best.kind_of` without name
  groups: its `kind` value when it names a kind, else the kind whose names hold its folded label); `tally_wins(winners,
  kinds) -> dict` (= `best.tally`); `rebuild_answer(...)`: each paper's values as `{kind: float(value)}` in the
  settings' kind order, exactly as `best.study` stores them (review I1: an item's `45` is `45.0` in the answer, and
  the values sha256 sees the difference), the top value by `higher_is_better`, winner or sorted tie, then the tally;
  `answer_lines(...)` (= kindtext `_best`, cut).
- Produces in `rules/inventory.py`: `rebuild_answer(...)` (= `inventory.answer` without groups: `same` names first,
  then the first form met; aliases sorted; entries sorted by folded name, then name); `answer_lines(...)` (= kindtext
  `_inventory`, cut). Both files define `notes_of(view) -> []`.
- Produces in `inputs.py`:
  - `best_inputs(ra) -> ProgramInputs`: settings `{kind: "best", measure: canonical, higher_is_better, kinds: {kind:
    [names]}}`; facts: measured values `{paper, item, type: "measured value", value, dataset, thing: F, measure: F}`,
    compared things `{paper, item, type: "compared thing", label, kind}` (`kind` the kind field's value or None),
    measures; papers in the recorded order: `{paper, values: [F, ...]}` (the measured values among the ids
    `best.study(protocol, doc, items, None, roles=roles, inferred=ra.inferred)` used) or `{paper, no_comparison:
    <entry reason>}`; a study whose recomputed values, winner or tie differ from the recorded ones →
    `NotRebuilt(NOT_FOUND_AGAIN.format(what="values", paper=doc))`.
  - `inventory_inputs(ra) -> ProgramInputs`: settings `{kind: "inventory", target, same: {name: [others]}}`; facts
    `{paper, item, type: <target>, name: <name_of(item, field)>}`; papers: the papers named in the recorded entries'
    `papers` (manifest order; so a paper the funnel screened out, whose items the engine did not count, stays out,
    review M8), each `{paper, names: [F, ...]}` with its target items in item order.
  - `inputs_of(ra) -> ProgramInputs`: dispatch on `ra.kind`, the kind's function looked up at call time (written added
    in Task 4).
  - `refusal(run: Path | str, corpus: Path | str | None = None) -> str | None`: `read_refusal`, else the `NotRebuilt`
    text `inputs_of(read_run(run, corpus, texts=False))` raises, else None (review I2: the page's `program_refused`
    and the download route then always agree). Exported from `evidence.readable`.

- [ ] **Step 1: Write the failing tests** (best items: conditions with `role` `rag` / `closed_book` and `kind` set
  as `kind_protocol` declares; a helper `best_items(paper, values: dict[str, float], kind_field=True)` in
  `readable_cases.py` builds one condition per kind (label = the kind's first name in `NAMES`, `kind` the id, or no
  `kind` field and a label from the names when `kind_field=False`), the metric and one value each):

```python
def test_best_rebuilds_wins_ties_and_reasons():
    p = case_protocol("best")
    ra = case_answer(p, {"S001": best_items("S001", {"rag": 0.7, "closed_book": 0.6}),
                         "S002": best_items("S002", {"rag": 0.5, "closed_book": 0.5}),           # a tie
                         "S003": best_items("S003", {"rag": 0.8, "closed_book": 0.4}, kind_field=False),
                         "S004": best_items("S004", {"rag": 0.9})}, "best")                       # one kind only
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and "\n".join(lines) == answer_text(ra)
    assert view["wins"] == {"rag": 2} and view["studies"][1]["tied"] == ["closed_book", "rag"]
    assert view["studies"][3]["reason"]["code"] == "too_few_kinds"

def test_best_whole_number_values_are_compared_as_the_engine_stores_them():
    ra = case_answer(case_protocol("best"), {"S001": best_items("S001", {"rag": 45, "closed_book": 5})}, "best")
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and view["studies"][0]["values"] == {"rag": 45.0, "closed_book": 5.0}
    assert common.values_sha256(view) == common.values_sha256(checked_view(ra))

def test_a_pair_that_cannot_be_found_again_is_a_refusal(monkeypatch):
    ra = case_answer(case_protocol("consistency"), {"S001": study_items("S001", 0.62, 0.5, claim="improves")},
                     "consistency")
    ra = dataclasses.replace(ra, answer={**ra.answer, "studies": [{**ra.answer["studies"][0],
                                                                    "direction": "contradicts"}]})
    with pytest.raises(NotRebuilt, match="the pair the run used for S001 could not be found again"):
        inputs_of(ra)

def test_refusal_also_builds_the_inputs(tmp_path, monkeypatch):
    root = plan_run(tmp_path, with_answer(make_plan(), "best", None))
    assert refusal(root) is None
    monkeypatch.setattr(inputs_module, "best_inputs", lambda ra: (_ for _ in ()).throw(NotRebuilt("not again")))
    assert refusal(root) == "not again"

def test_best_with_no_comparison_says_cant_tell():
    ra = case_answer(case_protocol("best"), {"S001": best_items("S001", {"rag": 0.9})}, "best")
    assert rebuilt(ra)[1][0] == common.CANT_TELL_LINE

@pytest.mark.parametrize("target", ["condition", "metric"])
def test_inventory_rebuilds_names_aliases_and_papers(target):
    p = case_protocol("inventory", target)
    by_paper = {"S001": study_items("S001", 0.6, 0.5, t_label="Method K", c_label="usual  method"),
                "S002": study_items("S002", 0.6, 0.5, t_label="method k", c_label="Usual method")}
    ra = case_answer(p, by_paper, "inventory")
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and "\n".join(lines) == answer_text(ra)

def test_long_inventories_are_cut_like_the_engine():
    p = case_protocol("inventory", "condition")
    by_paper = {f"S{i:03d}": study_items(f"S{i:03d}", 0.6, 0.5, t_label=f"Method {i}", c_label=f"Usual {i}")
                for i in range(1, 80)}
    ra = case_answer(p, by_paper, "inventory")
    view, lines = rebuilt(ra)
    assert len(lines) == common.MAX_KIND_LINES + 1 and "\n".join(lines) == answer_text(ra)

@pytest.mark.parametrize("name", ["best", "inventory"])
def test_a_rule_file_imports_only_the_standard_library(name):
    assert stdlib_only(Path(evidence.readable.rules.__file__).parent / f"{name}.py") <= ALLOWED
```

  (`rebuilt` here dispatches with `inputs_of` and the kind's rule module; `ALLOWED` as in Task 2; `inputs_module` is
  `evidence.readable.inputs`; `plan_run`, `make_plan` as in Task 1.)
- [ ] **Step 2: Run** `uv run pytest -q evidence/tests/test_readable_best_inventory.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the two rule files and the two input functions.
- [ ] **Step 4: Run** this file and `evidence/tests/test_readable_effect.py`. Expected: PASS.
- [ ] **Step 5: Commit** the five files and `readable_cases.py` (the `best_items` builder): `evidence: the readable
  program's rules for best and inventory`.

### Task 4: The rules, copied: the written answer

**Files:**
- Create: `backend/evidence/readable/rules/written.py`, `backend/evidence/tests/test_readable_written.py`
- Modify: `backend/evidence/readable/inputs.py` (`written_inputs`, dispatch)

**Interfaces:**
- Consumes: `evidence.written` (`numbers`, `check_written`, `answer_text_of`, `fact_text`, constants and regexes);
  Tasks 1-3.
- Produces in `rules/written.py` (constants pinned to `evidence.written`): `MAX_SENTENCES`, `MAX_SENTENCE_CHARS`,
  `MAX_REPAIRS`, `MAX_QUOTE`, `NO_FACTS_TEXT`, `PAPER_ID`, `THOUSANDS`, `NUMBER`; `fact_text_from_values(fact, facts)
  -> str` (= `written.fact_text` on the values: `_plain` with `decimal.Decimal`, `?` for a missing value, the quote cut
  at `MAX_QUOTE`); `numbers_in(text) -> list[float]`; `check_reply(reply: dict, writer_facts: list[dict], question:
  str) -> list[str]` (= `check_written` on plain dicts; a writer fact is a dict with at least `n`, `paper`, `text`);
  `answer_text_and_rows(reply, writer_facts) -> tuple[str, list[dict]]` (= `answer_text_of`); `rebuild_answer(settings, facts, papers, model_text) -> dict` (the Task 1 written
  view): rebuild every writer fact's text from its values; no writer fact → status `no_facts`, `answer_text`
  `NO_FACTS_TEXT`, sentences `[{"text": NO_FACTS_TEXT, "says": "cannot_tell", "facts": [], "papers": []}]`, tries
  `[]`; else check the recorded replies (`model_text`) in order, at most `MAX_REPAIRS + 1`, stopping at the first with
  no problem → `ok` with its text and rows, or `failed` with `answer_text ""` and `sentences []`; `answer_lines(settings,
  view, names) -> [view["answer_text"]]`; `notes_of(view) -> list[str]`: `ok` → `[NOTE_WRITTEN]`, `failed` →
  `[FAILED_NOTE.format(problems="; ".join(view["tries"][-1]))]`, `no_facts` → `[]`.
- Produces in `inputs.py`: `written_inputs(ra) -> ProgramInputs`: settings `{kind: "written", question}` (the
  recorded question); papers = the writer's facts in order `[{n, fact: F, paper}]` (no recorded text: the view's
  `fact_texts` and its sha256 already compare the rebuilt texts with the recorded ones, review M15); facts, every one
  with `paper`, `item` and `type` (one shape, review M16): a measurement `{paper, item, type: "measurement", value,
  dataset, condition: F | None, metric: F | None, quote}`, its condition `{paper, item, type: "condition", label}`,
  its metric `{paper, item, type: "metric", name, higher_is_better}`, an author claim `{paper, item, type:
  "author_claim", direction, quote}`, a claim `{paper, item, type: "claim", subject, relation, object, strength,
  quote}`; `quote` = the exact text of the item's value span, else its first span, uncut; fact keys in this order: each writer fact's
  item, then its condition, then its metric (so writer fact 1 is `F1`); `model_text` = `[t["reply"] for t in
  tries]`; spans for the comments.

- [ ] **Step 1: Write the failing tests** (`written_run`, `writer_model` of `test_written_stage.py`):

```python
GOOD = {"sentences": [{"text": "Retrieval helped.", "says": "finding", "facts": [1]}]}
BAD = {"sentences": [{"text": "Up 987654%.", "says": "finding", "facts": [1]}]}

def rebuilt(root):
    ra = read_run(root); i = inputs_of(ra)
    return ra, rules_written.rebuild_answer(i.settings, i.facts, i.papers, i.model_text)

@pytest.mark.parametrize("replies, status", [([GOOD], "ok"), ([BAD, GOOD], "ok"), ([BAD, BAD], "failed")])
def test_the_written_answer_is_rebuilt_from_its_replies(tmp_path, replies, status):
    it = iter(replies)
    ra, view = rebuilt(written_run(tmp_path, lambda p: next(it)))
    assert view == checked_view(ra) and view["status"] == status
    assert rules_written.answer_lines({}, view, {}) == [answer_text(ra)]

def test_no_fact_means_the_fixed_text(tmp_path):
    nothing = with_answer(make_plan(things={"zz": ["no such words anywhere"], "yy": ["nor these"]}, measures=()),
                          "written", None)
    ra, view = rebuilt(written_run(tmp_path, lambda p: GOOD, plan=nothing))
    assert view == checked_view(ra) and view["answer_text"] == NO_FACTS_TEXT

def test_fact_texts_rebuild_from_values():
    c = item("condition", {"label": "Method K", "role": "rag"})
    k = item("metric", {"name": "Yield", "canonical": "accuracy", "higher_is_better": True})
    for value in (0.62, 1e-05, 10, 1250.0):
        m = item("measurement", {"value": value, "dataset": None}, {"condition": c.item_id, "metric": k.item_id},
                 exact="x" * 250)
        by_id = {i.item_id: i for i in (c, k, m)}
        facts = {"F1": {"paper": "S001", "item": m.item_id, "type": "measurement", "value": value, "dataset": None,
                        "condition": "F2", "metric": "F3", "quote": "x" * 250},
                 "F2": {"paper": "S001", "item": c.item_id, "type": "condition", "label": "Method K"},
                 "F3": {"paper": "S001", "item": k.item_id, "type": "metric", "name": "Yield",
                        "higher_is_better": True}}
        assert rules_written.fact_text_from_values(facts["F1"], facts) == fact_text(m, by_id)

def test_the_checks_match_the_engine():
    facts = [Fact(n=1, item="m", paper="S001", type="measurement", text="Method K on Yield: 0.45, 1,250 cases")]
    plain = [f.model_dump() for f in facts]
    for text, says, cited in [("Up to 45% in 1 study.", "finding", [1]), ("Up by 12%.", "finding", [1]),
                              ("Better in S001.", "finding", [1]), ("Unknown.", "cannot_tell", [1]),
                              ("1,250 cases in 2026.", "finding", [9]), ("", "finding", [1])]:
        reply = WrittenReply(sentences=[Sentence(text=text, says=says, facts=cited)])
        assert rules_written.check_reply(reply.model_dump(), plain, "In 2026?") == check_written(reply, facts, "In 2026?")

def test_the_copies_match_the_engine():
    assert (rules_written.MAX_SENTENCES, rules_written.MAX_SENTENCE_CHARS, rules_written.MAX_REPAIRS,
            rules_written.MAX_QUOTE, rules_written.NO_FACTS_TEXT) == (
        written.MAX_SENTENCES, written.MAX_SENTENCE_CHARS, written.MAX_REPAIRS, written.MAX_QUOTE, written.NO_FACTS_TEXT)
    assert [r.pattern for r in (rules_written.PAPER_ID, rules_written.THOUSANDS, rules_written.NUMBER)] == [
        r.pattern for r in (written.PAPER_ID, written.THOUSANDS, written.NUMBER)]
```

  plus `test_a_rule_file_imports_only_the_standard_library` for `written.py` (`stdlib_only(...) <= ALLOWED`).
- [ ] **Step 2: Run** `uv run pytest -q evidence/tests/test_readable_written.py`. Expected: FAIL.
- [ ] **Step 3: Implement** `rules/written.py`, `written_inputs` and the dispatch.
- [ ] **Step 4: Run** the three `test_readable_*.py` files. Expected: PASS.
- [ ] **Step 5: Commit** the files: `evidence: the readable program's rules for the written answer (checks, reply, ids)`.

### Task 5: The program file and `evidence program`

**Files:**
- Create: `backend/evidence/readable/program.py`, `backend/evidence/tests/test_readable_program.py`
- Modify: `backend/evidence/readable/__init__.py` (export `program_of_run`), `backend/evidence/cli.py` (command
  `program`, docstring line), `backend/README.md` (one Run line)

**Interfaces:**
- Consumes: Tasks 1-4; `RunDir`; `SEAL_FILE` (`manifest.json` `code_commit`).
- Produces: `RULE_FILES: dict[str, tuple[str, ...]] = {"effect": ("common", "effect"), "consistency": ("common",
  "effect"), "best": ("common", "best"), "inventory": ("common", "inventory"), "written": ("common", "written")}`.
- Produces: `SECTION_NONE = "before the first heading"`; `SECTION_UNKNOWN = "unknown (the papers were not at hand when
  this file was made)"`; `section_at(text: str | None, start: int) -> str`: the last Markdown heading line
  (`^#{1,6}\s+(.+?)\s*#*\s*$`) that starts before `start`, its words; `SECTION_NONE` when there is none;
  `SECTION_UNKNOWN` when `text` is None.
- Produces: `fact_comment(key: str, fact: dict, spans: list[dict], texts: Mapping[str, str] | None) -> list[str]`:
  `# <key>: paper <paper>, section "<section of its first span>"`, then one line per span
  `#   <role>: <json.dumps(exact, ensure_ascii=False)>` (one line whatever the quote holds).
- Produces: `program_text(inputs: ProgramInputs, about: dict, texts: Mapping[str, str] | None, recorded_text: str,
  recorded_view: dict) -> str`, in this order (exact headings):
  1. `#!/usr/bin/env python3`, then `HEADER` (exact copy below);
  2. `from __future__ import annotations` (once, first), then the sorted, de-duplicated import lines of the rule
     files, any `from __future__` line of theirs left out (a second one after other imports is a SyntaxError);
  3. `# --- Part 1: what was asked ---`; `# Question: <question, line breaks as spaces>`; `KIND`, `THE_QUESTION`,
     `THE_RUN` (= `about`), `NAMES_OF_THINGS`, `RULE_SETTINGS` (each `NAME = <pprint.pformat(value, width=110,
     sort_dicts=False)>`);
  4. `# --- Part 2: the facts used ---`; `FACTS_USED = {` with each fact's comment lines then `"F1": {...},` `}`;
     `PAPERS = ...`; the line `# MODEL_TEXT: written by a model from the results above, not rebuilt by this file.`
     (written only) and `MODEL_TEXT = ...`; `RECORDED_ANSWER_SHA256 = '<text_sha256(recorded_text)>'`,
     `RECORDED_VALUES_SHA256 = '<values_sha256(recorded_view)>'`;
  5. `# --- Part 3: the rules (a copy, so this file runs on its own) ---`; each rule file's body (after `# --- rules
     ---`, without `# program: drop` lines);
  6. `# --- Part 4: run it ---`; `if __name__ == "__main__":` / `    sys.exit(main(sys.argv[1:], globals()))`.
  `HEADER` (exact copy; `<rule text>` is `kindtext.RULE_TEXT[kind]`):

```text
"""The answer of one recorded run, rebuilt from the facts it used.

Run it with Python 3.9 or later: python this_file.py (add --json for the rebuilt values). It needs no papers, no AI
and no other file, only the Python standard library. It prints the answer, then checks it against the answer the run
recorded.

How the answer is made: <rule text>

What this file shows: the run is replayable and checkable. The same recorded facts always rebuild the same answer,
and every fact below points to exact text in a paper: the comment above it names the paper, the section and the
quote. Which values each paper compared is recorded below (PAPERS), not chosen again by this file; from those values
on, every step is rebuilt here. The tools are fixed functions; the agent's choice of tool calls is not fixed, but
every call is recorded. This file does not show that the same question always gives the same answer, nor that
pulling the facts out of the papers is deterministic.

Part 1 says what was asked, part 2 holds the facts the rules used, part 3 is a copy of the rules, part 4 runs them.
"""
```

  For a written answer the header gets, before its last paragraph: `The answer's sentences were written by a model
  from the facts below; they are pasted here (MODEL_TEXT), not rebuilt by this file. This file re-runs the code checks
  on them, chooses the reply the run accepted and adds the paper ids.`
- Produces: `about_of(ra: RunAnswer) -> dict`: `{run: run_id, corpus: corpus_id, protocol_sha256, answer_file:
  "written-answer.json" | "answer.json", answer_file_sha256: <run.json outputs of that file>, code_commit: <manifest
  code_commit or None>}` (no path of this machine).
- Produces: `program_of_run(run: Path | str, corpus: Path | str | None = None) -> str` = `read_run`, `inputs_of`,
  `program_text(inputs, about_of(ra), ra.texts, answer_text(ra), checked_view(ra))`; raises `NotRebuilt`.
- Produces: `evidence program RUN --out FILE [--corpus DIR]` (`--out` required): writes the program (UTF-8, LF); exit 2
  with `error: <reason>` for `NotRebuilt`; for an `--out` inside the run folder (`error: the run folder is sealed;
  write the program elsewhere`); and for an `--out` inside the repository (`repo_paths.REPO`) that `git -C <repo>
  check-ignore -q <out>` does not report as ignored (`error: <out> is in the repository and not git-ignored; a program
  quotes papers and stays local`; review M12; when git cannot be run the file is written and a warning printed).
  Run line: `uv run evidence program RUN --out FILE.py   # the run's answer as a
  readable Python program (standard library only): it rebuilds the answer from the facts it used and checks it`.

- [ ] **Step 1: Write the failing tests:**

```python
def run_program(path, *args):
    return subprocess.run([sys.executable, "-I", "-S", str(path), *args], capture_output=True, cwd=path.parent,
                          timeout=120)

def make(root, tmp_path):
    path = tmp_path / "out" / "answer.py"; path.parent.mkdir(exist_ok=True)
    path.write_text(program_of_run(root), encoding="utf-8", newline="\n")
    return path

def expect(ra):
    notes = rules_written.notes_of(checked_view(ra)) if ra.kind == "written" else []
    return (answer_text(ra) + "\n\n" + "".join(f"{n}\n" for n in notes) + common.CHECK_OK + "\n").encode("utf-8")

@pytest.mark.parametrize("by, target", [("effect", None), ("consistency", None), ("inventory", "condition"),
                                        ("inventory", "metric"), ("best", None)])
def test_the_program_rebuilds_a_fixed_kind_run(tmp_path, by, target):
    root = plan_run(tmp_path, with_answer(make_plan(), by, target)); ra = read_run(root)
    path = make(root, tmp_path)
    out = json.loads(run_program(path, "--json").stdout.decode("utf-8"))
    assert out == {"kind": by, "answer": checked_view(ra), "text": answer_text(ra)}
    done = run_program(path)
    assert done.returncode == 0 and done.stdout == expect(ra), done.stderr

@pytest.mark.parametrize("replies", [[GOOD], [BAD, GOOD], [BAD, BAD]])
def test_the_program_rebuilds_a_written_run(tmp_path, replies):
    it = iter(replies)
    root = written_run(tmp_path, lambda p: next(it)); ra = read_run(root)
    path = make(root, tmp_path)
    assert json.loads(run_program(path, "--json").stdout.decode("utf-8"))["answer"] == checked_view(ra)
    done = run_program(path)
    assert done.returncode == 0 and done.stdout == expect(ra)
    text = path.read_text(encoding="utf-8")
    assert "# MODEL_TEXT: written by a model from the results above, not rebuilt by this file." in text

def test_the_same_run_gives_the_same_file_and_the_same_output(tmp_path):
    root = written_run(tmp_path, lambda p: GOOD)
    assert program_of_run(root) == program_of_run(root)
    path = make(root, tmp_path)
    assert run_program(path).stdout == run_program(path).stdout

def test_a_changed_fact_fails_the_check(tmp_path):
    root = written_run(tmp_path, lambda p: GOOD); path = make(root, tmp_path)
    path.write_text(path.read_text(encoding="utf-8").replace("Retrieval helped.", "Retrieval hurt."), encoding="utf-8")
    done = run_program(path)
    assert done.returncode == 1 and done.stdout.decode("utf-8").splitlines()[0] == common.CHECK_FAILED

def test_each_fact_names_its_paper_section_and_quote(tmp_path):
    root = written_run(tmp_path, lambda p: GOOD); ra = read_run(root)
    first = ra.answer["facts"][0]
    item = next(i for i in ra.items[first["paper"]] if i.item_id == first["item"])
    span = item.spans[0]                       # the comment's section is its first span's
    text = program_of_run(root)
    section = section_at(ra.texts[first["paper"]], span.selector["start"])
    assert f'# F1: paper {first["paper"]}, section "{section}"' in text
    assert json.dumps(span.selector["exact"], ensure_ascii=False) in text

def test_without_the_papers_the_program_is_still_made(tmp_path):
    root = plan_run(tmp_path, with_answer(make_plan(), "effect", None))
    shutil.rmtree(tmp_path / "corpus")
    path = make(root, tmp_path)
    assert SECTION_UNKNOWN in path.read_text(encoding="utf-8") and run_program(path).returncode == 0

def case_program(tmp_path, ra, name):
    text = program_text(inputs_of(ra), {"run": "case"}, None, answer_text(ra), checked_view(ra))
    ast.parse(text, feature_version=(3, 9))
    path = tmp_path / f"{name}.py"; path.write_text(text, encoding="utf-8", newline="\n")
    return path

def test_odd_text_stays_on_one_line_and_prints_anywhere(tmp_path):
    odd = 'Method "K" ≥ 2 \\ x'
    items = study_items("S001", 0.62, 0.5, t_label=odd)
    items = [i.model_copy(update={"spans": [s.model_copy(update={"selector": {**s.selector,
             "exact": 'a\n"""b\\c ≥'}}) for s in i.spans]}) for i in items]
    # the odd name reaches the printed head line through the names map (effect lines print names, never labels)
    ra = case_answer(case_protocol(), {"S001": items}, "effect", names={**NAMES, "rag": odd})
    done = run_program(case_program(tmp_path, ra, "odd"))
    assert done.returncode == 0 and odd in done.stdout.decode("utf-8")
    inv = case_answer(case_protocol("inventory", "condition"), {"S001": items}, "inventory")
    done = run_program(case_program(tmp_path, inv, "odd_inventory"))   # inventory lines print labels as written
    assert done.returncode == 0 and odd in done.stdout.decode("utf-8")

def test_whole_number_best_values_pass_the_check(tmp_path):
    ra = case_answer(case_protocol("best"), {"S001": best_items("S001", {"rag": 45, "closed_book": 5})}, "best")
    done = run_program(case_program(tmp_path, ra, "best45"))
    assert done.returncode == 0 and done.stdout.decode("utf-8").splitlines()[-1] == common.CHECK_OK

def test_the_program_imports_only_the_standard_library(tmp_path):
    root = written_run(tmp_path, lambda p: GOOD)
    tree = ast.parse(program_of_run(root), feature_version=(3, 9))   # the header promises Python 3.9
    tops = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    tops |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert tops <= set(sys.stdlib_module_names) | {"__future__"}

def test_the_command_writes_or_refuses(tmp_path, capsys):
    root = written_run(tmp_path / "w", lambda p: GOOD)
    assert cli.main(["program", str(root), "--out", str(tmp_path / "p.py")]) == 0
    assert (tmp_path / "p.py").read_text(encoding="utf-8") == program_of_run(root)
    assert cli.main(["program", str(root), "--out", str(root / "p.py")]) == 2
    lines = plan_run(tmp_path / "l")
    assert cli.main(["program", str(lines), "--out", str(tmp_path / "q.py")]) == 2
    assert LINES in capsys.readouterr().err
    tracked = repo_paths.REPO / "backend" / "zz-not-ignored-answer.py"   # inside the repo, not git-ignored
    assert cli.main(["program", str(root), "--out", str(tracked)]) == 2 and not tracked.exists()
    assert "not git-ignored" in capsys.readouterr().err
```

  (`GOOD` and `BAD` are Task 4's reply dicts, imported from `test_readable_written.py`.)
- [ ] **Step 2: Run** `uv run pytest -q evidence/tests/test_readable_program.py`. Expected: FAIL.
- [ ] **Step 3: Implement** `program.py` (rule-file pasting by the Task 2 convention; `json.dumps(...,
  ensure_ascii=False)` for quotes in comments; `pprint.pformat` for data), the CLI command and the README line.
- [ ] **Step 4: Run** the four `test_readable_*.py` files, `tests/test_boundaries.py` and
  `evidence/tests/test_no_topic_words.py`. Expected: PASS.
- [ ] **Step 5: Commit** the five files: `evidence: every run as one readable program that rebuilds and checks its answer`.

### Task 6: Re-execution that asks every model call again

**Files:**
- Modify: `backend/evidence/calls.py` (`CallCache(..., fresh_recorded: bool = False)`), `backend/evidence/engine.py`
  (`execute_run(..., fresh_recorded: bool = False)`; `RunCalls` in mode `reexec` too), `backend/evidence/replay.py`
  (`reexec(..., all_calls: bool = False)`, module docstring), `backend/evidence/cli.py` (`reexec --all-calls`,
  docstring)
- Create: `backend/evidence/tests/test_reexec_all_calls.py`

**Interfaces:**
- Produces: `CallCache.recorded` in mode `reexec` with `fresh_recorded` asks `make()` the first time a request is
  met in this process and returns `Asked(value, records, "fresh", <the recorded attempt>)`; a repeat of the same
  request in the same re-run gets that same `Asked` back from an in-process dict (`self.asked_again: dict[str,
  Asked]`, keyed by the cache key), as a run answers a repeat from its own calls (review M1: a v1 plan run maps
  experiments twice per paper); nothing is stored in the record cache (it stays the reference).
  Docstring line in calls.py: "`reexec` with `fresh_recorded`: the engine's own calls (the names check, the stages'
  `ctx.ask`) are asked again too, never read from the record."
- Produces: `execute_run` passes `fresh_recorded` to `CallCache`; `run_calls = RunCalls(...) if mode in ("run",
  "reexec")`, so a re-run keeps `calls.jsonl` (the requests and replies of its model calls).
- Produces: `reexec(run_dir, extractor=None, *, cache=None, corpus=None, out_dir=None, provider=None, locator=None,
  all_calls: bool = False) -> Path`: `all_calls` re-runs every extractor and asks the stages' and the names check's
  calls again (`fresh_recorded=True`); `ValueError("all_calls re-runs every extractor; leave out the extractor")` when
  both are given.
- Produces: `evidence reexec RUN [--extractor NAME | --all-calls] [--cache DIR] [--corpus DIR] [--out DIR]`.

- [ ] **Step 1: Write the failing tests:**

```python
GOOD = lambda p: {"sentences": [{"text": "Retrieval helped.", "says": "finding", "facts": [1]}]}

def rows(run):
    return [json.loads(x) for x in (run / RUN_CALLS_FILE).read_text(encoding="utf-8").splitlines()]

def test_all_calls_asks_the_writer_and_the_stages_again_and_keeps_the_cache(tmp_path):
    root = written_run(tmp_path, GOOD)
    cache = tmp_path / "cache" / CACHE_FILE; before = cache.read_bytes()
    calls, others = [], []
    new = reexec(root, all_calls=True, out_dir=tmp_path / "re",
                 provider=provider_of(writer_model(calls, GOOD, others=others)))
    assert len(calls) == 1 and others and cache.read_bytes() == before
    assert RunDir(new).complete and (new / "reexec.json").is_file()
    assert any(r["extractor_id"] == "stage:written-answer" and r["source"] == "fresh" for r in rows(new))

def test_without_all_calls_the_stages_read_the_record(tmp_path):
    root = written_run(tmp_path, GOOD); calls = []
    reexec(root, out_dir=tmp_path / "re", provider=provider_of(writer_model(calls, GOOD)))
    assert calls == []

def test_a_repeated_request_in_one_rerun_is_asked_once(tmp_path):
    cache = CallCache(JsonlCache(tmp_path / "c.jsonl"), "reexec", fresh_recorded=True, attempts={})
    made = []
    make = lambda: (made.append(1) or ({"status": "ok", "output": {"n": len(made)}}, []))
    first = cache.recorded("stage:x", {"q": 1}, make)
    again = cache.recorded("stage:x", {"q": 1}, make)
    assert len(made) == 1 and again.value == first.value and first.source == "fresh"
    assert not (tmp_path / "c.jsonl").exists() or (tmp_path / "c.jsonl").read_text(encoding="utf-8") == ""

def test_all_calls_names_no_extractor(tmp_path):
    with pytest.raises(ValueError, match="all_calls re-runs every extractor"):
        reexec(written_run(tmp_path, GOOD), "regex_measurement", all_calls=True)

def test_the_command_takes_all_calls(tmp_path, monkeypatch, capsys):
    root = written_run(tmp_path, GOOD); calls = []
    monkeypatch.setattr(replay_module, "default_provider", lambda alias: writer_model(calls, GOOD))
    assert cli.main(["reexec", str(root), "--all-calls", "--out", str(tmp_path / "re")]) == 0
    assert len(calls) == 1
```

- [ ] **Step 2: Run** `uv run pytest -q evidence/tests/test_reexec_all_calls.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the four changes.
- [ ] **Step 4: Run** the new file and `uv run pytest -q evidence/tests/test_llm.py evidence/tests/test_engine.py
  evidence/tests/test_run_calls.py evidence/tests/test_cli_prov.py evidence/tests/test_funnel.py
  evidence/tests/test_records_review.py evidence/tests/test_plan_run.py evidence/tests/test_written_stage.py`
  (old re-runs and replays unchanged). Expected: PASS.
- [ ] **Step 5: Commit** the five files: `evidence: reexec --all-calls asks every model call again, cache untouched`.

### Task 7: The re-run measure of one run

**Files:**
- Create: `backend/evidence/stability.py`, `backend/evidence/tests/test_stability.py`
- Modify: `backend/evidence/cli.py` (`reexec --times N`), `backend/README.md` (one Run line)

**Interfaces:**
- Consumes: Task 6 (`calls.jsonl` and `reexec.json` of a re-run); Task 1 (`read_run(..., texts=False)`,
  `answer_text`, `headline`); `replay._item_key` (content key of an item, ids left out), `contract.digest`.
- Produces: `GROUPS = ("llm", "agent", "stage", "names", "other")`; `GROUP_TEXT = {"llm": "LLM extractors", "agent":
  "agentic extractor", "stage": "stages (the run's own model calls)", "names": "names check", "other": "other model
  calls"}`; `OUTCOMES = ("identical", "other_reply", "failed", "unreadable", "not_asked_again")`.
- Produces: `ModelCall` (NamedTuple): `group: str`, `slot: str` (`<row key>#<index of the record in the row>`),
  `request: str | None`, `reply: str | None`, `failed: bool`, `readable: bool`, `temperature: float | None`,
  `served: str | None`. A record is read by its shape (review C1):
  - an engine record (`evidence/recording.py`: `request.settings`, and `response.output` or `error`): request =
    digest of `request`; reply = digest of `response.output`; failed = it has `error`; temperature =
    `request.settings.temperature`; served = `response.served_model`;
  - an agentic record (`kind == "agent_model_call"`, `evidence/agentic/extractor.py` `engine_records`): request =
    digest of `[request.step_id, request.prompt_sha256]` (its `status` is a reply-side value, left out); reply =
    `response.response_sha256`; failed = it has `error`, or `request.status` is not the agent loop's success value
    (read it where `agent/loop.py` writes its model-call steps); temperature = run.json
    `extractor_specs[id]["config"]["temperature"]` when present, else the `agent_run` record's `temperature` when
    present, else None; served = the `agent_run` record's `served_model` when present, else None;
  - any other record, or one with neither `response.output`, `response.response_sha256` nor `error`: `readable`
    False; it is never counted identical.
- Produces: `model_calls(run: Path) -> list[ModelCall]`: every model-call record of every `calls.jsonl` row; the group
  from the row's `extractor_id`: `stage:` prefix → stage; `names_confirm@` prefix → names; else run.json
  `extractor_specs[id]["kind"]` `llm` → llm, `agent` → agent, else other. `ValueError("<run> has no calls.jsonl: its
  model calls cannot be compared")` when absent.
- Produces: `compare_calls(original: Path, rerun: Path) -> dict[str, dict]`: per group `{calls, identical,
  other_reply, failed, unreadable, not_asked_again, new, temperatures, served}` (`temperatures` and `served`: the
  distinct known values of both runs, None left out, sorted). Matching within a group, each re-run call used once:
  first the re-run call in the same `slot` when its request is the same, else a re-run call with the same request
  (review M2: two calls with one request, such as a DSPy retry, stay paired by slot). An original call whose matched
  re-run call, or itself, is unreadable → unreadable; matched re-run call failed → failed; same reply → identical;
  another reply → other_reply; no match → not_asked_again; re-run calls left over → new.
- Produces: `item_stability(original: Path, rerun: Path) -> dict`: `{items, found_again, by_type: {type: [items,
  found_again]}}` over `evidence.jsonl`, items matched by `_item_key` as multisets.
- Produces: `items_by_extractor(original: Path, rerun: Path) -> dict[str, list[int]]`: the re-run's `reexec.json`
  `summary` (per extractor name: `items_original`, `items_reproduced`) summed by the extractor's kind in the original
  run.json `extractor_specs` (name = the id before `@`): `{"llm": [items, reproduced], "agent": [...], "other":
  [...]}` (review I4: the spec asks for the agentic and the LLM extractors apart).
- Produces: `same_answer(original: Path, rerun: Path) -> dict`: `{text: bool | None, headline: bool | None, why: str |
  None}` through `read_run(..., texts=False)` (None and the refusal text when either run cannot be read).
- Produces: `measure(original: Path, reruns: Sequence[Path]) -> dict`: `{run: <name>, reruns: n, calls: {group:
  sums}, items: sums, items_by_extractor: sums, answers: {compared, same_text, same_headline, whys: [distinct refusal
  texts, sorted]}}`; `combine(reports: Sequence[dict]) -> dict` (sums; `whys` joined as one sorted distinct list;
  `runs` = number of reports, `reruns` = total); `share(a, b) -> str` (`f"{100 * a / b:.1f}%"`, `"-"` when b is 0).
- Produces: `render(report: dict) -> list[str]` (exact copy; `<temps>` = the known temperatures as `f"{t:g}"` joined
  by `", "`, or `unknown` when none is known):
  - `Re-run measure: <runs> runs x <reruns per run> re-runs, no cache (every model call asked again).` (a single
    measure: `runs` 1);
  - `Model calls (identical: the same request got the same reply):`;
  - per group in `GROUPS` order (llm, agent, stage, names always; other only with calls): `  <GROUP_TEXT> (temperature
    <temps>): <calls> calls, <identical> identical (<share>), <other_reply> other reply, <failed> failed,
    <unreadable> unreadable, <not_asked_again> not asked again, <new> new`; a group with no calls: `  <GROUP_TEXT>: no
    calls in these runs`;
  - `  served models: <distinct, ", ", or unknown>`;
  - `Items found again: <share> of <items> (<type> <share>, ...)` (types sorted);
  - `Items found again by extractor: LLM extractors <share>, agentic extractor <share>, other extractors <share>`
    (a group without items reads `no items in these runs` in place of its share);
  - `Final answer the same: text in <same_text> of <compared> re-runs, headline in <same_headline> of <compared>`;
    then one `  not compared: <why>` per text in `whys`;
  - `This re-asks one run's calls once; it does not repeat the system's retry of a written answer that failed its
    checks.` (review M7).
- Produces: `evidence reexec RUN --all-calls --times N --out DIR` (N >= 1): N re-runs into `DIR`, then prints the
  `render(measure(run, news))` lines and writes `DIR/stability.json`; exit 0. `--all-calls` without `--times` keeps
  Task 6's output (one re-run, its summary). Returned with exit 2 by checks in the dispatch (not argparse):
  `--times` without `--all-calls` (`error: --times needs --all-calls`), `--times` without `--out` (`error: --times
  needs --out`, review M4: re-runs never land beside the original by default), an `--out` inside the original run
  folder (`error: the run folder is sealed; write the re-runs elsewhere`). Run line: `uv run evidence reexec RUN --all-calls --times 5 --out DIR   #
  every model call asked again (no cache), 5 times; prints identical calls, items found again, same answer`.

- [ ] **Step 1: Write the failing tests.** `fake_run(root, rows, specs)` writes `run.json` `{"extractor_specs":
  specs}` and `calls.jsonl` rows; `row(eid, req, reply, temperature=0.0)` is one row whose single model-call record
  has request `{"model": "orch-model", "user_prompt": req, "settings": {"temperature": temperature}}` and either
  `response {"output": {"r": reply}, "served_model": "served-x"}` or `error "down"` when `reply` is None; the row's
  `key` is `f"{eid}:{req}"`. `agent_row(req, reply_sha, status="<the loop's success value>")` is one row of
  `agentic@1#b` whose record is `{"id": "r/1", "kind": "agent_model_call", "request": {"step_id": req,
  "prompt_sha256": "p", "status": status}, "response": {"response_sha256": reply_sha}, "usage": {}}`; `odd_row(req)`
  one `llm_measurement@1#a` row whose record is `{"id": "x", "request": {"user_prompt": req}}` (no response, no
  error).

```python
SPECS = {"llm_measurement@1#a": {"kind": "llm"}, "agentic@1#b": {"kind": "agent", "config": {"temperature": 0.7}}}
COUNTS = ("calls", "identical", "other_reply", "failed", "unreadable", "not_asked_again", "new")

def test_calls_are_matched_by_request_and_told_apart(tmp_path):
    a = fake_run(tmp_path / "a", [row("llm_measurement@1#a", "A", "1"), row("llm_measurement@1#a", "B", "2"),
                                  row("llm_measurement@1#a", "C", "3"), row("stage:written-answer", "D", "4", 0.3),
                                  agent_row("s1", "h1"), agent_row("s2", "h2"), odd_row("F")], SPECS)
    b = fake_run(tmp_path / "b", [row("llm_measurement@1#a", "A", "1"), row("llm_measurement@1#a", "B", "9"),
                                  row("llm_measurement@1#a", "E", "5"), row("stage:written-answer", "D", None, 0.3),
                                  agent_row("s1", "h1"), agent_row("s2", "h9"), odd_row("F")], SPECS)
    out = compare_calls(a, b)
    assert {k: out["llm"][k] for k in COUNTS} == {"calls": 4, "identical": 1, "other_reply": 1, "failed": 0,
                                                 "unreadable": 1, "not_asked_again": 1, "new": 1}
    assert out["stage"]["failed"] == 1 and out["stage"]["temperatures"] == [0.3]
    assert out["llm"]["served"] == ["served-x"]
    assert {k: out["agent"][k] for k in ("calls", "identical", "other_reply")} == {"calls": 2, "identical": 1,
                                                                                   "other_reply": 1}
    assert out["agent"]["temperatures"] == [0.7] and out["agent"]["served"] == []

def test_two_agent_calls_with_another_reply_are_never_identical(tmp_path):
    a = fake_run(tmp_path / "a", [agent_row("s1", "h1")], SPECS)
    b = fake_run(tmp_path / "b", [agent_row("s1", "h2")], SPECS)
    assert compare_calls(a, b)["agent"]["other_reply"] == 1

def test_a_run_without_calls_jsonl_cannot_be_compared(tmp_path):
    (tmp_path / "a").mkdir()
    with pytest.raises(ValueError, match="has no calls.jsonl"):
        model_calls(tmp_path / "a")

def test_items_found_again_by_content(tmp_path):
    items = study_items("S001", 0.62, 0.5)
    changed = [*items[:-1], items[-1].model_copy(update={"fields": {**items[-1].fields, "value": 0.7}})]
    a, b = tmp_path / "a", tmp_path / "b"
    for root, rows_ in ((a, items), (b, changed)):
        root.mkdir(); write_lines(root / "evidence.jsonl", [i.model_dump(mode="json") for i in rows_])
    out = item_stability(a, b)
    assert out["items"] == len(items) and out["found_again"] == len(items) - 1
    assert out["by_type"]["measurement"] == [2, 1]

def test_two_reruns_one_with_another_reply(tmp_path):
    root = written_run(tmp_path, GOOD)
    same = reexec(root, all_calls=True, out_dir=tmp_path / "re", provider=provider_of(writer_model([], GOOD)))
    hurt = lambda p: {"sentences": [{"text": "Retrieval hurt.", "says": "finding", "facts": [1]}]}
    other = reexec(root, all_calls=True, out_dir=tmp_path / "re", provider=provider_of(writer_model([], hurt)))
    report = measure(root, [same, other])
    assert report["answers"] == {"compared": 2, "same_text": 1, "same_headline": 2, "whys": []}
    assert report["calls"]["stage"]["other_reply"] == 1 and report["items"]["found_again"] == report["items"]["items"]
    assert report["items_by_extractor"]["other"][0] > 0 and report["items_by_extractor"]["agent"] == [0, 0]
    lines = render(report)
    assert lines[0] == "Re-run measure: 1 runs x 2 re-runs, no cache (every model call asked again)."
    assert "  agentic extractor: no calls in these runs" in lines
    assert ("Items found again by extractor: LLM extractors no items in these runs, agentic extractor no items in "
            "these runs, other extractors 100.0%") in lines
    assert "Final answer the same: text in 1 of 2 re-runs, headline in 2 of 2" in lines
    assert lines[-1].startswith("This re-asks one run's calls once")

def test_combine_adds_runs(tmp_path):
    r = {"run": "x", "reruns": 2, "calls": {g: dict.fromkeys(COUNTS, 1) | {"temperatures": [0.0], "served": ["s"]}
                                            for g in GROUPS},
         "items": {"items": 4, "found_again": 3, "by_type": {"measurement": [4, 3]}},
         "items_by_extractor": {"llm": [2, 1], "agent": [0, 0], "other": [2, 2]},
         "answers": {"compared": 2, "same_text": 1, "same_headline": 2, "whys": ["b"]}}
    total = combine([r, r | {"answers": r["answers"] | {"whys": ["a", "b"]}}])
    assert total["runs"] == 2 and total["reruns"] == 4 and total["calls"]["llm"]["identical"] == 2
    assert total["items"]["by_type"]["measurement"] == [8, 6] and total["answers"]["same_text"] == 2
    assert total["items_by_extractor"]["llm"] == [4, 2] and total["answers"]["whys"] == ["a", "b"]

def test_the_command_measures_n_reruns(tmp_path, monkeypatch, capsys):
    root = written_run(tmp_path, GOOD)
    monkeypatch.setattr(replay_module, "default_provider", lambda alias: writer_model([], GOOD))
    assert cli.main(["reexec", str(root), "--all-calls", "--times", "2", "--out", str(tmp_path / "re")]) == 0
    assert "Final answer the same: text in 2 of 2 re-runs, headline in 2 of 2" in capsys.readouterr().out
    assert (tmp_path / "re" / "stability.json").is_file()
    assert cli.main(["reexec", str(root), "--times", "2", "--out", str(tmp_path / "x")]) == 2   # needs --all-calls
    assert cli.main(["reexec", str(root), "--all-calls", "--times", "2"]) == 2                  # needs --out
    assert cli.main(["reexec", str(root), "--all-calls", "--times", "1", "--out", str(root / "re")]) == 2
```

- [ ] **Step 2: Run** `uv run pytest -q evidence/tests/test_stability.py`. Expected: FAIL.
- [ ] **Step 3: Implement** `stability.py`, the `--times` option and the README line.
- [ ] **Step 4: Run** the file and Task 6's. Expected: PASS.
- [ ] **Step 5: Commit** the four files: `evidence: the re-run measure (identical calls, items found again, same answer)`.

### Task 8: `synth3 reexec`: one folder re-run 5 times

**Files:**
- Create: `backend/synth3/remeasure.py`, `backend/synth3/rcli.py` (`add_replay_commands(sub)`),
  `backend/synth3/tests/test_remeasure.py`
- Modify: `backend/synth3/cli.py` (one call to `add_replay_commands(sub)`), `backend/README.md` (one Run line)

**Interfaces:**
- Consumes: `evidence.replay.reexec` (imported as `reexec` into `remeasure`, so tests can replace it),
  `evidence.stability` (`measure`, `combine`, `render`); `synth3.system.run_path`; `RunDir`; `jsonio.write_json_atomic`;
  `synth3.cliargs` (`_spec`, `BadArgument`, `_ascii`), `synth3.qcli._questions`, `RESULTS`.
- Produces: `reexec_root(results: Path, domain: str, seed: int) -> Path` = `results / domain / "reexec" / f"s{seed}"`.
- Produces: `measure_folder(results: Path, domain: str, seed: int, qids: Sequence[str], *, times: int = 5,
  provider=None, rerun=None) -> dict` (`rerun` None: `remeasure.reexec`, looked up at call time), per question:
  - the original `run_path(results, domain, seed, qid)` not complete → `skipped[qid] = "no complete run; run synth3
    system-run first"`;
  - the question's folder `reexec_root(...) / qid` holds `source.json` `{run: <original path relative to results>,
    chain_head: <original run.json chain_head>}`; when it names another chain head the folder is moved aside to
    `<qid>.old-<n>` (never deleted) and started again;
  - the complete re-runs already there (each a folder with `reexec.json`, sealed complete) are kept; `times - kept`
    more are made with `rerun(original, all_calls=True, out_dir=<the question's folder>, **({"provider": provider} if
    provider else {}))`, one after another; an exception lists `failed[qid]` with its redacted reason (first 300
    characters) and the next question goes on;
  - `measure(original, <the first `times` re-runs, by name>)` is written to the question's folder as `stability.json`.
  Returns and writes to `reexec_root(...) / "report.json"`: `{domain, seed, times, questions: {qid: measure}, total:
  combine(...), made: <re-runs made now>, kept: <re-runs kept>, skipped, failed, commits: {<re-run folder name>:
  <its manifest.json code_commit or None>}}` (review M10: kept re-runs may come from other code).
- The printed report gains, when `commits` holds more than one distinct commit, the line `  note: the re-runs come
  from <n> code commits (<commits, ", ">); another commit can change every request`.
- Produces: `synth3 reexec --domain D --seed N [--times 5] [--questions QID,QID] [--questions-root Q] [--spec-root S]
  [--results R]`: the questions default to every question of the domain's file; an unknown id is exit 2 naming it;
  prints `render(total)` (its first line names `<runs> runs`), then per question `  <qid>: text same <a>/<n>, headline
  <b>/<n>, identical calls <share over every group>`, then each skipped and failed reason; exit 1 when anything failed.
  Run line: `uv run synth3 reexec --domain D --seed N [--times 5]   # re-run one folder's system runs N times with no
  cache (orch-model, cluster) and report identical calls, items found again and same answers;
  data/synth3/results/D/reexec/sN/report.json`.

- [ ] **Step 1: Write the failing tests** (`folder` fixture and `q()` of the synth3 conftest; `demo_plan`,
  `make_system_run`, `system_model`, `FACT_REPLY` of `synth3/tests/systemrun.py`; `provider_of` of the evidence
  conftest; `load_answers` of `synth3.answers`; `sha256_hex` of `jsonio`):

```python
def original(folder, tmp_path, SPEC, qid="d01", answer_by="written"):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?").model_copy(update={"id": qid})
    res = tmp_path / "res"
    return res, make_system_run(res / "demo" / "runs" / "s1", f, qq, demo_plan(SPEC, qq, answer_by),
                                writer_reply=FACT_REPLY, run_id=qid)

def fake(writer_reply=FACT_REPLY):
    return provider_of(system_model(writer_reply))

def hashes(*roots):
    return {str(p): sha256_hex(p.read_bytes()) for r in roots for p in sorted(Path(r).rglob("*")) if p.is_file()}

def test_one_folder_is_rerun_and_reported(folder, tmp_path, SPEC):
    res, run = original(folder, tmp_path, SPEC)
    cache = run.parent.parent / "cache"     # make_system_run's record cache: <out>.parent / "cache"
    before = hashes(run, cache); answers = load_answers(res, "demo")
    out = measure_folder(res, "demo", 1, ["d01"], times=2, provider=fake())
    assert out["made"] == 2 and out["questions"]["d01"]["answers"]["same_text"] == 2
    assert (reexec_root(res, "demo", 1) / "report.json").is_file() and len(out["commits"]) == 2
    assert (reexec_root(res, "demo", 1) / "d01" / "stability.json").is_file()
    assert hashes(run, cache) == before and load_answers(res, "demo") == answers   # review M3
    assert not list((res / "demo" / "runs" / "s1").glob("*reexec*"))

def test_a_second_call_keeps_reruns_and_tops_up(folder, tmp_path, SPEC):
    res, _ = original(folder, tmp_path, SPEC)
    measure_folder(res, "demo", 1, ["d01"], times=2, provider=fake())
    assert measure_folder(res, "demo", 1, ["d01"], times=2, provider=fake())["made"] == 0
    assert measure_folder(res, "demo", 1, ["d01"], times=3, provider=fake())["made"] == 1

def test_a_replaced_run_moves_old_reruns_aside(folder, tmp_path, SPEC):
    res, run = original(folder, tmp_path, SPEC)
    measure_folder(res, "demo", 1, ["d01"], times=1, provider=fake())
    shutil.rmtree(run)
    original(folder, tmp_path, SPEC, answer_by="effect")   # another protocol: another chain head
    out = measure_folder(res, "demo", 1, ["d01"], times=1, provider=fake())
    assert out["made"] == 1 and (reexec_root(res, "demo", 1) / "d01.old-1").is_dir()

def test_missing_and_failing_runs_are_listed_and_the_rest_go_on(folder, tmp_path, SPEC, monkeypatch):
    res, _ = original(folder, tmp_path, SPEC)
    original(folder, tmp_path, SPEC, qid="d02")
    real = remeasure.reexec
    def flaky(run, **kw):
        if Path(run).name == "d02":
            raise RuntimeError("gateway down")
        return real(run, **kw)
    monkeypatch.setattr(remeasure, "reexec", flaky)
    out = measure_folder(res, "demo", 1, ["d01", "d02", "d03"], times=1, provider=fake())
    assert out["skipped"] == {"d03": "no complete run; run synth3 system-run first"}
    assert "gateway down" in out["failed"]["d02"] and out["questions"]["d01"]["reruns"] == 1

def test_the_command(folder, tmp_path, spec_dir, monkeypatch, capsys):
    res, _ = original(folder, tmp_path, load_spec("demo", spec_dir), qid="d01")
    monkeypatch.setattr(replay_module, "default_provider", lambda alias: system_model(FACT_REPLY))
    args = ["reexec", "--domain", "demo", "--seed", "1", "--times", "1", "--questions", "d01",
            "--questions-root", str(FIX), "--spec-root", str(spec_dir), "--results", str(res)]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert out.startswith("Re-run measure: 1 runs x 1 re-runs, no cache") and "  d01: text same 1/1" in out
    unknown = [a if a != "d01" else "zz" for a in args]
    assert main(unknown) == 2
```

  (`FIX` is the questions fixture folder of the synth3 tests, as `test_system_plan.py` uses it.)
- [ ] **Step 2: Run** `uv run pytest -q synth3/tests/test_remeasure.py`. Expected: FAIL.
- [ ] **Step 3: Implement** `remeasure.py`, `rcli.py`, the `cli.py` call and the README line.
- [ ] **Step 4: Run** `uv run pytest -q synth3 tests/test_boundaries.py`. Expected: PASS.
- [ ] **Step 5: Commit** the six files: `synth3: reexec re-runs one folder's system runs with no cache and reports`.

### Task 9: The program from the web API

**Files:**
- Modify: `backend/webapp/evsystem.py` (`SystemSteps.program_refused`, `GET /system/runs/{rid}/program`),
  `backend/webapp/tests/test_evsystem.py` (fixture gains a lines run; new tests), `frontend/openapi.json`,
  `frontend/src/api/schema.d.ts` (regenerated)

**Interfaces:**
- Consumes: `evidence.readable` (`program_of_run`, `refusal`, `NotRebuilt`); `system_run`; `Conflict` (409).
- Produces: `SystemSteps.program_refused: str | None` (= `refusal(run)` for a done run; the not-complete text for a
  running or failed one).
- Produces: `GET /api/ev/system/runs/{rid}/program` (`tags=["system"]`): 200 with `program_of_run(run)` as
  `text/x-python; charset=utf-8` and `Content-Disposition: attachment; filename="<rid>-answer.py"`; 409 with the
  refusal text for `NotRebuilt`; 404 as the other system paths.

- [ ] **Step 1: Write the failing tests** (the `system_runs` fixture of plan 4 also makes `d01l`, a copy of `d01`
  with `demo_plan(SPEC, q, "lines")`, and returns it under `"lines"`):

```python
def test_the_program_downloads_and_rebuilds_the_answer(system_runs, tmp_path, review_root):
    c = client(tmp_path, review_root)
    for rid in (system_runs["written"], system_runs["effect"]):
        r = c.get(f"/api/ev/system/runs/{rid}/program")
        assert r.status_code == 200 and r.headers["content-disposition"] == f'attachment; filename="{rid}-answer.py"'
        path = tmp_path / f"{rid}-answer.py"; path.write_bytes(r.content)
        done = subprocess.run([sys.executable, "-I", "-S", str(path)], capture_output=True, timeout=120)
        assert done.returncode == 0 and done.stdout.decode("utf-8").splitlines()[-1] == CHECK_OK
        assert c.get(f"/api/ev/system/runs/{rid}/steps").json()["program_refused"] is None

def test_a_lines_run_has_no_program(system_runs, tmp_path, review_root):
    c = client(tmp_path, review_root)
    assert c.get(f"/api/ev/system/runs/{system_runs['lines']}/steps").json()["program_refused"] == LINES
    r = c.get(f"/api/ev/system/runs/{system_runs['lines']}/program")
    assert r.status_code == 409 and r.json()["detail"] == LINES

def test_a_bad_id_gets_no_program(system_runs, tmp_path, review_root):
    assert client(tmp_path, review_root).get("/api/ev/system/runs/..%2Fx/program").status_code in (400, 404, 422)
```

- [ ] **Step 2: Run** `uv run pytest -q webapp/tests/test_evsystem.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the field and the route.
- [ ] **Step 4: Run** `uv run pytest -q webapp` and the API type regeneration (Global Constraints). Expected: PASS;
  `frontend/src/api/schema.d.ts` gains `program_refused` and the `/program` path.
- [ ] **Step 5: Commit** `backend/webapp/evsystem.py`, `backend/webapp/tests/test_evsystem.py`,
  `frontend/openapi.json`, `frontend/src/api/schema.d.ts`: `webapp: download a system run as its readable program`.

### Task 10: The download link on the one-page UI

**Files:**
- Modify: `frontend/src/routes/system/AnswerBox.tsx` (prop `run: string | null`), `SystemPage.tsx` (passes `run`),
  `frontend/src/routes/system/api.ts` (`SystemSteps.program_refused: string | null`), `frontend/src/mocks/system.ts`
  (`program_refused: null`), `frontend/src/routes/system/system.test.tsx`, `frontend/dist/` (rebuilt)

**Interfaces:**
- Consumes: Task 9's field and path.
- The answer box, under the answer: when `program_refused` is null, a link `Download the readable program` with
  `href="/api/ev/system/runs/<run>/program"` and the `download` attribute, and the muted line `A Python file that
  rebuilds this answer from the facts it used, with no papers and no AI.`; else the muted line `No readable program:
  <reason>`.

- [ ] **Step 1: Write the failing tests** in `system.test.tsx` (inside "the run and the answer"):
  - `it("offers the readable program of a finished run")`: once the run is done, a link named "Download the readable
    program" has `href` `/api/ev/system/runs/<the mocked run id>/program` and a `download` attribute;
  - `it("says why a run has no readable program")`: the steps handler answers `program_refused: "a plan answered by
    its lines ..."`; no such link exists and the text `No readable program: a plan answered by its lines ...` is shown.
- [ ] **Step 2: Run** `uv run --group frontend npm test -- system` in `frontend/`. Expected: FAIL.
- [ ] **Step 3: Implement** the link, the prop, the type and the mock.
- [ ] **Step 4: Run** `uv run --group frontend npm test`, `npm run typecheck`, `npm run lint`, then `npm run build`
  (each through `uv run --group frontend`). Expected: PASS, `frontend/dist` rebuilt.
- [ ] **Step 5: Commit** the five source files and `frontend/dist` (by path): `webapp: download the readable program
  from the answer box`.

### Task 11: Close: the whole suite and the list for Aditya

**Files:**
- Create: `docs/superpowers/plans/2026-11-20-synth3-replay-handoff.md` (the handoff, as plans 2-4 wrote theirs)
- Not committed: `.superpowers/sdd/synth3-program.md` (the program ledger: add the plan 5 lines and the list below)

- [ ] **Step 1: Run the whole suite** (Global Constraints). Expected: PASS apart from the known `agent/tests` import
  errors. Run `uv run evidence --help` and `uv run synth3 --help`: `program` and `reexec` are listed.
- [ ] **Step 2: Check the gates held:** `git ls-files data/synth3/results data/synth3/built data/synth3/pools` prints
  nothing; `git status --short data/synth3` shows no staged file; `git log --stat main..HEAD` holds no `*-answer.py`.
- [ ] **Step 3: Write the handoff** (state, what it does in one breath, the decisions below with their cost, parked
  issues, the list) and **commit it**: `docs: synth3 replay handoff (plan 5)`.
- [ ] **Step 4: The list "for Aditya to run or decide"** (in this order; the plan does not wait), into the handoff and
  the ledger:
  1. After plan 4's `system-run` on medicine (and before or after the judge): on the cluster
     `uv run synth3 reexec --domain medicine --seed 1 --times 5` (25 runs x 5 re-runs of 40 papers, every model call
     asked again, one after another: heavy; `--questions d01,d02` measures fewer). Run it again after a failure: it
     keeps every finished re-run. Read `data/synth3/results/medicine/reexec/s1/report.json`.
  2. **Decide:** the agentic extractor (temperature 0.7) is not in the system's plan runs, so its row reads "no calls
     in these runs". To measure it, re-run an old RAG run that used it: `uv run evidence reexec RUN --all-calls
     --times 5 --out DIR` (cluster) — or say the agentic row stays empty.
  3. Download one program from `/system` (or `uv run evidence program data/synth3/results/medicine/runs/s1/d01 --out
     data/synth3/results/medicine/programs/s1-d01.py`), read it, and run it with `python` on a machine without the
     repo. Programs quote renamed real papers: keep them local, like the folders.
  4. **Decide:** answers made by a plan's lines (the `/plan` page's default) and the kinds chaining, limitations and
     builds_on get no program yet; nor do best or inventory runs with the names step on. Say if any of them is needed.
  5. **Decide:** "the final answer stays the same" is measured as the same answer text (exact) and the same headline
     (label, winner, agreement counts, names, written status). Say if the judge should mark the re-run answers instead.
     It measures one run's calls asked again once, not the system's writer retry policy: a re-run whose written reply
     fails its checks counts as an empty answer, where `system-run` would ask again at the next try (review M7).
  6. **Decide (it defines "rebuilds the answer" in the thesis):** the program records which values each paper
     compared (the pairing rule's and the best kind's choice) and rebuilds every step after them; it does not choose
     them again from all pulled values. Say if the thesis needs the choice rebuilt too (review M6).
  7. Before step 1, confirm the model gateway (LiteLLM) has its response cache off: the engine's caches are all
     bypassed, but a gateway cache would make every re-run "identical" (review M9).
  8. Spec §11 still lists the thesis deadline (20 or 40 papers per folder); §10c already says 40 for synth3. Confirm and
     the spec line can go (review M11).

---

## Decisions the planner made

Each with its cost if wrong.

1. **The program rebuilds from the facts the rules used, not from every pulled item.** The engine's per-paper choice
   (which treatment and control values the pairing rule picked, which values a best paper compared) and the reason a
   paper could not be read are recorded values in `PAPERS`; the program rebuilds every step after them (directions,
   differences, repeats, large effects, claim agreement, counts, the label table, wins, ties, names, the lines). This
   matches spec §9 "only the facts that were used"; the program's header says it in one sentence, and it is on
   Aditya's list (item 6). Cost if wrong: one more rules file that copies the pairing rule (`synthesis._pair`,
   `best_value` with table-cell detection) and a fact for every candidate value.
2. **The copied rules are real stdlib modules in `evidence/readable/rules/`, pasted into each program.** They are
   unit-tested by import, pinned to the engine's constants by drift tests, and checked against the engine's answers on
   handcrafted cases and on real plan runs. Cost if wrong: none for the program; a later engine rule change needs the
   copy changed too (the tests fail until it is).
3. **"Rebuilds the answer" is checked two ways, by tests and by the program itself:** its printed text equals the
   recorded answer text byte for byte (the kind lines plan 4 gives the judge, or the written text), and its rebuilt
   values equal a projection of the recorded answer (item ids left out); the program holds both sha256s and prints
   `Check FAILED` and exits 1 when either differs. Cost if wrong: a fuller projection (with item ids) later.
4. **The written answer:** the model's sentences are pasted (`MODEL_TEXT`, marked); the program rebuilds every fact
   text from values, re-runs the code checks on each recorded reply, chooses the reply the run accepted, and adds the
   paper ids. A failed writer call has no program (it is rerun with retry, plan 4). Cost if wrong: none.
5. **Refused, each with a named reason:** plan runs answered by lines, the kinds chaining, limitations and builds_on,
   subsets (moderators), best and inventory with the names step on, unfinished runs, and a run whose pair or values
   cannot be found again. None occurs in the synth3 system runs. `refusal()` also builds the inputs, so the page and
   the download always agree. Runs made with the reasoner on are not refused: their inferences (reason.json) go to the
   recompute, as the engine used them (review I2; one argument, smaller than a refusal). Cost if wrong: one task per
   kind later (on Aditya's list).
6. **"No cache" is a new `--all-calls` re-execution:** every extractor bypassed and the run's own stage calls asked
   again (a repeat inside one re-run asked once); fresh replies never enter the record cache; a re-run keeps its
   `calls.jsonl`. The existing `reexec` (stage calls read from the record) is unchanged. Declined from review M9: running
   `--all-calls` over an empty throw-away cache, because no code path of `--all-calls` reads a cached reply (the
   reviewer checked each) and the gateway cache, the real risk, is on Aditya's list. Cost if wrong: an engine flag.
7. **An identical model call means the same request got the same reply;** calls are paired by slot (row and record
   position) when the request is the same, else by request, so an earlier step that changed shows as "not asked again"
   and "new", never as a different reply to another question. A record the measure cannot read is counted
   "unreadable", never identical. Cost if wrong: a different matching later.
8. **Groups come from the extractor's kind in run.json** (LLM extractors, agentic extractor, stages, names check). A
   record is read by its shape: the engine's records give request, reply, temperature and served model; the agentic
   extractor's give a step and a reply hash, with the temperature from its spec and the served model from its run
   record, or "unknown" (review C1). Item stability is also split by extractor kind from each re-run's `reexec.json`
   (review I4). The system's plan runs have no agentic extractor, so those rows read "no calls" / "no items"
   (Aditya's list, item 2). Cost if wrong: one more command run.
9. **The final answer "stays the same" when its text is identical; a headline match is reported beside it.** Cost if
   wrong: a definition change in `stability.same_answer`.
10. **The measurement is a synth3 command over one folder's kept system runs;** re-runs live under
    `results/<d>/reexec/s<n>/<qid>/`, tied to their original by its chain head (old ones moved aside), never under
    `runs/`, never collected or judged. They run one after another. Cost if wrong: time on the cluster.
11. **`evidence program` needs `--out` and never writes into the run folder** (it is sealed), nor into the repository
    where git would see it (a program quotes papers); `evidence reexec --times` needs `--out` too. Only `/system`
    offers the download (the `/plan` page's runs are answered by lines, which are refused). Cost if wrong: one link
    later.
12. **A fact's section is the last Markdown heading above its first span**, read from the corpus when it is at hand,
    else "unknown"; the program is still made and still rebuilds. Cost if wrong: a wrong section name on papers
    without headings.
