"""Kind `effect`: does the treatment change the question metric? evidence/synthesis.py, unchanged."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import synthesis
from ..contract import Item
from ..evidence_types import EvidenceType
from ..protocol import Protocol, Synthesis

if TYPE_CHECKING:
    from ..comparisons import Comparisons
    from ..names import NameGroups
    from ..pack import RoleMap


def spec(protocol: Protocol) -> Synthesis:
    assert protocol.synthesis is not None, "an effect or consistency protocol has a synthesis block"
    return protocol.synthesis


def study(protocol: Protocol, document: str, items: list[Item], preset: dict[str, str] | None = None, *,
          roles: RoleMap | None = None) -> tuple[dict[str, Any], list[str]]:
    return synthesis.study(protocol, document, items, preset, roles=roles)


def gap_types(protocol: Protocol, code: str, *, roles: RoleMap | None = None) -> tuple[EvidenceType, ...]:
    return synthesis.gap_types(protocol, code, roles)


def answer(protocol: Protocol, documents: list[str], items: dict[str, list[Item]],
           reasons: dict[str, dict[str, str]] | None = None,
           funnel: dict[str, dict[str, Any]] | None = None, *,
           roles: RoleMap | None = None, groups: NameGroups | None = None,
           comparisons: Comparisons | None = None) -> tuple[dict[str, Any], list[str]]:
    """`groups` (the names step) is not read: an effect answer compares sides and canonical metrics, not names.
    Nor is `comparisons` (comparisons.json): an effect answer keeps synthesis's pair per study (spec section 6.2)."""
    return synthesis.answer(protocol, documents, items, reasons, funnel, roles=roles)


def extractor_config(protocol: Protocol) -> dict[str, Any]:
    s = spec(protocol)
    return {"question_metrics": list(s.metric_names), "compare": s.compare.model_dump()}


def screened_out(protocol: Protocol) -> dict[str, str]:
    return synthesis.reason("screened_out", spec(protocol))
