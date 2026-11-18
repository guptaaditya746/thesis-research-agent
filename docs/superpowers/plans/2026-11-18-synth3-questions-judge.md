# synth3 Questions and Judge (plan 3 of 5): question files, checklist answer sheets, the judge, the review page, the baseline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** everything needed to mark answers to Aditya's questions on the synth3 folders: a question file he writes,
answer sheets drafted from each folder's truth, a judge that gives three separate scores (A, B, C), the plain RAG
baseline on every question, a report with the judge's agreement with Aditya, and a review page where he checks
worlds and sheets and hand-marks the judge test.

**Architecture:**
- **Questions** (`data/synth3/questions/<domain>.yaml`, written by Aditya): any shape, optional sub-questions,
  optional `about` names. `synth3.questions` loads and checks the file. Sub-questions are kept for plan 4's
  protocol drafting only: they set no scope, never reach the sheet drafter, the baseline or the judge, and are
  never scored (spec §6).
- **The facts a question needs are found by code** (`synth3.sheetfacts`): the planted names in the main question
  (arm labels, measure names, conditions, settings) pick the in-scope facts from `ground_truth.json` `facts`, each
  rendered as one plain line with a stable id (`pair:<t>:<m>`, `h2h:<a>:<b>:<m>`, `rank:<m>`, `study:<sid>`).
  Code alone decides "can't tell" (every in-scope pair has no study).
- **Answer sheets** (`data/synth3/sheets/<domain>/s<seed>/<qid>.json`): checklists of 1 to 6 points, each citing
  the fact lines it rests on. A can't-tell sheet is written by code (one point). Others are drafted by a model
  (`synth3.drafter`, `orch-model`), checked by code, repaired at most once. A sheet records the hashes of its
  question and of the folder's truth; a change makes it stale. Aditya can always fix a sheet on the page: saving a
  stale sheet makes a new unchecked sheet for the current question and truth, and a missing sheet can be written
  from scratch.
- **Answers in one shape** (`synth3.answers.AnswerRecord`): the answer text, the cited papers, and the facts the
  system pulled per paper (engine run folders: `evidence.jsonl` items) or the passages it cited (the baseline).
- **The judge** (`synth3.judge`, `sub-model-1`, as `docs/prompt-writing.md` puts verification on a sub-model):
  three prompts, one task each. C ticks each sheet point; B checks each claim of the answer against the facts it
  used; A marks each planted fact of a paper as found, wrong or missing among the pulled facts. Code checks every
  reply (ids, quotes), gives one repair call, else the decision stays pending; a failed model call is pending too,
  and the run goes on. Code also gives `anchored`, the
  share of planted facts whose placement span a pulled fact touches.
- **Baseline:** `evaluation.baselines.rag.rag_baseline` (the `evaluate rag-baseline` code) on every question and
  folder, scored the same way (A is n/a: it pulls no per-paper facts).
- **Judge test and report** (`synth3.report`): a seeded sample of 30 judged answers, Aditya's hand marks, agreement
  with a flag below 80%, and one report table with the baseline next to the system.
- **The review page** (`/review`): a FastAPI router `webapp/evreview.py` under `/api/ev/review` and a React page
  `frontend/src/routes/review/`, following the plan page's pattern (`webapp/evplan.py`, `frontend/src/routes/plan/`).

