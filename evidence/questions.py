"""The question list (evidence/questions.yaml): the questions the system answers, shared by the web app
(webapp/evquestions.py) and the evaluation.

Per entry: `id` (a plain name), `question` (exactly as its hand-written protocol asks it), `kind` (effect,
inventory, consistency or best; the protocol's kind), `truth` (the parameters the expected answer is computed
with, fixed here and never taken from a user's protocol), `protocol` (the hand-written protocol, a path from the
repository root), `agentic_protocol` and `vocab` (rag-factuality only). Truth parameters by kind: effect and
consistency take `metric` and `min_effect`; inventory takes `target`; best takes `metric`. A parameter of another
kind is refused. This module checks the file's shape only; the web app also checks that each protocol parses
and asks the entry's question with the entry's kind.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .protocol import Kind

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
    vocab: str | None = Field(None, pattern=NAME)

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
