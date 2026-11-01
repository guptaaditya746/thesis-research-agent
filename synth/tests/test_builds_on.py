"""The builds_on preset, planted limitations and name variants (plan 2 Task 5): which earlier study a study builds on
and how, the limitations its authors state, and the variant names a paper uses for a thing."""
from __future__ import annotations

import hashlib
import random
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from evidence import names
from evidence.extractors import abbrev
from synth import corpus, truth
from synth.cli import main as synth_main
from synth.network import edge_of, latent
from synth.recipe import load_recipe
from synth.levels import make_plan
from synth.truth import generate

from .conftest import kept_registry

FIXTURES = Path(__file__).resolve().parents[2] / "evidence" / "tests" / "fixtures"
DRUGTOY = load_recipe("drugtoy", root=FIXTURES)
with kept_registry():                   # loading the drugtoy protocol registers its pack's types
    SPEC = truth.default_spec(DRUGTOY)
PINS = Path(__file__).resolve().parent / "data" / "rag_set_sha256.json"


def original_value(cited: truth.Study, citing: truth.Study, d: truth.Dependency) -> float:
    """The cited study's value on the copied fact's thing (by label), metric (by canonical) and context."""
    m = next(m for m in citing.measurements if m.id == d.measurement)
    label = next(c.label for c in citing.conditions if c.id == m.condition)
    canonical = next(k.canonical for k in citing.metrics if k.id == m.metric)
    return next(o.value for o in cited.measurements
                if next(c.label for c in cited.conditions if c.id == o.condition) == label
                and next(k.canonical for k in cited.metrics if k.id == o.metric) == canonical
                and o.dataset == m.dataset)


# --- the brief's tests ---------------------------------------------------------------------------------------

def test_dependencies_only_cite_earlier_studies():
    for s in generate(4, 16, recipe=DRUGTOY, preset="builds_on"):
        assert all(d.cites < s.study_id for d in s.dependencies)


def test_copied_result_equals_the_original_value():
    studies = {s.study_id: s for s in generate(4, 16, recipe=DRUGTOY, preset="builds_on")}
    for s in studies.values():
        for d in (d for d in s.dependencies if d.reuses == "result"):
            assert s.value_of(d.measurement) == original_value(studies[d.cites], s, d)


def test_limitations_use_recipe_categories():
    cats = set(DRUGTOY.limitations.categories)
    assert {l.category for s in generate(4, 16, recipe=DRUGTOY) for l in s.limitations} <= cats


def test_plain_preset_has_no_dependencies():
    assert all(not s.dependencies for s in generate(4, 16, recipe=DRUGTOY, preset="plain"))


# --- builds_on -------------------------------------------------------------------------------------------------

BUILT = generate(4, 16, recipe=DRUGTOY, spec=SPEC, preset="builds_on")   # spec given: no protocol load at import


def test_every_reuse_kind_is_planted_and_about_half_the_studies_build_on_one():
    kinds = Counter(d.reuses for s in BUILT for d in s.dependencies)
    assert set(kinds) == {"method", "dataset", "result"}
    assert 4 <= sum(kinds.values()) <= 12          # share 0.5 of the 15 studies that have an earlier one


def test_a_dependency_names_what_it_reuses():
    by_id = {s.study_id: s for s in BUILT}
    for s in BUILT:
        for d in s.dependencies:
            cited = by_id[d.cites]
            assert d.id.startswith(f"{s.study_id}.d")
            if d.reuses == "method":
                thing = next(c for c in s.conditions if c.id == d.thing)
                assert thing.label in {c.label for c in cited.conditions[:2]}
                assert thing.label != DRUGTOY.network.reference and d.measurement is None
            elif d.reuses == "dataset":
                assert d.thing is None and d.measurement is None and cited.datasets[0] == s.datasets[0]
            else:
                assert d.thing == s.control_condition.id
                m = next(m for m in s.measurements if m.id == d.measurement)
                assert m.condition == d.thing and m.copied_from == d.cites and m.metric == s.primary.id


