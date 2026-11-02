# EV4 Plan 1: Foundation (domain packs, open types, numbers, names) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every RAG topic word out of `evidence/` code into `domains/rag/`, open the closed set of evidence types behind roles, replace RAG-tuned number rules with one general reader, and group names across a corpus, so later plans can add a second topic without touching engine code.

**Architecture:** A frozen `Pack` object (loaded from `domains/<name>/`) is the only source of topic words; `engine.build_extractors` fills each extractor's config from it under the protocol's own config (protocol wins). Evidence types become a registry fed by the pack, and kinds/synthesis address types through a `RoleMap` instead of type names. Two new generic modules: `evidence/extractors/numreader.py` (number forms) and `evidence/names.py` (corpus-wide name groups, a new engine step writing `names.json`).

**Tech Stack:** Python 3.13, pydantic (existing `Strict` models), pyyaml, `rapidfuzz` (new), pytest via `uv run pytest`.

**Spec:** `docs/superpowers/specs/2026-11-01-ev4-general-evidence-system-design.md` (§5, §6.1, §6.2, §6.9 "One general number reader", §6.17, §7 steps 1-3; decisions D1, D8, D23, D24, D28, D35, D36, D38). This is plan 1 of 3; plan 2 (drug trials, steps 4-7) and plan 3 (Should items, steps 8-12) build on the **Shared interfaces** section below.

## Global Constraints

- Branch: `ev4/foundation` from `ev4/spec`. Nothing is merged, tagged or pushed without Aditya's go.
- "No embeddings in retrieval or screening." No change to `llm-setup`.
- "Same model for all systems."
- "Prefer maintained packages (rdflib, owlrl, pydantic, the MCP SDK) over home-made code."
- "Deterministic runs: anything new in a run ... is recorded in the run or frozen in the pack, so a replay never calls a live service."
- D36: old answers do not matter. RAG numbers and item/extractor ids may change. Old runs replay at their own code tag (`ev3b-code`); tests that pin old hashes are retired, not faked.
- D35: no per-topic switches in code. Topic words live only in `domains/<name>/`.
- Pack versus protocol: "If a protocol sets a value ..., the protocol wins; otherwise the pack's value is used."
- A protocol with no `domain:` key means `rag`.
- Every task ends with `uv run pytest evidence -q` passing (on WSL set `UV_PROJECT_ENVIRONMENT=~/.venvs/<name>`, README.md:138), apart from the 3 known Windows-only failures in docs/STATE.md:186.
- Test style: module docstring, `from __future__ import annotations`, `test_<plain_sentence>()` (copy evidence/tests/test_numbers.py:30-52).

## Review Focus

1. A protocol with no `domain:` key, or an old run directory, still loads (pack `rag`), and `Protocol.sha256` of the 12 existing protocols does not change because `domain` is registered in `DIGEST_OMIT_AT_DEFAULT`. → Task 2 test `test_protocol_without_domain_uses_rag_and_keeps_hash`.
2. A pack that lacks a role a protocol's kind needs fails at load with a message naming the role and the pack, before any model call. → Task 4 test `test_pack_check_names_missing_role`.
3. Near-match must never merge different versions or letters: "GPT-3" vs "GPT-3.5", "Drug A" vs "Drug B", "BERT-base" vs "BERT-large" stay apart; "drug-A" / "Drug A" / "DRUG A" join. → Task 7 tests.
4. Broken "k of n" text ("0 of 0", "45 of 30", "of 120") is skipped, never a crash or a value > 1. → Task 6 test `test_impossible_counts_are_skipped`.
5. Unicode and Greek: "α-blocker" and "alpha blocker" join; NFKC turns full-width digits into ASCII before the number guard. → Task 7 test `test_greek_and_fullwidth_names_join`.

## Shared interfaces (plans 2 and 3 rely on these names)

