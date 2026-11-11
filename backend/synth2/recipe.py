"""The recipe of one topic: the question, the two arms, the three candidate conditions and the number ranges."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from jsonio import sha256_hex
from repo_paths import DATA

RECIPES = DATA / "synth2"
MIN_AUTHORS = 20   # one author per study at 20 studies per corpus


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Level(Strict):
    id: str
    name: str


class ConditionSpec(Strict):
    id: str
    name: str
    levels: list[Level]


class Arm(Strict):
    label: str
    description: str


class Recipe(Strict):
    domain: str
    question: str
    treatment: Arm
    control: Arm
    metric: str
    unit: str
    conditions: list[ConditionSpec]
    n_range: tuple[int, int]
    n_step: int
    base_rate: tuple[float, float]
    effect: tuple[float, float]
    min_effect: float
    min_gap: float
    authors: list[str]
    years: tuple[int, int]
    datasets: list[str]
    sha256: str

    @model_validator(mode="after")
    def _check(self) -> "Recipe":
        if len(self.conditions) != 3 or any(len(c.levels) != 2 for c in self.conditions):
            raise ValueError("conditions: exactly 3 conditions with exactly 2 levels each")
        ids = [c.id for c in self.conditions] + [lv.id for c in self.conditions for lv in c.levels]
        if len(set(ids)) != len(ids):
            raise ValueError("conditions: condition ids and level ids must all be different")
        names = [self.treatment.label, self.control.label, *(lv.name for c in self.conditions for lv in c.levels)]
        for i, a in enumerate(names):
            for j, b in enumerate(names):
                if i != j and a.lower() in b.lower():
                    raise ValueError(f"names: '{a}' is inside '{b}', so the text would be ambiguous")
        if len(self.authors) < MIN_AUTHORS or len(set(self.authors)) != len(self.authors):
            raise ValueError(f"authors: need at least {MIN_AUTHORS} different names, got {len(self.authors)}")
        for field in ("n_range", "base_rate", "effect", "years"):
            low, high = getattr(self, field)
            if low > high:
                raise ValueError(f"{field}: must be ascending, got {low} > {high}")
        if self.n_step <= 0 or self.n_range[0] <= 0 or any(n % self.n_step for n in self.n_range):
            raise ValueError("n_range: both ends must be positive multiples of n_step")
        if self.min_effect <= 0 or self.min_gap <= 0:
            raise ValueError("min_effect and min_gap must be above zero")
        if self.effect[0] < self.min_effect:
            raise ValueError("effect: the smallest effect must be at least min_effect, or a planted effect could read as none")
        if self.base_rate[0] - self.effect[1] < 0 or self.base_rate[1] + self.effect[1] > 1:
            raise ValueError("base_rate: base rate plus or minus the largest effect must stay between 0 and 1")
        if not self.datasets:
            raise ValueError("datasets: must not be empty")
        self._check_text()
        return self

    def _check_text(self) -> None:
        """Everything the writer puts into a paper: no digits (only planted counts may be digits), no table
        bar, never empty, and no level id as a word of its own (a level is always named, never given by id)."""
        level_ids = {lv.id for c in self.conditions for lv in c.levels}
        texts = {"metric": self.metric, "unit": self.unit,
                 "treatment": f"{self.treatment.label} {self.treatment.description}",
                 "control": f"{self.control.label} {self.control.description}",
                 **{f"condition {c.id}": " ".join([c.name, *(lv.name for lv in c.levels)]) for c in self.conditions},
                 **{f"dataset {i + 1}": d for i, d in enumerate(self.datasets)},
                 **{f"author {i + 1}": a for i, a in enumerate(self.authors)}}
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


def load_recipe(domain: str, root: Path = RECIPES) -> Recipe:
    """Read `<root>/<domain>.yaml`. Any problem is a `ValueError` that names what is wrong."""
    path = root / f"{domain}.yaml"
    if not path.is_file():
        raise ValueError(f"no recipe file at {path}")
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    data = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the recipe must be a mapping")
    try:
        return Recipe(**data, domain=domain, sha256=sha256_hex(raw))
    except (ValidationError, TypeError) as err:
        raise ValueError(f"{path}: {err}") from err
