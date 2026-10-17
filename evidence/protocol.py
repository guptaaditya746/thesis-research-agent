"""The executable research protocol: a hand-written YAML file the engine runs (docs/evidence-system.md Part A,
protocol version 2 in Part C).

A protocol names the question, the evidence types it needs (each with a JSON schema for its fields, the
span roles its items carry, the earlier types it needs as context, and a cascade of registered
extractors), how passages are located, an optional screening question (Part D, the funnel), and how the
evidence becomes the answer: the `synthesis` block holds every rule parameter (which condition roles are
compared, the question metrics and their direction, the neutral band, the pairing rule, the claim
vocabulary, the label decision table, the flag thresholds), so `evidence/rules.py` knows nothing of the
question. Its `sha256` is the digest of the parsed content (agent/canonical.py), so comments, key order
and line ends in the file do not change it, and every run, task and record names the protocol by that
hash.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import rules
from .contract import Budget, EvidenceType, digest

LocateStrategy = Literal["exhaustive", "bm25", "agent"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExtractorRef(Strict):
    """One step of a cascade: a registered extractor name and its configuration."""
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    budget: Budget | None = None            # given to the task for agentic extractors only


class BoundWhen(Strict):
    link: str                               # the link whose target decides whether the bound applies
    field: str                              # a field of the linked item
    values: tuple[Any, ...]                 # the bound applies when that field has one of these values


class Bound(Strict):
    """A range a numeric field must lie in, checked by the engine (rejected with reason schema otherwise);
    e.g. a measurement of an accuracy or a rate is a fraction in [0, 1]."""
    field: str
    min: float | None = None
    max: float | None = None
    when: BoundWhen | None = None


class EvidenceTypeSpec(Strict):
    description: str = ""
    fields: dict[str, Any]                  # JSON schema (an object schema) of an item's fields
    links: dict[str, EvidenceType] = Field(default_factory=dict)   # link name -> evidence type it points to
    context: tuple[EvidenceType, ...] = ()  # earlier types whose items the extractors receive
    roles: tuple[str, ...] = Field(min_length=1)   # span roles; the first one is required on every item
    merge_key: tuple[str, ...] | None = None       # fields compared when merging a cascade (default: all)
    query: tuple[str, ...] = ()             # bm25 query terms for the locate step
    cascade: Literal["all", "until_found"] = "all"  # until_found: later extractors run only if none found
    bounds: tuple[Bound, ...] = ()          # ranges of numeric fields (checks.py)
    extractors: tuple[ExtractorRef, ...] = Field(min_length=1)

    @property
    def schema_sha256(self) -> str:
        """The task's field_schema_sha256: fields and links together, so a change to either is a new task."""
        return digest({"fields": self.fields, "links": self.links})

    @property
    def properties(self) -> dict[str, Any]:
        return dict(self.fields.get("properties", {}))

    def enum_of(self, field: str) -> tuple[Any, ...] | None:
        values = self.properties.get(field, {}).get("enum")
        return tuple(values) if values else None


class Locate(Strict):
    strategy: LocateStrategy = "exhaustive"
    params: dict[str, Any] = Field(default_factory=dict)


SCREEN_TYPE: EvidenceType = "screen"
# The one item a screening call returns (contract.Item on the pseudo type `screen`): the decision and why.
SCREEN_FIELDS: dict[str, Any] = {"type": "object", "additionalProperties": False, "required": ["relevant", "reason"],
                                 "properties": {"relevant": {"type": "boolean", "description": "the paper is one the protocol can use"},
                                                "reason": {"type": "string", "minLength": 1, "description": "why, in one sentence"}}}
SCREEN_ROLES = ("evidence",)   # the span: the first matching term (regex) or the model's quote (llm)


class Screen(Strict):
    """Per-document screening before any extraction (Part D, the funnel; ours): is the paper one the protocol
    can use at all? `terms` feed the regex screen (no hit: not relevant); the cascade decides the rest.
    `spec` is the pseudo evidence type the engine runs the screen calls on, so they are checked, cached and
    replayed exactly like extractor calls."""
    question: str
    terms: tuple[str, ...] = ()
    extractors: tuple[ExtractorRef, ...] = Field(min_length=1)
    on_fail: Literal["skip", "extract_anyway"] = "skip"

    @property
    def spec(self) -> EvidenceTypeSpec:
        return EvidenceTypeSpec(description=self.question, fields=SCREEN_FIELDS, roles=SCREEN_ROLES,
                                extractors=self.extractors)


class Compare(Strict):
    """The condition roles a study's pair is made of: the effect is treatment against control."""
    treatment: str
    control: str

    @model_validator(mode="after")
    def _distinct(self) -> Compare:
        if self.treatment == self.control:
            raise ValueError("synthesis.compare: treatment and control must be different roles")
        return self


class QuestionMetric(Strict):
    canonical: str
    higher_is_better: bool


class Pairing(Strict):
    """How a study's treatment and control measurements are chosen (evidence/synthesis.py): on the same
    dataset (the first dataset in document order that has both), preferring, in order, a value in a table
    cell over prose and the earlier value over the later one."""
    rule: Literal["same_dataset"] = "same_dataset"
    prefer: tuple[Literal["table_cell", "document_order"], ...] = ("table_cell", "document_order")


class LabelRow(Strict):
    """One row of the label decision table: every condition in `when` must hold on the counts."""
    when: dict[str, str] = Field(default_factory=dict)   # count name -> "<op><int>"
    then: rules.Label

    def get(self, key: str, default: Any = None) -> Any:   # lets rules.label read rows like mappings
        return getattr(self, key, default)