```python
# evidence/pack.py
DOMAINS: Path                       # repo_root / "domains"
class Role(StrEnum): COMPARED_THING="compared_thing"; METRIC="metric"; VALUE="measured_value"; CLAIM="author_claim"; CONTEXT="context"
class TypeDecl(Strict): prefix: str; role: Role; name_field: str | None; side_field: str | None; canonical_field: str | None; direction_field: str | None
class Words(Strict): conditions: dict[str, list[str]]; not_a_system: str; metrics: list[tuple[str, str, bool]]; claim_subject: str; claims: list[tuple[str, str]]; gliner_labels: dict[str, list[str]]; fraction_metrics: list[str]; dataset_pattern: str; metric_supplement: list[tuple[str, str, bool]]; screen_terms: list[str]; query: dict[str, list[str]]
class Pack(Strict): name: str; types: dict[str, TypeDecl]; words: Words; display: dict[str, str]; names_seed: dict[str, list[str]]; limitation_categories: list[str]; sha256: str
def load_pack(name: str, root: Path = DOMAINS) -> Pack
def protocol_path(pack: str, protocol_id: str) -> Path   # domains/<pack>/protocols/<id>.yaml
def questions_path(pack: str) -> Path                     # domains/<pack>/questions.yaml
class RoleMap:                                            # built from Pack.types
    def type_of(self, role: Role) -> str                  # raises PackError naming the role
    def types_of(self, role: Role) -> list[str]
    def field(self, etype: str, which: Literal["name","side","canonical","direction"]) -> str
# evidence/extractors/numreader.py
Form = Literal["plain","percent","fraction","k_of_n","range","plus_minus"]
@dataclass(frozen=True) class NumberSpan: start: int; end: int; value: float; form: Form; parts: tuple[tuple[int,int], ...]; raw: str
def read_numbers(text: str) -> list[NumberSpan]
# evidence/names.py
def clean(name: str) -> str
@dataclass(frozen=True) class Mention: name: str; doc: str; start: int; end: int; etype: str
@dataclass(frozen=True) class Match: mention: Mention; group: str; step: Literal["clean","alias","near","seed","model"]; quote: str | None
@dataclass(frozen=True) class NameGroups: groups: dict[str, list[str]]; matches: list[Match]; unresolved: list[Mention]
    def group_of(self, name: str) -> str | None
def group_names(mentions: list[Mention], texts: dict[str, str], seed: dict[str, list[str]] | None = None, threshold: int = 92) -> NameGroups
```

Run folder additions: `names.json` (`{"groups": ..., "matches": [...], "unresolved": [...]}`) and the count `unresolved_names` in `funnel.json` and `run.json`, written exactly like `dangling_links` (engine.py:261-266, 534-536, 615).

---

### Task 1: Pack format, loader and `domains/rag`

**Files:**
- Create: `evidence/pack.py`, `domains/rag/pack.yaml`, `domains/rag/words.yaml`, `domains/rag/provenance.json`
- Test: `evidence/tests/test_pack.py`

**Interfaces:**
- Produces: `DOMAINS`, `Role`, `TypeDecl`, `Words`, `Pack`, `PackError(ValueError)`, `load_pack` (Shared interfaces).

`domains/rag/words.yaml` holds, copied verbatim: `terms.CONDITIONS` (terms.py:27-40, `baseline` patterns stored *before* `control_cue` wrapping, with `not_a_system` = terms.py:16), `METRICS` (:42-54), `CLAIM_SUBJECT` (:59), `CLAIMS` (:63-80, order kept), `gliner.LABELS` (gliner.py:53-54), `units.FRACTION_METRICS` (units.py:25), `dataset.DEFAULT_PATTERN` (dataset.py:20), `abbrev.SUPPLEMENT` (abbrev.py:34-37), `screen_terms` and per-type `query` (rag-factuality-funnel.yaml:20, :41, :63, :87, :104). `pack.yaml` declares types `condition` (c, compared_thing, name_field `label`, side_field `role`), `metric` (k, metric, canonical_field `canonical`), `measurement` (m, measured_value), `author_claim` (a, author_claim, direction_field `direction`), `dataset` (d, context, name_field `name`), display names `{treatment: "RAG system", control: "closed-book model"}`, empty `names_seed`, `limitation_categories: []`. `provenance.json`: `{"source": "hand-moved from code at tag ev3b-code", "files": {...}}`. `Pack.sha256` = sha256 of the three files' LF-normalised bytes in name order (reuse `base.source_sha256` style).

