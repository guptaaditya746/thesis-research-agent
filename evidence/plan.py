"""The plan file: what a human confirms before a run (question, evidence lines, the main rule, the word list and
the decisions). Its sha256 and the word list's go into the protocol lock (lockfile.lock, `plan=`)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from .contract import Frozen, digest

__all__ = ["DIRECTION", "MAIN_RULE", "Decision", "EvidenceLine", "Plan", "WordList", "load_plan", "write_plan"]


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


MAIN_RULE = "main_rule"   # the id and the type of the main-answer rule's decision row
DIRECTION = "direction"   # the type of a measure's direction row: id "direction:<measure>", value "higher" | "lower"


class Decision(Frozen):
    """One choice the planner made; `confirmed_by` stays None until a human confirms it. Type `main_rule` is the
    main-answer rule (its value one of evidence.planner.RULES); type `direction` says whether a measure is better
    higher or lower (id "direction:<measure id>", value "higher" | "lower"). Neither fills a query parameter by itself
    nor is rerun."""
    id: str
    type: Literal["must_match", "counts_as", "threshold", "include", "main_rule", "direction"]
    value: Any
    reason: str
    flagged: bool = False
    flag_reason: str | None = None
    confirmed_by: str | None = None
    confirmed_at: str | None = None


class EvidenceLine(Frozen):
    """One line of evidence to look for; the oversell line has `removable=False`. `how`: the plain sentences shown
    under "how?" (never code), kept with the line so a reloaded plan still has them."""
    id: str
    question: str
    query: str
    template: str | None
    removable: bool = True
    how: list[str] = Field(default_factory=list)


class Plan(Frozen):
    """`measures`: the thing ids (keys of `words.things`) that are measures (a score, a rate); the other things are
    compared things, the first of them the one the question asks about (the treatment side of a plan run)."""
    question: str
    field: Literal["cs", "medicine", "materials", "other"]
    lines: list[EvidenceLine]
    main_rule: str
    words: WordList
    decisions: list[Decision]
    clarifications: list[dict[str, str]]
    measures: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _migrate_main_rule(cls, data: Any) -> Any:
        """A plan written before the `main_rule` type kept the rule as a `counts_as` row with id main_rule."""
        if isinstance(data, dict) and isinstance(data.get("decisions"), list):
            data = {**data, "decisions": [
                {**d, "type": MAIN_RULE} if isinstance(d, dict) and d.get("id") == MAIN_RULE and d.get("type") == "counts_as"
                else d for d in data["decisions"]]}
        return data

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
