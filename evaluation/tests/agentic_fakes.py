"""Shared pieces for the agentic extractor tests: a RunContext, field schemas, a task, recorded runs."""
from __future__ import annotations

from typing import Any

from agent.anchor import Index
from evidence.contract import DocumentRef, ExtractionTask, Item, ProtocolRef, Scope

from . import fixtures as fx

# As evidence/protocols/rag-factuality.yaml (ev/engine) has them: a measurement's condition and metric are links.
MEASUREMENT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["value", "dataset"],
                      "properties": {"value": {"type": "number", "description": "as a fraction for accuracies and rates"},
                                     "dataset": {"type": ["string", "null"], "description": "the dataset, or null"}}}
LINKS = {"condition": "condition", "metric": "metric"}
CONDITION_SCHEMA = {"type": "object", "required": ["label", "role"],
                    "properties": {"label": {"type": "string"}, "role": {"enum": ["rag", "baseline", "other"]}}}


class Ctx:
    """The engine's RunContext for one task, in memory."""

    def __init__(self, text: str, context: list[Item], schema: dict[str, Any], recorder: Any = None) -> None:
        self._text, self._context, self._schema, self._recorder = text, context, schema, recorder

    def llm(self) -> Any:  # the engine's Recorder (evidence/recording.py) has a `records` list
        return self._recorder

    def text(self) -> str:
        return self._text

    def index(self) -> Index:
        return Index(self._text)

    def context_items(self) -> list[Item]:
        return list(self._context)

    def field_schema(self) -> dict[str, Any]:
        return self._schema


def context() -> list[Item]:
    items = fx.perfect_items()
    return [items[k] for k in ("S001.c1", "S001.c2", "S001.c3", "S001.k1", "S001.k2")]


def task(kind: str = "measurement", scope: Scope | None = None) -> ExtractionTask:
    return ExtractionTask(protocol=ProtocolRef(id="rag-factuality", sha256="0" * 64), evidence_type=kind,
                          field_schema_sha256="1" * 64,
                          document=DocumentRef(id="S001", file="papers/S001.md", sha256=Index(fx.S001).sha256),
                          scope=scope or Scope(), context=tuple(i.item_id for i in context()))


def claim(n: int | None, p: str, o: Any, quote: str, step: int = 2, reason: str | None = None) -> dict[str, Any]:
    return {"step_id": step, "status": "accepted" if n else "rejected", "claim_id": f"claim-{n:06d}" if n else None,
            "reason": reason, "s": "r", "p": p, "o": o, "quote": quote, "file": "S001.md", "anchor": None}


def row(rid: str, cells: dict[str, Any], claims: list[int]) -> dict[str, Any]:
    return {"id": rid, "cells": cells, "facts": [{"id": f"f{rid}", "s": rid, "p": "row", "o": "x", "origin": "research",
                                                  "claims": [f"claim-{n:06d}" for n in claims]}]}


def recorded_run() -> dict[str, Any]:
    """What runner.collect returns for a run that read the results table and claimed four quotes."""
    ids = {k: i.item_id for k, i in fx.perfect_items().items()}
    c1, c2, k1 = ids["S001.c1"], ids["S001.c2"], ids["S001.k1"]
    table = fx.S001[fx.S001.index("| System"):fx.S001.index("Retrieval clearly")]
    return {
        "run_id": "agentic-test", "outcome": {"exit_status": "submitted", "answer_from": "final", "steps": 4},
        "claims": [claim(1, "value", 0.7, "0.70"), claim(2, "condition", c2, "retrieval-augmented variant (R)"),
                   claim(None, "value", 0.71, "R reached 71%", reason="not_found"),
                   claim(3, "value", 0.62, "62%"), claim(4, "value", 0.62, "0.62"),
                   claim(None, "value", 0.5, "x", reason="bad_field:o")],
        "commands": [{"step_id": 1, "command": "sed -n '/| System/,/R-noRerank/p' \"$CORPUS/S001.md\"", "output": table,
                      "output_sha256": "0" * 64, "exit_code": 0}],
        "model_calls": [{"task_id": "task-000001", "step_id": 1}, {"task_id": "task-000004", "step_id": 2}],
        "answer": {"rows": [
            row("r1", {"condition": c2, "metric": k1, "value": 0.7, "dataset": None}, [1, 2]),
            row("r2", {"condition": "closed-book model", "metric": k1, "value": 0.62, "dataset": None}, [3]),  # label
            row("r3", {"condition": c1, "metric": k1, "value": 0.62, "dataset": None}, [4]),     # same item as r2
            row("r4", {"condition": "c-0000000000000000", "metric": k1, "value": 0.66, "dataset": None}, [1]),  # dangling
            row("r5", {"condition": c1, "metric": k1, "value": None, "dataset": None}, [3]),     # schema: no value
            row("r6", {"condition": c1, "metric": k1, "value": 0.5, "dataset": None}, []),       # no claim
        ], "notes": ""},
        "trajectory": {"messages": []}, "head": "f" * 64,
    }


class FakeRunner:
    """AgentRunner returning a recorded run (or raising), and keeping the jobs it was given."""

    def __init__(self, record: dict[str, Any] | Exception) -> None:
        self.record = record
        self.jobs: list[Any] = []

    def run(self, job: Any) -> dict[str, Any]:
        self.jobs.append(job)
        if isinstance(self.record, Exception):
            raise self.record
        return dict(self.record, run_id=job.run_id)