- [ ] **Step 1: Write the failing tests**

```python
def test_rag_pack_loads_with_code_words():
    p = load_pack("rag")
    assert p.words.metrics[0] == terms.METRICS[0]
    assert p.words.gliner_labels == gliner.LABELS
    assert p.types["condition"].role is Role.COMPARED_THING

def test_unknown_pack_names_the_folder(tmp_path):
    with pytest.raises(PackError, match="nope"):
        load_pack("nope", root=tmp_path)

def test_pack_digest_changes_when_a_word_changes(tmp_path):
    shutil.copytree(DOMAINS / "rag", tmp_path / "rag")
    before = load_pack("rag", root=tmp_path).sha256
    (tmp_path / "rag/words.yaml").write_text((tmp_path / "rag/words.yaml").read_text().replace("hallucination", "halluc"))
    assert load_pack("rag", root=tmp_path).sha256 != before
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_pack.py -q`. Expected: FAIL (`No module named evidence.pack`).
- [ ] **Step 3:** Implement `evidence/pack.py` with pydantic `Strict` models (reuse `protocol.Strict`), `yaml.safe_load`, and the three data files.
- [ ] **Step 4:** Run `uv run pytest evidence/tests/test_pack.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git add evidence/pack.py domains/rag evidence/tests/test_pack.py && git commit -m "evidence: domain pack format and domains/rag"`

### Task 2: Protocols read the pack; code fallbacks removed

**Files:**
- Modify: `evidence/protocol.py` (add `domain: str = "rag"` to `Protocol`, register it in `DIGEST_OMIT_AT_DEFAULT` :107-108), `evidence/engine.py:134-162` (`build_extractors`), `evidence/extractors/{terms,regex,gliner,units,numbers,dataset,abbrev,measure}.py` (remove the fallbacks at regex.py:34 `default_patterns`, gliner.py:109/257/271, dataset.py:29, abbrev.py:174/219/236-238, units.py:39-41, numbers.py:111-113, terms.py:125-126; delete the moved constants), `evidence/tests/test_old_extractor_ids.py`, `evidence/tests/test_units_conditions.py`
- Create: `evidence/tests/fixtures/ev3b_configs.json` (snapshot, Step 1), `evidence/tests/test_pack_configs.py`

**Interfaces:**
- Consumes: `load_pack`, `Pack.words`.
- Produces: `Pack.extractor_config(etype: str, extractor: str) -> dict` — the words an extractor needs, in the exact key names extractors read today (`conditions`, `metrics`, `labels`, `pattern`, `fraction_metrics`, `not_a_system`, `claim_subject`, `claims`). `build_extractors` computes `{**pack.extractor_config(etype, ref.name), **ref.config, <injected keys as today>}` so protocol config wins. `GlinerCondition.fields` reads `config["conditions"]` instead of `terms.CONDITIONS`.

- [ ] **Step 1: Snapshot before changing code.** Write a throwaway script (not committed) that, at the current commit, calls `engine.build_extractors` for every protocol in `evidence/protocols/*.yaml` and every extractor, collecting `extractor.patterns`/effective config dicts; save to `evidence/tests/fixtures/ev3b_configs.json` keyed `"<protocol id>/<type>/<extractor>"`. Commit the fixture alone: `git commit -m "test: snapshot EV3b effective extractor configs"`.
- [ ] **Step 2: Write the failing tests**

