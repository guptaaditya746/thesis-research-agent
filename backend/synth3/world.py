"""The hidden world of one domain: one law per (treatment, measure) pair, and the file Aditya approves."""
from __future__ import annotations

import json
import math
import os
import random
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from synth2.world import direction
from synth3.spec import DomainSpec

KINDS = ("none", "uniform", "one_sided", "opposed")
DEPENDS = ("one_sided", "opposed")
WORD = {"helps": "better", "hurts": "worse", "no_effect": "no different"}
CLAIM_WORDS = ("helps", "hurts", "no_effect")
MIN_PER_PAIR = 3   # control studies every covered pair needs
MAX_TRIES = 50     # noise attempts the gate may draw before it gives up
MAX_REDRAWS = 1000  # redraws of one cell whose numbers repeat an earlier cell's


@dataclass(frozen=True)
class PairLaw:
    treatment: str
    measure: str
    kind: str
    condition: str | None
    effects: dict[str, float]   # level id -> signed effect, positive = better (rate difference or relative change)

    def json(self) -> dict:
        return {"treatment": self.treatment, "measure": self.measure, "kind": self.kind,
                "condition": self.condition, "effects": dict(self.effects)}

    @classmethod
    def parse(cls, obj: Any, spec: DomainSpec) -> "PairLaw":
        try:
            law = cls(obj["treatment"], obj["measure"], obj["kind"], obj["condition"],
                      {str(k): float(v) for k, v in obj["effects"].items()})
        except (KeyError, TypeError, AttributeError, ValueError) as err:
            raise ValueError(f"law {obj!r}: unreadable ({err})") from err
        bad = sorted(lv for lv, e in law.effects.items() if not math.isfinite(e))
        if bad:
            raise ValueError(f"law {law.treatment}/{law.measure}: the effect for {bad} is not a finite number")
        law.check(spec)
        return law

    def check(self, spec: DomainSpec) -> None:
        where = f"law {self.treatment}/{self.measure}"
        if self.kind not in KINDS:
            raise ValueError(f"{where}: unknown kind '{self.kind}'; known: {', '.join(KINDS)}")
        if (self.treatment, self.measure) not in spec.pairs:
            raise ValueError(f"{where}: not a pair of this spec")
        if self.kind == "none":
            if self.condition is not None or self.effects:
                raise ValueError(f"{where}: kind 'none' does not fit its effects (it has no condition and no effects)")
            return
        condition = next((c for c in spec.conditions if c.id == self.condition), None)
        if condition is None:
            raise ValueError(f"{where}: unknown condition '{self.condition}'")
        levels = [lv.id for lv in condition.levels]
        if set(self.effects) != set(levels):
            raise ValueError(f"{where}: unknown level or missing level; effects must be for {levels}, "
                             f"got {sorted(self.effects)}")
        min_effect = spec.measure(self.measure).min_effect
        words = [direction(self.effects[lv], min_effect) for lv in levels]
        fits = {"uniform": words[0] == words[1] != "no_effect",
                "one_sided": words.count("no_effect") == 1,
                "opposed": sorted(words) == ["helps", "hurts"]}[self.kind]
        if not fits:
            raise ValueError(f"{where}: kind '{self.kind}' does not fit its effects {self.effects}")

    def answer(self, min_effect: float) -> tuple[str, str | None, dict[str, str]]:
        """(word, condition, sides): the word is helps/hurts/no_effect/depends; sides maps level id -> word."""
        if self.kind == "none":
            return "no_effect", None, {}
        sides = {lv: direction(e, min_effect) for lv, e in self.effects.items()}
        words = set(sides.values())
        if len(words) == 1:
            return words.pop(), None, {}
        return "depends", self.condition, sides


