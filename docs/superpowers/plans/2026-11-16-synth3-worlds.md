# synth3 Worlds (plan 1 of 5): rich domain worlds and template folders

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a new package `synth3` draws, for any domain, a hidden world rich enough for about 25 different
questions. Aditya approves the drawn world for each of 5 folders. The package then writes each folder as template
papers, with the full truth beside them.

**Architecture:**
- **The spec:** a domain spec (YAML, drafted by Claude in a session and approved by Aditya) names the arms,
  measures (counts or measured values), conditions (some tied to the setting), settings and rates.
- **`synth3 draw`:** draws one world per seed: a law per (treatment, measure) pair, the pairs left uncovered, and
  the rates of head-to-head studies and exaggerating authors. It writes the world as a JSON file that Aditya
  reads, may edit, and marks as approved.
- **`synth3 build`:** refuses unapproved worlds. It draws studies, redraws only the noise until the papers
  support every covered law, writes template papers, and stores the reference facts.
- **Scope:** real-paper planting is plan 2.

**Tech Stack:** Python >= 3.13, pydantic, pyyaml, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-16-multi-domain-benchmark-design.md` (§4, §5, §10b, §10c).

**The five plans:**
1. **This plan:** worlds and template folders.
2. Real-paper planting per domain, medicine first.
3. Questions, checklist answer sheets, the judge (which reads `ground_truth.json` for planted facts and
   placements), the review page and the baseline scores.
4. The system: model-written answers, the sub-question box and the one-page UI.
5. The readable evidence program and the 5-re-run measurement.

**Review history:** two Fable reviewers (engineering and thesis fit) reviewed the first draft and debated it on
16 Nov 2026. This version has their agreed fixes and Aditya's five answers (spec §10c).

## Global Constraints

- **Hashed files:** never edit the files listed under "Hashed files: never edit" in `backend/README.md`.
- **synth2:** do not change its behaviour (it is the RAG stress test, spec §5.7). Import small types only. Its
  `pooled` and `law_answer` work on two-arm cells and must not be called with synth3 data. synth3 has its own
  logic.
- **Named seeds:** every random draw uses `random.Random(f"synth3:{seed}:<what>")`.
- **Text checks:** text from the spec that goes into a paper has no digits, no `|` and no line break, and never
  uses a level id as a word (`synth2/recipe.py:86-105`).
- **Folder size:** 5 folders per domain (seeds 1–5) and 40 studies per folder by default (spec §10c).
- **Git ignore:** built folders go under `data/synth3/built/` (git-ignored). World files under
  `data/synth3/worlds/` hold no paper text and are committed.
- **Git:** work on branch `synth3-worlds`. Commit steps run only after Aditya has approved executing this plan;
  never push or merge without him. End every commit message with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Tests:** run `uv run pytest -q backend/synth3` per task. Run the whole suite, `uv run pytest -q`, at the end
  of Tasks 1 and 6.

## Review Focus

- **Lower-is-better measures:** for side effects, "helps" must mean fewer side effects everywhere: in laws,
  claims, reference answers and paper wording (Task 3 and Task 5 tests use a lower-is-better measure).
- **Noisy right answers:** the build must never write a folder whose reference answer for a covered pair differs
  from its law. It redraws the noise, and refuses after 50 tries, naming the pair (Task 4 test).
- **An edited world:** if Aditya changes a law by hand into an impossible one (e.g. kind `none` with effects),
  the world must be refused with a message, not built (Task 2 test).
- **Two studies with equal numbers:** the engine merges them as one study (`evidence/rules.py:88-95`), so the
  draw must redraw them (Task 3 test).
- **The repo-wide suite:** a new backend package must be registered in `backend/tests/test_boundaries.py:12-17`
  (Task 1).

---

### Task 1: Domain spec

**Files:**
- Create: `backend/synth3/__init__.py` (docstring only) and `backend/synth3/spec.py`
- Create: `backend/synth3/tests/__init__.py`, `backend/synth3/tests/conftest.py` and
  `backend/synth3/tests/test_spec.py`
- Modify: `pyproject.toml` (add `"synth3"` to `module-name`, line 67)
- Modify: `backend/tests/test_boundaries.py:15` (add `"synth3"` to the evaluation tuple)
- Modify: the service map in `backend/README.md` (add `synth3` next to `synth2`)

**Interfaces:**
- Produces: `SPECS = DATA / "synth3"` and `MIN_AUTHORS = 40`.
- Produces: `ArmSpec(Strict)` with `id`, `label`, `description` and `control: bool = False`.
- Produces: `Measure(Strict)` with these fields:
  - `id`, `name`, `kind: Literal["count", "value"]`, `higher_is_better: bool`;
  - `effect: tuple[float, float]`, `min_effect: float`, `min_gap: float`;
  - for `count`: `unit` and `outcome` (text: `"{k} of {n} {unit} {outcome}"`) and
    `base_rate: tuple[float, float]`;
  - for `value`: `unit` (e.g. "mmHg"), `base_value: tuple[float, float]`, `spread: float` (SD as a share of the
    mean) and `decimals: int` (0–2).

  The effect is a rate difference for counts and a relative change for values (0.10 = 10%).
- Produces: `Condition(Strict)` with `id`, `name`, `levels: list[Level]` (exactly 2) and
  `from_setting: bool = False`.
- Produces: `Setting(Strict)` with `name` and `levels: dict[str, str]`, which maps each `from_setting`
  condition id to a level id.
- Produces: `DomainSpec(Strict)` with these fields:
  - `domain`, `field`, `arms`, `measures`, `conditions`, `settings`;
  - `n_range`, `n_step`, `head_to_head_rate: float`, `overclaim_rate: float`, `uncovered_rate: float`;
  - `authors`, `years`, `sha256`.

  It has the properties `control`, `treatments`, `pairs -> list[tuple[str, str]]` (treatment id, measure id, in
  spec order) and `measure(id) -> Measure`.
- Produces: `load_spec(domain: str, root: Path = SPECS) -> DomainSpec`. Any problem is a `ValueError` that names
  it.
- Reuses: `Strict` and `Level` from `synth2.recipe`.

- [ ] **Step 1: Write the failing tests.** In `conftest.py`, `good()` returns a valid dict with:
  - 3 arms (`ctrl` as control, `a`, `b`);
  - 3 measures: `m1` (count, higher is better), `m2` (count, lower is better) and `m3` (value);
  - 3 conditions, where `site` is `from_setting`;
  - 4 settings and 40 authors.

  `write(dir, d, newline="\n")` makes `dir` and writes `demo.yaml`. A fixture `SPEC` is the loaded `good()`.

```python
def test_loads_and_lists_pairs(tmp_path):
    spec = load_spec("demo", write(tmp_path, good()))
    assert spec.control.id == "ctrl" and [a.id for a in spec.treatments] == ["a", "b"]
    assert spec.pairs == [(t, m) for t in ("a", "b") for m in ("m1", "m2", "m3")]

