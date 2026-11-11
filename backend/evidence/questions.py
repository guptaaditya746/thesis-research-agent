"""The question list (domains/<pack>/questions.yaml): the questions the system answers, shared by the web app
(webapp/evquestions.py) and the evaluation.

Per entry: `id` (a plain name), `question` (exactly as its hand-written protocol asks it), `kind` (effect,
inventory, consistency, best, chaining, limitations or builds_on; the protocol's kind), `truth` (the parameters the expected answer is computed
with, fixed here and never taken from a user's protocol), `protocol` (the hand-written protocol, a path from the
questions file's folder, `protocol_file`) and `agentic_protocol` (optional). Truth parameters by
kind: effect and consistency take `metric` and `min_effect`; inventory takes `target`; best takes `metric`;
chaining takes `metric`, `min_effect`, `source` and `target` (two compared things); limitations and builds_on take
`thing` (a compared thing, or none for every one). A parameter of another kind is refused. This module checks the file's shape only; the web app also checks that
each protocol parses and asks the entry's question with the entry's kind.
"""
from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .pack import load_pack, questions_path
from .protocol import DEFAULT_PACK, Kind, Protocol, load as load_protocol
from .rundir import ANSWER_FILE, PROTOCOL_FILE, RUN_FILE, RunDir

DEFAULT = questions_path(DEFAULT_PACK)
NAME = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"   # a directory name, never a flag or a path
TRUTH_FIELDS: dict[str, tuple[str, ...]] = {"effect": ("metric", "min_effect"), "consistency": ("metric", "min_effect"),
                                            "inventory": ("target",), "best": ("metric",),
                                            "chaining": ("metric", "min_effect", "source", "target"),
                                            "limitations": ("thing",), "builds_on": ("thing",)}


class QuestionTruth(BaseModel):
    """What the expected answer is computed with (evaluation): the question metric and the neutral band, the
    inventory's target type (any type of the questions file's pack, `parse` checks it), a chain's `source` and
    `target` compared things, or the compared thing a limitations or builds-on question is about (`thing`)."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str | None = Field(None, min_length=1)
    min_effect: float | None = Field(None, gt=0)
    target: str | None = Field(None, min_length=1)
    source: str | None = Field(None, min_length=1)
    thing: str | None = Field(None, min_length=1)


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


def parse(path: Path, pack: Path | None = None) -> QuestionsFile:
    """The file, checked (ValueError naming every problem). When `pack` (default: the file's folder) is a pack
    folder (it holds pack.yaml), every inventory `truth.target` must be a type of that pack (a chain's `target` is a
    compared thing, not a type)."""
    try:
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"{path.name} is not YAML: {str(exc)[:300]}") from exc
    try:
        found = QuestionsFile.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"{path.name} does not validate: " + "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())) from exc
    folder = Path(pack if pack is not None else path.parent).resolve()
    if (folder / "pack.yaml").is_file():   # a pack's questions file: every inventory target is a type of the pack
        types = load_pack(folder.name, root=folder.parent).types
        bad = [f"{q.id}: {q.truth.target}" for q in found.questions
               if q.kind == "inventory" and q.truth.target not in (None, *types)]
        if bad:
            raise ValueError(f"{path.name}: truth.target names no type of pack {folder.name!r} ({sorted(types)}): "
                             + "; ".join(bad))
    return found


def load(path: Path | str = DEFAULT) -> list[QuestionEntry]:
    return parse(Path(path)).questions


def default_entry(path: Path | str = DEFAULT) -> QuestionEntry:
    """The default question of a questions file: its FIRST effect question, by rule (code names no question, D35;
    for the default pack it is the question its corpora are generated for, so domains/<pack>/questions.yaml lists it
    first among its effect questions and a test pins it: evaluation/tests/test_baseline_new_kinds.py)."""
    found = [q for q in load(path) if q.kind == "effect"]
    if not found:
        raise ValueError(f"{path} has no effect question, so no default question")
    return found[0]


def protocol_file(path_text: str, questions_file: Path | str = DEFAULT) -> Path:
    """An entry's `protocol` or `agentic_protocol` as a file: the path is relative to the questions file's folder
    (the pack folder, domains/<pack>/)."""
    return Path(questions_file).parent / path_text


def entry_protocol(path_text: str, questions_file: Path | str) -> Protocol:
    """An entry's hand-written protocol, parsed. A questions file in a pack folder outside the packs root (a test
    pack beside a pack.yaml) reads the protocol's pack from that folder's parent, so a test pack resolves (P19)."""
    from . import pack as pack_module
    questions_file = Path(questions_file)
    root = questions_file.resolve().parent.parent
    domains = (root if (questions_file.parent / "pack.yaml").is_file() and root != Path(pack_module.DOMAINS).resolve()
               else None)
    return load_protocol(protocol_file(path_text, questions_file), domains)


def every_question(root: Path | str | None = None) -> list[tuple[QuestionEntry, Path]]:
    """Every question of every pack (`<root>/*/questions.yaml`, root default the packs root, domains/, read at call
    time) with its questions file; ValueError for an id found in two packs (an id names one question)."""
    from . import pack as pack_module
    folder = Path(root) if root is not None else Path(pack_module.DOMAINS)
    found = [(q, path) for path in sorted(folder.glob("*/questions.yaml")) for q in load(path)]
    seen: dict[str, Path] = {}
    for q, path in found:
        if q.id in seen:
            raise ValueError(f"question id {q.id!r} is in two packs ({seen[q.id]} and {path}); an id names one "
                             f"question")
        seen[q.id] = path
    return found


def find(question_id: str, root: Path | str | None = None) -> tuple[QuestionEntry, Path]:
    """The question `question_id` of any pack (`every_question`) and its questions file; ValueError naming the
    known ids for an unknown one."""
    found = every_question(root)
    for q, path in found:
        if q.id == question_id:
            return q, path
    raise ValueError(f"unknown question id {question_id!r}; the packs' questions files have "
                     f"{', '.join(q.id for q, _ in found)}")


def run_questions(run_dir: Path) -> Path | None:
    """The questions file of the pack a run's protocol.yaml names (its `domain`, read from the `domains` folder
    run.json's settings name, else the packs root); None when the run has no protocol.yaml or its pack has no
    questions file."""
    from . import pack as pack_module
    rd = RunDir(Path(run_dir))
    if not rd.file(PROTOCOL_FILE).is_file():
        return None
    data = yaml.safe_load(rd.file(PROTOCOL_FILE).read_bytes().decode("utf-8"))
    domain = data.get("domain", DEFAULT_PACK) if isinstance(data, dict) else DEFAULT_PACK
    settings = rd.settings
    root = (settings.domains if settings is not None else None) or pack_module.DOMAINS
    path = Path(root) / str(domain) / "questions.yaml"
    return path if path.is_file() else None


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
        settings = rd.settings
        domains = settings.domains if settings is not None else None
        protocol = load_protocol(rd.file(PROTOCOL_FILE), domains)   # its pack from the run's `domains` folder
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
