"""Comparisons built from pairs in a study (plan 2 Task 8, spec section 6.2): every pair of compared things with
values on one metric and one context in a document is a comparison, written to comparisons.json for every kind; a
result copied from an earlier study counts once, at its origin (section 6.11). Also the kinds the plan adds
(chaining, limitations, builds_on) are known to protocols, packs and question files, and a value's context is read
from the pack's type of role `context` into the pack's `context_field`."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from evidence import contract, engine
from evidence.comparisons import Comparison, build_comparisons, of_run, resolve_cited, settings
from evidence.contract import Item, Span
from evidence.extractors import base
from evidence.names import NameGroups
from evidence.pack import DOMAINS, PackError, RoleMap, load_pack, register_pack
from evidence.protocol import load, parse
from evidence.questions import parse as parse_questions
from evidence.replay import replay

from .conftest import context_id, corpus_of, provider_of, regex_run_dir, run_json, scripted
from .test_pack_configs import OLD_SHA

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
DRUGTOY = FIXTURES / "drugtoy"
RESPONSE = DRUGTOY / "protocols" / "drugtoy-response.yaml"
BUILDS = DRUGTOY / "protocols" / "drugtoy-builds.yaml"
RAG_PROTOCOLS = sorted((DOMAINS / "rag" / "protocols").glob("*.yaml"))
GROUPS = NameGroups(groups={"Morvectin": ["Morvectin", "MV-3"], "Quintapride": ["Quintapride"],
                            "placebo": ["placebo", "Placebo"]}, matches=[], unresolved=[])


@pytest.fixture(autouse=True)
def _registry():
    """Each test leaves the type registry as it found it (the drugtoy pack registers its types)."""
    before = dict(contract.ITEM_PREFIX)
    register_pack(load_pack("drugtoy", root=FIXTURES))
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


ROLES = RoleMap(load_pack("drugtoy", root=FIXTURES))
KNOBS: dict[str, Any] = {"higher_is_better": lambda canonical: True, "min_effect": 0.01,
                         "prefer": ("table_cell", "document_order")}


class Paper:
    """Hand-built items of one paper, each placed at the next position (document order is build order)."""

    def __init__(self, doc: str = "p1") -> None:
        self.doc, self.at, self.items = doc, 0, []
        self.metric = self.add("outcome", {"name": "response rate", "canonical": "response_rate",
                                           "higher_is_better": True}, "metric_label")

    def add(self, etype: str, fields: dict[str, Any], role: str, links: dict[str, str] | None = None) -> Item:
        self.at += 10
        span = Span(role=role, selector={"file": f"papers/{self.doc}.md", "start": self.at, "end": self.at + 4,
                                         "exact": "x", "prefix": "", "suffix": ""})
        item = Item.build(etype, fields, [span], links=links)
        self.items.append(item)
        return item

    def arm(self, label: str, role: str = "drug") -> Item:
        return self.add("arm", {"label": label, "role": role}, "condition_label")

    def value(self, arm: Item, value: float, population: str | None = "adults", source: Item | None = None) -> Item:
        links = {"arm": arm.item_id, "outcome": self.metric.item_id, **({"source": source.item_id} if source else {})}
        return self.add("result", {"value": value, "population": population}, "value", links)

    def cites(self, label: str, reuses: str = "result") -> Item:
        return self.add("dependency", {"cited": label, "reuses": reuses}, "citation")

    def label(self, label: str) -> Item:
        return self.add("study_label", {"label": label}, "label")


def build(items: list[Item], groups: NameGroups | None = None, doc: str = "p1",
          cited: dict[str, str | None] | None = None) -> list[Comparison]:
    return build_comparisons(doc, items, ROLES, groups, cited=cited, **KNOBS)


def three_arm_items() -> list[Item]:
    p = Paper()
    for label, rate in (("Morvectin", 0.41), ("Quintapride", 0.35), ("placebo", 0.18)):
        p.value(p.arm(label, "placebo" if label == "placebo" else "drug"), rate)
    return p.items


def two_arms_two_populations() -> list[Item]:
    p = Paper()
    p.value(p.arm("Zelvora"), 0.4, "adults")
    p.value(p.arm("placebo", "placebo"), 0.2, "children")
    return p.items


# --- rules 1-3, 5, 6 ------------------------------------------------------------------------------------------

def test_three_arms_give_three_comparisons():
    cs = build(three_arm_items(), groups=GROUPS)
    assert {(c.a, c.b) for c in cs} == {("Morvectin", "Quintapride"), ("Morvectin", "placebo"), ("Quintapride", "placebo")}


def test_values_on_different_populations_do_not_pair():
    assert build(two_arms_two_populations(), groups=GROUPS) == []


def test_a_comparison_is_a_over_b_with_its_values_and_context():
    [c] = [c for c in build(three_arm_items(), groups=GROUPS) if (c.a, c.b) == ("Quintapride", "placebo")]
    assert (c.metric, c.context, c.a_value, c.b_value, c.direction, c.delta) == (
        "response_rate", "adults", 0.35, 0.18, "supports", 0.17)
    assert c.copied_from is None and c.id.startswith("cmp-") and len(c.id) == len("cmp-") + 16
    assert c.document == "p1" and len(c.items) == 5   # two values, two arms, one metric


def test_ids_are_stable():
    assert [c.id for c in build(three_arm_items())] == [c.id for c in build(three_arm_items())]


def test_a_value_naming_no_population_joins_a_named_one():
    p = Paper()
    p.value(p.arm("Zelvora"), 0.4, "adults")
    p.value(p.arm("placebo", "placebo"), 0.2, None)
    [c] = build(p.items)
    assert (c.a, c.b, c.context) == ("placebo", "Zelvora", "adults")


def test_each_shared_population_is_its_own_comparison():
    p = Paper()
    z, pl = p.arm("Zelvora"), p.arm("placebo", "placebo")
    p.value(z, 0.4, "adults"), p.value(pl, 0.2, "adults"), p.value(z, 0.3, "children"), p.value(pl, 0.25, "children")
    assert [(c.context, c.a_value, c.b_value) for c in build(p.items)] == [("adults", 0.2, 0.4), ("children", 0.25, 0.3)]


def test_the_earlier_value_of_a_thing_is_preferred():
    p = Paper()
    z = p.arm("Zelvora")
    p.value(z, 0.4)
    p.value(p.arm("placebo", "placebo"), 0.2)
    p.value(z, 0.9)
    assert [c.b_value for c in build(p.items)] == [0.4]


def test_without_groups_names_match_by_their_clean_form():
    p = Paper()
    p.value(p.arm("Zelvora"), 0.4)
    p.value(p.arm("Placebo", "placebo"), 0.2)
    p.value(p.arm("placebo", "placebo"), 0.25)
    assert [(c.a, c.b, c.a_value) for c in build(p.items)] == [("Placebo", "Zelvora", 0.2)]


def test_with_groups_a_code_name_is_its_group():
    p = Paper()
    p.value(p.arm("MV-3"), 0.4)
    p.value(p.arm("placebo", "placebo"), 0.2)
    assert [(c.a, c.b) for c in build(p.items, GROUPS)] == [("Morvectin", "placebo")]
    assert [(c.a, c.b) for c in build(p.items)] == [("MV-3", "placebo")]


def test_a_neutral_difference_is_neutral():
    p = Paper()
    p.value(p.arm("Zelvora"), 0.205)
    p.value(p.arm("placebo", "placebo"), 0.2)
    assert [c.direction for c in build(p.items)] == ["neutral"]


# --- rule 4: copied results -----------------------------------------------------------------------------------

def origin_and_copier() -> dict[str, list[Item]]:
    """origin: Zelvora 0.34 against placebo 0.17. copier: the same Zelvora value, the placebo value taken from
    origin, and Quintapride against that copied placebo."""
    o = Paper("origin")
    o.label("Halvorsen et al. (2019)")
    o.value(o.arm("Zelvora"), 0.34)
    o.value(o.arm("placebo", "placebo"), 0.17)
    c = Paper("copier")
    c.label("Brennick et al. (2021)")
    dep = c.cites("Halvorsen et al. (2019)")
    c.value(c.arm("Zelvora"), 0.34)
    c.value(c.arm("Quintapride"), 0.29)
    c.value(c.arm("placebo", "placebo"), 0.17, source=dep)
    return {"origin": o.items, "copier": c.items}


def test_a_cited_label_resolves_to_its_document():
    items = origin_and_copier()
    assert resolve_cited(["origin", "copier"], items, ROLES, None) == {"Halvorsen et al. (2019)": "origin"}
    assert resolve_cited(["copier"], items, ROLES, None) == {"Halvorsen et al. (2019)": None}


def test_a_copied_value_names_its_origin():
    items = origin_and_copier()
    cited = resolve_cited(["origin", "copier"], items, ROLES, None)
    copied = {(c.a, c.b): c.copied_from for c in build(items["copier"], doc="copier", cited=cited)}
    assert copied == {("Quintapride", "Zelvora"): None, ("placebo", "Quintapride"): "origin",
                      ("placebo", "Zelvora"): "origin"}


def test_an_unresolved_copy_names_no_document_and_keeps_the_cited_text():
    items = origin_and_copier()
    cs = build(items["copier"], doc="copier")
    assert {c.copied_from for c in cs} == {None}
    assert {(c.a, c.b): c.cited_text for c in cs} == {("Quintapride", "Zelvora"): None,
                                                      ("placebo", "Quintapride"): "Halvorsen et al. (2019)",
                                                      ("placebo", "Zelvora"): "Halvorsen et al. (2019)"}


def test_a_comparison_of_two_copied_values_is_dropped():
    p = Paper()
    dep = p.cites("Halvorsen et al. (2019)")
    p.value(p.arm("Zelvora"), 0.34, source=dep)
    p.value(p.arm("placebo", "placebo"), 0.17, source=dep)
    assert build(p.items) == []


def test_a_reused_method_copies_no_value():
    p = Paper()
    dep = p.cites("Halvorsen et al. (2019)", reuses="method")
    p.value(p.arm("Zelvora"), 0.34, source=dep)
    p.value(p.arm("placebo", "placebo"), 0.17)
    assert [c.copied_from for c in build(p.items)] == [None]


def test_a_copy_of_its_origins_comparison_is_listed_as_copied():
    out = of_run(load(BUILDS, FIXTURES), ["origin", "copier"], origin_and_copier(), ROLES, None)
    assert [(c.document, c.a, c.b) for c in out.comparisons] == [
        ("origin", "placebo", "Zelvora"), ("copier", "placebo", "Quintapride"), ("copier", "Quintapride", "Zelvora")]
    assert [(c.document, c.a, c.b, c.copied_from) for c in out.copied] == [("copier", "placebo", "Zelvora", "origin")]
    assert out.json()["min_effect"] == 0.01


def test_a_copy_spelled_otherwise_is_still_counted_once():
    """names off: the origin writes "placebo", the copier "Placebo"; the copy is found and a/b do not flip."""
    items = origin_and_copier()
    c = Paper("copier")
    c.label("Brennick et al. (2021)")
    dep = c.cites("Halvorsen et al. (2019)")
    c.value(c.arm("Zelvora"), 0.34)
    c.value(c.arm("Placebo", "placebo"), 0.17, source=dep)
    items["copier"] = c.items
    out = of_run(load(BUILDS, FIXTURES), ["origin", "copier"], items, ROLES, None)
    assert [(x.document, x.a, x.b, x.direction) for x in out.comparisons] == [("origin", "placebo", "Zelvora", "contradicts")]
    assert [(x.document, x.a, x.b, x.direction, x.copied_from) for x in out.copied] == [
        ("copier", "Placebo", "Zelvora", "contradicts", "origin")]


ORIGIN = ("# Zelvora trial\n\nHalvorsen et al. (2019)\n\nWe enrolled adults with the condition.\n\n"
          "The response rate was 0.34 for Zelvora and 0.17 for placebo.\n")
COPIER = ("# A second Zelvora trial\n\nBrennick et al. (2021)\n\nWe enrolled adults with the condition.\n\n"
          "The response rate was 0.34 for Zelvora. For placebo, the response rate is taken as reported by "
          "Halvorsen et al. (2019): 0.17.\n")
LABELS = {"origin": "Halvorsen et al. (2019)", "copier": "Brennick et al. (2021)"}


def builds_script(kind: str, doc: str, prompt: str) -> dict[str, Any]:
    """The careful reader of ORIGIN and COPIER: its population and byline, the copier's dependency on origin's result,
    and each arm's value; the copier's placebo value links the dependency."""
    if kind == "population":
        return {"items": [{"fields": {"name": "adults"}, "quotes": {"population_label": "adults with the condition"}}]}
    if kind == "study_label":
        return {"items": [{"fields": {"label": LABELS[doc]}, "quotes": {"label": LABELS[doc]}}]}
    if kind == "dependency" and doc == "copier":
        return {"items": [{"fields": {"cited": "Halvorsen et al. (2019)", "reuses": "result"},
                           "quotes": {"citation": "as reported by Halvorsen et al. (2019)"}}]}
    if kind == "result":
        rate = context_id(prompt, '"response_rate"')
        source = context_id(prompt, '"result"') if doc == "copier" else None

        def value(arm: str, number: str, linked: str | None) -> dict[str, Any]:
            return {"fields": {"value": float(number), "population": "adults"},
                    "links": {"arm": context_id(prompt, f'"{arm}"'), "outcome": rate, "source": linked},
                    "quotes": {"value": number, "condition_label": None, "metric_label": None}}
        return {"items": [value("Zelvora", "0.34", None), value("placebo", "0.17", source)]}
    return {"quotes": []} if kind == "retry" else {"items": []}


def builds_run(tmp_path: Path) -> Path:
    corpus = corpus_of(tmp_path / "corpus", {"origin": ORIGIN, "copier": COPIER})
    return engine.run(BUILDS, corpus, tmp_path / "runs", cache=tmp_path / "cache", model="scripted-alias",
                      provider=provider_of(scripted(builds_script, [])), strategy="all", confirm="none",
                      domains=FIXTURES)


def test_copied_control_counts_once_at_origin(tmp_path):
    out = builds_run(tmp_path)
    data = json.loads((out / "comparisons.json").read_text(encoding="utf-8"))
    assert [(c["document"], c["a"], c["b"]) for c in data["comparisons"]] == [("origin", "placebo", "Zelvora")]
    assert len(data["copied"]) == 1 and data["copied"][0]["copied_from"] == "origin"
    assert data["copied"][0]["document"] == "copier"
    assert "comparisons.json" in run_json(out)["outputs"]


def test_a_run_replays_its_comparisons(tmp_path):
    _, report = replay(builds_run(tmp_path))
    assert report["ok"] and "added" not in report, report


def test_a_run_made_before_comparisons_replays_with_the_file_added(tmp_path):
    out = regex_run_dir(["The response rate was 34% for Zelvora and 12% for placebo."], tmp_path, RESPONSE,
                        domains=FIXTURES)
    record = run_json(out)
    del record["outputs"]["comparisons.json"]   # a run recorded before the step
    (out / "run.json").write_text(json.dumps(record), encoding="utf-8")
    (out / "comparisons.json").unlink()
    _, report = replay(out)
    assert report["ok"] and report["added"] == ["comparisons.json"] and report["mismatched"] == [], report


def test_every_kind_writes_comparisons(tmp_path):
    out = regex_run_dir(["The response rate was 34% for Zelvora and 12% for placebo."], tmp_path, RESPONSE,
                        domains=FIXTURES)
    data = json.loads((out / "comparisons.json").read_text(encoding="utf-8"))
    assert [(c["a"], c["b"], c["a_value"], c["b_value"], c["context"]) for c in data["comparisons"]] == [
        ("placebo", "Zelvora", 0.12, 0.34, None)]
    assert data["min_effect"] == 0.01
    assert data["copied"] == []


# --- the context of a value -----------------------------------------------------------------------------------

def test_the_number_reader_writes_the_packs_context_field(tmp_path):
    out = regex_run_dir(["The response rate was 34% for Zelvora."], tmp_path, RESPONSE, domains=FIXTURES)
    items = [json.loads(x) for x in (out / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    results = [i["fields"] for i in items if i["evidence_type"] == "result"]
    assert results and all("population" in f and "dataset" not in f for f in results)


def test_the_context_type_is_found_by_role():
    words = load_pack("drugtoy", root=FIXTURES).extractor_config("result", "number_measurement")
    slots = base.Slots.of({k: words[k] for k in ("types", "context_field")})
    assert (slots.context, slots.context_field) == ("population", "population")
    assert (base.Slots().context, base.Slots().context_field) == ("dataset", "dataset")


def test_the_rag_pack_gives_no_context_field_to_its_extractors():
    assert "context_field" not in load_pack("rag").extractor_config("measurement", "number_measurement")


def test_a_metric_takes_its_direction_from_the_pack_else_none(tmp_path):
    p = Paper()
    lower = p.add("outcome", {"name": "adverse events", "canonical": "adverse_rate", "higher_is_better": False},
                  "metric_label")
    unknown = p.add("outcome", {"name": "visits", "canonical": "visits", "higher_is_better": True}, "metric_label")
    z, pl = p.arm("Zelvora"), p.arm("placebo", "placebo")
    for metric, zv, pv in ((lower, 0.1, 0.3), (unknown, 4.0, 2.0)):
        for arm, v in ((z, zv), (pl, pv)):
            p.add("result", {"value": v, "population": "adults"}, "value",
                  {"arm": arm.item_id, "outcome": metric.item_id})
    knobs = settings(load(BUILDS, FIXTURES))
    knobs["higher_is_better"] = adverse_pack_settings(tmp_path)["higher_is_better"]
    got = {c.metric: (c.direction, c.delta) for c in build_comparisons("p1", p.items, ROLES, None, **knobs)}
    # placebo (a) 0.3 against Zelvora (b) 0.1 on a lower-is-better rate: placebo is worse; visits: no direction known
    assert got == {"adverse_rate": ("contradicts", -0.2), "visits": (None, None)}


def adverse_pack_settings(root: Path) -> dict[str, Any]:
    """settings() of drugtoy-builds over a copy of the drugtoy pack whose words.metrics add a lower-is-better rate."""
    shutil.copytree(DRUGTOY, root / "drugtoy", dirs_exist_ok=True)
    words = root / "drugtoy" / "words.yaml"
    added = "metrics:\n- - (?i)\\badverse\\s+events\\b\n  - adverse_rate\n  - false\n"
    words.write_text(words.read_text(encoding="utf-8").replace("metrics:\n", added, 1), encoding="utf-8")
    return settings(load(root / "drugtoy" / "protocols" / "drugtoy-builds.yaml", root))


def test_settings_take_the_packs_metric_directions(tmp_path):
    better = adverse_pack_settings(tmp_path)["higher_is_better"]
    assert (better("response_rate"), better("adverse_rate"), better("visits")) == (True, False, None)


def test_settings_follow_the_protocols_kind():
    knobs = settings(load(BUILDS, FIXTURES))
    assert knobs["min_effect"] == 0.01 and knobs["prefer"] == ("table_cell", "document_order")
    assert knobs["higher_is_better"]("response_rate") is True


# --- the new kinds --------------------------------------------------------------------------------------------

def test_rag_protocol_hashes_unchanged_by_new_kinds():
    for path in RAG_PROTOCOLS:
        assert load(path).sha256 == OLD_SHA[path.stem]


CHAINING = """
id: drugtoy-chain
domain: drugtoy
version: 2
question: Is Zelvora better than Morvectin on the response rate?
kind: chaining
evidence_types:
  arm:
    fields: {type: object, properties: {label: {type: string}, role: {type: string}}}
    roles: [condition_label]
    extractors: [{name: regex_condition}]