@pytest.mark.parametrize("change, words", [
    (lambda d: d["arms"][0].update(control=False), "exactly one control"),
    (lambda d: d["arms"].pop(), "at least 3 arms"),
    (lambda d: d["measures"].pop(), "at least 3 measures"),
    (lambda d: d["measures"][0].update(base_rate=[0.2, 0.95]), "base_rate"),
    (lambda d: d["measures"][2].pop("base_value"), "base_value"),
    (lambda d: d["measures"][0].update(min_gap=0.5), "min_gap"),
    (lambda d: d["arms"][2].update(label=d["arms"][1]["label"] + " retard"), "inside"),
    (lambda d: d["measures"][0].update(outcome="reached grade 2"), "digit"),
    (lambda d: d["settings"][0]["levels"].clear(), "setting"),
    (lambda d: d["authors"].__delitem__(slice(10, None)), "authors"),
])
def test_refuses_bad_specs(tmp_path, change, words):
    d = good(); change(d)
    with pytest.raises(ValueError, match=words):
        load_spec("demo", write(tmp_path, d))

def test_crlf_and_lf_hash_the_same(tmp_path):
    assert load_spec("demo", write(tmp_path / "lf", good())).sha256 == \
           load_spec("demo", write(tmp_path / "crlf", good(), newline="\r\n")).sha256
