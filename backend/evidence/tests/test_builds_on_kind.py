"""Kind `builds_on` (plan 2 Task 11, spec section 6.18): links from a citing study to the cited one (the cited label
resolved by `comparisons.resolve_cited`), the origin of each thing, its direct and indirect followers and influence;
a citation that resolves to no document of the run is reported, never dropped and never a link."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import jsonio
from evidence import contract
from evidence.contract import Item, Span
from evidence.kinds import MODULES, builds_on
from evidence.names import NameGroups
from evidence.pack import load_pack, register_pack
from evidence.protocol import load

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
BUILDS_ON = FIXTURES / "drugtoy" / "protocols" / "drugtoy-builds-on.yaml"


@pytest.fixture(autouse=True)
def _registry():
    """Each test leaves the type registry as it found it (the drugtoy pack registers its types)."""
    before = dict(contract.ITEM_PREFIX)
    register_pack(load_pack("drugtoy", root=FIXTURES))
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def protocol(thing: str | None = None):
    p = load(BUILDS_ON, FIXTURES)
    assert p.builds_on is not None
    return p.model_copy(update={"builds_on": p.builds_on.model_copy(update={"thing": thing})})


class Papers:
    """Hand-built items by document: a study label per document (the document's name unless set), arm items, and
    dependency items that cite a label and may link an arm of their document."""

    def __init__(self) -> None:
        self.items: dict[str, list[Item]] = {}
        self.at = 0

    def add(self, doc: str, etype: str, fields: dict[str, Any], role: str, links: dict[str, str] | None = None) -> Item:
        self.at += 10
        span = Span(role=role, selector={"file": f"papers/{doc}.md", "start": self.at, "end": self.at + 4,
                                         "exact": "text", "prefix": "", "suffix": "", "sha256": "0"})
        item = Item.build(etype, fields, [span], links=links)
        self.items.setdefault(doc, []).append(item)
        return item

    def label(self, doc: str, label: str | None = None) -> None:
        if not any(i.evidence_type == "study_label" for i in self.items.get(doc, [])):
            self.add(doc, "study_label", {"label": label or doc}, "label")

    def arm(self, doc: str, name: str) -> Item:
        self.label(doc)
        found = next((i for i in self.items[doc] if i.evidence_type == "arm" and i.fields["label"] == name), None)
        return found or self.add(doc, "arm", {"label": name, "role": "drug"}, "condition_label")

    def dep(self, doc: str, cited: str, reuses: str, thing: str | None = None) -> Item:
        self.label(doc)
        links = {"thing": self.arm(doc, thing).item_id} if thing is not None else None
        return self.add(doc, "dependency", {"cited": cited, "reuses": reuses}, "citation", links)


def deps(*rows: tuple[str, ...]) -> Papers:
    """Dependencies (citing document, cited label, reuses[, thing])."""
    papers = Papers()
    for doc, cited, reuses, *thing in rows:
        papers.dep(doc, cited, reuses, *thing)
    return papers


def answer(papers: Papers, origins: dict[str, str] | None = None, thing: str | None = None,
           groups: NameGroups | None = None, documents: list[str] | None = None) -> dict[str, Any]:
    for name, doc in (origins or {}).items():
        papers.arm(doc, name)
    docs = documents if documents is not None else sorted(papers.items)
    out, _ = builds_on.answer(protocol(thing), docs, papers.items, groups=groups)
    return out


# --- the brief's tests ------------------------------------------------------------------------------------------

def test_direct_and_indirect_followers():
    a = answer(deps(("p2", "p1", "method"), ("p3", "p2", "method")), origins={"Zelvora": "p1"})
    assert a["followers"]["Zelvora"] == ["p2", "p3"] and a["influence"]["Zelvora"] == 2


def test_cycle_terminates():
    a = answer(deps(("p2", "p1", "method"), ("p1", "p2", "dataset")), origins={"Zelvora": "p1"})
    assert a["influence"]["Zelvora"] == 1


def test_unknown_citation_is_reported_not_dropped():
    assert answer(deps(("p2", "Nobody et al. (2017)", "result")))["unresolved"] == ["Nobody et al. (2017)"]


# --- beyond the brief -------------------------------------------------------------------------------------------

def test_kind_is_registered():
    assert MODULES["builds_on"] is builds_on


def test_an_unresolved_citation_is_not_a_link():
    a = answer(deps(("p2", "Nobody et al. (2017)", "result"), ("p3", "Nobody et al. (2017)", "method"),
                    ("p3", "p2", "dataset")))
    assert a["unresolved"] == ["Nobody et al. (2017)"]   # each cited text once
    assert [(link["from"], link["to"], link["reuses"]) for link in a["links"]] == [("p3", "p2", "dataset")]


def test_links_join_the_dependencies_of_one_kind_between_two_documents():
    papers = deps(("p2", "p1", "method"), ("p2", "p1", "method"), ("p2", "p1", "result"))
    papers.label("p1")
    a = answer(papers)
    assert [(link["from"], link["to"], link["reuses"], len(link["items"])) for link in a["links"]] == [
        ("p2", "p1", "method", 2), ("p2", "p1", "result", 1)]


def test_the_origin_is_the_earliest_label_year_not_the_manifest_order():
    papers = Papers()
    papers.label("late", "Ames et al. (2021)")
    papers.label("early", "Bray et al. 2014, revised (2016)")   # the year is the last 4-digit run
    papers.dep("third", "Bray et al. 2014, revised (2016)", "method", "Zelvora")
    papers.arm("late", "Zelvora")
    papers.arm("early", "Zelvora")
    a = answer(papers, documents=["late", "early", "third"])
    assert a["origins"]["Zelvora"] == "early" and a["followers"]["Zelvora"] == ["third"]


def test_label_year_ties_go_to_the_manifest_order():
    papers = Papers()
    papers.label("b", "Bray (2016)")
    papers.label("a", "Ames (2016)")
    papers.label("n", "Nash, no year")   # a label without a year comes after every dated one
    for doc in ("n", "b", "a"):
        papers.arm(doc, "Zelvora")
    assert answer(papers, documents=["n", "b", "a"])["origins"]["Zelvora"] == "b"
    assert answer(papers, documents=["n", "a", "b"])["origins"]["Zelvora"] == "a"


def test_a_document_with_a_dependency_for_the_thing_is_not_its_origin():
    papers = deps(("p1", "p2", "method", "Zelvora"))   # p1 takes Zelvora from p2, though p1 is first
    a = answer(papers, origins={"Zelvora": "p2"})
    assert a["origins"]["Zelvora"] == "p2" and a["followers"]["Zelvora"] == ["p1"]


def test_a_thing_whose_origin_is_outside_the_run_has_no_followers():
    a = answer(deps(("p2", "Nobody et al. (2017)", "method", "Zelvora"), ("p3", "p2", "method", "Zelvora")))
    assert a["origins"]["Zelvora"] is None and a["followers"]["Zelvora"] == [] and a["influence"]["Zelvora"] == 0
    assert a["unresolved"] == ["Nobody et al. (2017)"]


def test_ranking_by_influence_then_name():
    papers = deps(("p2", "p1", "method"), ("p3", "p1", "dataset"), ("p5", "p4", "method"))
    a = answer(papers, origins={"Zelvora": "p1", "Morvectin": "p4", "Aldrex": "p6"})
    assert a["influence"] == {"Zelvora": 2, "Morvectin": 1, "Aldrex": 0}
    assert a["ranking"] == ["Zelvora", "Morvectin", "Aldrex"]
    papers.dep("p6", "p4", "method")
    assert answer(papers)["ranking"] == ["Morvectin", "Zelvora", "Aldrex"]


def test_question_thing_keeps_one_thing():
    a = answer(deps(("p2", "p1", "method")), origins={"Zelvora": "p1", "Morvectin": "p3"}, thing="Zelvora")
    assert a["thing"] == "Zelvora" and list(a["followers"]) == ["Zelvora"] and a["ranking"] == ["Zelvora"]


def test_name_groups_resolve_a_cited_form_and_join_thing_names():
    groups = NameGroups(groups={"Halvorsen et al. (2019)": ["Halvorsen et al. (2019)", "Halvorsen et al., 2019"],
                                "Zelvora": ["Zelvora", "ZV-217"]}, matches=[], unresolved=[])
    papers = Papers()
    papers.label("origin", "Halvorsen et al. (2019)")
    papers.arm("origin", "ZV-217")
    papers.dep("later", "Halvorsen et al., 2019", "method", "Zelvora")
    a = answer(papers, groups=groups, documents=["origin", "later"])
    assert a["unresolved"] == [] and a["links"][0]["to"] == "origin"
    assert a["followers"] == {"Zelvora": ["later"]}


def test_the_answer_is_json_safe():
    a = answer(deps(("p2", "p1", "method"), ("p3", "Nobody (2017)", "result")), origins={"Zelvora": "p1"})
    assert json.loads(jsonio.canonical(a)) == a


def test_used_items_are_the_link_dependencies():
    papers = deps(("p2", "p1", "method"), ("p3", "Nobody (2017)", "result"))
    papers.label("p1")
    out, used = builds_on.answer(protocol(), sorted(papers.items), papers.items)
    assert used == [i for link in out["links"] for i in link["items"]] and len(used) == 1


def test_study_reasons_and_gap_types():
    p = protocol()
    assert builds_on.study(p, "p1", [])[0]["reason"]["code"] == "no_study_label"
    assert builds_on.gap_types(p, "no_study_label") == ("study_label",)
    assert builds_on.gap_types(p, "no_dependency_items") == ("dependency",)
    assert builds_on.gap_types(p, "screened_out") == ()
    labelled = Papers()
    labelled.label("p1")
    assert builds_on.study(p, "p1", labelled.items["p1"])[0]["reason"]["code"] == "no_dependency_items"
    entry, used = builds_on.study(p, "p2", deps(("p2", "p1", "method")).items["p2"])
    assert entry["reason"] is None and used == entry["items"] and len(used) == 2
    assert builds_on.study(p, "p1", [], {"code": "screened_out", "text": "x"})[0]["reason"]["code"] == "screened_out"
