"""A fixed kind's answer (effect, consistency, inventory, best) as short lines in plain words.

A plan run keeps the kind's structured answer under answer.json `synthesis`. `kind_lines` turns it into lines a judge
and a person read: summary lines first, then one line per study or entry. The lines hold paper ids, names and numbers,
never the word `system`, the protocol id or the question. Task 8 joins them with a newline as the answer text."""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from .plan import Plan
from .protocol import Protocol

__all__ = ["CANT_TELL_LINE", "MAX_KIND_LINES", "RULE_TEXT", "KindLine", "kind_lines", "plan_names"]

MAX_KIND_LINES = 120
CANT_TELL_LINE = "The papers in this folder cannot answer this question."
ITEM_ID = re.compile(r"^[a-z]+-[0-9a-f]{16}$")

RULE_TEXT: dict[str, str] = {
    "effect": "Each paper's treatment and control values give a direction; the label table turns the counts into the answer.",
    "consistency": "Each paper's measured direction is compared with what its authors claim.",
    "inventory": "Every distinct name of the chosen kind is listed with the papers that name it.",
    "best": "Inside each paper the kind with the best value wins; the kind with the most wins is the answer.",
    "written": "A model (orch-model) wrote the answer from the pulled facts; code checked that every sentence cites "
               "listed facts and copies its numbers from them.",
    "lines": "The plan's main rule: {rule}.",
}

# a study's direction -> the plain words (the effect and consistency answers share the four directions)
SAYS = {"supports": "better", "contradicts": "worse", "neutral": "no real difference"}
LABEL_TEXT = {"supported": "{t} does better.", "refuted": "{t} does worse.", "no_effect": "no real difference.",
              "mixed": "the papers disagree."}
# (answer key, words after "Papers that")
GROUPS = (("supporting", "show it better"), ("contradicting", "show it worse"), ("neutral", "show no real difference"),
          ("undetermined", "could not be read"), ("duplicates", "repeat an earlier paper"))
INVENTORY_TARGETS = {"condition": "compared things", "metric": "measures"}


class KindLine(BaseModel):
    text: str
    items: list[str] = []
    study: bool = False


def plan_names(plan: Plan) -> dict[str, str]:
    """Each thing id -> its first word-list name (the id when the list is empty)."""
    return {t: (words[0] if words else t) for t, words in plan.words.things.items()}


