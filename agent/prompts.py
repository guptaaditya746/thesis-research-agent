"""Versioned prompts (row 1.10): agent/prompts/system-<version>[-baseline].txt and task-<version>.txt.

The system prompt for `claim_on` is system-<version>.txt; the baseline (`claim_off`, row 2.4) is
system-<version>-baseline.txt, which is that prompt minus its claim block and nothing else:
system-<version>.diff is the checked-in diff and test_prompts checks that it still holds. Files
are hashed as stored (LF, .gitattributes); `{{steps}}`, `{{tokens}}` and the other template
values (agent/loop.py, ResearchAgent.extra_template_vars) are filled in by mini-swe-agent's
template step.

Versions:
- v1 (1.10): the M1-real runs (tests/M1-real); kept byte for byte so they can be reproduced, and
  run with the loop settings of that time (loop.LEGACY_V1: no masking, notices, draft or guided
  conclusion, the old wording) and, unless a budget is given, their budget (loop.budget_for:
  150 steps / 400,000 tokens): `agent run --prompt-version v1` is the M1-real run.
- v2 (1.13, 1.15): the corpus's real file names (`p12.md` and ACL Anthology ids such as
  `2025-acl-long-892.md`; the manifest has no titles), claim a fact in the command that finds it,
  keep ./answer-draft.json up to date, finish research by about 75% of the budget, what the
  budget notices and output masking mean, and a conclude reply that is the bare answer object.
The attach step (agent/attach.py) has its own attach-<version>.txt, and uses the run's version:
attach-v2 has v2's corpus paragraph and claim rules verbatim (test_attach checks both versions).

Subagents (row 2.12, agent/spawn.py): with `agent run --spawn on` the system prompt gets the
spawn block spawn-<version>.txt (spawn-<version>-baseline.txt for claim_off: the block minus
its claim lines), inserted before the draft-answer paragraph; v2 has one, v1 none (the M1-real
runs had no spawn). A subagent has its own prompts sub-<version>.txt (-baseline.txt without
the claim block, as for the main prompt) and sub-task-<version>.txt (load_sub).
"""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonio import sha256_hex

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


SPAWN_BEFORE = "Draft answer:"  # the spawn block goes before this paragraph of the system prompt


def _for(condition: str, name: str) -> str:
    """`name`.txt for claim_on, `name`-baseline.txt for claim_off."""
    if condition not in CONDITIONS:
        raise ValueError(f"condition must be one of {CONDITIONS}")
    return f"{name}.txt" if condition == "claim_on" else f"{name}-baseline.txt"


def load(version: str, condition: str, spawn: bool = False) -> Prompt:
    """The run's prompts; with `spawn` the system prompt has the spawn block (row 2.12), hashed in `files` too."""
    system_name = _for(condition, f"system-{version}")
    task_name = f"task-{version}.txt"
    system, system_sha = _read(system_name)
    task, task_sha = _read(task_name)
    files = {system_name: system_sha, task_name: task_sha}
    if spawn:
        block_name = _for(condition, f"spawn-{version}")
        if not (PROMPT_DIR / block_name).is_file():
            raise ValueError(f"prompt {version} has no spawn block ({block_name}); spawn needs prompt v2 or later")
        block, files[block_name] = _read(block_name)
        system = with_block(system, block)
    return Prompt(version, system, task, system_name, files)


def with_block(system: str, block: str) -> str:
    """`block` (ending in a blank line) inserted before the paragraph that starts with SPAWN_BEFORE."""
    at = system.find("\n" + SPAWN_BEFORE)
    if at < 0:
        raise ValueError(f"the system prompt has no {SPAWN_BEFORE!r} paragraph to put the spawn block before")
    return system[:at + 1] + block.rstrip("\n") + "\n\n" + system[at + 1:]


def load_sub(version: str, condition: str) -> Prompt:
    """A subagent's prompts (row 2.12): sub-<version>[-baseline].txt and sub-task-<version>.txt."""
    system_name = _for(condition, f"sub-{version}")
    task_name = f"sub-task-{version}.txt"
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
