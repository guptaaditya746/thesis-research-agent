"""Write one study as a short paper from fixed templates, and remember where every planted value sits.

Three text levels: `table` (counts in a table next to the subset's names), `prose` (counts in sentences),
`split` (the table names subsets only by a code; what the code means is said in Setup).
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

from synth2.recipe import Recipe
from synth2.world import Cell, Study

TEXT_LEVELS = ("table", "prose", "split")
CLAIMS: dict[str, str] = {
    "helps": "Overall, the {t} clearly improves {m} over the {c}.",
    "hurts": "Overall, the {t} lowers {m} compared with the {c}.",
    "no_effect": "Overall, the {t} and the {c} reach about the same {m}.",
}
HEADER = "| Subset | System | Correct | Total |\n| --- | --- | --- | --- |\n"
# Filler text: no digits, and none of the level ids as a word of its own.
TITLES = ("Measuring {m} of the {t}", "The {t} against the {c}: a study of {m}", "How the {t} changes {m}")
OPENERS = ("We compare the {t} with the {c} on {m}.", "This paper measures {m} for the {t} and for the {c}.",
           "We report a controlled comparison of the {t} and the {c}.")
CLOSERS = ("The counts behind this statement are given in the Results section.",
           "Further work should repeat the comparison on other benchmarks.",
           "All counts are reported so that others can add them to their own.")
COUNT_FIELDS = ("k_t", "n_t", "k_c", "n_c")


@dataclass(frozen=True)
class Placement:
    fact: str
    start: int
    end: int


@dataclass(frozen=True)
class Paper:
    study: str
    text: str
    placements: tuple[Placement, ...]


class _Builder:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.size = 0
        self.placements: list[Placement] = []

    def add(self, text: str) -> None:
        self.parts.append(text)
        self.size += len(text)

    def plant(self, fact: str, text: str) -> None:
        self.placements.append(Placement(fact, self.size, self.size + len(text)))
        self.add(text)


def _names(cell: Cell, recipe: Recipe) -> list[tuple[str, str]]:
    """(condition name, level name) for each of the three conditions, in recipe order."""
    return [(c.name, next(lv.name for lv in c.levels if lv.id == cell.levels[c.id])) for c in recipe.conditions]


def _table(b: _Builder, study: Study, recipe: Recipe, subsets: list[str]) -> None:
    b.add(HEADER)
    for i, (cell, subset) in enumerate(zip(study.cells, subsets)):
        for label, k, n in ((recipe.treatment.label, "k_t", "n_t"), (recipe.control.label, "k_c", "n_c")):
            b.add(f"| {subset} | {label} | ")
            b.plant(f"{study.id}.c{i}.{k}", str(getattr(cell, k)))
            b.add(" | ")
            b.plant(f"{study.id}.c{i}.{n}", str(getattr(cell, n)))
            b.add(" |\n")


def write_paper(study: Study, recipe: Recipe, text_level: str, seed: int) -> Paper:
    if text_level not in TEXT_LEVELS:
        raise ValueError(f"unknown text level '{text_level}'; known: {', '.join(TEXT_LEVELS)}")
    rng = random.Random(f"synth2:{seed}:{study.id}:text")
    words = {"t": recipe.treatment.label, "c": recipe.control.label, "m": recipe.metric}
    claim = CLAIMS[study.claim].format(**words)
    codes = [f"Subset {chr(ord('A') + i)}" for i in range(len(study.cells))]
    plain = [", ".join(level for _, level in _names(cell, recipe)) for cell in study.cells]
    b = _Builder()
    b.add(f"# {study.label}: {rng.choice(TITLES).format(**words)}\n\n## Abstract\n\n")
    b.add(rng.choice(OPENERS).format(**words) + " ")
    b.plant(f"{study.id}.claim.abstract", claim)
    b.add(f"\n\n## Setup\n\nThe {recipe.treatment.label} {recipe.treatment.description}. "
          f"The {recipe.control.label} {recipe.control.description}. "
          f"Both were scored on the {study.dataset} benchmark. The study covers these subsets:\n\n")
    for cell, code in zip(study.cells, codes):
        described = "; ".join(f"{name}: {level}" for name, level in _names(cell, recipe))
        b.add(f"- {code + '. ' if text_level == 'split' else ''}{described}\n")
    b.add("\n## Results\n\n")
    if text_level == "prose":
        for i, (cell, subset) in enumerate(zip(study.cells, plain)):
            for label, k, n in ((recipe.treatment.label, "k_t", "n_t"), (recipe.control.label, "k_c", "n_c")):
                b.add(f"On the subset with {subset}, the {label} answered ")
                b.plant(f"{study.id}.c{i}.{k}", str(getattr(cell, k)))
                b.add(" of ")
                b.plant(f"{study.id}.c{i}.{n}", str(getattr(cell, n)))
                b.add(f" {recipe.unit} correctly.\n")
    else:
        _table(b, study, recipe, codes if text_level == "split" else plain)
    b.add("\n## Conclusion\n\n")
    b.plant(f"{study.id}.claim.conclusion", claim)
    b.add(" " + rng.choice(CLOSERS) + "\n")
    return Paper(study.id, "".join(b.parts), tuple(b.placements))


def missing_facts(paper: Paper, study: Study) -> list[str]:
    """Fact ids whose span does not hold the planted value, or that have no span at all. Empty means faithful."""
    spans = {pl.fact: paper.text[pl.start:pl.end] for pl in paper.placements}
    pattern = re.escape(CLAIMS[study.claim]).replace(r"\{t\}", ".+").replace(r"\{c\}", ".+").replace(r"\{m\}", ".+")
    missing = []
    for i, cell in enumerate(study.cells):
        for field in COUNT_FIELDS:
            fact = f"{study.id}.c{i}.{field}"
            if spans.get(fact) != str(getattr(cell, field)):
                missing.append(fact)
    for place in ("abstract", "conclusion"):
        fact = f"{study.id}.claim.{place}"
        if not re.fullmatch(pattern, spans.get(fact, "")):
            missing.append(fact)
    return missing
