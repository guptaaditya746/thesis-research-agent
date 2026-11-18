# synth3 System (plan 4 of 5): model-written answers, the sub-question box and the one-page UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the system that answers Aditya's questions on the synth3 folders: the AI drafts a plan (the protocol) from
the main question and its sub-questions, a person edits it, the engine pulls facts per paper, and the answer is
either written by a model from those facts, with each sentence citing its facts, or made by the rules of a fixed kind
(effect, consistency, inventory, best). Every answer goes into plan 3's judge shape. A new one-page UI shows the
whole chain, box by box.

**Architecture:**
- **The system is a plan run** (the W7 planner, `evidence/planner`, `evidence/planrun.py`). The planner is "Tim's
  compiler chain": question → evidence lines → things and measures → rule → decisions → queries; code compiles the
  confirmed plan into a protocol (`planrun.protocol_for`) and the engine pulls facts per paper. Nothing new is built
  for extraction. The plan page (`/plan`) is "the planning page" of spec §8.
- **Sub-questions** go into the planner's lines and things steps through two new versioned signatures, used only when
  sub-questions are given (old plans and old prompts unchanged). The plan keeps them (`Plan.sub_questions`).
- **How the answer is made** is part of the plan (`Plan.answer_by`): `lines` (today's plan page answer), `written`
  (any question), or one of the four fixed kinds. A fixed kind turns the plan's protocol into that kind's protocol by
  code (`evidence/plankinds.py`), so the kind's own rules (`evidence/kinds/`) make the answer.
- **The written answer is a run stage** (`evidence/written.py`, after_run stage `written-answer`): code picks the
  facts that bear on the plan, round-robin over the papers so every paper with facts is in, up to a budget sized from
  the model's context window; orch-model writes 1 to 8 sentences each citing fact numbers; code checks every sentence
  (facts listed, numbers copied from its facts, no paper ids), gives one repair call, and adds the paper ids itself.
  The call goes through the run's recorder (`ctx.ask`), so the run replays byte for byte and plan 5 can read it.
- **A person edits the plan; skipping that is Aditya's recorded choice.** Batch plans live in
  `data/synth3/plans/<domain>/`, open on `/plan` for editing, and `system-run` refuses a plan no person confirmed
  unless `--confirm-as-system` is given, which runs a separate confirmed copy and never touches the draft. Every
  answer record says who confirmed its plan, and the report counts it.
- **synth3 glue** (`backend/synth3/system.py`, commands in `backend/synth3/scli.py`): one plan per question (shared by
  the 5 folders), one plan run per question and folder (a failed written answer or unchecked items are run again),
  and `from_system_run` puts each run into an `AnswerRecord`. `collect` reads plan runs too.
- **Web:** the plan API takes sub-questions, the answer kind, a synth3 folder and batch plans (`webapp/evplan.py`,
  `webapp/planwire.py`); a new read-only API `webapp/evsystem.py` (`/api/ev/system`) lists the domains, folders and
  questions and turns a finished run into the four rows (Find, Pull out, Combine, Answer) and a paper view. A new
  page `/system` (`frontend/src/routes/system/`) stacks the five boxes of spec §8; the plan page gets a sub-question
  box and opens batch plans.

**Tech Stack:** Python >= 3.13, pydantic, pyyaml, DSPy steps (`evidence.steps.Step`), pydantic-ai `FunctionModel` and
`RecordedLM` fakes in tests, FastAPI `TestClient`; React 19 + TanStack Query + Vitest + MSW for the page. No new
dependencies.

**Spec:** `docs/superpowers/specs/2026-11-16-multi-domain-benchmark-design.md` (§8 "The system (job 2)", §6
"Sub-questions", §7 "Baseline", §9 "Model-written answers", §10b "can't tell" and "Score B", §11). Read with it:
plan 3's handoff `docs/superpowers/plans/2026-11-18-synth3-questions-judge-handoff.md` ("Notes" for plan 4 are
requirements here) and `docs/prompt-writing.md`.

**The five plans:**
1. Worlds and template folders (merged).
2. Real-paper planting per domain (branch `synth3-real`).
3. Questions, checklist answer sheets, the judge, the review page, the baseline (branch `synth3-questions`).
4. **This plan:** the system: model-written answers, the sub-question box and the one-page UI.
5. The readable evidence program and the 5-re-run measurement.

**Review history:** written 17 Nov 2026 by a planner agent. A fresh reviewer found 1 critical, 4 important and 17
minor issues (`.superpowers/sdd/plan4-review.md`). The controller's rulings, all applied here: C1 in full (no plan
runs unreviewed by default; `--confirm-as-system` writes a separate copy; batch plans open on `/plan`; records and
report say who confirmed); I1 (no paper dropped by order: plan-bearing facts, round-robin, a budget from the model
limit, the cut recorded); I2 (`system-run` reruns a failed written answer or unchecked items with a fresh key); I3
(the writer fake reads the instructions); I4 (`POST /plan` takes the answer kind); all 17 minors; kind hashing: the
system's records hash kind and target (`asked_sha256`), the baseline's keep plan 3's hash.

## Global Constraints

- **Human gates (program ruling):** Aditya writes the questions, approves specs and worlds, checks sheets and
  hand-marks the judge test. This plan writes no question set, plan or run under `data/`; tests use the demo fixtures
  of `backend/synth3/tests/` and `tmp_path`. Spec §8 puts a person's edit of the plan inside the system: a plan no
  person confirmed never runs unless Aditya passes `--confirm-as-system`, and that choice is recorded in every answer
  record and counted in the report. `confirm_all` stamps only unconfirmed decisions, so a person's confirmation keeps
  his name.
- **No new LLM, no cluster run:** generation uses `orch-model` (the planner through `evaluation.planbatch.orch_lm`,
  the writer through the run's `ctx.ask` with `model=ORCH_ALIAS`); verification stays plan 3's judge (`sub-model-1`).
  Every model call in a test is a fake: `RecordedLM` with a scripted `ask` (as `evidence/tests/test_planner.py`), a
  pydantic-ai `FunctionModel` behind `provider_of` (as `evidence/tests/test_plan_run.py`), or a monkeypatched
  function. No test opens a socket. Every run command goes on the "for Aditya" list (Task 17).
- **Prompt policy (`docs/prompt-writing.md`):** each new prompt (the writer prompt `written-answer-v1.md`, the two
  sub-question signatures) states the task first, then the inputs, the output fields, three examples (a normal case, a
  confusing case, a missing case) and the acceptance rules. Code checks every reply; a failed check gets one repair
  call holding the task input, the rejected reply and the failed checks (`MAX_REPAIRS = 1`); every attempt is kept
  in the stage output (`tries`). Generation (`orch-model`, this plan) and verification (`sub-model-1`, plan 3's
  judge B) stay separate.
- **Prompt examples:** invented names only, never a name of any spec in `data/synth3/*.yaml` or
  `data/synth3/drafts/*.yaml`: control "Usual method", treatments "Method K" and "Method P", measures "Yield" (higher is
  better) and "Error count" (lower is better), groups "Small batches" / "Large batches", papers `S901`, `S902`. The
  examples together show better, worse (as fewer errors) and no real difference. Tests check the names (Tasks 3, 5).
- **Blindness (program rule):** no system name and no sub-question reaches a judge. The record text of a written
  answer is its sentences with paper ids; of a fixed kind, the code-written kind lines (`evidence/kindtext.py`, names
  not ids, never the answer JSON). The writer sees the main question only (plan 3's ruling: sub-questions are
  planning input only). Answer records keep the full question hash.
- **Hashes:** `question_sha256` stays plan 3's (`{question, sub_questions, about}`) and is what the baseline records
  carry. The system's records also carry `asked_sha256` = `{question, sub_questions, about, kind, target}`, which
  `marking.why_not` checks, so a kind edit asks for the system's answer again and never for the baseline's.
- **Hashed files:** never edit the files under "Hashed files: never edit" in `backend/README.md`. This plan edits
  `evidence/plan.py`, `evidence/planner/plan.py`, `evidence/planrun.py`, `evidence/stages.py` and `evidence/engine.py`
  (none listed) by small additions only; new behaviour is in new modules. New prompt files never go in
  `evidence/prompts/`, `evidence/extractors/prompts/` or `evidence/propose/prompts/` (hashed): the writer prompt goes in
  the new folder `backend/evidence/stage_prompts/`. `backend/synth2` is read-only.
- **Import cycles:** `planner/plan.py` imports `LINES_SUB`/`THINGS_SUB` inside `_line_drafts`/`_things_of` (subq.py
  imports `planner/plan.py`); `planrun.run` imports `kind_protocol` inside the function (plankinds.py imports
  `planrun`); `planrun.stage_entries` imports `written` inside the function.
- **Old runs and plans unchanged:** the new `Plan` fields are left out of the plan's dump and sha256 while they hold
  their defaults (`exclude_if`, as `WordList.tuned_sha256` does), so every saved plan keeps its sha256 and every
  recorded plan run replays as before. A `lines` plan run has the same stages as today.
- **Boundaries:** engine code (`evidence`) never imports `synth3` or `webapp`; `synth3` may import `evidence`,
  `evaluation`, `modelcall`, `jsonio`; `webapp` may import all of them. No new top-level package.
- **Files and folders:**
  - batch plans: drafts `data/synth3/plans/<domain>/<qid>.json`, system-confirmed copies
    `data/synth3/plans/<domain>/auto/<qid>.json` (no paper text; Aditya commits them if he wants; this plan never
    does);
  - local only, git-ignored (already, plan 3): `data/synth3/results/`, holding the run folders
    `results/<domain>/runs/s<seed>/<qid>/`, the run record cache `results/<domain>/run-cache/`, the planner caches
    `results/<domain>/planner*.jsonl` and the answer records;
  - never commit `data/synth3/pools/`, `data/synth3/built/`, `data/synth3/results/`. Runs started from `/system` go
    under `$EV/runs` and hold quotes of renamed papers: `$EV` must be outside the repo or git-ignored (Aditya's list).
- **System name:** plan 4's answer records use system id `system` (`synth3.system.SYSTEM`).
- **synth3 runs:** `reason="off"`, `links="off"` (no reasoner and no OpenAlex request on renamed papers),
  `strategy` the plan run's default, `workers` 3 (a CLI option).
- **Text files:** every read and write passes `encoding="utf-8"`; JSON is written with `jsonio.write_json_atomic`
  (synth3) or the engine's own writers (stages).
- **Git:** work on the existing branch `synth3-system`. Stage files by name only; never stage
  `backend/agent/tests/test_prompts.py`. Never push or merge. End every commit message with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Tests:** `uv run pytest -q <file>` per task; `uv run pytest -q backend/synth3 backend/evidence/tests/test_plan_run.py`
  after Tasks 1, 8, 10 and 11; `uv run pytest -q backend/webapp` in Tasks 12 and 13; in `frontend/`, `npm test`,
  `npm run typecheck`, `npm run lint` in Tasks 14 to 16; the whole suite at the end of Tasks 6 and 17 (on Windows with
  the two `--ignore`s from `backend/README.md`; the 10 `agent/tests` import errors are known).
- **No `...` in tests:** every test below is written out with the assertions given; where a body is described in
  words, those words name every assertion.

## Review Focus

- **The writer makes up a number or cites a fact that is not there:** a pooled "12%" the facts never state, fact
  `[9]` of 4 facts, a paper id typed into the sentence. `45%` for a fact `0.45` and "3 of 4 studies" over 4 cited
  facts are fine. Code refuses the rest with a named problem, gives one repair, and a reply still bad gives status
  `failed` and an empty answer, which `system-run` asks again with a fresh key (Tasks 5, 6, 10 tests).
- **A late paper never reaching the writer:** 40 papers with 10 facts each must give every paper at least one fact
  in the writer's input, and the facts left out are recorded and reported (Task 5, 11 tests).
- **A run collected or kept for another question or another plan:** the question text, a sub-question, the kind or
  the target changed, the plan was edited, or the run is of another folder. `from_system_run` refuses with the reason;
  `system-run` skips, reruns or replans (Tasks 8, 9, 10 tests).
- **The judge learning the system or a sub-question:** the record text never holds `evidence-engine`, `plan-`,
  `orch-model`, the plan's line questions or a sub-question (Task 8 test
  `test_the_record_holds_no_sub_question_and_no_system_name`).
- **Unreviewed plans passing as the spec's system:** a draft with an unconfirmed decision is skipped by `system-run`
  without `--confirm-as-system`; with it, the draft file stays byte-identical and every record says
  `plan_confirmed_by: "system"`, counted in the report (Tasks 10, 11 tests).

---

### Task 1: The question's inventory target and the system's answer hash

**Files:**
- Modify: `backend/synth3/questions.py`, `backend/synth3/answers.py` (one field), `backend/synth3/marking.py`
  (`why_not`), `backend/synth3/tests/test_questions.py`, `backend/synth3/tests/test_marking.py`

**Interfaces:**
- Consumes: `Question`, `question_sha256` (plan 3, unchanged), `AnswerRecord`, `why_not`.
- Produces: `TARGETS = ("condition", "metric")`; `Question.target: Literal[*TARGETS] | None = None` (allowed only with
  `kind: inventory`; `ValueError` `"<qid>: target is only for kind inventory"`); docstring example gains one inventory
  question with `target: metric` and the line "target: condition (the compared things, the default) or metric (the
  measures); inventory only".
- Produces: `asked_sha256(q: Question) -> str`: sha256 of canonical `{question, sub_questions, about, kind, target}`.
- Produces: `answer_by_of(q: Question) -> str`: `"written"` for `open`, else the kind.
  `target_of(q: Question) -> str | None`: `q.target or "condition"` for inventory, else `None`.
- Produces: `AnswerRecord.asked_sha256: str | None = None` (the system's records set it; baseline and engine records
  leave it `None`; old files load).
- Produces in `why_not`: after the `question_sha256` check, `rec.asked_sha256 is not None and rec.asked_sha256 !=
  asked_sha256(q)` → `"the answer was made for another kind of the question"`.

