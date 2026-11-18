"""The facts, papers and settings a readable program is made of, read from a finished run's answer.

`effect_inputs` covers the effect and consistency kinds: every value, compared thing, measure and author claim the
answer rests on becomes a fact with a key (`F1`, `F2`, ... in order of first use), and each paper names the facts its
row was read from."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import synthesis
from ..contract import Item
from ..kinds import best as best_kind, inventory as inventory_kind
from .runview import KIND_NOT_REBUILT, NOT_FOUND_AGAIN, NotRebuilt, RunAnswer, read_run
from .rules.common import BEST_REASON_TEMPLATES

__all__ = ["ProgramInputs", "best_inputs", "effect_inputs", "inputs_of", "inventory_inputs", "refusal"]


@dataclass
class ProgramInputs:
    """What a program holds: `settings` (RULE_SETTINGS), `facts` (FACTS_USED), `papers` (PAPERS), `model_text`
    (MODEL_TEXT), `names` (NAMES_OF_THINGS) and, for the comments only, the exact text each fact quotes (`spans`)."""
    kind: str
    question: str
    settings: dict[str, Any]
    facts: dict[str, dict[str, Any]]
    papers: list[dict[str, Any]]
    model_text: list[Any] = field(default_factory=list)
    names: dict[str, str] = field(default_factory=dict)
    spans: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


class FactTable:
    """The facts of one run, keyed in order of first use; a fact is made from an item once, whoever asks for it."""

    def __init__(self, ra: RunAnswer, types: synthesis.Types) -> None:
        self.ra = ra
        self.types = types
        self.keys: dict[str, str] = {}
        self.facts: dict[str, dict[str, Any]] = {}
        self.spans: dict[str, list[dict[str, Any]]] = {}

    def _name_field(self, etype: str | None) -> str | None:
        return self.ra.roles.field_or_none(etype, "name") if etype is not None else None

    def key_of(self, paper: str, item_id: str) -> str:
        """The key of the item's fact, made when the item is first asked for."""
        if item_id in self.keys:
            return self.keys[item_id]
        by_id = {i.item_id: i for i in self.ra.items.get(paper, [])}
        if item_id not in by_id:
            raise NotRebuilt(NOT_FOUND_AGAIN.format(what="item", paper=paper))
        key = f"F{len(self.keys) + 1}"
        self.keys[item_id] = key
        item = by_id[item_id]
        self.facts[key] = self._fact(paper, item)
        self.spans[key] = [{"paper": paper, "role": s.role, "start": s.selector.get("start"),
                            "exact": s.selector.get("exact", "")} for s in item.spans]
        return key

    def _fact(self, paper: str, item: Item) -> dict[str, Any]:
        ty, fields = self.types, item.fields
        base: dict[str, Any] = {"paper": paper, "item": item.item_id}
        if item.evidence_type == ty.value:
            thing = self.key_of(paper, item.links[ty.to_thing or ""])
            measure = self.key_of(paper, item.links[ty.to_metric or ""])
            return {**base, "type": "measured value", "value": fields["value"], "dataset": fields.get(ty.context),
                    "thing": thing, "measure": measure}
        if item.evidence_type == ty.thing:
            return {**base, "type": "compared thing", "label": fields.get(self._name_field(ty.thing) or ""),
                    "side": fields.get(ty.side or "")}
        if item.evidence_type == ty.metric:
            return {**base, "type": "measure", "name": fields.get(self._name_field(ty.metric) or ""),
                    "canonical": fields.get(ty.canonical or "")}
        return {**base, "type": "author claim", "direction": fields.get(ty.direction or "")}

    def ordered(self) -> dict[str, dict[str, Any]]:
        return dict(sorted(self.facts.items(), key=lambda pair: int(pair[0][1:])))


