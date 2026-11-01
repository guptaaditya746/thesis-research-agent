"""From one agent run's record (runner.collect) to the contract's items, rejected items and coverage.

- **Items** come from the rows of the agent's answer (answer.json, which the harness has already
  checked: every cited claim id is an accepted claim). A row's cells for the schema's properties are
  the item's fields; its spans are the accepted claims its facts cite, each quote anchored again in
  the engine's copy of the document (agent.anchor.find, rule R1) with the task's file name. A span's
  role comes from the claim's predicate, the field it supports (span_role). A link cell naming an
  earlier item (its id, or its label, name or alias) becomes a link (R2). Rows with equal fields and links
  are one item with all their spans (decision 1 of the contract).
- **Rejected**: every claim the broker refused (its anchor reason; broker reasons that are not
  anchor reasons map to not_found or schema), and every row that fails a check: no accepted claim
  (empty_quote), fields against the schema (schema), every span outside the scope (out_of_scope),
  a link to an item not in the context (dangling_link). A cited claim must support its row
  (claim_problem: s is the row id, p one of its fields, a value quote states the cell's number);
  one that does not is rejected (not_found) and not used as a span, and a row left without a
  supporting claim, or a numeric row without a supporting value claim, is rejected (not_found).
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
ITEM_ID = re.compile(r"^[a-z]+-[0-9a-f]{16}$")   # any registered type's prefix (contract.ITEM_PREFIX)
MIN_LINE = 8
# The span role of a quote, per built-in type; a pack's own type has span role `context`.
DEFAULT_ROLE: dict[EvidenceType, str] = {"condition": "condition_label", "metric": "metric_label",
                                         "measurement": "value", "author_claim": "claim"}
MEASUREMENT_ROLE = {"value": "value", "condition": "condition_label", "metric": "metric_label"}


def span_role(kind: EvidenceType, field: Any) -> str:
    """The span role for a quote supporting `field` of an item of type `kind` (other measurement fields: context)."""
    if kind == "measurement":
        return MEASUREMENT_ROLE.get(str(field), "context")
    return DEFAULT_ROLE.get(kind, "context")


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


def _resolve_link(kind: str, value: Any, context: list[Item]) -> str | None:
    """The context item of type `kind` a cell names: by its id, or by its label, name or an alias."""
    if not isinstance(value, str):
        return None
    if any(i.item_id == value and i.evidence_type == kind for i in context):
        return value
    if not ITEM_ID.match(value):
        folded = value.casefold().strip()
        for item in sorted(context, key=lambda i: i.item_id):
            names = [item.fields.get(k) for k in ("label", "name")] + list(item.fields.get("aliases") or [])
            if item.evidence_type == kind and folded in {str(n).casefold().strip() for n in names if n}:
                return item.item_id
    return None


def row_item(row: dict[str, Any], task: ExtractionTask, schema: dict[str, Any], link_names: dict[str, str],
             context: list[Item], claims: dict[str, dict[str, Any]], index: Index
             ) -> tuple[Item | Rejected, list[Rejected]]:
    """One answer row as an Item, or as a Rejected with the first check it fails; plus a Rejected for
    each cited claim that does not support the row (claim_problem), whose quote is not used as a span.

    Cells of the schema's properties are the fields (a null cell stays null: the schema decides
    whether that is allowed); cells named in `link_names` (link -> evidence type) are links.
    """
    kind = task.evidence_type
    cells = row.get("cells") or {}
    props = (schema or {}).get("properties")
    fields = {k: v for k, v in cells.items() if k not in link_names and (k in props if props is not None else v is not None)}
    cited = [claims[c] for f in row.get("facts", []) for c in f.get("claims", []) if c in claims]
    quotes = tuple(dict.fromkeys(c["quote"] for c in cited))

    def rejected(reason: RejectReason, detail: str) -> Rejected:
        return Rejected(evidence_type=kind, fields={**fields, **{k: cells.get(k) for k in link_names if cells.get(k)}},
                        quotes=quotes, reason=reason, detail=f"row {row.get('id')}: {detail}")

    links = {}
    for name, target_type in link_names.items():
        value = cells.get(name)
        if value is None:
            continue
        target = _resolve_link(target_type, value, context)
        if target is None:
            return rejected("dangling_link", f"{name}={value!r} names no {target_type} item of the context"), []
        links[name] = target
    errors = sorted(e.message for e in Draft202012Validator(schema).iter_errors(fields)) if schema else []
    if errors:
        return rejected("schema", "; ".join(errors)[:500]), []
    if not cited:
        return rejected("empty_quote", "no accepted claim cited"), []
    usable, unsupported = [], []
    for c in cited:
        why = claim_problem(c, row.get("id"), cells, link_names)
        if why:
            unsupported.append(Rejected(evidence_type=kind, fields={str(c.get("p")): c.get("o")},
                                        quotes=(c["quote"],), reason="not_found",
                                        detail=f"row {row.get('id')}: {c['claim_id']} {why}"))
        else:
            usable.append(c)
    numeric = _number(fields.get("value")) is not None
    if not usable or (numeric and not any(c.get("p") == "value" for c in usable)):
        what = "the value" if usable else "this row"
        return rejected("not_found", f"no cited claim states {what}"), unsupported
    spans, outside = {}, 0
    for c in usable:
        try:
            sel = find(index, c["quote"], file=task.document.file)
        except AnchorError as exc:  # the broker anchored it in the same text, so this means a different copy
            reason = exc.reason if exc.reason in ANCHOR_REASONS else "not_found"
            return rejected(reason, f"{c['claim_id']}: {exc}"), unsupported  # type: ignore[arg-type]
        if not task.scope.contains(sel.start, sel.end):
            outside += 1
            continue
        role = span_role(kind, c.get("p"))
        spans[(role, sel.start, sel.end)] = Span.of(role, sel)
    if not spans:
        return rejected("out_of_scope", f"all {outside} quoted passages lie outside the scope"), unsupported
    return Item.build(kind, fields, [spans[k] for k in sorted(spans)], links=links), unsupported


NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
VALUE_TOLERANCE = 0.005


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def quote_states(quote: str, value: float) -> bool:
    """A number in the quote that normalises to `value`: as written, or as a percentage (62% or 62.0 -> 0.62)."""
    for raw in NUMBER.findall(quote):
        n = float(raw.replace(",", "."))
        if min(abs(n - value), abs(n / 100 - value)) <= VALUE_TOLERANCE + 1e-12:
            return True
    return False


def claim_problem(claim: dict[str, Any], row_id: Any, cells: dict[str, Any], link_names: dict[str, str]) -> str:
    """Why a cited claim does not support its row ('' when it does).

    The concept asks for s = the row id and p = the field name; a claim for another row or for no
    field of this row is not this row's evidence, and a value claim's quote must state the cell's
    number (within 0.005, as written or as a percentage), so a row cannot borrow another row's span.
    """
    if claim.get("s") != row_id:
        return f"is about {claim.get('s')!r}, not this row"
    field = claim.get("p")
    if field not in cells and field not in link_names:
        return f"names the field {field!r}, which the row does not have"
    value = _number(cells.get("value"))
    if field == "value" and value is not None and not quote_states(str(claim.get("quote", "")), value):
        return f"quotes {claim.get('quote')!r}, which does not state the value {value}"
    return ""


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
