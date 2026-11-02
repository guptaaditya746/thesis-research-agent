"""Fidelity checks: does a rendered paper state exactly the facts of its plan, where the placements say?

Run on every paper of every renderer (the template passes by construction; the checks prove it and guard
against regressions) and, for the LLM renderer, after every attempt, whose failure reasons go into the
next attempt. A paper that never passes is reported in fidelity.json and excluded, never dropped silently.
"""
from __future__ import annotations

import functools
import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, create_model

from agent import anchor
from evidence.extractors import base as extractor_base
from synth import assoc, levelcheck
from synth.levels import DEPENDENCY_SECTION, LIMITATION_SECTION, Plan, Written, parse_value, written
from synth.recipe import REUSES, Recipe, default_recipe
from synth.text import TRUTH_TYPES, Decoy, Placement
from synth.truth import DECOY_GAP

NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
TOLERANCE = 0.005      # evaluation's value tolerance; a blind re-extraction must land within it
# Numbers any paper may hold outside its value placements and decoys (`added_numbers`, docs/evidence-system.md
# G.2): numbered tables, sections and figures, Markdown list markers; the recipe adds its own
# (`reporting.allowed_numbers`, e.g. the dataset size). The relative "N.N percentage points" string is a value
# placement itself; condition codes with a digit (A1) are allowed by name.
GENERIC_NUMBERS = r"\b(?:Table|Section|Figure|Appendix|Equation)\s+\d+\b|(?m:^\s*\d+[.)]\s)"


