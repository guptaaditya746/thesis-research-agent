"""Versioned prompts (row 1.10): agent/prompts/system-<version>[-baseline].txt and task-<version>.txt.

The system prompt for `claim_on` is system-v1.txt; the baseline (`claim_off`, row 2.4) is
system-v1-baseline.txt, which is v1 minus its claim block and nothing else: system-v1.diff is
the checked-in diff and test_prompts checks that it still holds. Files are hashed as stored (LF,
.gitattributes); `{{steps}}` and `{{tokens}}` are filled in by mini-swe-agent's template step.
"""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import sha256_hex

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
CONDITIONS = ("claim_on", "claim_off")
CLAIM_BLOCK_START = "Recording facts with claim:"


def _read(name: str) -> tuple[str, str]:
    data = (PROMPT_DIR / name).read_bytes()
    return data.decode("utf-8"), sha256_hex(data)


@dataclass(frozen=True)
class Prompt:
    version: str
    system: str
    task: str
    system_name: str
    files: dict[str, str]  # file name -> sha256

    @property
    def sha256(self) -> str:
        return self.files[self.system_name]


def load(version: str, condition: str) -> Prompt:
    if condition not in CONDITIONS:
        raise ValueError(f"condition must be one of {CONDITIONS}")
    system_name = f"system-{version}.txt" if condition == "claim_on" else f"system-{version}-baseline.txt"
    task_name = f"task-{version}.txt"
    system, system_sha = _read(system_name)
    task, task_sha = _read(task_name)
    return Prompt(version, system, task, system_name, {system_name: system_sha, task_name: task_sha})


def baseline_from(system: str) -> str:
    """The prompt minus its claim block: from CLAIM_BLOCK_START to the next blank line, inclusive."""
    lines = system.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith(CLAIM_BLOCK_START))
    end = next(i for i in range(start, len(lines)) if not lines[i].strip())
    return "".join(lines[:start] + lines[end + 1:])


def prompt_diff(system: str, baseline: str, version: str = "v1") -> str:
    """Unified diff from the claim_on prompt to the baseline, as checked in as system-<version>.diff."""
    return "".join(difflib.unified_diff(system.splitlines(keepends=True), baseline.splitlines(keepends=True),
                                        f"system-{version}.txt", f"system-{version}-baseline.txt"))


def _placeholder(type_name: str) -> Any:
    if type_name.startswith("list<"):
        return [f"<{type_name[5:-1]}>"]
    return f"<{type_name}>"


def row_example(concept: dict[str, Any]) -> dict[str, Any]:
    """One answer row with typed placeholders, for the task message."""
    shape = concept["answer_shape"]
    fact = {"id": "f1", "s": "<subject>", "p": "<predicate>", "o": "<object>"}
    if shape["kind"] == "table":
        return {"id": "r1", "cells": {c["name"]: _placeholder(c["type"]) for c in shape["columns"]},
                "facts": [fact]}
    edge = shape["edges"][0]
    row = {"id": "r1", "source": f"<{edge['source']}>", "source_type": edge["source"],
           "predicate": edge["predicate"], "target": f"<{edge['target']}>", "target_type": edge["target"]}
    if edge.get("attributes"):
        row["attributes"] = {a["name"]: _placeholder(a["type"]) for a in edge["attributes"]}
    row["facts"] = [fact]
    return row


def task_vars(concept: dict[str, Any]) -> dict[str, str]:
    """Template values for task-<version>.txt."""
    shape = concept["answer_shape"]
    kind = shape["kind"]
    if kind == "graph":
        edges = ", ".join(f"{e['source']} -{e['predicate']}-> {e['target']}" for e in shape["edges"])
        kind = f"graph; each row is one edge of type {edges}"
    return {"concept_json": json.dumps(concept, ensure_ascii=False, indent=2), "shape_kind": kind,
            "row_example": json.dumps(row_example(concept), ensure_ascii=False)}