def test_a_copied_result_keeps_exact_counts_and_the_latent_direction():
    rate = latent(4, DRUGTOY, SPEC)
    by_id = {s.study_id: s for s in BUILT}
    copied = [(s, d) for s in BUILT for d in s.dependencies if d.reuses == "result"]
    assert copied
    for s, d in copied:
        for m in s.measurements:
            assert m.value == m.k / s.arm_sizes[m.condition]
        m = next(m for m in s.measurements if m.id == d.measurement)
        source = next(o for o in by_id[d.cites].measurements if o.value == m.value and o.k == m.k)
        assert by_id[d.cites].arm_sizes[source.condition] == s.arm_sizes[m.condition]
        first, second = edge_of(s)
        want = "supports" if rate[(first, s.population)] > rate[(second, s.population)] else "contradicts"
        assert s.effect.direction == want
    # only copies carry copied_from
    assert sum(m.copied_from is not None for s in BUILT for m in s.measurements) == len(copied)


def test_builds_on_leaves_the_draws_of_the_plain_set_alone():
    """Only the copied arm of a result dependency changes: every other fact is the plain set's."""
    plain = {s.study_id: s for s in generate(4, 16, recipe=DRUGTOY)}
    for s in BUILT:
        copied_arms = {d.thing for d in s.dependencies if d.reuses == "result"}
        before = {m.id: m for m in plain[s.study_id].measurements}
        for m in s.measurements:
            if m.condition not in copied_arms:
                assert m == before[m.id]
        assert [c.label for c in s.conditions] == [c.label for c in plain[s.study_id].conditions]
        assert s.limitations == plain[s.study_id].limitations
        assert [c.variants for c in s.conditions] == [c.variants for c in plain[s.study_id].conditions]


def test_the_builds_on_preset_needs_a_recipe_block():
    with pytest.raises(SystemExit, match="builds_on"):
        generate(1, 6, recipe=load_recipe("rag"), preset="builds_on")
    with pytest.raises(SystemExit, match="preset"):
        generate(1, 6, preset="sideways")


def test_plain_preset_on_rag_is_the_pinned_task_2_set():
    pins = json.loads(PINS.read_text(encoding="utf-8"))["sets"]
    assert {str(s): hashlib.sha256(repr(generate(s, 6, preset="plain")).encode()).hexdigest()
            for s in (1, 2, 3)} == pins
    rag = generate(1, 6)
    assert all(not s.dependencies and not s.limitations and not any(c.variants for c in s.conditions) for s in rag)


def test_duplicates_carry_dependencies_and_limitations_renamed():
    studies = generate(4, 16, recipe=DRUGTOY, preset="builds_on", duplicates=16)
    by_id = {s.study_id: s for s in studies}
    for dup in (s for s in studies if s.duplicate_of):
        original = by_id[dup.duplicate_of]
        assert [(d.cites, d.reuses) for d in dup.dependencies] == [(d.cites, d.reuses) for d in original.dependencies]
        for d in dup.dependencies:
            assert d.id.startswith(dup.study_id) and (d.thing is None or d.thing.startswith(dup.study_id))
            assert d.measurement is None or dup.value_of(d.measurement) is not None
        assert [l.id.split(".")[1] for l in dup.limitations] == [l.id.split(".")[1] for l in original.limitations]
        assert all(l.thing.startswith(dup.study_id) for l in dup.limitations)


def test_missing_never_drops_a_copied_value():
    studies = generate(4, 16, recipe=DRUGTOY, preset="builds_on", missing=8)
    for s in studies:
        for d in s.dependencies:
            if d.measurement is not None:
                assert any(m.id == d.measurement for m in s.measurements)


# --- limitations -----------------------------------------------------------------------------------------------

def test_limitations_per_study_name_a_compared_thing_in_a_category_sentence():
    low, high = DRUGTOY.limitations.per_study
    for s in generate(4, 16, recipe=DRUGTOY):
        assert low <= len(s.limitations) <= high
        assert len({l.category for l in s.limitations}) == len(s.limitations)
        for i, l in enumerate(s.limitations):
            thing = next(c for c in s.conditions[:2] if c.id == l.thing)
            assert thing.label != DRUGTOY.network.reference and l.id == f"{s.study_id}.l{i + 1}"
            assert l.sentence in {t.replace("{thing}", thing.label) for t in DRUGTOY.limitations.categories[l.category]}


def test_irrelevant_papers_have_no_limitations():
    studies = generate(4, 6, recipe=DRUGTOY, irrelevant=2)
    assert all(not s.limitations for s in studies if not s.relevant)


# --- name variants ---------------------------------------------------------------------------------------------

VARIANTS = [(s, c, kind, form) for s in generate(4, 16, recipe=DRUGTOY, spec=SPEC) for c in s.conditions
            for kind, form in c.variants]