```

- [ ] **Step 2: Run the tests to watch them fail.** Run `uv run pytest -q backend/synth3`. Expected: FAIL with
  `ModuleNotFoundError: synth3`.
- [ ] **Step 3: Implement `spec.py`.** The rules:
  - at least 3 arms with exactly one control;
  - at least 3 measures and at least 2 conditions with 2 levels each;
  - all ids different;
  - a count measure keeps `base_rate ± effect[1]` inside 0–1;
  - a value measure has `base_value`, `spread` and `decimals`, and keeps `effect[1] < 1`;
  - per measure, `0 < min_effect <= effect[0]` and `min_gap <= effect[0]`;
  - every setting gives a level for every `from_setting` condition, and each level of such a condition is used by
    at least one setting;
  - no name inside another;
  - text checks on every text field;
  - the three rates within 0–1;
  - `n_range` ends are positive multiples of `n_step`;
  - at least `MIN_AUTHORS` different authors.

  CRLF is turned into LF before hashing, as in `synth2/recipe.py:108-120`.
- [ ] **Step 4: Run the tests.** Run `uv run pytest -q backend/synth3`, then the whole suite with
  `uv run pytest -q`. Expected: PASS, including `test_boundaries.py`.
- [ ] **Step 5: Commit**: `synth3: domain spec with count and value measures`.

### Task 2: The hidden world and its approval file

**Files:**
- Create: `backend/synth3/world.py` and `backend/synth3/tests/test_world.py`

**Interfaces:**
- Consumes: `DomainSpec` (Task 1).
- Produces: `KINDS = ("none", "uniform", "one_sided", "opposed")`.
- Produces: `PairLaw` (frozen dataclass) with `treatment`, `measure`, `kind`, `condition: str | None` and
  `effects: dict[str, float]`. The effects map each level to the signed effect, where a positive number means
  better. Kind `none` has condition `None` and effects `{}`. It has `json()`, `parse()` and
  `answer(min_effect) -> tuple[str, str | None, dict[str, str]]`:
  - `none` gives `("no_effect", None, {})`;
  - the same word on both levels gives `(word, None, {})`;
  - otherwise it gives `("depends", condition, sides)`.
- Produces: `World` (frozen dataclass) with these fields:
  - `domain`, `seed`, `spec_sha256`;
  - `laws: tuple[PairLaw, ...]`, one per pair in `spec.pairs` order;
  - `uncovered: tuple[tuple[str, str], ...]`;
  - `approved: bool`.

  It has `law(t, m)`, `json()` and `parse(obj, spec)`. `parse` refuses with a `ValueError` naming the problem:
  a kind that does not fit its effects, an unknown condition or level, a pair missing or doubled, an uncovered
  pair that is not a pair, or a `spec_sha256` that does not match the spec.
- Produces: `draw_world(spec: DomainSpec, seed: int) -> World` (`approved=False`).
- Produces: `save_world(path: Path, world: World) -> None` and
  `load_world(path: Path, spec: DomainSpec) -> World`.
- Produces: `describe(world: World, spec: DomainSpec) -> str`: a plain-English table that Aditya reads. It has one
  line per pair (e.g. "alvenor on side effects: better for older adults, worse for younger adults") and the
  uncovered pairs.

- [ ] **Step 1: Write the failing tests:**

```python
def test_same_seed_same_world(SPEC):
    assert draw_world(SPEC, 3).json() == draw_world(SPEC, 3).json()

def test_one_law_per_pair_and_never_approved_when_drawn(SPEC):
    w = draw_world(SPEC, 1)
    assert [(l.treatment, l.measure) for l in w.laws] == SPEC.pairs and w.approved is False

def test_every_world_has_a_law_that_depends(SPEC):
    assert all(any(l.kind in ("one_sided", "opposed") for l in draw_world(SPEC, s).laws) for s in range(1, 30))

def test_kinds_and_setting_conditions_occur_across_seeds(SPEC):
    laws = [l for s in range(1, 11) for l in draw_world(SPEC, s).laws]
    assert {l.kind for l in laws} == set(KINDS) and any(l.condition == "site" for l in laws)

def test_uncovered_pairs_occur_and_never_the_only_depends_law(SPEC):
    worlds = [draw_world(SPEC, s) for s in range(1, 21)]
    assert any(w.uncovered for w in worlds)
    for w in worlds:
        covered = [l for l in w.laws if (l.treatment, l.measure) not in w.uncovered]
        assert any(l.kind in ("one_sided", "opposed") for l in covered)

def test_law_answer_for_none_is_no_effect(SPEC):
    assert PairLaw("a", "m1", "none", None, {}).answer(0.01) == ("no_effect", None, {})

def test_round_trip_and_edits_are_checked(SPEC, tmp_path):
    w = draw_world(SPEC, 4)
    save_world(tmp_path / "w.json", w)
    assert load_world(tmp_path / "w.json", SPEC) == w
    bad = w.json(); bad["laws"][0] = {**bad["laws"][0], "kind": "none", "effects": {"young": 0.1}}
    with pytest.raises(ValueError, match="kind"):
        World.parse(bad, SPEC)

def test_describe_names_every_pair_in_words(SPEC):
    text = describe(draw_world(SPEC, 2), SPEC)
    assert all(SPEC.measure(m).name in text for _, m in SPEC.pairs) and "ctrl" not in text
