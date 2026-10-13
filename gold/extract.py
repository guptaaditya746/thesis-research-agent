"""Extraction (M3, plan "Gold": candidates.jsonl): answer rows with one checked quote per fact.

Per relevant chunk one call (gold/prompts/extract-v1.md) whose output type is derived from the
concept's answer_shape (`output_model`): a table row is {cells: {column: value}, facts}, a graph row
one variant per edge type {source, source_type, predicate, target, target_type, attributes, facts},
and every fact {s, p, o, quote}. Decoding under that JSON schema (vLLM structured outputs) keeps the
cells typed as agent.concept.answer_schema_for types them, so the rows can become a draft key.

Every quote is checked as the broker checks a claim: `check_quote` follows Broker.claim step for step
(the request parsed as the broker parses one, the file name resolved, the file's manifest hash
checked, the quote anchored with agent/anchor.find in the whole file, no context hints). A quote
rejected for a reason a new quote can fix (QUOTE_REASONS) gets one retry: one call per chunk
(gold/prompts/extract-retry-v1.md) lists the rejected facts with the broker's reason, explained in
the words the agent's prompt uses, and the new quotes are checked again. What still fails keeps its
reason as `anchor_status` with `anchor` null: it stays in D, flagged, and never reaches the key.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Literal, Union

from pydantic import BaseModel, Field, create_model

from agent.anchor import AnchorError, find
from agent.broker import Broker, Rejected
from agent.canonical import canonical_bytes

from .calls import Caller, CallError, PromptFile, load_prompt
from .chunks import Chunk, GoldCorpus
from .screen import Task, part_prompt

MAX_TOKENS = 8192
RETRY_MAX_TOKENS = 2048
QUOTE_REASONS = ("not_found", "ambiguous", "partial_number", "empty_quote", "bad_field:quote")
EDGE_FIELDS = ("source", "source_type", "predicate", "target", "target_type", "attributes")
SCALARS: dict[str, type] = {"integer": int, "number": float, "boolean": bool}


class Fact(BaseModel):
    s: str
    p: str
    o: str | int | float | bool
    quote: str


class RetryQuote(BaseModel):
    id: str
    quote: str


class Retry(BaseModel):
    quotes: list[RetryQuote]


RETRY_PROMPT: PromptFile = load_prompt("extract-retry-v1.md", Retry)


def _annotation(type_name: str) -> Any:
    """A concept value type as a pydantic annotation; scalars may be null, list items may not."""
    if type_name.startswith("list<"):
        return list[SCALARS.get(type_name[5:-1], str)]  # type: ignore[misc]
    return SCALARS.get(type_name, str) | None


def _fields(columns: list[dict[str, str]]) -> dict[str, Any]:
    return {c["name"]: (_annotation(c["type"]), Field(..., description=c["type"])) for c in columns}


def output_model(concept: dict[str, Any]) -> type[BaseModel]:
    """{rows: [...]} in the concept's answer shape, every field required (null or [] when unknown)."""
    shape = concept["answer_shape"]
    if shape["kind"] == "table":
        cells = create_model("Cells", **_fields(shape["columns"]))
        row: Any = create_model("Row", cells=(cells, ...), facts=(list[Fact], ...))
    else:
        variants = []
        for n, edge in enumerate(shape["edges"], 1):
            attributes = create_model(f"Attributes{n}", **_fields(edge.get("attributes", [])))
            variants.append(create_model(
                f"Edge{n}", source=(str, Field(..., description=edge["source"])),
                source_type=(Literal[edge["source"]], ...), predicate=(Literal[edge["predicate"]], ...),
                target=(str, Field(..., description=edge["target"])), target_type=(Literal[edge["target"]], ...),
                attributes=(attributes, ...), facts=(list[Fact], ...)))
        row = variants[0] if len(variants) == 1 else Union[tuple(variants)]  # noqa: UP007 - a runtime union
    return create_model("Extraction", rows=(list[row], ...))


def extract_prompt(concept: dict[str, Any]) -> tuple[PromptFile, type[BaseModel]]:
    model = output_model(concept)
    return load_prompt("extract-v1.md", model), model


def _clean(value: Any) -> Any:
    """Strip strings; an empty string is null and an empty list item is dropped (the answer schema
    wants non-empty strings)."""
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        items = [_clean(v) for v in value]
        return [v for v in items if v is not None]
    return value


