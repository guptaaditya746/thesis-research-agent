"""The protocol of a plan that answers by a fixed kind's rules (consistency, inventory, best).

`kind_protocol` starts from `protocol_for` (the plan run's protocol) and changes only what the kind needs. The kinds
`lines`, `written` and `effect` get `protocol_for` itself, byte for byte, so older plan runs do not change."""
from __future__ import annotations

from typing import Any

import yaml

from .plan import Plan
from .planlines import OTHER, directions, sides
from .planrun import ANY, protocol_for

__all__ = ["answer_problems", "kind_protocol"]

OWN_HEAD = "# Written by code from the plan (evidence/plankinds.py kind_protocol); do not edit.\n"


def _kind_ids(plan: Plan) -> list[str]:
    """The compared things a best answer groups conditions into (not `other`, not `any`)."""
    return [t for t in sides(plan) if t not in (OTHER, ANY)]


def _names(plan: Plan, thing: str) -> list[str]:
    seen: list[str] = []
    for name in [*plan.words.things.get(thing, []), *plan.words.ontology_names.get(thing, [])]:
        if name not in seen:
            seen.append(name)
    return seen


def answer_problems(plan: Plan) -> list[str]:
    """What stops the plan's chosen answer kind from running; the plan page and the batch treat these like
    `check_plan` problems."""
    out: list[str] = []
    if plan.answer_by == "best":
        if not plan.measures:
            out.append("a best answer needs a measure")
        if len(_kind_ids(plan)) < 2:
            out.append("a best answer needs two compared things")
    return out


def kind_protocol(plan: Plan) -> bytes:
    """The plan run's protocol (YAML) for the plan's `answer_by`."""
    base = protocol_for(plan)
    if plan.answer_by not in ("consistency", "inventory", "best"):
        return base
    protocol: dict[str, Any] = yaml.safe_load(base.decode("utf-8"))
    protocol["kind"] = plan.answer_by
    if plan.answer_by == "consistency":
        protocol["consistency"] = {"by": "direction"}
    elif plan.answer_by == "inventory":
        protocol.pop("synthesis")
        protocol["inventory"] = {"target": plan.target or "condition"}
    else:
        protocol.pop("synthesis")
        ids = _kind_ids(plan)
        condition = protocol["evidence_types"]["condition"]
        # `kind` may be null: a paper's further methods are none of the compared things, and the LLM extractor's
        # reply type requires every key, so without null the model had to file them under a compared thing.
        # kinds/best.py leaves a condition out when its kind is null and its name is none of the kinds' names.
        listed = " or ".join([", ".join(ids[:-1]), ids[-1]]) if len(ids) > 1 else ids[0]
        none = "neither" if len(ids) == 2 else "none of them"
        condition["fields"]["properties"]["kind"] = {
            "type": ["string", "null"], "enum": [*ids, None],
            "description": f"{listed} when the condition is that compared thing; null when it is {none}"}
        condition["description"] += (f" kind is the id of the compared thing this condition is ({listed}), or null "
                                     f"when it is {none}; a condition with kind null is left out of the comparison.")
        metric = plan.measures[0] if plan.measures else OTHER
        protocol["best"] = {"metric": {"canonical": metric,
                                       "higher_is_better": directions(plan).get(metric) is not False},
                            "kinds": {t: _names(plan, t) for t in ids}}
    return (OWN_HEAD + yaml.safe_dump(protocol, sort_keys=False, allow_unicode=True, width=120)).encode("utf-8")
