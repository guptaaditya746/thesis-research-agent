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
        condition["fields"]["properties"]["kind"] = {"type": "string", "enum": ids}
        condition["description"] += f" kind is the id of the thing the condition is: {', '.join(ids)}"
        metric = plan.measures[0] if plan.measures else OTHER
        protocol["best"] = {"metric": {"canonical": metric,
                                       "higher_is_better": directions(plan).get(metric) is not False},
                            "kinds": {t: _names(plan, t) for t in ids}}
    return (OWN_HEAD + yaml.safe_dump(protocol, sort_keys=False, allow_unicode=True, width=120)).encode("utf-8")
