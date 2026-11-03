"""The protocol lock (spec 6.6): what a run was built from, written next to the protocol as `protocol.lock.json`,
and `diff`, which says in words what differs between two protocols or two runs.

The lock holds the protocol's id and sha256, the domain pack's name and sha256, the ontology's sha256 (None for a
pack without one) and, per evidence type (and `screen`), the ids of the extractors that run, in cascade order."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from . import reasoner
from .contract import Extractor
from .plan import Plan
from .protocol import ExtractorRef, Protocol
from .rundir import LOCK_FILE, PROTOCOL_FILE

__all__ = ["diff", "lock"]


def lock(protocol: Protocol, cascades: dict[str, list[tuple[ExtractorRef, Extractor]]],
         domains: Path | None = None, *, plan: Plan | None = None, reason: str = "on") -> dict[str, Any]:
    """The lock of a run of `protocol` with `cascades` (engine.build_extractors); `domains`: the pack's folder
    when it is not domains/; `plan`: the confirmed plan of a planned run, which adds `plan_sha256` and
    `words_sha256` and `field_ontology_sha256` ({file name: sha256} of the plan field's ontology files the plan run's
    graph and ontology report read, evidence/ontology `ontology_hashes`; the pack's own ontology stays under
    `ontology_sha256`; {} when `reason` is off: the run reads no field ontology). A run without a plan locks exactly
    as before, without those keys."""
    pack = protocol.pack()
    onto = reasoner.ontology_sha256(pack) if domains is None else reasoner.ontology_sha256(pack, domains)
    out: dict[str, Any] = {
        "protocol": {"id": protocol.id, "sha256": protocol.sha256},
        "pack": {"name": pack.name, "sha256": pack.sha256},
        "ontology_sha256": onto,
        "extractors": {etype: [e.spec.extractor_id for _, e in cascade] for etype, cascade in cascades.items()}}
    if plan is not None:
        out["plan_sha256"] = plan.sha256
        out["words_sha256"] = plan.words.sha256
        from .ontology.sources import ontology_hashes
        out["field_ontology_sha256"] = ontology_hashes(plan.field) if reason == "on" else {}
    return out


def _read(path: Path) -> tuple[Any, dict[str, Any] | None]:
    """(the protocol's YAML data, its lock or None) of a protocol file or a run directory."""
    if path.is_dir():
        data = yaml.safe_load((path / PROTOCOL_FILE).read_text(encoding="utf-8"))
        file = path / LOCK_FILE
        return data, json.loads(file.read_text(encoding="utf-8")) if file.is_file() else None
    return yaml.safe_load(path.read_text(encoding="utf-8")), None


def _flat(value: Any, path: str, out: dict[str, Any]) -> None:
    """Every leaf of `value` by dotted path; a list of scalars is one entry (compared as a set), else by index."""
    if isinstance(value, dict):
        for key, child in value.items():
            _flat(child, f"{path}.{key}" if path else str(key), out)
    elif isinstance(value, list) and any(isinstance(v, (dict, list)) for v in value):
        for i, child in enumerate(value):
            _flat(child, f"{path}[{i}]", out)
    else:
        out[path] = value


def _show(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _protocol_lines(a: Any, b: Any) -> list[str]:
    fa: dict[str, Any] = {}
    fb: dict[str, Any] = {}
    _flat(a, "", fa)
    _flat(b, "", fb)
    changed, added, removed = [], [], []
    for path in sorted(set(fa) | set(fb)):
        if path not in fb:
            removed.append(f"removed {path}: {_show(fa[path])}")
        elif path not in fa:
            added.append(f"added {path}: {_show(fb[path])}")
        elif isinstance(fa[path], list) and isinstance(fb[path], list):
            old, new = [_show(v) for v in fa[path]], [_show(v) for v in fb[path]]
            added += [f"added {path}: {v}" for v in new if v not in old]
            removed += [f"removed {path}: {v}" for v in old if v not in new]
        elif fa[path] != fb[path]:
            changed.append(f"changed {path}: {_show(fa[path])} -> {_show(fb[path])}")
    return [*sorted(changed), *sorted(added), *sorted(removed)]


def _lock_lines(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    lines = []
    ea, eb = a["extractors"], b["extractors"]
    for etype in sorted(set(ea) | set(eb)):
        old, new = ea.get(etype, []), eb.get(etype, [])
        for i in range(max(len(old), len(new))):
            x, y = (old[i] if i < len(old) else "none"), (new[i] if i < len(new) else "none")
            if x != y:
                lines.append(f"extractor {etype}[{i}]: {x} -> {y}")
    if a["pack"] != b["pack"]:
        lines.append(f"pack: {a['pack']['name']} {a['pack']['sha256'][:12]} -> {b['pack']['name']} {b['pack']['sha256'][:12]}")
    if a["ontology_sha256"] != b["ontology_sha256"]:
        lines.append(f"ontology: {(a['ontology_sha256'] or 'none')[:12]} -> {(b['ontology_sha256'] or 'none')[:12]}")
    fa, fb = a.get("field_ontology_sha256") or {}, b.get("field_ontology_sha256") or {}
    for name in sorted(set(fa) | set(fb)):
        if fa.get(name) != fb.get(name):
            lines.append(f"field ontology {name}: {(fa.get(name) or 'none')[:12]} -> {(fb.get(name) or 'none')[:12]}")
    return lines


def diff(a: Path | str, b: Path | str) -> list[str]:
    """What differs between `a` and `b`, each a protocol .yaml or a run directory; `["same"]` when nothing does.
    Raises OSError, ValueError or YAMLError when an input cannot be read. A run directory without a lock (made
    before it existed) gets a `no lock (pre-EV4)` line; extractors, pack and ontology are compared when both
    sides have a lock."""
    a, b = Path(a), Path(b)
    (data_a, lock_a), (data_b, lock_b) = _read(a), _read(b)
    lines = _protocol_lines(data_a, data_b)
    if lock_a is not None and lock_b is not None:
        lines += _lock_lines(lock_a, lock_b)
    lines += [f"no lock (pre-EV4): {p}" for p, p_lock in ((a, lock_a), (b, lock_b)) if p.is_dir() and p_lock is None]
    return lines or ["same"]
