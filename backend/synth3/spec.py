"""The spec of one domain: arms, measures, conditions, settings and the number ranges a world is drawn from."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import ValidationError, model_validator

from jsonio import sha256_hex
from repo_paths import DATA
from synth2.recipe import Level, Strict

SPECS = DATA / "synth3"
MIN_AUTHORS = 40   # one author per study at 40 studies per folder


class ArmSpec(Strict):
    id: str
    label: str
    description: str
    control: bool = False


class Measure(Strict):
    id: str
    name: str
    kind: Literal["count", "value"]
    higher_is_better: bool
    effect: tuple[float, float]       # count: rate difference; value: relative change (0.10 = 10%)
    min_effect: float
    min_gap: float
    unit: str
    outcome: str | None = None                          # count: "{k} of {n} {unit} {outcome}"
    base_rate: tuple[float, float] | None = None        # count
    base_value: tuple[float, float] | None = None       # value
    spread: float | None = None                         # value: SD as a share of the mean
    decimals: int | None = None                         # value: 0-2

    @model_validator(mode="after")
    def _check(self) -> "Measure":
        where = f"measure {self.id}"
        if self.effect[0] > self.effect[1]:
            raise ValueError(f"{where}: effect must be ascending")
        if not 0 < self.min_effect <= self.effect[0]:
            raise ValueError(f"{where}: min_effect must be above 0 and at most the smallest effect")
        if not 0 < self.min_gap <= self.effect[0]:
            raise ValueError(f"{where}: min_gap must be above 0 and at most the smallest effect")
        if self.kind == "count":
            if self.outcome is None or self.base_rate is None:
                raise ValueError(f"{where}: a count measure needs outcome and base_rate")
            if self.base_rate[0] > self.base_rate[1]:
                raise ValueError(f"{where}: base_rate must be ascending")
            if self.base_rate[0] - self.effect[1] < 0 or self.base_rate[1] + self.effect[1] > 1:
                raise ValueError(f"{where}: base_rate plus or minus the largest effect must stay between 0 and 1")
        else:
            if self.base_value is None or self.spread is None or self.decimals is None:
                raise ValueError(f"{where}: a value measure needs base_value, spread and decimals")
            if not 0 < self.base_value[0] <= self.base_value[1]:
                raise ValueError(f"{where}: base_value must be positive and ascending")
            if self.spread <= 0:
                raise ValueError(f"{where}: spread must be above 0")
            if not 0 <= self.decimals <= 2:
                raise ValueError(f"{where}: decimals must be 0 to 2")
            if self.effect[1] >= 1:
                raise ValueError(f"{where}: a relative effect must stay below 1")
        return self


class Condition(Strict):
    id: str
    name: str
    levels: list[Level]
    from_setting: bool = False


class Setting(Strict):
    name: str
    levels: dict[str, str]   # from_setting condition id -> level id


class DomainSpec(Strict):
    domain: str
    field: str
    arms: list[ArmSpec]
    measures: list[Measure]
    conditions: list[Condition]
    settings: list[Setting]
    n_range: tuple[int, int]
    n_step: int
    head_to_head_rate: float
    overclaim_rate: float
    uncovered_rate: float
    authors: list[str]
    years: tuple[int, int]
    sha256: str

    @property
    def control(self) -> ArmSpec:
        return next(a for a in self.arms if a.control)

    @property
    def treatments(self) -> list[ArmSpec]:
        return [a for a in self.arms if not a.control]

    @property
    def pairs(self) -> list[tuple[str, str]]:
        return [(a.id, m.id) for a in self.treatments for m in self.measures]

    def measure(self, id: str) -> Measure:
        return next(m for m in self.measures if m.id == id)

    def names(self) -> list[str]:
        """Every arm label, measure name, condition name, level name and setting name."""
        return [*(a.label for a in self.arms), *(m.name for m in self.measures),
                *(c.name for c in self.conditions), *(lv.name for c in self.conditions for lv in c.levels),
                *(s.name for s in self.settings)]

    @model_validator(mode="after")
    def _check(self) -> "DomainSpec":
        if len(self.arms) < 3:
            raise ValueError("arms: need at least 3 arms")
        if sum(a.control for a in self.arms) != 1:
            raise ValueError("arms: exactly one control arm")
        if len(self.measures) < 3:
            raise ValueError("measures: need at least 3 measures")
        if len(self.conditions) < 2 or any(len(c.levels) != 2 for c in self.conditions):
            raise ValueError("conditions: at least 2 conditions with exactly 2 levels each")
        level_ids = [lv.id for c in self.conditions for lv in c.levels]
        ids = [a.id for a in self.arms] + [m.id for m in self.measures] + [c.id for c in self.conditions] + level_ids
        if len(set(ids)) != len(ids):
            raise ValueError("ids: arm, measure, condition and level ids must all be different")
        self._check_settings()
        names = self.names()
        for i, a in enumerate(names):
            for j, b in enumerate(names):
                if i != j and a.lower() in b.lower():
                    raise ValueError(f"names: '{a}' is inside '{b}', so the text would be ambiguous")
        for field in ("head_to_head_rate", "overclaim_rate", "uncovered_rate"):
            if not 0 <= getattr(self, field) <= 1:
                raise ValueError(f"{field}: must be between 0 and 1")
        for field in ("n_range", "years"):
            if getattr(self, field)[0] > getattr(self, field)[1]:
                raise ValueError(f"{field}: must be ascending")
        if self.n_step <= 0 or self.n_range[0] <= 0 or any(n % self.n_step for n in self.n_range):
            raise ValueError("n_range: both ends must be positive multiples of n_step")
        if len(self.authors) < MIN_AUTHORS or len(set(self.authors)) != len(self.authors):
            raise ValueError(f"authors: need at least {MIN_AUTHORS} different names, got {len(self.authors)}")
        self._check_text(set(level_ids))
        return self

    def _check_settings(self) -> None:
        wanted = {c.id: {lv.id for lv in c.levels} for c in self.conditions if c.from_setting}
        if not self.settings:
            raise ValueError("settings: need at least one setting")
        for s in self.settings:
            if set(s.levels) != set(wanted) or any(s.levels[c] not in wanted[c] for c in s.levels):
                raise ValueError(f"setting '{s.name}': must give one known level for each of {sorted(wanted)}")
        for c, levels in wanted.items():
            unused = levels - {s.levels[c] for s in self.settings}
            if unused:
                raise ValueError(f"settings: no setting uses the level {sorted(unused)} of condition {c}")

    def _check_text(self, level_ids: set[str]) -> None:
        """Everything the writer puts into a paper: no digits, no table bar, no line break, never empty, and no
        level id as a word of its own."""
        texts: dict[str, str] = {"field": self.field}
        for a in self.arms:
            texts[f"arm {a.id}"] = f"{a.label} {a.description}"
        for m in self.measures:
            texts[f"measure {m.id}"] = f"{m.name} {m.unit} {m.outcome or ''}"
        for c in self.conditions:
            texts[f"condition {c.id}"] = " ".join([c.name, *(lv.name for lv in c.levels)])
        for i, s in enumerate(self.settings):
            texts[f"setting {i + 1}"] = s.name
        for i, a in enumerate(self.authors):
            texts[f"author {i + 1}"] = a
        for where, text in texts.items():
            if not text.strip():
                raise ValueError(f"{where}: must not be empty")
            if any(ch.isdigit() for ch in text):
                raise ValueError(f"{where}: '{text}' holds a digit; only planted counts may be digits in a paper")
            if "|" in text or "\n" in text:
                raise ValueError(f"{where}: '{text}' holds '|' or a line break, which would break the tables")
            used = level_ids & {word.strip(".,;:()") for word in text.split()}
            if used:
                raise ValueError(f"{where}: '{text}' uses the level id {sorted(used)} as a word; use the level name")


def load_spec(domain: str, root: Path = SPECS) -> DomainSpec:
    """Read `<root>/<domain>.yaml`. Any problem is a `ValueError` that names what is wrong."""
    path = root / f"{domain}.yaml"
    if not path.is_file():
        raise ValueError(f"no spec file at {path}")
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    try:
        data = yaml.safe_load(raw.decode("utf-8"))
    except yaml.YAMLError as err:
        raise ValueError(f"{path}: not valid YAML ({err})") from err
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the spec must be a mapping")
    try:
        return DomainSpec(**data, domain=domain, sha256=sha256_hex(raw))
    except (ValidationError, TypeError) as err:
        raise ValueError(f"{path}: {err}") from err
