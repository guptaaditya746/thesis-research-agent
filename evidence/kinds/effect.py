"""Kind `effect`: does the treatment change the question metric? evidence/synthesis.py, unchanged."""
from __future__ import annotations

from typing import Any

from .. import synthesis
from ..contract import EvidenceType, Item
from ..protocol import Protocol, Synthesis


def spec(protocol: Protocol) -> Synthesis:
    assert protocol.synthesis is not None, "an effect or consistency protocol has a synthesis block"
    return protocol.synthesis


def study(protocol: Protocol, document: str, items: list[Item],
          preset: dict[str, str] | None = None) -> tuple[dict[str, Any], list[str]]:
    return synthesis.study(protocol, document, items, preset)


def gap_types(protocol: Protocol, code: str) -> tuple[EvidenceType, ...]:
    return synthesis.GAP_TYPES.get(code, ())  # type: ignore[return-value]


def answer(protocol: Protocol, documents: list[str], items: dict[str, list[Item]],
           reasons: dict[str, dict[str, str]] | None = None,
           funnel: dict[str, dict[str, Any]] | None = None) -> tuple[dict[str, Any], list[str]]:
    return synthesis.answer(protocol, documents, items, reasons, funnel)


def extractor_config(protocol: Protocol) -> dict[str, Any]:
    s = spec(protocol)
    return {"question_metrics": list(s.metric_names), "compare": s.compare.model_dump()}


def screened_out(protocol: Protocol) -> dict[str, str]:
    return synthesis.reason("screened_out", spec(protocol))