**Tech Stack:** Python >= 3.13, pydantic, pyyaml, pydantic-ai (`FunctionModel` fakes in tests), FastAPI
`TestClient`; React 19 + TanStack Query + Vitest + MSW for the page. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-16-multi-domain-benchmark-design.md` (§6, §7, §8 "A separate review
page", §10 "file formats ... judge prompt ... layout", §10b "can't tell", "Score B", "Mix of question kinds",
"Judge agreement", "The answer sheet is a checklist", "Review load", §10c).

**The five plans:**
1. Worlds and template folders (merged).
2. Real-paper planting per domain, medicine first (branch `synth3-real`).
3. **This plan:** questions, checklist answer sheets, the judge (reads `ground_truth.json`), review page, baseline
   scores.
4. The system: model-written answers, the sub-question box and the one-page UI.
5. The readable evidence program and the 5-re-run measurement.

**Review history:** written 17 Nov 2026 by a planner agent. A fresh reviewer found 0 critical, 7 important and 23
minor issues (`.superpowers/sdd/plan3-review.md`); this version fixes all 7 important ones and all 23 minor ones
(M22 by a note on Aditya's list, Task 13).

## Global Constraints

- **Human gates (program ruling):** Aditya writes the 25 questions per domain. This plan never writes a question
  set under `data/`; the only questions are 3 test fixtures for the demo spec
  (`backend/synth3/tests/fixtures/questions/demo.yaml`). Aditya checks sheets and hand-marks the judge test on the
  review page; the code never sets `checked` or a hand mark by itself. Approving a world stays his click.
- **No new LLM, no cluster run:** every model step uses the existing setup (`modelcall.ask_sync`,
  `modelcall.gateway.openai_model(alias)`, `JsonlCache`, `default_key`, `load_prompt`, `CallSettings`), and is
  tested with pydantic-ai `FunctionModel` fakes only, as `backend/synth3/tests/test_reader.py` does. Aliases: the
  sheet drafter is generation, `orch-model`; the judge is verification, `sub-model-1`; the baseline keeps its own
  default, `orch-model`. No test opens a socket. Every run command goes on the "for Aditya to run" list (Task 13).
- **Prompt policy (`docs/prompt-writing.md`):** each model call has one task and one typed reply; each prompt file
  gives the task first, then the inputs, the output fields, three examples (a normal case, a confusing case, a
  missing case) and the acceptance rules. Code checks every reply; a failed check gets one repair call that holds
  the task input, the rejected reply and the failed checks (`MAX_REPAIRS = 1`; `docs/prompt-writing.md`: "the
  failed task, rejected output, and specific failed checks"); every attempt is counted. A reply that still fails,
  and a call that raises `modelcall.ModelCallError` (cut by `max_tokens`, schema failure after pydantic-ai's
  retry, gateway error), is recorded as pending (the drafter: failed) with the redacted reason, never counted as
  right or wrong, and the command goes on with the next item. One shared helper does this for every model step
  (`synth3/asking.py`, Task 4). Prompt hashes go into the cache key (`load_prompt`) and into every output that a
  call made.
- **Prompt examples (`docs/prompt-writing.md`: "demonstrate the rule, rather than tell the model which benchmark
  answer to favor"):** every example in `sheet-v1`, `judge-a-v1`, `judge-b-v1` and `judge-c-v1` uses invented
  names that no domain spec has (e.g. control "Usual method", treatments "Method K" and "Method P", measures
  "Yield" (higher is better) and "Error count" (lower is better), groups "Small batches" / "Large batches"), and
  the examples together show better, worse, no real difference and a split, so no direction is the default. A test
  (Task 8) checks that no name of any spec in `data/synth3/*.yaml` or `data/synth3/drafts/*.yaml` occurs in a
  prompt file.
- **Marking (spec §7, Aditya's call):** the judge marks A, B and C; code only selects the inputs, checks replies,
  and adds `anchored` as an extra number beside A (builder's call: anchoring is code by the prompt policy, but it
  is not the score).
- **Three scores, kept separate:** A = found planted facts / planted facts in scope (pooled over papers);
  B = supported claims / claims; C = met points / points. Each is a float in [0, 1] or `null` (n/a or pending).
- **Hashed files:** never edit the files under "Hashed files: never edit" in `backend/README.md` (this plan only
  imports `evaluation.baselines.rag` and `evidence.rundir`; it changes neither).
- **Boundaries:** new Python code lives in `backend/synth3/` (evaluation service; it may import `evaluation`,
  `evidence`, `modelcall`, `jsonio`, `repo_paths`) and `backend/webapp/evreview.py` (api; it may import `synth3`).
  No new package, so `backend/tests/test_boundaries.py` needs no change. `synth2` stays read-only.
- **New commands go in a new module** `backend/synth3/qcli.py` (`add_question_commands(sub)`, called once from
  `synth3.cli.parser()`), so `cli.py` grows by two lines (builder's call: `cli.py` is already 285 lines). The
  helpers both need (`BadArgument`, `_Parser`, `_seeds`, `_spec`) move from `cli.py` to a new
  `backend/synth3/cliargs.py`, which imports neither; `cli.py` and `qcli.py` import from it, so there is no import
  cycle (Task 2).
- **Files and folders:**
  - committed by Aditya when he wants: `data/synth3/questions/`, `data/synth3/sheets/`, `data/synth3/judge-test/`
    (they hold no real-paper text);
  - local only, git-ignored: `data/synth3/results/` (answers, marks, call caches; baseline answers can quote renamed
    real papers), as `data/synth3/built/` and `data/synth3/pools/` already are.
- **The folder set of a domain:** `folders_of(domain)` = `data/synth3/built/<domain>-real` when it exists, else
  `data/synth3/built/<domain>`; each holds `s<seed>/`. Sheets are keyed by the truth hash of `world`, `studies` and
  `facts`, which the template and real folders of one world share (plan 2's "same truth"), so one sheet serves both.
- **Text files:** every read and write passes `encoding="utf-8"`; JSON is written with `jsonio.write_json_atomic`.
- **Named seeds:** `random.Random(f"synth3:review:{domain}:{qid}:{seed}")` for the sheet spot-check draw of one
  (folder, question), `random.Random(f"synth3:judge-test:{seed}")` for the judge-test sample.
- **Git:** work on the existing branch `synth3-questions` (cut from `synth3-real`). Stage files by name only; never stage
  `backend/agent/tests/test_prompts.py`. Never push or merge. End every commit message with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Tests:** `uv run pytest -q backend/synth3` per synth3 task; `uv run pytest -q backend/webapp` in Task 11; in
  `frontend/`, `npm test` in Task 12; the whole suite `uv run pytest -q` at the end of Tasks 1, 9 and 13 (on
  Windows with the two `--ignore`s from `backend/README.md`; the 10 `agent/tests` import errors are known).

## Review Focus

- **A sheet drafted for an older question or another truth:** after Aditya edits a question's text or a folder is
  rebuilt from a changed world, the old sheet must not be used silently. `stale` names why; the judge skips that
  answer with the reason; the page shows a banner, and saving makes a new unchecked sheet for the current question
  and truth, the old one archived (Task 3, 9 and 11 tests). A question with no sheet at all can be written on the
  page (Task 11 test).
- **A redraft over Aditya's work:** `draft-sheets` run again must never overwrite a `checked` sheet that is not
  stale, even with `--redraft`; it reports it (Task 4 test `test_folder_drafting_keeps_checked_sheets`).
- **One bad model call among thousands:** a call that raises `ModelCallError` makes that item pending (judge) or
  failed (drafter, baseline); the command finishes the rest (Task 4, 6, 7 and 9 tests with a raising fake).
- **The judge or Aditya seeing too much:** the C judge never sees sub-questions, fact lines or the system name
  (also not inside a fixed-kind answer's JSON); the hand-marking API and page never show the judge's ticks, but do
  show the facts the answer used, numbered as the B judge saw them (Task 5, 7, 11 and 12 tests).
- **Name matching in real questions:** "Response rates" (plural), "standard care" (lower case), a question naming
  only the control, or a name inside a longer word. The page shows the scope code found, so a wrong scope is seen
  (Task 2 test `test_named_matches_plural_and_case_but_not_inside_words`).
- **The baseline reading the truth:** the baseline must open only `manifest.json` and `papers/` of a folder, as the
  command does (Task 6 guard test).
- **Ids from the address bar:** an id with spaces, dots or a leading dash, or an unknown seed, in
  `/api/ev/review/...` is a 400 or 404, and the path builder never leaves the data root for `..` (Task 11 tests).

---

### Task 1: The question file and its loader

**Files:**
- Create: `backend/synth3/questions.py`, `backend/synth3/tests/test_questions.py`
- Create: `backend/synth3/tests/fixtures/questions/demo.yaml` (test fixture only)
- Modify: `.gitignore` (add `data/synth3/results/` under the synth3 comment)

**Interfaces:**
- Consumes: `DomainSpec`, `SPECS` (`synth3.spec`); `Strict` (`synth2.recipe`); `jsonio.canonical_bytes`,
  `sha256_hex`.
- Produces: `QUESTIONS = SPECS / "questions"`; `KINDS = ("open", "effect", "best", "consistency", "inventory")`.
- Produces: `Question(Strict)`: `id: str` (`^[a-z0-9][a-z0-9-]{0,39}$`), `question: str`,
  `sub_questions: list[str] = []`, `about: list[str] = []` (names from the spec that set the scope; Task 2),
  `kind: Literal[*KINDS] = "open"` (read by plan 4 only: a fixed kind keeps its rules there; the judge ignores it),
  `notes: str = ""`.
- Produces: `QuestionSet(Strict)`: `domain`, `questions: list[Question]`, `sha256` (of the file, CRLF as LF);
  `QuestionSet.get(qid) -> Question` (`KeyError` names the id).
- Produces: `question_sha256(q: Question) -> str`: sha256 of canonical `{question, sub_questions, about}`. Notes and
  kind are left out, so editing them does not make a sheet stale.
- Produces: `spec_names(spec: DomainSpec) -> list[str]`: every arm label, measure name, condition name, level name
  and setting name.
- Produces: `load_questions(domain: str, spec: DomainSpec, root: Path = QUESTIONS) -> QuestionSet`. Any problem is a
  `ValueError` that names the question id and the field:
  - no file: `"no questions file at <path>; Aditya writes it (see synth3/questions.py)"`;
  - not a mapping; `domain` differs from the argument (`"domain 'law' in the file, expected 'demo'"`); an unknown
    key (Strict, the key named);
  - a bad or repeated id (`"id 'Q 1' ..."`, `"id d01 is used twice"`);
  - an empty question or sub-question (`"d01: question is empty"`, `"d02: sub_questions holds an empty entry"`);
  - an unknown kind (`"d01: kind 'chaining' ..."`);
  - two questions with the same text once case and spaces are folded (`"same question"`);
  - an `about` name the spec does not have (the message lists `spec_names`).

  No upper limit on the count (spec §2: questions can be added later). The module docstring shows the file
  format with one example, so Aditya has it where the error message points.

The fixture (demo spec of `conftest.good()`):

```yaml
domain: demo
questions:
  - id: d01
    question: Does Targeted therapy improve the Response rate compared with Standard care?
  - id: d02
    question: Which treatment is best for Relapse rate, and does it depend on the patients' age?
    sub_questions: [Which studies measured Relapse rate?, Do older and younger patients differ?]
  - id: d03
    question: How well do patients tolerate each treatment?
    about: [Targeted therapy, Combined therapy]
    kind: open
```

- [ ] **Step 1: Write the failing tests.** `FIX = Path(__file__).parent / "fixtures" / "questions"`;
  `write_q(dir, d)` writes `demo.yaml` and returns `dir`.

```python
def test_example_questions_load(SPEC):
    qs = load_questions("demo", SPEC, FIX)
    assert [q.id for q in qs.questions] == ["d01", "d02", "d03"]
    assert len(qs.get("d02").sub_questions) == 2 and qs.get("d01").kind == "open"

@pytest.mark.parametrize("change, words", [
    (lambda d: d["questions"].append(dict(d["questions"][0], question="Other?")), "used twice"),
    (lambda d: d["questions"].append(dict(id="d09", question="  does targeted THERAPY improve the response "
                                                            "rate compared with standard care?")), "same question"),
    (lambda d: d["questions"][0].update(question=" "), "d01: question is empty"),
    (lambda d: d["questions"][1].update(sub_questions=[""]), "d02: sub_questions holds an empty entry"),
    (lambda d: d["questions"][2].update(about=["Aspirin"]), "Aspirin"),
    (lambda d: d.update(domain="law"), "domain 'law'"),
    (lambda d: d["questions"][0].update(id="Q 1"), "id 'Q 1'"),
    (lambda d: d["questions"][0].update(answer="yes"), "answer"),
    (lambda d: d["questions"][0].update(kind="chaining"), "d01: kind 'chaining'"),
])
def test_refuses_bad_question_files(tmp_path, SPEC, change, words):
    d = yaml.safe_load((FIX / "demo.yaml").read_text(encoding="utf-8")); change(d)
    with pytest.raises(ValueError, match=words):
        load_questions("demo", SPEC, write_q(tmp_path, d))

def test_missing_file_says_who_writes_it(tmp_path, SPEC):
    with pytest.raises(ValueError, match="no questions file.*Aditya"):
        load_questions("demo", SPEC, tmp_path)

def test_the_hash_ignores_notes_and_kind():
    q = Question(id="x", question="Q?", sub_questions=["s?"])
    assert question_sha256(q) == question_sha256(q.model_copy(update={"notes": "n", "kind": "best"}))
    assert question_sha256(q) != question_sha256(q.model_copy(update={"sub_questions": ["t?"]}))
```

- [ ] **Step 2: Run the tests to watch them fail.** Run `uv run pytest -q backend/synth3/tests/test_questions.py`.
  Expected: FAIL with `ModuleNotFoundError: synth3.questions`.
- [ ] **Step 3: Implement `questions.py`** and add `data/synth3/results/` to `.gitignore`.
- [ ] **Step 4: Run the tests**, then the whole suite. Check `git check-ignore data/synth3/results/x` prints the
  path. Expected: PASS.
- [ ] **Step 5: Commit** `backend/synth3/questions.py`, `backend/synth3/tests/test_questions.py`,
  `backend/synth3/tests/fixtures/questions/demo.yaml`, `.gitignore`: `synth3: question files and their loader`.

### Task 2: The facts a question needs, found by code

**Files:**
- Create: `backend/synth3/sheetfacts.py`, `backend/synth3/tests/test_sheetfacts.py`
- Create: `backend/synth3/qcli.py`, `backend/synth3/cliargs.py` (`BadArgument`, `_Parser`, `_seeds`, `_spec`
  moved here from `cli.py`, unchanged)
- Modify: `backend/synth3/cli.py` (import those four from `cliargs`; call `add_question_commands(sub)`)
- Modify: `backend/synth3/tests/conftest.py`:
  - fixture `folder(tmp_path, SPEC)`: `build_folder(tmp_path / "f" / "s1", SPEC, approved(SPEC, 1), 40, "table")`,
    returns the folder;
  - helpers `built(tmp_path, SPEC, seed)` (builds `tmp_path / "b" / f"s{seed}"`), `q(text, **kw)` (a
    `Question(id="x", question=text, **kw)`), `label(SPEC, arm_id)`, and `seed_with(SPEC, pred)`: the first seed in
    1..30 whose in-memory `{"world": draw_world(...).json(), "facts": reference_facts(...)}` (studies from
    `draw_supported_studies`) satisfies `pred`, without writing a folder; a seed whose draw raises `ValueError`
    is skipped (the demo spec has `uncovered_rate` 0.4, so such seeds exist).

**Interfaces:**
- Consumes: `Question`, `QuestionSet`, `load_questions`; `Study.parse`; `DomainSpec`.
- Produces: `Folder` (frozen dataclass): `path`, `seed: int` (from `corpus.json` `settings.seed`), `corpus_id`,
  `spec: DomainSpec` (built from `ground_truth.json` `spec`), `truth: dict`.
  `load_folder(path: Path) -> Folder`; `ValueError` when `ground_truth.json` or `corpus.json` is missing.
- Produces: `check_spec(folder: Folder, spec: DomainSpec) -> None`: `ValueError("the folder was built from another
  spec")` when the sha256 values differ (questions are checked against the live spec, facts read from the folder's).
- Produces: `Named(Strict)`: `arms: list[str]` (ids, control included when named), `measures: list[str]`,
  `conditions: list[str]` (a named level names its condition), `settings: list[str]` (names).
- Produces: `named(spec, text: str) -> Named`. Case-insensitive, whole words, an optional plural `s` or `es`
  (`(?<!\w)<name>(?:e?s)?(?!\w)`), ids in spec order.
- Produces: `scope(spec, q: Question) -> Named`: `named` over the `about` names when `about` is set, else over the
  main question only. Sub-questions never set the scope (spec §6: they are not scored, and a sub-question naming
  another measure would add points for it).
- Produces: `FactLine(Strict)`: `id: str`, `text: str`.
- Produces: `relevant_facts(spec, truth: dict, q: Question) -> list[FactLine]`. With `T` = the named treatments (all
  treatments when none is named) and `M` = the named measures (all when none):
  1. `pair:<t>:<m>` for every `t` in `T`, `m` in `M`, in spec order (from `facts.pairs`);
  2. `h2h:<arm>:<against>:<m>` for each `facts.head_to_head` entry with `m` in `M` and both arms in `T` (when two
     or more treatments are named) or one arm in `T` (when one is named) or any (when none is named);
  3. `rank:<m>` for every `m` in `M` when `T` has two or more treatments;
  4. `study:<sid>` for every study when the question names a setting, or names no arm and no measure.
- The line texts use names only (labels, measure names, level names, setting names), never arm, measure or level
  ids; study ids (`S001`) are kept. The wording (exact copy):
  - measure: `<Measure name> (higher is better)` / `(lower is better)`;
  - verdicts: `helps` = `<A> does better than <B>`; `hurts` = `<A> does worse than <B>`; `no_effect` =
    `<A> and <B> show no real difference`; `depends` = `it depends on <condition name>: <level name>: better,
    <level name>: no real difference` (better / worse / no real difference per side); `insufficient` =
    `no study in this folder compares <A> with <B> on <Measure name>`;
  - pair: `<T> against <Control> on <measure>: <verdict>.` then, when there are studies, ` Studies: S003, S010.
    The authors say better in 5, worse in 1, no real difference in 1.`; ` The authors claim more than their numbers
    show in S004.` when `overclaimed_in`; ` Not tested for: <level names>.` when `untested`;
  - h2h: `<A> against <B> on <measure>, compared directly: <verdict>. Studies: S001, S008.`;
  - rank: `<measure>, against <Control>, best first: <T1>, <T2>, <T3>.` plus ` No studies: <T>.` for a treatment
    without studies; no effect sizes (builder's call: a sheet point never asks for a pooled number);
  - study: `S001 <label>, <setting>: compares <arm labels> on <measure names>.`
- Produces: `cant_tell(spec, truth, q) -> list[str] | None`: the in-scope pair ids when every in-scope pair answer is
  `insufficient` and no in-scope h2h entry has studies; else `None`.
- Produces: `truth_sha256(truth: dict) -> str`: sha256 of canonical `{"world", "studies", "facts"}` of the truth.
- Produces: `synth3 questions --domain D [--spec-root S] [--questions-root Q]`: loads and checks the file, prints
  `<n> questions in <path>` and per question `<id>: arms <labels or "all">; measures <names or "all">;
  <k> sub-questions`. Exit 2 with the `ValueError` text on a bad file.

- [ ] **Step 1: Write the failing tests.** `truth(f)` reads `f / "ground_truth.json"`.

```python
def test_named_matches_plural_and_case_but_not_inside_words(SPEC):
    n = named(SPEC, "Is targeted therapy better than standard care for Older patients at the Coastal health service?")
    assert n.arms == ["ctrl", "a"] and n.conditions == ["age"] and n.settings == ["Coastal health service"]
    assert named(SPEC, "Response rates of each arm").measures == ["m1"]
    assert named(SPEC, "Targeted therapyX").arms == []

def test_one_treatment_and_one_measure(folder, SPEC):
    t = truth(folder)
    ids = [f.id for f in relevant_facts(SPEC, t, q("Does Targeted therapy raise the Response rate?"))]
    want = [f"h2h:{h['arm']}:{h['against']}:m1" for h in t["facts"]["head_to_head"]
            if h["measure"] == "m1" and "a" in (h["arm"], h["against"])]
    assert ids == ["pair:a:m1", *want]

def test_sub_questions_set_no_scope(folder, SPEC):
    plain = relevant_facts(SPEC, truth(folder), q("Does Targeted therapy raise the Response rate?"))
    more = relevant_facts(SPEC, truth(folder), q("Does Targeted therapy raise the Response rate?",
                                                 sub_questions=["And the Relapse rate of Combined therapy?"]))
    assert plain == more

def test_naming_nothing_gives_everything(folder, SPEC):
    ids = [f.id for f in relevant_facts(SPEC, truth(folder), q("What do these studies show?"))]
    assert sum(i.startswith("pair:") for i in ids) == 6 and sum(i.startswith("rank:") for i in ids) == 3
    assert sum(i.startswith("study:") for i in ids) == 40

def test_about_overrides_the_text(folder, SPEC):
    ids = [f.id for f in relevant_facts(SPEC, truth(folder), q("How is it tolerated?", about=["Relapse rate"]))]
    assert {i for i in ids if i.startswith("pair:")} == {"pair:a:m2", "pair:b:m2"}

def test_texts_use_names_never_ids(folder, SPEC):
    for line in relevant_facts(SPEC, truth(folder), q("What do these studies show?")):
        words = set(re.findall(r"\w+", line.text))
        assert not words & {"ctrl", "m1", "m2", "m3", "young", "old", "urban", "rural", "early", "late"}

def test_depends_names_the_condition_and_both_sides(tmp_path, SPEC):
    s = seed_with(SPEC, lambda t: any(p["answer"]["verdict"] == "depends" for p in t["facts"]["pairs"]))
    t = truth(built(tmp_path, SPEC, s))
    p = next(p for p in t["facts"]["pairs"] if p["answer"]["verdict"] == "depends")
    line = next(f for f in relevant_facts(SPEC, t, q("all?")) if f.id == f"pair:{p['treatment']}:{p['measure']}")
    cond = next(c for c in SPEC.conditions if c.id == p["answer"]["condition"])
    assert f"depends on {cond.name}" in line.text and all(lv.name in line.text for lv in cond.levels)

def test_an_uncovered_pair_is_cant_tell(tmp_path, SPEC):
    s = seed_with(SPEC, lambda t: t["world"]["uncovered"])
    t = truth(built(tmp_path, SPEC, s)); tr, m = t["world"]["uncovered"][0]
    text = f"Does {label(SPEC, tr)} change the {SPEC.measure(m).name}?"
    assert cant_tell(SPEC, t, q(text)) == [f"pair:{tr}:{m}"]
    assert cant_tell(SPEC, t, q("What do these studies show?")) is None

def test_truth_hash_is_shared_by_template_and_real(tmp_path, SPEC, REAL, pool):
    build_folder(tmp_path / "t", SPEC, approved(SPEC, 1), 40, "table")
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    assert truth_sha256(truth(tmp_path / "t")) == truth_sha256(truth(tmp_path / "r"))

def test_questions_command_prints_the_scope(tmp_path, spec_dir, capsys):
    assert main(["questions", "--domain", "demo", "--spec-root", str(spec_dir), "--questions-root", str(FIX)]) == 0
    out = capsys.readouterr().out
    assert "3 questions" in out and "d01: arms Standard care, Targeted therapy; measures Response rate" in out
```

- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement `sheetfacts.py`, `cliargs.py`, `qcli.py` (the `questions` command) and the hook in
  `cli.py`.** Add the Run line to `backend/README.md`: `uv run synth3 questions --domain D   # check Aditya's
  question file and show what each question is about`.
- [ ] **Step 4: Run the tests**, including the existing `backend/synth3/tests` (the moved helpers keep every old
  command working). Expected: PASS.
- [ ] **Step 5: Commit** the six files and `backend/README.md`: `synth3: the facts a question needs, by code`.

### Task 3: Answer sheets: format, checks, staleness and the review queue

**Files:**
- Create: `backend/synth3/sheets.py`, `backend/synth3/tests/test_sheets.py`

**Interfaces:**
- Consumes: Task 1 and 2.
- Produces: `SHEETS = SPECS / "sheets"`, `RESULTS = SPECS / "results"`, `BUILT = SPECS / "built"`;
  `folders_of(domain: str, built: Path = BUILT) -> Path` (Global Constraints).
- Produces: `MAX_POINTS = 6`, `MAX_POINT_CHARS = 300` (builder's calls),
  `CANT_TELL_POINT = "The answer says that the papers in this folder cannot answer the question."` (exact copy).
- Produces: `Point(Strict)`: `id: str` (`p1`, `p2`, ... in order), `text: str`, `facts: list[str]`.
- Produces: `Sheet(Strict)`: `domain`, `seed: int`, `question_id`, `question_sha256`, `truth_sha256`,
  `cant_tell: bool`, `facts: list[FactLine]` (the lines it was drafted from, shown on the page), `points:
  list[Point]`, `status: Literal["drafted", "checked"]`, `drafted_by: dict` (`{"code": "cant_tell"}` or the model
  record of Task 4), `checked_by: str | None = None`, `checked_at: str | None = None`, `warnings: list[str] = []`.
- Produces: `sheet_path(root, domain, seed, qid) -> Path` = `root / domain / f"s{seed}" / f"{qid}.json"`;
  `save_sheet(root, sheet) -> Path`; `load_sheet(root, domain, seed, qid) -> Sheet | None`;
  `sheet_sha256(sheet) -> str` (canonical JSON).
- Produces: `check_points(points: list[tuple[str, list[str]]], facts: list[FactLine], *, by_model: bool)
  -> list[str]`: problems, each naming the point number: none or more than `MAX_POINTS` points; empty or too long
  text; the same text twice; an unknown fact id (`"point 2: unknown fact pair:zz:m9"`); with `by_model`, a point
  citing no fact, and a digit outside a study id (`S\d{3}`) (`"point 1: holds a number"`: the rule "never a pooled
  number" is checked in code). A person's point may cite no fact and may hold numbers.
- Produces: `coverage_warnings(points, facts) -> list[str]`: `"fact <id> is in no point"` for each uncited `pair:`
  or `h2h:` line only (uncited `rank:` and `study:` lines are normal on a broad question).
- Produces: `make_sheet(folder: Folder, q: Question, points: list[tuple[str, list[str]]], drafted_by: dict)
  -> Sheet` (status `drafted`, warnings from `coverage_warnings`); `cant_tell_sheet(folder, q) -> Sheet | None`
  (one point `CANT_TELL_POINT` citing the `cant_tell` ids, `cant_tell` true, `drafted_by {"code": "cant_tell"}`).
- Produces: `stale(sheet, q: Question, folder: Folder) -> str | None`: `"the question changed after drafting"` or
  `"the folder's truth changed after drafting"`.
- Produces: `check_sheet(sheet, points: list[tuple[str, list[str]]], by: str, now: str) -> Sheet`: Aditya's edit
  of a sheet that is not stale; `ValueError` with the `check_points(by_model=False)` problems; status `checked`,
  `checked_by`, `checked_at`, warnings recomputed; `cant_tell` is true only when the points are exactly
  `[CANT_TELL_POINT]`.
- Produces: `person_sheet(folder, q, points, by: str, now: str, *, checked: bool) -> Sheet`: a sheet Aditya writes,
  built from the current question and truth (`make_sheet` with `drafted_by {"person": by}`), checked with
  `by_model=False`; status `checked` when `checked`, else `drafted`. Used for a missing sheet (`checked=True`) and
  for an edited stale sheet (`checked=False`: the new sheet is keyed to the current hashes and he checks it again).
- Produces: `archive_sheet(root, sheet) -> Path`: moves the current file to `<qid>.stale-<n>.json` beside it (`n`
  the next free number) before a stale sheet is replaced; never deletes.
- Produces: `PLANNED_QUESTIONS = 25`; `review_queue(root, domain, seeds: list[int], qids: list[str], full_seed: int =
  1, rate: float = 20 / (4 * PLANNED_QUESTIONS)) -> list[dict]`: one row per (seed, qid) with `seed`,
  `question_id`, `status` (`missing` / `drafted` / `checked`), `stale` (reason or None, when a sheet exists) and
  `must_check`: `"full"` for every row of `full_seed`; `"sample"` when the named seed of that (folder, question)
  draws below `rate`, so each row's membership never moves when questions are added or sheets appear (about 20 of
  the 100 rows of the other 4 folders at 25 questions); else `None`. Spec §10b: every sheet of one folder per
  domain, plus 20 spot checks (builder's call: the full folder is s1).

- [ ] **Step 1: Write the failing tests:**

```python
def test_cant_tell_sheet_has_the_one_point(tmp_path, SPEC):
    f = load_folder(built(tmp_path, SPEC, seed_with(SPEC, lambda t: t["world"]["uncovered"])))
    tr, m = f.truth["world"]["uncovered"][0]
    s = cant_tell_sheet(f, q(f"Does {label(SPEC, tr)} change the {SPEC.measure(m).name}?"))
    assert s.cant_tell and [p.text for p in s.points] == [CANT_TELL_POINT] and s.drafted_by == {"code": "cant_tell"}

def test_point_checks_name_the_problem():
    facts = [FactLine(id="pair:a:m1", text="x")]
    assert any("at most 6" in p for p in check_points([("t%d" % i, ["pair:a:m1"]) for i in range(7)], facts, by_model=True))
    assert check_points([("t", ["pair:zz:m9"])], facts, by_model=True) == ["point 1: unknown fact pair:zz:m9"]
    assert check_points([("t", [])], facts, by_model=True) and not check_points([("t", [])], facts, by_model=False)
    assert check_points([("Up by 12% in S004.", ["pair:a:m1"])], facts, by_model=True) == ["point 1: holds a number"]
    assert not check_points([("Better in S004.", ["pair:a:m1"])], facts, by_model=True)

def test_only_pair_and_head_to_head_lines_warn():
    facts = [FactLine(id="pair:a:m1", text="x"), FactLine(id="rank:m1", text="y"), FactLine(id="study:S001", text="z")]
    assert coverage_warnings([], facts) == ["fact pair:a:m1 is in no point"]

def test_a_sheet_goes_stale_when_the_question_or_truth_changes(folder, SPEC, tmp_path):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    s = make_sheet(f, qq, [("Targeted therapy does better.", ["pair:a:m1"])], {"model": "fake"})
    save_sheet(tmp_path / "sh", s)
    assert load_sheet(tmp_path / "sh", "demo", 1, "x") == s and stale(s, qq, f) is None
    assert stale(s, qq.model_copy(update={"notes": "n"}), f) is None
    assert "question changed" in stale(s, qq.model_copy(update={"question": "Other?"}), f)
    other = load_folder(built(tmp_path, SPEC, 2))
    assert "truth changed" in stale(s, qq, other)

def test_checking_records_who_and_drops_cant_tell(folder):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    s = make_sheet(f, qq, [("A.", ["pair:a:m1"])], {"model": "fake"})
    done = check_sheet(s, [("Targeted therapy does better than Standard care.", [])], "aditya", "2026-11-18T10:00:00Z")
    assert done.status == "checked" and done.checked_by == "aditya" and done.points[0].id == "p1"
    with pytest.raises(ValueError, match="point 1"):
        check_sheet(s, [("", [])], "aditya", "t")

def test_a_person_sheet_replaces_a_stale_one_unchecked(folder, tmp_path):
    f = load_folder(folder); old = q("Does Targeted therapy raise the Response rate?")
    s = make_sheet(f, old, [("A.", ["pair:a:m1"])], {"model": "fake"}); save_sheet(tmp_path / "sh", s)
    new = old.model_copy(update={"question": "Does Targeted therapy change the Response rate?"})
    archived = archive_sheet(tmp_path / "sh", s)
    fresh = person_sheet(f, new, [("Targeted therapy does better.", [])], "aditya", "t", checked=False)
    assert archived.name == "x.stale-1.json" and archived.is_file()
    assert fresh.status == "drafted" and stale(fresh, new, f) is None and fresh.drafted_by == {"person": "aditya"}
    assert person_sheet(f, new, [("B.", [])], "aditya", "t", checked=True).status == "checked"

def test_review_queue_full_folder_and_a_sample_that_never_moves(tmp_path):
    seeds, qids = [1, 2, 3, 4, 5], ["d01", "d02", "d03"]
    rows = review_queue(tmp_path, "demo", seeds, qids, rate=0.3)
    assert {(r["seed"], r["must_check"]) for r in rows if r["seed"] == 1} == {(1, "full")}
    picked = {(r["seed"], r["question_id"]) for r in rows if r["must_check"] == "sample"}
    more = review_queue(tmp_path, "demo", seeds, [*qids, "d04"], rate=0.3)
    assert picked == {(r["seed"], r["question_id"]) for r in more if r["must_check"] == "sample"
                      and r["question_id"] != "d04"}
    assert all(r["must_check"] == "sample" for r in review_queue(tmp_path, "demo", seeds, qids, rate=1.0)
               if r["seed"] != 1)
    assert all(r["status"] == "missing" for r in rows)
```

- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement `sheets.py`.** `make_sheet` does not check the points (its callers do: the drafter
  with `by_model=True`, `check_sheet` with `by_model=False`).
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: checklist answer sheets, staleness and the review queue`.

### Task 4: The sheet drafter (model behind the cluster setup, tested with fakes)

**Files:**
- Create: `backend/synth3/asking.py`, `backend/synth3/tests/test_asking.py` (the one checked-call helper the
  drafter and the judge share)
- Create: `backend/synth3/drafter.py`, `backend/synth3/prompts/sheet-v1.txt`, `backend/synth3/tests/test_drafter.py`
- Create: `backend/synth3/tests/fakes.py`, the fake models every later synth3 test uses:
  - `scripted(*replies)`: a pydantic-ai `FunctionModel` (`model_name="fake"`) that returns the replies in order as
    native JSON text and keeps every user prompt it saw in `.prompts` (as `test_reader.py` does);
  - `boom()`: a model that counts its calls in `.calls` and raises; tests assert `model.calls == 0` (an assert
    inside the model would be swallowed into a `ModelCallError`, then into "pending");
  - `failing()`: a model that always returns text that is not JSON, so `ask_sync` raises `ModelCallError`;
  - `answering(fn)`: a model whose reply is `fn(user_prompt)` (for commands and replies built from the input).

  All fakes have `model_name="fake"`, so they share cache keys the way one real alias does.
- Modify: `backend/synth3/qcli.py` (command `draft-sheets`), `backend/README.md` (one Run line)

**Interfaces:**
- Consumes: Tasks 1-3; `modelcall` (`ask_sync`, `load_prompt`, `JsonlCache`, `default_key`, `CallSettings`,
  `model_name`, `ModelCallError`).
- Produces in `asking.py`: `MAX_REPAIRS = 1`; `repair_input(first: str, rejected: BaseModel, problems: list[str])
  -> str` (the task input, the rejected reply as JSON, then the problems one per line under `Fix only these
  problems:`); `ask_checked(prompt_path, output_type, user: str, check: Callable[[BaseModel], list[str]], model,
  cache: JsonlCache, settings: CallSettings, *, fresh: str | None = None) -> dict`: one call, `check`, at most
  `MAX_REPAIRS` repair calls; a `ModelCallError` ends the attempts with its redacted message as a problem
  (`"model call failed: ..."`). Returns `{"reply": the accepted reply or None, "problems", "calls",
  "served_models", "prompt_sha256"}`. `fresh`, when set, is added to every cache key (`default_key(...) | {"fresh":
  fresh}`), so the calls are made again instead of read from the cache.
- Produces: `DRAFTER_ALIAS = "orch-model"`; `PROMPT = .../prompts/sheet-v1.txt`;
  `SETTINGS = CallSettings(max_tokens=2048)`.
- Produces: `DraftPoint(Strict)`: `text: str`, `facts: list[str]`; `DraftSheet(Strict)`: `points: list[DraftPoint]`.
- Produces: `drafter_input(q: Question, facts: list[FactLine]) -> str`: `Question: <main question>\n\nFacts:\n<id>:
  <text>\n...`. Sub-questions are left out (the simpler option of the I1 ruling: a sheet point can then never come
  from a sub-question).
- Produces: `draft_sheet(folder: Folder, q: Question, model, cache: JsonlCache, *, fresh: str | None = None)
  -> Sheet`. A can't-tell question gets `cant_tell_sheet` with no call. Otherwise `ask_checked` with
  `check_points(by_model=True)`; no accepted reply: `ValueError("<qid> s<seed>: <problems>")` (call failures
  included). `drafted_by` = `{"model": model_name(model), "served_model", "prompt_sha256", "attempts"}`.
- Produces: `draft_folder_sheets(folder: Folder, qs: QuestionSet, model, cache: JsonlCache, root: Path, *,
  redraft: set[str] = frozenset(), now: str) -> dict`: for each question:
  - a `checked` sheet that is not stale is kept, also when its id is in `redraft` (listed under `kept_checked`);
  - a stale `checked` sheet is kept and listed under `stale_checked` (Aditya fixes it on the page), unless its id
    is in `redraft`: then it is archived (`archive_sheet`) and drafted again;
  - a `drafted` sheet that is not stale is kept unless its id is in `redraft`;
  - otherwise (none, stale drafted, or redraft) it is drafted and saved; for an id in `redraft` with
    `fresh=now`, so the cache is not read (at temperature 0 the reply may still repeat; then Aditya writes the
    sheet on the page).
  One failure does not stop the others. Returns `{"drafted", "cant_tell", "kept", "kept_checked": [qid],
  "stale_checked": [qid], "failed": {qid: problem}}`.
- Produces: `synth3 draft-sheets --domain D [--folders F] [--seeds 1,2,3,4,5] [--model orch-model]
  [--redraft QID[,QID]] [--sheets S] [--questions-root Q] [--spec-root S] [--results R]`. Folders default
  `folders_of(domain)`; it runs `check_spec` per folder first; cache `R/<domain>/drafter-calls.jsonl`. Prints per
  seed `s<n>: drafted <a> (can't tell <b>), kept <c>, failed <d>`, then each failure and each stale checked sheet.
  Exit 1 when anything failed.
- Prompt `sheet-v1.txt` (task first): write the checklist of key points a right answer to the question must make
  for this folder, using only the facts listed; each point is one checkable statement in plain words that names
  treatments, measures and groups by name, cites the fact ids it rests on, and holds no number (study ids aside).
  Inputs, output fields, acceptance rules (1 to 6 points; every fact id must be one listed; a "no study compares"
  fact becomes a point saying the papers cannot tell that part). Three examples, with the invented names of the
  Global Constraints:
  - normal: `pair:k:yield` says Method K does worse than Usual method on Yield, 5 studies → one point "Method K
    gives a lower Yield than the Usual method." citing the pair;
  - confusing: `pair:p:errors` on Error count (lower is better) depends on batch size (Small batches: better,
    Large batches: no real difference), with an overclaim → "Method P gives fewer errors than the Usual method in
    Small batches." and "In Large batches Method P and the Usual method show no real difference." and "Some
    authors claim more than their numbers show.";
  - missing: a question about Yield and Error count where `pair:k:errors` has no study and `pair:k:yield` shows no
    real difference → "Method K and the Usual method show no real difference in Yield." and "No study in these
    papers compares Method K with the Usual method on Error count, so that part cannot be answered."

- [ ] **Step 1: Write the failing tests** (with `fakes.py`). In `test_asking.py`, with a tiny `Reply(Strict)`
  (`word: str`) and `check = lambda r: [] if r.word == "ok" else ["word is not ok"]`:

```python
def test_a_failed_check_gets_one_repair_with_the_input_and_the_problem(tmp_path):
    model = scripted(Reply(word="no"), Reply(word="ok"))
    out = ask_checked(PROMPT, Reply, "the task input", check, model, JsonlCache(tmp_path / "c"), SETTINGS)
    assert out["reply"].word == "ok" and out["calls"] == 2
    assert "the task input" in model.prompts[1] and "word is not ok" in model.prompts[1]

def test_a_raising_call_is_a_problem_not_a_crash(tmp_path):
    out = ask_checked(PROMPT, Reply, "x", check, failing(), JsonlCache(tmp_path / "c"), SETTINGS)
    assert out["reply"] is None and out["problems"][0].startswith("model call failed")

def test_fresh_skips_the_cache(tmp_path):
    c = JsonlCache(tmp_path / "c"); first = scripted(Reply(word="ok")); again = scripted(Reply(word="ok"))
    ask_checked(PROMPT, Reply, "x", check, first, c, SETTINGS)
    ask_checked(PROMPT, Reply, "x", check, again, c, SETTINGS)
    assert len(again.prompts) == 0
    ask_checked(PROMPT, Reply, "x", check, again, c, SETTINGS, fresh="t1")
    assert len(again.prompts) == 1
```

  In `test_drafter.py`:

```python
def test_a_good_draft_becomes_a_sheet(folder, tmp_path):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    s = draft_sheet(f, qq, scripted(DraftSheet(points=[DraftPoint(text="Targeted therapy does better.",
                                                                  facts=["pair:a:m1"])])), JsonlCache(tmp_path / "c"))
    assert [p.id for p in s.points] == ["p1"] and s.status == "drafted" and s.drafted_by["attempts"] == 1

def test_cant_tell_needs_no_model_call(tmp_path, SPEC):
    f = load_folder(built(tmp_path, SPEC, seed_with(SPEC, lambda t: t["world"]["uncovered"])))
    tr, m = f.truth["world"]["uncovered"][0]
    model = boom()
    s = draft_sheet(f, q(f"Does {label(SPEC, tr)} change the {SPEC.measure(m).name}?"), model, JsonlCache(tmp_path / "c"))
    assert s.cant_tell and model.calls == 0

def test_a_bad_draft_gets_one_repair_with_its_problems(folder, tmp_path):
    bad = DraftSheet(points=[DraftPoint(text="x", facts=["pair:zz:m9"])])
    good = DraftSheet(points=[DraftPoint(text="Targeted therapy does better.", facts=["pair:a:m1"])])
    model = scripted(bad, good)
    s = draft_sheet(load_folder(folder), q("Does Targeted therapy raise the Response rate?"), model, JsonlCache(tmp_path / "c"))
    assert s.drafted_by["attempts"] == 2 and "unknown fact pair:zz:m9" in model.prompts[1]

def test_two_bad_drafts_fail_with_the_problems(folder, tmp_path):
    bad = DraftSheet(points=[])
    with pytest.raises(ValueError, match="x s1: .*point"):
        draft_sheet(load_folder(folder), q("Does Targeted therapy raise the Response rate?"), scripted(bad, bad),
                    JsonlCache(tmp_path / "c"))

def test_the_input_holds_the_fact_lines_but_no_sub_question(folder):
    f = load_folder(folder); qq = q("Which is best for Relapse rate?", sub_questions=["Do older patients differ?"])
    text = drafter_input(qq, relevant_facts(f.spec, f.truth, qq))
    assert "Do older patients differ?" not in text and "pair:a:m2:" in text and "rank:m2:" in text

def test_a_failing_call_is_a_failure_and_the_folder_goes_on(folder, tmp_path, SPEC):
    out = draft_folder_sheets(load_folder(folder), load_questions("demo", SPEC, FIX), failing(),
                              JsonlCache(tmp_path / "c"), tmp_path / "sh", now="t")
    assert set(out["failed"]) | set_of_cant_tell(out) == {"d01", "d02", "d03"}
    assert all("model call failed" in why for why in out["failed"].values())

def test_folder_drafting_keeps_checked_sheets(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); root = tmp_path / "sh"
    for qq in qs.questions:
        save_sheet(root, check_sheet(make_sheet(f, qq, [("Kept.", [])], {"model": "x"}), [("Kept.", [])], "aditya", "t"))
    edited = qs.get("d01").model_copy(update={"question": "Changed?"})
    qs2 = qs.model_copy(update={"questions": [edited, *qs.questions[1:]]})
    model = boom()
    out = draft_folder_sheets(f, qs2, model, JsonlCache(tmp_path / "c"), root, redraft={"d02"}, now="t")
    assert out["stale_checked"] == ["d01"] and out["kept_checked"] == ["d02"] and model.calls == 0
    assert load_sheet(root, "demo", 1, "d01").points[0].text == "Kept."

def test_redraft_calls_again_after_two_cached_failures(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); c = JsonlCache(tmp_path / "c")
    bad = DraftSheet(points=[])
    first = scripted(*[bad] * 6)
    assert "d01" in draft_folder_sheets(f, qs, first, c, tmp_path / "sh", now="t0")["failed"]
    again = answering(lambda p: DraftSheet(points=[DraftPoint(text="A point.", facts=[first_fact(p)])]))
    out = draft_folder_sheets(f, qs, again, c, tmp_path / "sh", redraft={"d01"}, now="t1")
    assert "d01" not in out["failed"] and load_sheet(tmp_path / "sh", "demo", 1, "d01") is not None
```

  `set_of_cant_tell(out)` is the questions that got a code sheet (none or more, by seed); `first_fact(p)` returns
  the first fact id listed in a drafter input.

  Plus `test_draft_sheets_by_command`: monkeypatch `modelcall.gateway.openai_model` to return
  `answering(lambda p: DraftSheet(points=[DraftPoint(text="A point.", facts=[first_fact(p)])]))`;
  run `main(["draft-sheets", ...])` on `tmp_path / "f"` (the `folder` fixture's parent) with `--seeds 1` and the
  fixture questions; expect exit 0, three sheet files and `s1: drafted 3` in the output.
- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement `asking.py`, `drafter.py`, the prompt and the command**; Run line:
  `uv run synth3 draft-sheets --domain D [--redraft QID]   # orch-model drafts the answer sheets (cluster);
  can't-tell sheets by code; --redraft skips the call cache for those questions`.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: the answer-sheet drafter, tested with fake models`.

### Task 5: Answers in one shape; engine runs collected

**Files:**
- Create: `backend/synth3/answers.py`, `backend/synth3/tests/test_answers.py`
- Modify: `backend/synth3/qcli.py` (command `collect`)

**Interfaces:**
- Consumes: `evidence.rundir.RunDir` (`items()`, `json("answer.json")`, `json("run.json")`), `PaperIndex.of_corpus`;
  `Folder`, `Question`, `question_sha256`.
- Produces: `SYSTEM_ID = r"^[a-z0-9][a-z0-9-]*$"`; `MAX_TEXT = 12_000` characters (builder's call).
- Produces: `PulledFact(Strict)`: `paper: str`, `kind: str` (the evidence type, or `passage`), `fields: dict`,
  `quote: str`, `start: int | None`, `end: int | None`.
- Produces: `AnswerRecord(Strict)`: `domain`, `seed: int`, `corpus_id`, `question_id`, `question_sha256`,
  `system: str`, `text: str`, `text_cut: bool`, `cited: list[str]`, `facts: list[PulledFact] | None` (`None`: the
  system pulls no per-paper facts), `passages: list[PulledFact]` (the baseline's cited passages), `source: str`.
- Produces: `answer_text(answer: dict) -> tuple[str, bool]`: `answer["answer_text"]` when it is a non-empty string
  (plan 4's model-written answers write this field), else the canonical JSON of the answer (the fixed kinds'
  answers) without `HIDDEN = ("system", "question", "question_id", "protocol", "corpus_id", "run_id", "retrieved",
  "settings", "citations", "dropped_citations")` and every key ending in `_call`, at any depth: the judge must not
  learn which system answered (the engine writes `"system": "evidence-engine"`, `evidence/synthesis.py`). Cut at
  `MAX_TEXT`, the flag says so.
- Produces: `cited_papers(text: str, ids: list[str]) -> list[str]`: the folder's paper ids named in the text
  (`\bS\d{3}\b`), in first-seen order, unknown ids dropped.
- Produces: `from_engine_run(run: Path, folder: Folder, q: Question, system: str = "engine") -> AnswerRecord`.
  Each item is one `PulledFact`: its paper by `PaperIndex.of_corpus(folder.path)` (an item of a paper the folder
  lacks is a `ValueError`), `kind` its evidence type, `fields` its fields, `quote`/`start`/`end` from its first
  span's selector (`exact`, `start`, `end`). Refuses a run without `answer.json`, and a run whose `run.json` names a
  corpus id other than `folder.corpus_id`.
- Produces: `from_rag_answer(answer: dict, folder: Folder, q: Question, source: str) -> AnswerRecord`: system
  `rag-baseline`, `text` from `answer_text`, `cited` the documents of `answer["citations"]`, `passages` the cited
  spans cut from the paper text (kind `passage`), `facts=None`.
- Produces: `answer_path(results, domain, seed, system, qid) -> Path` =
  `results / domain / f"s{seed}" / system / f"{qid}.answer.json"`; `save_answer(results, rec) -> Path`;
  `load_answer(path) -> AnswerRecord`; `load_answers(results, domain) -> list[AnswerRecord]` (sorted by seed,
  system, question id); `item_id(rec) -> str` = `"<domain>/s<seed>/<system>/<qid>"`.
- Produces: `synth3 collect --domain D --seed N --question QID --run RUN [--system engine] [--folders F]
  [--questions-root Q] [--spec-root S] [--results R]`; prints the written path. This is how plan 4's runs and
  the existing fixed kinds reach the judge.

- [ ] **Step 1: Write the failing tests.** `fake_run(dir, folder, answer: dict, spans: list[tuple[str, int, int]])`
  writes `answer.json`, `run.json` (`{"corpus_id": ...}`: the engine writes it top-level, `evidence/engine.py`) and
  `evidence.jsonl` with one `measurement` `Item` per span, whose selector cuts `exact` from the paper.

```python
def test_engine_run_becomes_a_record(folder, tmp_path):
    f = load_folder(folder); text = (folder / "papers" / "S001.md").read_text(encoding="utf-8")
    run = fake_run(tmp_path / "run", f, {"label": "supported", "studies": [{"document": "S001"}]},
                   [("S001", 100, 120), ("S002", 50, 60)])
    rec = from_engine_run(run, f, q("Q?"))
    assert [x.paper for x in rec.facts] == ["S001", "S002"] and rec.facts[0].quote == text[100:120]
    assert '"label":"supported"' in rec.text and rec.cited == ["S001"] and not rec.text_cut

def test_a_model_written_answer_is_used_as_text(folder, tmp_path):
    f = load_folder(folder)
    run = fake_run(tmp_path / "run", f, {"answer_text": "Targeted therapy helps (S003).", "label": "x"}, [])
    assert from_engine_run(run, f, q("Q?")).text == "Targeted therapy helps (S003)."

def test_a_fixed_kind_answer_never_names_its_system():
    text, _ = answer_text({"system": "evidence-engine", "kind": "best", "winner": "Method K", "protocol": "p.yaml",
                           "question_id": "q1", "studies": [{"document": "S001", "system": "evidence-engine"}],
                           "model_call": {"model": "orch-model"}})
    assert "evidence-engine" not in text and "orch-model" not in text and "p.yaml" not in text
    assert '"winner":"Method K"' in text

def test_long_text_is_cut_and_flagged():
    text, cut = answer_text({"answer_text": "a" * (MAX_TEXT + 5)})
    assert cut and len(text) <= MAX_TEXT + 40

def test_a_run_on_another_corpus_is_refused(folder, tmp_path):
    f = load_folder(folder); run = fake_run(tmp_path / "run", f, {"label": "x"}, [])
    (run / "run.json").write_text(json.dumps({"corpus_id": "other"}), encoding="utf-8")
    with pytest.raises(ValueError, match="corpus"):
        from_engine_run(run, f, q("Q?"))

def test_rag_answer_keeps_the_cited_passages(folder):
    f = load_folder(folder); text = (folder / "papers" / "S002.md").read_text(encoding="utf-8")
    rec = from_rag_answer({"answer_text": "See S002.", "citations": [{"document": "S002", "start": 10, "end": 90}]},
                          f, q("Q?"), "a.json")
    assert rec.facts is None and rec.passages[0].quote == text[10:90] and rec.cited == ["S002"]
```

  Plus `test_collect_by_command` (writes `answer_path(...)`, prints it).
- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement `answers.py` and the command.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: answers in one shape, engine runs collected`.

### Task 6: The baseline on every question

**Files:**
- Create: `backend/synth3/baseline.py`, `backend/synth3/tests/test_baseline.py`
- Modify: `backend/synth3/qcli.py` (command `baseline`), `backend/README.md` (one Run line)

**Interfaces:**
- Consumes: `evaluation.baselines.rag.rag_baseline` (unchanged); Task 5.
- Produces: `BASELINE = "rag-baseline"`.
- Produces: `baseline_folder(folder: Folder, qs: QuestionSet, model, model_id: str, cache: JsonlCache,
  results: Path) -> dict`. For each question: `rag_baseline(folder.path, model=model, model_id=model_id,
  question=q.question, cache=cache)` with the command's defaults (global retrieval, k 8; builder's call: the
  standard RAG setup the command already records). It writes the raw answer to
  `results/<domain>/s<seed>/rag-baseline/<qid>/answer.json` and `from_rag_answer` through `save_answer`.
  Sub-questions are not sent (builder's call: they are planning input for the system, plan 4). The mapping call's
  label stays in the raw `answer.json` and is not scored. A record with the same `question_sha256` is skipped; a
  failed question (a `ModelCallError` or a `ValueError` from `rag_baseline`) is listed with its redacted reason and
  does not stop the others. Returns `{"answered", "skipped", "failed": {qid: reason}}`.
- Produces: `synth3 baseline --domain D [--folders F] [--seeds 1,2,3,4,5] [--model orch-model] [--results R]
  [--questions-root Q] [--spec-root S]`; the model is `openai_model(alias)` and `model_id =
  modelcall.model_identity([model])` (the pinned weights, as `evaluate`'s private `_model` records them); cache
  `R/<domain>/rag-baseline-calls.jsonl`; prints per seed `s<n>: answered <a>, skipped <b>, failed <c>`; exit 1 when
  anything failed. Each question costs two orch calls (the answer and the mapping call, `rag.py:226`), about 1000
  per domain.

- [ ] **Step 1: Write the failing tests** (`scripted` and `guard_corpus` from `evaluation.tests.test_rag` and
  `evaluation.tests.helpers`):

```python
def test_every_question_gets_a_baseline_record(folder, tmp_path, SPEC, monkeypatch):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX)   # the truth is read before the guard
    attempts = guard_corpus(monkeypatch, folder)
    out = baseline_folder(f, qs, scripted(text="Targeted therapy helps (S001).").model(), "fake",
                          JsonlCache(tmp_path / "c.jsonl"), tmp_path / "res")
    assert out == {"answered": 3, "skipped": 0, "failed": {}} and attempts == []
    recs = load_answers(tmp_path / "res", "demo")
    assert [r.question_id for r in recs] == ["d01", "d02", "d03"] and all(r.system == "rag-baseline" for r in recs)
    assert recs[0].text == "Targeted therapy helps (S001)." and recs[0].passages and recs[0].facts is None

def test_a_second_run_skips_answered_questions(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); c = JsonlCache(tmp_path / "c.jsonl")
    baseline_folder(f, qs, scripted().model(), "fake", c, tmp_path / "res")
    assert baseline_folder(f, qs, scripted().model(), "fake", c, tmp_path / "res")["skipped"] == 3

def test_a_failing_call_is_listed_and_the_rest_go_on(folder, tmp_path, SPEC):
    out = baseline_folder(load_folder(folder), load_questions("demo", SPEC, FIX), failing(), "fake",
                          JsonlCache(tmp_path / "c.jsonl"), tmp_path / "res")
    assert set(out["failed"]) == {"d01", "d02", "d03"} and out["answered"] == 0
```

  Plus `test_baseline_by_command`: monkeypatch `modelcall.gateway.openai_model` to return
  `scripted(text="An answer.").model()`, run `main(["baseline", ...])` with `--seeds 1`, expect exit 0, three
  records and `s1: answered 3, skipped 0, failed 0` in the output.
- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement**; Run line: `uv run synth3 baseline --domain D   # evaluate rag-baseline on every
  question and folder (orch-model, cluster; 2 calls per question and folder)`.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: the RAG baseline on every question`.

### Task 7: The judge, score C (the checklist)

**Files:**
- Create: `backend/synth3/judge.py`, `backend/synth3/prompts/judge-c-v1.txt`, `backend/synth3/tests/test_judge_c.py`
- Modify: `backend/synth3/tests/fakes.py` (add `rec(text, **kw)`)

**Interfaces:**
- Consumes: `Sheet`, `AnswerRecord`, `Question`; `asking.ask_checked` (Task 4: repairs and call failures are
  handled there, for A, B and C alike).
- Produces: `JUDGE_ALIAS = "sub-model-1"`, `SETTINGS = CallSettings(max_tokens=4096)`.
- Produces: `squash(text) -> str` (spaces folded, lower case).
- Produces: `Tick(Strict)`: `point: str`, `met: bool`, `quote: str | None`, `reason: str`; `Ticks(Strict)`:
  `ticks: list[Tick]`.
- Produces: `c_input(q: Question, sheet: Sheet, text: str) -> str`: `Question: <main question>\n\nPoints:\np1:
  <text>\n...\n\nAnswer:\n<text>`. Never the sub-questions, the fact lines or the system name.
- Produces: `check_ticks(t: Ticks, sheet, text) -> list[str]`: every point exactly once (`"p2 missing"`,
  `"p2 twice"`, `"unknown point p9"`); a met point has a quote found in the answer by `squash`
  (`"p1: quote not in the answer"`).
- Produces: `score_c(q, sheet, rec: AnswerRecord, model, cache) -> dict`: `{"score", "ticks", "missed", "status":
  "ok" | "pending", "problems", "calls", "prompt_sha256", "served_models"}`. An empty text is `score` 0 with every
  point missed and no call. Pending (checks still failing, or the call failed): `score` None.
- Prompt `judge-c-v1.txt` (task first): for each point, say whether the answer makes it, with a short verbatim quote
  from the answer when it does. A point is met only when the answer states it with the same direction and the same
  group split; a vague or hedged statement that does not commit is not met. Examples (invented names, Global
  Constraints):
  - normal: point "Method K gives a lower Yield than the Usual method" and the answer "Yield fell with Method K
    compared with the usual method" → met, with the quote;
  - confusing: point "Method P gives fewer errors than the Usual method" (Error count: lower is better) and the
    answer "Method P reduced the error count" → met; point "It depends on batch size: better in Small batches, no
    real difference in Large batches" and the answer "Method P helps" → not met (the split is missing);
  - missing: the can't-tell point and the answer "No study in these papers compares Method K with the usual method
    on error count" → met; point "Method K and the Usual method show no real difference in Yield" and an answer
    that never mentions Yield → not met, quote null.

- [ ] **Step 1: Write the failing tests.** `sheet3()` makes a 3-point drafted sheet; `rec(text, **kw)` (added to
  `fakes.py`, used again in Task 8) makes an engine `AnswerRecord` for the `folder` fixture with `facts=[]` unless
  given.

```python
def test_two_of_three_points_give_two_thirds(tmp_path):
    t = "Targeted therapy does better. Combined therapy is no different."
    out = score_c(q("Q?"), sheet3(), rec(t), scripted(Ticks(ticks=[
        Tick(point="p1", met=True, quote="Targeted therapy does better", reason=""),
        Tick(point="p2", met=True, quote="combined therapy is no different", reason=""),
        Tick(point="p3", met=False, quote=None, reason="")])), JsonlCache(tmp_path / "c"))
    assert out["score"] == pytest.approx(2 / 3) and out["missed"] == ["p3"] and out["status"] == "ok"

def test_a_quote_not_in_the_answer_gets_one_repair(tmp_path):
    bad = Ticks(ticks=[Tick(point=p, met=True, quote="never said", reason="") for p in ("p1", "p2", "p3")])
    good = Ticks(ticks=[Tick(point=p, met=False, quote=None, reason="") for p in ("p1", "p2", "p3")])
    model = scripted(bad, good)
    out = score_c(q("Q?"), sheet3(), rec("Something else."), model, JsonlCache(tmp_path / "c"))
    assert out["score"] == 0 and out["calls"] == 2 and "quote not in the answer" in model.prompts[1]

def test_a_reply_that_stays_bad_is_pending(tmp_path):
    bad = Ticks(ticks=[Tick(point="p1", met=False, quote=None, reason="")])
    out = score_c(q("Q?"), sheet3(), rec("x"), scripted(bad, bad), JsonlCache(tmp_path / "c"))
    assert out["status"] == "pending" and out["score"] is None and "p2 missing" in out["problems"]

def test_a_failing_call_is_pending(tmp_path):
    out = score_c(q("Q?"), sheet3(), rec("x"), failing(), JsonlCache(tmp_path / "c"))
    assert out["status"] == "pending" and out["score"] is None and "model call failed" in out["problems"][0]

def test_an_empty_answer_scores_zero_without_a_call(tmp_path):
    model = boom()
    out = score_c(q("Q?"), sheet3(), rec(" "), model, JsonlCache(tmp_path / "c"))
    assert out["score"] == 0 and out["calls"] == 0 and model.calls == 0

def test_the_judge_sees_no_sub_question_no_fact_and_no_system():
    text = c_input(q("Q?", sub_questions=["Secret sub-question?"]), sheet3(), "An answer.")
    assert "Secret sub-question?" not in text and "pair:" not in text and "rag-baseline" not in text
```

- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement the C part of `judge.py` and the prompt.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** (`judge.py`, the prompt, `test_judge_c.py`, `fakes.py`): `synth3: the judge's checklist
  score C, tested with fake models`.

### Task 8: The judge, scores A and B

**Files:**
- Modify: `backend/synth3/judge.py`
- Create: `backend/synth3/prompts/judge-a-v1.txt`, `backend/synth3/prompts/judge-b-v1.txt`,
  `backend/synth3/tests/test_judge_ab.py`

**Interfaces:**
- Consumes: `scope`, `Folder`, `Study.parse`, `ask_checked`.
- Produces: `MAX_FACTS = 150` (B's input, builder's call), `MAX_PER_PAPER = 60` (A's pulled facts per paper).
- Produces: `PlantedFact(Strict)`: `id`, `paper`, `text`, `spans: list[tuple[int, int]]`.
- Produces: `planted_facts(folder: Folder, q: Question) -> dict[str, list[PlantedFact]]` (by paper, in paper order).
  With `scope` giving the treatments `T` (all when none named) plus the control, and the measures `M`:
  - in each cell on a measure in `M`, the result row of every arm in `T`, and the control's row of a cell that
    has one of them: id `<sid>.c<i>.<arm>`, text
    `<Arm label>, <Measure name>, <level names of the cell>: <k> of <n> (<k/n as a percentage, 1 decimal>%)`
    (count; code computes the percentage so the judge never does a sum, `docs/prompt-writing.md`) or `mean <mean>,
    SD <sd>, n <n>` (value, with the measure's decimals);
  - each claim in scope, that is, on a measure in `M` with both arms in `T` plus the control: id
    `<sid>.claim.<arm>.<against>.<m>`, text `The authors say <Arm> does better than / does worse than / shows no
    real difference from <Against> on <Measure>`;
  - the setting of every paper that has one of the above: id `<sid>.setting`, text `The study ran at <setting>`.
  - `spans`: the placements whose fact id equals the id or starts with `<id>.`.
- Produces: `anchored(planted: dict, facts: list[PulledFact]) -> float | None`: share of planted facts with a span
  that shares a character with a pulled fact's `[start, end)` in the same paper (code only); None when nothing is
  planted.
- Produces: `Mark(Strict)`: `fact: str`, `verdict: Literal["found", "wrong", "missing"]`, `pulled: int | None`,
  `reason: str`; `PaperMarks(Strict)`: `marks: list[Mark]`.
- Produces: `a_input(planted: list[PlantedFact], pulled: list[PulledFact]) -> str`: `Planted facts:\n<id>: <text>`
  then `Pulled facts:\n1. <kind> <fields as JSON> quote: "<quote>"` (at most `MAX_PER_PAPER`). One paper only.
- Produces: `check_marks(m: PaperMarks, planted, n_pulled) -> list[str]`: each planted id exactly once; `found` and
  `wrong` cite a pulled number in range; `missing` cites none.
- Produces: `score_a(folder, q, rec, model, cache) -> dict | None`: None when `rec.facts is None` (the baseline).
  Per paper with planted facts: no pulled facts there → all `missing`, no call; else one judged call (a failed call
  makes that paper pending). Returns `{"score": found / total over the papers not pending, "found", "wrong",
  "missing", "total", "anchored", "pending_papers": [sid], "pulled_cut": [sid] (papers with more than
  `MAX_PER_PAPER` pulled facts, whose later facts the judge did not see), "papers": {sid: [mark dicts]}, "calls",
  "prompt_sha256", "served_models"}`; `score` None when every paper is pending or nothing is planted.
- Produces: `ClaimCheck(Strict)`: `claim: str`, `verdict: Literal["supported", "invented", "contradicted"]`,
  `facts: list[int]`, `reason: str`; `ClaimChecks(Strict)`: `claims: list[ClaimCheck]`.
- Produces: `used_facts(rec) -> tuple[list[PulledFact], bool]`: `rec.passages` for a record without facts; else the
  facts of the cited papers (all facts when none is cited); cut at `MAX_FACTS` (the flag says so).
- Produces: `b_input(q, rec, used) -> str`: the main question, the numbered used facts, the answer.
- Produces: `check_claims(c: ClaimChecks, text, n) -> list[str]`: each claim found in the answer by `squash`;
  `supported` and `contradicted` cite at least one fact number in range; `invented` cites none.
- Produces: `score_b(q, rec, model, cache) -> dict`: `{"score": supported / claims (None when no claim or no text),
  "claims", "invented", "contradicted", "facts_cut", "status", "problems", "calls", "prompt_sha256",
  "served_models"}`.
- Prompt `judge-a-v1.txt` (task first): for each planted fact of this paper, say whether a pulled fact states it
  (found), states the same thing with another value or another group (wrong), or none does (missing); cite the
  pulled fact's number. Examples (invented names): normal (a Yield row of Method K in Small batches found, the
  numbers equal); confusing (the same mean but Large batches instead of Small batches → wrong; a pulled fraction
  0.45 where the planted text reads "45 of 100 (45.0%)" → found, as the prompt policy names percentages vs
  fractions); missing (no pulled fact for the authors' claim → missing).
- Prompt `judge-b-v1.txt` (task first): split the answer into its factual claims (each a verbatim span of the
  answer) and mark each as supported by the numbered facts, contradicted by them, or invented (no fact speaks to
  it). Examples (invented names): normal (a claim that Method P gave fewer errors, supported by facts 2 and 3);
  confusing (the right number attached to the wrong method → contradicted, as `docs/prompt-writing.md` says of a
  correct number on the wrong metric); missing (a claim about a measure no fact mentions → invented). A sentence
  saying the papers cannot tell something is not a claim and is not listed (B checks how facts were used; C checks
  whether "cannot tell" was right).

- [ ] **Step 1: Write the failing tests:**

```python
def test_planted_facts_follow_the_scope(folder):
    f = load_folder(folder); got = planted_facts(f, q("Does Targeted therapy raise the Response rate?"))
    rows = [p for ps in got.values() for p in ps if not p.id.endswith(".setting")]
    assert rows and all("Response rate" in p.text and "Combined therapy" not in p.text for p in rows)
    assert all(re.search(r"\d+ of \d+ \(\d+\.\d%\)", p.text) for p in rows if ".claim." not in p.id)
    assert all(p.spans for ps in got.values() for p in ps)
    texts = {p.paper: (folder / "papers" / f"{p.paper}.md").read_text(encoding="utf-8") for ps in got.values() for p in ps}
    assert all(texts[p.paper][a:b] for ps in got.values() for p in ps for a, b in p.spans)

def test_anchored_counts_span_overlap(folder):
    f = load_folder(folder); got = planted_facts(f, q("Does Targeted therapy raise the Response rate?"))
    first = next(iter(got.values()))[0]; a, b = first.spans[0]
    hit = PulledFact(paper=first.paper, kind="measurement", fields={}, quote="", start=a, end=a + 1)
    total = sum(len(v) for v in got.values())
    assert anchored(got, [hit]) == pytest.approx(1 / total)

def test_a_paper_without_pulled_facts_is_missing_without_a_call(folder, tmp_path):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    model = boom()
    out = score_a(f, qq, rec("x", facts=[]), model, JsonlCache(tmp_path / "c"))
    assert model.calls == 0 and out["found"] == 0 and out["missing"] == out["total"] > 0 and out["score"] == 0

def test_a_marks_count_found_and_wrong(folder, tmp_path):
    ...  # one paper with pulled facts; the scripted judge marks its first planted fact found (pulled 1), the
         # second wrong (pulled 2), the rest missing: found == 1, wrong == 1, papers[sid] has every planted id once

def test_a_found_mark_without_a_pulled_number_is_repaired_then_pending(folder, tmp_path):
    ...  # two bad replies: that paper is in pending_papers and left out of the score; with failing() instead,
         # the same paper is pending and the other papers are still marked

def test_too_many_pulled_facts_are_cut_and_said(folder, tmp_path):
    ...  # 61 pulled facts on one paper: a_input lists 60 and the result has that paper in pulled_cut

def test_baseline_has_no_score_a(folder, tmp_path):
    assert score_a(load_folder(folder), q("Q?"), rec("x", facts=None), boom(), JsonlCache(tmp_path / "c")) is None

@pytest.mark.parametrize("prompt", sorted((BACKEND / "synth3" / "prompts").glob("*.txt")))
def test_prompt_examples_use_no_domain_name(prompt):
    names = {n for f in [*SPECS.glob("*.yaml"), *(SPECS / "drafts").glob("*.yaml")]
             for n in spec_names(load_spec(f.stem, f.parent))}
    text = prompt.read_text(encoding="utf-8")
    assert not [n for n in names if re.search(rf"(?i)(?<!\w){re.escape(n)}(?!\w)", text)]

def test_b_counts_supported_claims(tmp_path):
    used = [PulledFact(paper="S001", kind="measurement", fields={"value": 0.5}, quote="50%", start=1, end=4)]
    r = rec("Targeted therapy helps. Combined therapy hurts.", facts=used, cited=["S001"])
    out = score_b(q("Q?"), r, scripted(ClaimChecks(claims=[
        ClaimCheck(claim="Targeted therapy helps", verdict="supported", facts=[1], reason=""),
        ClaimCheck(claim="Combined therapy hurts", verdict="contradicted", facts=[1], reason="")])),
        JsonlCache(tmp_path / "c"))
    assert out["score"] == 0.5 and out["contradicted"] == 1

def test_b_for_the_baseline_reads_its_passages(tmp_path):
    p = PulledFact(paper="S002", kind="passage", fields={}, quote="Relapse fell in older patients.", start=0, end=31)
    r = rec("Relapse fell.", facts=None, passages=[p])
    assert "Relapse fell in older patients." in b_input(q("Q?"), r, used_facts(r)[0])
```

  The `...` tests are written by the builder with the assertions given in their comments. The prompt-name test
  covers all four prompt files (`sheet-v1` too) and, as written, `reader-v1.txt` of plan 2: if `reader-v1.txt`
  fails it, limit the glob to the four new files rather than edit plan 2's prompt.
- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement the A and B parts and the two prompts.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: the judge's scores A and B, tested with fake models`.

### Task 9: `synth3 judge`: marks for every answer

**Files:**
- Create: `backend/synth3/marking.py`, `backend/synth3/tests/test_marking.py`
- Modify: `backend/synth3/qcli.py` (command `judge`), `backend/README.md` (one Run line)

**Interfaces:**
- Consumes: Tasks 3, 5, 7 and 8.
- Produces: `marks_path(results, domain, seed, system, qid) -> Path` (beside the answer: `<qid>.marks.json`).
- Produces: `judge_answer(folder, q, sheet, rec, model, cache) -> dict`: `{"item": item_id(rec), "question_id",
  "seed", "system", "corpus_id", "answer_sha256", "sheet": {"sha256", "status", "cant_tell", "points"}, "A", "B",
  "C", "judge": {"model", "served_models", "prompts": {"a", "b", "c"}}, "calls"}`.
- Produces: `why_not(folder, q, sheet, rec) -> str | None`: `"no sheet"`, the `stale` reason, `"the answer is to
  an older version of the question"` (record `question_sha256` differs), `"the answer is from another folder"`
  (record `corpus_id` differs from the folder's).
- Produces: `judge_domain(domain, folders: Path, seeds, systems: list[str] | None, spec, qs, model, cache,
  sheets_root, results) -> dict`: every saved answer of those seeds and systems; an existing marks file is kept (no
  calls) only when its `answer_sha256`, sheet `sha256` and the three prompt sha256 values all equal the current
  ones; returns `{"judged", "kept", "skipped": {item: reason}, "pending": [item]}` (pending: any of A, B, C
  pending, including a failed model call; the marks file is still written and the next item follows). A pending
  marks file is judged again on the next run.
- Produces: `synth3 judge --domain D [--folders F] [--seeds ...] [--systems engine,rag-baseline] [--model
  sub-model-1] [--sheets S] [--results R] [--questions-root Q] [--spec-root S]`; cache
  `R/<domain>/judge-calls.jsonl`; prints `judged <a>, kept <b>, skipped <c>, pending <d>` and each skip reason.

- [ ] **Step 1: Write the failing tests.** `judge_model()` is `answering(fn)` where `fn` tells the call from its
  user prompt: one with `Points:` (C) gets every point met, quoting the answer's first word; one starting
  `Planted facts:` (A) gets every listed planted id `missing`; any other (B) gets no claims.

```python
def test_one_answer_gets_three_separate_scores(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); qq = qs.get("d01")
    save_sheet(tmp_path / "sh", make_sheet(f, qq, [("Targeted therapy does better.", ["pair:a:m1"])], {"model": "x"}))
    save_answer(tmp_path / "res", engine_rec(f, qq, text="Targeted therapy does better.", facts=[pulled_on("S001")]))
    out = judge_domain("demo", folder.parent, [1], None, SPEC, qs, judge_model(), JsonlCache(tmp_path / "c"),
                       tmp_path / "sh", tmp_path / "res")
    m = json.loads(marks_path(tmp_path / "res", "demo", 1, "engine", "d01").read_text(encoding="utf-8"))
    assert out["judged"] == 1 and m["C"]["score"] == 1.0 and m["A"]["score"] == 0 and m["B"]["score"] is None
    assert set(m["judge"]["prompts"]) == {"a", "b", "c"}

def test_a_stale_sheet_is_skipped_with_its_reason(...):
    ...  # the question text changed after the sheet: skipped[item] == "the question changed after drafting"

def test_a_second_run_makes_no_calls(...):
    ...  # judge_domain twice with the same files: second returns kept == 1 and boom().calls == 0; with a
         # changed prompt sha256 in the marks file, the answer is judged again

def test_an_answer_to_an_older_question_is_skipped(...):
    ...  # record question_sha256 from an older text: skipped reason names the older version

def test_a_failing_judge_leaves_pending_marks_and_goes_on(...):
    ...  # two answers, failing() model: judged == 2, both items in pending, both marks files written
```

  Plus `test_judge_by_command`: monkeypatch `modelcall.gateway.openai_model` to return `judge_model()`, run
  `main(["judge", ...])`, expect exit 0 and `judged 1, kept 0, skipped 0, pending 0`. `engine_rec` and `pulled_on`
  are small helpers in the test file; the `...` tests are written by the builder with the assertions in their
  comments.
- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement `marking.py` and the command**; Run line: `uv run synth3 judge --domain D   # sub-model-1
  marks every saved answer: A, B, C into <results>/D/s<n>/<system>/<qid>.marks.json (cluster)`.
- [ ] **Step 4: Run the tests**, then the whole suite. Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: the judge command, three scores per answer`.

### Task 10: The judge test and the report

**Files:**
- Create: `backend/synth3/report.py`, `backend/synth3/tests/test_report.py`
- Modify: `backend/synth3/qcli.py` (commands `judge-sample`, `report`), `backend/README.md` (two Run lines)

**Interfaces:**
- Consumes: Tasks 5 and 9.
- Produces: `JUDGE_TEST = SPECS / "judge-test"` (`sample.json`: a list of item ids; `marks.json`: item id →
  `{"points": {pid: bool}, "faithful": bool | None, "by", "at"}`); `FLAG_BELOW = 0.80`; `SAMPLE = 30`.
- Produces: `pick_sample(results, domains, n=SAMPLE, seed=0, have: list[str] = ()) -> list[str]`: judged items whose
  C is `ok`, half `rag-baseline` and half other systems (the other half fills up when one side is short), at most 2
  per (domain, question), items in `have` left out; seeded as in Global Constraints; sorted for display.
- Produces: `save_hand_mark(root, item, points: dict[str, bool], faithful: bool | None, by, at)`;
  `load_hand_marks(root) -> dict`; `load_sample(root) -> list[str]`.
- Produces: `agreement(sample, hand, judged: dict[str, dict]) -> dict`: over every (item, point) that both the judge
  (C ticks) and Aditya marked: `{"points", "agree", "rate", "flag": rate < FLAG_BELOW, "answers_marked",
  "faithful": {"n", "agree", "rate"}, "disagreements": [{"item", "point", "judge", "hand"}]}`. `faithful` compares
  his yes/no with the judge's "B is `ok` with no invented and no contradicted claim" (a pending B is left out).
  `rate` None when nothing is marked (no flag then).
- Produces: `build_report(results, domains, sheets_root, judge_test_root) -> dict` and `render_report(r) -> str`
  (markdown). Per domain and system (baseline rows next to the system's): answers, A mean, anchored mean, the A
  cross-check (share of planted facts the A judge marks `found` whose span no pulled fact touches, and share it
  marks `missing` whose span one does; code, not a score, since no person checks A), B mean, C mean, C on can't-tell
  sheets, C on the others, pending, cut texts, papers with `pulled_cut`. Per domain: sheets checked / drafted /
  missing, the 5 most missed points with their text, and the judge-test items of that domain. Then the judge
  agreement; when flagged the line reads
  `Judge agreement <r>% (below 80%: reported as a limitation).` (exact copy). A mean over no values is printed
  `n/a`.
- Produces: `synth3 judge-sample [--domains medicine] [--n 30] [--seed 0] [--add N] [--results R] [--judge-test J]`:
  writes `sample.json`; refuses when it exists unless `--add N` (then appends N new items from the named domains,
  keeping the marked ones; this is how later domains join the one judge test of about 30, spec §7).
  `synth3 report --domains medicine[,law,...] --out FILE.json [--results R] [--sheets S] [--judge-test J]`:
  writes the JSON and `FILE.md`, prints the markdown.

- [ ] **Step 1: Write the failing tests:**

```python
def test_agreement_and_the_flag():
    judged = {f"i{k}": {"C": {"ticks": [{"point": "p1", "met": True}]}} for k in range(10)}
    hand = {f"i{k}": {"points": {"p1": k < 9}, "faithful": None} for k in range(10)}
    a = agreement(list(judged), hand, judged)
    assert a["rate"] == 0.9 and not a["flag"] and a["answers_marked"] == 10
    hand = {f"i{k}": {"points": {"p1": k < 7}, "faithful": None} for k in range(10)}
    a = agreement(list(judged), hand, judged)
    assert a["rate"] == 0.7 and a["flag"] and len(a["disagreements"]) == 3

def test_unmarked_items_do_not_count():
    judged = {"i1": {"C": {"ticks": [{"point": "p1", "met": True}]}}}
    assert agreement(["i1"], {}, judged)["rate"] is None and not agreement(["i1"], {}, judged)["flag"]

def test_sample_is_balanced_capped_and_stable(tmp_path):
    fake_marks(tmp_path / "res", systems=("engine", "rag-baseline"), questions=10, seeds=5)
    s = pick_sample(tmp_path / "res", ["demo"], n=10)
    assert s == pick_sample(tmp_path / "res", ["demo"], n=10) and len(s) == 10
    assert sum("/rag-baseline/" in i for i in s) == 5
    assert max(Counter(i.split("/")[3] for i in s).values()) <= 2

def test_report_puts_the_baseline_next_to_the_system_and_flags(tmp_path):
    ...  # fake marks for engine and rag-baseline, hand marks agreeing 70%: render_report holds a row per system,
         # "n/a" for the baseline's A, and the exact flag sentence with "70%"
```

  `fake_marks` writes marks files in the shape of Task 9 for the given grid. Plus `test_judge_sample_by_command`
  (first run writes 10 items; a second run without `--add` exits 2 naming `sample.json`; `--add 4` gives 14, the
  first 10 unchanged) and `test_report_by_command` (writes `FILE.json` and `FILE.md`, exit 0).
- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement `report.py` and the two commands**; Run lines: `uv run synth3 judge-sample --domains D   #
  the ~30 answers Aditya hand-marks on the review page` and `uv run synth3 report --domains D --out FILE.json   #
  A, B, C per system with the baseline, judge agreement (flag below 80%)`.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: judge test sample, agreement and the report`.

### Task 11: The review API

**Files:**
- Create: `backend/webapp/evreview.py`, `backend/webapp/tests/test_evreview.py`
- Modify: `backend/webapp/settings.py` (`synth3_data`), `backend/webapp/app.py` (include the router; its docstring
  line "The server writes only job state and logs ... and decisions.yaml" also names world files, answer sheets and
  hand marks), `backend/webapp/files.py` (the same in its docstring), `backend/webapp/tests/test_settings.py`

**Interfaces:**
- Consumes: `synth3.questions`, `synth3.sheetfacts`, `synth3.sheets` (`check_sheet`, `person_sheet`,
  `archive_sheet`, `stale`, `review_queue`), `synth3.answers`, `synth3.judge.used_facts`, `synth3.report`,
  `synth3.spec.load_spec`, `synth3.world` (`load_world`, `save_world`, `describe`); `webapp.files` (`check_id`,
  `inside`, `NotFound`, `Conflict`, `BadRequest`).
- Produces: `Settings.synth3_data: Path = Field(repo_paths.DATA / "synth3", validation_alias="SYNTH3_DATA")`, added
  to the `_absolute` validator and the docstring table. The layout below it is fixed: `<domain>.yaml`,
  `worlds/<domain>/s<n>.json`, `questions/`, `sheets/`, `built/` (`folders_of`), `results/`, `judge-test/`.
- Produces: `evreview_router(settings: Settings) -> APIRouter`, mounted at `/api/ev` by `create_app`, with:

| Method and path | Body | Answer |
|---|---|---|
| `GET /review` | | `{domains: [{domain, questions: n or null, seeds: [n], worlds: [n]}]}` (domains = approved spec files) |
| `GET /review/{domain}/worlds` | | `[{seed, approved, text: describe(...), path}]` |
| `PUT /review/{domain}/worlds/{seed}` | `{approved: bool}` | the world row; 422 when the world file does not load |
| `GET /review/{domain}/sheets` | | `review_queue` rows (with `stale`) |
| `GET /review/{domain}/sheets/{seed}/{qid}` | | `{question, sub_questions, scope: {arms, measures, ...} as names, facts (the current relevant_facts), sheet or null, stale}` |
| `PUT /review/{domain}/sheets/{seed}/{qid}` | `{points: [{text, facts}]}` | the saved sheet; 400 with the problems; 404 for an unknown question or seed (see below) |
| `GET /review/judge-test` | | `[{n, item, done}]` from `sample.json` and `marks.json` |
| `GET /review/judge-test/{n}` | | `{item, question, answer, points: [{id, text}], facts: [{n, paper, kind, quote}], facts_cut, marked}`; never the judge's ticks or scores |
| `PUT /review/judge-test/{n}` | `{points: {pid: bool}, faithful: bool or null}` | the saved mark; 400 for an unknown or missing point |

  The sheet PUT always lets Aditya fix a sheet:
  - a sheet that is not stale: `check_sheet` (status `checked`);
  - a stale sheet: `archive_sheet`, then `person_sheet(..., checked=False)`: a new unchecked sheet keyed to the
    current question and truth hashes; he checks it with a second save;
  - no sheet (none drafted, or the draft failed): `person_sheet(..., checked=True)`.

  The judge-test item's `facts` are exactly `used_facts(rec)` (the list and numbering the B judge saw; the cited
  passages for the baseline), so his "uses its facts faithfully" answer rests on what the judge read.
  Every path part goes through `check_id`; `seed` is an int; file paths are built with `files.inside` under
  `settings.synth3_data`. `checked_by` and the hand mark's `by` are `settings.user`; times are UTC ISO strings.
  Writes go through one module lock and `write_json_atomic` (through `save_world`, `save_sheet`,
  `save_hand_mark`).

- [ ] **Step 1: Write the failing tests.** A fixture `review_root(tmp_path)` writes the demo spec (`conftest.good()`
  of synth3) as `demo.yaml`, draws and saves world s1 (not approved), builds folder `built/demo/s1` from an approved
  copy, writes the fixture questions to `questions/demo.yaml`, a drafted sheet for `d01` (none for `d02`), an
  engine answer record for `d01` with two pulled facts and its marks file, and `judge-test/sample.json` naming it. `client(root)` is `TestClient(create_app(Settings(
  SYNTH3_DATA=root, ...), plan_backend=PlanBackend()))`; writes send JSON (the guard). `keys(obj)` collects every
  dict key in a JSON value, at any depth.

```python
def test_worlds_show_the_plain_table_and_approve(review_root):
    c = client(review_root)
    rows = c.get("/api/ev/review/demo/worlds").json()
    assert rows[0]["seed"] == 1 and not rows[0]["approved"] and "World of demo, seed 1" in rows[0]["text"]
    assert c.put("/api/ev/review/demo/worlds/1", json={"approved": True}).json()["approved"]
    assert json.loads((review_root / "worlds" / "demo" / "s1.json").read_text(encoding="utf-8"))["approved"] is True

def test_a_sheet_is_shown_with_its_facts_and_saved_as_checked(review_root):
    c = client(review_root)
    got = c.get("/api/ev/review/demo/sheets/1/d01").json()
    assert got["scope"]["arms"] == ["Standard care", "Targeted therapy"] and got["facts"] and got["stale"] is None
    saved = c.put("/api/ev/review/demo/sheets/1/d01", json={"points": [{"text": "Edited.", "facts": []}]}).json()
    assert saved["status"] == "checked" and saved["checked_by"] and saved["points"][0]["text"] == "Edited."

def test_a_bad_point_is_400(review_root):
    r = client(review_root).put("/api/ev/review/demo/sheets/1/d01",
                                json={"points": [{"text": "x", "facts": ["pair:zz:m9"]}]})
    assert r.status_code == 400 and "pair:zz:m9" in r.json()["detail"]

def test_saving_a_stale_sheet_makes_a_new_unchecked_one(review_root):
    c = client(review_root)
    edit_question(review_root, "d01", "Does Targeted therapy change the Response rate?")
    assert c.get("/api/ev/review/demo/sheets/1/d01").json()["stale"]
    saved = c.put("/api/ev/review/demo/sheets/1/d01", json={"points": [{"text": "New.", "facts": []}]}).json()
    assert saved["status"] == "drafted" and saved["drafted_by"]["person"]
    assert c.get("/api/ev/review/demo/sheets/1/d01").json()["stale"] is None
    assert (review_root / "sheets" / "demo" / "s1" / "d01.stale-1.json").is_file()
    again = c.put("/api/ev/review/demo/sheets/1/d01", json={"points": [{"text": "New.", "facts": []}]}).json()
    assert again["status"] == "checked"

def test_a_missing_sheet_can_be_written_on_the_page(review_root):
    c = client(review_root)
    got = c.get("/api/ev/review/demo/sheets/1/d02").json()
    assert got["sheet"] is None and got["facts"]
    saved = c.put("/api/ev/review/demo/sheets/1/d02", json={"points": [{"text": "Written by hand.", "facts": []}]})
    assert saved.status_code == 200 and saved.json()["status"] == "checked"

def test_the_judge_test_item_shows_the_facts_but_not_the_judge(review_root):
    c = client(review_root); item = c.get("/api/ev/review/judge-test/0").json()
    assert not keys(item) & {"met", "score", "ticks", "A", "B", "C", "judge"}
    assert item["facts"][0]["n"] == 1 and item["facts"][0]["quote"]
    assert c.put("/api/ev/review/judge-test/0", json={"points": {"p9": True}, "faithful": None}).status_code == 400
    assert c.put("/api/ev/review/judge-test/0", json={"points": {"p1": True}, "faithful": True}).status_code == 200
    assert c.get("/api/ev/review/judge-test").json()[0]["done"]

@pytest.mark.parametrize("path", ["/api/ev/review/demo/sheets/1/a.b%20c", "/api/ev/review/demo/sheets/1/-x",
                                  "/api/ev/review/de%2E%2Emo/worlds", "/api/ev/review/demo/sheets/x/d01",
                                  "/api/ev/review/demo/sheets/9/d01", "/api/ev/review/nope/worlds"])
def test_bad_ids_are_refused(review_root, path):
    assert client(review_root).get(path).status_code in (400, 404, 422)

def test_the_path_builder_stays_under_the_root(review_root):
    with pytest.raises((BadRequest, NotFound)):
        ReviewFiles(Settings(SYNTH3_DATA=review_root)).sheet_file("demo", 1, "..")
```

  `ReviewFiles` is the class in `evreview.py` that turns ids into paths (`sheet_file(domain, seed, qid)` and the
  like). Plus `test_queue_marks_the_full_folder` (seed 1 rows `must_check == "full"`) and a settings test that
  `SYNTH3_DATA` is read and made absolute (in `test_settings.py`).
- [ ] **Step 2: Run the tests to watch them fail.** Run `uv run pytest -q backend/webapp/tests/test_evreview.py`.
  Expected: FAIL with `ModuleNotFoundError: webapp.evreview`.
- [ ] **Step 3: Implement `evreview.py`, the setting and the mount.** The `answer` of a judge-test item is the
  record's `text`; points come from the sheet the marks file names (its `sheet.points`), so the item still shows the
  points Aditya's marks refer to if the sheet is edited later.
- [ ] **Step 4: Run** `uv run pytest -q backend/webapp`. Expected: PASS (the write contract is unchanged: the review
  API is not in `write_contract.py`, as the plan API is not).
- [ ] **Step 5: Commit** the six files of the Files list:
  `webapp: review API for worlds, answer sheets and the judge test`.

### Task 12: The review page

**Files:**
- Create: `frontend/src/routes/review/api.ts`, `ReviewPage.tsx`, `WorldsTab.tsx`, `SheetsTab.tsx`,
  `JudgeTestTab.tsx`, `review.test.tsx`
- Modify: `frontend/src/app/routes.tsx` (lazy `ReviewPage`, routes `review` and `review/:tab`),
  `frontend/src/components/layout/pages.ts` (VIEWER entry `{ to: "/review", label: "Review", icon: ListChecksIcon }`
  after Plan), `frontend/src/mocks/handlers.ts` (mock answers for the review GETs and PUTs, so `npm run dev:mock`
  shows the page), `frontend/src/api/client.ts` (only if it lacks `putJson`), `frontend/openapi.json` and
  `frontend/src/api/schema.d.ts` (regenerated), `frontend/dist/` (rebuilt)

**Interfaces:**
- Consumes: Task 11's API; `@/api/client` (`getJson`, `postJson`, and a `putJson` if the client has none, added the
  same way); `renderWithProviders`, `server` from the test setup, as `routes/plan/plan.test.tsx` does.
- Produces: `api.ts` with the types of Task 11's answers written by hand (as `routes/plan/api.ts` does) and one
  TanStack hook per endpoint.
- The page (layout is the builder's call within this): a domain picker on top; three tabs.
  - **Worlds:** one card per seed with the plain table in a `<pre>`, an "Approved" or "Not approved" badge, and a
    button "Approve" / "Withdraw approval" (a confirm dialog says this decides which worlds can be built).
  - **Answer sheets:** the queue table (seed, question, status, must check, stale), sortable by "must check" first.
    Opening a row shows the question, its sub-questions (labelled "for planning only; not scored"), the scope found
    ("about: Targeted therapy, Standard care; measures: all"), the fact lines (id and text), the points as editable
    text with their fact ids as removable chips and a fact picker, add / remove point, the warnings, and "Save and
    mark checked". A stale sheet shows a banner with the reason and the button reads "Save as a new sheet" (the
    new sheet is unchecked; he saves again to check it). A missing sheet opens an empty editor with "Write and
    mark checked".
  - **Judge test:** the list with done marks; an item shows the question, the answer, the numbered facts or
    passages the answer used (paper, kind, quote; a note when they were cut), and per point "Met" / "Not met" radio
    buttons, an optional "Uses its facts faithfully: yes / no / skip", and Save. Nothing of the judge's marks is
    fetched or shown.

- [ ] **Step 1: Install and write the failing tests.** In `frontend/`: `uv run --group frontend npm ci`. Tests in
  `review.test.tsx`, each with `server.use(http.get(...), http.put(...))` handlers that record the request bodies:
  - `it("saves edited points as checked")`: change point 1's text, click "Save and mark checked", expect one PUT to
    `/api/ev/review/demo/sheets/1/d01` with `{points: [{text: "Edited.", facts: ["pair:a:m1"]}]}`;
  - `it("saves a stale sheet as a new sheet")`: `stale: "the question changed after drafting"` → the banner text
    is shown, the button reads "Save as a new sheet", and clicking it sends one PUT with the edited points;
  - `it("writes a missing sheet")`: `sheet: null` → an empty editor; adding one point and "Write and mark checked"
    sends `{points: [{text: "By hand.", facts: []}]}`;
  - `it("hand-marks a judge-test answer without showing the judge")`: the facts' quotes are shown; no element has
    text matching `/judge|score/i` inside the item panel; ticking p1 "Met" and Save sends
    `{points: {p1: true}, faithful: null}`;
  - `it("approves a world")`: clicking "Approve" then confirming sends `{approved: true}`.
- [ ] **Step 2: Run** `npm test -- review`. Expected: FAIL (module not found).
- [ ] **Step 3: Implement the page, the route and the sidebar entry.**
- [ ] **Step 4: Run** `npm test`, `npm run typecheck`, `npm run lint`. Expected: PASS. Then from the repo root
  `uv run webapp openapi -o frontend/openapi.json && (cd frontend && npm run gen:api)` and `npm run build` in
  `frontend/`. Check by hand: `uv run webapp serve` with `SYNTH3_DATA` pointing at a scratchpad copy holding the
  demo files of Task 11's fixture, open `/review`, and click through the three tabs (the `run` skill can drive it).
- [ ] **Step 5: Commit** the new and changed source files, `frontend/openapi.json`, `frontend/src/api/schema.d.ts`
  and `frontend/dist/` (stage `frontend/dist` by path; it is committed so Slurm needs no npm):
  `webapp: review page for worlds, answer sheets and the judge test`.

### Task 13: Close: the whole suite and the list for Aditya

**Files:**
- Modify: `backend/README.md` only if a Run line from Tasks 2-10 is missing
- Not committed: `.superpowers/sdd/synth3-program.md` (the program ledger)

- [ ] **Step 1: Run the whole suite** `uv run pytest -q` (with the Windows `--ignore`s). Expected: PASS apart from
  the known `agent/tests` import errors. Run `uv run synth3 --help` and check the seven new commands are listed:
  `questions`, `draft-sheets`, `collect`, `baseline`, `judge`, `judge-sample`, `report`.
- [ ] **Step 2: Check the gates held:** `git ls-files data/synth3/questions data/synth3/sheets
  data/synth3/judge-test` prints nothing (no question set or sheet was committed), and `git check-ignore
  data/synth3/results/x` prints the path.
- [ ] **Step 3: Commit** a README fix if Step 1 found one: `synth3: README run lines for questions and the judge`.
- [ ] **Step 4: Add to the ledger's list "for Aditya to run or decide"** (in this order; the plan does not wait):
  1. write the 25 questions per domain in `data/synth3/questions/<domain>.yaml` (format: the docstring of
     `backend/synth3/questions.py`), check with `uv run synth3 questions --domain medicine`;
  2. on the cluster: `uv run synth3 draft-sheets --domain medicine` (orch-model), then on the review page check every
     sheet of s1 and the 20 marked "sample";
  3. on the cluster: `uv run synth3 baseline --domain medicine` (orch-model);
  4. after plan 4's runs (or for the fixed kinds now): `uv run synth3 collect ...` per run, then
     `uv run synth3 judge --domain medicine` (sub-model-1);
  5. `uv run synth3 judge-sample --domains medicine`, hand-mark the 30 answers on the review page, then
     `uv run synth3 report --domains medicine --out data/synth3/results/report-medicine.json`; read the agreement
     line (below 80% is flagged as a limitation).

  Repeat 1-4 for law, materials and RAG once their specs and worlds are approved and built (plan 2's list); for
  step 5 use `uv run synth3 judge-sample --domains law --add N` with N his choice (or none), so the judge test
  stays one set of about 30 (spec §7), and `report --domains medicine,law,...`.
  Two notes for him: (a) a question: should sub-questions also help the drafter read the question? This plan keeps
  them out of sheets entirely (spec §6, review ruling I1); (b) the new synth3 modules change
  `synth3.corpus.code_sha256()` (it hashes every `synth3/*.py`), so folders built after this plan record a new
  generator hash although the generator did not change; nothing checks it today.
