"""The question list (evidence/questions.yaml): the questions the system answers, shared by the web app
(webapp/evquestions.py) and the evaluation.

Per entry: `id` (a plain name), `question` (exactly as its hand-written protocol asks it), `kind` (effect,
inventory, consistency or best; the protocol's kind), `truth` (the parameters the expected answer is computed
with, fixed here and never taken from a user's protocol), `protocol` (the hand-written protocol, a path from the
repository root) and `agentic_protocol` (rag-factuality only). Truth parameters by kind: effect and
consistency take `metric` and `min_effect`; inventory takes `target`; best takes `metric`. A parameter of another
kind is refused. This module checks the file's shape only; the web app also checks that each protocol parses
and asks the entry's question with the entry's kind.
"""
from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence
from typing import Any, Literal, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .protocol import Kind, load as load_protocol
from .rundir import ANSWER_FILE, PROTOCOL_FILE, RUN_FILE, RunDir

DEFAULT = Path(__file__).resolve().parent / "questions.yaml"
NAME = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"   # a directory name, never a flag or a path
TRUTH_FIELDS: dict[str, tuple[str, ...]] = {"effect": ("metric", "min_effect"), "consistency": ("metric", "min_effect"),
                                            "inventory": ("target",), "best": ("metric",)}


class QuestionTruth(BaseModel):
    """What the expected answer is computed with (evaluation): the question metric and the neutral band, or the
    inventory's target type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str | None = Field(None, min_length=1)
    min_effect: float | None = Field(None, gt=0)
    target: Literal["metric", "condition", "dataset"] | None = None


class QuestionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=NAME)
    question: str = Field(min_length=1)
    kind: Kind = "effect"
    truth: QuestionTruth = QuestionTruth()
    protocol: str | None = None
    agentic_protocol: str | None = None

    @field_validator("question")
    @classmethod
    def _stripped(cls, value: str) -> str:
        if value != value.strip() or not value.strip():
            raise ValueError("the question must not be empty or start or end with spaces")
        return value

    @model_validator(mode="after")
    def _truth_fits_kind(self) -> QuestionEntry:
        foreign = [k for k, v in self.truth.model_dump().items() if v is not None and k not in TRUTH_FIELDS[self.kind]]
        if foreign:
            raise ValueError(f"truth.{', truth.'.join(foreign)} does not belong to kind {self.kind!r} "
                             f"(it takes {', '.join(TRUTH_FIELDS[self.kind])})")
        return self


class QuestionsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[QuestionEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> QuestionsFile:
        ids = [q.id for q in self.questions]
        twice = sorted({i for i in ids if ids.count(i) > 1})
        if twice:
            raise ValueError(f"question ids must be unique: {', '.join(twice)}")
        return self


def parse(path: Path) -> QuestionsFile:
    """The file, checked (ValueError naming every problem)."""
    try:
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"{path.name} is not YAML: {str(exc)[:300]}") from exc
    try:
        return QuestionsFile.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"{path.name} does not validate: " + "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())) from exc


def load(path: Path | str = DEFAULT) -> list[QuestionEntry]:
    return parse(Path(path)).questions


Q = TypeVar("Q")   # an entry with `id`, `question` and `kind`: a QuestionEntry, or the web app's Question


class UnknownQuestion(ValueError):
    """No entry, or more than one, matches a run: `run` (its directory name) and `why` (what it asks), so a caller
    can word its own advice; the message itself gives the command line's (`--question-id`)."""

    def __init__(self, run: str, why: str) -> None:
        self.run, self.why = run, why
        super().__init__(f"cannot tell which question the run {run} answers: {why}; "
                         f"give the question id (evaluate score --question-id)")


def answered_by(run_dir: Path, entries: Sequence[Q]) -> Q:
    """The entry a run answers, for scoring it without a question id: the one whose question and kind its
    frozen protocol.yaml asks. A run without one (before the engine froze its protocol, or written by hand) is
    matched by its answer.json (`question_id`, else the question asked), else by the protocol id of its run.json
    (a hand-written protocol is named after its question). UnknownQuestion (a ValueError) when no entry, or
    more than one, matches."""
    rd = RunDir(Path(run_dir))
    if rd.file(PROTOCOL_FILE).is_file():
        protocol = load_protocol(rd.file(PROTOCOL_FILE))
        found = [q for q in entries if q.question == protocol.question and q.kind == protocol.kind]
        why = f"its protocol {protocol.id!r} asks {protocol.question!r} ({protocol.kind})"
    else:
        answer = rd.try_json(ANSWER_FILE)
        answer = answer if isinstance(answer, dict) else {}
        run = rd.try_json(RUN_FILE)
        ref = (run.get("protocol") or {}) if isinstance(run, dict) else {}
        found = ([q for q in entries if q.id == answer.get("question_id")]
                 or [q for q in entries if q.question == answer.get("question")]
                 or [q for q in entries if q.id == ref.get("id")])
        why = "it has no protocol.yaml, and its answer.json and run.json name no question of the list"
    if len(found) != 1:
        raise UnknownQuestion(rd.root.name, why)
    return found[0]


def answers_asked(answers: Sequence[dict[str, Any]], entries: Sequence[Q]) -> Q:
    """The one entry every baseline answer asks (`question_id`, else the question text); ValueError otherwise."""
    asked = set()
    for answer in answers:
        found = ([q for q in entries if q.id == answer.get("question_id")]
                 or [q for q in entries if q.question == answer.get("question")])
        asked.add(found[0].id if len(found) == 1 else None)
    if len(asked) != 1 or None in asked:
        raise ValueError("cannot tell which question the answers answer (none given, an answer of no question of the "
                         "list, or answers of different questions); give the question id (evaluate score "
                         "--question-id)")
    (qid,) = asked
    return next(q for q in entries if q.id == qid)