chaining: {source: Zelvora, target: Morvectin, metric: {canonical: response_rate, higher_is_better: true},
           min_effect: 0.01}
"""


def test_a_chaining_protocol_parses_with_its_block():
    p = parse(CHAINING, FIXTURES)
    assert p.kind == "chaining" and p.chaining is not None and p.chaining.max_hops == 2


def test_a_new_kind_without_its_block_is_refused():
    with pytest.raises(ValueError, match="needs its chaining block"):
        parse(CHAINING.split("chaining: {source")[0], FIXTURES)


@pytest.mark.parametrize("kind,block,role", [("limitations", "limitations: {}", "limitation"),
                                             ("builds_on", "builds_on: {thing: null}", "dependency")])
def test_a_pack_without_the_kinds_role_is_refused(kind, block, role):
    text = f"""
id: rag-{kind.replace('_', '-')}
version: 2
question: Which?
kind: {kind}
evidence_types:
  condition:
    fields: {{type: object, properties: {{label: {{type: string}}}}}}
    roles: [condition_label]
    extractors: [{{name: regex_condition}}]
{block}
"""
    with pytest.raises(ValueError, match=f"no type has role '{role}'"):
        parse(text)


def test_an_optional_link_names_a_link():
    text = BUILDS.read_text(encoding="utf-8").replace("optional_links: [source]", "optional_links: [cited_by]")
    with pytest.raises(ValueError, match="optional_links names"):
        parse(text, FIXTURES)


def test_the_drugtoy_questions_take_the_chaining_truth():
    entries = parse_questions(DRUGTOY / "questions.yaml").questions
    chain = next(q for q in entries if q.kind == "chaining")
    assert (chain.truth.source, chain.truth.target, chain.truth.metric) == ("Zelvora", "Morvectin", "response_rate")


def test_a_chaining_truth_field_is_refused_on_an_effect_question(tmp_path):
    path = tmp_path / "questions.yaml"
    path.write_text("questions:\n  - {id: q, question: Which, kind: effect, truth: {source: Zelvora}}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not belong to kind 'effect'"):
        parse_questions(path)


def test_pack_check_knows_the_new_kinds():
    from evidence.pack import check
    check(load_pack("drugtoy", root=FIXTURES), ["chaining", "limitations", "builds_on"])
    with pytest.raises(PackError, match="needed by kind 'limitations'"):
        check(load_pack("rag"), ["limitations"])
