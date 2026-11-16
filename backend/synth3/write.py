"""Write one synth3 study as a template paper and remember where every planted fact sits.

Two text levels: `table` (numbers in tables) and `prose` (numbers in sentences). Only human names are printed
(arm label, measure name, level names, setting name), never ids, and the study id is not printed at all.
A subset is named by the level of every condition, in spec order.
"""
from __future__ import annotations

import random

from synth2.write import Paper, _Builder
from synth3.spec import DomainSpec
from synth3.world import ArmResult, Cell, Study

TEXT_LEVELS = ("table", "prose")
COUNT_FIELDS = ("k", "n")
VALUE_FIELDS = ("mean", "sd", "n")
# Claim words are "better" words: on a lower-is-better measure, helps reads "reduces".
CLAIMS: dict[tuple[str, bool], str] = {
    ("helps", True): "Overall, the {a} improves {m} compared with the {c}.",
    ("helps", False): "Overall, the {a} reduces {m} compared with the {c}.",
    ("hurts", True): "Overall, the {a} lowers {m} compared with the {c}.",
    ("hurts", False): "Overall, the {a} increases {m} compared with the {c}.",
    ("no_effect", True): "Overall, the {a} and the {c} reach about the same {m}.",
    ("no_effect", False): "Overall, the {a} and the {c} reach about the same {m}.",
}
COUNT_HEADER = "| Subset | Arm | Measure | Count | Total |\n| --- | --- | --- | --- | --- |\n"
VALUE_HEADER = "| Subset | Arm | Measure | Mean | SD | n |\n| --- | --- | --- | --- | --- | --- |\n"
# Filler text: no digits.
TITLES = ("A comparison of {a} and {c} on {m}", "Measuring {m} under {a}", "How {a} changes {m}")
OPENERS = ("We compare the {a} with the {c} on {m}.", "This paper measures {m} for the {a} and for the {c}.",
           "We report a controlled comparison of the {a} and the {c}.")
CLOSERS = ("The numbers behind this statement are given in the Results section.",
           "Further work should repeat the comparison in other settings.",
           "All numbers are reported so that others can add them to their own.")


def _claim_sentence(spec: DomainSpec, key: str, word: str) -> str:
    arm, against, measure_id = key.split("|")
    measure = spec.measure(measure_id)
    label = {a.id: a.label for a in spec.arms}
    return CLAIMS[(word, measure.higher_is_better)].format(
        a=label[arm], c=label[against], m=measure.name.lower())


def _fact_claim(sid: str, key: str, place: str) -> str:
    return f"{sid}.claim.{key.replace('|', '.')}.{place}"


def _subset(cell: Cell, spec: DomainSpec) -> str:
    return ", ".join(next(lv.name for lv in c.levels if lv.id == cell.levels[c.id]) for c in spec.conditions)


def _value(r: ArmResult, field: str, decimals: int | None) -> str:
    v = getattr(r, field)
    return f"{v:.{decimals}f}" if field in ("mean", "sd") else str(v)


def _fields(kind: str) -> tuple[str, ...]:
    return COUNT_FIELDS if kind == "count" else VALUE_FIELDS


def write_paper(study: Study, spec: DomainSpec, text_level: str, seed: int) -> Paper:
    if text_level not in TEXT_LEVELS:
        raise ValueError(f"unknown text level '{text_level}'; known: {', '.join(TEXT_LEVELS)}")
    rng = random.Random(f"synth3:{seed}:{study.id}:text")
    label = {a.id: a.label for a in spec.arms}
    sid = study.id
    a0, c0, m0 = next(iter(study.claims)).split("|")
    words = {"a": label[a0], "c": label[c0], "m": spec.measure(m0).name.lower()}
    b = _Builder()
    b.add(f"# {study.label}: {rng.choice(TITLES).format(**words)}\n\n## Abstract\n\n")
    b.add(rng.choice(OPENERS).format(**words))
    for key, word in study.claims.items():
        b.add(" ")
        b.plant(_fact_claim(sid, key, "abstract"), _claim_sentence(spec, key, word))
    b.add("\n\n## Setup\n\n")
    for arm in study.arms:
        a = next(x for x in spec.arms if x.id == arm)
        b.add(f"The {a.label} {a.description}. ")
    b.add("The study was run at the ")
    b.plant(f"{sid}.setting", study.setting)
    b.add(". It covers these subsets:\n\n")
    seen: list[str] = []
    for cell in study.cells:
        subset = _subset(cell, spec)
        if subset not in seen:
            seen.append(subset)
            b.add(f"- {subset}\n")
    b.add("\n## Results\n\n")
    if text_level == "prose":
        for cell in study.cells:
            measure = spec.measure(cell.measure)
            subset = _subset(cell, spec)
            for r in cell.results:
                fact = f"{sid}.c{cell.index}.{r.arm}"
                if measure.kind == "count":
                    b.add(f"On the subset with {subset}, ")
                    b.plant(f"{fact}.k", str(r.k))
                    b.add(" of ")
                    b.plant(f"{fact}.n", str(r.n))
                    b.add(f" {measure.unit} {measure.outcome} with the {label[r.arm]}.\n\n")
                else:
                    b.add(f"On the subset with {subset}, the {label[r.arm]} reached a mean "
                          f"{measure.name.lower()} of ")
                    b.plant(f"{fact}.mean", _value(r, "mean", measure.decimals))
                    b.add(f" {measure.unit} (SD ")
                    b.plant(f"{fact}.sd", _value(r, "sd", measure.decimals))
                    b.add(", n = ")
                    b.plant(f"{fact}.n", str(r.n))
                    b.add(").\n\n")
    else:
        for kind, header in (("count", COUNT_HEADER), ("value", VALUE_HEADER)):
            cells = [c for c in study.cells if spec.measure(c.measure).kind == kind]
            if not cells:
                continue
            b.add(header)
            for cell in cells:
                measure = spec.measure(cell.measure)
                fields = _fields(kind)
                for r in cell.results:
                    b.add(f"| {_subset(cell, spec)} | {label[r.arm]} | {measure.name} | ")
                    for i, field in enumerate(fields):
                        b.plant(f"{sid}.c{cell.index}.{r.arm}.{field}", _value(r, field, measure.decimals))
                        b.add(" | " if i < len(fields) - 1 else " |\n")
            b.add("\n")
    b.add("## Conclusion\n\n")
    for i, (key, word) in enumerate(study.claims.items()):
        if i:
            b.add(" ")
        b.plant(_fact_claim(sid, key, "conclusion"), _claim_sentence(spec, key, word))
    b.add(" " + rng.choice(CLOSERS) + "\n")
    return Paper(sid, "".join(b.parts), tuple(b.placements))


def missing_facts(paper: Paper, study: Study, spec: DomainSpec) -> list[str]:
    """Fact ids whose span does not hold the planted value, or that have no span at all. Empty means faithful."""
    spans = {pl.fact: paper.text[pl.start:pl.end] for pl in paper.placements}
    sid = study.id
    missing = []
    if spans.get(f"{sid}.setting") != study.setting:
        missing.append(f"{sid}.setting")
    for cell in study.cells:
        measure = spec.measure(cell.measure)
        for r in cell.results:
            for field in _fields(measure.kind):
                fact = f"{sid}.c{cell.index}.{r.arm}.{field}"
                if spans.get(fact) != _value(r, field, measure.decimals):
                    missing.append(fact)
    for key, word in study.claims.items():
        for place in ("abstract", "conclusion"):
            fact = _fact_claim(sid, key, place)
            if spans.get(fact) != _claim_sentence(spec, key, word):
                missing.append(fact)
    return missing
