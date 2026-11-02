"""Kind `limitations` (plan 2 Task 10, spec section 6.18): the limitations papers state, grouped by thing and category,
every paper counted; the protocol category enum is the pack list."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from evidence import contract
from evidence.contract import Item, Span
from evidence.kinds import MODULES, limitations
from evidence.names import NameGroups
from evidence.pack import load_pack, register_pack
from evidence.protocol import load, parse

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
LIMITS = FIXTURES / "drugtoy" / "protocols" / "drugtoy-limits.yaml"


@pytest.fixture(autouse=True)
def _registry():
    """Each test leaves the type registry as it found it (the drugtoy pack registers its types)."""
    before = dict(contract.ITEM_PREFIX)
    register_pack(load_pack("drugtoy", root=FIXTURES))
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def protocol(thing: str | None = None):
    p = load(LIMITS, FIXTURES)
    assert p.limitations is not None
    return p.model_copy(update={"limitations": p.limitations.model_copy(update={"thing": thing})})


class Papers:
    """Hand-built items by document: an arm item per (document, name), a limitation item linking it (or none)."""

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

    def limitation(self, doc: str, thing: str | None, category: str) -> Item:
        links = {}
        if thing is not None:
            arm = next((i for i in self.items.get(doc, []) if i.evidence_type == "arm" and i.fields["label"] == thing),
                       None) or self.add(doc, "arm", {"label": thing, "role": "drug"}, "condition_label")
            links = {"thing": arm.item_id}
        return self.add(doc, "limitation", {"category": category}, "limitation", links)


def lims(*rows: tuple[str, str | None, str]) -> Papers:
    papers = Papers()
    for doc, thing, category in rows:
        papers.limitation(doc, thing, category)
    return papers


def answer(papers: Papers, thing: str | None = None, groups: NameGroups | None = None) -> dict[str, Any]:
    out, _ = limitations.answer(protocol(thing), list(papers.items), papers.items, groups=groups)
    return out


# --- the brief's tests ------------------------------------------------------------------------------------------

def test_limitations_grouped_by_thing_and_category():
    a = answer(lims(("p1", "Zelvora", "small_sample"), ("p2", "ZELVORA", "small_sample"),
                    ("p2", "Zelvora", "side_effects")))
    assert a["counts"]["Zelvora"] == {"small_sample": 2, "side_effects": 1}
    assert [(e["thing"], e["category"], e["papers"]) for e in a["entries"]] == [
        ("Zelvora", "small_sample", ["p1", "p2"]), ("Zelvora", "side_effects", ["p2"])]


def test_question_thing_filters_entries():
    a = answer(lims(("p1", "Zelvora", "cost"), ("p1", "Morvectin", "cost")), thing="Morvectin")
    assert [e["thing"] for e in a["entries"]] == ["Morvectin"]
    assert a["thing"] == "Morvectin"


def test_unknown_category_is_rejected_by_the_protocol():
    """The category enum of the protocol must be the pack list, so a category the pack does not know cannot reach the
    counts (and a category the pack has cannot be left out)."""
    text = LIMITS.read_text(encoding="utf-8")
    for bad in (text.replace("small_sample, side_effects, cost", "small_sample, side_effects, bad_luck"),
                text.replace("small_sample, side_effects, cost", "small_sample, side_effects")):
        with pytest.raises(ValueError, match="limitation_categories"):
            parse(bad, FIXTURES)
    assert parse(text, FIXTURES).kind == "limitations"


def test_a_limitation_type_without_a_category_enum_is_refused():
    text = LIMITS.read_text(encoding="utf-8").replace(", enum: [small_sample, side_effects, cost]", "")
    with pytest.raises(ValueError, match="limitation_categories"):
        parse(text, FIXTURES)


# --- beyond the brief -------------------------------------------------------------------------------------------

def test_kind_is_registered():
    assert MODULES["limitations"] is limitations


def test_a_name_group_joins_forms_and_names_the_thing():
    groups = NameGroups(groups={"Zelvora": ["Zelvora", "zel-vora"]}, matches=[], unresolved=[])
    a = answer(lims(("p1", "Zelvora", "cost"), ("p2", "zel-vora", "cost")), thing="zel-vora", groups=groups)
    assert [(e["thing"], e["papers"]) for e in a["entries"]] == [("Zelvora", ["p1", "p2"])]


def test_every_paper_counts_and_each_paper_once():
    a = answer(lims(("p1", "Zelvora", "cost"), ("p1", "Zelvora", "cost"), ("p2", "Zelvora", "cost")))
    (entry,) = a["entries"]
    assert entry["papers"] == ["p1", "p2"] and len(entry["items"]) == 3 and a["counts"] == {"Zelvora": {"cost": 2}}


def test_a_limitation_without_a_thing_is_kept_under_null_last():
    papers = lims(("p1", None, "cost"), ("p1", "Zelvora", "cost"))
    a = answer(papers)
    assert [e["thing"] for e in a["entries"]] == ["Zelvora", None]
    assert a["counts"] == {"Zelvora": {"cost": 1}, None: {"cost": 1}}
    assert [e["thing"] for e in answer(papers, thing="Zelvora")["entries"]] == ["Zelvora"]


def test_entries_follow_thing_then_the_pack_category_order():
    a = answer(lims(("p1", "Zelvora", "cost"), ("p1", "Morvectin", "side_effects"), ("p1", "Zelvora", "small_sample")))
    assert [(e["thing"], e["category"]) for e in a["entries"]] == [
        ("Morvectin", "side_effects"), ("Zelvora", "small_sample"), ("Zelvora", "cost")]


def test_used_items_are_the_limitations_listed():
    papers = lims(("p1", "Zelvora", "cost"), ("p1", "Morvectin", "cost"))
    out, used = limitations.answer(protocol("Zelvora"), ["p1"], papers.items)
    assert used == out["entries"][0]["items"]


def test_study_reasons_and_gap_types():
    p = protocol()
    assert limitations.study(p, "p1", [])[0]["reason"]["code"] == "no_limitation_items"
    assert limitations.gap_types(p, "no_limitation_items") == ("limitation",)
    assert limitations.gap_types(p, "unlinked") == () and limitations.gap_types(p, "screened_out") == ()
    entry, used = limitations.study(p, "p1", lims(("p1", None, "cost")).items["p1"])
    assert entry["reason"]["code"] == "unlinked" and used == entry["items"]
    assert limitations.study(p, "p1", lims(("p1", "Zelvora", "cost")).items["p1"])[0]["reason"] is None
    assert limitations.study(p, "p1", [], {"code": "screened_out", "text": "x"})[0]["reason"]["code"] == "screened_out"
