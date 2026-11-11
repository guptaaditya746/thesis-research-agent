"""The fixed answer form and three ways to conclude from the studies.

`pooled` adds up the counts per side of each candidate condition; it gives the answer key and is the oracle.
`vote` lets each study vote; `lumped` adds everything together and ignores the conditions. The last two are the
weaker ways a system can go wrong, kept so their mistakes can be recognised.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from synth2.recipe import Recipe
from synth2.world import Cell, Study, direction, study_delta

VERDICTS = ("depends", "helps", "hurts", "no_effect", "mixed", "insufficient")
SIDE_WORDS = ("helps", "hurts", "no_effect")
KEYS = {"verdict", "condition", "sides", "untested"}


@dataclass(frozen=True)
class Answer:
    verdict: str
    condition: str | None
    sides: dict[str, str]
    untested: tuple[str, ...]

    def json(self) -> dict:
        return {"verdict": self.verdict, "condition": self.condition, "sides": dict(self.sides),
                "untested": list(self.untested)}

    @classmethod
    def parse(cls, obj: Any) -> "Answer":
        if not isinstance(obj, dict) or set(obj) != KEYS:
            raise ValueError(f"an answer is an object with exactly the keys {sorted(KEYS)}")
        verdict, condition, sides, untested = obj["verdict"], obj["condition"], obj["sides"], obj["untested"]
        if not isinstance(verdict, str) or verdict not in VERDICTS:
            raise ValueError(f"unknown verdict {verdict!r}; known: {', '.join(VERDICTS)}")
        if (verdict == "depends") != isinstance(condition, str) or (verdict != "depends" and condition is not None):
            raise ValueError("condition is a string for the verdict 'depends' and null for every other verdict")
        if not isinstance(sides, dict) or any(not isinstance(k, str) or v not in SIDE_WORDS for k, v in sides.items()):
            raise ValueError(f"sides maps a level id to one of {', '.join(SIDE_WORDS)}")
        if not isinstance(untested, list) or any(not isinstance(u, str) for u in untested):
            raise ValueError("untested is a list of '<condition id>.<level id>' strings")
        return cls(verdict, condition, dict(sides), tuple(sorted(untested)))


def _cells(studies: Sequence[Study]) -> list[Cell]:
    return [c for s in studies if s.duplicate_of is None for c in s.cells]


def _delta(cells: Sequence[Cell]) -> float:
    return sum(c.k_t for c in cells) / sum(c.n_t for c in cells) - sum(c.k_c for c in cells) / sum(c.n_c for c in cells)


def _untested(cells: Sequence[Cell], recipe: Recipe) -> tuple[str, ...]:
    seen = {(cond, level) for c in cells for cond, level in c.levels.items()}
    return tuple(sorted(f"{c.id}.{lv.id}" for c in recipe.conditions for lv in c.levels if (c.id, lv.id) not in seen))


def lumped(studies: Sequence[Study], recipe: Recipe) -> Answer:
    cells = _cells(studies)
    verdict = direction(_delta(cells), recipe.min_effect) if cells else "insufficient"
    return Answer(verdict, None, {}, _untested(cells, recipe))


def pooled(studies: Sequence[Study], recipe: Recipe) -> Answer:
    cells = _cells(studies)
    best: tuple[float, str, dict[str, str]] | None = None
    for cond in recipe.conditions:
        per_level = [[c for c in cells if c.levels[cond.id] == lv.id] for lv in cond.levels]
        if not all(per_level):
            continue
        deltas = [_delta(group) for group in per_level]
        words = [direction(d, recipe.min_effect) for d in deltas]
        gap = abs(deltas[0] - deltas[1])
        if words[0] != words[1] and gap >= recipe.min_gap and (best is None or gap > best[0]):
            best = (gap, cond.id, {lv.id: w for lv, w in zip(cond.levels, words)})
    if best is None:
        return lumped(studies, recipe)
    return Answer("depends", best[1], best[2], _untested(cells, recipe))


def vote(studies: Sequence[Study], recipe: Recipe) -> Answer:
    counted = [s for s in studies if s.duplicate_of is None]
    votes = {direction(study_delta(s), recipe.min_effect) for s in counted}
    if not counted:
        verdict = "insufficient"
    elif {"helps", "hurts"} <= votes:
        verdict = "mixed"
    else:
        verdict = next((w for w in ("helps", "hurts") if w in votes), "no_effect")
    return Answer(verdict, None, {}, _untested(_cells(studies), recipe))
