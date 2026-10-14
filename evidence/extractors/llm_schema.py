"""Output types and prompts of the single-call LLM extractor, derived from the protocol's evidence type.

The reply type is built from the type's field schema (JSON schema properties as pydantic fields), its links
(a local context id such as "c1" per link) and its span roles (a verbatim quote per role, the first one
required), so a change to the protocol's schema changes the output schema and with it `prompt_sha256` and
the extractor id. Templates are read with LF line ends, so the hash is the same on every checkout.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

from ..contract import ITEM_PREFIX, Item

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
SCALARS: dict[str, Any] = {"string": str, "number": float, "integer": int, "boolean": bool}


def read_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_bytes().decode("utf-8").replace("\r\n", "\n")


def annotation(prop: dict[str, Any]) -> Any:
    """A JSON schema property as a pydantic annotation (string, number, integer, boolean, enum, nullable)."""
    kinds = prop.get("type", "string")
    kinds = list(kinds) if isinstance(kinds, list) else [kinds]
    nullable = "null" in kinds
    kinds = [k for k in kinds if k != "null"]
    if "enum" in prop:
        values = tuple(v for v in prop["enum"] if v is not None)
        base: Any = Literal[values]  # type: ignore[valid-type]
    elif len(kinds) == 1 and kinds[0] in SCALARS:
        base = SCALARS[kinds[0]]
    else:
        raise ValueError(f"the LLM extractor cannot type the schema property {prop}")
    return base | None if nullable else base


def output_model(evidence_type: str, field_schema: dict[str, Any], links: dict[str, str],
                 roles: list[str]) -> type[BaseModel]:
    """{items: [{fields, links?, quotes}]} for one evidence type, every key required (null when unknown)."""
    props = field_schema.get("properties", {})
    fields = create_model("Fields", **{name: (annotation(p), Field(..., description=p.get("description", "")))
                                       for name, p in props.items()})
    parts: dict[str, Any] = {"fields": (fields, ...)}
    if links:
        parts["links"] = (create_model("Links", **{
            name: (str, Field(..., description=f"the id of the {target} from the context list, e.g. "
                                               f"{ITEM_PREFIX[target]}1")) for name, target in links.items()}), ...)
    quotes = {role: (str if n == 0 else str | None,
                     Field(..., description=f"verbatim quote of the {role.replace('_', ' ')}"
                                            + ("" if n == 0 else ", or null if the text does not give one")))
              for n, role in enumerate(roles)}
    parts["quotes"] = (create_model("Quotes", **quotes), ...)
    item = create_model(f"{evidence_type.title().replace('_', '')}Item", **parts)
    return create_model("Extraction", items=(list[item], ...))  # type: ignore[valid-type]


class RetryQuote(BaseModel):
    id: str
    quote: str


class Retry(BaseModel):
    quotes: list[RetryQuote]


def instructions(template: str, evidence_type: str, description: str, field_schema: dict[str, Any],
                 links: dict[str, str], roles: list[str]) -> str:
    link_text = "".join(f"- {name}: the id of the {target} it belongs to, from the context list\n"
                        for name, target in links.items())
    role_text = "\n".join(f"- {role}" + (" (required)" if n == 0 else " (optional)") for n, role in enumerate(roles))
    return template.format(
        evidence_type=evidence_type, description=description.strip(),
        fields=json.dumps(field_schema, ensure_ascii=False, sort_keys=True, indent=1),
        links=("\nEvery item links to items of the context by id:\n" + link_text) if links else "",
        roles=role_text)


def local_ids(context: list[Item]) -> dict[str, Item]:
    """Short ids for the context items in the prompt ("c1", "k2"), in canonical order per type."""
    out: dict[str, Item] = {}
    counts: dict[str, int] = {}
    for item in context:
        counts[item.evidence_type] = counts.get(item.evidence_type, 0) + 1
        out[f"{ITEM_PREFIX[item.evidence_type]}{counts[item.evidence_type]}"] = item
    return out


def user_prompt(document: str, part: int, parts: int, start: int, end: int, chunk: str,
                context: dict[str, Item]) -> str:
    lines = [f"Paper {document}, part {part} of {parts} (characters {start}-{end})."]
    if context:
        lines.append("Context (items found earlier in this paper; link to them by id):")
        for local, item in context.items():
            fields = json.dumps(item.fields, ensure_ascii=False, sort_keys=True)
            lines.append(f"- {local} ({item.evidence_type}): {fields}")
    lines += ["Text:", "<<<", chunk, ">>>"]
    return "\n".join(lines)
