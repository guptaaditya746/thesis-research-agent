"""Compare a frozen proposal with a hand-written protocol (the runbook's step 9 and the flow's tests).

Both protocols are parsed and compared without their id and revision, free text (descriptions, the screening
question) and the bm25 query lists; screen terms as a set. The query lists are checked separately: the
hand-written protocol's query tokens per type should be a subset of the frozen one's.

    python -m evidence.propose.compare HAND.yaml FROZEN.yaml > protocol-compare.json

prints `{equal, differs: [{path, hand, frozen}], query_tokens_superset: {type: bool}}`. Nothing runs either
protocol.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from evidence.locate import tokens
from evidence.protocol import Protocol, load


def _strip_descriptions(schema: Any) -> Any:
    if isinstance(schema, dict):
        return {k: _strip_descriptions(v) for k, v in schema.items() if k != "description"}
    if isinstance(schema, list):
        return [_strip_descriptions(v) for v in schema]
    return schema


def comparable(p: Protocol) -> dict[str, Any]:
    """The parsed protocol without its id and revision, free text (descriptions, the screening question) and
    bm25 query lists (checked separately, as a superset); screen terms as a set; the params an exhaustive locate
    ignores."""
    d = p.model_dump(mode="json", exclude={"id", "revision"})
    if d["locate"]["strategy"] == "exhaustive":
        d["locate"]["params"] = {}
    if d.get("screen"):
        d["screen"]["question"] = None
        d["screen"]["terms"] = sorted(d["screen"]["terms"])
    for spec in d["evidence_types"].values():
        spec["description"] = None
        spec["query"] = None
        spec["fields"] = _strip_descriptions(spec["fields"])
    return d


def query_tokens(p: Protocol) -> dict[str, set[str]]:
    return {t: {x for q in spec.query for x in tokens(q)} for t, spec in p.evidence_types.items()}


def _flat(x: Any, path: str = "") -> dict[str, Any]:
    if isinstance(x, dict):
        return {k: v for key, val in x.items() for k, v in _flat(val, f"{path}.{key}" if path else key).items()}
    return {path: x}


def compare(hand: Protocol, frozen: Protocol) -> dict[str, Any]:
    a, b = _flat(comparable(hand)), _flat(comparable(frozen))
    differs = [{"path": k, "hand": a.get(k), "frozen": b.get(k)} for k in sorted(a.keys() | b.keys())
               if a.get(k) != b.get(k)]
    qh, qf = query_tokens(hand), query_tokens(frozen)
    return {"equal": not differs, "differs": differs,
            "query_tokens_superset": {t: qh[t] <= qf.get(t, set()) for t in qh}}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: python -m evidence.propose.compare HAND.yaml FROZEN.yaml", file=sys.stderr)
        return 2
    print(json.dumps(compare(load(args[0]), load(args[1])), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
