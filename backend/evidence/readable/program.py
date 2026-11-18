"""The readable program of one run: one standard-library Python file that rebuilds the run's answer from the facts it
used (no papers, no AI) and checks it against the answer the run recorded.

The two recorded hashes come from the RECORDED answer, never from the rebuilt one, so a wrong rebuild fails its check
instead of agreeing with itself."""
from __future__ import annotations

import ast
import json
import pprint
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..kindtext import RULE_TEXT
from ..rundir import SEAL_FILE, RunDir
from .inputs import ProgramInputs, inputs_of
from .rules.common import text_sha256, values_sha256
from .runview import RunAnswer, answer_text, checked_view, read_run

__all__ = ["RULE_FILES", "SECTION_NONE", "SECTION_UNKNOWN", "about_of", "fact_comment", "program_of_run",
           "program_text", "section_at"]

RULE_FILES: dict[str, tuple[str, ...]] = {"effect": ("common", "effect"), "consistency": ("common", "effect"),
                                          "best": ("common", "best"), "inventory": ("common", "inventory"),
                                          "written": ("common", "written")}
SECTION_NONE = "before the first heading"
SECTION_UNKNOWN = "unknown (the papers were not at hand when this file was made)"
RULES_DIR = Path(__file__).resolve().parent / "rules"
RULES_LINE = "# --- rules ---"
DROP_MARK = "# program: drop"
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
MODEL_TEXT_NOTE = "# MODEL_TEXT: written by a model from the results above, not rebuilt by this file."

HEADER = '''"""The answer of one recorded run, rebuilt from the facts it used.

Run it with Python 3.9 or later: python this_file.py (add --json for the rebuilt values). It needs no papers, no AI
and no other file, only the Python standard library. It prints the answer, then checks it against the answer the run
recorded.

How the answer is made: {rule_text}

What this file shows: the run is replayable and checkable. The same recorded facts always rebuild the same answer,
and every fact below points to exact text in a paper: the comment above it names the paper, the section and the
quote. Which values each paper compared is recorded below (PAPERS), not chosen again by this file; from those values
on, every step is rebuilt here. The tools are fixed functions; the agent's choice of tool calls is not fixed, but
every call is recorded. This file does not show that the same question always gives the same answer, nor that
pulling the facts out of the papers is deterministic.

{written}Part 1 says what was asked, part 2 holds the facts the rules used, part 3 is a copy of the rules, part 4 runs them.
"""'''
WRITTEN_PARAGRAPH = ("The answer's sentences were written by a model from the facts below; they are pasted here "
                     "(MODEL_TEXT), not rebuilt by this file. This file re-runs the code checks on them, chooses the "
                     "reply the run accepted and adds the paper ids.\n\n")


def section_at(text: str | None, start: int) -> str:
    """The words of the last Markdown heading that starts before `start`; SECTION_NONE when there is none and
    SECTION_UNKNOWN when the text is not at hand."""
    if text is None:
        return SECTION_UNKNOWN
    found = [m for m in HEADING.finditer(text) if m.start() < start]
    return " ".join(found[-1].group(1).split()) if found else SECTION_NONE


def fact_comment(key: str, fact: dict[str, Any], spans: list[dict[str, Any]],
                 texts: Mapping[str, str] | None) -> list[str]:
    """The comment lines above a fact: its paper and section, then each quote on one line."""
    paper = fact["paper"]
    text = texts.get(paper) if texts is not None else None
    first = spans[0].get("start") if spans else None
    section = section_at(text, first if isinstance(first, int) else 0)
    lines = [f'# {key}: paper {paper}, section "{section}"']
    for span in spans:
        lines.append(f"#   {span.get('role')}: {json.dumps(span.get('exact', ''), ensure_ascii=False)}")
    return lines


def _data(value: Any) -> str:
    return pprint.pformat(value, width=110, sort_dicts=False)


def _rule_file(name: str) -> tuple[list[str], list[str]]:
    """The import lines and the body of one rule file, its drop-marked lines removed."""
    lines = (RULES_DIR / f"{name}.py").read_text(encoding="utf-8").split("\n")
    at = lines.index(RULES_LINE)
    kept = [line for line in lines[:at] if not line.rstrip().endswith(DROP_MARK)]
    head = "\n".join(kept)
    imports = [ast.get_source_segment(head, node) or "" for node in ast.parse(head).body
               if isinstance(node, (ast.Import, ast.ImportFrom))]
    body = [line for line in lines[at + 1:] if not line.rstrip().endswith(DROP_MARK)]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return imports, body


def program_text(inputs: ProgramInputs, about: dict[str, Any], texts: Mapping[str, str] | None,
                 recorded_text: str, recorded_view: dict[str, Any]) -> str:
    """The program, in its four parts (see the module's tests for the exact order)."""
    imports: set[str] = set()
    bodies: list[str] = []
    for name in RULE_FILES[inputs.kind]:
        found, body = _rule_file(name)
        imports |= {line for line in found if not line.startswith("from __future__")}
        bodies.append("\n".join(body))
    written = inputs.kind == "written"
    out = ["#!/usr/bin/env python3",
           HEADER.format(rule_text=RULE_TEXT[inputs.kind], written=WRITTEN_PARAGRAPH if written else ""),
           "from __future__ import annotations", *sorted(imports), "",
           "# --- Part 1: what was asked ---",
           "# Question: " + " ".join(inputs.question.splitlines()),
           f"KIND = {_data(inputs.kind)}", f"THE_QUESTION = {_data(inputs.question)}",
           f"THE_RUN = {_data(about)}", f"NAMES_OF_THINGS = {_data(inputs.names)}",
           f"RULE_SETTINGS = {_data(inputs.settings)}", "",
           "# --- Part 2: the facts used ---", "FACTS_USED = {"]
    for key, fact in inputs.facts.items():
        out.extend(fact_comment(key, fact, inputs.spans.get(key, []), texts))
        out.append(f"{json.dumps(key)}: " + _data(fact).replace("\n", "\n    ") + ",")
    out += ["}", f"PAPERS = {_data(inputs.papers)}"]
    if written:
        out.append(MODEL_TEXT_NOTE)
    out += [f"MODEL_TEXT = {_data(inputs.model_text)}",
            f"RECORDED_ANSWER_SHA256 = {_data(text_sha256(recorded_text))}",
            f"RECORDED_VALUES_SHA256 = {_data(values_sha256(recorded_view))}", "",
            "# --- Part 3: the rules (a copy, so this file runs on its own) ---", "\n\n\n".join(bodies), "",
            "# --- Part 4: run it ---", 'if __name__ == "__main__":', "    sys.exit(main(sys.argv[1:], globals()))", ""]
    return "\n".join(out)


def about_of(ra: RunAnswer) -> dict[str, Any]:
    """Which run the program is of (no path of this machine)."""
    record = ra.record
    name = "written-answer.json" if ra.kind == "written" else "answer.json"
    seal = RunDir(ra.run).try_json(SEAL_FILE)
    return {"run": record.get("run_id"), "corpus": record.get("corpus_id"),
            "protocol_sha256": (record.get("protocol") or {}).get("sha256"), "answer_file": name,
            "answer_file_sha256": ra.outputs.get(name),
            "code_commit": seal.get("code_commit") if isinstance(seal, dict) else None}


def program_of_run(run: Path | str, corpus: Path | str | None = None) -> str:
    """The run's readable program; raises NotRebuilt when the run cannot be rebuilt."""
    ra = read_run(run, corpus)
    return program_text(inputs_of(ra), about_of(ra), ra.texts, answer_text(ra), checked_view(ra))
