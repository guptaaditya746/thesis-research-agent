"""Domain packs: the topic words and evidence-type roles of one research domain, kept in `domains/<name>/`.

A pack is three files: `pack.yaml` (types, display names), `words.yaml` (patterns and term lists) and
`provenance.json` (where the words came from). `Pack.sha256` digests the three, so a changed word is a new pack.

Two rules every pack follows:
- `words.yaml` `conditions` is ordered: the first role is the treatment side, and every role after it is a control
  whose patterns get the `not_a_system` cue (Pack.extractor_config). The order of the roles decides the control.
- Type names and prefixes are global across packs (evidence_types.register keeps one registry per process): the
  same type name in two packs must have the same prefix, and a new pack must pick prefixes no other pack uses.
"""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from collections.abc import Iterable
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from jsonio import sha256_hex

from . import evidence_types
from .contract import digest
from .protocol import DEFAULT_PACK, Strict   # DEFAULT_PACK: re-exported, the pack of a protocol with no `domain:`

DOMAINS = Path(__file__).resolve().parents[1] / "domains"
# The files of Pack.sha256, in name order. Left out on purpose: `propose.yaml` (the drafting cards of `evidence
# propose`, not read by a run, so editing them must not make every run's pack new) and `questions.yaml` and
# `protocols/` (each protocol has its own sha256). domains/default.yaml is outside every pack: it only names the
# default pack.
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
    kind_field: str | None = None      # the compared thing's method kind (kind `best`), when the type carries one


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
    system_nouns: list[str] = []   # the domain's own system nouns, beside measure.GENERIC_SYSTEM_NOUNS


_CONDITIONS = ("conditions", "not_a_system")
# The config keys of the pack words each extractor reads (its key names as the extractor reads them); an
# extractor not named here (LLM, screen, configured names) takes no pack words.
READS: dict[str, tuple[str, ...]] = {
    "regex_condition": _CONDITIONS, "abbrev_condition": _CONDITIONS, "gliner_condition": ("labels", *_CONDITIONS),
    "regex_metric": ("metrics",), "abbrev_metric": ("metrics", "supplement"), "gliner_metric": ("labels", "metrics"),
    "regex_measurement": (*_CONDITIONS, "metrics", "system_nouns"),
    "regex_measurement_units": (*_CONDITIONS, "metrics", "fraction_metrics", "system_nouns"),
    "number_measurement": (*_CONDITIONS, "metrics", "fraction_metrics", "system_nouns"),
    "regex_author_claim": ("subject", "claims"), "regex_dataset": ("pattern",), "gliner_dataset": ("labels",),
    "agentic": ("display", "metric_names"),   # the examples of its task brief (evidence/agentic/task.py)
}
# The measured-value extractors also read `types` (role -> the pack's type of that role): which context items are
# the compared things and which the metrics, and so the links they fill (protocol EvidenceTypeSpec.links).
for _name in ("regex_measurement", "regex_measurement_units", "number_measurement"):
    READS[_name] = (*READS[_name], "types")


class OntologyDecl(Strict):
    """The pack's OWL ontology file and the ontology class each role's types belong to (spec 6.3)."""
    file: str = "ontology.ttl"
    roles: dict[Role, str]


class Pack(Strict):
    name: str
    types: dict[str, TypeDecl]
    words: Words
    display: dict[str, str]
    names_seed: dict[str, list[str]]
    limitation_categories: list[str]
    sha256: str
    ontology: OntologyDecl | None = None

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
            "system_nouns": list(w.system_nouns),
            "subject": w.claim_subject,
            "claims": [list(c) for c in w.claims],
            "pattern": w.dataset_pattern,
            "display": dict(self.display),
            "metric_names": [m for m in dict.fromkeys(c for _, c, _ in w.metrics) if m != "other"],
            # role -> its type; a role with several types gives the list, and the measured-value extractors pick
            # the one the measured-value type links to (extractors/base.py Slots.of) or refuse
            "types": {str(role): found[0] if len(found) == 1 else found
                      for role in Role if (found := RoleMap(self).types_of(role))},
        }
        if etype in w.gliner_labels:
            words["labels"] = list(w.gliner_labels[etype])
        return {key: words[key] for key in READS.get(extractor, ()) if key in words}


