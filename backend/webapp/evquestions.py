"""The questions the app offers (domains/rag/questions.yaml, `$EV_QUESTIONS`): the user selects one, never
types it.

    questions:
      - id: <question-id>                        # a plain name (webapp/files.py ID)
        question: Does <treatment> ...?          # the exact question; a hand-written protocol must ask it too
        kind: effect                             # effect | inventory | consistency | best; the protocol's kind
        truth: {metric: <canonical metric>, min_effect: 0.01}   # the expected answer's parameters (evaluation)
        protocol: protocols/<question-id>.yaml         # optional: the hand-written protocol
        agentic_protocol: protocols/<question-id>-agentic.yaml # optional: its agentic variant

Paths are relative to the questions file's folder (the pack folder) and must lie in the protocols directory
(`$EV_PROTOCOLS`), where the run step finds protocols by name; a protocol must parse (evidence/protocol.py)
and ask the entry's question with the entry's kind. The entry model is evidence/questions.py's (shared with
the evaluation). A question without a protocol gets one through the proposal flow (docs/evidence-system.md
Part E). The file is validated when it is read (re-read when it changes); a broken file is a 409 naming the
problem.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import yaml

from evidence.protocol import load as load_protocol
from evidence.questions import QuestionEntry, parse

from .evfiles import subdirs
from .evmodels import Question
from .files import Conflict, NotFound, read_json, signature
from .settings import Settings


# The entry and file models are evidence/questions.py's (shared with the evaluation); this module adds the
# checks against the protocols directory.
Entry = QuestionEntry


def protocol_name(path_text: str, protocols: Path, question: str, base: Path, kind: str | None = None) -> str:
    """The protocol's name (file stem) after checking it lies in `protocols`, parses, asks `question` and (when
    `kind` is given) is of that kind."""
    path = (base / path_text).resolve()
    root = protocols.resolve()
    if path.parent != root or path.suffix != ".yaml":
        raise ValueError(f"{path_text}: a protocol must be a .yaml file directly in {root}")
    if not path.is_file():
        raise ValueError(f"{path_text}: no such file")
    try:
        protocol = load_protocol(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ValueError(f"{path_text} does not validate: {str(exc)[:500]}") from exc
    if protocol.question != question:
        raise ValueError(f"{path_text} asks {protocol.question!r}, not {question!r}")
    if kind is not None and protocol.kind != kind:
        raise ValueError(f"{path_text} is of kind {protocol.kind!r}, not {kind!r}")
    return path.stem


def load(path: Path, protocols: Path, base: Path | None = None) -> list[Question]:
    """The questions of the file, checked (ValueError naming every problem). Protocol paths are relative to
    `base`, by default the file's folder."""
    base = path.parent if base is None else base
    parsed = parse(path, base)   # the pack folder: inventory targets are its types
    out, problems = [], []
    for q in parsed.questions:
        names: dict[str, str | None] = {"protocol": None, "agentic_protocol": None}
        for key in names:
            text = getattr(q, key)
            if text is not None:
                try:
                    names[key] = protocol_name(text, protocols, q.question, base, q.kind)
                except ValueError as exc:
                    problems.append(f"{q.id}.{key}: {exc}")
        out.append(Question(id=q.id, question=q.question, kind=q.kind, **names))
    if problems:
        raise ValueError(f"{path.name} does not validate: " + "; ".join(problems))
    return out


class Questions:
    """The questions file of the settings, re-read when it (or a protocol it names) changes."""

    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self._lock = threading.Lock()
        self._memo: tuple[tuple[Any, ...], list[Question]] | None = None

    def _signature(self) -> tuple[Any, ...]:
        root = self.s.protocols
        return signature(self.s.questions, *(sorted(root.glob("*.yaml")) if root.is_dir() else []))

    def list(self) -> list[Question]:
        sig = self._signature()
        with self._lock:
            if self._memo and self._memo[0] == sig:
                questions = self._memo[1]
            else:
                questions = None
        if questions is None:
            if not self.s.questions.is_file():
                return []
            try:
                questions = load(self.s.questions, self.s.protocols)
            except ValueError as exc:
                raise Conflict(str(exc)) from exc
            with self._lock:
                self._memo = (sig, questions)
        return [q.model_copy(update={"proposals": self._proposals(q.question)}) for q in questions]

    def _proposals(self, question: str) -> list[str]:
        root = self.s.proposals_dir
        if root is None or not root.is_dir():
            return []
        return [p.name for p in subdirs(root) if (read_json(p / "frame.json") or {}).get("question") == question]

    def get(self, qid: str) -> Question:
        found = next((q for q in self.list() if q.id == qid), None)
        if found is None:
            raise NotFound(f"no such question: {qid!r}")
        return found