- [ ] **Step 1: Write the failing tests** (plan 3's `test_the_hash_ignores_notes_and_kind` stays as it is):

```python
def test_the_asked_hash_covers_kind_and_target():
    q = Question(id="x", question="Q?", sub_questions=["s?"])
    assert asked_sha256(q) == asked_sha256(q.model_copy(update={"notes": "n"}))
    assert asked_sha256(q) != asked_sha256(q.model_copy(update={"kind": "best"}))
    inv = q.model_copy(update={"kind": "inventory"})
    assert asked_sha256(inv) != asked_sha256(inv.model_copy(update={"target": "metric"}))
    assert question_sha256(q) == question_sha256(q.model_copy(update={"kind": "best"}))

def test_target_only_with_inventory(tmp_path, SPEC):
    d = yaml.safe_load((FIX / "demo.yaml").read_text(encoding="utf-8"))
    d["questions"][0].update(target="metric")
    with pytest.raises(ValueError, match="d01: target is only for kind inventory"):
        load_questions("demo", SPEC, write_q(tmp_path, d))

def test_how_the_system_answers_each_kind():
    assert answer_by_of(Question(id="x", question="Q?")) == "written"
    inv = Question(id="x", question="Q?", kind="inventory")
    assert answer_by_of(inv) == "inventory" and target_of(inv) == "condition"
    assert target_of(inv.model_copy(update={"target": "metric"})) == "metric"
    assert target_of(Question(id="x", question="Q?", kind="effect")) is None
```

  In `test_marking.py`:

```python
def test_a_kind_edit_skips_the_system_answer_but_not_the_baseline(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    sheet = make_sheet(f, qq, [("Targeted therapy does better.", ["pair:a:m1"])], {"model": "x"})
    sys_rec = engine_rec(f, qq, text="x").model_copy(update={"system": "system", "asked_sha256": asked_sha256(qq)})
    base_rec = engine_rec(f, qq, text="x").model_copy(update={"system": "rag-baseline"})
    edited = qq.model_copy(update={"kind": "effect"})
    assert why_not(f, edited, sheet, sys_rec) == "the answer was made for another kind of the question"
    assert why_not(f, edited, sheet, base_rec) is None
```

- [ ] **Step 2: Run** `uv run pytest -q backend/synth3/tests/test_questions.py backend/synth3/tests/test_marking.py`.
  Expected: FAIL (`ImportError` `asked_sha256`).
- [ ] **Step 3: Implement** the field, the check, `asked_sha256`, the two helpers, the record field and the
  `why_not` line.
- [ ] **Step 4: Run** `uv run pytest -q backend/synth3`. Expected: PASS.
- [ ] **Step 5: Commit** the five files: `synth3: an inventory target and a system answer hash that covers the kind`.

### Task 2: The plan keeps its sub-questions and how its answer is made

**Files:**
- Modify: `backend/evidence/plan.py`
- Create: `backend/evidence/tests/test_plan_fields.py`

**Interfaces:**
- Produces in `evidence/plan.py`: `AnswerBy = Literal["lines", "written", "effect", "consistency", "inventory", "best"]`;
  `ANSWER_BY: tuple[str, ...]` (its values); `TARGETS = ("condition", "metric")`.
- Produces on `Plan`:
  - `sub_questions: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)`;
  - `answer_by: AnswerBy = Field("lines", exclude_if=lambda v: v == "lines")`;
  - `target: Literal["condition", "metric"] | None = Field(None, exclude_if=lambda v: v is None)`;
  - `writer_try: int = Field(0, ge=0, exclude_if=lambda v: v == 0)` (which try of the written answer this run is;
    Task 6 adds it to the writer's cache key, Task 10 raises it to ask again past the cache);
  - a model validator: `target` set only with `answer_by == "inventory"` (`ValueError("target is only for an inventory
    answer")`); an empty sub-question is refused (`ValueError("a sub-question is empty")`).
- Produces: `with_answer(plan: Plan, answer_by: str, target: str | None) -> Plan`: a validated copy
  (`Plan.model_validate({**plan.model_dump(mode="json"), "answer_by": ..., "target": ...})`); `ValueError` for an
  unknown `answer_by`.

- [ ] **Step 1: Write the failing tests.** Before changing `plan.py`, run
  `uv run python -c "from evidence.tests.test_plan_run import make_plan; print(make_plan().sha256)"` and paste the
  printed value as the literal `OLD_SHA` in the test file.

```python
OLD_SHA = "<the value printed above>"

def test_an_old_plan_keeps_its_dump_and_sha256():
    old = make_plan()
    dumped = old.model_dump(mode="json")
    assert old.sha256 == OLD_SHA
    assert not {"sub_questions", "answer_by", "target", "writer_try"} & set(dumped)
    assert Plan.model_validate_json(old.model_dump_json()).answer_by == "lines"

def test_new_fields_change_the_sha256_and_round_trip(tmp_path):
    p = with_answer(make_plan().model_copy(update={"sub_questions": ["Which papers measured it?"]}), "inventory", "metric")
    write_plan(p, tmp_path / "p.json")
    back = load_plan(tmp_path / "p.json")
    assert back == p and back.sha256 != OLD_SHA and back.target == "metric"
    assert back.model_copy(update={"writer_try": 1}).sha256 != back.sha256

def test_target_only_for_inventory_and_no_empty_sub_question():
    with pytest.raises(ValueError, match="target is only for an inventory answer"):
        with_answer(make_plan(), "written", "metric")
    with pytest.raises(ValueError, match="a sub-question is empty"):
        Plan.model_validate({**make_plan().model_dump(mode="json"), "sub_questions": [" "]})
    with pytest.raises(ValueError):
        with_answer(make_plan(), "chaining", None)
```

- [ ] **Step 2: Run** `uv run pytest -q backend/evidence/tests/test_plan_fields.py`. Expected: FAIL (`ImportError`).
- [ ] **Step 3: Implement** the fields, the validator and `with_answer`.
- [ ] **Step 4: Run** the new tests and `uv run pytest -q backend/evidence/tests/test_plan.py
  backend/evidence/tests/test_plan_run.py backend/evidence/tests/test_planner.py` (old plans, the lock fixture and
  replays unchanged). Expected: PASS.
- [ ] **Step 5: Commit** `backend/evidence/plan.py`, `backend/evidence/tests/test_plan_fields.py`:
  `evidence: a plan keeps its sub-questions and how its answer is made`.

### Task 3: The planner reads the sub-questions

**Files:**
- Create: `backend/evidence/planner/subq.py`, `backend/evidence/tests/test_planner_subq.py`
- Modify: `backend/evidence/planner/plan.py` (`propose`, `_line_drafts`, `_things_of`: one keyword each)

**Interfaces:**
- Consumes: `LinesSig`, `ThingsSig`, `LineDraft`, `Step` (planner/plan.py, evidence/steps).
- Produces in `subq.py`:
  - `LinesSubSig(dspy.Signature)`: the inputs of `LinesSig` plus `sub_questions: str` (desc "JSON list of the parts
    of the question the person also wants looked at; may be empty"), the same output `lines: list[LineDraft]`;
  - `ThingsSubSig(dspy.Signature)`: the inputs of `ThingsSig` plus the same `sub_questions` field, the same outputs;
  - `LINES_SUB = Step(LinesSubSig, "planner_lines_sub")`, `THINGS_SUB = Step(ThingsSubSig, "planner_things_sub")`.
  Docstrings (task first): the lines one says "List what would prove or disprove the main question from papers ...
  The sub-questions name parts the person also wants looked at: give a line for each part they add when it helps
  answer the main question; never a line the main question does not need." The things one says the sub-questions may
  name more things or measures to look for (a group named only in a sub-question is not a thing). Three examples each
  with the invented names of the Global Constraints: normal (main "Does Method K improve Yield compared with the Usual
  method?", sub-question "Which studies measured Yield?" → an effect line and an inventory line), confusing (a
  sub-question "Does Method K also cut the Error count?" adds the measure `error_count` with `lower_is_better`), missing
  (a sub-question "Do Small batches differ?" adds no thing and no line beyond the effect line).
- Produces in `plan.py`: `propose(question, clarifications=None, *, write_words, templates=None, explain=True,
  sub_questions: Sequence[str] = ())`. With no sub-questions every call is exactly today's (same steps, same
  prompts, so cached plans and `test_planner.py` stay as they are). With sub-questions, `_line_drafts` calls
  `LINES_SUB` and `_things_of` calls `THINGS_SUB` (both imported inside the function: subq.py imports this module),
  with `sub_questions=json.dumps(list(sub_questions))`; the rule, decisions, query and explain steps get the main
  question only. The plan gets `sub_questions=list(sub_questions)`; `Plan.question` is the main question alone.

- [ ] **Step 1: Write the failing tests** with the `lm` fixture and `script`, `line`, `words` helpers copied from
  `evidence/tests/test_planner.py` (scripted replies in step order):

```python
def test_sub_questions_reach_the_lines_and_things_steps_only(lm):
    replies, seen = lm
    script(replies, [line()])
    plan, _ = propose("Does it help?", sub_questions=["Which papers measured it?"], write_words=words)
    assert plan.sub_questions == ["Which papers measured it?"] and plan.question == "Does it help?"
    with_sub = [p for p in seen if "Which papers measured it?" in p]
    assert len(with_sub) == 2 and all("sub_questions" in p for p in with_sub)

def test_without_sub_questions_the_old_steps_run(lm):
    replies, seen = lm
    script(replies, [line()])
    plan, _ = propose("Does it help?", write_words=words)
    assert plan.sub_questions == [] and not any("sub_questions" in p for p in seen)

def spec_name_hits(text: str) -> list[str]:
    names = {n for f in [*SPECS.glob("*.yaml"), *(SPECS / "drafts").glob("*.yaml")]
             for n in spec_names(load_spec(f.stem, f.parent))}
    assert names, "no spec names found: the check would pass on nothing"
    return sorted(n for n in names if re.search(rf"(?i)(?<!\w){re.escape(n)}(?!\w)", text))

@pytest.mark.parametrize("sig", [LinesSubSig, ThingsSubSig])
def test_examples_use_no_domain_name(sig):
    assert spec_name_hits(sig.__doc__) == []
    assert "Method K" in sig.__doc__ and "Usual method" in sig.__doc__
```

  (`SPECS`, `load_spec`, `spec_names` from `synth3`; tests may reach across packages. Task 5 imports
  `spec_name_hits` from this file.)
- [ ] **Step 2: Run** `uv run pytest -q backend/evidence/tests/test_planner_subq.py`. Expected: FAIL (`ImportError`).
- [ ] **Step 3: Implement** `subq.py` and the keyword in `propose`, `_line_drafts`, `_things_of`.
- [ ] **Step 4: Run** the new tests and `uv run pytest -q backend/evidence/tests/test_planner.py
  backend/evidence/tests/test_planner_ontology_names.py`. Expected: PASS.
- [ ] **Step 5: Commit** the three files: `evidence: the planner reads sub-questions through new versioned steps`.

### Task 4: Fixed kinds from a plan

**Files:**
- Create: `backend/evidence/plankinds.py`, `backend/evidence/tests/test_plankinds.py`
- Modify: `backend/evidence/planrun.py` (`run` writes `kind_protocol(plan)` instead of `protocol_for(plan)`,
  importing it inside the function)

**Interfaces:**
- Consumes: `protocol_for`, `planlines.sides`, `planlines.directions`, `planlines.OTHER`, `planrun.ANY`; `Plan`.
- Produces: `kind_protocol(plan: Plan) -> bytes`:
  - `lines`, `written`, `effect`: exactly `protocol_for(plan)` (byte-identical: old plan runs unchanged);
  - `consistency`: `kind: consistency` and `consistency: {by: direction}` added; `synthesis` kept;
  - `inventory`: `kind: inventory`, `inventory: {target: plan.target or "condition"}`, `synthesis` removed;
  - `best`: `kind: best`, `synthesis` removed; the `condition` type gains the optional field `kind` (string, enum the
    compared thing ids: `sides(plan)` without `other` and `any`) and its description gets "kind is the id of the
    thing the condition is: <ids>"; `best: {metric: {canonical: plan.measures[0], higher_is_better:
    directions(plan).get(m) is not False}, kinds: {thing: the plan's names of it (words.things + ontology_names,
    duplicates dropped)}}`.
  The header line names `evidence/plankinds.py kind_protocol` for every kind but the first three. Every result
  parses (`evidence.protocol.parse`).
- Produces: `answer_problems(plan: Plan) -> list[str]`: `"a best answer needs a measure"` (no measures);
  `"a best answer needs two compared things"` (fewer than two ids for `kinds`); none otherwise. The plan page and the
  batch treat these like `check_plan` problems.

- [ ] **Step 1: Write the failing tests** (`make_plan`, `plan_run` from `evidence.tests.test_plan_run`):

```python
def test_effect_written_and_lines_are_todays_protocol():
    for by in ("lines", "written", "effect"):
        plan = with_answer(make_plan(), by, None)
        assert kind_protocol(plan) == protocol_for(plan)

@pytest.mark.parametrize("by, target", [("consistency", None), ("inventory", "condition"), ("inventory", "metric"),
                                        ("best", None)])
def test_each_fixed_kind_parses_as_its_kind(by, target):
    p = parse(kind_protocol(with_answer(make_plan(), by, target)).decode("utf-8"))
    assert p.kind == by
    if by == "inventory":
        assert p.inventory.target == target and p.synthesis is None
    if by == "best":
        assert set(p.best.kinds) == {"rag", "closed_book"} and p.best.metric.canonical == "accuracy"
        assert "retrieval-augmented model" in p.best.kinds["rag"]
    if by == "consistency":
        assert p.consistency.by == "direction" and p.synthesis is not None

def test_best_without_a_measure_is_a_problem():
    plan = with_answer(make_plan(things={"rag": ["rag"], "closed_book": ["closed-book"]}, measures=()), "best", None)
    assert "a best answer needs a measure" in answer_problems(plan)
    assert answer_problems(with_answer(make_plan(), "best", None)) == []

def test_an_inventory_plan_run_answers_by_the_inventory_rule(tmp_path):
    root = plan_run(tmp_path, with_answer(make_plan(), "inventory", "condition"))
    answer = json.loads((root / "answer.json").read_text(encoding="utf-8"))
    assert answer["synthesis"]["kind"] == "inventory" and answer["synthesis"]["target"] == "condition"
    assert yaml.safe_load((root / "protocol.yaml").read_text(encoding="utf-8"))["kind"] == "inventory"
```

- [ ] **Step 2: Run** `uv run pytest -q backend/evidence/tests/test_plankinds.py`. Expected: FAIL (`ImportError`).
- [ ] **Step 3: Implement** `plankinds.py` (load `protocol_for`'s YAML with `yaml.safe_load`, change it, dump it the
  way `protocol_for` does) and the change in `planrun.run`.
- [ ] **Step 4: Run** the new tests and `uv run pytest -q backend/evidence/tests/test_plan_run.py
  backend/evidence/tests/test_plan_run_switches.py`. Expected: PASS.
- [ ] **Step 5: Commit** the three files: `evidence: a plan can answer by a fixed kind's rules`.