# The roles each question kind needs a type for (spec section 6.2): a pack may lack values and claims (a
# SciREX-style pack) and still answer inventories; an inventory needs only its target type, which the protocol
# names (Protocol checks it is a type of the pack).
KIND_ROLES: dict[str, tuple[Role, ...]] = {
    "effect": (Role.COMPARED_THING, Role.METRIC, Role.VALUE),
    "best": (Role.COMPARED_THING, Role.METRIC, Role.VALUE),
    "consistency": (Role.COMPARED_THING, Role.METRIC, Role.VALUE, Role.CLAIM),
    "inventory": (),
}
FieldName = Literal["name", "side", "canonical", "direction", "kind"]


class RoleMap:
    """The pack's evidence types by role, and the fields that carry a type's name, side, canonical name and
    direction, so code asks for "the compared thing" and never for a type name."""

    def __init__(self, pack: Pack) -> None:
        self.pack = pack

    def types_of(self, role: Role) -> list[str]:
        """Every type of role `role`, in the pack's order."""
        return [name for name, decl in self.pack.types.items() if decl.role == role]

    def type_in(self, role: Role, declared: Iterable[str]) -> str | None:
        """The first type of role `role` (pack order) among `declared` (a protocol's evidence types); None if none."""
        names = set(declared)
        return next((t for t in self.types_of(role) if t in names), None)

    def type_of(self, role: Role) -> str:
        """The one type of role `role`; PackError naming the role and the pack when there is none or several."""
        found = self.types_of(role)
        if not found:
            raise PackError(f"pack {self.pack.name!r}: no type has role {str(role)!r}")
        if len(found) > 1:
            raise PackError(f"pack {self.pack.name!r}: several types have role {str(role)!r}: {found}")
        return found[0]

    def field(self, etype: str, which: FieldName) -> str:
        """The field of type `etype` that holds its `which` (TypeDecl.<which>_field); PackError when undeclared."""
        decl = self.pack.types.get(etype)
        if decl is None:
            raise PackError(f"pack {self.pack.name!r}: no type {etype!r}")
        name = getattr(decl, f"{which}_field")
        if name is None:
            raise PackError(f"pack {self.pack.name!r}: type {etype!r} declares no {which}_field")
        return name

    def field_or_none(self, etype: str, which: FieldName) -> str | None:
        """`field`, or None when the type declares no such field."""
        decl = self.pack.types.get(etype)
        return getattr(decl, f"{which}_field") if decl is not None else None


def check(pack: Pack, kinds: Iterable[str]) -> None:
    """Every role the question kinds `kinds` need has a type in `pack` (KIND_ROLES); else PackError of the form
    `pack '<name>': no type has role '<role>' (needed by kind '<kind>')`."""
    roles = RoleMap(pack)
    for kind in kinds:
        for role in KIND_ROLES[kind]:
            if not roles.types_of(role):
                raise PackError(f"pack {pack.name!r}: no type has role {str(role)!r} (needed by kind {kind!r})")


def register_pack(pack: Pack) -> None:
    """Register every type of `pack` with its item prefix (evidence_types.register); a clash raises PackError."""
    for name, decl in pack.types.items():
        try:
            evidence_types.register(name, decl.prefix)
        except ValueError as e:
            raise PackError(f"pack {pack.name!r}: {e}") from e


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
        pack = Pack(**head, words=Words(**words), sha256=digest([[f, sha256_hex(raw[f])] for f in FILES]))
    except (yaml.YAMLError, ValidationError, TypeError) as e:
        raise PackError(f"domain pack {name!r} ({folder}) is invalid: {e}") from e
    if pack.name != folder.name:   # a protocol's `domain:` names the folder; the pack must answer to the same name
        raise PackError(f"domain pack {name!r}: pack.yaml has name {pack.name!r}, not its folder {folder.name!r}")
    return pack