def _settings(ra: RunAnswer) -> dict[str, Any]:
    spec = ra.protocol.synthesis
    assert spec is not None, "an effect or consistency protocol has a synthesis block"
    return {"kind": ra.kind, "treatment": spec.compare.treatment, "control": spec.compare.control,
            "metrics": [{"canonical": m.canonical, "higher_is_better": m.higher_is_better} for m in spec.metrics],
            "measure": spec.metrics[0].canonical, "smallest_real_difference": spec.min_effect,
            "claim_map": dict(spec.claim_map), "label_rows": spec.table,
            "flags": {"duplicates": spec.flags.duplicates,
                      "large_effect": {"factor": spec.flags.large_effect.factor,
                                       "min_studies": spec.flags.large_effect.min_studies}}}


def _first_claim(table: FactTable, paper: str) -> str | None:
    claims = table.types.of_type(table.ra.items.get(paper, []), table.types.claim)
    return table.key_of(paper, claims[0].item_id) if claims else None


def _paper(table: FactTable, entry: dict[str, Any], claim_known: bool) -> dict[str, Any]:
    """One paper's record from its study entry (the effect answer's own, or consistency's re-made one); `claim_known`
    is False when the recorded answer names no author claim for the paper."""
    ra, paper = table.ra, entry["document"]
    if entry["direction"] == "undetermined":
        claim = _first_claim(table, paper) if claim_known else None
        return {"paper": paper, "could_not_be_read": entry["reason"], "claim": claim}
    treatment = table.key_of(paper, entry["treatment"][synthesis.SIDE_VALUE])
    control = table.key_of(paper, entry["control"][synthesis.SIDE_VALUE])
    claim = _first_claim(table, paper) if claim_known else None
    return {"paper": paper, "measure": entry["metric"], "treatment_value": treatment, "control_value": control,
            "claim": claim, "experiment_setting": synthesis.experiment_key(entry, ra.items.get(paper, []))}


def effect_inputs(ra: RunAnswer) -> ProgramInputs:
    """The inputs of an effect or consistency run (`ra.kind`)."""
    types = synthesis.Types.of(ra.protocol, ra.roles)
    table = FactTable(ra, types)
    papers = []
    for recorded in ra.answer.get("studies", []):
        paper = recorded["document"]
        if ra.kind == "effect":
            entry = recorded
            claim_known = recorded.get("author_claim") is not None
        else:
            claim_known = recorded.get("claim") is not None
            entry = dict(recorded)
            if recorded["direction"] != "undetermined":
                entry, _ = synthesis.study(ra.protocol, paper, ra.items.get(paper, []), None, roles=ra.roles,
                                           inferred=ra.inferred)
                if entry["direction"] != recorded["direction"]:
                    raise NotRebuilt(NOT_FOUND_AGAIN.format(what="pair", paper=paper))
        papers.append(_paper(table, entry, claim_known))
    return ProgramInputs(kind=ra.kind, question=ra.protocol.question, settings=_settings(ra), facts=table.ordered(),
                         papers=papers, model_text=[], names=dict(ra.names), spans=table.spans)


class _BestFacts(FactTable):
    """The facts of a best run: a compared thing carries its label and kind value, no side."""

    def _fact(self, paper: str, item: Item) -> dict[str, Any]:
        ty = self.types
        if item.evidence_type != ty.thing:
            return super()._fact(paper, item)
        kind_field = self.ra.roles.field_or_none(ty.thing, "kind")
        return {"paper": paper, "item": item.item_id, "type": "compared thing",
                "label": item.fields.get(self._name_field(ty.thing) or ""),
                "kind": item.fields.get(kind_field) if kind_field is not None else None}


def _best_settings(ra: RunAnswer) -> dict[str, Any]:
    spec = best_kind.spec(ra.protocol)
    return {"kind": "best", "measure": spec.metric.canonical, "higher_is_better": spec.metric.higher_is_better,
            "kinds": {k: list(names) for k, names in spec.kinds.items()}}