```

- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement.**
  - **Laws:** per pair, use `Random(f"synth3:{seed}:law:{t}:{m}")`. The kind is uniform over `KINDS` and the
    condition is uniform over `spec.conditions`. Side swap and mirror are coin flips, as in
    `synth2/world.py:105-117`. Sizes come from `measure.effect`.
  - **Forced depends:** if no pair is `one_sided` or `opposed`, the first pair is redrawn as `opposed` with
    `Random(f"synth3:{seed}:law:forced")`.
  - **Uncovered:** with `Random(f"synth3:{seed}:uncovered")`, and probability `spec.uncovered_rate`, one pair is
    left uncovered. It is chosen among the pairs whose removal keeps at least one covered "depends" law.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: hidden world, approval file and plain description`.

### Task 3: Studies

**Files:**
- Modify: `backend/synth3/world.py`
- Create: `backend/synth3/tests/test_studies.py`

**Interfaces:**
- Consumes: `World`, `PairLaw` and `DomainSpec`.
- Produces: `ArmResult` (frozen dataclass) with `arm`, `n: int`, `k: int | None`, `mean: float | None` and
  `sd: float | None`. A count result has `k` only, with `0 <= k <= n`. A value result has `mean` and `sd` only.
  Anything else is a `ValueError`.