def test_variants_are_planted_of_every_kind_on_compared_things_only():
    assert {kind for *_, kind, _ in VARIANTS} == {"spelling", "code_name", "hereafter"}
    for s, c, _, _ in VARIANTS:
        assert c in s.conditions[:2] and c.label != DRUGTOY.network.reference and len(c.variants) == 1
    things = sum(1 for s in generate(4, 16, recipe=DRUGTOY) for c in s.conditions[:2]
                 if c.label != DRUGTOY.network.reference)
    assert 0.1 * things <= len(VARIANTS) <= 0.5 * things      # share 0.3


def test_a_variant_never_contains_another_things_name():
    others = {n.lower() for side in DRUGTOY.sides.values() for x in side.names for n in (x.label, x.synonym)}
    others |= {n.lower() for x in DRUGTOY.others for n in (x.label, x.synonym)}
    for _, c, _, form in VARIANTS:
        assert not any(o in form.lower() or form.lower() in o for o in others - {c.label.lower(), c.synonym.lower()})


def test_variant_forms_follow_the_generators_own_rules():
    """Spelling: upper case or a hyphen at the second syllable ("zel-vora"); hereafter: the parts' initials, distinct
    between things. Drawn by fixed rules: the generator never asks the engine's name grouping."""
    forms = truth.variant_forms(random.Random(0), DRUGTOY)
    assert forms["Zelvora"]["spelling"] == ["ZELVORA", "zel-vora"] and forms["Zelvora"]["hereafter"] == ["ZV"]
    shorts = [f for v in forms.values() for f in v["hereafter"]]
    assert len(shorts) == len(set(shorts)) == 3
    assert "evidence.names" not in Path(truth.__file__).read_text(encoding="utf-8")
    assert "from evidence import names" not in Path(truth.__file__).read_text(encoding="utf-8")
    for _, c, kind, form in VARIANTS:
        if kind == "spelling":
            assert form in (c.label.upper(), "-".join(p.lower() for p in truth._parts(c.label)))
        elif kind == "hereafter":
            assert form == truth._short_form(c.label)


def test_the_engine_joins_spelling_and_hereafter_variants():
    """A cross-check, not a filter: D38's clean step joins every spelling variant ("zel-vora" too), and its alias
    step a hereafter alias defined at the start of a clause. Code names are left to the model step."""
    for _, c, kind, form in VARIANTS:
        if kind == "spelling":
            assert len(names.group_names([names.Mention(c.label, "p", 0, 0, "x"),
                                          names.Mention(form, "q", 0, 0, "x")], {}).groups) == 1
        elif kind == "hereafter":
            text = f"{c.label} (hereafter {form}) was given."
            assert [(d.long, d.short) for d in abbrev.definitions(text)] == [(c.label, form)]


def test_a_thing_has_one_code_name_in_the_whole_set():
    codes: dict[str, set[str]] = {}
    for _, c, kind, form in VARIANTS:
        if kind == "code_name":
            codes.setdefault(c.label, set()).add(form)
            assert re.fullmatch(r"[A-Z]{2,}-\d{3}", form)
    assert codes and all(len(v) == 1 for v in codes.values())
    assert len({next(iter(v)) for v in codes.values()}) == len(codes)


# --- truth records, settings, command line ---------------------------------------------------------------------

def record_of(s: truth.Study, spec=SPEC) -> dict:
    plan = make_plan(s, "explicit", random.Random(0))
    return corpus.study_truth(corpus.Rendered(s, plan, "", [], [], None), spec)


def test_ground_truth_records_dependencies_limitations_and_variants():
    records = [record_of(s) for s in BUILT]
    assert all("dependencies" in r and "limitations" in r for r in records)
    deps = [d for r in records for d in r["dependencies"]]
    assert {d["reuses"] for d in deps} == {"method", "dataset", "result"}
    assert all(set(d) == {"id", "cites", "reuses", "thing", "measurement"} for d in deps)
    copied = [m for r in records for m in r["measurements"] if "copied_from" in m]
    assert len(copied) == sum(d["reuses"] == "result" for d in deps)
    assert all(set(l) == {"id", "thing", "category", "sentence"} for r in records for l in r["limitations"])
    variants = [v for r in records for c in r["conditions"] for v in c.get("variants", [])]
    assert variants and all(len(v) == 2 for v in variants)
    assert all("variants" not in c for r in records for c in r["conditions"][2:])