### Task 5: The written answer: facts, checks and the prompt

**Files:**
- Create: `backend/evidence/written.py` (this task: everything but the stage), `backend/evidence/stage_prompts/written-answer-v1.md`,
  `backend/evidence/tests/test_written.py`

**Interfaces:**
- Consumes: `evidence.contract.Item`; `Plan`, `planlines.sides`, `planlines.OTHER`, `planrun.ANY`;
  `modelcall.load_prompt`; `modelcall.pins.ORCH_ALIAS`, `modelcall.pins.ORCHESTRATOR` (its `context_tokens`).
- Produces: `STAGE = "written-answer"`; `PROMPT = Path(__file__).parent / "stage_prompts" / "written-answer-v1.md"`;
  `WRITER_ALIAS = ORCH_ALIAS`; `MAX_SENTENCES = 8`; `MAX_SENTENCE_CHARS = 400`; `MAX_QUOTE = 200`; `MAX_REPAIRS = 1`;
  `CHARS_PER_TOKEN = 4`; `FACT_SHARE = 0.5` (the share of the context window the facts may fill);
  `FACT_TYPES = ("measurement", "author_claim", "claim")` (builder's calls);
  `NO_FACTS_TEXT = "No paper in this folder gave a fact that answers the question."` (exact copy).
- Produces: `fact_budget(context_tokens: int) -> int` = `int(context_tokens * FACT_SHARE) * CHARS_PER_TOKEN`
  characters (orch-model's 65,536 tokens give 131,072 characters).
- Produces: `Fact(BaseModel)`: `n: int` (from 1), `item: str`, `paper: str`, `type: str`, `text: str`.
- Produces: `bears_on(item: Item, by_id: Mapping[str, Item], plan: Plan) -> bool`: a measurement whose linked
  condition's `role` is one of `sides(plan)` (not `other`, not `any`) and, when the plan has measures, whose linked
  metric's `canonical` is one of `plan.measures`; every author claim and claim of a paper that has such a measurement.
- Produces: `fact_lines(by_paper: Mapping[str, list[Item]], plan: Plan, budget: int) -> tuple[list[Fact], dict]`:
  1. per paper (the given order), its items of `FACT_TYPES` that `bears_on`, in item order, rendered (texts below);
  2. picked round-robin: the 1st fact of every paper, then the 2nd of every paper, ..., stopping when the next text
     would pass `budget` characters (counted as `len(text) + 16` each);
  3. numbered in paper order, then item order.
  The dict is the cut record: `{"pulled": <facts that bear on the plan>, "kept": <given to the writer>, "left_out":
  {paper: <its facts left out>} (papers with none left out are absent), "off_plan": <facts of FACT_TYPES that do
  not bear on the plan>}`.
  Texts (exact copy; a missing link or field reads `?`):
  - measurement: `<condition label> on <metric name> (<higher|lower> is better): <value>, <dataset or "no dataset
    named">. Quote: "<first span exact, cut at MAX_QUOTE>"`; the direction from the metric item's
    `higher_is_better`, left out when it has none;
  - author_claim: `The authors say: <direction>. Quote: "..."`;
  - claim: `<subject> <relation> <object> (<strength>). Quote: "..."`.
- Produces: `writer_input(question: str, facts: list[Fact]) -> str`: `Question: <question>\n\nFacts:\n[1] S003
  <text>\n[2] ...`.
- Produces: `Sentence(BaseModel)`: `text: str`, `says: Literal["finding", "cannot_tell"]`, `facts: list[int]`;
  `WrittenReply(BaseModel)`: `sentences: list[Sentence]`.
- Produces: `numbers(text: str) -> list[float]`: paper ids (`\bS\d{3}\b`) removed first, then thousands commas
  (`(?<=\d),(?=\d{3}\b)`), then every `\d+(?:\.\d+)?` read as a number.
- Produces: `check_written(reply: WrittenReply, facts: list[Fact]) -> list[str]`, problems naming the sentence:
  `"give 1 to 8 sentences"`; `"sentence 2: empty"`; `"sentence 2: longer than 400 characters"`; `"sentence 2: said
  twice"`; `"sentence 1: a finding cites at least one fact"`; `"sentence 3: a cannot_tell sentence cites no fact"`;
  `"sentence 1: fact 9 is not listed"`; `"sentence 1: leave paper ids out; the code adds them"`; `"sentence 1: the
  number 12 is in none of its facts"`. A number is fine when it equals (`abs(a - b) < 1e-9`) a number of its cited
  facts' texts, or that number times or divided by 100, or is a whole number from 1 to the count of its cited facts
  (a count such as "3 of 4 studies").
- Produces: `answer_text_of(reply: WrittenReply, facts: list[Fact]) -> tuple[str, list[dict]]`: the text (sentences
  joined by one space; a finding ends with ` (S003, S010).`, its cited facts' papers in first-seen order, its own
  final full stop dropped first) and the sentence rows `{text, says, facts, papers}`.
- Produces: `repair_input(first: str, rejected: WrittenReply, problems: list[str]) -> str` (the task input, the
  rejected reply as JSON, then `Fix only these problems:` and one problem per line), as `synth3/asking.py` does (the
  engine cannot import synth3).
- The prompt `written-answer-v1.md` (task first): "Write a short answer to the question, using only the numbered
  facts." Inputs (question; facts `[n] <paper> <text>`), output fields (`sentences`: `text`, `says`, `facts`), rules:
  1 to 8 sentences; each finding names treatments, measures and groups as the facts name them and lists the numbers of
  the facts it rests on; copy numbers from the cited facts only, never compute a sum, mean, difference or percentage;
  a fraction and its percentage are the same number (0.45 may be written 45%); write a count of studies as a number
  no larger than the facts you cite, or in words; when facts disagree, say so and cite both sides; a part of the
  question no fact speaks to gets one `cannot_tell` sentence with no facts; leave paper ids out. Examples:
  - normal: question about Method K and Yield; facts `[1] S901 Method K on Yield (higher is better): 0.45`, `[2] S901
    Usual method on Yield (higher is better): 0.38`, `[3] S902 The authors say: improves` → "Method K gave a higher
    Yield than the Usual method, 45% against 38%." facts [1, 2]; "The authors of one study say Method K improves
    Yield." facts [3];
  - confusing: question about Method P and Error count; facts on Error count (lower is better) 12 and 15 and one on
    Yield → "Method P gave fewer errors than the Usual method, 12 against 15." facts [1, 2]; the Yield fact is not used
    (another measure);
  - missing: question about Yield and Error count of Method K; facts only on Yield, equal values → "Method K and the
    Usual method show no real difference in Yield, 0.50 against 0.50." facts [1, 2]; "No fact here reports the Error
    count of Method K, so that part cannot be answered." `cannot_tell`, facts [].

- [ ] **Step 1: Write the failing tests.** `item(type, fields, links=None, paper="S001", exact="...", start=0)`
  builds an `Item` with one span (selector `file papers/<paper>.md`, `start`, `end`, `exact`); `plan()` is
  `make_plan()` of `test_plan_run.py` (things `rag`, `closed_book`, measure `accuracy`); `paper_facts(p, k)` builds
  one condition (`role "rag"`), one metric (`canonical "accuracy"`, `higher_is_better True`) and `k` measurements
  linked to them in paper `p`.

```python
def test_a_measurement_reads_its_condition_metric_and_direction():
    c = item("condition", {"label": "Method K", "role": "rag"})
    k = item("metric", {"name": "Yield", "canonical": "accuracy", "higher_is_better": True})
    m = item("measurement", {"value": 0.62, "dataset": None}, {"condition": c.item_id, "metric": k.item_id},
             exact="0.62")
    facts, cut = fact_lines({"S001": [c, k, m]}, plan(), 10_000)
    assert [f.n for f in facts] == [1] and cut == {"pulled": 1, "kept": 1, "left_out": {}, "off_plan": 0}
    assert facts[0].text == 'Method K on Yield (higher is better): 0.62, no dataset named. Quote: "0.62"'

def test_a_fact_off_the_plan_is_left_out_and_counted():
    c = item("condition", {"label": "Other model", "role": "other"})
    k = item("metric", {"name": "Yield", "canonical": "accuracy", "higher_is_better": True})
    m = item("measurement", {"value": 0.5, "dataset": None}, {"condition": c.item_id, "metric": k.item_id})
    facts, cut = fact_lines({"S001": [c, k, m]}, plan(), 10_000)
    assert facts == [] and cut["off_plan"] == 1

def test_every_paper_is_represented_when_the_budget_is_small():
    by_paper = {f"S{i:03d}": paper_facts(f"S{i:03d}", 10) for i in range(1, 41)}
    one = len(fact_lines({"S001": by_paper["S001"]}, plan(), 10_000)[0][0].text) + 16
    facts, cut = fact_lines(by_paper, plan(), budget=60 * one)
    assert {f.paper for f in facts} == set(by_paper) and len(facts) < 400
    assert cut["pulled"] == 400 and cut["kept"] == len(facts) and sum(cut["left_out"].values()) == 400 - len(facts)
    assert [f.n for f in facts] == list(range(1, len(facts) + 1))
    assert [f.paper for f in facts] == sorted(f.paper for f in facts)

def test_the_budget_follows_the_model_limit():
    assert fact_budget(65_536) == 131_072

def test_checks_name_each_problem():
    facts = [Fact(n=1, item="m-1", paper="S001", type="measurement", text="Method K on Yield: 0.45")]
    s = lambda text, says="finding", f=(1,): WrittenReply(sentences=[Sentence(text=text, says=says, facts=list(f))])
    assert check_written(s("Up to 45% with Method K, in 1 study."), facts) == []
    assert check_written(s("Up by 12%."), facts) == ["sentence 1: the number 12 is in none of its facts"]
    assert check_written(s("Better.", f=(9,)), facts) == ["sentence 1: fact 9 is not listed"]
    assert check_written(s("Better in S001."), facts) == ["sentence 1: leave paper ids out; the code adds them"]
    assert check_written(s("No study.", "cannot_tell", ()), facts) == []
    assert check_written(s("Unknown.", "cannot_tell", (1,)), facts) == ["sentence 1: a cannot_tell sentence cites no fact"]
    assert check_written(WrittenReply(sentences=[]), facts) == ["give 1 to 8 sentences"]
    assert numbers("In S001 and S010, 1,250 cases and 0.45.") == [1250.0, 0.45]

def test_the_code_adds_the_papers():
    facts = [Fact(n=1, item="a", paper="S003", type="measurement", text="x 1"),
             Fact(n=2, item="b", paper="S010", type="measurement", text="x 2")]
    reply = WrittenReply(sentences=[Sentence(text="Method K did better.", says="finding", facts=[2, 1]),
                                    Sentence(text="No study measured cost.", says="cannot_tell", facts=[])])
    text, rows = answer_text_of(reply, facts)
    assert text == "Method K did better (S010, S003). No study measured cost."
    assert rows[0]["papers"] == ["S010", "S003"]

def test_the_prompt_uses_no_domain_name_and_holds_its_three_examples():
    text = PROMPT.read_text(encoding="utf-8")
    assert spec_name_hits(text) == []   # from test_planner_subq.py
    assert text.splitlines()[0].startswith("Write a short answer to the question")
    assert all(w in text for w in ("Method K", "Method P", "Usual method", "Error count", "45%", "cannot_tell"))
```

- [ ] **Step 2: Run** `uv run pytest -q backend/evidence/tests/test_written.py`. Expected: FAIL (`ImportError`).
- [ ] **Step 3: Implement** the functions and write the prompt.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** the three files: `evidence: the written answer's facts, checks and prompt`.

### Task 6: The written answer runs as a stage of the plan run

**Files:**
- Modify: `backend/evidence/written.py` (the stage), `backend/evidence/planrun.py` (`stage_entries` adds the stage
  when `plan.answer_by == "written"`, importing `written` inside the function), `backend/evidence/stages.py`
  (`StageContext.corpus: Path | None = None`, a defaulted last field), `backend/evidence/engine.py` (pass
  `corpus=Path(setup.settings.corpus)` where the context is made)
- Create: `backend/evidence/tests/test_written_stage.py`

**Interfaces:**
- Consumes: Task 5; `StageContext.ask` (raises `StageCallError` on a failed call); `RunDir.items`;
  `PaperIndex.of_corpus`; `load_prompt`; `ORCHESTRATOR["context_tokens"]`.
- Produces: `written_stage(run: RunDir, ctx: StageContext) -> dict` (after_run, written by the engine as
  `written-answer.json` and hashed into run.json):
  - facts: `fact_lines(PaperIndex.of_corpus(ctx.corpus).group(run.items()), ctx.plan,
    fact_budget(ORCHESTRATOR["context_tokens"]))`;
  - no fact: no call; `status "no_facts"`, `answer_text NO_FACTS_TEXT`, one `cannot_tell` row;
  - else `ctx.ask(prompt.text, writer_input(plan.question, facts), output_type=WrittenReply, purpose=STAGE,
    model=WRITER_ALIAS, max_tokens=2048, request_extra={"try": plan.writer_try} if plan.writer_try else None)`,
    `check_written`, at most one repair call with `repair_input(...)` (same `request_extra`);
  - returns `{"status": "ok" | "failed" | "no_facts", "question", "answer_text", "sentences", "facts" (the Fact
    dumps), "cut" (Task 5's cut record), "tries": [{"reply": <reply dump>, "problems": [...]}] (every attempt, in
    order), "problems" (the last try's), "model": WRITER_ALIAS, "prompt_sha256", "writer_try"}`; `failed` keeps
    `answer_text ""`;
  - a `StageCallError` is not caught: the engine writes `{"failed": "<reason>"}` (stages.py rule) and the run goes
    on, so `--retry-errors` asks the call again.
- Produces in `planrun.stage_entries`: `(written.STAGE, "after_run", written.written_stage)` appended last when
  `plan.answer_by == "written"`; any other plan gets today's list.
- Test fake (the call is told apart by what is really sent): `ctx.ask` sends the prompt file as the agent's
  `instructions` and the writer input as the user message. `writer_model(calls, reply)` is a `FunctionModel` whose
  function, when `"Write a short answer to the question" in (info.instructions or "")`, appends `prompt_of(messages)`
  (the user part: the input, or the repair input with its problems) to `calls` and returns `respond(info,
  reply(prompt_of(messages)))`; a reply that is an `Exception` is raised; every other call goes to `fake_model`'s
  function of `test_plan_run.py`.

- [ ] **Step 1: Write the failing tests.** `written_run(tmp_path, reply, plan=None, calls=None)` runs
  `with_answer(make_plan(), "written", None)` (or `plan`) as `plan_run` does, with `provider_of(writer_model(calls,
  reply))`, and returns the run folder.

```python
def read(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))

def test_a_written_plan_run_writes_the_answer_and_replays(tmp_path):
    good = lambda p: {"sentences": [{"text": "Retrieval helped.", "says": "finding", "facts": [1]}]}
    root = written_run(tmp_path, good)
    out, run = read(root, "written-answer.json"), read(root, "run.json")
    assert out["status"] == "ok" and out["answer_text"].startswith("Retrieval helped (")
    assert out["cut"]["kept"] == len(out["facts"]) >= 1 and len(out["tries"]) == 1
    assert run["stages"]["after_run"][-1] == "written-answer" and "written-answer.json" in run["outputs"]
    (tmp_path / "plan.json").unlink()
    _, report = replay(root)
    assert report["ok"] and report["mismatched"] == []

def test_a_bad_reply_gets_one_repair_with_its_problem(tmp_path):
    calls = []
    replies = iter([{"sentences": [{"text": "Up 987654%.", "says": "finding", "facts": [1]}]},
                    {"sentences": [{"text": "Retrieval helped.", "says": "finding", "facts": [1]}]}])
    out = read(written_run(tmp_path, lambda p: next(replies), calls=calls), "written-answer.json")
    assert out["status"] == "ok" and len(out["tries"]) == 2 and len(calls) == 2
    assert out["tries"][0]["problems"] == ["sentence 1: the number 987654 is in none of its facts"]
    assert "the number 987654" in calls[1] and calls[1].startswith("Question: ")

def test_two_bad_replies_leave_an_empty_failed_answer(tmp_path):
    out = read(written_run(tmp_path, lambda p: {"sentences": []}), "written-answer.json")
    assert out["status"] == "failed" and out["answer_text"] == "" and out["problems"] == ["give 1 to 8 sentences"]
    assert [t["problems"] for t in out["tries"]] == [["give 1 to 8 sentences"]] * 2

def test_a_failed_call_is_recorded_and_the_run_completes(tmp_path):
    root = written_run(tmp_path, lambda p: RuntimeError("gateway down"))
    assert set(read(root, "written-answer.json")) == {"failed"} and RunDir(root).complete

def test_a_later_try_is_a_new_call(tmp_path):
    calls = []
    good = lambda p: {"sentences": [{"text": "Retrieval helped.", "says": "finding", "facts": [1]}]}
    written_run(tmp_path / "a", good, calls=calls)
    tried = with_answer(make_plan(), "written", None).model_copy(update={"writer_try": 1})
    written_run(tmp_path / "a", good, plan=tried, calls=calls)   # same record cache folder
    assert len(calls) == 2

def test_no_fact_means_no_call(tmp_path):
    calls = []
    nothing = with_answer(make_plan(things={"zz": ["no such words anywhere"], "yy": ["nor these"]}, measures=()),
                          "written", None)
    out = read(written_run(tmp_path, lambda p: {"sentences": []}, plan=nothing, calls=calls), "written-answer.json")
    assert out["status"] == "no_facts" and out["answer_text"] == NO_FACTS_TEXT and calls == []

def test_a_lines_plan_has_todays_stages(tmp_path):
    root = plan_run(tmp_path)   # the old helper, answer_by lines
    assert "written-answer" not in read(root, "run.json")["stages"]["after_run"]
```

  `written_run` runs into `tmp_path / "runs"` with a distinct `run_id` per call so `test_a_later_try_is_a_new_call`
  can run twice over one cache.
- [ ] **Step 2: Run** `uv run pytest -q backend/evidence/tests/test_written_stage.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the stage, the `StageContext.corpus` field, the engine line and the `stage_entries`
  line.
- [ ] **Step 4: Run** the new tests, then the whole suite. Expected: PASS (the `test_plan_run*.py` files, the lock
  fixture and every replay test unchanged).
- [ ] **Step 5: Commit** the five files: `evidence: a model writes the answer from the pulled facts, as a recorded stage`.

### Task 7: Fixed-kind answers as short lines in plain words

**Files:**
- Create: `backend/evidence/kindtext.py`, `backend/evidence/tests/test_kindtext.py`

**Interfaces:**
- Consumes: `Protocol`; `Plan`; the kinds' answers (`effect` = synthesis.answer, `consistency`, `inventory`, `best`;
  their docstrings give the shapes). A plan run keeps the kind's answer under answer.json `synthesis`.
- Produces: `MAX_KIND_LINES = 120`; `CANT_TELL_LINE = "The papers in this folder cannot answer this question."`
  (exact copy); `KindLine(BaseModel)`: `text: str`, `items: list[str]` (every string in the line's entry that is an
  item id: code walks the entry, `^[a-z]+-[0-9a-f]{16}$`), `study: bool`.
- Produces: `plan_names(plan: Plan) -> dict[str, str]`: each thing id → its first word-list name
  (`plan.words.things[t][0]`, the id when the list is empty).
- Produces: `RULE_TEXT: dict[str, str]` (exact copy, also the UI's Combine row):
  - `effect`: "Each paper's treatment and control values give a direction; the label table turns the counts into the answer."
  - `consistency`: "Each paper's measured direction is compared with what its authors claim."
  - `inventory`: "Every distinct name of the chosen kind is listed with the papers that name it."
  - `best`: "Inside each paper the kind with the best value wins; the kind with the most wins is the answer."
  - `written`: "A model (orch-model) wrote the answer from the pulled facts; code checked that every sentence cites listed facts and copies its numbers from them."
  - `lines`: "The plan's main rule: {rule}." (formatted with `evidence.planner.RULES[main_rule]`).
- Produces: `kind_lines(protocol: Protocol, answer: dict, names: Mapping[str, str]) -> list[KindLine]` where
  `answer` is the kind's answer (answer.json `synthesis`) and `names` is `plan_names(plan)`. Every thing and measure
  is written by its name (an id missing from `names` is written as it is). Summary lines first (`study=False`), no
  rule name in them, then one per study or entry (`study=True`), at most `MAX_KIND_LINES` lines in all, then
  `... and <n> more.` Text (exact copy):
  - effect: `<Treatment> against <Control> on <measures>: ` + by label: supported `<Treatment> does better.`;
    refuted `<Treatment> does worse.`; no_effect `no real difference.`; mixed `the papers disagree.`; insufficient
    `CANT_TELL_LINE`; then one line per non-empty group `Papers that show it better: S001, S004.` / `show it worse` /
    `show no real difference` / `could not be read` / `repeat an earlier paper`; study: `S001: better|worse|no real
    difference on <measure> (<value> against <value>).` or `S001: could not be read (<reason text>).`;
  - consistency: `On <measure>, the authors' claims agree with their numbers in S001, S003; disagree in S004; cannot
    be checked in S002.`; no checkable study: `CANT_TELL_LINE`; study `S001: the authors say <claim>, the numbers say
    <direction>.`;
  - best: `On <measure>, <Winner> is best in the most papers (<Name> <n>, ...).` or `On <measure>, no single kind is
    best: <Names> tie.`; no study with a comparison: `CANT_TELL_LINE`; study `S001: <Winner> is best.` / `S001: <Names>
    tie.` / `S001: no comparison (<reason>).`;
  - inventory: `<n> distinct names of <compared things|measures>.`; no entry: `CANT_TELL_LINE`; entry `<name> (also
    <aliases>): S001, S003.`
- The judge's text of a fixed-kind answer is `"\n".join(line.text ...)` (Task 8); it holds paper ids, names and
  numbers, never `system`, the protocol id or the question.

- [ ] **Step 1: Write the failing tests.** Helpers in the test file: `effect_protocol()` =
  `parse(protocol_for(make_plan()).decode("utf-8"))` (treatment `rag`, control `closed_book`, metric `accuracy`);
  `inventory_protocol()`, `best_protocol()`, `consistency_protocol()` through `kind_protocol(with_answer(make_plan(),
  ...))`; `NAMES = plan_names(make_plan())` (`rag` → "retrieval-augmented model", `closed_book` → "closed-book model",
  `accuracy` → "answer accuracy"); `effect_answer(studies=n, label="supported")`, `inventory_answer(entries=n)`,
  `best_answer(winner="rag")`, `consistency_answer(checkable=True)` build answers in the shapes the kinds' docstrings
  give (studies `S001`..., item ids like `m-0123456789abcdef`).

```python
def test_effect_lines_use_names_and_each_study():
    lines = kind_lines(effect_protocol(), effect_answer(studies=3), NAMES)
    assert lines[0].text == ("retrieval-augmented model against closed-book model on answer accuracy: "
                             "retrieval-augmented model does better.")
    studies = [l for l in lines if l.study]
    assert len(studies) == 3 and all(l.items for l in studies)
    assert not any(w in l.text for l in lines for w in ("rag ", "closed_book", "Answer by"))

def test_forty_studies_stay_under_the_judge_cut():
    text = "\n".join(l.text for l in kind_lines(effect_protocol(), effect_answer(studies=40), NAMES))
    assert len(text) < 12_000 and "evidence-engine" not in text and "plan-" not in text

def test_long_inventories_are_cut_with_a_count():
    lines = kind_lines(inventory_protocol(), inventory_answer(entries=200), NAMES)
    assert len(lines) == MAX_KIND_LINES + 1 and lines[-1].text == f"... and {200 - (MAX_KIND_LINES - 1)} more."

@pytest.mark.parametrize("protocol, answer", [
    (effect_protocol, lambda: effect_answer(studies=2, label="insufficient")),
    (inventory_protocol, lambda: inventory_answer(entries=0)),
    (best_protocol, lambda: best_answer(winner=None, comparisons=0)),
    (consistency_protocol, lambda: consistency_answer(checkable=False)),
])
def test_every_kind_says_cant_tell_in_plain_words(protocol, answer):
    assert CANT_TELL_LINE in [l.text for l in kind_lines(protocol(), answer(), NAMES)]

def test_best_and_consistency_summaries():
    assert kind_lines(best_protocol(), best_answer(winner="rag"), NAMES)[0].text.startswith(
        "On answer accuracy, retrieval-augmented model is best in the most papers (")
    assert kind_lines(consistency_protocol(), consistency_answer(checkable=True), NAMES)[0].text.startswith(
        "On answer accuracy, the authors' claims agree with their numbers in ")
```

- [ ] **Step 2: Run** `uv run pytest -q backend/evidence/tests/test_kindtext.py`. Expected: FAIL.
- [ ] **Step 3: Implement** `kindtext.py`.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** both files: `evidence: fixed-kind answers as short lines in plain words`.

### Task 8: synth3 collects a system run

**Files:**
- Create: `backend/synth3/system.py` (this task: collecting), `backend/synth3/tests/systemrun.py` (test helper),
  `backend/synth3/tests/test_system_collect.py`
- Modify: `backend/synth3/answers.py` (move the item loop of `from_engine_run` into `pulled_facts`, unchanged
  behaviour; two optional record fields), `backend/synth3/qcli.py` (`collect` reads plan runs; `--system` default by
  run kind)

**Interfaces:**
- Consumes: Tasks 1, 2, 4, 6, 7; `AnswerRecord`, `cited_papers`, `save_answer`, `MAX_TEXT` (answers.py); `RunDir`,
  `load_plan`, `PLAN_FILE`, `PROTOCOL_FILE`, `ANSWER_FILE`; `evidence.protocol.parse`; `kind_lines`, `plan_names`.
- Produces in `answers.py`: `pulled_facts(run: Path, folder: Folder) -> list[PulledFact]` (the loop
  `from_engine_run` has today); `AnswerRecord.plan_confirmed_by: str | None = None` (`"person"` or `"system"`, the
  system's records only) and `AnswerRecord.facts_left_out: int | None = None` (facts that bear on the plan but were
  not given to the writer; written answers only).
- Produces in `system.py`: `SYSTEM = "system"`; `is_plan_run(run: Path) -> bool` (run.json `settings.stage_set ==
  "plan"`); `confirmed_by(plan: Plan) -> str`: `"system"` when any decision's `confirmed_by == "system"`, else
  `"person"`.
- Produces: `from_system_run(run: Path, folder: Folder, q: Question, system: str = SYSTEM) -> AnswerRecord`. Refused
  with `ValueError` naming the run and the reason, in this order:
  - not sealed complete: `"the run is not complete (state <state>)"`;
  - run.json corpus id is not the folder's: `"the run is of corpus ..."` (as `from_engine_run`);
  - the run's plan.json `question` or `sub_questions` differ from `q`: `"the run was planned for another version of
    the question"`;
  - `plan.answer_by != answer_by_of(q)` or `plan.target != target_of(q)`: `"the run answers by <a>, the question
    asks for <b>"`;
  - written: no `written-answer.json`: `"the run has no written answer"`; `{"failed": r}`: `"the written answer's
    model call failed: <r>; run it again with retry"`.
  The record is built directly (not through `_record`/`answer_text`, which would turn an empty text into a JSON dump):
  text written `ok` or `no_facts` → its `answer_text`; written `failed` → `""` (C scores it 0 without a call, plan
  3); a fixed kind → `"\n".join` of `kind_lines(parse(protocol.yaml), answer["synthesis"], plan_names(plan))`, cut
  at `MAX_TEXT` with `text_cut` as plan 3 cuts. `cited` from the text (`cited_papers`), `facts = pulled_facts(run,
  folder)`, `passages = []`, `source = str(run)`, `question_sha256(q)`, `asked_sha256(q)`,
  `plan_confirmed_by = confirmed_by(plan)`, `facts_left_out = sum(cut["left_out"].values())` for written answers.
- Produces in `qcli.collect`: a plan run → `from_system_run` with `--system` default `system`; any other run →
  `from_engine_run` with default `engine` (as today).
- Produces in `tests/systemrun.py` (Tasks 10, 13 use it):
  - `demo_plan(SPEC, q: Question, answer_by: str = "written", target: str | None = None, confirmed: str | None =
    "aditya") -> Plan`: `q`'s question and sub-questions, things `targeted` → ["Targeted therapy"], `standard` →
    ["Standard care"], `response_rate` → ["Response rate"], the measure `response_rate`, a threshold, direction and
    main-rule decision, every decision confirmed by `confirmed` (none confirmed when `None`), `words.written_by
    "orch-model"`, the lines of `test_plan_run.make_plan` (effect template, oversell);
  - `write_demo_plans(root: Path, qs: QuestionSet, SPEC, confirmed: str | None = "aditya") -> None`: `demo_plan` of
    each question with `answer_by_of(q)` / `target_of(q)`, at `root / "demo" / f"{q.id}.json"`;
  - `OK_REPLY`: a reply function giving one `cannot_tell` sentence ("The papers cannot tell.", no facts), valid
    whatever the facts are; `FACT_REPLY`: one finding citing fact 1 when the input lists `[1]`, else `OK_REPLY`'s
    reply; `system_model(writer_reply=OK_REPLY)`: Task 6's `writer_model` with no call log;
  - `make_system_run(out: Path, folder: Folder, q: Question, plan: Plan, *, writer_reply=OK_REPLY, run_id=None) ->
    Path`: writes the plan beside `out`, then `planrun.run(plan file, folder.path, out, cache=out.parent / "cache",
    run_id=run_id or q.id, selection="regex-only", reason="off", links="off", workers=1,
    provider=provider_of(system_model(writer_reply)))`.

- [ ] **Step 1: Write the failing tests** (the `folder` fixture and `q()` of plan 3's conftest):

```python
QQ = dict(text="Does Targeted therapy raise the Response rate?", sub_questions=["Which papers say Secret-sub?"])

@pytest.fixture
def written(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"], sub_questions=QQ["sub_questions"])
    plan = demo_plan(SPEC, qq)
    return f, qq, plan, make_system_run(tmp_path / "runs", f, qq, plan)

def test_a_written_run_becomes_a_record(written):
    f, qq, plan, run = written
    rec = from_system_run(run, f, qq)
    out = json.loads((run / "written-answer.json").read_text(encoding="utf-8"))
    assert rec.system == "system" and rec.question_sha256 == question_sha256(qq)
    assert rec.asked_sha256 == asked_sha256(qq) and rec.plan_confirmed_by == "person"
    assert rec.text == out["answer_text"] and rec.facts == pulled_facts(run, f)
    assert rec.facts_left_out == sum(out["cut"]["left_out"].values())

def test_the_record_holds_no_sub_question_and_no_system_name(written):
    f, qq, plan, run = written
    text = from_system_run(run, f, qq).text
    banned = ["Secret-sub", "evidence-engine", "plan-", "orch-model", "system", *(l.question for l in plan.lines)]
    assert [b for b in banned if b in text] == []

@pytest.mark.parametrize("change, words", [
    (lambda qq: qq.model_copy(update={"question": "Other?"}), "planned for another version of the question"),
    (lambda qq: qq.model_copy(update={"sub_questions": []}), "planned for another version of the question"),
    (lambda qq: qq.model_copy(update={"kind": "effect"}), "answers by written, the question asks for effect"),
])
def test_a_run_for_another_question_is_refused(written, change, words):
    f, qq, plan, run = written
    with pytest.raises(ValueError, match=words):
        from_system_run(run, f, change(qq))

def test_a_failed_writer_call_asks_for_a_rerun(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"])
    run = make_system_run(tmp_path / "runs", f, qq, demo_plan(SPEC, qq), writer_reply=lambda p: RuntimeError("down"))
    with pytest.raises(ValueError, match="model call failed.*run it again with retry"):
        from_system_run(run, f, qq)

def test_a_failed_written_answer_is_an_empty_answer(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"])
    run = make_system_run(tmp_path / "runs", f, qq, demo_plan(SPEC, qq), writer_reply=lambda p: {"sentences": []})
    rec = from_system_run(run, f, qq)
    assert rec.text == "" and rec.cited == [] and not rec.text_cut

def test_an_effect_run_is_judged_as_kind_lines(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"], kind="effect")
    run = make_system_run(tmp_path / "runs", f, qq, demo_plan(SPEC, qq, answer_by="effect"))
    rec = from_system_run(run, f, qq)
    assert rec.text.startswith("Targeted therapy against Standard care on Response rate: ")
    assert not rec.text.lstrip().startswith("{") and "targeted" not in rec.text.replace("Targeted", "")

def test_a_system_confirmed_plan_is_recorded_as_such(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"])
    run = make_system_run(tmp_path / "runs", f, qq, demo_plan(SPEC, qq, confirmed="system"))
    assert from_system_run(run, f, qq).plan_confirmed_by == "system"

def test_collect_reads_a_plan_run(written, tmp_path, spec_dir):
    f, qq, plan, run = written
    (tmp_path / "qs").mkdir()
    (tmp_path / "qs" / "demo.yaml").write_text(yaml.safe_dump({"domain": "demo", "questions": [
        {"id": qq.id, "question": qq.question, "sub_questions": qq.sub_questions}]}), encoding="utf-8")
    assert main(["collect", "--domain", "demo", "--seed", "1", "--question", qq.id, "--run", str(run),
                 "--folders", str(f.path.parent), "--questions-root", str(tmp_path / "qs"),
                 "--spec-root", str(spec_dir), "--results", str(tmp_path / "res")]) == 0
    assert answer_path(tmp_path / "res", "demo", 1, "system", qq.id).is_file()
```

  (`q()` of plan 3's conftest gives the id `x`, a valid question id.) Plan 3's `test_answers.py` keeps passing
  unchanged (the move is behaviour-free).
- [ ] **Step 2: Run** `uv run pytest -q backend/synth3/tests/test_system_collect.py`. Expected: FAIL.
- [ ] **Step 3: Implement** `pulled_facts`, the record fields, `system.py` (collecting part), the helper and the
  `collect` change.
- [ ] **Step 4: Run** `uv run pytest -q backend/synth3 backend/evidence/tests/test_plan_run.py`. Expected: PASS.
- [ ] **Step 5: Commit** the five files: `synth3: system runs collected into the judge's shape`.

### Task 9: synth3 plans every question

**Files:**
- Modify: `backend/synth3/system.py` (planning part)
- Create: `backend/synth3/scli.py` (`add_system_commands(sub)`, command `system-plan`),
  `backend/synth3/tests/test_system_plan.py`
- Modify: `backend/synth3/cli.py` (one call to `add_system_commands(sub)`), `backend/README.md` (one Run line)

**Interfaces:**
- Consumes: `propose`, `critic`, `using`, `check_plan` (evidence.planner); `write_words` (evidence.words.write,
  imported into `system.py` so tests can replace it); `with_answer`, `load_plan`, `write_plan`; `answer_problems`;
  `orch_lm`, `saved_templates`, `PLANNER_CACHE` (evaluation.planbatch); `answer_by_of`, `target_of`.
- Produces: `PLANS = SPECS / "plans"`; `plan_path(root: Path, domain: str, qid: str) -> Path` =
  `root / domain / f"{qid}.json"`; `auto_path(root, domain, qid) -> Path` = `root / domain / "auto" / f"{qid}.json"`.
- Produces: `draft_plan(q: Question, lm, templates: Mapping[str, str]) -> Plan`: under `using(lm)`, `propose(q.question,
  [], sub_questions=q.sub_questions, write_words=lambda t, th: write_words(t, th, lm=lm), templates=templates)`, then
  `critic`, then `with_answer(plan, answer_by_of(q), target_of(q))`. No clarifying questions (a batch has no one to
  answer them; the page asks them). Nothing is confirmed.
- Produces: `plan_stale(plan: Plan, q: Question) -> str | None`: `"the question changed after planning"` (question or
  sub-questions differ); else `None`.
- Produces: `plan_domain(domain: str, qs: QuestionSet, root: Path, lm, templates, *, redo: set[str] = frozenset(),
  redo_lm=None) -> dict`: per question: no file → drafted with `lm`; stale → the old file moved to
  `<qid>.stale-<n>.json` (never deleted) and drafted with `lm`; in `redo` → moved the same way and drafted with
  `redo_lm` (a model whose record cache is a new file, so no cached reply is read); kind or target changed → set in
  place with `with_answer` (listed under `rekinded`; the planner's work does not depend on it, and confirmations
  stay); else kept. A drafting failure (`ModelCallError`, `ValueError`, `RuntimeError` from a step) is listed with
  its redacted reason; the rest go on. Returns `{"drafted", "kept", "rekinded", "failed": {qid: reason}, "problems":
  {qid: [...]}}` where `problems` are `check_plan(plan, templates) + answer_problems(plan)` of every plan now on disk.
- Produces: `synth3 system-plan --domain D [--redo QID[,QID]] [--plans P] [--questions-root Q] [--spec-root S]
  [--results R]`: `lm = orch_lm(R/D/planner.jsonl)`; with `--redo`, `redo_lm = orch_lm(R/D/planner-redo-<UTC time,
  %Y%m%dT%H%M%S>.jsonl)`; an unknown `--redo` id is exit 2 naming it; prints `drafted <a>, kept <b>, rekinded <c>,
  failed <d>`, each failure, each plan's problems, and the line `Plans are drafts: open each on /plan (or edit the
  file) and confirm it, or run system-run with --confirm-as-system.`; exit 1 when anything failed or has problems.

- [ ] **Step 1: Write the failing tests.** `use_fake_draft(monkeypatch, SPEC, fail=())` replaces
  `synth3.system.draft_plan` with `fake_draft(q, lm, templates)` = `with_answer(demo_plan(SPEC, q, confirmed=None),
  answer_by_of(q), target_of(q))` (raising `ModelCallError("down")` for ids in `fail`) and returns a list that
  records `(q.id, lm)` per call. The first test runs the real `propose` with the `lm` fixture and `script` helper of
  Task 3's tests and `synth3.system.write_words` replaced by Task 3's `words` fake.

```python
def test_draft_plan_passes_the_sub_questions_and_the_kind(lm, monkeypatch):
    replies, seen = lm
    monkeypatch.setattr(system, "write_words", lambda text, things, lm=None: words(text, things))
    script(replies, [line()]); replies.append(flags("d1"))
    qq = Question(id="d01", question="Does Targeted therapy raise the Response rate?", kind="inventory",
                  sub_questions=["Which papers measured it?"])
    plan = draft_plan(qq, steps.current(), {})
    assert plan.sub_questions == ["Which papers measured it?"] and plan.answer_by == "inventory"
    assert plan.target == "condition" and any("Which papers measured it?" in p for p in seen)
    assert not plan.ready()

def test_a_second_run_keeps_plans_and_a_changed_question_is_replanned(tmp_path, SPEC, monkeypatch):
    qs = load_questions("demo", SPEC, FIX); calls = use_fake_draft(monkeypatch, SPEC)
    assert sorted(plan_domain("demo", qs, tmp_path, "lm", {})["drafted"]) == ["d01", "d02", "d03"]
    assert len(plan_domain("demo", qs, tmp_path, "lm", {})["kept"]) == 3 and len(calls) == 3
    edited = qs.model_copy(update={"questions": [qs.get("d01").model_copy(update={"question": "Changed?"}),
                                                 *qs.questions[1:]]})
    out = plan_domain("demo", edited, tmp_path, "lm", {})
    assert out["drafted"] == ["d01"] and (tmp_path / "demo" / "d01.stale-1.json").is_file()

def test_redo_drafts_with_a_fresh_model(tmp_path, SPEC, monkeypatch):
    qs = load_questions("demo", SPEC, FIX); calls = use_fake_draft(monkeypatch, SPEC)
    plan_domain("demo", qs, tmp_path, "lm", {})
    out = plan_domain("demo", qs, tmp_path, "lm", {}, redo={"d02"}, redo_lm="fresh-lm")
    assert out["drafted"] == ["d02"] and calls[-1] == ("d02", "fresh-lm")
    assert (tmp_path / "demo" / "d02.stale-1.json").is_file()

def test_a_changed_kind_is_set_in_place(tmp_path, SPEC, monkeypatch):
    qs = load_questions("demo", SPEC, FIX); calls = use_fake_draft(monkeypatch, SPEC)
    plan_domain("demo", qs, tmp_path, "lm", {})
    edited = qs.model_copy(update={"questions": [qs.get("d01").model_copy(update={"kind": "effect"}),
                                                 *qs.questions[1:]]})
    out = plan_domain("demo", edited, tmp_path, "lm", {})
    assert out["rekinded"] == ["d01"] and len(calls) == 3
    assert load_plan(plan_path(tmp_path, "demo", "d01")).answer_by == "effect"

def test_a_failing_draft_is_listed_and_the_rest_go_on(tmp_path, SPEC, monkeypatch):
    use_fake_draft(monkeypatch, SPEC, fail={"d02"})
    out = plan_domain("demo", load_questions("demo", SPEC, FIX), tmp_path, "lm", {})
    assert list(out["failed"]) == ["d02"] and "down" in out["failed"]["d02"]
    assert sorted(out["drafted"]) == ["d01", "d03"]

def test_system_plan_by_command(tmp_path, spec_dir, monkeypatch, capsys):
    use_fake_draft(monkeypatch, SPEC := load_spec("demo", spec_dir))
    monkeypatch.setattr(system, "orch_lm", lambda path: f"lm:{path.name}")
    args = ["system-plan", "--domain", "demo", "--plans", str(tmp_path / "p"), "--questions-root", str(FIX),
            "--spec-root", str(spec_dir), "--results", str(tmp_path / "r")]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "drafted 3, kept 0, rekinded 0, failed 0" in out and "--confirm-as-system" in out
    assert main([*args, "--redo", "zz"]) == 2
```

  (`check_plan` problems are empty for `demo_plan`: its lines are `make_plan`'s, which `check_plan` accepts.)
- [ ] **Step 2: Run** `uv run pytest -q backend/synth3/tests/test_system_plan.py`. Expected: FAIL.
- [ ] **Step 3: Implement**; Run line: `uv run synth3 system-plan --domain D [--redo QID]   # orch-model drafts one
  plan per question from the question and its sub-questions (cluster); data/synth3/plans/D/<qid>.json, to be
  confirmed on /plan`.
- [ ] **Step 4: Run** `uv run pytest -q backend/synth3`. Expected: PASS.
- [ ] **Step 5: Commit** `system.py`, `scli.py`, `cli.py`, the test file, `backend/README.md`:
  `synth3: one plan per question, drafted with its sub-questions`.

### Task 10: synth3 runs every confirmed plan on every folder

**Files:**
- Modify: `backend/synth3/system.py` (running part), `backend/synth3/scli.py` (command `system-run`),
  `backend/README.md` (one Run line)
- Create: `backend/synth3/tests/test_system_run.py`

**Interfaces:**
- Consumes: Tasks 8 and 9; `planrun.run`; `confirm_all`; `check_plan`; `answer_problems`; `sealed_complete`,
  `set_aside`, `has_unchecked` (evaluation.planbatch); `each_folder` (cliargs).
- Produces: `MAX_WRITER_TRIES = 3`; `run_path(results: Path, domain: str, seed: int, qid: str) -> Path` =
  `results / domain / "runs" / f"s{seed}" / qid`.
- Produces: `plan_to_run(draft: Plan, root: Path, domain: str, qid: str, *, as_system: bool) -> tuple[Plan | None,
  str | None]` (the plan, or the reason to skip):
  - a draft every decision of which is confirmed → the draft;
  - else without `as_system` → `None, "decisions not confirmed by a person: d1, main_rule; confirm the plan on /plan
    or pass --confirm-as-system"` (the ids listed);
  - else the system copy at `auto_path`: kept when it equals `confirm_all(draft, "system")` once its system stamps
    are cleared (so the draft did not change since); otherwise `confirm_all(draft, "system")` written there. The draft
    file is never written.
- Produces: `run_folder(folder: Folder, qs: QuestionSet, plans: Path, results: Path, *, as_system: bool = False,
  provider=None, workers: int = 3, runner=None) -> dict` (`runner` None: `system.planrun_run`, looked up at call
  time), per question, in this order:
  - no plan file: skipped `"no plan; run synth3 system-plan first"`; a stale plan: skipped with its reason; the plan
    answers by another kind or target than the question asks: skipped `"the plan answers by <a>, the question asks for
    <b>; run synth3 system-plan"`; problems (`check_plan` + `answer_problems`): skipped with them; `plan_to_run`
    gives a reason: skipped with it;
  - the run folder (`run_path`), compared through its `plan.json` with `writer_try` set to 0:
    - complete, same plan, a good written answer (or a fixed kind) and no unchecked item (`has_unchecked`) → kept;
    - complete, same plan, but `written-answer.json` holds `{"failed": ...}` or `has_unchecked` → set aside as
      `.redo-<n>`, run again with `retry_errors=True` and the same `writer_try`;
    - complete, same plan, written `status "failed"` and its `writer_try < MAX_WRITER_TRIES - 1` → set aside as
      `.redo-<n>`, run again with `writer_try + 1` (a fresh key past the cache); at the last try it is kept (an empty
      answer);
    - complete with another plan → `.old-<n>`, run with `writer_try` 0; failed or unsealed → `.failed-<n>`, run with
      `retry_errors=True`;
  - the run: the plan to run (with its `writer_try`) is written to `run_path(...).with_suffix(".plan.json")`, then
    `runner(that file, folder.path, run_path(...).parent, cache=results/<domain>/run-cache, run_id=qid, reason="off",
    links="off", workers=workers, retry_errors=..., **({"provider": provider} if provider else {}))`; an exception is
    listed under `failed` and the next question runs;
  - then `from_system_run` and `save_answer`; a `ValueError` is listed under `failed`; a record with empty text is
    also listed under `empty`.
  Returns `{"ran", "rerun", "kept", "skipped": {qid: reason}, "failed": {qid: reason}, "empty": [qid],
  "by_system": [qid]}` (`by_system`: answers whose plan the system confirmed).
- Produces: `synth3 system-run --domain D [--seeds 1,2,3,4,5] [--workers 3] [--confirm-as-system] [--folders F]
  [--plans P] [--questions-root Q] [--spec-root S] [--results R]`: `each_folder` over the seeds; prints per seed
  `s<n>: ran <a>, rerun <b>, kept <c>, skipped <d>, failed <e>, empty <f>, plans confirmed by system <g>` then each
  reason; exit 1 when anything failed.

- [ ] **Step 1: Write the failing tests.** `counting_runner(calls, writer_reply=OK_REPLY)` is a runner that records
  `(plan file, kwargs)` in `calls` and makes the run through the real `planrun.run` with `selection="regex-only"` and
  `provider=provider_of(system_model(writer_reply))` added to the kwargs it got. A test that needs a finished run with
  a given `written-answer.json` makes it with the `writer_reply` that gives that result.

```python
def setup(folder, tmp_path, SPEC, confirmed="aditya"):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX)
    write_demo_plans(tmp_path / "plans", qs, SPEC, confirmed=confirmed)
    return f, qs

def test_one_folder_runs_every_plan_and_saves_records(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC); calls = []
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert sorted(out["ran"]) == ["d01", "d02", "d03"] and out["failed"] == {} and out["by_system"] == []
    assert {r.question_id for r in load_answers(tmp_path / "res", "demo")} == {"d01", "d02", "d03"}
    assert all(k["reason"] == "off" and k["links"] == "off" for _, k in calls)

def test_an_unconfirmed_plan_is_skipped_without_the_flag(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC, confirmed=None); calls = []
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert calls == [] and set(out["skipped"]) == {"d01", "d02", "d03"}
    assert "--confirm-as-system" in out["skipped"]["d01"] and "not confirmed by a person" in out["skipped"]["d01"]

def test_confirm_as_system_runs_a_copy_and_leaves_the_draft(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC, confirmed=None); calls = []
    draft = plan_path(tmp_path / "plans", "demo", "d01"); before = draft.read_bytes()
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", as_system=True, workers=1,
                     runner=counting_runner(calls))
    assert draft.read_bytes() == before and sorted(out["by_system"]) == ["d01", "d02", "d03"]
    auto = load_plan(auto_path(tmp_path / "plans", "demo", "d01"))
    assert auto.ready() and {d.confirmed_by for d in auto.decisions} == {"system"}
    recs = load_answers(tmp_path / "res", "demo")
    assert {r.plan_confirmed_by for r in recs} == {"system"}
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", as_system=True, workers=1, runner=counting_runner(calls))
    assert len(calls) == 3   # the copy is kept when the draft did not change, so the runs are kept

def test_a_second_run_keeps_complete_runs(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC); calls = []
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert out["ran"] == [] and sorted(out["kept"]) == ["d01", "d02", "d03"] and len(calls) == 3

def test_a_changed_plan_runs_again_and_the_old_run_is_kept_aside(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC); calls = []
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    path = plan_path(tmp_path / "plans", "demo", "d01"); p = load_plan(path)
    write_plan(p.model_copy(update={"decisions": [d.model_copy(update={"value": "0.02"}) if d.type == "threshold"
                                                  else d for d in p.decisions]}), path)
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert out["ran"] == ["d01"] and run_path(tmp_path / "res", "demo", 1, "d01").with_name("d01.old-1").is_dir()

def test_a_failed_writer_call_is_rerun_with_retry(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC); calls = []
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1,
               runner=counting_runner(calls, writer_reply=lambda p: RuntimeError("down")))
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert sorted(out["rerun"]) == ["d01", "d02", "d03"] and all(k["retry_errors"] for _, k in calls[3:])
    assert run_path(tmp_path / "res", "demo", 1, "d01").with_name("d01.redo-1").is_dir()
    assert out["failed"] == {}

def test_a_written_answer_that_failed_its_checks_is_asked_again_with_a_fresh_key(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC); calls = []; bad = lambda p: {"sentences": []}
    first = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls, bad))
    assert sorted(first["empty"]) == ["d01", "d02", "d03"]
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls, bad))
    assert load_plan(calls[3][0]).writer_try == 1
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls, bad))
    last = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls, bad))
    assert sorted(last["kept"]) == ["d01", "d02", "d03"] and len(calls) == 3 * MAX_WRITER_TRIES

def test_missing_stale_and_rekinded_plans_are_skipped_with_reasons(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC)
    plan_path(tmp_path / "plans", "demo", "d02").unlink()
    edited = qs.model_copy(update={"questions": [qs.get("d01").model_copy(update={"kind": "effect"}),
                                                 qs.get("d02"),
                                                 qs.get("d03").model_copy(update={"question": "Changed?"})]})
    out = run_folder(f, edited, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner([]))
    assert out["skipped"]["d02"] == "no plan; run synth3 system-plan first"
    assert out["skipped"]["d03"] == "the question changed after planning"
    assert out["skipped"]["d01"].startswith("the plan answers by written, the question asks for effect")

def test_system_run_by_command(folder, tmp_path, spec_dir, monkeypatch, capsys):
    f, qs = setup(folder, tmp_path, load_spec("demo", spec_dir))
    monkeypatch.setattr(system, "planrun_run", counting_runner([]))   # the default runner, looked up at call time
    assert main(["system-run", "--domain", "demo", "--seeds", "1", "--workers", "1", "--folders", str(folder.parent),
                 "--plans", str(tmp_path / "plans"), "--questions-root", str(FIX), "--spec-root", str(spec_dir),
                 "--results", str(tmp_path / "res")]) == 0
    assert "s1: ran 3, rerun 0, kept 0, skipped 0, failed 0, empty 0, plans confirmed by system 0" in capsys.readouterr().out
```

  `system.py` imports `planrun.run` as `planrun_run` and `run_folder`'s default `runner=None` means "use
  `planrun_run`" (looked up at call time, so the command test can replace it).
- [ ] **Step 2: Run** `uv run pytest -q backend/synth3/tests/test_system_run.py`. Expected: FAIL.
- [ ] **Step 3: Implement**; Run line: `uv run synth3 system-run --domain D [--workers N] [--confirm-as-system]   #
  every confirmed plan on every folder (orch-model, cluster), saved for the judge as system "system"; reruns failed
  written answers and unchecked items`.
- [ ] **Step 4: Run** `uv run pytest -q backend/synth3 backend/evidence/tests/test_plan_run.py`. Expected: PASS.
- [ ] **Step 5: Commit** the four files: `synth3: every confirmed plan run on every folder and collected`.

### Task 11: The report says who confirmed the plans and what the writer did not see

**Files:**
- Modify: `backend/synth3/report.py`, `backend/synth3/tests/test_report.py`

**Interfaces:**
- Consumes: `AnswerRecord.plan_confirmed_by`, `AnswerRecord.facts_left_out` (Task 8); `build_report`,
  `render_report`, `_row` (plan 3).
- Produces in each report row: `plans_person: int`, `plans_system: int` (records with that `plan_confirmed_by`),
  `facts_left_out: int` (records whose `facts_left_out` is above 0); the JSON keeps them; `render_report` adds the
  columns "plans by person / by system" and "answers with facts left out" to the system table, and, when any row has
  `plans_system > 0`, the line (exact copy) `<n> of <m> system answers ran on plans the system confirmed, not a
  person (spec §8 puts a person's edit in the system): reported as a limitation.`

- [ ] **Step 1: Write the failing test** (`fake_marks` of plan 3's `test_report.py`, plus records with the two new
  fields):

```python
def test_the_report_counts_who_confirmed_the_plans(tmp_path):
    fake_marks(tmp_path / "res", systems=("system", "rag-baseline"), questions=4, seeds=1)
    for i, rec in enumerate(load_answers(tmp_path / "res", "demo")):
        if rec.system == "system":
            save_answer(tmp_path / "res", rec.model_copy(update={"plan_confirmed_by": "system" if i % 2 else "person",
                                                                 "facts_left_out": 3 if i == 0 else 0}))
    r = build_report(tmp_path / "res", ["demo"], tmp_path / "sh", tmp_path / "jt")
    row = next(x for x in r["domains"]["demo"]["rows"] if x["system"] == "system")
    assert row["plans_person"] + row["plans_system"] == 4 and row["plans_system"] == 2
    assert "2 of 4 system answers ran on plans the system confirmed, not a person" in render_report(r)
    base = next(x for x in r["domains"]["demo"]["rows"] if x["system"] == "rag-baseline")
    assert base["plans_person"] == base["plans_system"] == 0
```

  (Use the row path `report.py` really has; the names above follow plan 3's `build_report` JSON. If `fake_marks`
  writes no answer records, write them with plan 3's `rec()` helper beside the marks.)
- [ ] **Step 2: Run** `uv run pytest -q backend/synth3/tests/test_report.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the counters and the rendering.
- [ ] **Step 4: Run** `uv run pytest -q backend/synth3`. Expected: PASS.
- [ ] **Step 5: Commit** both files: `synth3: the report says who confirmed each answer's plan`.

### Task 12: The plan API takes sub-questions, the answer kind, a synth3 folder and batch plans

**Files:**
- Modify: `backend/webapp/evplan.py`, `backend/webapp/planwire.py`
- Create: `backend/webapp/evsystem.py` (this task: `synth3_folder` only), `backend/webapp/tests/test_evplan_system.py`

**Interfaces:**
- Consumes: `with_answer` (Task 2), `answer_problems` (Task 4), `propose(sub_questions=...)` (Task 3);
  `plan_path`, `plan_stale` (Task 9); `ReviewFiles` (webapp/evreview.py: `folders`, `built_seeds`, `spec`,
  `questions`, `question`), `load_folder`.
- Produces in `evsystem.py`: `synth3_folder(settings: Settings, domain: str, seed: int) -> Path`: `check_id(domain)`,
  the seed among `ReviewFiles(settings).built_seeds(domain)` else `NotFound`, the folder loads (`load_folder`) else
  `NotFound` naming why; returns the folder path.
- Produces in `evplan.py` (the docstring lists the new routes and says the answer kind is chosen on `/system`, and a
  `written` plan's result shows the written answer's text):
  - `PlanStart.sub_questions: list[str] = []` (each stripped; an empty one is a 400 `"a sub-question is empty"`),
    `PlanStart.answer_by: str = "lines"`, `PlanStart.target: str | None = None` (checked as `with_answer` checks them:
    400 with its text). The `Entry` keeps all three; `make()` passes the sub-questions to `be.do_propose(question,
    answers, sub_questions)` and applies `with_answer(plan, answer_by, target)` to every plan it makes, so a plan made
    after `/clarify` keeps them. `PlanBackend.do_propose` calls a test fake `propose(question, answers)` as before
    when there are no sub-questions and `propose(question, answers, sub_questions=...)` when there are; the real path
    passes them to `evidence.planner.propose`;
  - `PlanView.sub_questions: list[str] = []`, `PlanView.batch: str | None = None` (`"<domain>/<qid>"` for a batch
    plan);
  - `POST /plan/{pid}/answer` body `AnswerRequest{answer_by: str, target: str | None = None}` → the plan with
    `with_answer` (400 with the `ValueError` text), saved, only while open (409 otherwise); 409 `"a batch plan's
    answer kind comes from the question file"` for a batch plan; 409 `"answer the clarifying questions first"` with
    no plan yet (the kind is then kept on the entry and applied when the plan is made);
  - `POST /plan/batch/{domain}/{qid}` → opens `plan_path(settings.synth3_data / "plans", domain, qid)` as a new
    entry bound to that file (404 when there is no file; ids through `check_id`); the view's `problems` also hold
    `plan_stale(plan, question)` when the question file's question differs. Every later change of that entry
    (`decision`, `confirm-all`, `main-rule`, line delete) writes the plan back to that file (atomically, under the
    entry's lock) as well as to `$EV/plans/<id>/`; the run does not change the file;
  - the view's `problems` and the run's 409 check also hold `answer_problems(plan)`;
  - `POST /plan/{pid}/run` body `RunRequest{domain: str | None = None, seed: int | None = None}` (an empty body is
    today's run): both or neither (400 `"give both domain and seed, or neither"`); with them,
    `corpus = synth3_folder(settings, domain, seed)` and `be.run(plan, d, corpus=corpus)`; without,
    `be.run(plan, d)` as today.
- Produces in `planwire.py`: `PlanRuns.run(plan, folder, corpus: Path | None = None) -> str`: with `corpus`, that
  folder (no `$EV_PLAN_CORPUS` needed) and `reason="off"`, `links="off"`; without, today's behaviour.
  `PlanRuns.result(rid)`: when the run has `written-answer.json` with an `answer_text`, the result's
  `answer.text` is that text (a `failed` one: `"The model's answer failed its checks: <problems>"`).

- [ ] **Step 1: Write the failing tests** (the `world` fixture pattern of `test_evplan.py`: `fake_backend(**parts)`
  is a `PlanBackend` with fake `clarify` (none asked unless given), `propose`, `critic`, `run`; `plan_of(q)` a
  confirmed-free plan; `review_root` from `webapp/tests/test_evreview.py`; `client(tmp_path, be, **env)`):

```python
def test_sub_questions_reach_the_planner_and_the_view(tmp_path):
    seen = {}
    be = fake_backend(propose=lambda q, a, sub_questions=(): (seen.update(sub=list(sub_questions)), plan_of(q))[1])
    v = client(tmp_path, be).post("/api/ev/plan", json={"question": "Q?", "sub_questions": ["S1?"]}).json()
    assert seen["sub"] == ["S1?"] and v["sub_questions"] == ["S1?"] and v["plan"]["sub_questions"] == ["S1?"]

def test_an_old_style_propose_fake_still_works_without_sub_questions(tmp_path):
    be = fake_backend(propose=lambda q, a: plan_of(q))
    assert client(tmp_path, be).post("/api/ev/plan", json={"question": "Q?"}).status_code == 200

def test_the_answer_kind_survives_clarifying_questions(tmp_path):
    be = fake_backend(clarify=lambda q: [{"question": "Which?", "options": ["a", "b"]}])
    c = client(tmp_path, be)
    v = c.post("/api/ev/plan", json={"question": "Q?", "answer_by": "inventory", "target": "metric"}).json()
    assert v["plan"] is None
    v = c.post(f"/api/ev/plan/{v['id']}/clarify", json={"answers": [{"question": "Which?", "answer": "a"}]}).json()
    assert v["plan"]["answer_by"] == "inventory" and v["plan"]["target"] == "metric"

def test_the_answer_kind_is_set_and_checked(tmp_path):
    c = client(tmp_path, fake_backend()); pid = c.post("/api/ev/plan", json={"question": "Q?"}).json()["id"]
    assert c.post(f"/api/ev/plan/{pid}/answer", json={"answer_by": "inventory", "target": "metric"}).json()["plan"]["target"] == "metric"
    assert c.post(f"/api/ev/plan/{pid}/answer", json={"answer_by": "written", "target": "metric"}).status_code == 400
    assert c.post("/api/ev/plan", json={"question": "Q?", "answer_by": "chaining"}).status_code == 400

def test_a_batch_plan_opens_and_its_edits_are_saved_to_its_file(review_root, tmp_path):
    qs = load_questions("demo", load_spec("demo", review_root), review_root / "questions")
    write_demo_plans(review_root / "plans", qs, load_spec("demo", review_root), confirmed=None)
    c = client(tmp_path, fake_backend(), SYNTH3_DATA=review_root)
    v = c.post("/api/ev/plan/batch/demo/d01").json()
    assert v["batch"] == "demo/d01" and not v["ready"]
    c.post(f"/api/ev/plan/{v['id']}/confirm-all")
    saved = load_plan(review_root / "plans" / "demo" / "d01.json")
    assert saved.ready() and {d.confirmed_by for d in saved.decisions} == {Settings().user}
    assert c.post(f"/api/ev/plan/{v['id']}/answer", json={"answer_by": "effect"}).status_code == 409
    assert c.post("/api/ev/plan/batch/demo/d09").status_code == 404

def test_a_run_on_a_synth3_folder_passes_the_folder(review_root, tmp_path):
    got = {}
    be = fake_backend(run=lambda plan, d, corpus=None: (got.update(corpus=corpus), "r1")[1])
    c = client(tmp_path, be, SYNTH3_DATA=review_root); pid = confirmed_plan(c)
    assert c.post(f"/api/ev/plan/{pid}/run", json={"domain": "demo", "seed": 1}).json() == {"run": "r1"}
    assert Path(got["corpus"]).resolve() == (review_root / "built" / "demo" / "s1").resolve()

@pytest.mark.parametrize("body", [{"domain": "demo"}, {"domain": "demo", "seed": 9}, {"domain": "..", "seed": 1}])
def test_a_bad_folder_is_refused(review_root, tmp_path, body):
    called = []
    be = fake_backend(run=lambda plan, d, corpus=None: (called.append(1), "r1")[1])
    c = client(tmp_path, be, SYNTH3_DATA=review_root); pid = confirmed_plan(c)
    assert c.post(f"/api/ev/plan/{pid}/run", json=body).status_code in (400, 404) and called == []

def test_plan_runs_on_a_given_corpus_turn_reasoning_and_links_off(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(planrun, "run", lambda path, corpus, out, **kw: seen.update(corpus=corpus, **kw))
    runs = PlanRuns(Settings(EV=tmp_path / "ev"))
    rid = runs.run(make_plan(), None, corpus=tmp_path / "c")
    runs.threads[rid].join(5)
    assert seen["reason"] == "off" and seen["links"] == "off" and seen["corpus"] == tmp_path / "c"

def test_a_written_result_shows_the_written_text(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    run = make_system_run(tmp_path / "ev" / "runs", f, qq, demo_plan(SPEC, qq), writer_reply=FACT_REPLY, run_id="r1")
    want = json.loads((run / "written-answer.json").read_text(encoding="utf-8"))["answer_text"]
    assert PlanRuns(Settings(EV=tmp_path / "ev")).result("r1")["answer"]["text"] == want
```

  (`folder`, `SPEC`, `q` come from `backend/synth3/tests/conftest.py`; import its fixtures into this test module.)
- [ ] **Step 2: Run** `uv run pytest -q backend/webapp/tests/test_evplan_system.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the changes.
- [ ] **Step 4: Run** `uv run pytest -q backend/webapp`. Expected: PASS (`test_evplan.py` unchanged).
- [ ] **Step 5: Commit** the four files: `webapp: the plan API takes sub-questions, the answer kind, a synth3 folder and
  batch plans`.

### Task 13: The system API: domains, the four rows and the paper view

**Files:**
- Modify: `backend/webapp/evsystem.py`, `backend/webapp/app.py` (include `evsystem_router(s)` at `/api/ev`; its
  docstring names the system API as read-only)
- Create: `backend/webapp/tests/test_evsystem.py`

**Interfaces:**
- Consumes: `ReviewFiles` (`domains`, `spec`, `questions`, `built_seeds`); `plan_path`, `plan_stale`, `auto_path`
  (Task 9, 10); `RunDir`; `written.fact_lines`, `written.fact_budget`, `written.STAGE`; `kindtext.kind_lines`,
  `plan_names`, `RULE_TEXT`; `evidence.protocol.parse`; `load_plan`; `evfiles.segments`; `files.check_id`, `inside`,
  `NotFound`.
- Produces: `evsystem_router(settings: Settings) -> APIRouter`:

| Method and path | Answer |
|---|---|
| `GET /system/domains` | `[{domain, seeds: [n], questions: [{id, question, sub_questions, kind, target, plan}], error}]`; `plan` is `"missing"`, `"draft"`, `"confirmed"` or `"stale"` (the batch plan's state); a broken or missing question file gives `questions: []` and `error` its text |
| `GET /system/runs/{rid}/steps` | `SystemSteps` (below); 404 for an unknown run |
| `GET /system/runs/{rid}/papers/{doc}` | `{paper, text, segments}`: the paper of the run's corpus with the spans of the run's items in it (`segments`) |

- Produces: `steps_of(run: Path) -> SystemSteps` (pydantic models in `evsystem.py`):
  - `status`: `running` (not sealed), `failed` (sealed failed; `error` its reason), `done`;
  - `answer_by` (the run's plan) and `question`;
  - `find: {count, papers: [{paper, kept: bool, why: str}]}` from funnel.json: `kept` when the screen did not drop
    it; `why` "screened out", "kept by the screen" or "no screen"; `count` the kept papers with at least one fact;
  - `pull: {count, left_out: int, facts: [{n, item, paper, type, text}]}`: for a written run the facts of
    `written-answer.json` (the numbers the writer saw) and `left_out` from its `cut`; else `fact_lines` over the
    run's items by paper with the run's plan and `fact_budget` (the same numbering rule);
  - `combine: {rule, count, rows: [{text, facts: [n]}]}`: `rule` from `RULE_TEXT` (`lines` formatted with the main
    rule); rows: written → one row per fact the answer cites, its text; fixed kind → the study lines of
    `kind_lines(parse(protocol.yaml), answer["synthesis"], plan_names(plan))` with their items turned into fact
    numbers; lines → each plan line's question and row count from answer.json `lines`;
  - `answer: {text, status, problems, lines: [{text, facts: [n]}]}`: written → its sentences; fixed kind → the
    summary lines of `kind_lines`; lines → answer.json `answer.text`.
- Every path part goes through `check_id`; the run folder is `inside(settings.ev_runs_dir, rid)` and must be an
  engine run (`RunDir.kind == "engine"`) of a plan (`plan.json` present); the paper's text is read from the corpus
  named in run.json `settings.corpus` (a folder holding `manifest.json`), the paper must be in its manifest.

- [ ] **Step 1: Write the failing tests.** A fixture `system_runs(tmp_path, review_root)` makes one written run
  (`d01`, `writer_reply=FACT_REPLY`) and one effect run (a copy of `d01` with `kind="effect"`, run id `d01e`,
  `demo_plan(SPEC, q, "effect")`) with `make_system_run` (Task 8) into `tmp_path / "ev" / "runs"` and returns
  `{"written": "d01", "effect": "d01e"}`; `client(tmp_path, review_root)` is `TestClient(create_app(Settings(
  EV=tmp_path / "ev", SYNTH3_DATA=review_root), plan_backend=PlanBackend()))`.

```python
def test_domains_list_folders_questions_and_plan_states(review_root, tmp_path):
    rows = client(tmp_path, review_root).get("/api/ev/system/domains").json()
    demo = next(r for r in rows if r["domain"] == "demo")
    assert demo["seeds"] == [1] and [q["id"] for q in demo["questions"]] == ["d01", "d02", "d03"]
    assert {q["plan"] for q in demo["questions"]} == {"missing"}

def test_the_four_rows_of_a_written_run(system_runs, tmp_path, review_root):
    s = client(tmp_path, review_root).get(f"/api/ev/system/runs/{system_runs['written']}/steps").json()
    assert s["status"] == "done" and s["answer_by"] == "written"
    assert s["pull"]["count"] == len(s["pull"]["facts"]) >= 1 and s["find"]["count"] >= 1
    assert s["combine"]["rule"].startswith("A model (orch-model) wrote the answer")
    assert s["answer"]["lines"][0]["facts"] == [1] and s["combine"]["rows"][0]["facts"] == [1]

def test_an_effect_run_shows_the_kind_rule(system_runs, tmp_path, review_root):
    s = client(tmp_path, review_root).get(f"/api/ev/system/runs/{system_runs['effect']}/steps").json()
    assert s["combine"]["rule"] == RULE_TEXT["effect"]
    assert s["answer"]["lines"][0]["text"].startswith("Targeted therapy against Standard care on Response rate: ")

def test_a_paper_shows_the_run_items_marked(system_runs, tmp_path, review_root):
    c = client(tmp_path, review_root)
    fact = c.get(f"/api/ev/system/runs/{system_runs['written']}/steps").json()["pull"]["facts"][0]
    page = c.get(f"/api/ev/system/runs/{system_runs['written']}/papers/{fact['paper']}").json()
    assert page["text"] and any(fact["item"] in (seg.get("marks") or []) for seg in page["segments"])

def test_a_running_run_says_running(system_runs, tmp_path, review_root):
    (tmp_path / "ev" / "runs" / system_runs["written"] / "manifest.json").unlink()
    s = client(tmp_path, review_root).get(f"/api/ev/system/runs/{system_runs['written']}/steps").json()
    assert s["status"] == "running" and s["pull"]["facts"] == [] and s["answer"]["lines"] == []

@pytest.mark.parametrize("path", ["/api/ev/system/runs/..%2F..%2Fetc/steps", "/api/ev/system/runs/-x/steps",
                                  "/api/ev/system/runs/nope/steps", "/api/ev/system/runs/d01/papers/S999",
                                  "/api/ev/system/runs/d01/papers/..%2Fmanifest"])
def test_bad_ids_are_refused(system_runs, tmp_path, review_root, path):
    assert client(tmp_path, review_root).get(path).status_code in (400, 404, 422)
```

- [ ] **Step 2: Run** `uv run pytest -q backend/webapp/tests/test_evsystem.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the router, `steps_of` and the mount.
- [ ] **Step 4: Run** `uv run pytest -q backend/webapp`. Expected: PASS.
- [ ] **Step 5: Commit** the three files: `webapp: system API for the one-page UI (domains, the four rows, papers)`.

### Task 14: The plan page: a sub-question box and batch plans

**Files:**
- Create: `frontend/src/routes/plan/SubQuestionsBox.tsx`
- Modify: `frontend/src/routes/plan/PlanPage.tsx` (the box under the question; `?batch=<domain>/<qid>` opens a batch
  plan; export `Clarify`), `frontend/src/routes/plan/api.ts` (`startPlan(question, subQuestions = [], answer?:
  {answer_by, target})` sends `sub_questions` and the answer kind; `PlanView.sub_questions`, `PlanView.batch`,
  `PlanData.sub_questions?`, `answer_by?`, `target?`; `openBatchPlan(domain, qid)`; `setAnswer(id, answerBy,
  target)`; `startRun(id, folder?: {domain, seed})`), `frontend/src/routes/plan/plan.test.tsx`

**Interfaces:**
- Consumes: Task 12's plan API.
- Produces: `SubQuestionsBox({ value: string, onChange })` (a labelled textarea "Sub-questions (optional, one per
  line; they help draft the plan and are never scored)") and `parseSubQuestions(text: string): string[]` (lines
  trimmed, empty lines dropped). With `?batch=demo/d01` the page posts `/api/ev/plan/batch/demo/d01` once and shows
  that plan with the note "Batch plan demo/d01: your changes are saved to its file." and its sub-questions (read-only).

- [ ] **Step 1: Write the failing tests** in `plan.test.tsx`:
  - `it("sends the sub-questions with the question")`: typing two lines and one empty line in the box sends one POST
    `/api/ev/plan` with `{question: "Does it help?", sub_questions: ["A?", "B?"]}`;
  - `it("opens a batch plan from the address and says where edits go")`: rendered at `/plan?batch=demo/d01`, one
    POST to `/api/ev/plan/batch/demo/d01`, the note text is shown, and "Confirm all" posts to that plan's id.
- [ ] **Step 2: Run** `npm test -- plan` in `frontend/`. Expected: FAIL.
- [ ] **Step 3: Implement** the box, the batch opening and the api changes.
- [ ] **Step 4: Run** `npm test`, `npm run typecheck`, `npm run lint`. Expected: PASS.
- [ ] **Step 5: Commit** the four files: `webapp: sub-question box and batch plans on the plan page`.

### Task 15: The one-page page, boxes 1 to 3

**Files:**
- Create: `frontend/src/routes/system/api.ts`, `SystemPage.tsx`, `PickBox.tsx`, `QuestionBox.tsx`, `ProtocolBox.tsx`,
  `system.test.tsx`, `frontend/src/mocks/system.ts`
- Modify: `frontend/src/app/routes.tsx` (lazy `SystemPage`, route `system`), `frontend/src/components/layout/pages.ts`
  (VIEWER entry `{ to: "/system", label: "System", icon: WorkflowIcon }` first), `frontend/src/mocks/handlers.ts`
  (`...systemHandlers`)

**Interfaces:**
- Consumes: Task 12's plan API, Task 13's `GET /api/ev/system/domains`; Task 14's `SubQuestionsBox`, `Clarify`,
  `startPlan`, `openBatchPlan`; `LineCard`, `DecisionsPanel`.
- Produces in `system/api.ts`: hand-written types `SystemDomain`, `SystemQuestion`, `SystemSteps`, `StepFact`,
  `AnswerLine`, `PaperView` (Task 13's shapes), hooks `useSystemDomains()`, `useSteps(rid, enabled)`,
  `usePaper(rid, doc)`.
- The page `/system`, top to bottom, each box a card whose content shows only when the box above is done (else the
  muted line "Finish the box above first."):
  1. **Folder:** domain select and folder (seed) select; done when both are chosen.
  2. **Question:** a select "Use a question from the domain's file" (fills the text, the sub-questions and the
     answer kind), the question text, `SubQuestionsBox`, and "How the answer is made" (`written` "Written by a model
     from the facts (any question)", `effect`, `consistency`, `inventory` + target select condition / metric,
     `best`). The button "Draft the protocol" posts `/plan` with the question, `sub_questions`, `answer_by` and
     `target` in one call. When the chosen file question has a batch plan (`plan` not `missing`), a second button
     "Open its batch plan" calls `openBatchPlan` instead, with a link "edit on the plan page" to `/plan?batch=...`.
     Done when the plan view exists.
  3. **Protocol:** clarifying questions if asked (`Clarify`), the lines (`LineCard`), the decisions
     (`DecisionsPanel`, confirm, change, confirm all), the problems; "Run on <domain> s<seed>" enabled only when
     `ready`, posting `/plan/{id}/run` with `{domain, seed}`; done when the run starts.

- [ ] **Step 1: Write the failing tests** (`server.use` handlers record request bodies, as the plan page tests do):
  - `it("opens each box only after the one above is done")`: at first only box 1 has controls and boxes 2 and 3 say
    "Finish the box above first."; choosing demo and s1 shows the question box's controls;
  - `it("fills the question from the domain's file")`: choosing d02 fills the text and both sub-questions;
  - `it("drafts the protocol with the sub-questions and the answer kind in one call")`: one POST `/api/ev/plan` with
    `{question, sub_questions, answer_by: "inventory", target: "metric"}` and no POST to `/answer`;
  - `it("keeps the answer kind when the planner asks a clarifying question")`: the start answers with one
    clarification and `plan: null`; answering it posts `/clarify`; the shown plan's kind reads "inventory";
  - `it("opens a question's batch plan")`: for d01 with `plan: "draft"`, "Open its batch plan" posts
    `/api/ev/plan/batch/demo/d01`;
  - `it("runs on the chosen folder only when every decision is confirmed")`: the Run button is disabled until confirm
    all; clicking it sends `{domain: "demo", seed: 1}`.
- [ ] **Step 2: Run** `npm test -- system` in `frontend/`. Expected: FAIL.
- [ ] **Step 3: Implement** the page's first three boxes, the route, the sidebar entry and the mocks.
- [ ] **Step 4: Run** `npm test`, `npm run typecheck`, `npm run lint`. Expected: PASS.
- [ ] **Step 5: Commit** the new and changed files: `webapp: the one-page system page (folder, question, protocol)`.

### Task 16: The one-page page, boxes 4 and 5, and the build

**Files:**
- Create: `frontend/src/routes/system/RunBox.tsx`, `AnswerBox.tsx`, `PaperPanel.tsx`
- Modify: `frontend/src/routes/system/SystemPage.tsx`, `system.test.tsx`, `frontend/src/mocks/system.ts`,
  `frontend/openapi.json` and `frontend/src/api/schema.d.ts` (regenerated), `frontend/dist/` (rebuilt)

**Interfaces:**
- Consumes: `usePlanResult` (polls `/plan/{id}/result` while `running`), `useSteps`, `usePaper`, `PaperText`.
- The boxes:
  4. **Run:** while running, "Running..." with the plan result's status; on `failed: <reason>` that text in an alert;
     when done, four rows **Find**, **Pull out**, **Combine**, **Answer**, each with its count and a "Show" toggle:
     Find lists papers with kept or dropped and why; Pull out lists the numbered facts (paper, type, text), each a
     button that opens `PaperPanel` with that fact's spans marked, and, when `left_out > 0`, the note "<n> facts that
     bear on the plan were not given to the writer"; Combine shows the rule sentence and its rows with their fact
     numbers; Answer lists the answer lines with their fact numbers. Done when the run is done.
  5. **Answer:** the answer text; each line's fact numbers are buttons that open Pull out and mark that fact
     (`data-selected`); a written answer with status `failed` says "The model's answer failed its checks: <problems>".

- [ ] **Step 1: Write the failing tests:**
  - `it("shows the four rows with their counts once the run is done")`: the result handler answers `running` then
    `done`; "Running..." shows first, then the rows read "Find 3", "Pull out 5", "Combine", "Answer";
  - `it("lists a row when it is opened")`: "Show" on Find lists the three papers with "screened out" on one;
  - `it("links each answer line to its facts")`: clicking fact `2` in the answer box marks fact 2 in Pull out
    (`data-selected="true"`) and no other fact;
  - `it("shows a fact in its paper")`: clicking fact 1 renders the paper text with a `mark` whose `data-marks` holds
    its item id;
  - `it("says what the writer did not see")`: with `left_out: 4` the note "4 facts that bear on the plan were not
    given to the writer" is shown;
  - `it("says when the written answer failed its checks")`: status `failed`, problems `["give 1 to 8 sentences"]` →
    "The model's answer failed its checks: give 1 to 8 sentences".
- [ ] **Step 2: Run** `npm test -- system`. Expected: FAIL.
- [ ] **Step 3: Implement** the two boxes and the paper panel.
- [ ] **Step 4: Run** `npm test`, `npm run typecheck`, `npm run lint`. Expected: PASS. Then from the repo root
  `uv run webapp openapi -o frontend/openapi.json && (cd frontend && npm run gen:api)` and `npm run build` in
  `frontend/`. Check by hand: `uv run webapp serve` with `EV` and `SYNTH3_DATA` pointing at a scratchpad copy of Task
  13's fixture runs, open `/system`, pick demo s1, and click through the boxes and rows (the `run` skill can drive it;
  the planner has no model here, so start from `npm run dev:mock` for boxes 2 to 3).
- [ ] **Step 5: Commit** the new and changed source files, `frontend/openapi.json`, `frontend/src/api/schema.d.ts`
  and `frontend/dist/` (stage `frontend/dist` by path): `webapp: the one-page system page (run rows and answer)`.

### Task 17: Close: the whole suite and the list for Aditya

**Files:**
- Modify: `backend/README.md` only if a Run line from Tasks 9-10 is missing
- Not committed: `.superpowers/sdd/synth3-program.md` (the program ledger)

- [ ] **Step 1: Run the whole suite** `uv run pytest -q` (with the Windows `--ignore`s). Expected: PASS apart from the
  known `agent/tests` import errors. Run `uv run synth3 --help` and check `system-plan` and `system-run` are listed.
- [ ] **Step 2: Check the gates held:** `git ls-files data/synth3/plans data/synth3/results` prints nothing, and
  `git status --short data/synth3` shows no staged file.
- [ ] **Step 3: Commit** a README fix if Step 1 found one: `synth3: README run lines for the system`.
- [ ] **Step 4: Add to the ledger's list "for Aditya to run or decide"** (in this order; the plan does not wait):
  1. after his questions exist (plan 3's step 1): on the cluster `uv run synth3 system-plan --domain medicine`
     (orch-model drafts one plan per question; nothing is confirmed);
  2. **decide:** review the plans yourself (open each on `/plan?batch=medicine/<qid>` or from `/system`, edit and
     confirm), or run with `--confirm-as-system` (the report then says how many answers ran on plans no person
     confirmed, as a limitation of spec §8's system);
  3. on the cluster: `uv run synth3 system-run --domain medicine --workers N [--confirm-as-system]` (orch-model; one
     plan run per question and folder, 125 runs of 40 papers, heavy). Run the same command again until it reports no
     failures: it reruns failed runs, failed writer calls and runs with unchecked items with retry, asks a written
     answer that failed its checks again with a fresh key (up to 3 tries; then it stays an empty answer), and keeps
     every complete good run;
  4. then plan 3's steps: `uv run synth3 judge --domain medicine` (the `system` records are judged beside
     `rag-baseline`), `judge-sample`, hand marks, `report`;
  5. click through `/system` once on one folder and `/plan` with sub-questions and a batch plan (never clicked in a
     browser with a real model); keep `$EV` outside the repo or git-ignored, since runs from `/system` copy quotes of
     renamed papers into `$EV/runs`;
  then repeat 1-4 for law, materials and RAG once their worlds are built.
  Notes for him: (a) editing a question's kind asks for the system's answer again (`asked_sha256`), never the
  baseline's; (b) a `best` question answers with the plan's things as the kinds, so it is only as good as the plan's
  names; (c) a failed model call is never scored, a written answer that fails its checks three times is scored as an
  empty answer (counted under `empty`); (d) known limitation beside plan 3's: on the blind judge-test page a system
  answer can be told by its form (sentences ending in `(S003, S010).`, or kind lines), as the baseline can by its
  `[S003, ...]` marks.

---

## Decisions the planner made

Each with its cost if wrong.

1. **The system is the W7 plan run and `/plan` is "the planning page".** Spec §8 says the planning page gets the
   sub-question box and names Tim's compiler chain; the planner is that chain, and its runs need no domain pack (the
   proposal flow's templates are the RAG pack's and cannot draft a medicine protocol). Cost if wrong: the box and the
   kind choice move to the proposal flow's page (Tasks 12, 14, 15 rework); Tasks 5-7 stay.
2. **The written answer is a recorded run stage, not a step after the run.** It is replayed and hashed like every
   other output, so plan 5's readable program and its re-run measure can read it from the run folder. It is written by
   orch-model with code checks; verification stays the judge's (sub-model-1). A later try gets a fresh cache key
   through the plan's `writer_try`, which the run's own plan copy records, so replay still asks no model. Cost if
   wrong: moving the call out of the run (one module) and losing its replay.
3. **Fixed kinds are made from the plan by code (`kind_protocol`).** effect = the plan's own protocol, consistency
   adds its block, inventory takes `target` (condition or metric, a new optional question field), best uses the plan's
   compared things as the kinds with the plan's names. Cost if wrong: best answers may be weak; an inventory of
   settings or datasets is not offered.
4. **The writer's facts are chosen by the plan and round-robin over papers, within half of orch-model's context
   window.** Facts about things or measures the plan does not name are left out and counted. Cost if wrong: a fact
   the question needs is filtered out as off-plan; the count in `cut.off_plan` shows how many.
5. **A plan runs only when a person confirmed it, unless Aditya passes `--confirm-as-system`** (controller ruling C1):
   the system's copy goes to `plans/<d>/auto/`, the draft stays, and records and report carry who confirmed. Cost if
   wrong: none beyond one flag.
6. **A written answer that fails its checks is asked again with a fresh key, up to 3 tries, then scored as empty; a
   failed model call is never scored** and is rerun with retry. Cost if wrong: a few answers scored differently.
7. **Fixed-kind answers reach the judge as code-written lines in plain words (`kind_lines`), not JSON**, with things
   named by the plan's first word-list name and "The papers in this folder cannot answer this question." when the
   kind cannot tell. Cost if wrong: the judge sees less detail per study.
8. **The writer sees the main question only, not the sub-questions** (plan 3's ruling that sub-questions only help
   planning). Cost if wrong: one input line.
9. **No pulled fact means a code answer, with no model call** (`NO_FACTS_TEXT`). Cost if wrong: none for the judge (a
   can't-tell sheet still matches).
10. **The four rows fill in when the run is done**; while running the page says "Running...". The answer kind is
    chosen on `/system` (and kept from the question file for batch plans); `/plan` shows a written run's text. Cost if
    wrong: a live per-paper count later (the trace endpoint already exists).