@dataclass(frozen=True)
class World:
    domain: str
    seed: int
    spec_sha256: str
    laws: tuple[PairLaw, ...]
    uncovered: tuple[tuple[str, str], ...]
    approved: bool

    def law(self, t: str, m: str) -> PairLaw:
        return next(l for l in self.laws if (l.treatment, l.measure) == (t, m))

    def json(self) -> dict:
        return {"domain": self.domain, "seed": self.seed, "spec_sha256": self.spec_sha256,
                "approved": self.approved, "laws": [l.json() for l in self.laws],
                "uncovered": [list(p) for p in self.uncovered]}

    @classmethod
    def parse(cls, obj: Any, spec: DomainSpec) -> "World":
        try:
            domain, seed, sha = obj["domain"], int(obj["seed"]), obj["spec_sha256"]
            raw_laws, raw_uncovered, approved = obj["laws"], obj["uncovered"], obj["approved"]
        except (KeyError, TypeError, ValueError) as err:
            raise ValueError(f"world: unreadable ({err})") from err
        if not isinstance(approved, bool):
            raise ValueError(f"world: approved must be true or false without quotes, got {approved!r}")
        if sha != spec.sha256 or domain != spec.domain:
            raise ValueError("world: spec_sha256 does not match the spec; the spec changed after the world was drawn")
        laws = tuple(PairLaw.parse(l, spec) for l in raw_laws)
        seen = [(l.treatment, l.measure) for l in laws]
        for p in spec.pairs:
            if seen.count(p) == 0:
                raise ValueError(f"world: pair {p[0]}/{p[1]} is missing")
            if seen.count(p) > 1:
                raise ValueError(f"world: pair {p[0]}/{p[1]} is doubled")
        try:
            uncovered = tuple((str(p[0]), str(p[1])) for p in raw_uncovered)
        except (TypeError, IndexError) as err:
            raise ValueError(f"world: uncovered must be a list of pairs ({err})") from err
        for p in uncovered:
            if p not in spec.pairs:
                raise ValueError(f"world: uncovered {p[0]}/{p[1]} is not a pair of this spec")
        return cls(domain, seed, sha, laws, uncovered, approved)


def _draw_law(spec: DomainSpec, t: str, m: str, kind: str, rng: random.Random) -> PairLaw:
    if kind == "none":
        return PairLaw(t, m, "none", None, {})
    measure = spec.measure(m)
    condition = rng.choice(spec.conditions)
    mirrored = rng.random() < 0.5    # which direction is "better"
    swapped = rng.random() < 0.5     # which level carries the first word
    words = {"uniform": ("helps", "helps"), "one_sided": ("helps", "no_effect"), "opposed": ("helps", "hurts")}[kind]
    if swapped:
        words = words[::-1]
    sign = {"helps": 1.0, "hurts": -1.0, "no_effect": 0.0}
    effects = {}
    for level, word in zip(condition.levels, words):
        size = round(rng.uniform(*measure.effect), 3) if sign[word] else 0.0
        effects[level.id] = size * sign[word] * (-1.0 if mirrored else 1.0) + 0.0   # + 0.0 turns -0.0 into 0.0
    return PairLaw(t, m, kind, condition.id, effects)


def draw_world(spec: DomainSpec, seed: int) -> World:
    laws = []
    for t, m in spec.pairs:
        rng = random.Random(f"synth3:{seed}:law:{t}:{m}")
        laws.append(_draw_law(spec, t, m, rng.choice(KINDS), rng))
    if not any(l.kind in DEPENDS for l in laws):
        t, m = spec.pairs[0]
        laws[0] = _draw_law(spec, t, m, "opposed", random.Random(f"synth3:{seed}:law:forced"))

    def depends(skip: tuple[str, str] | None) -> bool:
        return any(l.kind in DEPENDS for l in laws if (l.treatment, l.measure) != skip)

    uncovered: tuple[tuple[str, str], ...] = ()
    rng = random.Random(f"synth3:{seed}:uncovered")
    if rng.random() < spec.uncovered_rate:
        options = [p for p in spec.pairs if depends(p)]
        if options:
            uncovered = (rng.choice(options),)
    return World(spec.domain, seed, spec.sha256, tuple(laws), uncovered, False)


