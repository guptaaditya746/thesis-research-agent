"""The facts, papers and settings a readable program is made of, read from a finished run's answer.

`effect_inputs` covers the effect and consistency kinds: every value, compared thing, measure and author claim the
answer rests on becomes a fact with a key (`F1`, `F2`, ... in order of first use), and each paper names the facts its
row was read from."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import synthesis
from ..contract import Item
from .runview import NOT_FOUND_AGAIN, NotRebuilt, RunAnswer

__all__ = ["ProgramInputs", "effect_inputs"]


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