```python
def test_rag_filled_configs_match_ev3b_snapshot():
    # migration check (D36): reports differences; update the fixture only with a reason in the commit message
    assert effective_configs(all_protocols()) == json.loads(SNAPSHOT.read_text())

def test_protocol_wins_over_pack():
    proto = with_config(load(PROTOCOL), "metric", "regex_metric", {"metrics": [["acc", "accuracy", True]]})
    ex = build(proto, "metric", "regex_metric")
    assert ex.patterns["metrics"] == [["acc", "accuracy", True]]

def test_protocol_without_domain_uses_rag_and_keeps_hash():
    for path in PROTOCOLS:
        p = load(path)
        assert p.domain == "rag" and p.sha256() == OLD_SHA[path.stem]

def test_extractors_have_no_code_word_fallback():
    with pytest.raises(KeyError):
        extractors.get("regex_metric", {"evidence_type": "metric"}).extract(TASK, Ctx)
```

`OLD_SHA` is captured in Step 1's fixture as well (`"<id>/sha256"`).

- [ ] **Step 3:** Run `uv run pytest evidence/tests/test_pack_configs.py -q`. Expected: FAIL.
- [ ] **Step 4:** Implement: `Protocol.domain`; `Pack.extractor_config`; `build_extractors` loads `load_pack(protocol.domain)` once per call; remove fallbacks and moved constants (functions that took them as defaults now require the argument). Keep the injected-key handling exactly as today (regex.py:23 `INJECTED`).
- [ ] **Step 5: Retire hash pins.** In `test_old_extractor_ids.py` delete `:28-45` (old EV2 ids rebuild) and keep `:48-55`; in `test_units_conditions.py` delete `EXISTING` and `test_existing_extractor_ids_unchanged` (:19-28, :55-56). Add one replacement test: `test_extractor_id_changes_when_pack_words_change` (two packs differing in one metric pattern give different `extractor_id`s; same pack gives the same id twice).
- [ ] **Step 6:** Run `uv run pytest evidence -q`. Expected: PASS.
- [ ] **Step 7: Commit** `git commit -am "evidence: extractors take topic words from the pack; protocol wins; hash pins retired (D36)"`

### Task 3: Protocols, questions, propose and agentic prompts move to the pack

**Files:**
- Move: `evidence/protocols/*.yaml` → `domains/rag/protocols/`, `evidence/questions.yaml` → `domains/rag/questions.yaml`
- Modify: `evidence/questions.py:24` (`DEFAULT = questions_path("rag")`), `evidence/tests/conftest.py:20`, and every path constant listed in the facts: `webapp/settings.py`, `webapp/evquestions.py`, `webapp/evmodels.py`, `webapp/evfiles.py`, `evaluation/{score,expected,cli,canon}.py`, `evaluation/baselines/{common,rag,agent}.py`, `synth/{truth,corpus}.py`, `evidence/propose/{common,cards}.py`; `evidence/propose/{frame,draft,critic}.py` and `evidence/agentic/task.py` (take words from the pack instead of `terms`; RAG examples in field descriptions at frame.py:43, 50, 59, 182 filled from `pack.display` / `pack.words`)
- Test: `evidence/tests/test_pack_paths.py`

**Interfaces:**
- Produces: `protocol_path(pack, protocol_id)`, `questions_path(pack)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_no_code_refers_to_old_protocol_folder():
    hits = [p for p in REPO.rglob("*.py") if "evidence/protocols" in p.read_text(encoding="utf-8")]
    assert hits == []

def test_questions_point_to_existing_pack_protocols():
    for q in questions.load().entries:
        assert protocol_path("rag", Path(q.protocol).stem).exists()

def test_propose_frame_examples_come_from_pack():
    assert "factual_accuracy" not in inspect.getsource(frame)
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_pack_paths.py -q`. Expected: FAIL.
- [ ] **Step 3:** `git mv` the files; replace constants with `protocol_path`/`questions_path`; `QuestionEntry.protocol` values become paths relative to the pack folder.
- [ ] **Step 4:** Run `uv run pytest -q` (whole repo: evidence, evaluation, synth, webapp, agent). Expected: PASS apart from the known webapp `test_evjobs` failure.
- [ ] **Step 5: Commit** `git commit -am "evidence: protocols and questions live in domains/rag"`