def save_world(path: Path, world: World) -> None:
    """Indented JSON so Aditya can read and edit it; written to a temporary file and renamed over `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(world.json(), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_world(path: Path, spec: DomainSpec) -> World:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ValueError(f"{path}: cannot read the world file ({err})") from err
    return World.parse(obj, spec)


def _effect_words(law: PairLaw, spec: DomainSpec) -> str:
    if law.kind == "none":
        return "no effect for anyone"
    condition = next(c for c in spec.conditions if c.id == law.condition)
    names = {lv.id: lv.name for lv in condition.levels}
    sides = law.answer(spec.measure(law.measure).min_effect)[2]
    if not sides:
        word = direction(next(iter(law.effects.values())), spec.measure(law.measure).min_effect)
        return f"{WORD[word]} for every {condition.name.lower()} ({condition.name} makes no split)"
    return f"split by {condition.name.lower()}: " + ", ".join(f"{WORD[w]} for {names[lv]}" for lv, w in sides.items())


def describe(world: World, spec: DomainSpec) -> str:
    """A plain-English table, one line per pair, then the uncovered pairs. Names only, never ids."""
    arm = {a.id: a.label for a in spec.arms}
    lines = [f"World of {spec.domain}, seed {world.seed} ({'approved' if world.approved else 'not approved yet'})", ""]
    for l in world.laws:
        lines.append(f"{arm[l.treatment]} on {spec.measure(l.measure).name}: {_effect_words(l, spec)}")
    lines.append("")
    if world.uncovered:
        lines.append("No study will cover: " + "; ".join(
            f"{arm[t]} on {spec.measure(m).name}" for t, m in world.uncovered))
    else:
        lines.append("Every pair is covered by studies.")
    return "\n".join(lines)


def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


@dataclass(frozen=True)
class ArmResult:
    """One arm in one cell: `k` of `n` for a count, or `mean` and `sd` of `n` for a value."""
    arm: str
    n: int
    k: int | None = None
    mean: float | None = None
    sd: float | None = None

    def __post_init__(self) -> None:
        n_ok = isinstance(self.n, int) and not isinstance(self.n, bool) and self.n > 0
        count = (isinstance(self.k, int) and not isinstance(self.k, bool) and self.mean is None and self.sd is None
                 and n_ok and 0 <= self.k <= self.n)
        value = self.k is None and _number(self.mean) and _number(self.sd) and self.sd >= 0
        if not (n_ok and (count or value)):
            raise ValueError(f"arm {self.arm}: a result is k of n, or a mean and SD of n; got "
                             f"n={self.n!r}, k={self.k!r}, mean={self.mean!r}, sd={self.sd!r}")

    def json(self) -> dict:
        return {"arm": self.arm, "n": self.n, "k": self.k, "mean": self.mean, "sd": self.sd}

    @classmethod
    def parse(cls, obj: Any) -> "ArmResult":
        return cls(obj["arm"], obj["n"], obj.get("k"), obj.get("mean"), obj.get("sd"))


@dataclass(frozen=True)
class Cell:
    index: int                        # study-wide, from 0
    measure: str
    levels: dict[str, str]            # every condition id -> level id
    results: tuple[ArmResult, ...]    # in the study's arm order

    def result(self, arm: str) -> ArmResult:
        found = next((r for r in self.results if r.arm == arm), None)
        if found is None:
            raise ValueError(f"cell {self.index}: no result for arm '{arm}'")
        return found

    def json(self) -> dict:
        return {"index": self.index, "measure": self.measure, "levels": dict(self.levels),
                "results": [r.json() for r in self.results]}

    @classmethod
    def parse(cls, obj: Any) -> "Cell":
        return cls(int(obj["index"]), obj["measure"], {str(k): str(v) for k, v in obj["levels"].items()},
                   tuple(ArmResult.parse(r) for r in obj["results"]))


@dataclass(frozen=True)
class Study:
    id: str
    label: str
    setting: str                      # the setting's name
    arms: tuple[str, ...]             # the control first when present; head to head: 2 treatments, no control
    measures: tuple[str, ...]
    cells: tuple[Cell, ...]
    claims: dict[str, str]            # "<arm>|<against>|<measure>" -> helps / hurts / no_effect
    overclaims: tuple[str, ...]       # the claim keys that exaggerate

    def __post_init__(self) -> None:
        if len(self.arms) < 2 or not self.cells:
            raise ValueError(f"study {self.id}: needs at least 2 arms and one cell")
        for c in self.cells:
            if c.measure not in self.measures or tuple(r.arm for r in c.results) != self.arms:
                raise ValueError(f"study {self.id}: cell {c.index} does not match the study's measures or arms")
        if any(w not in CLAIM_WORDS for w in self.claims.values()):
            raise ValueError(f"study {self.id}: a claim word must be one of {', '.join(CLAIM_WORDS)}")
        if any(self.claims.get(k) != "helps" for k in self.overclaims):
            raise ValueError(f"study {self.id}: every overclaim must be a claim that says helps")

    def json(self) -> dict:
        return {"id": self.id, "label": self.label, "setting": self.setting, "arms": list(self.arms),
                "measures": list(self.measures), "cells": [c.json() for c in self.cells],
                "claims": dict(self.claims), "overclaims": list(self.overclaims)}

    @classmethod
    def parse(cls, obj: Any) -> "Study":
        sid = obj.get("id", "?") if isinstance(obj, dict) else "?"
        try:
            return cls(obj["id"], obj["label"], obj["setting"], tuple(obj["arms"]), tuple(obj["measures"]),
                       tuple(Cell.parse(c) for c in obj["cells"]), dict(obj["claims"]), tuple(obj["overclaims"]))
        except (KeyError, TypeError, AttributeError, ValueError) as err:
            raise ValueError(f"study {sid}: unreadable ({err})") from err


def pair_delta(spec: DomainSpec, cells: Sequence[Cell], arm: str, against: str) -> float:
    """The pooled difference of `arm` over `against`, positive = better. Counts: rate minus rate. Values: the
    n-weighted mean of `arm` minus that of `against`, divided by the latter."""
    measures = {c.measure for c in cells}
    if len(measures) != 1:
        raise ValueError(f"pair_delta needs cells of exactly one measure, got {sorted(measures)}")
    measure = spec.measure(measures.pop())

    def pooled(name: str) -> float:
        results = [c.result(name) for c in cells]
        n = sum(r.n for r in results)
        if measure.kind == "count":
            return sum(r.k for r in results) / n
        return sum(r.mean * r.n for r in results) / n

    a, b = pooled(arm), pooled(against)
    if measure.kind == "value" and b == 0:
        raise ValueError(f"pair_delta: the pooled mean of '{against}' on {measure.id} is 0, so no relative change")
    delta = a - b if measure.kind == "count" else (a - b) / b
    return delta if measure.higher_is_better else -delta


@dataclass(frozen=True)
class _Design:
    label: str
    setting: str
    arms: tuple[str, ...]
    measures: tuple[str, ...]
    population: dict[str, str]        # every condition id -> the study's level
    split: str | None                 # the condition that gives 2 cells per measure
    n: int
    base: dict[str, float]            # measure id -> the control's true rate or mean


def _design(spec: DomainSpec, world: World, seed: int, sid: str, author: str, main: tuple[str, str],
            labels: set[str]) -> _Design:
    rng = random.Random(f"synth3:{seed}:{sid}:design")

    def covered(t: str, m: str) -> bool:
        return (t, m) not in world.uncovered

    t, m = main
    treatments, measures = [t], [m]
    rivals = [a.id for a in spec.treatments if a.id != t and covered(a.id, m)]
    head_to_head = rng.random() < spec.head_to_head_rate and bool(rivals)
    if head_to_head:
        treatments.append(rng.choice(rivals))
    if rng.random() < 0.4 and not head_to_head:
        extra = rng.choice([a.id for a in spec.treatments if a.id != t])
        if covered(extra, m):
            treatments.append(extra)
    if rng.random() < 0.4:
        extra = rng.choice([x.id for x in spec.measures if x.id != m])
        if all(covered(x, extra) for x in treatments):
            measures.append(extra)
    splittable = [c for c in spec.conditions if not c.from_setting]
    split = rng.choice(splittable).id if rng.random() < 0.5 and splittable else None
    drawn = {c.id: rng.choice(c.levels).id for c in splittable}
    setting = rng.choice(spec.settings)
    population = {c.id: setting.levels[c.id] if c.from_setting else drawn[c.id] for c in spec.conditions}
    low, high = spec.n_range
    n = rng.randrange(low, high + 1, spec.n_step)
    first, last = spec.years
    drawn_year = rng.randint(first, last)
    base = {x: rng.uniform(*(spec.measure(x).base_rate or spec.measure(x).base_value)) for x in measures}
    # a label names one study, so a surname already used in the drawn year moves to the next free year
    surname = author.split()[-1]
    span = last - first + 1
    label = next((lb for off in range(span)
                  if (lb := f"{surname} et al. ({first + (drawn_year - first + off) % span})") not in labels), None)
    if label is None:
        raise ValueError(f"study {sid}: every year from {first} to {last} already has a study by {surname}; "
                         "add authors or widen the years")
    arms = tuple(treatments) if head_to_head else (spec.control.id, *treatments)
    return _Design(label, setting.name, arms, tuple(measures), population, split, n, base)


def _true(spec: DomainSpec, world: World, arm: str, measure_id: str, levels: dict[str, str], base: float) -> float:
    """The arm's true rate or mean: the control's base plus the arm's law effect at the cell's level."""
    measure = spec.measure(measure_id)
    effect = 0.0
    if arm != spec.control.id:
        law = world.law(arm, measure_id)
        if law.kind != "none":
            effect = law.effects[levels[law.condition]]
    raw = effect if measure.higher_is_better else -effect
    if measure.kind == "count":
        return min(max(base + raw, 0.0), 1.0)
    return base * (1 + raw)


def _result(spec: DomainSpec, measure_id: str, arm: str, n: int, true: float, rng: random.Random) -> ArmResult:
    measure = spec.measure(measure_id)
    if measure.kind == "count":
        return ArmResult(arm, n, k=rng.binomialvariate(n, true))
    mean = round(rng.gauss(true, measure.spread * true / math.sqrt(n)), measure.decimals)
    # the reported SD follows the drawn mean, not the true one, so the SDs do not give the true means away
    return ArmResult(arm, n, mean=mean, sd=round(measure.spread * abs(mean), measure.decimals))


def _key(spec: DomainSpec, measure_id: str, by_arm: dict[str, ArmResult], arm: str, against: str) -> tuple:
    """The engine's duplicate key of one comparison: (metric, treatment value, control value) rounded to 3
    decimals (evidence/rules.VALUE_DECIMALS; the engine is not imported here)."""
    def value(r: ArmResult) -> float:
        return r.k / r.n if spec.measure(measure_id).kind == "count" else r.mean
    return measure_id, round(value(by_arm[arm]), 3), round(value(by_arm[against]), 3)


def draw_studies(spec: DomainSpec, world: World, seed: int, count: int, attempt: int = 0) -> tuple[Study, ...]:
    """`count` studies of the world. `attempt` changes only the count/value noise; the design stays the same."""
    if count > len(spec.authors):
        raise ValueError(f"{count} studies need {count} authors, the spec has {len(spec.authors)}")
    authors = list(spec.authors)
    random.Random(f"synth3:{seed}:authors").shuffle(authors)
    order = list(spec.pairs)
    random.Random(f"synth3:{seed}:pairs").shuffle(order)
    covered = [p for p in order if p not in world.uncovered]
    control = spec.control.id
    done: Counter[tuple[str, str]] = Counter()      # control studies per pair so far
    labels: set[str] = set()
    taken: set[tuple] = set()                       # the comparison keys of every cell so far
    studies = []
    for i in range(count):
        sid = f"S{i + 1:03d}"
        index = 0                                   # cell index, study-wide
        main = min(covered, key=lambda p: done[p])  # the first in the shuffled order among the fewest
        d = _design(spec, world, seed, sid, authors[i], main, labels)
        labels.add(d.label)
        split = next((c for c in spec.conditions if c.id == d.split), None)
        cells = []
        compared = [(t, control) for t in d.arms[1:]] if d.arms[0] == control else [(d.arms[0], d.arms[1])]
        for m in d.measures:
            for level in [lv.id for lv in split.levels] if split else [None]:
                levels = {**d.population, **({split.id: level} if split else {})}
                trues = [_true(spec, world, arm, m, levels, d.base[m]) for arm in d.arms]
                # the engine merges two results with the same metric and treatment and control values as one study
                # published twice (n and any other arm do not count), so no comparison may repeat an earlier one
                for j in range(MAX_REDRAWS + 1):
                    again = f":again{j}" if j else ""
                    results = tuple(
                        _result(spec, m, arm, d.n, true,
                                random.Random(f"synth3:{seed}:{attempt}:{sid}:c{index}:{arm}{again}"))
                        for arm, true in zip(d.arms, trues))
                    keys = [_key(spec, m, {r.arm: r for r in results}, a, b) for a, b in compared]
                    if len(set(keys)) == len(keys) and taken.isdisjoint(keys):
                        break
                else:
                    raise ValueError(f"study {sid}, cell {index}, measure {m}: {MAX_REDRAWS} redraws all repeat "
                                     "an earlier cell's numbers; give the measure more decimals or larger values")
                taken.update(keys)
                cells.append(Cell(index, m, levels, results))
                index += 1
        pairs = compared
        claims = {f"{arm}|{against}|{m}":
                  direction(pair_delta(spec, [c for c in cells if c.measure == m], arm, against),
                            spec.measure(m).min_effect)
                  for arm, against in pairs for m in d.measures}
        overclaims: tuple[str, ...] = ()
        rng = random.Random(f"synth3:{seed}:{sid}:claims")
        if rng.random() < spec.overclaim_rate:
            options = [k for k, w in claims.items() if w != "helps"]
            if options:
                key = rng.choice(options)
                claims[key], overclaims = "helps", (key,)
        if d.arms[0] == control:
            done.update((t, m) for t in d.arms[1:] for m in d.measures)
        studies.append(Study(sid, d.label, d.setting, d.arms, d.measures, tuple(cells), claims, overclaims))
    short = [f"{t}|{m} has {done[(t, m)]}" for t, m in covered if done[(t, m)] < MIN_PER_PAIR]
    if short:
        raise ValueError(f"fewer than {MIN_PER_PAIR} studies: {', '.join(short)}; draw more studies")
    return tuple(studies)
