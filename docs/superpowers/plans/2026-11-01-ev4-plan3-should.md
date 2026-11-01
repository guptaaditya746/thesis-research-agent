# EV4 Plan 3: Should items (reasoner, lock and sealed runs, estimate, real-paper checks, web app, runbook) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Should items of EV4 build steps 8-12:
- a reasoner step that matches narrower kinds to broader ones and flags wrong links;
- a protocol lock, `evidence protocol diff`, sealed run folders with `evidence verify`, and `evidence estimate`;
- costs and losses first in the report;
- four real-paper checks;
- arXiv HTML first, with Docling as fallback;
- the web app changes (Scores page out, three-column graph);
- the Codex runbook for the EV4 runs.

**Architecture:** Every new engine output is one file in the run folder (D24): `reason.json`, `protocol.lock.json` and `manifest.json`. They are written like `dangling_links` today (engine.py:261-266, 534-536, 610-615), and a missing setting means off (D30, replay.py:39-40). The pieces live here:
- the reasoner in `evidence/reasoner.py` (rdflib + owlrl over `domains/<pack>/ontology.ttl`);
- lock and diff in `evidence/lockfile.py`;
- sealing in `evidence/seal.py`;
- the estimate in `evidence/estimate.py`;
- real-paper loaders and scorers in `evaluation/realpapers/`, each writing `real.json`/`real.md` and never mixed into `report.json`;
- the losses-first table in `evaluation/losses.py`.

The web app only reads files (D27).

**Tech Stack:** Python 3.13, rdflib==7.6.0 (already a dependency), `owlrl` (new), `docling==2.110.0` (new dependency group `fetch`; `pymupdf4llm` removed), pydantic, pytest via `uv run pytest`. React 19, `@xyflow/react` 12.12.0, `@dagrejs/dagre` 3.1.1, Vitest 4 with MSW.

**Spec:** `docs/superpowers/specs/2026-11-01-ev4-general-evidence-system-design.md`: §6.3, §6.6, §6.7, §6.12 (D21, D42), §6.13 (`evidence estimate` only, D41), §6.14 (without the add-a-topic demo), §6.15 (D40), §6.16, §6.17 (D24, D25, D27, D30, D31), §7 steps 8-12. This is plan 3 of 3. It uses plan 1's **Shared interfaces** (`load_pack`, `Pack` incl. `sha256`, `Role`, `RoleMap`, `names.json`/`unresolved_names`, `CHECKED_DIRS`). From plan 2 it uses only the question kinds `"chaining"`, `"limitations"`, `"builds_on"` and the pack `domains/drugtrials`.

## Global Constraints

- **Branch:** `ev4/should` from `ev4/foundation`. Steps 8-11 (Tasks 1-14) do not depend on each other. Tasks 6, 9, 13 and 15 need plan 2's work, so merge plan 2's branch into `ev4/should` before starting them. Nothing is merged, tagged or pushed without Aditya's go.
- **Reasoner** (§6.3): "Inferences are written into the run, so replays never re-reason." "The reasoner is a setting; a missing setting means off, so old runs replay unchanged (same rule as relink)" (D30). "The reasoner runs after merge and before comparisons" (D25).
- **CS-KG seed:** namespace `https://w3id.org/cskg/ontology#`. Mapping: compared thing → `Method`, metric → `Metric`, dataset → `Material`, task → `Task`, builds-on → `based-on`, default parent `OtherEntity`. "The measured value stays our own internal type (D9)". No measured-value class is added to the ontology, and nothing is exported as RDF (§4).
- **Lock** (§6.6): "every run writes `protocol.lock.json`: protocol digest, pack digest, every resolved extractor id, the ontology digest". "an unknown name or missing input fails before any model call".
- **Sealed runs** (§6.7): "Every run directory ends with `manifest.json`: every file with its sha256, the corpus manifest sha256, the protocol lock digest and the code commit. A failed run still writes all expected files (empty when there is nothing). `evidence verify <run>` recomputes the hashes. Old runs: 'no manifest (pre-EV4)'."
- **Real-paper checks** (D42): each is "reported as 'real-paper check', never mixed with synthetic scores". For Yun et al., "Only 59% of records have complete numbers; score the rest on names and direction only." SciREX is scored at two levels (mention, salient cluster). Real-paper test sets "are read by neither helper" (§6.11). Gold is read only by the scorer (D31).
- **arXiv demo** (§6.15): label it "demonstration, not an evaluation".
- **Web app:** never show OWL, ontology or class words (D13, §4). The app shows plain names only.
- **Report** (§6.16): "losses first", one line per engine loss from: "missed / wrongly linked / names not grouped / wrong rule". "Next to the scores: model calls and tokens per system (D41)." The comparison section opens with Tim's sentence: "We should not assume that the evidence-level approach will necessarily perform better".
- **Not in this plan** (cut first): the BM25 first pass and 10,000-paper scale, and the add-a-topic web demo. DuckDB (D33) is not added; reports read run folders and report files directly.
- **Codex runbook conventions:** code tag `ev4-code`; reports under `reports/ev4/` on branch **`results-ev4`**, tag **`ev4`**. Never push `main` or `results`. Session dir `$EV=/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-ev4`.
- **Tests:** every task ends with its package passing: `uv run pytest evidence -q`, `uv run pytest evaluation -q`, `uv run pytest webapp -q`; frontend `npm --prefix webapp/web test -- --run`. Expected failures that are not yours:
  - the 3 known Windows-only failures in docs/STATE.md:186;
  - the known webapp `test_evjobs` failure;
  - the old vitest failure "lists every corpus with level, knobs and the variant" (docs/STATE.md:117).
- **Test style:** as plan 1 (module docstring, `from __future__ import annotations`, `test_<plain_sentence>()`).

## Review Focus

These five inputs and failure modes would bite a user, and no other task tests them. Each test is added in the task named.

1. **An old run folder** (no `reason`, no lock, no manifest in run.json) still replays with every output hash equal. `evidence verify` prints `"manifest": "no manifest (pre-EV4)"` and exits on the chain result only.
   - Task 2: `test_replay_of_a_run_without_reason_keeps_every_hash`.
   - Task 4: `test_verify_old_run_says_pre_ev4`.
2. **A strange ontology** (a metric name not in the ontology, a subClassOf cycle, two classes with the same label) never crashes. An unknown name counts only for itself.
   - Task 1: `test_unknown_metric_counts_only_for_itself`, `test_subclass_cycle_terminates`, `test_duplicate_label_is_refused_with_both_iris`.
3. **A run that crashes at paper 2** of 3 still has every expected file. `manifest.json` has `status: "failed"`, there is no `run.json`, and the `RunDirExists` message still says "killed or crashed".
   - Task 4: `test_a_crash_writes_all_expected_files_and_a_failed_manifest`.
4. **An arXiv HTML page** that answers 200 but is an error page, too short, or a 404 falls back to the PDF, and the reason goes into `source.json`. When both fail, the paper is skipped with both reasons.
   - Task 7: `test_bad_html_falls_back_to_pdf_with_reason`, `test_both_failing_skips_with_both_reasons`.
5. **Run folders committed by Codex** to `results-ev4` and checked out on Windows with `core.autocrlf` would fail `verify` on every JSON file.
   - Task 4 adds `reports/** -text` to `.gitattributes` and `test_report_files_are_never_converted`, which checks that `git check-attr text reports/ev4/runs/x/answer.json` gives `unset`.

## Shared names (this plan)

```python
# evidence/reasoner.py
CSKG = "https://w3id.org/cskg/ontology#"
@dataclass(frozen=True) class Inferences: ontology_sha256: str | None; broader: dict[str, list[str]]; link_flags: list[list[str]]
def ontology_sha256(pack: Pack, root: Path = DOMAINS) -> str | None
def load_ontology(pack: Pack, root: Path = DOMAINS) -> rdflib.Graph | None   # closure applied
def broader_of(graph: rdflib.Graph, label: str) -> list[str]
def reason(pack: Pack, protocol: Protocol, items: dict[str, list[Item]], root: Path = DOMAINS) -> Inferences
def counts_as(name: str, wanted: str, inferred: Inferences | None) -> bool
# evidence/lockfile.py
LOCK_FILE = "protocol.lock.json"
def lock(protocol: Protocol, pack: Pack, cascades: dict[str, list[tuple[ExtractorRef, Extractor]]], ontology: str | None) -> dict
def diff(a: Path, b: Path) -> list[str]
# evidence/seal.py
MANIFEST_FILE = "manifest.json"
def code_commit() -> str | None
def fill_expected(root: Path, settings: Settings) -> None
def seal(root: Path, *, corpus_manifest_sha256: str, lock_sha256: str | None, status: Literal["complete","failed"], error: str | None = None) -> Path
def check(root: Path) -> dict | str          # "no manifest (pre-EV4)" for old runs
# evidence/estimate.py
def estimate(protocol_path: Path, corpus: Path, *, strategy: Strategy = "gaps", selection: Selection = "cascade", from_run: Path | None = None) -> dict
# evaluation/losses.py
CAUSES = ("missed", "wrongly linked", "names not grouped", "wrong rule")
def headline(kind: str, system: dict) -> float | None
def loss_cause(report: dict) -> str
def losses(reports: list[dict]) -> dict
```

