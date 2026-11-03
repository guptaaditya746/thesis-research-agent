"""Hand-built records for the graph tests: papers of the drugtoy pack (arm / outcome / result) plus experiment items."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from evidence import contract
from evidence.contract import Item, Span
from evidence.pack import RoleMap, load_pack, register_pack
from evidence.records import ClaimRecord, Experiment, LinkRecord, item

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROLES = RoleMap(load_pack("drugtoy", root=FIXTURES))


def register() -> dict[str, str]:
    before = dict(contract.ITEM_PREFIX)
    register_pack(load_pack("drugtoy", root=FIXTURES))
    return before


def restore(before: dict[str, str]) -> None:
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def paper(pid: str) -> SimpleNamespace:
    return SimpleNamespace(id=pid, file=f"papers/{pid}.md", sha256="0" * 64, path=Path(pid))


def span(doc: str, at: int, role: str = "value") -> Span:
    return Span(role=role, selector={"file": f"papers/{doc}.md", "start": at, "end": at + 4, "exact": "x",
                                     "prefix": "", "suffix": "", "sha256": "x"})


class Doc:
    """One paper's items; each item sits at the next position."""

    def __init__(self, pid: str) -> None:
        self.id, self.at, self.items = pid, 0, []
        self.arms: dict[tuple[str, str], Item] = {}
        self.metrics: dict[tuple[str, bool], Item] = {}

    def _add(self, etype: str, fields: dict[str, Any], role: str, links: dict[str, str] | None = None) -> Item:
        self.at += 10
        it = Item.build(etype, fields, [span(self.id, self.at, role)], links=links)
        self.items.append(it)
        return it

    def value(self, thing: str, number: float, *, metric: str = "acc", higher: bool = True,
              population: str | None = "adults", side: str = "drug") -> Item:
        arm = self.arms.get((thing, side)) or self._add("arm", {"label": thing, "role": side}, "condition_label")
        self.arms[(thing, side)] = arm
        m = self.metrics.get((metric, higher)) or self._add(
            "outcome", {"name": metric, "canonical": metric, "higher_is_better": higher}, "metric_label")
        self.metrics[(metric, higher)] = m
        return self._add("result", {"value": number, "population": population}, "value",
                         {"arm": arm.item_id, "outcome": m.item_id})

    def experiment(self, exp_id: str, setting: dict[str, str]) -> Item:
        it = item(Experiment(exp_id=exp_id, document=self.id, label=exp_id, setting=setting,
                             span=span(self.id, self.at + 1, "experiment")))
        self.at += 10
        self.items.append(it)
        return it

    def claim(self, subject: str, relation: str, **kw: Any) -> Item:
        rec = ClaimRecord(subject=subject, relation=relation, object=kw.get("object"), setting=kw.get("setting", {}),
                          strength=kw.get("strength", "firm"), direction=kw.get("direction"),
                          relation_group=kw.get("relation_group"), span=span(self.id, self.at + 1, "claim"))
        self.at += 10
        it = item(rec)
        self.items.append(it)
        return it

    def limitation(self, thing: str | None, category: str) -> Item:
        links = {"thing": self.arms[(thing, "drug")].item_id} if thing else None
        return self._add("limitation", {"category": category}, "limitation", links)

    def link(self, relation: str, ref: str, object_doc: str | None = None) -> Item:
        it = item(LinkRecord(subject_doc=self.id, relation=relation, object_ref=ref, object_doc=object_doc,
                             outside_set=object_doc is None, span=span(self.id, self.at + 1, "link")))
        self.at += 10
        self.items.append(it)
        return it