def best_inputs(ra: RunAnswer) -> ProgramInputs:
    """The inputs of a best run: for each paper the measured values the engine compared, or why it compared none."""
    types = synthesis.Types.of(ra.protocol, ra.roles)
    table = _BestFacts(ra, types)
    papers: list[dict[str, Any]] = []
    for recorded in ra.answer.get("studies", []):
        paper = recorded["document"]
        reason = recorded.get("reason")
        if reason is not None and reason.get("code") not in BEST_REASON_TEMPLATES:
            papers.append({"paper": paper, "no_comparison": reason})   # a paper the funnel set aside
            continue
        items = ra.items.get(paper, [])
        entry, used = best_kind.study(ra.protocol, paper, items, None, roles=ra.roles, inferred=ra.inferred)
        if any(entry[name] != recorded.get(name) for name in ("values", "winner", "tied", "reason")):
            raise NotRebuilt(NOT_FOUND_AGAIN.format(what="values", paper=paper))
        if entry["reason"] is not None:
            papers.append({"paper": paper, "no_comparison": entry["reason"]})
            continue
        by_id = {i.item_id: i for i in items}
        papers.append({"paper": paper, "values": [table.key_of(paper, i) for i in used
                                                  if by_id[i].evidence_type == types.value]})
    return ProgramInputs(kind="best", question=ra.protocol.question, settings=_best_settings(ra),
                         facts=table.ordered(), papers=papers, model_text=[], names=dict(ra.names),
                         spans=table.spans)


class _InventoryFacts(FactTable):
    """The facts of an inventory run: one name per target item."""

    def __init__(self, ra: RunAnswer, target: str, name_field: str) -> None:
        super().__init__(ra, None)   # type: ignore[arg-type]  (no value or thing types are read)
        self.target, self.field = target, name_field

    def _fact(self, paper: str, item: Item) -> dict[str, Any]:
        return {"paper": paper, "item": item.item_id, "type": self.target,
                "name": inventory_kind.name_of(item, self.field)}


def inventory_inputs(ra: RunAnswer) -> ProgramInputs:
    """The inputs of an inventory run: for each paper an entry names, the names of its target items in item order."""
    spec = inventory_kind.spec(ra.protocol)
    name_field = inventory_kind.name_field(ra.protocol, ra.roles)
    table = _InventoryFacts(ra, spec.target, name_field)
    named = {p for entry in ra.answer.get("entries", []) for p in entry.get("papers", [])}
    if not named <= set(ra.items):
        raise NotRebuilt(NOT_FOUND_AGAIN.format(what="items", paper=sorted(named - set(ra.items))[0]))
    papers = []
    for paper in ra.items:   # manifest order
        if paper not in named:
            continue
        keys = [table.key_of(paper, i.item_id) for i in ra.items[paper]
                if i.evidence_type == spec.target and inventory_kind.name_of(i, name_field) is not None]
        papers.append({"paper": paper, "names": keys})
    return ProgramInputs(kind="inventory", question=ra.protocol.question,
                         settings={"kind": "inventory", "target": spec.target,
                                   "same": {n: list(o) for n, o in spec.same.items()}},
                         facts=table.ordered(), papers=papers, model_text=[], names=dict(ra.names),
                         spans=table.spans)


_INPUTS = {"effect": "effect_inputs", "consistency": "effect_inputs", "best": "best_inputs",
           "inventory": "inventory_inputs", "written": "written_inputs"}


def inputs_of(ra: RunAnswer) -> ProgramInputs:
    """The inputs of the run's kind; the kind's function is looked up when called."""
    build = globals().get(_INPUTS.get(ra.kind, ""))
    if build is None:
        raise NotRebuilt(KIND_NOT_REBUILT.format(kind=ra.kind))
    return build(ra)   # type: ignore[no-any-return]


NOT_READ = "the run could not be read: {problem}"


def refusal(run: Path | str, corpus: Path | str | None = None) -> str | None:
    """Why a readable program cannot be made for the run, None when it can. It never raises: a run that cannot be
    read or rebuilt, for any reason, is a refusal text."""
    try:
        inputs_of(read_run(run, corpus, texts=False))
    except NotRebuilt as exc:
        return str(exc)
    except json.JSONDecodeError as exc:
        return NOT_READ.format(problem=f"a file is not valid JSON ({exc})")
    except ValueError as exc:
        return NOT_READ.format(problem=str(exc))
    except AssertionError as exc:
        return NOT_READ.format(problem=str(exc) or "the protocol misses a part the rules need")
    except Exception as exc:   # a refusal text, never a crash on a page or a download
        return NOT_READ.format(problem=f"{type(exc).__name__}: {exc}")
    return None
