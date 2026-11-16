"""The hidden world of one domain: one law per (treatment, measure) pair, and the file Aditya approves."""
from __future__ import annotations

import json
import os
import random
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from synth2.world import direction
from synth3.spec import DomainSpec

KINDS = ("none", "uniform", "one_sided", "opposed")
DEPENDS = ("one_sided", "opposed")
WORD = {"helps": "better", "hurts": "worse", "no_effect": "no different"}


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
            raw_laws, raw_uncovered, approved = obj["laws"], obj["uncovered"], bool(obj["approved"])
        except (KeyError, TypeError, ValueError) as err:
            raise ValueError(f"world: unreadable ({err})") from err
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