### Task 4: Open evidence types and pack check

**Files:**
- Modify: `evidence/contract.py:20-26` (`EvidenceType = str`; `ITEM_PREFIX` becomes a mutable registry seeded with c/k/m/a/s), `evidence/evidence_types.py` (replace `_widen()` with `register(name: str, prefix: str) -> None`, raising on a prefix clash), `evidence/protocol.py` (`evidence_types` keys validated against the loaded pack's `types`; `_synthesis_matches_types` :287-304 and `_kind_matches_types` :306-315 use `RoleMap`), `evidence/agentic/convert.py:31,36`, `evidence/agentic/task.py:16`, `evaluation/truth.py:22-36`
- Create: `evidence/cli.py` subcommand `evidence pack check <name>`
- Test: `evidence/tests/test_open_types.py`

**Interfaces:**
- Consumes: `Pack.types`.
- Produces: `evidence_types.register`, `RoleMap(pack)`, `PackError` messages of the form `pack '<name>': no type has role '<role>' (needed by kind '<kind>')`.

- [ ] **Step 1: Write the failing tests**

```python
def test_pack_type_registers_with_its_prefix(tmp_path):
    pack = toy_pack(tmp_path, types={"arm": ("x", "compared_thing")})
    register_pack(pack)
    assert contract.ITEM_PREFIX["arm"] == "x"

def test_existing_type_ids_keep_their_prefix():
    item = Item.build("condition", {"label": "RAG", "role": "rag"}, spans=[SPAN])
    assert item.id.startswith("c-")

def test_prefix_clash_is_refused(tmp_path):
    with pytest.raises(PackError, match="prefix 'c'"):
        register_pack(toy_pack(tmp_path, types={"arm": ("c", "compared_thing")}))

def test_pack_check_names_missing_role(tmp_path):
    pack = toy_pack(tmp_path, drop_role="metric")
    with pytest.raises(PackError, match="no type has role 'metric'.*kind 'effect'"):
        check(pack, kinds=["effect"])
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_open_types.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. `pack check` requires only the roles the pack's questions' kinds need (spec §6.2: a SciREX-style pack may lack values and claims): effect/best/consistency need compared_thing, metric, measured_value (+author_claim for consistency); inventory needs only its target type.
- [ ] **Step 4:** Run `uv run pytest evidence -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evidence: open evidence types registered from the pack; pack check"`

### Task 5: Kinds and synthesis address roles, not type names

**Files:**
- Modify: `evidence/synthesis.py:58-64, 119-139`, `evidence/engine.py:165-193` (`focus_for`), `evidence/kinds/{inventory.py:22, effect.py, consistency.py:22, best.py:32-33, 49, 52, 67-75}`, `evidence/kinds/__init__.py` (pass `RoleMap` into `study`/`answer`/`gap_types`)
- Create: `evidence/tests/fixtures/renamed/` (copy of `domains/rag` with types renamed `condition→arm`, `metric→outcome`, `measurement→result`, `author_claim→conclusion`, prefixes kept; plus one protocol `rag-factuality-funnel.yaml` with those names)
- Test: `evidence/tests/test_roles.py`

**Interfaces:**
- Consumes: `RoleMap.type_of`, `RoleMap.field`.
- Produces: kind functions take `roles: RoleMap` as a keyword argument; `inventory.Inventory.target` becomes `str` validated against the pack's types.

- [ ] **Step 1: Write the failing tests**

```python
def test_effect_answer_is_the_same_with_renamed_types(tmp_path):
    a = regex_run(PAPERS, tmp_path / "a", PROTOCOL)
    b = regex_run(PAPERS, tmp_path / "b", RENAMED_PROTOCOL, domains=RENAMED_DOMAINS)
    assert answer_of(a)["verdict"] == answer_of(b)["verdict"]

def test_inventory_lists_any_declared_type(tmp_path):
    out = regex_run(PAPERS, tmp_path, inventory_protocol(target="dataset"))
    assert {"TriviaQA"} <= set(answer_of(out)["names"])

def test_no_kind_module_names_a_rag_type():
    for mod in KIND_MODULES + [synthesis]:
        src = inspect.getsource(mod)
        assert '"condition"' not in src and '"measurement"' not in src
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_roles.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. `regex_run` (conftest.py:50) gains an optional `domains: Path` passed to `load_pack(..., root=)`.
- [ ] **Step 4:** Run `uv run pytest evidence -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evidence: kinds and synthesis work over roles"`

### Task 6: One general number reader

**Files:**
- Create: `evidence/extractors/numreader.py`
- Modify: `evidence/extractors/numbers.py` (`_candidate` :242-260 and `_value` :142-150 use `read_numbers`; drop the `COUNT_AFTER`/`SHARE_AFTER` rejections :258-260 for spans whose form is `k_of_n` or `percent`; keep the generic rejections: bare integer with no unit :248-249, years :250-251, deltas/references :255-257), `evidence/extractors/base.py:77-87` (remove unused `COUNT`/`count_fraction`, now in numreader), `domains/rag/protocols/*.yaml` (measurement `fields` gain optional `form`; `merge_key` stays `[value]`), `numbers.SOURCES` (add numreader.py)
- Test: `evidence/tests/test_numreader.py`

**Interfaces:**
- Produces: `Form`, `NumberSpan`, `read_numbers` (Shared interfaces). Measured-value items carry `fields["form"]`. "k of n" value = k/n; spans of both numbers kept as span roles `value` (k) and `value_total` (n).

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("text,value,form", [
    ("accuracy of 0.68", 0.68, "plain"),
    ("reached 82.5%", 0.825, "percent"),
    ("41 of 120 patients", 41 / 120, "k_of_n"),
    ("41/120 responded", 41 / 120, "fraction"),
    ("0.61 ± 0.03", 0.61, "plus_minus"),
    ("between 0.4 and 0.6", 0.4, "range"),
])
def test_reads_each_form(text, value, form):
    (n,) = [s for s in read_numbers(text) if s.form == form]
    assert n.value == pytest.approx(value)

def test_impossible_counts_are_skipped():
    assert [s for s in read_numbers("0 of 0 and 45 of 30 and of 120") if s.form == "k_of_n"] == []

def test_count_result_becomes_a_measurement(tmp_path):
    items = measurements(["Zelvora: 41 of 120 patients reached response rate."], tmp_path, DRUG_TOY_PROTOCOL)
    assert items[0].fields["value"] == pytest.approx(0.3417, abs=1e-4) and items[0].fields["form"] == "k_of_n"

def test_enrolment_count_is_not_a_measurement(tmp_path):
    assert measurements(["We enrolled 120 patients."], tmp_path, DRUG_TOY_PROTOCOL) == []
```

`DRUG_TOY_PROTOCOL` is a fixture protocol + pack in `evidence/tests/fixtures/drugtoy/` with condition patterns `Zelvora|placebo` and metric `response rate` (fraction metric).

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_numreader.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement `read_numbers` with `re` over NFKC-normalised text (offsets mapped back to the original); percent values divided by 100.
- [ ] **Step 4:** Run `uv run pytest evidence -q`. Expected: PASS; update `test_numbers.py` cases that asserted the old count/share rejections, each with a one-line comment "D35".
- [ ] **Step 5: Commit** `git commit -am "evidence: one general number reader (D35)"`

### Task 7: Name grouping (clean, aliases, guarded near-match, seed)

**Files:**
- Create: `evidence/names.py`
- Modify: `pyproject.toml`/`uv.lock` (`uv add rapidfuzz`)
- Test: `evidence/tests/test_names.py`

**Interfaces:**
- Consumes: `abbrev.definitions(text) -> list[Definition]` (abbrev.py:70; `PHRASES` :94-100 covers "hereafter").
- Produces: `clean`, `Mention`, `Match`, `NameGroups`, `group_names` (Shared interfaces). Group key = the most frequent original form in the group (ties: shortest, then alphabetical). Guard: the sequence of digit runs and of single-letter tokens after `clean` must be equal for a near-match (`rapidfuzz.fuzz.token_sort_ratio >= threshold`). Seed names (pack `names_seed`) form groups first; a mention matching a seed variant after `clean` gets step `seed`.

- [ ] **Step 1: Write the failing tests**

```python
def test_spelling_variants_join():
    g = group_names(ms("Drug A", "drug-A", "DRUG A"), {})
    assert len(g.groups) == 1 and g.unresolved == []

@pytest.mark.parametrize("a,b", [("GPT-3", "GPT-3.5"), ("Drug A", "Drug B"), ("BERT-base", "BERT-large")])
def test_guard_keeps_different_things_apart(a, b):
    assert len(group_names(ms(a, b), {}).groups) == 2

def test_paper_alias_joins_with_quote():
    texts = {"p1": "compound 12 (hereafter Drug A) was given."}
    g = group_names(ms("compound 12", "Drug A", doc="p1"), texts)
    m = [m for m in g.matches if m.step == "alias"][0]
    assert "hereafter" in m.quote and len(g.groups) == 1

def test_greek_and_fullwidth_names_join():
    assert len(group_names(ms("α-blocker", "alpha blocker", "Ｂｅｔａ２", "Beta2"), {}).groups) == 2

def test_every_match_records_its_step():
    g = group_names(ms("Drug A", "drug-A"), {})
    assert {m.step for m in g.matches} <= {"clean", "alias", "near", "seed", "model"}
```

`ms(*names, doc="p1")` builds `Mention`s with `etype="condition"`.

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_names.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. `clean`: `unicodedata.normalize("NFKC")`, casefold, Greek letters to names (α→alpha, β→beta, γ→gamma, δ→delta, κ→kappa, μ→mu), hyphens/underscores/slashes to spaces, collapse spaces, drop a trailing plural "s" on words longer than 3 letters. Names left without a group are `unresolved` (a singleton group is still created so answers keep them).
- [ ] **Step 4:** Run `uv run pytest evidence/tests/test_names.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evidence: corpus-wide name grouping (D38)"`

### Task 8: Model check for leftovers, engine step and run files

**Files:**
- Modify: `evidence/names.py` (add `confirm_leftovers(groups: NameGroups, texts: dict[str, str], ask: Callable[[str], str]) -> NameGroups`), `evidence/engine.py` (new step after all documents are merged and relinked: collect mentions from items of every type whose `TypeDecl.name_field` is set, call `group_names` with `pack.names_seed`, then `confirm_leftovers` through the same recorded model path the `llm_*` extractors use (evidence/extractors/llm.py, recorded so replay never calls a live model); write `names.json`; add `unresolved_names` to `funnel.json` and `run.json` like `dangling_links`; kinds receive `groups` and use `groups.group_of(name)` for compared things and metrics), `evidence/replay.py:40` (missing `names` setting means off, as `relink`), `evidence/engine.py:121-126` (`Settings.names: Literal["on","off"] = "off"`, emitted in `Settings.json()` only when on)
- Create: `evidence/prompts/names-confirm-v1.md` (per docs/prompt-writing.md: one atomic task — "Is <name> the same <type> as <group>? Answer JSON {same: bool, quote: str}"; the quote must be a verbatim substring of the given text, checked in code; a non-verbatim quote counts as `same: false`)
- Test: `evidence/tests/test_names_step.py`

**Interfaces:**
- Consumes: `group_names`, recorded model calls (llm.py).
- Produces: `Settings.names`; run files `names.json`, counts `unresolved_names`. Plan 2's chaining uses `groups.group_of`.

- [ ] **Step 1: Write the failing tests**

```python
def test_names_off_writes_nothing_new(tmp_path):
    out = regex_run(PAPERS, tmp_path, PROTOCOL)
    assert not (out / "names.json").exists() and "unresolved_names" not in run_json(out)

def test_names_on_writes_groups_and_count(tmp_path):
    out = regex_run(PAPERS, tmp_path, PROTOCOL, settings={"names": "on"}, model=scripted([]))
    data = json.loads((out / "names.json").read_text())
    assert set(data) == {"groups", "matches", "unresolved"}
    assert run_json(out)["unresolved_names"] == len(data["unresolved"])

def test_model_match_needs_a_verbatim_quote():
    g = confirm_leftovers(LEFTOVER, {"p1": "Agent Z was tested."}, ask=lambda _: '{"same": true, "quote": "not in text"}')
    assert g.unresolved == LEFTOVER.unresolved
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_names_step.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evidence -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evidence: names step with model check for leftovers, names.json, unresolved_names"`

### Task 9: No-topic-words test

**Files:**
- Create: `evidence/tests/test_no_topic_words.py`, `domains/allowlist.yaml` (entries `{word: str, reason: str}`; start with generic words such as `baseline`, `accuracy`, `dataset`, each with a reason)

**Interfaces:**
- Consumes: every pack under `domains/` (`load_pack` for each folder with a `pack.yaml`).
- Produces: `CHECKED_DIRS = ["evidence", "agent"]` at the top of the test file. Plan 2 adds `"synth", "evaluation"`; plan 3 adds `"webapp"`.

- [ ] **Step 1: Write the test**

```python
def test_no_pack_word_appears_in_checked_code():
    words = pack_words() - allowlist()
    hits = [(f, w) for f in code_files(CHECKED_DIRS) for w in words if re.search(rf"\b{re.escape(w)}\b", text_of(f), re.I)]
    assert hits == []
```

`pack_words()` = literal words from every pack's `words.yaml` (regex patterns reduced to their alphabetic runs of ≥ 4 letters), enum values and display names; `code_files` = `*.py`, `*.md`, `*.txt`, `*.yaml` under the checked dirs, excluding `tests/` and fixtures.

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_no_topic_words.py -q`. Expected: FAIL listing the remaining hits.
- [ ] **Step 3:** Move each remaining hit into `domains/rag/` or into the allowlist with a reason. Docstrings that mention RAG as an example are rewritten generically.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: PASS apart from the known webapp `test_evjobs` failure.
- [ ] **Step 5: Commit** `git commit -am "test: no topic words in evidence/ and agent/"`

---

## Self-review notes

- Spec coverage for steps 1-3: §6.1 move list → Tasks 1-3, 9 (synth/, evaluation/ topic words and the web app are moved by plans 2 and 3, which extend `CHECKED_DIRS`); fallbacks → Task 2; pack vs protocol → Task 2; no-topic-words → Task 9; §6.2 open types, roles, pack check → Tasks 4-5; D38 names → Tasks 7-8; D35 numbers → Task 6; D36 hash pins → Task 2 Step 5; D24 one file per step → `names.json` in Task 8. Comparisons built from pairs (§6.2) and chaining are plan 2.
- `RoleMap`, `Pack`, `NameGroups`, `read_numbers` names match across Tasks 1-8 and the Shared interfaces block.
