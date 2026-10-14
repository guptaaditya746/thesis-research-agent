"""An ExtractionTask as a concept brief for the research agent (agent/schemas/concept.schema.json).

The agent's prompts are fixed (agent/prompts/system-v2.txt, task-v2.txt) and show it the concept in
full, so the task travels in the concept: a table with one column per field of the evidence type's
schema, the paper (the only file in its corpus), the scope, the fields' meaning, the context items it
may refer to by id, and how to claim. TEMPLATE_VERSION names this wording; it is part of the
extractor's config, so a change of wording is a new extractor id.
"""
from __future__ import annotations

import json
import re
from typing import Any

from evidence.contract import EvidenceType, ExtractionTask, Item

TEMPLATE_VERSION = "agentic-task-v1"
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


def columns(field_schema: dict[str, Any]) -> list[dict[str, str]]:
    """One table column per property of the evidence type's schema (names the concept schema allows)."""
    props = field_schema.get("properties") or {}
    return [{"name": name, "type": column_type(spec)} for name, spec in props.items() if COLUMN_NAME.match(name)]


def describe_fields(field_schema: dict[str, Any], context: list[Item]) -> str:
    required = set(field_schema.get("required") or [])
    parts = []
    for name, spec in (field_schema.get("properties") or {}).items():
        text = f"{name} ({column_type(spec)}{', required' if name in required else ''})"
        if spec.get("description"):
            text += f": {spec['description']}"
        if spec.get("enum"):
            text += f"; one of {', '.join(map(str, spec['enum']))}"
        if any(name == i.evidence_type for i in context):  # e.g. a measurement's condition
            text += "; give the id of the earlier item it refers to"
        parts.append(text)
    return "; ".join(parts) or "the fields the paper states"


def describe_context(context: list[Item]) -> str:
    return "; ".join(f"{i.item_id} ({i.evidence_type}) {json.dumps(i.fields, sort_keys=True, ensure_ascii=False)}"
                     for i in sorted(context, key=lambda i: i.item_id))


def concept_for(task: ExtractionTask, field_schema: dict[str, Any], context: list[Item], file: str,
                length: int) -> dict[str, Any]:
    """The concept brief that asks the agent for every item of the task's evidence type in `file`."""
    kind: EvidenceType = task.evidence_type
    noun = NOUN[kind]
    where = ("the whole paper" if task.scope.kind == "document" or not task.scope.ranges else
             "only these character ranges of the file (offsets into the file as stored, of "
             f"{length} characters): " + ", ".join(f"{a}-{b}" for a, b in task.scope.ranges)
             + "; a quote outside them is not used")
    scope = {
        "paper": f"only {file}, the one paper in the corpus",
        "passages": where,
        "item": f"one row per {noun}: {WHAT[kind]}. List every one the paper states, each once; a value stated twice "
                "(abstract and table) is one row with both quotes",
        "fields": describe_fields(field_schema, context),
        "claims": "for each field of a row, claim a verbatim quote that states it: s = the row id (r1, r2, ...), "
                  f"p = the field name, o = the value, file = {file}; list those claim ids in the row's facts. "
                  "A row without an accepted claim is not used",
    }
    if context:
        scope["earlier_items"] = "items found earlier in this paper, referred to by id: " + describe_context(context)
    title = f"Every {noun} stated in {file}"
    return {
        "title": title,
        "definition": f"{title}, with its fields and a verbatim quote for each field.",
        "measure": {"operation": "list", "of": noun.title().replace(" ", "")},
        "scope": scope,
        "answer_shape": {"kind": "table", "columns": columns(field_schema) or [{"name": "text", "type": "string"}]},
        "competency_questions": [f"Which {noun}s does {file} state?",
                                 "Which passage of the paper states each field of each row?"],
        "needs": [f"the passages of {file} that state each {noun}", "a quote for every field"],
    }
