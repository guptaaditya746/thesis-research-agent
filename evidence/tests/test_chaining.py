"""Kind `chaining` (plan 2 Task 9, spec section 6.10): from A over B and B over C on one metric and one context,
conclude A over C, marked inferred; a direct result is never chained; every refusal is named (rules.CHAIN_REASONS)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evidence import contract, engine, rules
from evidence.comparisons import Comparison, Comparisons, thing_key
from evidence.kinds import MODULES, chaining
from evidence.names import NameGroups
from evidence.pack import load_pack, register_pack
from evidence.protocol import load
from evidence.questions import parse as parse_questions, protocol_file
from evidence.replay import replay

from .conftest import context_id, corpus_of, provider_of, scripted

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
DRUGTOY = FIXTURES / "drugtoy"
CHAIN = DRUGTOY / "protocols" / "drugtoy-chain.yaml"
VALUES = {"better": (0.5, 0.3), "worse": (0.3, 0.5), "no_difference": (0.4, 0.4)}   # x's and y's value


@pytest.fixture(autouse=True)
def _registry():
    """Each test leaves the type registry as it found it (the drugtoy pack registers its types)."""
    before = dict(contract.ITEM_PREFIX)
    register_pack(load_pack("drugtoy", root=FIXTURES))
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def cmps(*rows: tuple[str, str, str, str | None, str], metric: str = "response_rate",
         groups: NameGroups | None = None) -> list[Comparison]:
    """Comparisons from (x, y, x's result against y, context, document) rows. As comparisons.json writes them, `a`
    is the thing whose key sorts first and `direction` is a over b (P13): a row whose x sorts after y is turned."""
    out = []
    for n, (x, y, result, context, doc) in enumerate(rows):
        xv, yv = VALUES[result]
        (a, av), (b, bv) = sorted(((x, xv), (y, yv)), key=lambda t: thing_key(t[0], groups).split(":", 1)[1])
        direction, delta = rules.effect(av, bv, True, 0.01)
        out.append(Comparison(id=f"cmp-{n}", document=doc, a=a, b=b, metric=metric, context=context, a_value=av,
                              b_value=bv, direction=direction, delta=delta, items=(f"i{n}a", f"i{n}b"),
                              copied_from=None))
    return out


def groups_joining(*forms: str) -> NameGroups:
    return NameGroups(groups={forms[0]: list(forms)}, matches=[], unresolved=[])


def protocol(source: str = "A", target: str = "C", max_hops: int = 2):
    p = load(CHAIN, FIXTURES)
    assert p.chaining is not None
    return p.model_copy(update={"chaining": p.chaining.model_copy(update={"source": source, "target": target,
                                                                          "max_hops": max_hops})})


def answer(found: list[Comparison], *, source: str, target: str, groups: NameGroups | None = None,
           max_hops: int = 2) -> dict[str, Any]:
    documents = sorted({c.document for c in found})
    out, _ = chaining.answer(protocol(source, target, max_hops), documents, {}, groups=groups,
                             comparisons=Comparisons(comparisons=tuple(found), min_effect=0.01))
    return out


# --- the brief's tests ------------------------------------------------------------------------------------------

def test_chain_concludes_and_is_marked_inferred():
    a = answer(cmps(("A", "B", "better", "adults", "s1"), ("B", "C", "better", "adults", "s2")), source="A", target="C")
    assert (a["verdict"], a["inferred"], a["via"], a["studies"]) == ("better", True, ["B"], ["s1", "s2"])
    assert a["note"] == "inferred through B, not tested directly"


def test_chain_refused_across_populations():
    a = answer(cmps(("A", "B", "better", "adults", "s1"), ("B", "C", "better", "children", "s2")), source="A", target="C")
    assert (a["verdict"], a["reason"]) == ("refused", "context_differs")


def test_chain_through_name_variant():
    a = answer(cmps(("A", "Drug B", "better", None, "s1"), ("drug-B", "C", "better", None, "s2")), source="A", target="C",
               groups=groups_joining("Drug B", "drug-B"))
    assert a["verdict"] == "better"


def test_direct_result_is_never_chained():
    a = answer(cmps(("A", "C", "worse", None, "s3"), ("A", "B", "better", None, "s1"), ("B", "C", "better", None, "s2")), source="A", target="C")
    assert (a["verdict"], a["inferred"], a["reason"]) == ("worse", False, "direct_comparison")


@pytest.mark.parametrize("d1,d2", [("better", "worse"), ("better", "no_difference")])
def test_mixed_steps_are_refused(d1, d2):
    assert answer(cmps(("A", "B", d1, None, "s1"), ("B", "C", d2, None, "s2")), source="A", target="C")["reason"] == "mixed_directions"


# --- more rules ---------------------------------------------------------------------------------------------------

def test_the_answer_has_every_field():
    a = answer(cmps(("A", "B", "worse", "adults", "s1"), ("B", "C", "worse", None, "s2")), source="A", target="C")
    assert set(a) == {"kind", "system", "source", "target", "metric", "verdict", "inferred", "via", "studies", "paths",
                      "reason", "note"}
    assert (a["kind"], a["source"], a["target"], a["metric"], a["verdict"], a["reason"]) == (
        "chaining", "A", "C", "response_rate", "worse", None)
    assert a["paths"] == [{"via": ["B"], "verdict": "worse", "reason": None, "steps": [
        {"comparison": "cmp-0", "document": "s1", "from": "A", "to": "B", "metric": "response_rate",
         "direction": "worse", "context": "adults"},
        {"comparison": "cmp-1", "document": "s2", "from": "B", "to": "C", "metric": "response_rate",
         "direction": "worse", "context": None}]}]


def test_a_step_walked_against_its_comparison_is_turned():
    """comparisons.json stores B over A as "a vs b" with a = A; walking A -> B reads it the other way round (P13)."""
    a = answer(cmps(("B", "A", "worse", None, "s1"), ("C", "B", "worse", None, "s2")), source="A", target="C")
    assert (a["verdict"], a["paths"][0]["steps"][0]["direction"]) == ("better", "better")


def test_a_direct_no_difference_is_the_answer():
    a = answer(cmps(("A", "C", "no_difference", "adults", "s1")), source="A", target="C")
    assert (a["verdict"], a["inferred"], a["reason"], a["via"], a["note"]) == (
        "no_difference", False, "direct_comparison", [], None)


def test_disagreeing_direct_results_are_refused():
    a = answer(cmps(("A", "C", "better", None, "s1"), ("A", "C", "worse", None, "s2")), source="A", target="C")
    assert (a["verdict"], a["inferred"], a["reason"], a["studies"]) == ("refused", False, "direct_comparison",
                                                                         ["s1", "s2"])


def test_paths_with_different_verdicts_disagree():
    a = answer(cmps(("A", "B", "better", "adults", "s1"), ("B", "C", "better", "adults", "s2"),
                    ("A", "D", "worse", "children", "s3"), ("D", "C", "worse", "children", "s4")),
               source="A", target="C")
    assert (a["verdict"], a["reason"], a["inferred"], a["note"]) == ("refused", "paths_disagree", False, None)
    assert (a["via"], a["studies"]) == (["B", "D"], ["s1", "s2", "s3", "s4"])


def test_a_refused_path_beside_a_concluding_one_does_not_count():
    a = answer(cmps(("A", "B", "better", "adults", "s1"), ("B", "C", "better", "adults", "s2"),
                    ("B", "C", "better", "children", "s3")), source="A", target="C")
    assert (a["verdict"], a["studies"]) == ("better", ["s1", "s2"])
    assert [p["reason"] for p in a["paths"]] == [None, "context_differs"]


def test_a_path_only_on_another_metric_is_metric_differs():
    """Preflight T9: metric_differs when a path exists only on other metrics, no_path when there is none at all."""
    found = cmps(("A", "B", "better", None, "s1")) + cmps(("B", "C", "better", None, "s2"), metric="adverse_rate")
    a = answer(found, source="A", target="C")
    assert (a["verdict"], a["reason"], a["inferred"], a["studies"]) == ("refused", "metric_differs", False, ["s1", "s2"])


def test_no_path_at_all_is_no_path():
    a = answer(cmps(("A", "B", "better", None, "s1"), ("D", "C", "better", None, "s2")), source="A", target="C")
    assert (a["verdict"], a["reason"], a["paths"], a["studies"], a["via"]) == ("refused", "no_path", [], [], [])


def test_a_path_longer_than_max_hops_is_not_taken():
    rows = (("A", "B", "better", None, "s1"), ("B", "D", "better", None, "s2"), ("D", "C", "better", None, "s3"))
    assert answer(cmps(*rows), source="A", target="C")["reason"] == "no_path"
    a = answer(cmps(*rows), source="A", target="C", max_hops=3)
    assert (a["verdict"], a["via"], a["note"]) == ("better", ["B", "D"], "inferred through B, D, not tested directly")


def test_every_reason_is_a_chain_reason():
    assert {"direct_comparison", "no_path", "metric_differs", "context_differs", "mixed_directions",
            "paths_disagree"} == set(rules.CHAIN_REASONS)


def test_answer_takes_and_ignores_a_reason_keyword():
    found = cmps(("A", "B", "better", None, "s1"), ("B", "C", "better", None, "s2"))
    out, used = chaining.answer(protocol(), ["s1", "s2"], {}, comparisons=Comparisons(comparisons=tuple(found)),
                                reason=object())
    assert out["verdict"] == "better" and used == ["i0a", "i0b", "i1a", "i1b"]


def test_the_kind_is_registered():
    assert MODULES["chaining"] is chaining


def test_no_path_escalates_measured_values():
    p = protocol()
    assert chaining.gap_types(p, "no_path", roles=p.roles()) == ("result",)
    assert chaining.gap_types(p, "screened_out", roles=p.roles()) == ()


def test_the_drugtoy_chain_question_has_its_protocol():
    entry = next(q for q in parse_questions(DRUGTOY / "questions.yaml").questions if q.kind == "chaining")
    assert entry.protocol is not None
    p = load(protocol_file(entry.protocol, DRUGTOY / "questions.yaml"), FIXTURES)
    assert (p.kind, p.question, p.chaining.source, p.chaining.target) == (
        "chaining", entry.question, entry.truth.source, entry.truth.target)


# --- an engine run: names on, population items, a copied result -------------------------------------------------

PAPERS = {
    "p1": ("# Zelvora against Quintapride\n\nHalvorsen et al. (2019)\n\nWe enrolled adults with the condition.\n\n"
           "The response rate was 0.42 for Zelvora and 0.31 for Quintapride.\n"),
    "p2": ("# Quintapride against Morvectin\n\nBrennick et al. (2021)\n\nWe enrolled children with the condition.\n\n"
           "The response rate was 0.36 for Quintapride and 0.22 for Morvectin.\n"),
    "p3": ("# Zelvora again\n\nCastell et al. (2022)\n\nWe enrolled adults with the condition.\n\n"
           "The response rate was 0.42 for Zelvora. For Quintapride, the response rate is taken as reported by "
           "Halvorsen et al (2019): 0.31.\n"),
}
LABELS = {"p1": "Halvorsen et al. (2019)", "p2": "Brennick et al. (2021)", "p3": "Castell et al. (2022)"}
POPULATIONS = {"p1": "adults", "p2": "children", "p3": "adults"}
ARMS = {"p1": [("Zelvora", "0.42"), ("Quintapride", "0.31")], "p2": [("Quintapride", "0.36"), ("Morvectin", "0.22")],
        "p3": [("Zelvora", "0.42"), ("Quintapride", "0.31")]}
ARM_QUOTES = {("p3", "Quintapride"): "For Quintapride"}   # else "<value> for <arm>": a name alone is not unique
CITED = "Halvorsen et al (2019)"   # p3 cites p1 without the full stop: the names step groups it with p1's label


def chain_script(kind: str, doc: str, prompt: str) -> dict[str, Any]:
    """The careful reader of PAPERS: arms, population, byline, p3's dependency on p1's result, and each arm's value
    with its population; p3's Quintapride value links the dependency (a copied result)."""
    if kind == "arm":
        return {"items": [{"fields": {"label": arm, "role": "drug"}, "quotes": {"condition_label": ARM_QUOTES.get((doc, arm), f"{v} for {arm}")}}
                          for arm, v in ARMS[doc]]}
    if kind == "population":
        population = POPULATIONS[doc]
        return {"items": [{"fields": {"name": population},
                           "quotes": {"population_label": f"{population} with the condition"}}]}
    if kind == "study_label":
        return {"items": [{"fields": {"label": LABELS[doc]}, "quotes": {"label": LABELS[doc]}}]}
    if kind == "dependency" and doc == "p3":
        return {"items": [{"fields": {"cited": CITED, "reuses": "result"},
                           "quotes": {"citation": f"as reported by {CITED}"}}]}
    if kind == "result":
        rate = context_id(prompt, '"response_rate"')
        source = context_id(prompt, '"result"') if doc == "p3" else None

        def value(arm: str, number: str, linked: str | None) -> dict[str, Any]:
            return {"fields": {"value": float(number), "population": POPULATIONS[doc]},
                    "links": {"arm": context_id(prompt, f'"{arm}"'), "outcome": rate, "source": linked},
                    "quotes": {"value": number, "condition_label": None, "metric_label": None}}
        (a, av), (b, bv) = ARMS[doc]
        return {"items": [value(a, av, None), value(b, bv, source if doc == "p3" else None)]}
    return {"quotes": []} if kind == "retry" else {"items": []}


def chain_run(tmp_path: Path, names: str) -> Path:
    corpus = corpus_of(tmp_path / "corpus", PAPERS)
    return engine.run(CHAIN, corpus, tmp_path / f"runs-{names}", cache=tmp_path / "cache", model="scripted-alias",
                      provider=provider_of(scripted(chain_script, [])), strategy="all", confirm="none",
                      domains=FIXTURES, names=names)


def test_a_run_with_names_on_resolves_the_cited_label_and_refuses_across_populations(tmp_path):
    out = chain_run(tmp_path, "on")
    data = json.loads((out / "comparisons.json").read_text(encoding="utf-8"))
    counted = [(c["document"], c["a"], c["b"], c["context"]) for c in data["comparisons"]]
    assert counted == [("p1", "Quintapride", "Zelvora", "adults"), ("p2", "Morvectin", "Quintapride", "children")]
    # p3's copied value names p1 although p3 cites "Halvorsen et al (2019)": the names step joined it to p1's label
    assert [(c["document"], c["copied_from"], c["cited_text"]) for c in data["copied"]] == [("p3", "p1", CITED)]
    answer = json.loads((out / "answer.json").read_text(encoding="utf-8"))
    assert (answer["verdict"], answer["reason"], answer["inferred"], answer["via"], answer["studies"]) == (
        "refused", "context_differs", False, ["Quintapride"], ["p1", "p2"])
    assert [s["context"] for s in answer["paths"][0]["steps"]] == ["adults", "children"]


def test_the_same_run_with_names_off_does_not_resolve_the_cited_label(tmp_path):
    data = json.loads((chain_run(tmp_path, "off") / "comparisons.json").read_text(encoding="utf-8"))
    assert data["copied"] == []
    assert [(c["document"], c["copied_from"], c["cited_text"]) for c in data["comparisons"] if c["cited_text"]] == [
        ("p3", None, CITED)]


def test_a_chain_run_with_names_on_replays(tmp_path):
    _, report = replay(chain_run(tmp_path, "on"))
    assert report["ok"] and "added" not in report, report
