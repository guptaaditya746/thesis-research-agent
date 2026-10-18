"""The questions the app offers (evidence/questions.yaml, `$EV_QUESTIONS`): the user selects one, never types it.

    questions:
      - id: rag-factuality                       # a plain name (webapp/files.py ID)
        question: Does retrieval-augmented ...?  # the exact question; a hand-written protocol must ask it too
        protocol: evidence/protocols/rag-factuality.yaml           # optional: the hand-written protocol
        agentic_protocol: evidence/protocols/rag-factuality-agentic.yaml   # optional: its agentic variant
        vocab: rag-factuality                    # optional: the proposal flow's vocabulary (evidence/vocab/)

Paths are relative to the repository and must lie in the protocols directory (`$EV_PROTOCOLS`), where the run
step finds protocols by name; a protocol must parse (evidence/protocol.py) and ask the entry's question. A
question without a protocol gets one through the proposal flow (docs/evidence-system.md Part E). The file is
validated when it is read (re-read when it changes); a broken file is a 409 naming the problem.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from evidence.protocol import load as load_protocol

from .evfiles import subdirs
from .evmodels import NAME, Question
from .files import Conflict, NotFound, read_json, signature
from .settings import REPO, Settings


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=NAME)
    question: str = Field(min_length=1)
    protocol: str | None = None
    agentic_protocol: str | None = None
    vocab: str | None = Field(None, pattern=NAME)

    @field_validator("question")
    @classmethod
    def _stripped(cls, value: str) -> str:
        if value != value.strip() or not value.strip():
            raise ValueError("the question must not be empty or start or end with spaces")
        return value


class QuestionsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[Entry] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> QuestionsFile:
        ids = [q.id for q in self.questions]
        twice = sorted({i for i in ids if ids.count(i) > 1})
        if twice:
            raise ValueError(f"question ids must be unique: {', '.join(twice)}")
        return self


def protocol_name(path_text: str, protocols: Path, question: str, base: Path = REPO) -> str:
    """The protocol's name (file stem) after checking it lies in `protocols`, parses and asks `question`."""
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
    return path.stem


def load(path: Path, protocols: Path, base: Path = REPO) -> list[Question]:
    """The questions of the file, checked (ValueError naming every problem)."""
    try:
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"{path.name} is not YAML: {str(exc)[:300]}") from exc
    try:
        parsed = QuestionsFile.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"{path.name} does not validate: " + "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())) from exc
    out, problems = [], []
    for q in parsed.questions:
        names: dict[str, str | None] = {"protocol": None, "agentic_protocol": None}
        for key in names:
            text = getattr(q, key)
            if text is not None:
                try:
                    names[key] = protocol_name(text, protocols, q.question, base)
                except ValueError as exc:
                    problems.append(f"{q.id}.{key}: {exc}")
        out.append(Question(id=q.id, question=q.question, vocab=q.vocab, **names))
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
