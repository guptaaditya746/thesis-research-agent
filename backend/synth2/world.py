"""The made-up field: one hidden law and the noisy studies that were run under it.

Every draw has its own named seed, so changing one side of the law or one study's noise leaves every other
number as it was. That is what lets a twin corpus differ from its base in exactly the papers it should.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import Any

from synth2.recipe import Recipe

# law kind -> the direction on the first and on the second side (before the seed swaps or mirrors them)
LAW_KINDS: dict[str, tuple[str, str]] = {
    "uniform": ("helps", "helps"),
    "one_sided": ("helps", "no_effect"),
    "opposed": ("helps", "hurts"),
}
SIGN = {"helps": 1.0, "hurts": -1.0, "no_effect": 0.0}


@dataclass(frozen=True)
class Law:
    condition: str
    effects: dict[str, float]   # level id of the true condition -> treatment rate minus control rate
    kind: str
    mirrored: bool

    def json(self) -> dict:
        return {"condition": self.condition, "effects": dict(self.effects), "kind": self.kind,
                "mirrored": self.mirrored}

    @classmethod
    def parse(cls, obj: dict) -> "Law":
        return cls(obj["condition"], {k: float(v) for k, v in obj["effects"].items()}, obj["kind"],
                   bool(obj["mirrored"]))


@dataclass(frozen=True)
class Cell:
    levels: dict[str, str]   # condition id -> level id, for all three conditions
    n_t: int
    k_t: int
    n_c: int
    k_c: int

    def __post_init__(self) -> None:
        for arm, n, k in (("treatment", self.n_t, self.k_t), ("control", self.n_c, self.k_c)):
            if not (isinstance(n, int) and isinstance(k, int) and 0 < n and 0 <= k <= n):
                raise ValueError(f"impossible counts in the {arm} arm: {k} of {n}")

    def json(self) -> dict:
        return {"levels": dict(self.levels), "n_t": self.n_t, "k_t": self.k_t, "n_c": self.n_c, "k_c": self.k_c}


@dataclass(frozen=True)
class Study:
    id: str
    label: str
    dataset: str
    cells: tuple[Cell, ...]
    claim: str
    overclaims: bool
    duplicate_of: str | None = None

    def json(self) -> dict:
        return {"id": self.id, "label": self.label, "dataset": self.dataset,
                "cells": [c.json() for c in self.cells], "claim": self.claim, "overclaims": self.overclaims,
                "duplicate_of": self.duplicate_of}

    @classmethod
    def parse(cls, obj: Any) -> "Study":
        sid = obj.get("id", "?") if isinstance(obj, dict) else "?"
        try:
            cells = tuple(Cell(dict(c["levels"]), c["n_t"], c["k_t"], c["n_c"], c["k_c"]) for c in obj["cells"])
            if not cells or obj["claim"] not in SIGN:
                raise ValueError("a study needs at least one cell and a known claim word")
            return cls(obj["id"], obj["label"], obj["dataset"], cells, obj["claim"], bool(obj["overclaims"]),
                       obj.get("duplicate_of"))
        except (KeyError, TypeError, ValueError) as err:
            raise ValueError(f"study {sid}: {err}") from err


def direction(delta: float, min_effect: float) -> str:
    if delta >= min_effect:
        return "helps"
    if delta <= -min_effect:
        return "hurts"
    return "no_effect"


def study_delta(study: Study) -> float:
    """The study's own counts added over its cells: treatment rate minus control rate."""
    return (sum(c.k_t for c in study.cells) / sum(c.n_t for c in study.cells)
            - sum(c.k_c for c in study.cells) / sum(c.n_c for c in study.cells))


def honest(study: Study, recipe: Recipe) -> Study:
    """The study with the claim its own counts support."""
    return replace(study, claim=direction(study_delta(study), recipe.min_effect), overclaims=False)


def draw_law(recipe: Recipe, seed: int, kind: str) -> Law:
    if kind not in LAW_KINDS:
        raise ValueError(f"unknown law kind '{kind}'; known: {', '.join(LAW_KINDS)}")
    rng = random.Random(f"synth2:{seed}:law")
    condition = rng.choice(recipe.conditions)
    mirrored = rng.random() < 0.5
    swapped = rng.random() < 0.5
    words = LAW_KINDS[kind][::-1] if swapped else LAW_KINDS[kind]
    effects = {}
    for level, word in zip(condition.levels, words):
        size = round(rng.uniform(*recipe.effect), 3) if SIGN[word] else 0.0
        effects[level.id] = size * SIGN[word] * (-1.0 if mirrored else 1.0) + 0.0   # + 0.0 turns -0.0 into 0.0
    return Law(condition.id, effects, kind, mirrored)


def draw_studies(recipe: Recipe, law: Law, seed: int, count: int, *, exact: bool = False, noise_seed: int = 0,
                 untested: str | None = None, redraw_level: str | None = None) -> tuple[Study, ...]:
    if count > len(recipe.authors):
        raise ValueError(f"{count} studies need {count} authors, the recipe has {len(recipe.authors)}")
    true = next(c for c in recipe.conditions if c.id == law.condition)
    side = {"a": true.levels[0].id, "b": true.levels[1].id}
    if untested is not None and untested not in side.values():
        raise ValueError(f"'{untested}' is not a level of the true condition {true.id}")
    authors = list(recipe.authors)
    random.Random(f"synth2:{seed}:authors").shuffle(authors)
    low, high = recipe.n_range
    studies = []
    for i in range(count):
        sid = f"S{i + 1:03d}"
        rng = random.Random(f"synth2:{seed}:{sid}:design")
        coverage = rng.choice(("a", "b", "both"))
        fake = {c.id: rng.choice(c.levels).id for c in recipe.conditions if c.id != true.id}
        n = rng.randrange(low, high + 1, recipe.n_step)
        base = rng.uniform(*recipe.base_rate)
        dataset = rng.choice(recipe.datasets)
        year = rng.randint(*recipe.years)
        covered = [side[x] for x in (("a", "b") if coverage == "both" else (coverage,))]
        if untested is not None:
            covered = [next(v for v in side.values() if v != untested)]
        cells = []
        for level in covered:
            with_effect = min(max(base + law.effects[level], 0.0), 1.0)
            if exact:
                k_c, k_t = round(n * base), round(n * with_effect)
            else:
                ns = noise_seed if redraw_level == level else 0
                counts = random.Random(f"synth2:{seed}:{ns}:{sid}:{level}:counts")
                k_c = counts.binomialvariate(n, base)
                k_t = counts.binomialvariate(n, with_effect)
            levels = {c.id: (level if c.id == true.id else fake[c.id]) for c in recipe.conditions}
            cells.append(Cell(levels, n, k_t, n, k_c))
        studies.append(honest(Study(sid, f"{authors[i]} et al. ({year})", dataset, tuple(cells), "no_effect", False),
                              recipe))
    return tuple(studies)
