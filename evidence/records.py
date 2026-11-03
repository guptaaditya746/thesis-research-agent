"""Record types of the general system: experiments, open claims and links between papers.

Each record is a frozen pydantic model with one checked source span; `item(record)` turns it into a contract
`Item` of its registered evidence type (`experiment` x, `claim` cl, `link` ln), registered here at import.
"""
from __future__ import annotations

from typing import Literal

from .contract import Frozen, Item, Span
from .evidence_types import register

EXPERIMENT, CLAIM, LINK = "experiment", "claim", "link"
register(EXPERIMENT, "x")
register(CLAIM, "cl")
register(LINK, "ln")


class Experiment(Frozen):
    exp_id: str
    document: str
    label: str
    setting: dict[str, str]                # field names such as dataset, model, population
    span: Span


class ClaimRecord(Frozen):
    subject: str
    relation: str                          # the paper's own verb
    object: str | None
    setting: dict[str, str]
    strength: Literal["firm", "hedged"]
    direction: Literal["improves", "worsens", "no_effect"] | None
    span: Span
    relation_group: str | None = None      # filled after the run by the grouping step; queries match this


class LinkRecord(Frozen):
    subject_doc: str
    relation: str
    object_ref: str                        # a DOI, an arXiv id or the cited text
    object_doc: str | None
    outside_set: bool
    span: Span
    resolve_failed: str | None = None      # OpenAlex could not be asked (network, timeout, 429/5xx): the reason


_TYPE = {Experiment: EXPERIMENT, ClaimRecord: CLAIM, LinkRecord: LINK}


def item(record: Experiment | ClaimRecord | LinkRecord) -> Item:
    """The record as an Item of its evidence type, with the record's span (the span is not repeated in fields)."""
    fields = record.model_dump(mode="json", exclude={"span"})
    if isinstance(record, LinkRecord) and record.resolve_failed is None:
        del fields["resolve_failed"]       # a resolved link's fields are as before
    return Item.build(_TYPE[type(record)], fields, [record.span])
