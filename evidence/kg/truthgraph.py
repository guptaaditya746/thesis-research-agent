"""The answer key as a graph (W4 task 4.4): every query also runs on the answer key's records, so an error can be placed.

`truth_store(truth)` builds the records of a ground truth (its conditions, metrics and measurements, with the spans of
their main placements) into the same graph as a system's records (`kg.build.build`), so the same SPARQL runs on both.
A `RealQuestion` (Task 6.1) carries its answer key in `gold`: `truth_store(question)` reads that.

`split(ours, gold_on_truth, expected)` places a wrong answer:
- "right": our answer is the expected one;
- "synthesis error": the query is wrong even on the answer key's records (the question, the template or its decisions);
- "extraction error": the query is right on the answer key's records but wrong on ours (a record is missing or wrong).

`matches(answer, expected)` says when an answer is the expected one: `expected` is a list of rows (dicts: every key given
must be equal, order ignored), a list of values (the first column of each row, in order), or one value; an empty
list or None is an empty answer ("No evidence found"). With `column`, a list of values is read from that column of each
row (each value once, in order) instead of the first."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pyoxigraph as ox

from evidence.contract import Item, Span
from evidence.pack import RoleMap, load_pack, register_pack
from evidence.protocol import DEFAULT_PACK

from .build import build
from .query import Answer

if TYPE_CHECKING:
    from rdflib import Graph

KINDS = ("condition", "metric", "measurement")   # built in this order: a measurement links to the first two
DOMAINS = Path(__file__).resolve().parents[2] / "domains"


def _fields(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    if kind == "condition":
        return {"label": data["label"], "role": data["role"]}
    if kind == "metric":
        return {"name": data["name"], "canonical": data["canonical"], "higher_is_better": data["higher_is_better"]}
    return {"value": data["value"], "dataset": data.get("dataset")}


def _spans(truth: Any, fact: Any, role: str) -> list[Span]:
    placed = [p for p in truth.placements_of(fact.id, role) if p.get("paper", fact.paper) == fact.paper]
    if not placed:
        placed = [{"start": 0, "end": 0}]
    return [Span(role=role, selector={"file": f"papers/{fact.paper}.md", "start": p["start"], "end": p["end"],
                                      "exact": "", "prefix": "", "suffix": "", "sha256": ""}) for p in placed]


def truth_items(truth: Any) -> dict[str, list[Item]]:
    """The answer key's records by paper, as items of the truth's pack (condition / metric / measurement)."""
    items: dict[str, list[Item]] = {}
    item_of: dict[str, str] = {}
    for kind in KINDS:
        for fact in (f for f in truth.facts.values() if f.type == kind):
            links = ({"condition": item_of[fact.data["condition"]], "metric": item_of[fact.data["metric"]]}
                     if kind == "measurement" else None)
            item = Item.build(kind, _fields(kind, fact.data), _spans(truth, fact, truth.main_role[kind]), links=links)
            items.setdefault(fact.paper, []).append(item)
            item_of[fact.id] = item.item_id
    return items


def truth_store(truth: Any, ontology: Graph | None = None, *, domains: Path = DOMAINS) -> ox.Store:
    """The answer key's records as a graph. `truth` is a GroundTruth, or a RealQuestion (its `gold`)."""
    from types import SimpleNamespace
    truth = getattr(truth, "gold", truth)
    if not hasattr(truth, "facts"):
        raise TypeError(f"no answer key to read in {type(truth).__name__}: expected a GroundTruth or a RealQuestion")
    pack = load_pack(getattr(truth, "domain", None) or DEFAULT_PACK, root=domains)
    register_pack(pack)
    items = truth_items(truth)
    papers = [SimpleNamespace(id=p, file=f"papers/{p}.md", sha256="", path=Path(p))
              for p in dict.fromkeys(s["paper"] for s in truth.studies)]
    return build(papers, items, RoleMap(pack), ontology)


def matches(answer: Answer, expected: Any, column: str | None = None) -> bool:
    rows = answer.rows
    if expected is None or expected == []:
        return answer.empty
    if not isinstance(expected, list):
        return len(rows) == 1 and next(iter(rows[0].values())) == expected
    if all(isinstance(e, dict) for e in expected):
        if len(rows) != len(expected):
            return False
        free = list(rows)
        for e in expected:
            hit = next((r for r in free if all(r.get(k) == v for k, v in e.items())), None)
            if hit is None:
                return False
            free.remove(hit)
        return True
    if column is not None:
        got = list(dict.fromkeys(r.get(column) for r in rows))   # once each, in order; an extra or misordered value still differs
        return got == expected
    return [next(iter(r.values())) for r in rows] == expected


def split(ours: Answer, gold_on_truth: Answer, expected: Any,
          column: str | None = None) -> Literal["right", "synthesis error", "extraction error"]:
    if matches(ours, expected, column):
        return "right"
    return "extraction error" if matches(gold_on_truth, expected, column) else "synthesis error"