def test_rag_records_and_settings_gain_no_keys():
    r = record_of(generate(1, 2)[0], truth.default_spec())
    assert not {"dependencies", "limitations"} & set(r)
    assert not any("variants" in c for c in r["conditions"])
    assert not any("copied_from" in m for m in r["measurements"])
    plain = corpus.settings_of(name="n", studies=6, mix=None, levels=["explicit"])
    assert "preset" not in plain and corpus.settings_of(name="n", studies=6, mix=None, levels=["explicit"],
                                                        preset="plain") == plain
    assert corpus.settings_of(name="n", studies=6, mix=None, levels=["explicit"],
                              preset="builds_on")["preset"] == "builds_on"


def test_cli_passes_the_preset_to_the_build(tmp_path, monkeypatch):
    seen = {}

    def fake_build(**kwargs):
        seen.update(kwargs)
        return {"corpora": {}, "excluded": {}, "selection": {"requested_studies": 0}}
    monkeypatch.setattr(corpus, "build", fake_build)
    assert synth_main(["build", "--name", "c", "--seed", "4", "--out", str(tmp_path), "--preset", "builds_on"]) == 0
    assert seen["preset"] == "builds_on"
    assert synth_main(["build", "--name", "c", "--seed", "4", "--out", str(tmp_path)]) == 0
    assert seen["preset"] == "plain"
    with pytest.raises(SystemExit):
        synth_main(["build", "--name", "c", "--seed", "4", "--out", str(tmp_path), "--preset", "other"])


@pytest.mark.parametrize("old,new,match", [
    ("skip doses of {thing}.", "skip doses of the drug.", "naming"),
    ("per_study: [1, 2]", "per_study: [2, 1]", "per_study"),
    ("  share: 0.5\n", "  share: 1.5\n", "shares"),
    ("    result: 0.4\n", "    result: -0.4\n", "reuses"),
    ("costs much more than", "costs 3 times more than", "digit"),
])
def test_recipe_planted_blocks_are_checked(tmp_path, old, new, match):
    folder = tmp_path / "drugtoy"
    folder.mkdir()
    text = (FIXTURES / "drugtoy" / "generator.yaml").read_text(encoding="utf-8")
    assert old in text
    (folder / "generator.yaml").write_text(text.replace(old, new), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        load_recipe("drugtoy", root=tmp_path)


class _Named:
    name = "fake"

    def models(self):
        return None


def written_truth(tmp_path, excluded: set[str]) -> dict:
    """ground_truth.json of the builds_on set written with `excluded` left out as fidelity failures."""
    from evidence import protocol as protocol_module
    from synth.fidelity import PaperFidelity
    from synth.recipe import effect_protocol_path
    proto = protocol_module.load(effect_protocol_path(DRUGTOY), FIXTURES)
    papers = {s.study_id: corpus.Rendered(s, make_plan(s, "explicit", random.Random(0)), "text", [], [],
                                          PaperFidelity(s.study_id, s.study_id not in excluded, []))
              for s in BUILT}
    corpus.write_corpus(tmp_path / "c", name="c", level="explicit", seed=4, renderer=_Named(), protocol=proto,
                        studies=BUILT, papers=papers, failed={sid: ["explicit"] for sid in excluded},
                        settings=corpus.settings_of(name="c", studies=16, mix=None, levels=["explicit"],
                                                    preset="builds_on"))
    return json.loads((tmp_path / "c" / "ground_truth.json").read_text(encoding="utf-8"))


def test_truth_drops_links_to_excluded_studies_and_orphan_copies(tmp_path):
    copy_study, dep = next((s, d) for s in BUILT for d in s.dependencies if d.reuses == "result")
    other = next(d.cites for s in BUILT for d in s.dependencies if d.reuses != "result" and d.cites != dep.cites)
    gt = written_truth(tmp_path, {dep.cites, other})
    records = {r["study_id"]: r for r in gt["studies"]}
    assert dep.cites not in records and other not in records
    assert all(d["cites"] in records for r in records.values() for d in r["dependencies"])
    copied = next(m for m in records[copy_study.study_id]["measurements"] if m["id"] == dep.measurement)
    assert "copied_from" not in copied and copied["value"] == copy_study.value_of(dep.measurement)
    # nothing excluded: every link and mark is written
    full = {r["study_id"]: r for r in written_truth(tmp_path / "all", set())["studies"]}
    assert sum(len(r["dependencies"]) for r in full.values()) == sum(len(s.dependencies) for s in BUILT)
    assert any(m.get("copied_from") == dep.cites for m in full[copy_study.study_id]["measurements"])
