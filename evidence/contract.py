"""The extractor contract (docs/evidence-system.md Part B) as pydantic models.

One interface for every kind of extractor (regex, model, single-call LLM, agentic LLM). The engine
cannot tell which kind produced an item: every item carries checked source spans (`agent/anchor.py`
selectors), absence is recorded as coverage, and every result is canonical so it hashes the same.
"""
from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from agent.anchor import Selector
from jsonio import canonical_bytes, sha256_hex

Kind = Literal["regex", "model", "llm", "agent"]
Determinism = Literal["exact", "near_exact", "variable"]
# `screen` is the pseudo evidence type of the funnel's screening calls (docs/evidence-system.md Part D, ours):
# one item {relevant, reason} per call, checked, cached and replayed like any call; never an evidence item.
EvidenceType = Literal["condition", "metric", "measurement", "author_claim", "screen"]
Status = Literal["ok", "partial", "error"]
RejectReason = Literal["empty_quote", "not_found", "ambiguous", "partial_number", "schema", "out_of_scope",
                       "dangling_link"]
CoverageStatus = Literal["found", "none", "skipped", "error"]

ITEM_PREFIX = {"condition": "c", "metric": "k", "measurement": "m", "author_claim": "a", "screen": "s"}


def digest(obj: Any) -> str:
    """sha256 of the canonical JSON of `obj` (jsonio)."""
    return sha256_hex(canonical_bytes(obj))


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExtractorSpec(Frozen):
    """Identity of one extractor version (contract section 3)."""
    name: str = Field(pattern=r"^[a-z0-9_]+$")
    version: int = Field(ge=1)
    kind: Kind
    evidence_types: tuple[EvidenceType, ...]
    code_sha256: str
    config: dict[str, Any] = Field(default_factory=dict)
    determinism: Determinism

    @property
    def config_sha256(self) -> str:
        return digest(self.config)

    @property
    def extractor_id(self) -> str:
        return f"{self.name}@{self.version}#{digest([self.code_sha256, self.config_sha256])[:12]}"


class ProtocolRef(Frozen):
    id: str
    sha256: str


class DocumentRef(Frozen):
    id: str
    file: str
    sha256: str


class Scope(Frozen):
    kind: Literal["document", "sections", "ranges"] = "document"
    ranges: tuple[tuple[int, int], ...] = ()

    def contains(self, start: int, end: int) -> bool:
        return self.kind == "document" or any(a <= start and end <= b for a, b in self.ranges)


class Budget(Frozen):
    steps: int | None = None
    tokens: int | None = None


class Focus(Frozen):
    """What a targeted task of the funnel (Part D, `gaps`) still needs: the synthesis reason code of the gap,
    what was found so far (`have`: condition roles and canonical metrics), and the request in words (`want`,
    engine.focus_for), which the LLM extractor appends to its prompt and the agentic brief adds to its scope."""
    gap: str
    have: dict[str, list[str]]
    want: str


class ExtractionTask(Frozen):
    """One request to an extractor (contract section 4). The extractor receives nothing else.

    `focus` is part of `task_sha256` (it changes what the extractor is asked), so a targeted call and the
    untargeted call on the same document are different cache entries under the same extractor id. Adding
    the field changed the hash of every task, targeted or not; no live record cache existed at the time of
    this change (17 Oct), so nothing was invalidated by it."""
    protocol: ProtocolRef
    evidence_type: EvidenceType
    field_schema_sha256: str
    document: DocumentRef
    scope: Scope = Scope()
    context: tuple[str, ...] = ()          # item ids from earlier phases the extractor may use
    budget: Budget | None = None           # agentic extractors only
    focus: Focus | None = None             # the funnel's targeted tasks only (Part D)

    @property
    def task_sha256(self) -> str:
        return digest(self.model_dump(mode="json"))


class Span(Frozen):
    role: str                              # e.g. value, condition_label, metric_label, claim
    selector: dict[str, Any]               # Selector.json(): file, start, end, exact, prefix, suffix, sha256

    @classmethod
    def of(cls, role: str, selector: Selector) -> Span:
        return cls(role=role, selector=selector.json())


class Item(Frozen):
    """One piece of evidence: typed fields plus checked spans (contract section 5)."""
    item_id: str
    evidence_type: EvidenceType
    fields: dict[str, Any]
    spans: tuple[Span, ...] = Field(min_length=1)
    links: dict[str, str] = Field(default_factory=dict)
    confidence: float | None = None        # never used by synthesis
    found_by: tuple[str, ...] = ()         # extractor ids, filled by the engine when merging a cascade

    @staticmethod
    def make_id(evidence_type: EvidenceType, fields: dict[str, Any], spans: tuple[Span, ...] | list[Span]) -> str:
        where = sorted((s.selector["file"], s.selector["start"], s.selector["end"]) for s in spans)
        return f"{ITEM_PREFIX[evidence_type]}-{digest([evidence_type, fields, where])[:16]}"

    @classmethod
    def build(cls, evidence_type: EvidenceType, fields: dict[str, Any], spans: list[Span],
              links: dict[str, str] | None = None, confidence: float | None = None) -> Item:
        return cls(item_id=cls.make_id(evidence_type, fields, spans), evidence_type=evidence_type,
                   fields=fields, spans=tuple(spans), links=links or {}, confidence=confidence)

    def first_start(self) -> int:
        return min(s.selector["start"] for s in self.spans)


class Rejected(Frozen):
    evidence_type: EvidenceType
    fields: dict[str, Any]
    quotes: tuple[str, ...] = ()           # what the extractor proposed as passages
    reason: RejectReason
    detail: str = ""


class Coverage(Frozen):
    range: tuple[int, int] | None = None   # character offsets, or
    section: str | None = None             # a heading path
    status: CoverageStatus
    found: int = 0
    reason: str | None = None


class ExtractionError(Frozen):
    reason: str
    detail: str = ""


class ExtractionResult(Frozen):
    """What every extractor returns (contract section 5); canonical order so it hashes the same."""
    call_id: str = ""                      # assigned by the engine
    extractor_id: str
    task_sha256: str
    status: Status
    error: ExtractionError | None = None
    items: tuple[Item, ...] = ()
    rejected: tuple[Rejected, ...] = ()
    coverage: tuple[Coverage, ...] = ()
    model_calls: tuple[str, ...] = ()

    def canonical(self) -> ExtractionResult:
        """Items by first span start then evidence type then id; rejected and coverage sorted too (R7)."""
        items = tuple(sorted(self.items, key=lambda i: (i.first_start(), i.evidence_type, i.item_id)))
        rejected = tuple(sorted(self.rejected, key=lambda r: digest(r.model_dump(mode="json"))))
        coverage = tuple(sorted(self.coverage, key=lambda c: (c.range or (-1, -1), c.section or "")))
        return self.model_copy(update={"items": items, "rejected": rejected, "coverage": coverage})

    @property
    def output_sha256(self) -> str:
        """Hash of the canonical result without the engine-assigned call id."""
        return digest(self.canonical().model_dump(mode="json", exclude={"call_id"}))


@runtime_checkable
class RunContext(Protocol):
    """Given by the engine; the only way out of an extractor (contract section 12, rule R4)."""

    def text(self) -> str: ...                       # the document text exactly as stored
    def index(self) -> Any: ...                      # agent.anchor.Index over it, normalised once
    def context_items(self) -> list[Item]: ...       # the task's declared context, resolved
    def field_schema(self) -> dict[str, Any]: ...    # the evidence type's JSON schema from the protocol


@runtime_checkable
class Extractor(Protocol):
    spec: ExtractorSpec

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult: ...