def row_fields(concept: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """The answer-row fields of an extracted row (no facts): table cells, or the edge fields."""
    if concept["answer_shape"]["kind"] == "table":
        return {name: _clean(value) for name, value in row["cells"].items()}
    out = {k: _clean(row[k]) for k in EDGE_FIELDS if k != "attributes"}
    out["attributes"] = {name: _clean(value) for name, value in (row.get("attributes") or {}).items()}
    return out


def check_quote(corpus: GoldCorpus, *, s: Any, p: Any, o: Any, file: str, quote: Any) -> tuple[dict | None, str]:
    """The broker's claim check (Broker.claim) without a run: (selector json, "ok") or (None, reason)."""
    try:
        request = Broker._parse(canonical_bytes({"s": s, "p": p, "o": o, "file": file, "quote": quote}), {})
        name = corpus.name(request["file"])
        selector = find(corpus.index(name), request["quote"], file=name)
    except (Rejected, AnchorError) as exc:
        return None, exc.reason
    except ValueError:  # not serialisable (cannot come from decoded JSON), rejected as the broker would
        return None, "malformed_json"
    return selector.json(), "ok"


def _check(corpus: GoldCorpus, chunk: Chunk, file: str, items: list[dict[str, Any]]) -> None:
    for item in items:
        anchor, status = check_quote(corpus, s=item["s"], p=item["p"], o=item["o"], file=file, quote=item["quote"])
        item["anchor"], item["anchor_status"] = anchor, status
        item["anchor_in_chunk"] = (chunk.start <= anchor["start"] and anchor["end"] <= chunk.end) if anchor else None


async def _retry(caller: Caller, task: Task, chunk: Chunk, parts: int, text: str, corpus: GoldCorpus, file: str,
                 failed: list[dict[str, Any]]) -> None:
    """One call for every rejected quote of the chunk, then the check again (see the module docstring)."""
    listing = [{"id": f"q{n}", "s": it["s"], "p": it["p"], "o": it["o"], "quote": it["quote"],
                "reason": it["anchor_status"]} for n, it in enumerate(failed, 1)]
    extra = "Rejected quotes:\n" + json.dumps(listing, ensure_ascii=False, indent=1)
    for item in failed:
        item.update(attempts=2, first_quote=item["quote"], first_reason=item["anchor_status"])
    try:
        result = await caller.call("retry", RETRY_PROMPT, Retry, part_prompt(task, chunk, parts, text, extra=extra),
                                   max_tokens=RETRY_MAX_TOKENS)
    except CallError as exc:
        for item in failed:
            item["retry"] = {"error": exc.reason}
        return
    quotes = {q.id: q.quote for q in result.output.quotes}
    meta = {k: result.meta[k] for k in ("model", "served_model", "prompt_sha256")}
    again = []
    for n, item in enumerate(failed, 1):
        item["retry"] = dict(meta)
        if f"q{n}" in quotes:
            item["quote"] = quotes[f"q{n}"]
            again.append(item)
        else:
            item["retry"]["missing"] = True  # the model gave no new quote: the first reason stands
    await asyncio.to_thread(_check, corpus, chunk, file, again)


async def extract_chunk(caller: Caller, task: Task, prompt: PromptFile, output_type: type[BaseModel], chunk: Chunk,
                        parts: int, text: str, corpus: GoldCorpus) -> list[dict[str, Any]]:
    """The candidates of one chunk (without ids), every quote checked; a failed call raises CallError."""
    result = await caller.call("extract", prompt, output_type, part_prompt(task, chunk, parts, text),
                               max_tokens=MAX_TOKENS)
    file = corpus.file(chunk.paper_id)
    items: list[dict[str, Any]] = []
    for r, row in enumerate(result.output.rows):  # type: ignore[attr-defined]
        data = row.model_dump(mode="json")
        fields = row_fields(task.concept, data)
        for f, fact in enumerate(data["facts"]):
            o = fact["o"].strip() if isinstance(fact["o"], str) else fact["o"]
            items.append({"row": fields, "s": fact["s"].strip(), "p": fact["p"].strip(), "o": o,
                          "quote": fact["quote"], "extracted_row": r, "fact": f, "attempts": 1})
    await asyncio.to_thread(_check, corpus, chunk, file, items)
    failed = [it for it in items if it["anchor_status"] in QUOTE_REASONS]
    if failed:
        await _retry(caller, task, chunk, parts, text, corpus, file, failed)
    meta = {"model": result.meta["model"], "served_model": result.meta["served_model"],
            "prompt_sha256": result.meta["prompt_sha256"]}
    return [{"qid": task.qid, "paper_id": chunk.paper_id, "file": file, "chunk": chunk.chunk,
             "heading": chunk.heading, **item, **meta} for item in items]