Run folder additions:
- `reason.json` (`{"ontology_sha256", "broader", "link_flags"}`), an output written only with `reason: on`;
- `protocol.lock.json`, an output;
- `manifest.json`, written last and not an output.

`Settings.reason: Literal["off","on"]` follows the `relink` pattern exactly.

---

### Task 1: Reasoner core and the `rag` ontology seed

**Files:**
- Create: `evidence/reasoner.py`, `domains/rag/ontology.ttl`, `evidence/tests/fixtures/onto/ontology.ttl`, `evidence/tests/test_reasoner.py`.
- Modify: `pyproject.toml` / `uv.lock` (`uv add owlrl`; keep the version uv resolves against `rdflib==7.6.0`); `evidence/pack.py` (add `OntologyDecl(Strict)` with `file: str = "ontology.ttl"` and `roles: dict[Role, str]`; add `Pack.ontology: OntologyDecl | None = None`; `Pack.sha256` stays as plan 1 defines it, and the ontology has its own digest); `domains/rag/pack.yaml` (`ontology: {roles: {compared_thing: "cskg:Method", metric: "cskg:Metric", context: "cskg:Material"}}`); `domains/rag/provenance.json` (an `ontology` entry listing each class and narrower→broader pair with its source).

**Interfaces:**
- Consumes: `Pack`, `load_pack`, `Role`.
- Produces: `CSKG`, `ontology_sha256`, `load_ontology`, `broader_of`, `counts_as` (Shared names).

**`domains/rag/ontology.ttl`** holds:
- the CS-KG subset `cskg:Method`, `cskg:Metric`, `cskg:Material`, `cskg:Task`, `cskg:OtherEntity`, `cskg:based-on`;
- one class per canonical metric in `domains/rag/words.yaml` `metrics`, each `rdfs:subClassOf cskg:Metric` with `rdfs:label` = the canonical name;
- the narrower→broader pairs the builder finds among those names, each also listed in `provenance.json`.

Pinned values:
- **Label match:** labels are compared after `names.clean` (plan 1).
- **`broader_of`** returns the labels of every superclass after `owlrl.DeductiveClosure(owlrl.RDFS_Semantics).expand(g)`. It leaves out the label itself and the top classes (`cskg:Metric`, `cskg:Method`, `cskg:Material`, `cskg:Task`, `cskg:OtherEntity`, `owl:Thing`, `rdfs:Resource`). It returns `[]` for an unknown label.
- **Digest:** `ontology_sha256` is the sha256 of the LF-normalised file bytes, or None when the pack has no ontology.

- [ ] **Step 1: Write the failing tests**

```python
def test_narrower_metric_counts_for_broader():
    g = load_ontology(fixture_pack())
    assert "accuracy" in broader_of(g, "top-1 accuracy")
    inf = Inferences(None, {"top-1 accuracy": broader_of(g, "top-1 accuracy")}, [])
    assert counts_as("top-1 accuracy", "accuracy", inf) and not counts_as("accuracy", "top-1 accuracy", inf)

def test_unknown_metric_counts_only_for_itself():
    g = load_ontology(fixture_pack())
    assert broader_of(g, "made-up score") == []
    assert counts_as("made-up score", "made-up score", None) and not counts_as("made-up score", "accuracy", None)

def test_subclass_cycle_terminates():
    g = load_ontology(fixture_pack(extra=":A rdfs:subClassOf :B . :B rdfs:subClassOf :A ."))
    assert broader_of(g, "a") == ["b"]

def test_duplicate_label_is_refused_with_both_iris():
    with pytest.raises(PackError, match=r"label 'accuracy'.*#Accuracy.*#Acc2"):
        load_ontology(fixture_pack(extra=':Acc2 rdfs:label "accuracy" .'))

def test_top_classes_are_never_broader_names():
    assert "metric" not in broader_of(load_ontology(fixture_pack()), "accuracy")

def test_rag_ontology_loads_and_has_a_digest():
    p = load_pack("rag")
    assert load_ontology(p) is not None and len(ontology_sha256(p)) == 64
```

`fixture_pack(extra="")` copies `domains/rag` into `tmp_path`, replaces `ontology.ttl` with the fixture (`:TopOne rdfs:label "top-1 accuracy"; rdfs:subClassOf :Accuracy . :Accuracy rdfs:label "accuracy"; rdfs:subClassOf cskg:Metric .` plus `extra`), and returns `load_pack("rag", root=tmp_path)`.

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_reasoner.py -q`. Expected: FAIL (`No module named evidence.reasoner`).
- [ ] **Step 3:** Implement `evidence/reasoner.py` (the functions above, not yet `reason`) and the pack and ontology files.
- [ ] **Step 4:** Run `uv run pytest evidence/tests/test_reasoner.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git add evidence/reasoner.py evidence/pack.py domains/rag evidence/tests/test_reasoner.py evidence/tests/fixtures/onto pyproject.toml uv.lock && git commit -m "evidence: reasoner core (owlrl over rdflib) and CS-KG seed for rag"`

### Task 2: Reasoner step in the engine, `reason.json`, kinds use it

**Files:**
- Modify:
  - `evidence/engine.py`: `Reason = Literal["off","on"]` next to :96-97; `Settings.reason: Reason = "on"` after :119; `Settings.json()` :121-126 adds `**({"reason": self.reason} if self.reason == "on" else {})`. In `finish()` :525-547, before `kinds.of(...).answer(...)` (:529, or before plan 2's comparisons step if that has moved it): with `reason == "on"`, call `reason(...)`, write `reason.json` into `self.outputs`, and pass `reason=` to the kind. `Execution.__init__` :224-227 and `_warm` :550-560 take `reason`. `run()` :629-641 takes `reason: Reason = "on"`.
  - `evidence/replay.py:33-40`: `reason=s.get("reason", "off")`.
  - `evidence/cli.py`: `--reason on|off` default `on` beside :82-84, passed on at :183; the module docstring :3-5.
  - The question-metric tests at `evidence/synthesis.py:129` and `evidence/kinds/best.py:71` (line numbers as of `ev4/spec`): `m.fields.get("canonical") == name` becomes `counts_as(m.fields.get("canonical"), name, reason)`.
  - `evidence/kinds/__init__.py`: kinds' `answer` takes `reason: Inferences | None = None`.
  - `evidence/rundir.py:28-34`: `REASON_FILE = "reason.json"`, added to `ENGINE_MARKERS`.
- Test: `evidence/tests/test_reason_step.py`.

**Interfaces:**
- Consumes: Task 1, plan 1 `RoleMap` and `NameGroups` (kinds already take `roles` and `groups`).
- Produces: `reason(pack, protocol, items, root) -> Inferences`, `Settings.reason`, and the run file `reason.json`. **Link check:**
  - For every item and every `(link_name, target)`, the expected role is the `Role` of the type the protocol declares for that link (`EvidenceTypeSpec.links[link_name]`, read through `RoleMap`), and the expected class is `pack.ontology.roles[role]`.
  - The target's class is the class whose label equals the target's name or canonical field (through `RoleMap.field`), else the class of its type's role.
  - The link is flagged `[item_id, link_name, target, "not a <plain role name>"]` when the target's class is not that class or a subclass of it.
  - Plain role names: `compared_thing` → "compared thing", `metric` → "metric", `context` → "context".
  - With no ontology in the pack, `reason.json` is `{"ontology_sha256": null, "broader": {}, "link_flags": []}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_reason_off_writes_nothing_new(tmp_path):
    out = regex_run(PAPERS, tmp_path, PROTOCOL, settings={"reason": "off"})
    assert not (out / "reason.json").exists() and "reason" not in run_json(out)["settings"]

def test_reason_on_writes_inferences_as_an_output(tmp_path):
    out = regex_run(PAPERS, tmp_path, PROTOCOL)
    data = json.loads((out / "reason.json").read_text())
    assert set(data) == {"ontology_sha256", "broader", "link_flags"}
    assert "reason.json" in run_json(out)["outputs"] and run_json(out)["settings"]["reason"] == "on"

def test_narrower_metric_answers_a_broader_question(tmp_path):
    out = regex_run(["System R reaches top-1 accuracy of 0.71; the closed-book model 0.52."], tmp_path,
                    question_metric_protocol("accuracy"), domains=onto_domains(tmp_path))
    assert answer_of(out)["studies"][0]["direction"] == "supports"

