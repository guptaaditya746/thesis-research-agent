"""The plan file: what a human confirms before a run (question, evidence lines, the main rule, the word list and
the decisions). Its sha256 and the word list's go into the protocol lock (lockfile.lock, `plan=`)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from .contract import Frozen, digest

__all__ = ["Decision", "EvidenceLine", "Plan", "WordList", "load_plan", "write_plan"]


class WordList(Frozen):
    """Names per thing id (20-50 written by the LLM, `written_by`), the cue words, and the ontology's names kept
    apart in `ontology_names`."""
    things: dict[str, list[str]]
    cues: list[str]
    written_by: str
    ontology_names: dict[str, list[str]]

    @property
    def sha256(self) -> str:
        return digest(self.model_dump(mode="json"))


class Decision(Frozen):
    """One choice the planner made; `confirmed_by` stays None until a human confirms it."""
    id: str
    type: Literal["must_match", "counts_as", "threshold", "include"]
    value: Any
    reason: str
    flagged: bool = False
    flag_reason: str | None = None
    confirmed_by: str | None = None
    confirmed_at: str | None = None


class EvidenceLine(Frozen):
    """One line of evidence to look for; the oversell line has `removable=False`."""
    id: str
    question: str
    query: str
    template: str | None
    removable: bool = True


class Plan(Frozen):
    question: str
    field: Literal["cs", "medicine", "materials", "other"]
    lines: list[EvidenceLine]
    main_rule: str
    words: WordList
    decisions: list[Decision]
    clarifications: list[dict[str, str]]

    def ready(self) -> bool:
        """True when every decision is confirmed."""
        return all(d.confirmed_by is not None for d in self.decisions)

    @property
    def sha256(self) -> str:
        return digest(self.model_dump(mode="json"))


def load_plan(path: Path | str) -> Plan:
    return Plan.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_plan(plan: Plan, path: Path | str) -> None:
    Path(path).write_text(plan.model_dump_json(indent=2), encoding="utf-8")
