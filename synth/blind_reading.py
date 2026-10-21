"""Read source numbers and relations; normalize and calculate them in code.

No rendering plan or private expected values enter this module.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal
import re

from pydantic import BaseModel, Field

from agent import anchor
from synth.fidelity import BlindExtraction, BlindMeasurement

DECIMAL = r"^\d+(?:,\d{3})*(?:\.\d+)?$"

class DirectReading(BaseModel):
    condition: str
    metric: str
    dataset: str
    number: str = Field(pattern=DECIMAL)
    unit: Literal["percent", "fraction", "count", "raw"]
    denominator: str | None = Field(default=None, pattern=DECIMAL)
    quote: str


class RelativeReading(BaseModel):
    condition: str
    metric: str
    dataset: str
    reference_condition: str
    points: str = Field(pattern=DECIMAL)
    direction: Literal["higher", "lower"]
    quote: str


class ReadingReply(BaseModel):
    direct: list[DirectReading]
    relative: list[RelativeReading] = Field(default_factory=list)


def number(raw: str, quote: str) -> Decimal:
    if not re.fullmatch(r"\d+(?:,\d{3})*(?:\.\d+)?", raw):
        raise ValueError("Source number must be a nonnegative decimal or count")
    # Match entire tokens so 6.7 cannot be justified by a quote containing 16.7.
    if not re.search(r"(?<![\d.,])" + re.escape(raw) + r"(?![\d.,]\d)", quote):
        raise ValueError(f"Source quote does not contain number {raw!r}")
    return Decimal(raw.replace(",", ""))


def resolve(text: str, reply: ReadingReply) -> BlindExtraction:
    """Anchor source readings, normalize units and apply explicit signed deltas."""
    index = anchor.Index(text)
    measurements = []
    for row in reply.direct:
        anchor.find(index, row.quote)
        value = number(row.number, row.quote)
        if row.unit == "percent":
            value /= 100
        elif row.unit == "count":
            denominator = number(row.denominator or "", row.quote)
            if denominator <= 0:
                raise ValueError("Count denominator must be positive")
            value /= denominator
        measurements.append(BlindMeasurement(condition=row.condition, metric=row.metric,
                                              dataset=row.dataset, value=float(value)))
    for row in reply.relative:
        anchor.find(index, row.quote)
        if not re.search(r"\b" + row.direction + r"\b", row.quote, re.IGNORECASE):
            raise ValueError("Relative direction is absent from source quote")
        points = number(row.points, row.quote)
        references = [m for m in measurements if m.condition == row.reference_condition
                      and m.metric == row.metric and m.dataset == row.dataset]
        if len(references) != 1:
            raise ValueError("Relative result needs one unambiguous extracted reference")
        value = Decimal(str(references[0].value)) + points / 100 * (1 if row.direction == "higher" else -1)
        measurements.append(BlindMeasurement(condition=row.condition, metric=row.metric,
                                              dataset=row.dataset, value=float(value)))
    return BlindExtraction(measurements=measurements)