def test_value_linked_to_a_dataset_name_is_flagged(tmp_path):
    out = regex_run(["accuracy on SQuAD: 0.71"], tmp_path, metric_is_squad_protocol(), domains=onto_domains(tmp_path))
    flags = json.loads((out / "reason.json").read_text())["link_flags"]
    assert any(f[1] == "metric" and f[3] == "not a metric" for f in flags)

def test_replay_never_re_reasons(tmp_path, monkeypatch):
    out = regex_run(PAPERS, tmp_path, PROTOCOL)
    monkeypatch.setattr(reasoner, "load_ontology", lambda *a, **k: pytest.fail("re-reasoned"))
    new, report = replay(out)
    assert report["ok"]

def test_replay_of_a_run_without_reason_keeps_every_hash(tmp_path):
    out = regex_run(PAPERS, tmp_path, PROTOCOL, settings={"reason": "off"})
    strip_setting(out, "reason")          # as a run made before this task
    assert replay(out)[1]["ok"]

def test_cli_reason_default_on():
    assert cli._parser().parse_args(["run", "--protocol", "p", "--corpus", "c"]).reason == "on"
```

For `test_replay_never_re_reasons`, replay reads `reason.json` from the recorded run when present. The inferences are recorded and reused, never recomputed. The ids in the file must be equal, and the new run's `reason.json` hash is checked like every output.

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_reason_step.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. In replay and reexec mode, the engine copies `reason.json` from `source_run` instead of calling `reason` (pass the recorded file through `execute_run(..., source_run=...)`; `replay.py:48-50` already gives `source_run`).
- [ ] **Step 4:** Run `uv run pytest evidence -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evidence: reasoner step after merge, reason.json, setting off when missing (D25, D30)"`

### Task 3: Protocol lock, early refusal, `evidence protocol diff`

**Files:**
- Create: `evidence/lockfile.py`, `evidence/tests/test_lockfile.py`.
- Modify:
  - `evidence/engine.py:575-593`: parse, `load_pack(protocol.domain)`, gliner info, `build_extractors` and `lock(...)` all happen **before** `root.mkdir` (:581-584). Then write `protocol.yaml` and `protocol.lock.json`, and set `ex.outputs[LOCK_FILE]`.
  - `evidence/cli.py:103-104`: add `proto.add_parser("diff", ...)` with `a`, `b` (Path); handler beside `_protocol_check` :230-242.
  - `evidence/rundir.py:28-34`: `LOCK_FILE` in `ENGINE_MARKERS`.

**Interfaces:**
- Consumes: `Protocol.sha256` (protocol.py:318), `Pack.sha256`, `ontology_sha256`, `ExtractorSpec.extractor_id`.
- Produces:
  - **Lock file:** `{"protocol": {"id", "sha256"}, "pack": {"name", "sha256"}, "ontology_sha256": str|None, "extractors": {"<etype or screen>": ["<extractor_id>", ...]}}`, where the cascade order is kept.
  - **`diff(a, b)` inputs:** each of `a` and `b` is a protocol `.yaml` or a run dir (its `protocol.yaml` plus `protocol.lock.json`).
  - **`diff` output lines** (sorted within each group):
    - `changed <dotted.path>: <old> -> <new>`
    - `added <dotted.path>: <new>`
    - `removed <dotted.path>: <old>`
    - `extractor <etype>[<i>]: <old id> -> <new id>`
    - `pack: <name> <sha12> -> <name> <sha12>`
    - `ontology: <sha12|none> -> <sha12|none>`
    - `no lock (pre-EV4): <path>`
  - **List rule:** lists of scalars are compared as sets (`added screen.terms: "x"`); other lists by index.
  - **Exit status:** 0 with the single line `same` when nothing differs, 1 when something differs, 2 when a file cannot be read.

- [ ] **Step 1: Write the failing tests**

```python
def test_every_run_writes_a_lock_with_all_digests(tmp_path):
    out = regex_run(PAPERS, tmp_path, PROTOCOL)
    lock = json.loads((out / "protocol.lock.json").read_text())
    assert lock["protocol"]["sha256"] == load(PROTOCOL).sha256 and lock["pack"]["sha256"] == load_pack("rag").sha256
    assert lock["extractors"]["metric"] == [e for e in run_json(out)["extractors"] if e in lock["extractors"]["metric"]]
    assert "protocol.lock.json" in run_json(out)["outputs"]

def test_unknown_extractor_fails_before_any_model_call_and_any_folder(tmp_path):
    def provider(alias): pytest.fail("model called")
    with pytest.raises(KeyError, match="no extractor named 'nope'"):
        run(with_extractor(PROTOCOL, "metric", "nope"), CORPUS, tmp_path, provider=provider)
    assert list(tmp_path.iterdir()) == []

def test_diff_names_a_changed_term_and_extractor(tmp_path):
    a, b = two_runs_differing_in_screen_term(tmp_path)
    lines = lockfile.diff(a, b)
    assert 'added screen.terms: "hallucinate"' in lines and any(l.startswith("extractor screen[0]:") for l in lines)

def test_diff_of_the_same_protocol_is_same():
    assert lockfile.diff(PROTOCOL, PROTOCOL) == ["same"]

def test_diff_of_a_pre_ev4_run_says_so(tmp_path):
    old = regex_run(PAPERS, tmp_path, PROTOCOL); (old / "protocol.lock.json").unlink()
    assert f"no lock (pre-EV4): {old}" in lockfile.diff(old, PROTOCOL)

def test_cli_diff_exit_codes(tmp_path):
    assert cli.main(["protocol", "diff", str(PROTOCOL), str(PROTOCOL)]) == 0
    assert cli.main(["protocol", "diff", str(PROTOCOL), str(OTHER_PROTOCOL)]) == 1
    assert cli.main(["protocol", "diff", str(PROTOCOL), str(tmp_path / "missing.yaml")]) == 2
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_lockfile.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. A missing input (a link to an undeclared type) already fails in `protocol.parse` (protocol.py:269-274), which now runs before the mkdir too.
- [ ] **Step 4:** Run `uv run pytest evidence -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evidence: protocol.lock.json, refusal before any model call, protocol diff (§6.6)"`

### Task 4: Sealed runs (`manifest.json`) and `evidence verify`

**Files:**
- Create: `evidence/seal.py`, `evidence/tests/test_seal.py`.
- Modify:
  - `evidence/engine.py:596-616`: wrap the paper loop and `finish()` in `try/except BaseException`. On failure, call `fill_expected(root, settings)`, then `seal(..., status="failed", error=f"{type(exc).__name__}: {redact(str(exc))[:300]}")`, then re-raise. No `run.json` is written, so `RunDir.complete` (rundir.py:201-206) and the `RunDirExists` wording (rundir.py:60-69) stay as they are. On success, call `seal(..., status="complete")` after `run.json`.
  - `evidence/cli.py:102, 225-227`: `verify` keeps the chain check and adds `"manifest": seal.check(run)`. It exits 1 when the chain or the manifest fails. A pre-EV4 run is judged on the chain only. Update the help text to "check the run's hash chain and file hashes".
  - `.gitattributes`: add `reports/** -text` with a comment ("run folders are hashed byte for byte; `evidence verify` must pass on every checkout").

**Interfaces:**
- Produces:
  - **`manifest.json`:** `{"files": {"<posix relpath>": "<sha256>"}, "corpus_manifest_sha256", "protocol_lock_sha256", "code_commit", "status", "error"}`. It lists every file under the run folder except itself, sorted. `code_commit` is `$EVIDENCE_CODE_COMMIT`, else `git rev-parse HEAD` in the repo root, else null.
  - **`check()`:** returns `{"ok": bool, "mismatched": [...], "missing": [...], "extra": [...], "status": ...}`, or the string `"no manifest (pre-EV4)"`.
  - **Expected files and their empty forms:** `locate.json` `[]`, `evidence.jsonl` empty, `funnel.json` `{"strategy": <s>, "documents": {}}`, `answer.json` `{}`, `graph.json` `{"nodes": [], "edges": []}`, `calls/` (directory). Also `reason.json` with `reason: on` (empty `Inferences` JSON) and `names.json` with `names: on` (`{"groups": {}, "matches": [], "unresolved": []}`).

- [ ] **Step 1: Write the failing tests**

