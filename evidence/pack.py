"""Domain packs: the topic words and evidence-type roles of one research domain, kept in `domains/<name>/`.

A pack is three files: `pack.yaml` (types, display names), `words.yaml` (patterns and term lists) and
`provenance.json` (where the words came from). `Pack.sha256` digests the three, so a changed word is a new pack.
"""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import ValidationError

from jsonio import sha256_hex

from .contract import digest
from .protocol import Strict

DOMAINS = Path(__file__).resolve().parents[1] / "domains"
FILES = ("pack.yaml", "provenance.json", "words.yaml")   # name order, as digested


class PackError(ValueError):
    pass


class Role(StrEnum):
    COMPARED_THING = "compared_thing"
    METRIC = "metric"
    VALUE = "measured_value"
    CLAIM = "author_claim"
    CONTEXT = "context"


class TypeDecl(Strict):
    prefix: str
    role: Role
    name_field: str | None = None
    side_field: str | None = None
    canonical_field: str | None = None
    direction_field: str | None = None


class Words(Strict):
    conditions: dict[str, list[str]]
    not_a_system: str
    metrics: list[tuple[str, str, bool]]
    claim_subject: str
    claims: list[tuple[str, str]]
    gliner_labels: dict[str, list[str]]
    fraction_metrics: list[str]
    dataset_pattern: str
    metric_supplement: list[tuple[str, str, bool]]
    screen_terms: list[str]
    query: dict[str, list[str]]


class Pack(Strict):
    name: str
    types: dict[str, TypeDecl]
    words: Words
    display: dict[str, str]
    names_seed: dict[str, list[str]]
    limitation_categories: list[str]
    sha256: str


def load_pack(name: str, root: Path = DOMAINS) -> Pack:
    """Read and check `<root>/<name>/`; any missing or malformed part raises PackError naming the folder."""
    folder = root / name
    if not folder.is_dir():
        raise PackError(f"domain pack {name!r}: folder {folder} does not exist")
    raw: dict[str, bytes] = {}
    for fname in FILES:
        path = folder / fname
        if not path.is_file():
            raise PackError(f"domain pack {name!r}: {path} is missing")
        raw[fname] = path.read_bytes().replace(b"\r\n", b"\n")
    try:
        head, words = yaml.safe_load(raw["pack.yaml"]), yaml.safe_load(raw["words.yaml"])
        if not isinstance(head, dict) or not isinstance(words, dict):
            raise PackError(f"domain pack {name!r}: pack.yaml and words.yaml must be mappings")
        return Pack(**head, words=Words(**words), sha256=digest([[f, sha256_hex(raw[f])] for f in FILES]))
    except (yaml.YAMLError, ValidationError, TypeError) as e:
        raise PackError(f"domain pack {name!r} ({folder}) is invalid: {e}") from e
