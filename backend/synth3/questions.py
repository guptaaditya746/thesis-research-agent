"""Aditya's question file for one domain, and its loader.

The file is `data/synth3/questions/<domain>.yaml`. Example:

    domain: law
    questions:
      - id: l01                      # lower case letters, digits and "-", at most 40 characters, never repeated
        question: Does Method K improve Yield compared with Usual method?
        sub_questions:               # optional; only plan 4 reads them, they are never scored
          - Which studies measured Yield?
        about: [Method K]            # optional; names from the spec that set the scope
        kind: open                   # optional: open, effect, best, consistency or inventory
        notes: free text             # optional; ignored by the code
      - id: l02
        question: Which things were compared?
        kind: inventory
        target: metric               # target: condition (the compared things, the default) or metric (the
                                     # measures); inventory only

Only `id` and `question` are needed. Any other key is refused. There is no upper limit on the number of questions.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import ValidationError

from jsonio import canonical_bytes, sha256_hex
from synth2.recipe import Strict
from synth3.spec import SPECS, DomainSpec

QUESTIONS = SPECS / "questions"
KINDS = ("open", "effect", "best", "consistency", "inventory")
TARGETS = ("condition", "metric")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


class Question(Strict):
    id: str
    question: str
    sub_questions: list[str] = []
    about: list[str] = []
    kind: Literal[*KINDS] = "open"   # plan 4 only; the judge ignores it
    target: Literal[*TARGETS] | None = None   # inventory only: what the list is of
    notes: str = ""


class QuestionSet(Strict):
    domain: str
    questions: list[Question]
    sha256: str

    def get(self, qid: str) -> Question:
        for q in self.questions:
            if q.id == qid:
                return q
        raise KeyError(f"no question with id {qid!r}")


def question_sha256(q: Question) -> str:
    """Hash of what an answer depends on (answer records, `marking.why_not`): the question, the sub-questions (plan
    4's system plans with them) and `about`. Notes and kind are left out."""
    return sha256_hex(canonical_bytes({"question": q.question, "sub_questions": q.sub_questions, "about": q.about}))


def asked_sha256(q: Question) -> str:
    """Hash of what the system's answer was made for: `question_sha256`'s parts plus the kind and the target
    (normalised by `target_of`, so no target and `condition` hash the same on an inventory question)."""
    return sha256_hex(canonical_bytes({"question": q.question, "sub_questions": q.sub_questions, "about": q.about,
                                       "kind": q.kind, "target": target_of(q)}))


def answer_by_of(q: Question) -> str:
    """How the system answers: "written" for an open question, else by the kind."""
    return "written" if q.kind == "open" else q.kind


def target_of(q: Question) -> str | None:
    """What an inventory question lists (the compared things by default); None for any other kind."""
    return (q.target or "condition") if q.kind == "inventory" else None


def sheet_question_sha256(q: Question) -> str:
    """Hash of what a sheet depends on: the question and `about`. Sub-questions are never scored and set no scope,
    so editing them (or notes, or kind) keeps every sheet fresh."""
    return sha256_hex(canonical_bytes({"question": q.question, "about": q.about}))


def spec_names(spec: DomainSpec) -> list[str]:
    return spec.names()


def _fold(text: str) -> str:
    return " ".join(text.lower().split())


def _check_entry(entry: object, seen: dict[str, str], names: list[str]) -> Question:
    if not isinstance(entry, dict):
        raise ValueError("each question must be a mapping")
    qid = entry.get("id")
    if not isinstance(qid, str) or not _ID.match(qid):
        raise ValueError(f"id {qid!r} must be lower case letters, digits and '-' (1 to 40 characters, "
                         "starting with a letter or digit)")
    if qid in seen:
        raise ValueError(f"id {qid} is used twice")
    if "kind" in entry and entry["kind"] not in KINDS:
        raise ValueError(f"{qid}: kind {entry['kind']!r} is not one of {', '.join(KINDS)}")
    try:
        q = Question(**entry)
    except (ValidationError, TypeError) as err:
        raise ValueError(f"{qid}: {err}") from err
    if q.target is not None and q.kind != "inventory":
        raise ValueError(f"{qid}: target is only for kind inventory")
    if not q.question.strip():
        raise ValueError(f"{qid}: question is empty")
    if any(not s.strip() for s in q.sub_questions):
        raise ValueError(f"{qid}: sub_questions holds an empty entry")
    folded = _fold(q.question)
    for other, text in seen.items():
        if text == folded:
            raise ValueError(f"{qid}: same question as {other}")
    unknown = [n for n in q.about if n not in names]
    if unknown:
        raise ValueError(f"{qid}: about names {unknown} that the spec does not have; the spec has {names}")
    seen[qid] = folded
    return q


def load_questions(domain: str, spec: DomainSpec, root: Path = QUESTIONS) -> QuestionSet:
    """Read `<root>/<domain>.yaml`. Any problem is a `ValueError` that names the question id and the field."""
    path = root / f"{domain}.yaml"
    if not path.is_file():
        raise ValueError(f"no questions file at {path}; Aditya writes it (see synth3/questions.py)")
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    try:
        data = yaml.safe_load(raw.decode("utf-8"))
    except yaml.YAMLError as err:
        raise ValueError(f"{path}: not valid YAML ({err})") from err
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the questions file must be a mapping")
    if data.get("domain") != domain:
        raise ValueError(f"domain {data.get('domain')!r} in the file, expected {domain!r}")
    extra = sorted(set(data) - {"domain", "questions"})
    if extra:
        raise ValueError(f"{path}: unknown key {extra[0]!r}")
    entries = data.get("questions")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: 'questions' must be a list")
    seen: dict[str, str] = {}
    names = spec_names(spec)
    questions = [_check_entry(e, seen, names) for e in entries]
    return QuestionSet(domain=domain, questions=questions, sha256=sha256_hex(raw))