@functools.cache
def _allowed_numbers(patterns: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile("|".join([*patterns, GENERIC_NUMBERS]))


def allowed_numbers(recipe: Recipe) -> re.Pattern[str]:
    """The numbers a paper of `recipe` may hold outside its placements: the recipe's, then the generic ones."""
    return _allowed_numbers(tuple(recipe.reporting.allowed_numbers))


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class PaperFidelity:
    """One paper's fidelity record (fidelity.json): `attempts` renderings were tried; `history` keeps
    the failed checks of each attempt that did not pass; `statements` (LLM renderer with statements only)
    is {"rounds": statement calls, "failed": task ids never accepted}."""
    id: str
    ok: bool
    checks: list[Check]
    attempts: int = 1
    history: list[dict] = field(default_factory=list)
    excluded_reason: str | None = None
    statements: dict | None = None

    def json(self) -> dict:
        out = asdict(self)
        for key in ("excluded_reason", "statements"):
            if out[key] is None:
                del out[key]
        return out


def _check(name: str, problems: list[str]) -> Check:
    return Check(name, not problems, "; ".join(problems[:10]) + (" ..." if len(problems) > 10 else ""))


def facts_rendered(plan: Plan, ps: list[Placement]) -> list[str]:
    """Every fact of the plan has at least one rendering of its type's main role: the fact types and their roles are
    the ground truth's (`text.TRUTH_TYPES`, ground_truth.json `types`), the facts of each type the plan's."""
    have = {(p.fact, p.role) for p in ps}
    want = [(fact, t["main_role"]) for t in TRUTH_TYPES.values() for fact in plan.facts(t["list"])]
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
    """Each value rendering states its fact's value (a relative one, relative to the control value): it reads as the
    truth written in its format reads (a count k of n exactly; a percent to its tenth, which for a value in thousandths
    is the truth itself)."""
    study, bad = plan.study, []
    base = study.value_of(study.effect.control) if study.effect.control else None   # None: --missing, irrelevant
    for p in ps:
        if p.role != "value":
            continue
        fmt = p.fmt or "frac"
        m = next(x for x in study.measurements if x.id == p.fact)
        try:
            got = parse_value(p.exact, fmt, base)
            want = parse_value(written(study, m, fmt, base), fmt, base)
        except (ValueError, IndexError, KeyError, TypeError):
            bad.append(f"{p.fact}: cannot read {p.exact!r}")
            continue
        if abs(got - want) > 1e-9:
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
    """Every rendering of a condition or metric name (levelcheck.renderings: codes and abbreviations only
    in tables and definitions) is a recorded placement of that fact."""
    spans = {(p.fact, p.start, p.end) for p in ps}
    return [f"{fact}: unrecorded {text[a:b]!r} at {a}" for fact, _, a, b, _ in levelcheck.renderings(text, plan)
            if not any(f == fact and s <= a and b <= e for f, s, e in spans)]


def stray_numbers(text: str, plan: Plan, ps: list[Placement], decoys: list[Decoy]) -> list[str]:
    """A number outside every value placement and decoy that reads as one of the study's values (as is,
    as percent or as a count of the recipe's `count_base`) would mislead an extractor."""
    covered = [(p.start, p.end) for p in ps if p.role == "value"] + [(d.start, d.end) for d in decoys]
    truth = {round(m.value, 6): m.id for m in plan.study.measurements}
    bases = [1, 100] + ([plan.recipe.reporting.count_base] if plan.recipe.reporting.count_base else [])
    bad = []
    for m in NUMBER.finditer(text):
        if any(a <= m.start() and m.end() <= b for a, b in covered):
            continue
        x = float(m.group().replace(",", ""))
        hits = {truth[c] for c in (round(x / base, 6) for base in bases) if c in truth}
        if hits:
            bad.append(f"{m.group()!r} at {m.start()} reads as {sorted(hits)}")
    return bad


def values_apart(plan: Plan) -> list[str]:
    """The study's true values (in the units they are scored in) are pairwise more than DECOY_GAP apart,
    so no value matches another fact within the evaluation tolerance."""
    ms = sorted(plan.study.measurements, key=lambda m: m.value)
    return [f"{a.id}={a.value} and {b.id}={b.value} are within {DECOY_GAP}"
            for a, b in zip(ms, ms[1:]) if b.value - a.value <= DECOY_GAP]


def _around(text: str, start: int, end: int, width: int = 30) -> str:
    return text[max(0, start - width):end + width].replace("\n", " / ")


def added_numbers(text: str, plan: Plan, ps: list[Placement], decoys: list[Decoy]) -> list[str]:
    """No number outside the value placements, the decoys and `allowed_numbers` (plus the condition codes with a
    digit, A1: the recipe's `other_codes`, the plan's aliases and its name variants, such as a code name ZV-217): a
    paper that adds a number adds a result the ground truth does not have (the writer prompt's rule 3). Each offending
    number is reported with its offset and context."""
    covered = [(p.start, p.end) for p in ps if p.role == "value"] + [(d.start, d.end) for d in decoys]
    covered += [(m.start(), m.end()) for m in allowed_numbers(plan.recipe).finditer(text)]
    codes = set(plan.recipe.other_codes) | {a for aliases in plan.cond_aliases.values() for a in aliases}
    codes |= {form for _, form in plan.variants.values()}
    for code in sorted(codes):
        if any(ch.isdigit() for ch in code):
            covered += levelcheck.occurs(text, code)
    return [f"{m.group()!r} at {m.start()}: {_around(text, m.start(), m.end())!r}" for m in NUMBER.finditer(text)
            if not any(a <= m.start() and m.end() <= b for a, b in covered)]


def added_claims(text: str, plan: Plan, ps: list[Placement]) -> list[str]:
    """No sentence outside the claim placements names the question's subject and states an effect: it matches the
    recipe's `text.claim_subject` and one of its `text.claim_cues` (the generator's own copy of the claim wording,
    never the engine's words.yaml), over the regex extractor's sentence split. A second statement on whether
    the method helps would be a second author claim (the writer prompt's rule 4). A recipe without the two
    regexes is refused: the check would pass every paper."""
    t = plan.recipe.text
    if not t.claim_subject or not t.claim_cues:
        raise ValueError(f"the recipe of {plan.recipe.domain} has no text.claim_subject or text.claim_cues for the "
                         "added_claims check")
    claims = [(p.start, p.end) for p in ps if p.role == "claim"]
    bad = []
    for a, b in extractor_base.sentences(text):
        if any(a < e and s < b for s, e in claims):
            continue
        sentence = text[a:b]
        if re.search(t.claim_subject, sentence) and any(re.search(p, sentence) for p in t.claim_cues):
            bad.append(f"{sentence!r} at {a}")
    return bad


def sentences_placed(text: str, ps: list[Placement], planned: tuple[Written, ...], role: str,
                     section: str) -> list[str]:
    """Each planned sentence occurs exactly once in the text, verbatim, placed as its fact's `role` rendering, in the
    '## `section`' section."""
    index, bad = anchor.Index(text), []
    for x in planned:
        found = len(index.spans(anchor.normalize(x.sentence)))
        if found != 1:
            bad.append(f"{x.id}: {x.sentence!r} occurs {found} times, not once")
            continue
        placed = [p for p in ps if p.fact == x.id and p.role == role]
        if not placed:
            bad.append(f"{x.id}: {x.sentence!r} is not placed as its {role}")
        elif levelcheck.section_at(text, placed[0].start) != section:
            bad.append(f"{x.id}: {x.sentence!r} is in {levelcheck.section_at(text, placed[0].start)!r}, not {section!r}")
    return bad


def limitations_placed(text: str, plan: Plan, ps: list[Placement]) -> list[str]:
    """Each planted limitation sentence is in the Discussion, once (`sentences_placed`)."""
    return sentences_placed(text, ps, plan.limitations, "limitation", LIMITATION_SECTION)


def dependencies_placed(text: str, plan: Plan, ps: list[Placement]) -> list[str]:
    """Each dependency sentence (the builds_on preset) is in the Method, once (`sentences_placed`)."""
    return sentences_placed(text, ps, plan.dependencies, "dependency", DEPENDENCY_SECTION)


def check_paper(text: str, plan: Plan, ps: list[Placement], decoys: list[Decoy]) -> list[Check]:
    return [
        _check("values_apart", values_apart(plan)),
        Check("lf_only", "\r" not in text, "carriage return in text" if "\r" in text else ""),
        _check("facts_rendered", facts_rendered(plan, ps)),
        _check("anchored", anchored(text, ps)),
        _check("values_match", values_match(plan, ps)),
        _check("values_unique", values_unique(text, ps)),
        _check("values_associated", assoc.associations(text, plan, ps)),
        _check("labels_covered", labels_covered(text, plan, ps)),
        _check("stray_numbers", stray_numbers(text, plan, ps, decoys)),
        _check("added_numbers", added_numbers(text, plan, ps, decoys)),
        _check("added_claims", added_claims(text, plan, ps)),
        _check("limitations_placed", limitations_placed(text, plan, ps)),
        _check("dependencies_placed", dependencies_placed(text, plan, ps)),
        _check(f"level_{plan.level}" if plan.study.relevant else "irrelevant",
               levelcheck.check_level(text, plan, ps, decoys)),
    ]


@functools.cache
def _blind_model(context: str, categories: tuple[str, ...] | None, cites: bool) -> type[BaseModel]:
    measurement = create_model("BlindMeasurement", condition=(str, ...), metric=(str, ...), **{context: (str, ...)},
                               value=(float, ...))
    fields: dict[str, Any] = {"measurements": (list[measurement], ...)}
    if categories is not None:
        limitation = create_model("BlindLimitation", condition=(str, ...), category=(Literal[categories], ...))
        fields["limitations"] = (list[limitation], ...)
    if cites:
        cite = create_model("BlindCite", label=(str, ...), reuses=(Literal[REUSES], ...))
        fields["cites"] = (list[cite], ...)
    return create_model("BlindExtraction", **fields)


def blind_model(recipe: Recipe) -> type[BaseModel]:
    """The reply schema of the blind reader for papers of `recipe`, from its schema: `measurements` [{condition,
    metric, <the recipe's context: dataset or population>, value}]; with planted limitations, `limitations`
    [{condition, category}], the category one of the recipe's; with the builds_on block, `cites` [{label, reuses}],
    reuses one of method, dataset, result. The thing is called `condition`, as the rag recipe's blind examples call it
    (they are pinned with the recipe). For the rag recipe this is the schema the blind reader always had, so its
    prompt hash does not move."""
    lim = recipe.limitations
    return _blind_model(recipe.context, tuple(lim.categories) if lim is not None else None, recipe.builds_on is not None)


# The default pack's reply schema (and its measurement), as before the schema came from the recipe.
BlindExtraction = blind_model(default_recipe())
BlindMeasurement = BlindExtraction.model_fields["measurements"].annotation.__args__[0]
BlindExtractor = Callable[[str], Awaitable[BaseModel]]


def _norm(name: str) -> str:
    name = " ".join(name.lower().split())
    return name[4:] if name.startswith("the ") else name


def names_condition(reported: str, plan: Plan, cid: str) -> bool:
    """The reported condition is this condition: one of its names in the paper (or its code) exactly, or,
    for a name longer than a code, containing it or contained in it."""
    got = _norm(reported)
    for name in (plan.cond_name[cid], *plan.cond_aliases[cid]):
        n = _norm(name)
        if got == n or (len(n) > 3 and len(got) > 3 and (n in got or got in n)):
            return True
    return False


def names_metric(got: str, plan: Plan, metric_id: str) -> bool:
    """The reported metric is this metric: its name in the paper, an alias or its abbreviation, any case."""
    names = (plan.metric_name[metric_id], plan.metric_of(metric_id).abbr, *plan.metric_aliases[metric_id])
    return _norm(got) in {_norm(n) for n in names}


def names_dataset(got: str, dataset: str) -> bool:
    return _norm(got) == _norm(dataset)


def planned_extras(plan: Plan) -> list[tuple[str, float]]:
    """(condition id, value) pairs a blind reader may report besides the measurements: the decoy (a stated
    wrong treatment value) and the relative difference the complex level writes, read as a value."""
    out = []
    if plan.decoy is not None:
        out.append((next(m.condition for m in plan.measurements if m.id == plan.decoy.measurement), plan.decoy.stated_value))
    e = plan.study.effect
    if e.treatment and e.control and any(v.fmt == "relative" for v in plan.values.values()):
        out.append((next(m.condition for m in plan.measurements if m.id == e.treatment),
                    abs(round(plan.study.value_of(e.treatment) - plan.study.value_of(e.control), 6))))
    return out


async def blind_check(text: str, plan: Plan, extract: BlindExtractor) -> list[Check]:
    """A model that never saw the plan reads the paper (its reply follows `blind_model` of the plan's recipe).

    - `blind_reextraction`: every planned measurement comes back whole, in one reply: the value within the
      evaluation tolerance, the condition, the metric and the context (dataset or population), so a value written
      next to the wrong condition, metric or context fails (the detail names the first failing field of the closest
      reply).
    - `blind_extra`: nothing else comes back, except the decoy and the relative difference, which the paper does
      state (condition and value only: they have no metric or context); an extra measurement is a result the ground
      truth does not have (docs/evidence-system.md G.2).
    - `blind_limitations`: every planted limitation comes back, its thing (`names_condition`) and its category exact.
    - `blind_dependencies`: every dependency comes back as a cite whose label is the cited study's label, exactly.
    A recipe that plants no limitations or dependencies (rag) passes the last two with nothing to find."""
    reply = await extract(text)
    got, context = reply.measurements, plan.recipe.context

    def near(v: float, truth: float) -> bool:      # a percent the model did not convert still counts
        return abs(v - truth) <= TOLERANCE or abs(v / 100 - truth) <= TOLERANCE

    def matches(g: BaseModel, condition: str, value: float) -> bool:
        return near(g.value, value) and names_condition(g.condition, plan, condition)

    def first_failure(g: BaseModel, m) -> int:   # index of the first failing field; 4 = none
        checks = (near(g.value, m.value), names_condition(g.condition, plan, m.condition),
                  names_metric(g.metric, plan, m.metric), names_dataset(getattr(g, context), m.dataset))
        return next((i for i, ok in enumerate(checks) if not ok), 4)

    fields = ("value", "condition", "metric", context)
    missing = []
    for m in plan.measurements:
        best = max((first_failure(g, m) for g in got), default=0)
        if best < 4:
            missing.append(f"{m.id} ({fields[best]})")
    allowed = [(m.condition, m.value) for m in plan.measurements] + planned_extras(plan)
    extra = [(g.condition, g.value) for g in got if not any(matches(g, c, v) for c, v in allowed)]
    limitations, cites = getattr(reply, "limitations", []), getattr(reply, "cites", [])
    lost = [f"{x.id} ({x.category})" for x in plan.limitations
            if not any(g.category == x.category and names_condition(g.condition, plan, x.thing) for g in limitations)]
    unread = [f"{d.id} ({d.label})" for d in plan.dependencies if not any(c.label.strip() == d.label for c in cites)]
    return [Check("blind_reextraction", not missing, f"missing {missing}" if missing else "all values recovered"),
            Check("blind_extra", not extra, f"extra {extra}" if extra else "nothing beyond the plan"),
            Check("blind_limitations", not lost, f"missing {lost}" if lost else "all limitations recovered"),
            Check("blind_dependencies", not unread, f"missing {unread}" if unread else "all cited studies recovered")]