class LargeEffect(Strict):
    factor: float = Field(default=3.0, gt=0)
    min_studies: int = Field(default=3, ge=1)


class Flags(Strict):
    duplicates: bool = True
    large_effect: LargeEffect = LargeEffect()


class Synthesis(Strict):
    compare: Compare
    metrics: tuple[QuestionMetric, ...] = Field(min_length=1)   # question metrics, priority order
    min_effect: float = Field(gt=0)                             # |delta| below this is neutral
    pairing: Pairing = Pairing()
    claim_map: dict[str, rules.Direction]                       # author-claim value -> the direction it asserts
    label: tuple[LabelRow, ...] = Field(min_length=1)
    flags: Flags = Flags()

    @model_validator(mode="after")
    def _consistent(self) -> Synthesis:
        names = [m.canonical for m in self.metrics]
        if len(set(names)) != len(names):
            raise ValueError(f"synthesis.metrics names a metric twice: {names}")
        for n, row in enumerate(self.label):
            unknown = [k for k in row.when if k not in rules.COUNTS]
            if unknown:
                raise ValueError(f"synthesis.label row {n}: unknown counts {unknown}; use {list(rules.COUNTS)}")
            for condition in row.when.values():
                rules.condition_holds(condition, 0)     # raises on a malformed condition
            if not row.when and n != len(self.label) - 1:
                raise ValueError(f"synthesis.label row {n} has no `when`, so the rows after it can never match")
        if self.label[-1].when:
            raise ValueError("synthesis.label: the last row must have no `when` (the default label)")
        if not self.claim_map:
            raise ValueError("synthesis.claim_map must map every author-claim value to a direction")
        return self

    @property
    def metric_names(self) -> tuple[str, ...]:
        return tuple(m.canonical for m in self.metrics)

    def higher_is_better(self, canonical: str) -> bool:
        return next(m.higher_is_better for m in self.metrics if m.canonical == canonical)

    @property
    def table(self) -> list[dict[str, Any]]:
        return [{"when": dict(r.when), "then": r.then} for r in self.label]


class Protocol(Strict):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    version: int = Field(ge=1)
    question: str
    evidence_types: dict[EvidenceType, EvidenceTypeSpec]
    locate: Locate = Locate()
    screen: Screen | None = None
    synthesis: Synthesis

    @model_validator(mode="after")
    def _consistent(self) -> Protocol:
        if SCREEN_TYPE in self.evidence_types:
            raise ValueError(f"evidence_types may not be named {SCREEN_TYPE!r}: it is the funnel's screening pseudo type")
        for name, spec in self.evidence_types.items():
            try:
                Draft202012Validator.check_schema(spec.fields)
            except SchemaError as exc:
                raise ValueError(f"{name}.fields is not a valid JSON schema: {exc.message}") from exc
            if spec.fields.get("type") != "object":
                raise ValueError(f"{name}.fields must be an object schema")
            for target in (*spec.context, *spec.links.values()):
                if target not in self.evidence_types:
                    raise ValueError(f"{name} refers to evidence type {target!r}, which the protocol does not define")
            for target in spec.links.values():
                if target not in spec.context:
                    raise ValueError(f"{name} links to {target!r} but does not list it as context")
            for bound in spec.bounds:
                if bound.field not in spec.properties or (bound.when and bound.when.link not in spec.links):
                    raise ValueError(f"{name}.bounds names an unknown field or link: {bound}")
            missing = [k for k in spec.merge_key or () if k not in spec.properties]
            if missing:
                raise ValueError(f"{name}.merge_key names unknown fields {missing}")
        self._synthesis_matches_types()
        self.phases()  # raises on a cycle
        return self

    def _synthesis_matches_types(self) -> None:
        """The synthesis parameters name values the evidence types can carry (when the types declare enums)."""
        s = self.synthesis
        roles = self.evidence_types["condition"].enum_of("role") if "condition" in self.evidence_types else None
        if roles is not None:
            bad = [r for r in (s.compare.treatment, s.compare.control) if r not in roles]
            if bad:
                raise ValueError(f"synthesis.compare names roles {bad} that condition.role does not allow {roles}")
        canon = self.evidence_types["metric"].enum_of("canonical") if "metric" in self.evidence_types else None
        if canon is not None:
            bad = [m for m in s.metric_names if m not in canon]
            if bad:
                raise ValueError(f"synthesis.metrics names {bad}, which metric.canonical does not allow {canon}")
        claims = (self.evidence_types["author_claim"].enum_of("direction")
                  if "author_claim" in self.evidence_types else None)
        if claims is not None and set(s.claim_map) != set(claims):
            raise ValueError(f"synthesis.claim_map must map exactly author_claim.direction {claims}; got {sorted(s.claim_map)}")

    @property
    def sha256(self) -> str:
        return digest(self.model_dump(mode="json"))

    def phases(self) -> list[EvidenceType]:
        """Evidence types in dependency order; among types that are ready, the order of the file."""
        done: list[EvidenceType] = []
        pending = list(self.evidence_types)
        while pending:
            ready = next((t for t in pending if all(c in done for c in self.evidence_types[t].context)), None)
            if ready is None:
                raise ValueError(f"evidence types {pending} depend on each other in a cycle")
            done.append(ready)
            pending.remove(ready)
        return done


def parse(text: str) -> Protocol:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("a protocol is a YAML mapping")
    return Protocol.model_validate(data)


def load(path: Path | str) -> Protocol:
    return parse(Path(path).read_bytes().decode("utf-8"))
