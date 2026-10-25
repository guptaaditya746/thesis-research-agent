"""The `dataset` evidence type (question-first step 2): one item `{name}` per benchmark a paper reports on.

It lives here, not in contract.py, because contract.py is one of the shared sources hashed into the code hash
of every extractor (extractors/base.SHARED_SOURCES): adding the type there gave every existing extractor a new
id, so EV1/EV2 runs no longer replayed and every cached model call missed once. contract.py stays exactly as
it was at the end of EV2; this module widens its evidence type by `dataset` (item prefix `d`) when the
`evidence` package is imported (evidence/__init__.py), so no code ever sees the contract without it.
Extractors that make dataset items hash this module in their SOURCES; other modules take `EvidenceType` from
here (the agentic package keeps the contract's, as its files are its code hash).
"""
from __future__ import annotations

from typing import Literal, get_args

from pydantic.fields import FieldInfo

from . import contract

DATASET = "dataset"
PREFIX = "d"
EvidenceType = Literal["condition", "metric", "measurement", "author_claim", "dataset", "screen"]


def _widen() -> None:
    """Add `dataset` to the contract: its item prefix, and the evidence type fields of the contract's models
    (rebuilt in dependency order, so ExtractionResult validates dataset items and rejections too)."""
    assert set(get_args(EvidenceType)) == {*get_args(contract.EvidenceType), DATASET}
    contract.ITEM_PREFIX.setdefault(DATASET, PREFIX)
    fields = {contract.ExtractorSpec: ("evidence_types", tuple[EvidenceType, ...]),
              contract.ExtractionTask: ("evidence_type", EvidenceType),
              contract.Item: ("evidence_type", EvidenceType),
              contract.Rejected: ("evidence_type", EvidenceType)}
    for model, (name, annotation) in fields.items():
        model.model_fields[name] = FieldInfo.from_annotation(annotation)
        model.model_rebuild(force=True)
    contract.ExtractionResult.model_rebuild(force=True)


_widen()
