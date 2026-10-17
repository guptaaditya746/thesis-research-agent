"""An ExtractionTask as a concept brief for the research agent (agent/schemas/concept.schema.json).

The agent's prompts are fixed (agent/prompts/system-v2.txt, task-v2.txt) and show it the concept in
full, so the task travels in the concept: a table with one column per field of the evidence type's
schema, the paper (the only file in its corpus), the scope, the fields' meaning, the context items it
may refer to by id, how to claim, and (a targeted task of the funnel, Part D) `scope.focus`: what is
still missing. TEMPLATE_VERSION names this wording; it is part of the extractor's config, so a change
of wording is a new extractor id (v2: the focus line).
"""
from __future__ import annotations

import json
import re
from typing import Any

from evidence.contract import EvidenceType, ExtractionTask, Item

TEMPLATE_VERSION = "agentic-task-v2"
NOUN = {"condition": "condition", "metric": "metric", "measurement": "measurement", "author_claim": "author claim"}
WHAT = {
    "condition": "a system or setting the paper compares (for example a model without retrieval, a retrieval-augmented "
                 "variant, an ablation or another system)",
    "metric": "a quantity the paper measures its systems with (for example answer accuracy, hallucination rate, latency)",
    "measurement": "one reported number: the value of one metric for one condition (in a table, or in the text)",
    "author_claim": "the authors' own conclusion about whether retrieval improves the factual accuracy of answers",
}
COLUMN_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
SCALARS = {"number": "number", "integer": "integer", "boolean": "boolean", "string": "string"}


def column_type(schema: dict[str, Any]) -> str:
    kind = schema.get("type", "string")
    if isinstance(kind, list):
        kind = next((k for k in kind if k != "null"), "string")
    return SCALARS.get(kind, "string")


def link_names(task: ExtractionTask, links: dict[str, str] | None, context: list[Item]) -> dict[str, str]:
    """Link name -> evidence type it points to: the protocol's `links` when given, else one per context type."""
    if links:
        return dict(links)
    return {t: t for t in sorted({i.evidence_type for i in context}) if t != task.evidence_type}


def columns(field_schema: dict[str, Any], links: dict[str, str]) -> list[dict[str, str]]:
    """A table column per link (an earlier item's id) and per property of the schema (names the concept allows)."""
    props = field_schema.get("properties") or {}
    out = [{"name": name, "type": "string"} for name in links if COLUMN_NAME.match(name)]
    return out + [{"name": n, "type": column_type(s)} for n, s in props.items() if COLUMN_NAME.match(n) and n not in links]


def describe_fields(field_schema: dict[str, Any], links: dict[str, str]) -> str:
    required = set(field_schema.get("required") or [])
    parts = [f"{name}: the id of the earlier {NOUN.get(kind, kind)} item this one belongs to (listed below)"
             for name, kind in links.items()]
    for name, spec in (field_schema.get("properties") or {}).items():
        text = f"{name} ({column_type(spec)}{', required' if name in required else ''})"
        if spec.get("description"):
            text += f": {spec['description']}"
        if spec.get("enum"):
            text += f"; one of {', '.join(map(str, spec['enum']))}"
        parts.append(text)
    return "; ".join(parts) or "the fields the paper states"


def describe_context(context: list[Item]) -> str:
    return "; ".join(f"{i.item_id} ({i.evidence_type}) {json.dumps(i.fields, sort_keys=True, ensure_ascii=False)}"
                     for i in sorted(context, key=lambda i: i.item_id))


def concept_for(task: ExtractionTask, field_schema: dict[str, Any], links: dict[str, str], context: list[Item],
                file: str, length: int, description: str = "") -> dict[str, Any]:
    """The concept brief that asks the agent for every item of the task's evidence type in `file`.

    `links` (link_names): the columns that name earlier items; `description`: the protocol's text for
    the evidence type, used instead of the built-in one when given.
    """
    kind: EvidenceType = task.evidence_type
    noun = NOUN[kind]
    what = (" ".join(description.split()) or WHAT[kind]).rstrip(".") + "."
    where = ("the whole paper" if task.scope.kind == "document" or not task.scope.ranges else
             "only these character ranges of the file (offsets into the file as stored, of "
             f"{length} characters): " + ", ".join(f"{a}-{b}" for a, b in task.scope.ranges)
             + "; a quote outside them is not used")
    scope = {
        "paper": f"only {file}, the one paper in the corpus",
        "passages": where,
        "item": f"one row per {noun}: {what} List every one the paper states, each once; a value stated twice "
                "(abstract and table) is one row with both quotes",
        "fields": describe_fields(field_schema, links),
        "claims": "for each field of a row, claim a verbatim quote that states it: s = the row id (r1, r2, ...), "
                  f"p = the field name, o = the value, file = {file}; list those claim ids in the row's facts. "
                  "A row without an accepted claim is not used",
    }
    if context:
        scope["earlier_items"] = "items found earlier in this paper, referred to by id: " + describe_context(context)
    if task.focus is not None:   # the funnel's targeted task: what the earlier extractors left missing
        have = "; ".join(f"{k} found: {', '.join(v) if v else 'none'}" for k, v in sorted(task.focus.have.items()))
        scope["focus"] = f"gap {task.focus.gap}: {task.focus.want} ({have})"
    title = f"Every {noun} stated in {file}"
    return {
        "title": title,
        "definition": f"{title}, with its fields and a verbatim quote for each field.",
        "measure": {"operation": "list", "of": noun.title().replace(" ", "")},
        "scope": scope,
        "answer_shape": {"kind": "table",
                         "columns": columns(field_schema, links) or [{"name": "text", "type": "string"}]},
        "competency_questions": [f"Which {noun}s does {file} state?",
                                 "Which passage of the paper states each field of each row?"],
        "needs": [f"the passages of {file} that state each {noun}", "a quote for every field"],
    }
