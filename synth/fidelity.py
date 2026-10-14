"""Fidelity checks: does a rendered paper state exactly the facts of its plan, where the placements say?

Run on every paper of every renderer (the template passes by construction; the checks prove it and guard
against regressions) and, for the LLM renderer, after every attempt, whose failure reasons go into the
next attempt. A paper that never passes is reported in fidelity.json and excluded, never dropped silently.
"""
from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field

from pydantic import BaseModel

from agent import anchor
from synth import levelcheck
from synth.levels import Plan, parse_value
from synth.text import Decoy, Placement

NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
TOLERANCE = 0.005      # evaluation's value tolerance; a blind re-extraction must land within it


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class PaperFidelity:
    """One paper's fidelity record (fidelity.json): `attempts` renderings were tried; `history` keeps
    the failed checks of each attempt that did not pass."""
    id: str
    ok: bool
    checks: list[Check]
    attempts: int = 1
    history: list[dict] = field(default_factory=list)
    excluded_reason: str | None = None

    def json(self) -> dict:
        out = asdict(self)
        if out["excluded_reason"] is None:
            del out["excluded_reason"]
        return out


def _check(name: str, problems: list[str]) -> Check:
    return Check(name, not problems, "; ".join(problems[:10]) + (" ..." if len(problems) > 10 else ""))


def facts_rendered(plan: Plan, ps: list[Placement]) -> list[str]:
    """Every fact of the plan has at least one rendering of its role."""
    have = {(p.fact, p.role) for p in ps}
    want = [(m.id, "value") for m in plan.measurements] + [(c.id, "condition_label") for c in plan.conditions]
    want += [(k.id, "metric_label") for k in plan.metrics] + [(f"{plan.paper}.a1", "claim")]
    return [f"{fact} has no {role} rendering" for fact, role in want if (fact, role) not in have]


def anchored(text: str, ps: list[Placement]) -> list[str]:
    """Each placement holds its exact text and anchor.find, given its context, lands on it and nowhere else."""
    index = anchor.Index(text)
    bad = []
    for p in ps:
        if text[p.start:p.end] != p.exact:
            bad.append(f"{p.fact}/{p.role}: offsets [{p.start}, {p.end}) do not hold {p.exact!r}")
            continue
        try:
            sel = anchor.find(index, p.exact, prefix=text[max(0, p.start - anchor.CONTEXT):p.start],
                              suffix=text[p.end:p.end + anchor.CONTEXT])
        except anchor.AnchorError as exc:
            bad.append(f"{p.fact}/{p.role} {p.exact!r}: {exc.reason}")
            continue
        if (sel.start, sel.end) != (p.start, p.end):
            bad.append(f"{p.fact}/{p.role} {p.exact!r}: found at {sel.start}, placed at {p.start}")
    return bad


def values_match(plan: Plan, ps: list[Placement]) -> list[str]:
    """Each value rendering states its fact's value (a relative one, relative to the baseline)."""
    study, bad = plan.study, []
    base = study.value_of(study.effect.baseline)
    for p in ps:
        if p.role != "value":
            continue
        try:
            got = parse_value(p.exact, p.fmt or "frac", base)
        except (ValueError, IndexError):
            bad.append(f"{p.fact}: cannot read {p.exact!r}")
            continue
        if abs(got - study.value_of(p.fact)) > 1e-9:
            bad.append(f"{p.fact}: {p.exact!r} reads {got}, truth {study.value_of(p.fact)}")
    return bad


def values_unique(text: str, ps: list[Placement]) -> list[str]:
    """A value string occurs only where it is placed: no second, unrecorded copy."""
    index, bad = anchor.Index(text), []
    for exact in sorted({p.exact for p in ps if p.role == "value"}):
        placed = sum(1 for p in ps if p.role == "value" and p.exact == exact)
        found = len(index.spans(anchor.normalize(exact)))
        if found != placed:
            bad.append(f"{exact!r} occurs {found} times, placed {placed}")
    return bad


def labels_covered(text: str, plan: Plan, ps: list[Placement]) -> list[str]:
    """Every occurrence of a condition or metric name is a recorded rendering of that fact."""
    names = [(c, plan.cond_name[c]) for c in plan.cond_name] + [(c, a) for c, al in plan.cond_aliases.items() for a in al]
    names += [(k, plan.metric_name[k]) for k in plan.metric_name] + [
        (k, a) for k, al in plan.metric_aliases.items() for a in al]
    spans = {(p.fact, p.start, p.end) for p in ps}
    bad = []
    for fact, name in names:
        for a, b in levelcheck.occurs(text, name):
            if not any(f == fact and s <= a and b <= e for f, s, e in spans):
                bad.append(f"{fact}: unrecorded {text[a:b]!r} at {a}")
    return bad


def stray_numbers(text: str, plan: Plan, ps: list[Placement], decoys: list[Decoy]) -> list[str]:
    """A number outside every value placement and decoy that reads as one of the study's values (as is,
    as percent or as a count of 1,000) would mislead an extractor."""
    covered = [(p.start, p.end) for p in ps if p.role == "value"] + [(d.start, d.end) for d in decoys]
    truth = {round(m.value, 6): m.id for m in plan.study.measurements}
    bad = []
    for m in NUMBER.finditer(text):
        if any(a <= m.start() and m.end() <= b for a, b in covered):
            continue
        x = float(m.group().replace(",", ""))
        hits = {truth[c] for c in (round(x, 6), round(x / 100, 6), round(x / 1000, 6)) if c in truth}
        if hits:
            bad.append(f"{m.group()!r} at {m.start()} reads as {sorted(hits)}")
    return bad


def check_paper(text: str, plan: Plan, ps: list[Placement], decoys: list[Decoy]) -> list[Check]:
    return [
        Check("lf_only", "\r" not in text, "carriage return in text" if "\r" in text else ""),
        _check("facts_rendered", facts_rendered(plan, ps)),
        _check("anchored", anchored(text, ps)),
        _check("values_match", values_match(plan, ps)),
        _check("values_unique", values_unique(text, ps)),
        _check("labels_covered", labels_covered(text, plan, ps)),
        _check("stray_numbers", stray_numbers(text, plan, ps, decoys)),
        _check(f"level_{plan.level}", levelcheck.check_level(text, plan, ps, decoys)),
    ]


class BlindMeasurement(BaseModel):
    condition: str
    metric: str
    dataset: str
    value: float


class BlindExtraction(BaseModel):
    measurements: list[BlindMeasurement]


BlindExtractor = Callable[[str], Awaitable[BlindExtraction]]


async def blind_check(text: str, plan: Plan, extract: BlindExtractor) -> Check:
    """A model that never saw the plan reads the paper; every planned value must come back (within the
    evaluation tolerance). Extra values (a decoy, a computed relative value) are reported, not failed."""
    values = [g.value for g in (await extract(text)).measurements]

    def near(v: float, truth: float) -> bool:      # a percent the model did not convert still counts
        return abs(v - truth) <= TOLERANCE or abs(v / 100 - truth) <= TOLERANCE

    missing = [m.id for m in plan.measurements if not any(near(v, m.value) for v in values)]
    extra = [v for v in values if not any(near(v, m.value) for m in plan.measurements)]
    detail = (f"missing {missing}" if missing else "all values recovered") + (f"; extra {extra}" if extra else "")
    return Check("blind_reextraction", not missing, detail)
