"""Concept brief and answer validation (docs/earlier-work.md, build row 1.3).

The concept schema and the concept-independent answer schema live in agent/schemas/. A concept's
answer_shape narrows the answer: `answer_schema_for` derives the full JSON Schema of a valid answer
for one concept (table cells per column, or graph rows per edge type).
"""
from __future__ import annotations

import copy
from typing import Any

from . import schema
from jsonio import canonical_bytes, sha256_hex


def concept_sha256(concept: dict[str, Any]) -> str:
    """Hash of concept.json as RunDir writes it (canonical form plus newline)."""
    return sha256_hex(canonical_bytes(concept) + b"\n")


def validate_concept(concept: Any) -> list[str]:
    problems = schema.check("concept", concept)
    if problems:
        return problems
    shape = concept["answer_shape"]
    if shape["kind"] == "table":
        names = [c["name"] for c in shape["columns"]]
        problems += [f"answer_shape: duplicate column {n!r}" for n in sorted(set(names)) if names.count(n) > 1]
    else:
        types = [n["type"] for n in shape["nodes"]]
        problems += [f"answer_shape: duplicate node type {t!r}" for t in sorted(set(types)) if types.count(t) > 1]
        seen: set[tuple[str, str, str]] = set()
        for edge in shape["edges"]:
            key = (edge["source"], edge["predicate"], edge["target"])
            problems += [f"answer_shape: edge {key} uses undeclared node type {t!r}"
                         for t in (edge["source"], edge["target"]) if t not in types]
            if key in seen:
                problems.append(f"answer_shape: duplicate edge {key}")
            seen.add(key)
            attrs = [a["name"] for a in edge.get("attributes", [])]
            if len(attrs) != len(set(attrs)):
                problems.append(f"answer_shape: duplicate attribute in edge {key}")
    return problems


def _value(type_name: str, nullable: bool = True) -> dict[str, Any]:
    if type_name.startswith("list<"):
        out: dict[str, Any] = {"type": "array", "items": _value(type_name[5:-1], nullable=False)}
    elif type_name in ("integer", "number", "boolean"):
        out = {"type": type_name}
    else:  # string, date, or an ontology class given by its label
        out = {"type": "string", "minLength": 1}
    if nullable:  # null = the agent could not establish the value
        out["type"] = [out["type"], "null"]
    return out


def answer_schema_for(concept: dict[str, Any]) -> dict[str, Any]:
    """The answer schema with `rows` narrowed to this concept's answer_shape."""
    base = copy.deepcopy(schema.load("answer"))
    shape = concept["answer_shape"]
    row_id = base["$defs"]["row"]["properties"]["id"]
    facts = base["$defs"]["row"]["properties"]["facts"]
    base["properties"]["kind"] = {"const": shape["kind"]}
    if shape["kind"] == "table":
        names = [c["name"] for c in shape["columns"]]
        rows = {
            "type": "object", "additionalProperties": False, "required": ["id", "cells", "facts"],
            "properties": {
                "id": row_id, "facts": facts,
                "cells": {"type": "object", "additionalProperties": False, "required": names,
                          "properties": {c["name"]: _value(c["type"]) for c in shape["columns"]}},
            },
        }
    else:
        variants = []
        for edge in shape["edges"]:
            attrs = {a["name"]: _value(a["type"]) for a in edge.get("attributes", [])}
            variants.append({
                "type": "object", "additionalProperties": False,
                "required": ["id", "source", "source_type", "predicate", "target", "target_type", "facts"],
                "properties": {
                    "id": row_id, "facts": facts,
                    "source": {"type": "string", "minLength": 1}, "source_type": {"const": edge["source"]},
                    "predicate": {"const": edge["predicate"]},
                    "target": {"type": "string", "minLength": 1}, "target_type": {"const": edge["target"]},
                    "attributes": {"type": "object", "additionalProperties": False, "properties": attrs},
                },
            })
        rows = {"oneOf": variants}
    base["properties"]["rows"] = {"type": "array", "items": rows}
    return base


def validate_answer(answer: Any, concept: dict[str, Any]) -> list[str]:
    """Schema problems, a concept hash mismatch, and duplicate row or fact ids."""
    problems = schema.errors(answer_schema_for(concept), answer)
    if problems:
        return problems
    if answer["concept_sha256"] != concept_sha256(concept):
        problems.append("concept_sha256 does not match the concept")
    rows = [r["id"] for r in answer["rows"]]
    facts = [f["id"] for r in answer["rows"] for f in r["facts"]]
    problems += [f"duplicate row id {i}" for i in sorted(set(rows)) if rows.count(i) > 1]
    problems += [f"duplicate fact id {i}" for i in sorted(set(facts)) if facts.count(i) > 1]
    return problems


def claim_ids(answer: dict[str, Any]) -> set[str]:
    """Every claim id the answer cites (1.11 checks that each exists in claims.jsonl)."""
    return {c for r in answer["rows"] for f in r["facts"] for c in f["claims"]}
