"""The config of one domain's real-paper pool: what to fetch, which papers to keep, and which words to rename."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import ValidationError, model_validator

from jsonio import sha256_hex
from synth2.recipe import Strict
from synth3.spec import SPECS, DomainSpec

REAL_SPECS = SPECS / "real"
POOLS = SPECS / "pools"
TEMPLATE_WORDS = ("SD",)   # words our own planted text prints that synth2 would treat as a name
_NUMBER = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVXLC]+\.)\s+")
_GAP = r"[\s-]+"


def phrase(name: str) -> str:
    """A regex for a plain name whose words may be joined by spaces, line breaks or hyphens."""
    return _GAP.join(map(re.escape, name.split()))


class RealSpec(Strict):
    domain: str
    source: Literal["pmc", "files"]
    query: str = ""
    max_fetch: int = 600
    article_types: list[str]
    exclude_title: str
    min_words: int
    max_words: int
    min_tables: int
    results_heading: str
    conclusion_heading: str
    drop_sections: str
    control_words: str
    keep: list[str]
    name_stems: list[str]
    name_words: list[str]
    min_names: int = 0   # a paper must name at least this many words of name_stems/name_words (medicine: drugs)
    n_test: int = 30
    sha256: str

    @model_validator(mode="after")
    def _check(self) -> "RealSpec":
        for field in ("exclude_title", "results_heading", "conclusion_heading", "drop_sections", "control_words"):
            try:
                re.compile(getattr(self, field))
            except re.error as err:
                raise ValueError(f"{field}: not a valid regex ({err})") from err
        if not 0 < self.min_words < self.max_words:
            raise ValueError("min_words: must be above 0 and below max_words")
        if self.n_test < 5:
            raise ValueError("n_test: must be at least 5 (the classifier uses 5 folds)")
        if self.max_fetch <= 0 or self.min_tables < 0:
            raise ValueError("max_fetch: must be above 0, and min_tables at least 0")
        if self.min_names < 0:
            raise ValueError("min_names: must be at least 0")
        if self.source == "pmc" and not self.query.strip():
            raise ValueError("query: a pmc source needs a query")
        for field in ("name_stems", "name_words"):
            if any(not w or w != w.lower() for w in getattr(self, field)):
                raise ValueError(f"{field}: every entry must be lower case")
        missing = [w for w in TEMPLATE_WORDS if w not in self.keep]
        if missing:
            raise ValueError(f"keep: must hold {missing}, which our own planted text prints")
        return self

    def control_regex(self) -> str:
        """`control_words` with each space matching any run of spaces, line breaks or hyphens: papers write
        "usual care", "usual-care group" and "usual\\ncare" for the same arm."""
        return re.sub(r"(?<!\\) ", lambda m: _GAP, self.control_words)

    def banned(self, spec: DomainSpec) -> re.Pattern:
        """Control words, every arm label and every setting name: whole words, any case."""
        names = [phrase(n) for n in (*(a.label for a in spec.arms), *(s.name for s in spec.settings))]
        return re.compile(rf"\b(?:{self.control_regex()}|{'|'.join(names)})\b", re.I)

    def heading(self, kind: Literal["results", "conclusion"], line: str) -> bool:
        if not line.lstrip().startswith("#"):
            return False
        text = _NUMBER.sub("", line.strip().lstrip("#").strip())
        regex = self.results_heading if kind == "results" else self.conclusion_heading
        return re.search(regex, text, re.I) is not None


def load_real_spec(domain: str, root: Path = REAL_SPECS) -> RealSpec:
    """Read `<root>/<domain>.yaml`. Any problem is a `ValueError` that names the field."""
    path = root / f"{domain}.yaml"
    if not path.is_file():
        raise ValueError(f"no real-paper config at {path}")
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    data = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the config must be a mapping")
    try:
        return RealSpec(**data, domain=domain, sha256=sha256_hex(raw))
    except (ValidationError, TypeError) as err:
        raise ValueError(f"{path}: {err}") from err
