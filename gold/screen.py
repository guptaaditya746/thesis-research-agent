"""Screening (M3, plan "Gold": screening.jsonl): is a chunk relevant to the question's concept?

Every chunk of every paper is screened (gold/chunks.py), one call per chunk, with the prompt
gold/prompts/screen-v1.md. The reply is {relevant, findings}; the prompt asks the model to answer
"relevant" when unsure, because a wrong "not relevant" drops a part's facts without trace (the
screening false-negative check in review samples papers marked not relevant to bound that).

A paper's status comes from its chunks:
- `relevant`: at least one chunk is relevant (its relevant chunks go to extraction);
- `error`: no chunk is relevant and at least one call failed, or the paper could not be read (hash
  mismatch); failures are not cached, so the next build retries exactly those chunks;
- `not_relevant`: every chunk was screened and none is relevant;
- `no_text`: the manifest records a failed conversion (the scanned p38), or the file is empty.
A relevant paper can still have failed chunks: `chunks_error` lists them, and they are retried too.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from .calls import Caller, PromptFile, load_prompt
from .chunks import Chunk

TEXT_START = "----- text of this part (verbatim) -----"
TEXT_END = "----- end of text -----"
MAX_TOKENS = 1024


class Screening(BaseModel):
    relevant: bool
    findings: list[str]


PROMPT: PromptFile = load_prompt("screen-v1.md", Screening)


@dataclass(frozen=True)
class Task:
    """What every call of one build is about: the question and its picked concept."""
    qid: str
    question: str | None
    concept: dict[str, Any]


def part_prompt(task: Task, chunk: Chunk, parts: int, text: str, *, extra: str = "") -> str:
    """The user prompt for one chunk: question, concept, which part of which paper, then its text verbatim
    between marker lines (not JSON-escaped, so a quote can be copied from it as it stands in the file)."""
    where = f"part {chunk.chunk + 1} of {parts}"
    if chunk.heading:
        where += f', starting in the section "{chunk.heading}"'
    question = task.question or "(not given; the concept says what is asked)"
    return (f"Question: {question}\n\n"
            f"Concept:\n{json.dumps(task.concept, ensure_ascii=False, indent=1)}\n\n"
            f"Paper: {chunk.paper_id} (file {chunk.paper_id}.md), {where}.\n\n"
            + (f"{extra.strip()}\n\n" if extra.strip() else "")
            + f"{TEXT_START}\n{text}\n{TEXT_END}\n")


async def screen_chunk(caller: Caller, task: Task, chunk: Chunk, parts: int, text: str) -> dict[str, Any]:
    """{chunk, status: relevant | not_relevant, findings, model, served_model, prompt_sha256, cached}.
    A failed call raises calls.CallError."""
    result = await caller.call("screen", PROMPT, Screening, part_prompt(task, chunk, parts, text),
                               max_tokens=MAX_TOKENS)
    relevant = result.output.relevant
    findings = [f.strip() for f in result.output.findings if f.strip()] if relevant else []
    return {"chunk": chunk.chunk, "status": "relevant" if relevant else "not_relevant", "findings": findings,
            **{k: result.meta[k] for k in ("model", "served_model", "prompt_sha256", "cached")}}


def _joined(values: list[Any]) -> str | None:
    found = sorted({str(v) for v in values if v})
    return ",".join(found) if found else None


def paper_record(paper_id: str, file: str, chunk_results: list[dict[str, Any]], *,
                 error: str | None = None, no_text: str | None = None) -> dict[str, Any]:
    """One screening.jsonl line from a paper's chunk results (see the module docstring for the status)."""
    relevant = [r["chunk"] for r in chunk_results if r["status"] == "relevant"]
    failed = [r["chunk"] for r in chunk_results if r["status"] == "error"]
    if no_text is not None:
        status = "no_text"
    elif error is not None:
        status = "error"
    elif relevant:
        status = "relevant"
    elif failed:
        status = "error"
    else:
        status = "not_relevant"
    record = {
        "paper_id": paper_id, "file": file, "status": status, "chunks": len(chunk_results),
        "chunks_relevant": relevant, "chunks_error": failed,
        "findings": [f for r in chunk_results for f in r.get("findings", [])],
        "model": _joined([r.get("model") for r in chunk_results]),
        "served_model": _joined([r.get("served_model") for r in chunk_results]),
        "prompt_sha256": PROMPT.sha256,
    }
    reasons = [f"chunk {r['chunk']}: {r['error']}" for r in chunk_results if r.get("error")]
    if error or reasons:
        record["error"] = error or "; ".join(reasons)[:1000]
    if no_text is not None:
        record["reason"] = no_text
    return record
