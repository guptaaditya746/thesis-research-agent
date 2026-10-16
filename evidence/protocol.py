"""The executable research protocol: a hand-written YAML file the engine runs (docs/evidence-system.md Part A).

A protocol names the question, the evidence types it needs (each with a JSON schema for its fields, the
span roles its items carry, the earlier types it needs as context, and a cascade of registered
extractors), how passages are located, and how the evidence becomes the answer. Its `sha256` is the
digest of the parsed content (agent/canonical.py), so comments, key order and line ends in the file do
not change it, and every run, task and record names the protocol by that hash.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from jsonschema import Draft202012Validator
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


class Locate(Strict):
    strategy: LocateStrategy = "exhaustive"
    params: dict[str, Any] = Field(default_factory=dict)


class Synthesis(Strict):
    metrics: tuple[str, ...]                # canonical question metrics, in priority order (rules.METRICS)
    min_effect: float = rules.MIN_EFFECT
    label_rule: Literal["rules.label"] = "rules.label"
    # how a study's rag and baseline measurements are chosen (evidence/synthesis.py): same dataset, first
    # dataset in document order, a table cell before prose, then document order of the value
    pairing: Literal["same_dataset_table_first"] = "same_dataset_table_first"

    @model_validator(mode="after")
    def _known_metrics(self) -> Synthesis:
        unknown = [m for m in self.metrics if m not in rules.METRICS]
        if unknown or not self.metrics:
            raise ValueError(f"synthesis.metrics must name metrics of rules.METRICS {sorted(rules.METRICS)}; got {unknown}")
        return self


class Protocol(Strict):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    version: int = Field(ge=1)
    question: str
    evidence_types: dict[EvidenceType, EvidenceTypeSpec]
    locate: Locate = Locate()
    synthesis: Synthesis

    @model_validator(mode="after")
    def _consistent(self) -> Protocol:
        for name, spec in self.evidence_types.items():
            Draft202012Validator.check_schema(spec.fields)
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
        self.phases()  # raises on a cycle
        return self

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