```python
def test_a_run_ends_with_a_complete_manifest(tmp_path):
    out = regex_run(PAPERS, tmp_path, PROTOCOL)
    m = json.loads((out / "manifest.json").read_text())
    assert m["status"] == "complete" and "run.json" in m["files"] and "manifest.json" not in m["files"]
    assert m["corpus_manifest_sha256"] == run_json(out)["manifest_sha256"]
    assert m["protocol_lock_sha256"] == file_sha256(out / "protocol.lock.json")

def test_verify_names_an_edited_file(tmp_path):
    out = regex_run(PAPERS, tmp_path, PROTOCOL)
    (out / "answer.json").write_bytes((out / "answer.json").read_bytes() + b" ")
    assert seal.check(out)["mismatched"] == ["answer.json"]
    assert cli.main(["verify", str(out)]) == 1

def test_verify_old_run_says_pre_ev4(tmp_path):
    out = regex_run(PAPERS, tmp_path, PROTOCOL); (out / "manifest.json").unlink()
    assert seal.check(out) == "no manifest (pre-EV4)" and cli.main(["verify", str(out)]) == 0

def test_a_crash_writes_all_expected_files_and_a_failed_manifest(tmp_path):
    corpus = corpus_with_bad_sha_at(2, tmp_path)          # CorpusError at paper 2 of 3
    with pytest.raises(CorpusError):
        regex_run_corpus(corpus, tmp_path / "runs", PROTOCOL, run_id="r")
    root = tmp_path / "runs" / "r"
    assert not (root / "run.json").exists()
    for name in ("locate.json", "evidence.jsonl", "funnel.json", "answer.json", "graph.json", "protocol.lock.json"):
        assert (root / name).is_file()
    m = json.loads((root / "manifest.json").read_text())
    assert m["status"] == "failed" and m["error"].startswith("CorpusError")
    assert "killed or crashed" in str(RunDirExists(root))

def test_report_files_are_never_converted():
    out = subprocess.run(["git", "check-attr", "text", "reports/ev4/runs/x/answer.json"], capture_output=True, text=True, cwd=REPO)
    assert out.stdout.strip().endswith(": text: unset")
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_seal.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evidence webapp -q`. Expected: PASS. The web app's `RunDir.kind` and `complete` are unchanged.
- [ ] **Step 5: Commit** `git commit -am "evidence: sealed runs (manifest.json), failed runs keep every file, verify recomputes hashes (§6.7)"`

### Task 5: `evidence estimate`

**Files:**
- Create: `evidence/estimate.py`, `evidence/tests/test_estimate.py`.
- Modify: `evidence/cli.py` (`sub.add_parser("estimate")` with `--protocol`, `--corpus`, `--strategy gaps|all`, `--extractors`, `--from-run`; a `_dispatch` branch that prints JSON and exits 0; docstring :3-19).