def item_ids(entry: Any) -> list[str]:
    """Every string of `entry` (walked through its dicts and lists) that is an item id, once each, in order."""
    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            if ITEM_ID.match(value) and value not in found:
                found.append(value)
        elif isinstance(value, Mapping):
            for v in value.values():
                walk(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                walk(v)

    walk(entry)
    return found


def _num(value: Any) -> str:
    return f"{value:.10g}"


def _join(words: list[str]) -> str:
    return ", ".join(words)


def _reason(reason: Mapping[str, Any] | None) -> str:
    """The reason's text; a reason with no text is written as a fixed phrase, never its code."""
    return str((reason or {}).get("text") or "no reason given")


def _study(text: str, entry: Any) -> KindLine:
    return KindLine(text=text, items=item_ids(entry), study=True)


def _summary(text: str) -> KindLine:
    return KindLine(text=text)


def _effect(protocol: Protocol, answer: dict[str, Any], names: Mapping[str, str]) -> tuple[list[KindLine], list[KindLine]]:
    assert protocol.synthesis is not None
    name = lambda i: names.get(i, i)   # noqa: E731
    treatment, control = (name(r) for r in (protocol.synthesis.compare.treatment, protocol.synthesis.compare.control))
    label = answer.get("label")
    if label == "insufficient":
        head = [_summary(CANT_TELL_LINE)]
    else:
        said = LABEL_TEXT.get(label, f"{label}.".replace("_", " ")).format(t=treatment)
        measures = _join([name(m.canonical) for m in protocol.synthesis.metrics])
        head = [_summary(f"{treatment} against {control} on {measures}: {said}")]
    for key, words in GROUPS:
        if answer.get(key):
            head.append(_summary(f"Papers that {words}: {_join(answer[key])}."))
    body: list[KindLine] = []
    for s in answer.get("studies", []):
        if s["direction"] in SAYS:
            t, c = s.get("treatment") or {}, s.get("control") or {}
            values = f" ({_num(t['value'])} against {_num(c['value'])})" if t.get("value") is not None and c.get("value") is not None else ""
            text = f"{s['document']}: {SAYS[s['direction']]} on {name(s.get('metric') or '')}{values}."
        else:
            text = f"{s['document']}: could not be read ({_reason(s.get('reason'))})."
        body.append(_study(text, s))
    return head, body


def _consistency(protocol: Protocol, answer: dict[str, Any], names: Mapping[str, str]) -> tuple[list[KindLine], list[KindLine]]:
    metric = answer.get("metric") or (protocol.synthesis.metrics[0].canonical if protocol.synthesis else "")
    agree, disagree = answer.get("agreeing", []), answer.get("disagreeing", [])
    unknown = answer.get("undetermined", [])
    if not agree and not disagree:
        head = [_summary(CANT_TELL_LINE)]
    else:
        parts = ([f"agree with their numbers in {_join(agree)}"] if agree else []) \
            + ([f"disagree in {_join(disagree)}"] if disagree else []) \
            + ([f"cannot be checked in {_join(unknown)}"] if unknown else [])
        head = [_summary(f"On {names.get(metric, metric)}, the authors' claims {'; '.join(parts)}.")]
    body: list[KindLine] = []
    for s in answer.get("studies", []):
        if s.get("agrees") is None:
            text = f"{s['document']}: cannot be checked ({_reason(s.get('reason'))})."
        else:
            text = (f"{s['document']}: the authors say {SAYS.get(s.get('claim'), 'nothing clear')}, "
                    f"the numbers say {SAYS.get(s.get('direction'), 'nothing clear')}.")
        body.append(_study(text, s))
    return head, body


def _best(protocol: Protocol, answer: dict[str, Any], names: Mapping[str, str]) -> tuple[list[KindLine], list[KindLine]]:
    name = lambda i: names.get(i, i)   # noqa: E731
    metric = name(answer.get("metric") or (protocol.best.metric.canonical if protocol.best else ""))
    studies = answer.get("studies", [])
    winner, tied = answer.get("winner"), answer.get("tied", [])
    if winner is not None:
        wins = sorted(answer.get("wins", {}).items(), key=lambda kv: (-kv[1], name(kv[0])))
        head = [_summary(f"On {metric}, {name(winner)} is best in the most papers "
                         f"({_join([f'{name(k)} {n}' for k, n in wins])}).")]
    elif tied and any(s.get("winner") or s.get("tied") for s in studies):
        head = [_summary(f"On {metric}, no single kind is best: {_join([name(k) for k in tied])} tie.")]
    else:
        head = [_summary(CANT_TELL_LINE)]
    body: list[KindLine] = []
    for s in studies:
        if s.get("winner"):
            text = f"{s['document']}: {name(s['winner'])} is best."
        elif s.get("tied"):
            text = f"{s['document']}: {_join([name(k) for k in s['tied']])} tie."
        else:
            text = f"{s['document']}: no comparison ({_reason(s.get('reason'))})."
        body.append(_study(text, s))
    return head, body


def _inventory(protocol: Protocol, answer: dict[str, Any], names: Mapping[str, str]) -> tuple[list[KindLine], list[KindLine]]:
    entries = answer.get("entries", [])
    if not entries:
        return [_summary(CANT_TELL_LINE)], []
    target = answer.get("target") or (protocol.inventory.target if protocol.inventory else "")
    kind = INVENTORY_TARGETS.get(target, target.replace("_", " ") + "s")
    body = []
    for e in entries:
        also = f" (also {_join(e['aliases'])})" if e.get("aliases") else ""
        body.append(_study(f"{e['name']}{also}: {_join(e.get('papers', []))}.", e))
    return [_summary(f"{len(entries)} distinct names of {kind}.")], body


def kind_lines(protocol: Protocol, answer: dict[str, Any], names: Mapping[str, str]) -> list[KindLine]:
    """The lines of the fixed kind `protocol.kind`: summary lines (`study` False), then one per study or entry,
    at most MAX_KIND_LINES in all and then `... and <n> more.`"""
    build = {"effect": _effect, "consistency": _consistency, "best": _best, "inventory": _inventory}[protocol.kind]
    head, body = build(protocol, answer, names)
    lines = [*head, *body]
    if len(lines) <= MAX_KIND_LINES:
        return lines
    return [*lines[:MAX_KIND_LINES], KindLine(text=f"... and {len(lines) - MAX_KIND_LINES} more.")]