- Produces: `Cell` (frozen dataclass) with `index: int` (study-wide, from 0), `measure: str`,
  `levels: dict[str, str]` (every condition id) and `results: tuple[ArmResult, ...]` (in the study's arm order).
- Produces: `Study` (frozen dataclass) with these fields:
  - `id`, `label`, `setting`;
  - `arms: tuple[str, ...]`: the control first when present; a head-to-head study has 2 treatments and no
    control;
  - `measures`, `cells`;
  - `claims: dict[str, str]`: a key `"<arm>|<against>|<measure>"` maps to helps / hurts / no_effect;
  - `overclaims: tuple[str, ...]`: the claim keys that exaggerate.

  It has `json()` and `parse()`.
- Produces: `MIN_PER_PAIR = 3` and `MAX_TRIES = 50`.
- Produces: `pair_delta(spec: DomainSpec, cells: Sequence[Cell], arm: str, against: str) -> float`: the signed
  pooled difference, where positive means better.
  - For counts, it is the pooled rate minus the pooled rate.
  - For values, it is the n-weighted mean of `arm`, minus that of `against`, divided by the latter.
  - It is negated when `higher_is_better` is false.
- Produces: `draw_studies(spec, world, seed, count, attempt: int = 0) -> tuple[Study, ...]`. `attempt` changes
  only the count/value noise seeds. The design (arms, measures, cells, settings) is the same for every attempt.

- [ ] **Step 1: Write the failing tests:**

```python
def test_refuses_too_few_studies_and_names_a_pair(SPEC):
    with pytest.raises(ValueError, match=r"fewer than 3 studies: \w+\|\w+"):
        draw_studies(SPEC, draw_world(SPEC, 1), 1, count=5)

def control_pairs(studies):
    return Counter((t, m) for s in studies if s.arms[0] == "ctrl" for t in s.arms[1:] for m in s.measures)

def test_covered_pairs_get_three_studies_uncovered_get_none(SPEC):
    for seed in range(1, 11):
        w = draw_world(SPEC, seed); seen = control_pairs(draw_studies(SPEC, w, seed, 40))
        for p in SPEC.pairs:
            assert (seen[p] == 0) if p in w.uncovered else (seen[p] >= MIN_PER_PAIR)

def test_head_to_head_studies_exist_without_control(SPEC):
    studies = draw_studies(SPEC, draw_world(SPEC, 2), 2, 40)
    assert any("ctrl" not in s.arms and len(s.arms) == 2 for s in studies)

def test_lower_is_better_sign(SPEC):
    w = draw_world(SPEC, 3)
    for s in draw_studies(SPEC, w, 3, 40):
        for c in s.cells:
            if c.measure == "m2" and s.arms[0] == "ctrl":
                ctrl, a = c.results[0], c.results[1]
                raw = a.k / a.n - ctrl.k / ctrl.n
                assert pair_delta(SPEC, [c], s.arms[1], "ctrl") == pytest.approx(-raw)

def test_claims_honest_except_listed_overclaims(SPEC):
    studies = [s for seed in range(1, 6) for s in draw_studies(SPEC, draw_world(SPEC, seed), seed, 40)]
    assert any(s.overclaims for s in studies)
    for s in studies:
        for key, word in s.claims.items():
            arm, against, m = key.split("|")
            honest = direction(pair_delta(SPEC, [c for c in s.cells if c.measure == m], arm, against),
                               SPEC.measure(m).min_effect)
            assert (word == "helps" and honest != "helps") if key in s.overclaims else word == honest

def test_no_two_results_share_their_numbers_within_a_folder(SPEC):
    studies = draw_studies(SPEC, draw_world(SPEC, 4), 4, 40)
    keys = [tuple((r.k, r.n, r.mean) for r in c.results) for s in studies for c in s.cells]
    assert len(keys) == len(set(keys))

def test_attempt_changes_numbers_not_design(SPEC):
    w = draw_world(SPEC, 5)
    a, b = draw_studies(SPEC, w, 5, 40, 0), draw_studies(SPEC, w, 5, 40, 1)
    assert [(s.arms, s.measures, s.setting) for s in a] == [(s.arms, s.measures, s.setting) for s in b]
    assert [s.cells for s in a] != [s.cells for s in b]
```

  `direction` comes from `synth2.world`.
- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement `draw_studies`.** The design uses `Random(f"synth3:{seed}:S{i+1:03d}:design")`:
  - **Head to head or control:** with probability `head_to_head_rate`, the study compares 2 treatments.
    Otherwise it has the control plus a main pair's treatment.
  - **Main pair:** the covered pair with the fewest control studies so far. Ties are broken by a shuffle of
    `spec.pairs` with `Random(f"synth3:{seed}:pairs")`.
  - **Extras:** with probability 0.4 each, add a second treatment and a second measure. An addition is skipped if
    it would create an uncovered pair.
  - **Split:** with probability 0.5, the study reports 2 cells per measure, split on any condition. A
    `from_setting` condition takes its level from the setting and never splits.
  - **Other draws:** `n`, `setting` and `year`.

  The numbers use `Random(f"synth3:{seed}:{attempt}:S{i+1:03d}:c{index}:{arm}")`, with `index` study-wide:
  - The control's base is drawn per (study, measure) from `base_rate` or `base_value`.
  - Each arm's true rate or mean is the base plus that arm's law effect at the cell's level. The effect is
    unsigned for lower-is-better measures, and relative for values.
  - Counts are `binomialvariate`. Values are `gauss(true, sd/sqrt(n))`, rounded to `decimals`, with
    `sd = spread * true`.
  - If a cell's numbers equal an earlier cell's, redraw them with `:again{j}` added to the seed, as in
    `synth2/world.py:153-175`.

  Claims are honest per (arm, against, measure). Then, with `Random(f"synth3:{seed}:S{i+1:03d}:claims")` and
  probability `overclaim_rate`, one claim whose honest word is not "helps" becomes "helps" and its key goes into
  `overclaims`.

  After drawing: any covered pair with fewer than `MIN_PER_PAIR` control studies is a
  `ValueError(f"fewer than 3 studies: {t}|{m} ...")`.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: studies with counts, values, head-to-head and exaggerated claims`.

### Task 4: Reference facts and the noise gate

**Files:**
- Create: `backend/synth3/reference.py` and `backend/synth3/tests/test_reference.py`

**Interfaces:**
- Consumes: `Study`, `Cell`, `pair_delta`, `draw_studies`, `World` and `DomainSpec`.
- Produces: `pair_answer(spec, studies, arm, against, measure) -> dict`. It returns
  `{"verdict", "condition", "sides", "untested"}`, the same shape as `synth2.conclude.Answer.json()`, with its own
  logic:
  - It uses the cells of `measure` in studies that include both `arm` and `against`.
  - Per condition, it splits by level. The result is "depends" when the two level words differ and the gap is at
    least `min_gap`; otherwise the pooled direction.
  - It is "insufficient" when no study covers the pair.
  - `untested` lists `"<condition>.<level>"` with no cell.
- Produces: `reference_facts(spec, world, studies) -> dict` with these keys:
  - `pairs`: one entry per `spec.pairs` item, with `treatment`, `measure`, `law`, `answer` (against the
    control), `matches_law`, `uncovered`, `reason` (the condition's name when "depends", else null),
    `studies`, `supporting`, `contradicting`, `neutral` (by each study's claim) and `overclaimed_in` (study ids);
  - `head_to_head`: one entry per treatment pair compared directly in a study, with `answer` and `studies`;
  - `ranking`: per measure, the treatments ordered by their pooled effect against the control (covered pairs
    only);
  - `inventory`: the settings, arms and measures each study reports.
- Produces: `draw_supported_studies(spec, world, seed, count) -> tuple[tuple[Study, ...], int]`. It tries
  `attempt = 0..MAX_TRIES-1` and returns the first studies where every covered pair's `matches_law` is true,
  plus that attempt. Otherwise it raises `ValueError` naming the pairs that never matched.

- [ ] **Step 1: Write the failing tests:**

```python
def test_supported_studies_match_every_covered_law(SPEC):
    for seed in range(1, 6):
        w = draw_world(SPEC, seed)
        studies, _ = draw_supported_studies(SPEC, w, seed, 40)
        facts = reference_facts(SPEC, w, studies)
        assert all(p["matches_law"] for p in facts["pairs"] if not p["uncovered"])

def test_uncovered_pair_is_insufficient_and_marked(SPEC):
    seed = next(s for s in range(1, 50) if draw_world(SPEC, s).uncovered)
    w = draw_world(SPEC, seed); studies, _ = draw_supported_studies(SPEC, w, seed, 40)
    p = next(p for p in reference_facts(SPEC, w, studies)["pairs"] if p["uncovered"])
    assert p["answer"]["verdict"] == "insufficient"

def test_depends_gives_the_reason_in_words(SPEC):
    w = draw_world(SPEC, 1); studies, _ = draw_supported_studies(SPEC, w, 1, 40)
    for p in reference_facts(SPEC, w, studies)["pairs"]:
        if p["answer"]["verdict"] == "depends":
            assert p["reason"] == next(c.name for c in SPEC.conditions if c.id == p["answer"]["condition"])

def test_groups_partition_and_overclaims_are_listed(SPEC):
    w = draw_world(SPEC, 2); studies, _ = draw_supported_studies(SPEC, w, 2, 40)
    for p in reference_facts(SPEC, w, studies)["pairs"]:
        assert sorted(p["supporting"] + p["contradicting"] + p["neutral"]) == sorted(p["studies"])
        assert set(p["overclaimed_in"]) <= set(p["studies"])

def test_gate_refuses_when_noise_cannot_be_beaten(SPEC):
    tiny = SPEC.model_copy(update={"n_range": (50, 50), "n_step": 50})
    with pytest.raises(ValueError, match="never matched"):
        draw_supported_studies(tiny, draw_world(tiny, 1), 1, 40)
```

- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement.** `matches_law` compares `(verdict, condition, sides)` with `PairLaw.answer`.
- [ ] **Step 4: Run the tests.** Expected: PASS. If `test_supported_studies_match_every_covered_law` needs more
  than 50 tries, widen `good()`'s `n_range`. Do not raise `MAX_TRIES`. Ledger the change.
- [ ] **Step 5: Commit**: `synth3: reference facts and the gate that keeps answers out of the noise`.

### Task 5: Template papers

**Files:**
- Create: `backend/synth3/write.py` and `backend/synth3/tests/test_write.py`

**Interfaces:**
- Consumes: `Study` and `DomainSpec`.
- Produces: `TEXT_LEVELS = ("table", "prose")`.
- Produces: `write_paper(study, spec, text_level, seed) -> Paper` and
  `missing_facts(paper, study, spec) -> list[str]`, reusing `synth2.write.Paper` and `Placement`. An empty list
  means faithful.
- Fact ids:
  - `"<sid>.c<index>.<arm>.<field>"`, where the field is `k` and `n` for counts, or `mean`, `sd` and `n` for
    values;
  - `"<sid>.claim.<arm>.<against>.<measure>.abstract"` and `".conclusion"`;
  - `"<sid>.setting"`.
- Sections: `# <label>: <title>`, `## Abstract` (claims), `## Setup` (arms, setting, subsets by level names),
  `## Results` and `## Conclusion` (claims again).
  - **Results, table level:** count rows are `| Subset | Arm | Measure | Count | Total |`; value rows are
    `| Subset | Arm | Measure | Mean | SD | n |`.
  - **Results, prose level:** `"On the subset with <levels>, <k> of <n> <unit> <outcome> with the <arm>."` or
    `"On the subset with <levels>, the <arm> reached a mean <measure> of <mean> <unit> (SD <sd>, n = <n>)."`
- Claim words are "better" words, so a lower-is-better measure reads naturally: helps → "reduces <side
  effects>", hurts → "increases", no_effect → "about the same".

- [ ] **Step 1: Write the failing tests:**

```python
@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_every_planted_fact_is_where_it_says(SPEC, level):
    w = draw_world(SPEC, 1); studies, _ = draw_supported_studies(SPEC, w, 1, 40)
    assert all(missing_facts(write_paper(s, SPEC, level, 1), s, SPEC) == [] for s in studies)

def test_only_planted_numbers_and_the_year_are_digits(SPEC):
    w = draw_world(SPEC, 2); s = draw_supported_studies(SPEC, w, 2, 40)[0][0]
    p = write_paper(s, SPEC, "prose", 2)
    planted = [(pl.start, pl.end) for pl in p.placements]
    year = re.search(r"\((\d{4})\)", p.text).span(1)
    for m in re.finditer(r"\d+(?:\.\d+)?", p.text):
        assert m.span() == year or any(a <= m.start() and m.end() <= b for a, b in planted)
    assert not re.search(r"\b(ctrl|m1|m2|m3)\b", p.text)

def test_lower_is_better_claim_reads_reduces(SPEC):
    w = draw_world(SPEC, 3); studies, _ = draw_supported_studies(SPEC, w, 3, 40)
    s = next(s for s in studies if any(k.endswith("|m2") and v == "helps" for k, v in s.claims.items()))
    assert "reduces" in write_paper(s, SPEC, "table", 3).text

def test_unknown_text_level_is_refused(SPEC):
    s = draw_supported_studies(SPEC, draw_world(SPEC, 1), 1, 40)[0][0]
    with pytest.raises(ValueError, match="text level"):
        write_paper(s, SPEC, "split", 1)
```

- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement.** Use the builder pattern of `synth2/write.py:46-58` and filler from
  `Random(f"synth3:{seed}:{sid}:text")`. Values are printed with exactly `decimals` places.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: template papers for counts and values`.

### Task 6: Folders and the two commands

**Files:**
- Create: `backend/synth3/corpus.py`, `backend/synth3/cli.py` and `backend/synth3/tests/test_corpus.py`
- Modify: `pyproject.toml` (add `synth3 = "synth3.cli:main"` after line 42)
- Modify: `.gitignore` (add `data/synth3/built/`)

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: `GENERATOR = "synth3"` and `VERSION = 1`.
- Produces: `build_folder(out: Path, spec: DomainSpec, world: World, studies: int, text_level: str) -> str`. It
  refuses `world.approved == False` and a non-empty `out`. It calls `draw_supported_studies` and writes the
  folder. It returns the id `"<domain>3-<8 hex>"`, made from the paper hashes as in `synth2/corpus.py:76-77`.
- Layout: the system reads `papers/S*.md` and `manifest.json` (the same shape as `synth2/corpus.py:83-85`, which
  `evidence/rundir.py:128-142` reads). It must not read:
  - `corpus.json`: `generator {name, version, code_sha256}`, `spec {domain, sha256}`, `settings {seed, studies,
    text_level, attempt}`;
  - `ground_truth.json`: `corpus_id`, `world`, `spec` (the dict), `studies`, `placements` (`paper`, `fact`,
    `start`, `end`) and `facts` (`reference_facts`).

  Ruling: `evaluation/truth.py` cannot read this truth; plan 3's judge reads it directly.
- Produces: `synth3 draw --domain <d> --seeds 1,2,3,4,5 [--spec-root P] [--worlds W]`. It writes
  `W/<d>/s<seed>.json` (default `W` = `data/synth3/worlds`), refuses to overwrite an existing file, and prints
  `describe` per seed.
- Produces: `synth3 build --domain <d> --seeds ... [--studies 40] [--text-level table] [--worlds W] --out O`.
  It loads each world file and writes `O/s<seed>/`, printing one line per folder with its id and attempt.

- [ ] **Step 1: Write the failing tests:**

```python
def approved(SPEC, seed):
    return replace(draw_world(SPEC, seed), approved=True)

def test_unapproved_world_is_refused(tmp_path, SPEC):
    with pytest.raises(ValueError, match="approved"):
        build_folder(tmp_path / "f", SPEC, draw_world(SPEC, 1), 40, "table")

def test_same_world_builds_byte_identical_folders(tmp_path, SPEC):
    build_folder(tmp_path / "a", SPEC, approved(SPEC, 1), 40, "table")
    build_folder(tmp_path / "b", SPEC, approved(SPEC, 1), 40, "table")
    files = sorted(p.relative_to(tmp_path / "a") for p in (tmp_path / "a").rglob("*") if p.is_file())
    assert files and all((tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes() for f in files)

def test_truth_is_beside_the_papers(tmp_path, SPEC):
    out = tmp_path / "f"; build_folder(out, SPEC, approved(SPEC, 2), 40, "prose")
    manifest = json.loads((out / "manifest.json").read_text())
    assert {p["file"] for p in manifest["papers"]} == {f"papers/{p.name}" for p in (out / "papers").glob("*.md")}
    assert set(json.loads((out / "ground_truth.json").read_text())) == \
           {"corpus_id", "world", "spec", "studies", "placements", "facts"}

def test_draw_then_build_by_command(tmp_path, spec_dir, capsys):
    common = ["--domain", "demo", "--spec-root", str(spec_dir), "--seeds", "1,2", "--worlds", str(tmp_path / "w")]
    assert main(["draw", *common]) == 0
    for s in (1, 2):
        f = tmp_path / "w" / "demo" / f"s{s}.json"; d = json.loads(f.read_text()); d["approved"] = True
        f.write_text(json.dumps(d))
    assert main(["build", *common, "--out", str(tmp_path / "o")]) == 0
    assert (tmp_path / "o" / "s2" / "ground_truth.json").is_file()
    assert main(["draw", *common]) != 0   # refuses to overwrite approved worlds
```

  `spec_dir` is a conftest fixture that writes `good()` as `demo.yaml`.
- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement.** Write files with `jsonio.write_json_atomic` / `write_text_atomic`, as synth2 does.
- [ ] **Step 4: Run the tests.** Run `uv run pytest -q backend/synth3`, then `uv run pytest -q` (the whole suite,
  including synth2 untouched). Expected: all pass.
- [ ] **Step 5: Commit**: `synth3: folders and the draw and build commands`.

### Task 7: Medicine: spec, approved worlds, 5 folders

**Files:**
- Create: `data/synth3/medicine.yaml`, `data/synth3/worlds/medicine/s1.json` … `s5.json` and
  `backend/synth3/tests/test_domains.py`

There are two stops for Aditya: after Step 3 (the spec) and after Step 4 (the drawn worlds).

- [ ] **Step 1: Write the failing test:**

```python
def test_medicine_spec_loads_and_fits_forty_studies():
    spec = load_spec("medicine")
    assert len(spec.pairs) * MIN_PER_PAIR <= 40 * (1 - spec.head_to_head_rate)
    assert {m.kind for m in spec.measures} == {"count", "value"}
    assert any(not m.higher_is_better for m in spec.measures) and any(c.from_setting for c in spec.conditions)
```

- [ ] **Step 2: Run it to watch it fail.** Expected: FAIL with `no spec file`.
- [ ] **Step 3: Write the spec draft.** The arms:
  - control `standard care`;
  - treatments `alvenor`, `brostamide` and `cardivel` (invented blood-pressure drugs).

  The measures:
  - `bp_control`: count, "patients", "reached their target blood pressure", higher is better, base 0.40–0.60,
    effect 0.08–0.14;
  - `side_effects`: count, "patients", "reported a side effect", lower is better, base 0.15–0.30, effect
    0.06–0.10;
  - `systolic_drop`: value, "mmHg", higher is better, base 8.0–14.0, spread 0.5, decimals 1, effect 0.15–0.30.

  The conditions:
  - `age`: younger adults / older adults;
  - `kidney`: normal kidney function / reduced kidney function;
  - `care`: university hospital / community clinic, `from_setting`.

  The rest:
  - six invented cohorts, three per care level;
  - `n_range` [200, 800], `n_step` 50;
  - `head_to_head_rate` 0.15, `overclaim_rate` 0.15, `uncovered_rate` 0.4;
  - per measure, `min_effect` = half of `effect[0]` and `min_gap` = `effect[0]`;
  - 40 surnames, years 2016–2025.

  Run the test. Expected: PASS. **Stop: ask Aditya to approve or edit the spec.**
- [ ] **Step 4: Draw the worlds.** Run `uv run synth3 draw --domain medicine --seeds 1,2,3,4,5`. Show the five
  descriptions to Aditya. **Stop: he edits the world files if he wants, and approval is set only on his word**
  (he flips `approved`, or tells Claude to).
- [ ] **Step 5: Build.** Run `uv run synth3 build --domain medicine --seeds 1,2,3,4,5 --out data/synth3/built/medicine`.
  Expected: 5 lines with a `medicine3-` id each. A gate failure names the pair; widen `n_range` in the spec (with
  Aditya's ok) and rebuild.
- [ ] **Step 6: Commit** the spec, the 5 approved world files and the test: `synth3: medicine spec and approved
  worlds`. The built folders stay git-ignored.
