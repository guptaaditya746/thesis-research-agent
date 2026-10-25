"""Kind `best`: which method kind reaches the top value of `best.metric` inside each paper, and which kind wins
in the most papers?

A condition's kind is its `kind` field when that names one of `best.kinds`, else the kind whose names hold its
label (case-folded, whitespace collapsed); a condition of no kind is left out. The values compared are the
measurements on a metric item whose `canonical` is `best.metric.canonical`, of a condition with a kind. They are
chosen as `Pairing` chooses a pair (evidence/synthesis.py): the datasets are tried in the order they first appear
(by value position) and the first one with values of at least two kinds is used; only when none has, values that
name no dataset join a named dataset (synthesis._pair's fallback). Among several values of one kind there,
`best.pairing.prefer` decides (`synthesis.best_value`: a table cell first, then the earlier value). One value per
kind is compared.

Per document: the kind with the top value (the highest, or the lowest when `higher_is_better` is false) is the
`winner`; when several kinds share the top value there is no winner and `tied` lists them (sorted), and the paper
counts no win. Reasons: `too_few_kinds` (conditions of fewer than two kinds; the funnel escalates condition) and
`no_comparison` (no dataset has values of two kinds on the metric; escalates measurement); a tie is complete
(reason null). Answer: `{kind, system, metric, studies: [{document, winner, tied, values, reason}], wins, winner,
tied}`; `wins` counts the papers each kind won (kinds without a win are left out), `winner` is the kind with the
most wins, or null with `tied` listing the kinds that share the most wins.
"""
from __future__ import annotations

from typing import Any

from .. import synthesis
from ..contract import Item
from ..evidence_types import EvidenceType
from ..protocol import Best, Protocol

KIND = "best"
GAP_TYPES: dict[str, tuple[EvidenceType, ...]] = {"too_few_kinds": ("condition",), "no_comparison": ("measurement",),
                                                  "screened_out": ()}
REASONS = {"too_few_kinds": "conditions of fewer than two method kinds found",
           "no_comparison": "no dataset with values of two method kinds on {metric}"}


def spec(protocol: Protocol) -> Best:
    assert protocol.best is not None, "a best protocol has a best block"
    return protocol.best


def _fold(name: Any) -> str:
    return " ".join(str(name).split()).casefold()


def kind_of(condition: Item, best: Best) -> str | None:
    given = condition.fields.get("kind")
    if given in best.kinds:
        return str(given)
    label = _fold(condition.fields.get("label", ""))
    return next((k for k, names in best.kinds.items() if label in {_fold(n) for n in names}), None)


def reason(code: str, best: Best) -> dict[str, str]:
    return {"code": code, "text": REASONS[code].format(metric=best.metric.canonical)}


def study(protocol: Protocol, document: str, items: list[Item],
          preset: dict[str, str] | None = None) -> tuple[dict[str, Any], list[str]]:
    best = spec(protocol)
    entry: dict[str, Any] = {"document": document, "winner": None, "tied": [], "values": {}, "reason": None}
    if preset is not None:
        entry["reason"] = dict(preset)
        return entry, []
    kinds = {i.item_id: k for i in items if i.evidence_type == "condition" and (k := kind_of(i, best)) is not None}
    if len(set(kinds.values())) < 2:
        entry["reason"] = reason("too_few_kinds", best)
        return entry, []
    metrics = {i.item_id for i in items if i.evidence_type == "metric" and i.fields.get("canonical") == best.metric.canonical}
    on = [m for m in items if m.evidence_type == "measurement" and m.links.get("metric") in metrics
          and m.links.get("condition") in kinds]
    chosen: dict[str, Item] = {}
    order: list[Any] = []
    for m in sorted(on, key=lambda m: (synthesis.value_start(m), m.item_id)):
        if m.fields.get("dataset") not in order:
            order.append(m.fields.get("dataset"))
    def of(allowed: tuple[Any, ...]) -> dict[str, list[Item]]:
        by_kind: dict[str, list[Item]] = {}
        for m in on:
            if m.fields.get("dataset") in allowed:
                by_kind.setdefault(kinds[m.links["condition"]], []).append(m)
        return by_kind

    groups = None
    for dataset in order:   # the same dataset for every kind, first dataset in document order
        if len(by_kind := of((dataset,))) >= 2:
            groups = by_kind
            break
    if groups is None:      # fallback, as synthesis._pair: values that name no dataset join a named one
        for dataset in order:
            by_kind = of((dataset, None))
            if len(by_kind) >= 2 and (dataset is None or any(m.fields.get("dataset") is None
                                                             for ms in by_kind.values() for m in ms)):
                groups = by_kind
                break
    if groups is not None:
        chosen = {k: synthesis.best_value(ms, best.pairing.prefer) for k, ms in groups.items()}
    if not chosen:
        entry["reason"] = reason("no_comparison", best)
        return entry, []
    values = {k: float(chosen[k].fields["value"]) for k in best.kinds if k in chosen}
    top = (max if best.metric.higher_is_better else min)(values.values())
    leaders = sorted(k for k, v in values.items() if v == top)
    entry.update(values=values, winner=leaders[0] if len(leaders) == 1 else None,
                 tied=leaders if len(leaders) > 1 else [])
    used = [x for k in values for x in (chosen[k].item_id, chosen[k].links["condition"], chosen[k].links["metric"])]
    return entry, list(dict.fromkeys(used))


def gap_types(protocol: Protocol, code: str) -> tuple[EvidenceType, ...]:
    return GAP_TYPES.get(code, ())


def answer(protocol: Protocol, documents: list[str], items: dict[str, list[Item]],
           reasons: dict[str, dict[str, str]] | None = None,
           funnel: dict[str, dict[str, Any]] | None = None) -> tuple[dict[str, Any], list[str]]:
    best = spec(protocol)
    studies, used = [], []
    for doc in documents:
        entry, ids = study(protocol, doc, items.get(doc, []), (reasons or {}).get(doc))
        studies.append(entry)
        used += ids
    out = {"kind": KIND, "system": synthesis.SYSTEM, "metric": best.metric.canonical, "studies": studies,
           **tally([s["winner"] for s in studies], best.kinds)}
    return out, used


def tally(winners: list[str | None], kinds: Any) -> dict[str, Any]:
    """`{wins, winner, tied}` from the per-paper winners (None: no win): `wins` counts each kind's wins in the
    order of `kinds`, leaving out kinds without a win; `winner` is the kind with the most wins, or None with `tied`
    listing (sorted) the kinds that share the most wins. Shared by the engine and the baselines."""
    wins: dict[str, int] = {}
    for k in kinds:                           # in the protocol's kind order
        n = sum(1 for w in winners if w == k)
        if n:
            wins[k] = n
    most = max(wins.values(), default=0)
    leaders = sorted(k for k, n in wins.items() if n == most) if most else []
    return {"wins": wins, "winner": leaders[0] if len(leaders) == 1 else None,
            "tied": leaders if len(leaders) > 1 else []}


def extractor_config(protocol: Protocol) -> dict[str, Any]:
    best = spec(protocol)
    return {"question_metrics": [best.metric.canonical],
            "kinds": {k: list(names) for k, names in best.kinds.items()}}
