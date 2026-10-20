"""One hash chain over every record of a run (events.jsonl), with claims.jsonl as a verified copy.

Each record carries `prev_hash` (the previous record's hash, or 64 zeros) and `hash`, the sha256 of
the canonical JSON of the record without `hash`. Records are stored one per line in canonical
form, so a checker can also demand that each stored line is canonical.

events.jsonl holds every record in chain order (docs/earlier-work.md, Provenance model: one record per activity,
claims included). claims.jsonl holds the `claim` records again, byte-identical and in the same
order, so claim readers need not scan the whole log; verification checks the two agree.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonio import GENESIS, canonical, canonical_bytes, sha256_hex

FIELDS = ("task_id", "subtype", "used", "generated", "parent_task_id", "group_id", "agent_id",
          "source_agent_id", "workflow_id", "started_at", "ended_at", "status", "custom_metadata",
          "step_id", "prev_hash", "hash")


def task_id(n: int) -> str:
    return f"t{n:06d}"


def seal(record: dict[str, Any], prev_hash: str) -> dict[str, Any]:
    body = {k: v for k, v in record.items() if k != "hash"}
    body["prev_hash"] = prev_hash
    body["hash"] = sha256_hex(canonical_bytes(body))
    return body


def line(record: dict[str, Any]) -> bytes:
    return canonical_bytes(record) + b"\n"


@dataclass
class Report:
    records: int = 0
    claims: int = 0
    head: str = GENESIS
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def verify(events: Path, claims: Path | None = None, head: str | None = None) -> Report:
    """Check the chain in `events`, that `claims` repeats its claim records, and optionally the head."""
    report = Report()
    claim_lines: list[bytes] = []
    prev = GENESIS
    for n, raw in enumerate(events.read_bytes().splitlines(keepends=True), 1):
        where = f"{events.name}:{n}"
        try:
            text = raw.decode("utf-8")
            record = json.loads(text)
        except ValueError as exc:
            report.errors.append(f"{where}: not UTF-8 JSON ({exc})")
            return report
        if not isinstance(record, dict) or set(record) != set(FIELDS):
            report.errors.append(f"{where}: fields differ from the record schema")
            return report
        if text != canonical(record) + "\n":
            report.errors.append(f"{where}: line is not in canonical form")
            return report
        if record["prev_hash"] != prev:
            report.errors.append(f"{where}: prev_hash does not match the previous record")
            return report
        if seal(record, prev)["hash"] != record["hash"]:
            report.errors.append(f"{where}: hash does not match the record")
            return report
        if record["task_id"] != task_id(n):
            report.errors.append(f"{where}: task_id {record['task_id']} out of sequence")
            return report
        if record["subtype"] == "claim":
            claim_lines.append(raw)
        prev = record["hash"]
        report.records = n
    report.head = prev
    if claims is not None:
        copied = claims.read_bytes().splitlines(keepends=True) if claims.exists() else []
        report.claims = len(copied)
        if copied != claim_lines:
            first = next((i for i, (a, b) in enumerate(zip(copied, claim_lines)) if a != b),
                         min(len(copied), len(claim_lines)))
            report.errors.append(f"{claims.name}:{first + 1}: differs from the claim records in "
                                 f"{events.name} ({len(copied)} lines vs {len(claim_lines)} claim records)")
    if head is not None and head != report.head:
        report.errors.append(f"head {report.head} differs from the expected head {head}")
    return report