**Interfaces:**
- Consumes: `execute_run` with `selection="regex-only"` into a `tempfile.TemporaryDirectory`, with no provider and no model call.
- Produces: `estimate(...) -> {"papers", "screened_out", "papers_reaching_llm", "calls": {"low", "high"}, "tokens": {"input": {"low","high"}, "output": {"low","high"}}, "basis"}`. The pinned rules:
  - **Papers reaching the LLM:** papers the regex run did not screen out (`funnel.json` `screened`); all papers when there is no screen block.
  - **`calls.high`:** papers reaching the LLM × (LLM screen positions + every `llm`/`agent` position of every type's cascade).
  - **`calls.low`:** under `gaps`, papers reaching the LLM × (LLM screen positions + LLM/agent positions at cascade position 0); under `all`, it equals `high`.
  - **Input tokens per call:** `ceil(len(paper text) / CHARS_PER_TOKEN) + PROMPT_TOKENS`, with `CHARS_PER_TOKEN = 4` and `PROMPT_TOKENS = 1500`.
  - **Output tokens per call:** `OUTPUT_TOKENS = 1024`.
  - **`--from-run R`:** input and output per call are R's `cost.input_tokens / cost.made_model_calls` and `cost.output_tokens / cost.made_model_calls`, and `basis = "run <run_id>"`. Otherwise `basis = "chars/4"`.
  - `calls` counts extractor and screen calls. Model calls can be more (chunks, retries), and the JSON says so in `"note"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_estimate_needs_no_model(monkeypatch):
    monkeypatch.setattr(engine, "default_provider", lambda alias: pytest.fail("model"))
    e = estimate(PROTOCOL_FUNNEL, CORPUS)
    assert e["papers"] == n_papers(CORPUS) and e["calls"]["low"] <= e["calls"]["high"]

def test_actual_llm_calls_fall_inside_the_estimate(tmp_path):
    e = estimate(PROTOCOL_FUNNEL, CORPUS)
    out = run(PROTOCOL_FUNNEL, CORPUS, tmp_path, provider=scripted_any(), workers=1)
    llm = llm_and_screen_calls(out)        # extractor_call events of kind llm/agent
    assert e["calls"]["low"] <= llm <= e["calls"]["high"]

def test_screened_out_papers_reach_no_llm():
    e = estimate(PROTOCOL_FUNNEL, CORPUS_WITH_IRRELEVANT)
    assert e["papers_reaching_llm"] == e["papers"] - e["screened_out"]

def test_from_run_uses_the_runs_tokens_per_call(tmp_path):
    prior = run(PROTOCOL_FUNNEL, CORPUS, tmp_path, provider=scripted_any(), workers=1)
    assert estimate(PROTOCOL_FUNNEL, CORPUS, from_run=prior)["basis"].startswith("run ")
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_estimate.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evidence -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evidence: estimate calls and tokens before a run (D41)"`

### Task 6: Cost per system and the losses-first table

Plan 2 must be merged first: the headline fields of its kinds are needed.

**Files:**
- Create: `evaluation/losses.py`, `evaluation/tests/test_losses.py`.
- Modify:
  - `evaluation/score.py`: add `system_cost(answer: dict, run: dict | None) -> dict`. Each `synthesis` entry made in `score()` :1329-1359 and `score_answers()` :1362-1379 gets a `cost` key; `report["domain"] = protocol.domain` (default `"rag"`).
  - `evaluation/report.py`: in `render()` :125-257, a `## Cost per system` table right after C, with columns `system, model_calls, input_tokens, output_tokens, tokens`.
  - `evaluation/cli.py:213-298`: `evaluate losses --scores DIR --out DIR`.

**Interfaces:**
- **`system_cost`:**
  - Engine: from `run.json` `cost` (`model_calls`, `input_tokens`, `output_tokens`).
  - RAG baseline: `model_call` plus `mapping_call` (`evaluation/baselines/common.py:175-177`, `rag.py:227-228`); `model_calls` = 1 + (mapping_call is not None).
  - Agent baseline: its `agent` block (`baselines/agent.py:91-93`): `model_calls`, `tokens` (in and out null when not split), plus its mapping call.
  - `tokens = input + output` when both are known.
- **`headline(kind, system)`:** the overall `level == "all"` row where there is one.
  - effect: `direction_accuracy`
  - inventory: `f1`
  - best: `per_study_accuracy`
  - consistency: `per_study_accuracy`
  - `"chaining"`, `"limitations"`, `"builds_on"`: the row's `headline` key, which plan 2's scorer writes. A missing key raises `KeyError` naming the kind.
- **Engine loss:** the engine's headline is lower than the best baseline's, or (effect) `label_correct` is false, or (best) `winner_correct` is false.
- **`loss_cause(report)`**, the first that holds:
  1. `extraction.missed` non-empty for the scored types → `"missed"`;
  2. B accuracy < 1 (`association_accuracy`, or the kind's B accuracy from `KIND_B`) → `"wrongly linked"`;
  3. `unresolved_names > 0` in the run, or inventory `split`/`merged` > 0 → `"names not grouped"`;
  4. otherwise → `"wrong rule"`.
- **`losses(reports)`:** `{"domains": {"<domain>": [{"question_id", "kind", "systems": {system: headline}, "cost": {system: cost}, "engine_loss": bool, "cause": str|None, "report": "<group>~<name>"}]}}`, losses first, then by `question_id`.
- **Files:** `losses.json` and `losses.md`. `losses.md` opens the comparison section with: "We should not assume that the evidence-level approach will necessarily perform better" (Tim, §7).

- [ ] **Step 1: Write the failing tests**

```python
def test_baseline_cost_counts_both_calls():
    c = system_cost(rag_answer(model_call={"input_tokens": 900, "output_tokens": 100}, mapping_call={"input_tokens": 50, "output_tokens": 10}), None)
    assert c == {"model_calls": 2, "input_tokens": 950, "output_tokens": 110, "tokens": 1060}

def test_losses_come_first_with_one_cause():
    out = losses([report("q1", engine=0.9, rag=0.5), report("q2", engine=0.4, rag=0.8, missed=["f1"])])
    rows = out["domains"]["rag"]
    assert [r["question_id"] for r in rows] == ["q2", "q1"] and rows[0]["cause"] == "missed" and rows[1]["cause"] is None

@pytest.mark.parametrize("fields,cause", [({"assoc": 0.5}, "wrongly linked"), ({"unresolved_names": 3}, "names not grouped"), ({}, "wrong rule")])
def test_each_cause(fields, cause):
    assert loss_cause(report("q", engine=0.1, rag=0.9, **fields)) == cause

def test_new_kind_without_headline_is_named():
    with pytest.raises(KeyError, match="chaining"):
        headline("chaining", {"rows": [{"level": "all"}]})

def test_losses_md_opens_with_tims_sentence(tmp_path):
    write_losses(losses([report("q1", engine=0.1, rag=0.9)]), tmp_path)
    assert "We should not assume that the evidence-level approach will necessarily perform better" in (tmp_path / "losses.md").read_text().split("##")[1]
```

- [ ] **Step 2:** Run `uv run pytest evaluation/tests/test_losses.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evaluation -q`. Expected: PASS. Golden report files gain `cost`/`domain` keys; update them in this commit with the reason in the message.
- [ ] **Step 5: Commit** `git commit -am "evaluation: cost per system and losses-first table (§6.16, D41)"`

### Task 7: `evidence fetch`: arXiv HTML first, Docling fallback, `--ids`

**Files:**
- Modify:
  - `evidence/arxiv.py`:
    - replace `pdf_markdown` :159-172 with `docling_markdown(data: bytes, kind: Literal["html","pdf"]) -> str` (Docling `DocumentConverter`; PDF options `PdfPipelineOptions(do_ocr=False, do_table_structure=True)` as in `scripts/build-corpus.py`);
    - add `paper_body(entry: Entry, client: Client, convert=docling_markdown) -> tuple[str, Literal["html","pdf"], str, str | None]` returning (body, source, source sha256, fallback reason);
    - replace the call site :205-210;
    - manifest rows :219-221 get `source`, and `html_sha256` or `pdf_sha256`;
    - `source.json` :227-230 gets `converter: f"docling {_version('docling')}"`, `"html": n`, `"pdf": n` and per-paper `fallbacks`;
    - `fetch(...)` takes `ids: list[str] | None` (API `id_list=`, mutually exclusive with `query`);
    - `add_parser` :252-257 gets `--ids FILE` (one id per line) in a mutually exclusive group with `--query`.
  - `pyproject.toml`: remove `pymupdf4llm==1.28.2` from `dependencies`; add `[dependency-groups] fetch = ["docling==2.110.0"]`. A missing Docling gives `FetchError("Docling is not installed: uv sync --group fetch")`.
  - `webapp/evjobs.py:238-254`: the fetch job runs with the `fetch` group.
- Test: `evidence/tests/test_arxiv.py` (extend).

**Interfaces:**
- **HTML URL:** `https://arxiv.org/html/<id>` (the id with its version).
- **HTML accepted** when the status is 200, the body contains `ltx_page_main` (the LaTeXML marker; the builder confirms it on 3 live pages and notes them in the commit message), and the converted text has at least `MIN_HTML_CHARS = 2000` characters. Otherwise the PDF is used and the reason is kept.
- **Fallback reasons:** `"html 404"`, `"html: no LaTeXML page"`, `"html: 812 chars"`.
- Both requests go through `Client.get` (the 3-second spacing is unchanged).

- [ ] **Step 1: Write the failing tests**

```python
def test_html_is_preferred(tmp_path):
    src = fetch_with(tmp_path, html=LTX_PAGE, pdf=PDF, convert=fake_convert)
    assert src["html"] == 1 and manifest(tmp_path)["papers"][0]["source"] == "html"

@pytest.mark.parametrize("html,reason", [(None, "html 404"), (b"<html>Error</html>", "html: no LaTeXML page"), (SHORT_LTX, "html: ")])
def test_bad_html_falls_back_to_pdf_with_reason(tmp_path, html, reason):
    src = fetch_with(tmp_path, html=html, pdf=PDF, convert=fake_convert)
    assert src["pdf"] == 1 and src["fallbacks"][0]["reason"].startswith(reason)

def test_both_failing_skips_with_both_reasons(tmp_path):
    with pytest.raises(FetchError, match="no paper could be fetched"):
        fetch_with(tmp_path, html=None, pdf=None, convert=fake_convert)
    # the skipped entry (logged) names "html 404" and the PDF error

def test_ids_fetch_uses_id_list():
    assert captured_params(ids=["2411.18583v1"])["id_list"] == "2411.18583v1"

def test_source_names_docling():
    assert fetch_with_tmp()["converter"].startswith("docling ")
```

`fetch_with` uses a transport built on `httpx.MockTransport`, as the existing tests in `test_arxiv.py` do, and `Client(delay=0, sleep=lambda _: None)`.

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_arxiv.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. `uv remove pymupdf4llm` and `uv add --group fetch docling==2.110.0`.
- [ ] **Step 4:** Run `uv run pytest evidence webapp -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evidence: fetch prefers arXiv HTML, Docling fallback, --ids (D40)"`

### Task 8: Real-paper check: SciREX names at two levels

**Files:**
- Create:
  - `evaluation/realpapers/__init__.py`, `evaluation/realpapers/common.py` (`write_real(result: dict, out: Path, title: str) -> tuple[Path, Path]`: `real.json` plus `real.md` whose first line is `# real-paper check: <title> (not a synthetic score)`);
  - `evaluation/realpapers/scirex.py`;
  - `domains/ml/` (pack: types `method` compared_thing, `dataset` context, `task` context, `metric` metric, `measurement` measured_value; `ontology.ttl` CS-KG seed; a protocol `protocols/names.yaml` of kind `inventory` with target `method` and all four name types);
  - `evaluation/tests/test_scirex.py`, `evaluation/tests/data/scirex_tiny.jsonl`.
- Modify: `evaluation/cli.py` (`evaluate scirex corpus --jsonl F --out DIR [--limit N]`, `evaluate scirex score --run R --corpus C --out D`).

**Who writes `domains/ml`:** a fresh helper that reads only the text of 10 SciREX **train**-split papers, never the test split, any gold, or SciLead. Its work is logged in `provenance.json`, and the pack is frozen under tag `ev4-ml-pack` before any scored run (§6.11, "Frozen before scored").

**Interfaces:**
- **`to_corpus(jsonl: Path, out: Path, *, limit: int | None = None) -> Path`:**
  - writes `manifest.json` and `papers/<doc_id>.md` (words joined by single spaces, sections by `"\n\n"`, so a token-to-character map is exact);
  - writes `scirex_gold.json`: `{doc: {"mentions": [[start_char, end_char, type, text]], "clusters": {name: [[s, e]]}, "salient": [name]}}`;
  - salient clusters are the cluster names that occur in `n_ary_relations`. The builder confirms this against the SciREX README and writes what the gold holds into `real.md`.
- **`score(run_dir: Path, corpus: Path) -> dict`**, per SciREX type (`Method→method, Dataset→dataset, Task→task, Metric→metric`):
  - **Mention level:** an item is right when one of its spans overlaps a gold mention of the same type. Precision is right items over items; recall is matched mentions over mentions.
  - **Salient-cluster level** (headline): an extracted name is right when its `names.clean` equals the cleaned text of any mention of a salient cluster of that type. Recall is clusters hit over salient clusters; precision is distinct right names over distinct names.
- The output reports the number of papers and that the estimate (Task 5) was used to choose `--limit` (§8: "the number of SciREX papers (reported)").

- [ ] **Step 1: Write the failing tests**

```python
def test_corpus_offsets_match_tokens(tmp_path):
    c = to_corpus(TINY, tmp_path)
    gold = json.loads((c / "scirex_gold.json").read_text())["d1"]
    text = (c / "papers/d1.md").read_text()
    assert [text[s:e] for s, e, *_ in gold["mentions"]] == ["BERT", "SQuAD"]

def test_engine_never_reads_scirex_gold(tmp_path):
    c = to_corpus(TINY, tmp_path); (c / "scirex_gold.json").write_text("not json")
    regex_run_corpus(c, tmp_path / "runs", ML_NAMES_PROTOCOL)   # must not fail

def test_two_levels(tmp_path):
    r = score(run_with_items(tmp_path, [("method", "bert", (0, 0))]), to_corpus(TINY, tmp_path / "c"))
    assert r["mention"]["method"]["recall"] == 0.0 and r["salient"]["method"]["recall"] == 1.0

def test_real_md_says_real_paper_check(tmp_path):
    write_real({"papers": 1}, tmp_path, "SciREX test split")
    assert (tmp_path / "real.md").read_text().startswith("# real-paper check: SciREX test split (not a synthetic score)")
```

- [ ] **Step 2:** Run `uv run pytest evaluation/tests/test_scirex.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evaluation evidence -q`. Expected: PASS (`evidence pack check ml` passes for kind inventory).
- [ ] **Step 5: Commit** `git commit -am "evaluation: SciREX real-paper check at mention and salient-cluster level (D21)"`

### Task 9: Real-paper check: Yun et al. 2024 and Evidence Inference

Plan 2's `domains/drugtrials` pack, frozen, is needed first.

**Files:**
- Create: `evaluation/realpapers/yun.py`, `evaluation/tests/test_yun.py`, `evaluation/tests/data/yun_tiny/` (a 3-row CSV with the real header, 2 markdown papers, a 3-row Evidence Inference prompts/labels file).
- Modify: `evaluation/cli.py` (`evaluate yun corpus --repo DIR --ei DIR --out C`, `evaluate yun score --run R --corpus C --out D`).

**Sources:**
- github.com/hyesunyun/llm-meta-analysis, `evaluation/data/annotated_rct_dataset.csv`, Apache-2.0;
- Evidence Inference 2.0, MIT, from the GitHub copy `annotations/`.

The builder pins both commit hashes in `real.md` and copies the exact CSV header into the fixture.

**Interfaces:**
- **`to_corpus(repo: Path, ei: Path, out: Path) -> Path`:** papers from the repo's markdown, plus `yun_gold.json`:
  `{doc: [{"intervention", "comparator", "outcome", "kind": "binary"|"continuous", "values": {...} | null, "ei_label": "significantly increased"|"significantly decreased"|"no significant difference" | null, "complete": bool}]}`.
  - `complete` is true when every number of the record's kind is present: events and group size per arm (binary), or mean and SD per arm (continuous).
- **`score(run_dir, corpus) -> dict`.** A, B and C are reported separately. The run's comparisons are plan 2's comparisons output.
  - **A names** (all records): intervention and comparator found among compared-thing items, and outcome found among metric items, by equal `names.clean` or the same name group (`names.json`).
  - **A values** (complete records only): a measured-value item whose value is within 0.005 (absolute) of events/size (binary) or within 1% (relative) of the mean (continuous).
  - **B** (complete records only): that item links to the matched arm and the matched outcome.
  - **C** (records with an `ei_label`): the engine's direction for (I, C, O) is compared with the label. Pinned: delta > 0 and not neutral → "significantly increased"; delta < 0 and not neutral → "significantly decreased"; neutral (below `min_effect`) → "no significant difference".
  - **Output:** `{"records", "complete", "complete_share", "A_names", "A_values", "B", "C"}`, with `real.md` stating "records without complete numbers are scored on names and direction only".

- [ ] **Step 1: Write the failing tests**

```python
def test_incomplete_record_is_scored_on_names_and_direction_only(tmp_path):
    r = score_tiny(tmp_path)
    assert r["A_values"]["records"] == r["complete"] and r["A_names"]["records"] == r["records"]

def test_count_value_matches_events_over_size(tmp_path):
    assert score_tiny(tmp_path, items=[measure("p1", 41 / 120, arm="Zelvora", outcome="response rate")])["A_values"]["matched"] == 1

@pytest.mark.parametrize("delta,neutral,label", [(0.1, False, "significantly increased"), (-0.1, False, "significantly decreased"), (0.001, True, "no significant difference")])
def test_direction_mapping(delta, neutral, label):
    assert direction_label(delta, neutral) == label

def test_complete_share_is_reported(tmp_path):
    assert 0 <= score_tiny(tmp_path)["complete_share"] <= 1
```

- [ ] **Step 2:** Run `uv run pytest evaluation/tests/test_yun.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evaluation -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evaluation: Yun et al. + Evidence Inference real-paper check, A/B/C separately (D42)"`

### Task 10: Real-paper check: SciLead "best" and chains

**Files:**
- Create: `evaluation/realpapers/scilead.py`, `evaluation/tests/test_scilead.py`, `evaluation/tests/data/scilead_tiny/`.
- Modify: `evaluation/cli.py` (`evaluate scilead ids --data DIR --out ids.txt`, `evaluate scilead score --run R --corpus C --data DIR --out D`).

**Source:** the ACL Anthology attachment `2024.emnlp-main.453.data.zip`. The builder confirms the URL, the file layout and how papers are identified, and records them in `real.md`.

**Interfaces:**
- **Papers:** `ids(data: Path) -> list[str]` gives arXiv ids. Papers are fetched with `evidence fetch --ids ids.txt` (Task 7) into a corpus. A paper with no arXiv id is listed as not fetched.
- **Gold:** `gold(data: Path) -> {"tuples": {paper: [(task, dataset, metric, result)]}, "leaderboards": [{"task", "dataset", "metric", "ranking": [paper, ...], "higher_is_better": bool}]}`.
- **`score(run_dir, corpus, data) -> dict`:**
  - **Value found:** a measured-value item in the paper whose value equals the gold result within 0.005 after percent normalisation (both read with plan 1's `read_numbers`).
  - **Link:** that item links to a metric item whose cleaned name equals the gold metric or is in its name group.
  - **Best:** per leaderboard, the engine ranks papers by their found values for that (dataset, metric) in the leaderboard's direction. A match is engine top-1 == gold top-1, reported as "N of 27".
  - **Chains:** the share of paper pairs, both found, ordered as in the gold.
  - The method→value link is not scored, and `real.md` says why ("each value is the paper's best number", §6.12).

- [ ] **Step 1: Write the failing tests**

```python
def test_best_matches_when_top_paper_agrees(tmp_path):
    r = score_tiny(tmp_path, values={"p1": 0.9, "p2": 0.8})
    assert r["best"]["matched"] == 1 and r["best"]["leaderboards"] == 1

def test_lower_is_better_leaderboard(tmp_path):
    assert score_tiny(tmp_path, values={"p1": 0.2, "p2": 0.1}, higher=False)["best"]["matched"] == 1

def test_pair_order_share(tmp_path):
    assert score_tiny(tmp_path, values={"p1": 0.9, "p2": 0.8, "p3": 0.85})["chains"]["agree_share"] == pytest.approx(2 / 3)

def test_percent_and_fraction_values_match(tmp_path):
    assert score_tiny(tmp_path, values={"p1": 0.905}, gold_result="90.5")["values"]["found"] == 1
```

- [ ] **Step 2:** Run `uv run pytest evaluation/tests/test_scilead.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evaluation -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evaluation: SciLead real-paper check, best and chains (D42)"`

### Task 11: arXiv edit test and hand-check sheets

**Files:**
- Create: `evaluation/realpapers/edits.py`, `evaluation/realpapers/sheet.py`, `evaluation/tests/test_edits.py`, `evaluation/realpapers/data/arxiv-edits.yaml` (written in Step 6).
- Modify: `evaluation/cli.py`: `evaluate edits apply --corpus C --edits F --out DIR`, `evaluate edits check --original R --runs DIR --edits F --out D`, `evaluate sheet --run R --corpus C (--sample N | --papers N) [--seed 0] --out F.csv`, `evaluate sheet-summary F.csv`.

**Interfaces:**
- **`Edit(Strict)`:** `id: str; paper: str; kind: Literal["number","name","limitation"]; find: str; replace: str`. A `limitation` edit uses `replace=""`.
- **`apply(corpus: Path, edit: Edit, out: Path) -> Path`:** one corpus per edit; only that paper changes, and its manifest sha256 is updated. `find` must occur exactly once in the paper, else `EditError` naming the edit id and the count.
- **`check(original: Path, edited: Path, edit: Edit) -> {"item": bool, "link": bool, "answer": bool}`:**
  - `number`: an item whose span covers the new text has the new value (by `read_numbers`); its links point to items with the same fields as before; the answer entry for that paper differs.
  - `name`: a compared-thing item named `replace` exists in the paper and none named `find`; measurements that linked to the old item link to the new one; the answer names `replace`.
  - `limitation`: the limitation item over the deleted sentence is gone; the paper's limitation count in the `"limitations"` answer drops by 1. The link part is true when no item links to the deleted one.
  - **Summary:** the share of edits carried through per part, and over all three.
- **`sheet(...)`:** a CSV with columns `item_id, paper, type, fields, sentence, right_or_wrong, note`. `sentence` is the text around the span, cut at sentence ends. `--sample N` draws N random items (`random.Random(seed)`); `--papers N` takes every item of the first N papers in manifest order.
- **`summarise(csv) -> {"n", "right", "precision", "wilson95": [lo, hi]}`:** Wilson interval with z = 1.96; blank rows are not counted.
- **Arxiv demo sheet:** `--papers 5` on the demo run. Its `real.md` heading says "demonstration, not an evaluation".

- [ ] **Step 1: Write the failing tests**

```python
def test_find_must_occur_once(tmp_path):
    with pytest.raises(EditError, match="e1.*2 times"):
        apply(corpus_with("0.71 and 0.71"), Edit(id="e1", paper="p1", kind="number", find="0.71", replace="0.31"), tmp_path)

def test_number_edit_carries_through(tmp_path):
    orig, edited = run_pair(tmp_path, Edit(id="e1", paper="p1", kind="number", find="0.71", replace="0.31"))
    assert check(orig, edited, EDIT) == {"item": True, "link": True, "answer": True}

def test_name_swap_moves_the_links(tmp_path):
    orig, edited = run_pair(tmp_path, Edit(id="e2", paper="p1", kind="name", find="System R", replace="System Q"))
    assert check(orig, edited, EDIT2)["link"]

def test_wilson_interval():
    s = summarise(csv_rows(right=80, wrong=20))
    assert s["precision"] == 0.8 and s["wilson95"] == pytest.approx([0.7112, 0.8666], abs=1e-3)

def test_sample_is_reproducible(tmp_path):
    assert sheet_rows(tmp_path, sample=100, seed=0) == sheet_rows(tmp_path, sample=100, seed=0)
```

- [ ] **Step 2:** Run `uv run pytest evaluation/tests/test_edits.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evaluation -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evaluation: arXiv edit test and hand-check sheets with Wilson intervals"`
- [ ] **Step 6:** Fetch the 5 arXiv RAG papers locally (`evidence fetch --ids`, D32). Write `arxiv-edits.yaml` with 3-5 edits per paper (at least one of each kind across the set), freeze it before any run, and commit: `git commit -m "data: arXiv edit set (frozen before runs)"`.

### Task 12: Web app: Scores page out, Report page for all runs, scores on the Run page

**Files:**
- Delete: `webapp/web/src/pages/ev/ScoresPage.tsx`.
- Modify:
  - `webapp/web/src/app/routes.tsx`: drop :27 and :54; add `report` → new `ReportsPage` and `{ path: "scores", element: <Navigate to="/report" replace /> }`; move `scores/reports/:id`, `compares`, `shifts`, `benchmarks` to `report/...` and keep the old paths as `Navigate` redirects.
  - `components/layout/pages.ts:12`: `{ to: "/report", label: "Report", icon: BarChart3Icon }`.
  - Back links: `ReportPage.tsx:181`, `ComparePage.tsx:22`, `ShiftPage.tsx:24`, `BenchmarkPage.tsx:19`.
  - Links: `RunPage.tsx:154`, `RunStep.tsx:294`, `lib/jobs.ts:47-48`, `HomePage.tsx:30` (text "score reports" kept).
  - `ResultSteps.tsx:4` (comment).
  - `pages/ev/RunPage.tsx`: add a "Scores" tab for an engine run with a report (the run's `reports[0]`, read through `useReport`): C, A and the cost per system rows from Task 6, plus the link flags count as "values linked to the wrong kind of thing: N".
  - `api/ev.ts`: `useLosses`.
  - `mocks/ev.ts`, `mocks/ev-fixtures.json` (losses fixture).
  - `pages/ev/ev-pages.test.tsx:24, :159, :342-383`: paths `/report...`.
- Create: `webapp/web/src/pages/ev/ReportsPage.tsx`.
- Backend:
  - `webapp/evfiles.py`: `losses() -> LossesView` reads `<scores root>/losses/losses.json` and `.md`; `run()` :578-609 adds `link_flags: int | None` from `reason.json`.
  - `webapp/evapi.py`: `@api.get("/losses", response_model=LossesView)`.
  - `webapp/evmodels.py`: `LossesView`; `EvRunDetail.link_flags`.
  - Regenerate `uv run webapp openapi -o webapp/web/openapi.json`, then `npm --prefix webapp/web run gen:api`.

**Interfaces:**
- Consumes: Task 6 `losses.json`, `system_cost` rows.
- Produces: `GET /api/ev/losses`. `ReportsPage` shows, per domain, the losses table first, with one cause line per engine loss and model calls and tokens per system beside the scores. Below it are the per-run report, comparison, shift and benchmark lists that the Scores page had.

- [ ] **Step 1: Write the failing tests** (in `ev-pages.test.tsx`, plus `webapp/tests/test_evidence_api.py`)

```tsx
it("has no Scores page; /scores goes to the Report", async () => {
  const { router } = renderRoutes(routes, "/scores")
  await screen.findByRole("heading", { name: "Report" }, T)
  expect(router.state.location.pathname).toBe("/report")
  expect(screen.queryByRole("link", { name: "Scores" })).toBeNull()
})
it("the Report lists losses first with their cause and costs", async () => {
  renderRoutes(routes, "/report")
  const rows = within(await screen.findByRole("table", { name: "Questions, losses first" }, T)).getAllByRole("row")
  expect(rows[1]).toHaveTextContent("missed")
  expect(screen.getByRole("table", { name: "Model calls and tokens per system" })).toBeInTheDocument()
})
it("a run shows its own scores", async () => {
  renderRoutes(routes, `${run(`cascade-gaps~${MIXED}`)}?tab=scores`)
  expect(await screen.findByRole("table", { name: "Synthesis per system" }, T)).toBeInTheDocument()
})
```

```python
def test_losses_endpoint_reads_the_file(client, world):
    world.write_losses({"domains": {"rag": []}})
    assert client.get("/api/ev/losses").json()["losses"]["domains"] == {"rag": []}
```

- [ ] **Step 2:** Run `npm --prefix webapp/web test -- --run` and `uv run pytest webapp -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run both again. Expected: PASS. Then run `npm --prefix webapp/web run typecheck` and `npm --prefix webapp/web run build` (`dist/` is committed).
- [ ] **Step 5: Commit** `git commit -am "webapp: Scores page removed; Report page for all runs, losses first; scores on the Run page (§6.14, §6.16)"`

### Task 13: Web app: three-column evidence graph (Papers → Claims → Verdict)

Plan 2 must be merged first for the `limitations`, `builds_on` and `chaining` answers.

**Files:**
- Create: `webapp/web/src/lib/claimgraph.ts`, `webapp/web/src/lib/claimgraph.test.ts`, `webapp/web/src/components/ev/ClaimGraph.tsx`.
- Modify:
  - `pages/ev/RunPage.tsx:34-51` (`GraphTab` shows `ClaimGraph`; the old `EvidenceGraph` stays behind a "raw items" switch for debugging);
  - `webapp/evfiles.py` / `evmodels.py` (`EvRunDetail.display: dict[str, str]` from the run's pack `Pack.display`, so treatment and control show the topic's own names).
- **First step of this task:** the builder reviews the EV3 graph (`EvidenceGraph.tsx`, `lib/evgraph.ts`) on one engine run and writes the list of what is dropped into `ClaimGraph.tsx`'s doc comment. The expected drops are `in_document` edges, metric and condition nodes by default, and the per-paper selector.

**Interfaces:**
- **`claimsOf(answer, kind) -> Claim[]`:** one case per kind.
  - effect / best / consistency: a determined study with treatment and control values, labelled `"<treatment display> <t value> vs <control display> <c value> on <metric>"`;
  - `"limitations"`: one claim per limitation entry;
  - `"builds_on"`: one claim per dependency link;
  - `"chaining"`: one claim per chain step.
  - The fields are read from plan 2's answer shapes in this one function only.
- **`toClaimFlow(graph: EvGraph, answer, kind, display) -> {nodes, edges}`:**
  - three dagre ranks pinned by node rank: Papers x-rank 0, Claims 1, Verdict 2, using `rankdir: "LR"` with `rank` constraints;
  - the Verdict node is the kind's answer text and its rule name.
- **Edges:**
  - `supports`: solid `var(--status-good)`, label "supports";
  - `contradicts`: solid `var(--status-critical)`, label "contradicts";
  - neutral: `var(--muted-foreground)`;
  - dependencies (`builds_on`) and chains: dashed `"6 4"`, labels "builds on" / "inferred through <B>".
  - Edges always carry a text label, so colour is never the only cue.
- **Internal items** (conditions, metrics, measurements) are hidden. Clicking a claim opens a `Sheet` listing its items, each linking to the paper view at its span.
- Below the canvas, the node and edge lists stay, as `EvidenceGraph.tsx` has them.

- [ ] **Step 1: Write the failing tests**

```ts
it("places papers, claims and the verdict in three columns", () => {
  const { nodes } = toClaimFlow(GRAPH, EFFECT_ANSWER, "effect", DISPLAY)
  const x = (k: string) => Math.max(...nodes.filter((n) => n.data.column === k).map((n) => n.position.x))
  expect(x("paper")).toBeLessThan(Math.min(...nodes.filter((n) => n.data.column === "claim").map((n) => n.position.x)))
  expect(x("claim")).toBeLessThan(nodes.find((n) => n.data.column === "verdict")!.position.x)
})
it("hides internal items until a claim is clicked", () => {
  expect(toClaimFlow(GRAPH, EFFECT_ANSWER, "effect", DISPLAY).nodes.some((n) => ["condition", "metric", "measurement"].includes(n.data.type))).toBe(false)
})
it("draws chains and dependencies dashed and labelled", () => {
  const { edges } = toClaimFlow(GRAPH, CHAIN_ANSWER, "chaining", DISPLAY)
  expect(edges.filter((e) => e.data?.rel === "chain").every((e) => e.style?.strokeDasharray === "6 4" && String(e.label).startsWith("inferred through"))).toBe(true)
})
it("uses the topic's names for the two sides", () => {
  expect(claimsOf(EFFECT_ANSWER, "effect")[0].label).toContain(DISPLAY.treatment)
})
```

Also replace the page test at `ev-pages.test.tsx:162-178`: the graph tab shows `group` "Evidence graph" with the three column headings "Papers", "Claims", "Verdict", and clicking a claim opens a dialog listing its items.

- [ ] **Step 2:** Run `npm --prefix webapp/web test -- --run`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests again (PASS), then `typecheck` and `build`.
- [ ] **Step 5: Commit** `git commit -am "webapp: readable evidence graph, Papers -> Claims -> Verdict (§6.14)"`

### Task 14: No ontology words and no topic words in the web app

**Files:**
- Modify:
  - `evidence/tests/test_no_topic_words.py` (plan 1): `CHECKED_DIRS` gets `"webapp"`. `code_files` also reads `*.ts` and `*.tsx` under `webapp/web/src`, excluding `node_modules`, `dist`, `mocks`, `*.test.ts(x)`, `src/api/schema.d.ts` and `openapi.json`.
  - Move any remaining topic words in `webapp/` (e.g. "RAG system" labels in `lib/ev.ts`) to the pack's `display`, served through `EvRunDetail.display`, or to `domains/allowlist.yaml` with a reason.
- Create: `webapp/web/src/lib/no-ontology-words.test.tsx`.

- [ ] **Step 1: Write the failing tests**

```tsx
const JARGON = /\b(owl|ontology|ontologies|class|subclass|superclass|rdf|rdfs|cskg|iri)\b/i
it.each(["/report", `/runs/${encodeURIComponent(`cascade-gaps~${MIXED}`)}?tab=dev&dev=graph`, `/runs/${encodeURIComponent(`cascade-gaps~${MIXED}`)}?tab=scores`])(
  "%s shows no ontology words", async (path) => {
    renderRoutes(routes, path)
    await screen.findByRole("main", {}, T)
    expect(document.body.textContent ?? "").not.toMatch(JARGON)
  })
it("source strings shown to users carry no ontology words", () => {
  for (const [file, text] of Object.entries(import.meta.glob("/src/{pages,components,lib}/**/*.tsx", { eager: true, query: "?raw", import: "default" })))
    if (!file.includes(".test.")) expect(userStrings(text as string).filter((s) => JARGON.test(s)), file).toEqual([])
})
```

`userStrings` takes JSX text nodes and the string literals given to `title`, `description`, `label` and `aria-label` (a regex helper in the test file). The run fixture includes a `reason.json` with link flags, so the flags line is on screen.

- [ ] **Step 2:** Run `npm --prefix webapp/web test -- --run` and `uv run pytest evidence/tests/test_no_topic_words.py -q`. Expected: FAIL listing hits.
- [ ] **Step 3:** Fix each hit by rewording, moving it to the pack's `display`, or adding it to the allowlist with a reason.
- [ ] **Step 4:** Run both again, plus `uv run pytest -q`. Expected: PASS apart from the known failures.
- [ ] **Step 5: Commit** `git commit -am "test: no ontology words in the web app (D13); webapp in CHECKED_DIRS"`

### Task 15: Codex runbook `docs/runbook-ev4.md`

All tasks and plan 2 must be merged into `ev4/should` first.

**Files:**
- Create: `docs/runbook-ev4.md`, `evidence/tests/test_runbook_ev4.py`.

**Structure** (as `docs/runbook-ev3b.md`: title "(Codex)", preamble, "What changed in the code (all on `ev4-code`)", "Decisions by Aditya", "Rules that differ", numbered sections):
- **Rules:**
  - Code tag `ev4-code`; packs frozen under their tags (`domains/rag`, `domains/drugtrials`, `domains/ml`), and every file changed after a tag is logged in the report;
  - session dir `$EV=/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-ev4`;
  - reports under `reports/ev4/`, branch **`results-ev4`** from `origin/results`, tag **`ev4`**;
  - "Never push to `main` or `results`"; **USER** marks every stop.
- **§0 Branch and setup:** `git checkout --detach ev4-code`, `git describe --tags`, submodule, `uv sync --locked --all-groups` (includes the `fetch` group).
- **§1 Offline check:**
  - `uv run pytest -q` (record the count);
  - `evidence pack check rag`, `drugtrials`, `ml`;
  - `evidence protocol diff` of each scored protocol against its frozen tag copy (must print `same`).
- **§2 Estimate before every Slurm run (D41):** `evidence estimate --protocol P --corpus C` for every cell. Write the JSON into `$EV/estimates/`. Stop (**USER**) when `calls.high` is more than 2× the plan in `session.json`.
- **§3 RAG rerun:** the four kinds (effect, inventory, consistency, best) from `domains/rag/questions.yaml` × the RAG corpora × three systems (engine, `rag-per-paper` as main RAG row, agent v3), using the `one.sh` / `grid.sh` pattern of `runbook-question-first.md` §4. EV3 numbers are never a comparison point (§6.8).
- **§4 Drug trials:** all kinds of `domains/drugtrials/questions.yaml` (effect, inventory, consistency, best, chaining, limitations, builds_on) × three systems, with the baseline map prompts.
- **§5 Real-paper checks:** SciREX (`--limit` from §2), Yun et al. + Evidence Inference, SciLead (`fetch --ids`), the arXiv edit test (the frozen `arxiv-edits.yaml`). Each goes to `reports/ev4/real/<name>/` and is never mixed with synthetic scores.
- **§6 arXiv demo:** about 30 papers by `evidence fetch` (HTML first), the frozen RAG protocols, `evaluate sheet --papers 5`, the sample precision labelled "demonstration, not an evaluation".
- **§7 Checks, per run:**
  - `evidence verify` ok;
  - `manifest.json` `status: complete`;
  - `dangling_links` 0;
  - `unresolved_names` reported;
  - `reason` on with `link_flags` counted;
  - the lock's pack and ontology digests equal to the frozen tag;
  - failed runs go to `$RUNS/failed/<corpus>/` as before.
- **§8 Deliverable `reports/ev4/summary.md`:**
  - `evaluate losses` output first (losses first, cause lines, Tim's sentence opening the comparison);
  - cost per system;
  - real-paper section;
  - demo section;
  - Limits;
  - the "Paperwork" grep (`grep -n "Pending\|running"` prints nothing).
- **§9 Hand-back:** the ev3b §7 command block with `results-ev4` / `ev4` / `reports/ev4`, including the staged-runs check.

- [ ] **Step 1: Write the failing test**

```python
def test_every_command_in_the_runbook_exists():
    text = (REPO / "docs/runbook-ev4.md").read_text(encoding="utf-8")
    for tool, sub in set(re.findall(r"^\s*(?:uv run )?(evidence|evaluate) ([a-z-]+)", text, re.M)):
        main = {"evidence": evidence_cli.main, "evaluate": evaluation_cli.main}[tool]
        with pytest.raises(SystemExit) as e:
            main([sub, "--help"])
        assert e.value.code == 0, f"{tool} {sub}"

def test_runbook_names_branch_tag_and_never_main():
    text = (REPO / "docs/runbook-ev4.md").read_text(encoding="utf-8")
    assert "results-ev4" in text and "git tag -a ev4" in text and "Never push to `main` or `results`" in text
    assert "git push origin main" not in text and "git push origin results\n" not in text
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_runbook_ev4.py -q`. Expected: FAIL (no file).
- [ ] **Step 3:** Write `docs/runbook-ev4.md`.
- [ ] **Step 4:** Run `uv run pytest evidence/tests/test_runbook_ev4.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git add docs/runbook-ev4.md evidence/tests/test_runbook_ev4.py && git commit -m "docs: EV4 Codex runbook (RAG rerun, drug trials, real-paper checks, arXiv demo, report)"`

---

## Self-review notes

**Spec coverage:**
- §6.3 → Tasks 1-2 (matching kinds, checking links, inferences recorded, never re-reasoned on replay).
- §6.6 → Task 3.
- §6.7 → Task 4.
- D41 / §6.13 `estimate` → Task 5.
- §6.16 → Tasks 6 and 12.
- §6.12 / D21 / D42 → Tasks 8-11.
- §6.15 / D40 → Tasks 7 and 11 (demo sheet).
- §6.14 → Tasks 12-14.
- §7 step 12 → Task 15.
- D30 (setting off when missing) → Task 2.
- D31 (gold only in the scorer) → Task 8 `test_engine_never_reads_scirex_gold`.

**Decisions taken here, each named in its task:**
- A failed run writes no `run.json`, so "complete" keeps its meaning.
- `verify` is extended, not renamed.
- Docling lives in a `fetch` dependency group.
- `domains/ml` serves both SciREX and SciLead.
- Plan 2's kinds report a `headline` key.

**Names:** `Inferences`, `reason`, `counts_as`, `lock`, `diff`, `seal`, `check`, `estimate`, `losses`, `loss_cause` and `headline` are spelled the same in the Shared names block and in every task.
