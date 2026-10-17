"""Step 6, `amend` (deterministic): a frozen protocol changed by hand becomes the next revision, with the
reason and the impact on record (PROSPERO/OSF-style amendments; Part E).

The person edits DIR/protocol.yaml, then runs `evidence propose amend DIR --reason R [--before-main-run]`.
The edited file is compared with the last frozen or amended revision, kept as `protocol.v<N>.yaml`: the
parsed protocols (without `revision`) are walked key by key, and every changed, added or removed key path
(`synthesis.min_effect`, `evidence_types.condition.extractors`; a list counts as one value) is the impact.
`revision` becomes N + 1 in protocol.yaml (the line is rewritten in place, so the person's layout and
comments stay; `with_revision` says when it falls back to a full dump), the file is copied to `protocol.v<N+1>.yaml`, and one line is appended to amendments.jsonl:

    {revision, sha256, amends_sha256, reason, impact, before_main_run, at}

`revision` stands where Part E wrote `version`: `version` is the protocol format (evidence/protocol.py).
`amends_sha256` is the protocol sha256 of revision N, `sha256` that of the new revision. Refused: an empty
reason, an edit that changes nothing, a protocol that does not validate, a directory not frozen.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from ..protocol import Protocol, parse
from .common import AMENDMENTS, PROPOSAL, PROTOCOL, ProposalError, need, now, read_json, write_text
from .freeze import versioned


def changes(old: Any, new: Any, path: str = "") -> list[str]:
    """Key paths where two parsed protocols differ (dicts walked key by key, anything else compared whole)."""
    if isinstance(old, dict) and isinstance(new, dict):
        out: list[str] = []
        for key in [*old, *(k for k in new if k not in old)]:
            sub = f"{path}.{key}" if path else str(key)
            if key not in old or key not in new:
                out.append(sub)
            else:
                out += changes(old[key], new[key], sub)
        return out
    return [] if old == new else [path or "(root)"]


def _dump(p: Protocol) -> dict[str, Any]:
    return p.model_dump(mode="json", exclude={"revision"})


def current_revision(directory: Path) -> int:
    lines = (directory / AMENDMENTS).read_text(encoding="utf-8").splitlines() if (directory / AMENDMENTS).exists() else []
    rows = [json.loads(x) for x in lines if x.strip()]
    if rows:
        return int(rows[-1]["revision"])
    return int(read_json(directory / PROPOSAL)["protocol"]["revision"])


def _dumped(text: str, revision: int) -> str:
    """The full-dump fallback: the parsed mapping with `revision` after `version` (comments are lost)."""
    from .freeze import ordered
    return yaml.safe_dump(ordered(yaml.safe_load(text), revision), sort_keys=False, allow_unicode=True, width=110)


def with_revision(text: str, revision: int) -> str:
    """The protocol text with its top-level `revision` set, editing one line so layout and comments stay:
    `revision: <n>` (a trailing comment kept) is rewritten, or a line is added after `version:` when there is
    none. Anything else falls back to a full dump of the parsed protocol (comments lost): a value on the next
    line (`revision:` alone), a quoted or flow-style key, or any edit after which the parsed revision is not
    `revision` (e.g. a second, quoted `"revision"` key further down)."""
    line = re.compile(r"^revision:[ \t]*(?P<value>[^#\n]*?)[ \t]*(?P<comment>#[^\n]*)?$", re.M)
    found = line.search(text)
    if found and found.group("value"):
        comment = f"  {found.group('comment')}" if found.group("comment") else ""
        edited = text[:found.start()] + f"revision: {revision}{comment}" + text[found.end():]
    elif found:   # `revision:` with its value on the next line
        return _dumped(text, revision)
    else:
        version = re.compile(r"^(version:[^\n]*)$", re.M)
        if not version.search(text):
            return _dumped(text, revision)
        edited = version.sub(lambda m: f"{m.group(1)}\nrevision: {revision}", text, count=1)
    try:
        data = yaml.safe_load(edited)
    except yaml.YAMLError:
        return _dumped(text, revision)
    return edited if isinstance(data, dict) and data.get("revision") == revision else _dumped(text, revision)


def run(directory: Path | str, reason: str, *, before_main_run: bool = False, at: str | None = None) -> dict[str, Any]:
    """Amend DIR/protocol.yaml; returns the amendments.jsonl line written."""
    directory = Path(directory)
    if not reason or not reason.strip():
        raise ProposalError("an amendment needs a reason (--reason)")
    need(directory, PROPOSAL, "freeze")
    path = need(directory, PROTOCOL, "freeze")
    n = current_revision(directory)
    base_path = versioned(directory, n)
    if not base_path.exists():
        raise ProposalError(f"{base_path} is missing: it is the revision {n} the amendment is compared with")
    try:
        old = parse(base_path.read_text(encoding="utf-8"))
    except (ValueError, yaml.YAMLError) as exc:
        raise ProposalError(f"{base_path} (revision {n}, the base) does not validate: {exc}") from exc
    text = path.read_text(encoding="utf-8")
    try:
        new = parse(text)
    except (ValueError, yaml.YAMLError) as exc:
        raise ProposalError(f"{path} does not validate: {exc}") from exc
    impact = changes(_dump(old), _dump(new))
    if not impact:
        raise ProposalError(f"{path} is the same protocol as revision {n}: nothing to amend")
    try:
        text = with_revision(text, n + 1)
        amended = parse(text)
    except (ValueError, yaml.YAMLError) as exc:
        raise ProposalError(f"could not set revision {n + 1} in {path}: {exc}") from exc
    if amended.revision != n + 1:
        raise ProposalError(f"could not set revision {n + 1} in {path}")
    write_text(path, text)
    write_text(versioned(directory, n + 1), text)
    entry = {"revision": n + 1, "sha256": amended.sha256, "amends_sha256": old.sha256, "reason": reason.strip(),
             "impact": impact, "before_main_run": bool(before_main_run), "at": at or now()}
    with (directory / AMENDMENTS).open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry
