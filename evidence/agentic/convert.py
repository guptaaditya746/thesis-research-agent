"""From one agent run's record (runner.collect) to the contract's items, rejected items and coverage.

- **Items** come from the rows of the agent's answer (answer.json, which the harness has already
  checked: every cited claim id is an accepted claim). A row's cells are the item's fields (null
  cells left out); its spans are the accepted claims its facts cite, each quote anchored again in
  the engine's copy of the document (agent.anchor.find, rule R1) with the task's file name. A span's
  role comes from the claim's predicate, the field it supports (ROLE). A field naming an earlier
  item (its id, or its label, name or alias) becomes a link (R2). Rows with equal fields and links
  are one item with all their spans (decision 1 of the contract).
- **Rejected**: every claim the broker refused (its anchor reason; broker reasons that are not
  anchor reasons map to not_found or schema), and every row that fails a check: no accepted claim
  (empty_quote), fields against the schema (schema), every span outside the scope (out_of_scope),
  a link to an item not in the context (dangling_link).
- **Coverage** is what the agent was shown: a line of the paper counts as read when it occurs in the
  output of one of its commands (the first 8 KB the agent saw). Lines of fewer than MIN_LINE
  characters (blank lines, table rules) take the state of the lines around them. Read runs are
  `found` (with the number of item spans in them) or `none`; runs never shown are `skipped`
  (reason not_read). Everything is clipped to the task's scope.
"""
from __future__ import annotations

import re
from typing import Any

from jsonschema import Draft202012Validator

from agent.anchor import AnchorError, Index, find
from evidence.contract import (Coverage, EvidenceType, ExtractionTask, Item, Rejected, RejectReason, Span)

ANCHOR_REASONS = {"empty_quote", "not_found", "ambiguous", "partial_number"}
ITEM_ID = re.compile(r"^[ckma]-[0-9a-f]{16}$")
MIN_LINE = 8
DEFAULT_ROLE: dict[EvidenceType, str] = {"condition": "condition_label", "metric": "metric_label",
                                         "measurement": "value", "author_claim": "claim"}
MEASUREMENT_ROLE = {"value": "value", "condition": "condition_label", "metric": "metric_label"}


def span_role(kind: EvidenceType, field: Any) -> str:
    """The span role for a quote supporting `field` of an item of type `kind` (other measurement fields: context)."""
    if kind == "measurement":
        return MEASUREMENT_ROLE.get(str(field), "context")
    return DEFAULT_ROLE[kind]


def reject_reason(broker_reason: str | None) -> RejectReason:
    reason = broker_reason or "not_found"
    if reason in ANCHOR_REASONS:
        return reason  # type: ignore[return-value]
    if reason.startswith(("malformed_json", "missing_field", "bad_field", "request_too_large")):
        return "schema"
    return "not_found"  # unknown_file, file_outside_corpus, corpus_file_hash_mismatch


def rejected_claims(record: dict[str, Any], kind: EvidenceType) -> list[Rejected]:
    out = []
    for c in record.get("claims", []):
        if c["status"] == "accepted":
            continue
        fields = {str(c["p"]): c["o"]} if isinstance(c.get("p"), str) and c.get("o") is not None else {}
        out.append(Rejected(evidence_type=kind, fields=fields, quotes=(c["quote"],) if isinstance(c.get("quote"), str) else (),
                            reason=reject_reason(c.get("reason")), detail=f"claim at step {c['step_id']}: {c.get('reason')}"))
    return out


def _resolve_link(name: str, value: Any, context: list[Item]) -> str | None:
    """The context item a field value names: its id, or (for a field named after its type) its label."""
    if isinstance(value, str) and any(i.item_id == value for i in context):
        return value
    if isinstance(value, str) and not ITEM_ID.match(value):
        folded = value.casefold().strip()
        for item in sorted(context, key=lambda i: i.item_id):
            names = [item.fields.get(k) for k in ("label", "name")] + list(item.fields.get("aliases") or [])
            if item.evidence_type == name and folded in {str(n).casefold().strip() for n in names if n}:
                return item.item_id
    return None


def row_item(row: dict[str, Any], task: ExtractionTask, schema: dict[str, Any], context: list[Item],
             claims: dict[str, dict[str, Any]], index: Index) -> Item | Rejected:
    """One answer row as an Item, or as a Rejected with the first check it fails."""
    kind = task.evidence_type
    fields = {k: v for k, v in (row.get("cells") or {}).items() if v is not None}
    cited = [claims[c] for f in row.get("facts", []) for c in f.get("claims", []) if c in claims]
    quotes = tuple(dict.fromkeys(c["quote"] for c in cited))

    def rejected(reason: RejectReason, detail: str) -> Rejected:
        return Rejected(evidence_type=kind, fields=fields, quotes=quotes, reason=reason, detail=f"row {row.get('id')}: {detail}")

    links = {}
    context_types = {i.evidence_type for i in context}
    for name, value in list(fields.items()):
        target = _resolve_link(name, value, context)
        if target:
            fields[name] = links[name] = target
        elif (isinstance(value, str) and ITEM_ID.match(value)) or (name in context_types and name != kind):
            return rejected("dangling_link", f"{name}={value!r} names no item of the context")
    errors = sorted(e.message for e in Draft202012Validator(schema).iter_errors(fields)) if schema else []
    if errors:
        return rejected("schema", "; ".join(errors)[:500])
    if not cited:
        return rejected("empty_quote", "no accepted claim cited")
    spans, outside = {}, 0
    for c in cited:
        try:
            sel = find(index, c["quote"], file=task.document.file)
        except AnchorError as exc:  # the broker anchored it in the same text, so this means a different copy
            return rejected(exc.reason if exc.reason in ANCHOR_REASONS else "not_found", f"{c['claim_id']}: {exc}")  # type: ignore[arg-type]
        if not task.scope.contains(sel.start, sel.end):
            outside += 1
            continue
        role = span_role(kind, c.get("p"))
        spans[(role, sel.start, sel.end)] = Span.of(role, sel)
    if not spans:
        return rejected("out_of_scope", f"all {outside} quoted passages lie outside the scope")
    return Item.build(kind, fields, [spans[k] for k in sorted(spans)], links=links)


def merge(items: list[Item]) -> list[Item]:
    """Items with equal type, fields and links become one item holding all their spans."""
    groups: dict[str, list[Item]] = {}
    for item in items:
        key = repr((item.evidence_type, sorted(item.fields.items(), key=str), sorted(item.links.items())))
        groups.setdefault(key, []).append(item)
    out = []
    for same in groups.values():
        spans = {(s.role, s.selector["start"], s.selector["end"]): s for i in same for s in i.spans}
        first = same[0]
        out.append(Item.build(first.evidence_type, first.fields, [spans[k] for k in sorted(spans)], links=first.links))
    return out


def line_reads(text: str, outputs: list[str]) -> list[tuple[int, int, bool]]:
    """(start, end, read) per line of `text`; see the module docstring for what counts as read."""
    blob = "\n\0\n".join(outputs)
    lines, pos = [], 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        lines.append([pos, pos + len(line), (stripped in blob) if len(stripped) >= MIN_LINE else None])
        pos += len(line)
    known = [i for i, ln in enumerate(lines) if ln[2] is not None]
    for i, ln in enumerate(lines):
        if ln[2] is None:
            before = [lines[j][2] for j in known if j < i][-1:]
            after = [lines[j][2] for j in known if j > i][:1]
            ln[2] = all(before + after) if before + after else False
    return [(a, b, bool(r)) for a, b, r in lines]


def coverage(text: str, record: dict[str, Any], scope_ranges: list[tuple[int, int]], items: list[Item]) -> list[Coverage]:
    runs: list[list[Any]] = []
    for a, b, read in line_reads(text, [c.get("output", "") for c in record.get("commands", [])]):
        if runs and runs[-1][2] == read:
            runs[-1][1] = b
        else:
            runs.append([a, b, read])
    starts = [s.selector["start"] for i in items for s in i.spans]
    out = []
    for a, b, read in runs:
        for lo, hi in scope_ranges:
            x, y = max(a, lo), min(b, hi)
            if x >= y:
                continue
            if not read:
                out.append(Coverage(range=(x, y), status="skipped", reason="not_read"))
            else:
                found = sum(x <= s < y for s in starts)
                out.append(Coverage(range=(x, y), status="found" if found else "none", found=found))
    return out
