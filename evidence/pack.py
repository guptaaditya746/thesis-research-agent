"""Domain packs: the topic words and evidence-type roles of one research domain, kept in `domains/<name>/`.

A pack is three files: `pack.yaml` (types, display names), `words.yaml` (patterns and term lists) and
`provenance.json` (where the words came from). `Pack.sha256` digests the three, so a changed word is a new pack.
"""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

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


_CONDITIONS = ("conditions", "not_a_system")
# The config keys of the pack words each extractor reads (its key names as the extractor reads them); an
# extractor not named here (LLM, screen, configured names) takes no pack words.
READS: dict[str, tuple[str, ...]] = {
    "regex_condition": _CONDITIONS, "abbrev_condition": _CONDITIONS, "gliner_condition": ("labels", *_CONDITIONS),
    "regex_metric": ("metrics",), "abbrev_metric": ("metrics", "supplement"), "gliner_metric": ("labels", "metrics"),
    "regex_measurement": (*_CONDITIONS, "metrics"),
    "regex_measurement_units": (*_CONDITIONS, "metrics", "fraction_metrics"),
    "number_measurement": (*_CONDITIONS, "metrics", "fraction_metrics"),
    "regex_author_claim": ("subject", "claims"), "regex_dataset": ("pattern",), "gliner_dataset": ("labels",),
    "agentic": ("display", "metric_names"),   # the examples of its task brief (evidence/agentic/task.py)
}


class Pack(Strict):
    name: str
    types: dict[str, TypeDecl]
    words: Words
    display: dict[str, str]
    names_seed: dict[str, list[str]]
    limitation_categories: list[str]
    sha256: str

    def extractor_config(self, etype: str, extractor: str) -> dict[str, Any]:
        """The pack words `extractor` reads when it runs on evidence type `etype`, under its config keys. The
        engine puts a protocol's own config over these (the protocol wins). Condition patterns of every role
        after the first (the controls) end in `not_a_system`, as terms.control_cue builds them."""
        w = self.words
        roles = list(w.conditions.items())
        words: dict[str, Any] = {
            "conditions": {role: [p + w.not_a_system if i else p for p in ps] for i, (role, ps) in enumerate(roles)},
            "not_a_system": w.not_a_system,
            "metrics": [list(m) for m in w.metrics],
            "supplement": [list(m) for m in w.metric_supplement],
            "fraction_metrics": list(w.fraction_metrics),
            "subject": w.claim_subject,
            "claims": [list(c) for c in w.claims],
            "pattern": w.dataset_pattern,
            "display": dict(self.display),
            "metric_names": [m for m in dict.fromkeys(c for _, c, _ in w.metrics) if m != "other"],
        }
        if etype in w.gliner_labels:
            words["labels"] = list(w.gliner_labels[etype])
        return {key: words[key] for key in READS.get(extractor, ()) if key in words}


def protocol_path(pack: str, protocol_id: str) -> Path:
    """The hand-written protocol `protocol_id` of pack `pack`: domains/<pack>/protocols/<protocol_id>.yaml."""
    return DOMAINS / pack / "protocols" / f"{protocol_id}.yaml"


def questions_path(pack: str) -> Path:
    """The question list of pack `pack`: domains/<pack>/questions.yaml."""
    return DOMAINS / pack / "questions.yaml"


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
