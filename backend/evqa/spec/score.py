"""Advisor eval: how much of what the question needs made it into the locked Spec. Eval passes the needs (derived
from its gold); this module reads nothing itself."""
from __future__ import annotations

import re
from typing import Any

from evqa.contracts import Spec


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def spec_names(spec: Spec) -> set[str]:
    """Every label and synonym in the spec, normalised (lower case, punctuation as spaces)."""
    names = [*spec.subjects, spec.measure, *([spec.comparator] if spec.comparator else [])]
    return {_norm(x) for n in names for x in (n.label, *n.synonyms)}


def spec_slots(spec: Spec) -> dict[str, str]:
    """Point id -> the spec's value: a value the question fixes, else the open point's choice."""
    return {**{p.id: p.choice for p in spec.open_points}, **spec.fixed}


def advisor_score(spec: Spec, needed: dict[str, Any]) -> dict[str, Any]:
    """needed = {"names": [names the papers use that Find needs], "slots": {point id: value, "all" for open}}.

    Returns the share present for names and for slots, what is missing, and `share` over both together.
    A slot matches when the normalised values are equal ("24 weeks" == "24 Weeks")."""
    have_names, have_slots = spec_names(spec), spec_slots(spec)
    names = list(dict.fromkeys(needed.get("names", [])))
    slots = dict(needed.get("slots", {}))
    miss_names = [n for n in names if _norm(n) not in have_names]
    miss_slots = {k: {"needed": v, "spec": have_slots.get(k)} for k, v in slots.items()
                  if _norm(str(have_slots.get(k, ""))) != _norm(str(v))}
    total = len(names) + len(slots)
    hit = total - len(miss_names) - len(miss_slots)

    def share(n: int, m: int) -> float | None:
        return round((n - m) / n, 4) if n else None

    return {"names": {"needed": len(names), "present": len(names) - len(miss_names),
                      "share": share(len(names), len(miss_names)), "missing": miss_names},
            "slots": {"needed": len(slots), "present": len(slots) - len(miss_slots),
                      "share": share(len(slots), len(miss_slots)), "missing": miss_slots},
            "share": round(hit / total, 4) if total else None}
