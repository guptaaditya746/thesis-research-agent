"""Text built piece by piece with exact offsets, so every placement holds by construction.

Offsets are Python string indices, i.e. Unicode code points of the text as stored, which is what
`agent/anchor.read_text` and every selector use. The text never contains a carriage return.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

ROLES = ("value", "condition_label", "metric_label", "claim")
SLOT = re.compile(r"\{(\w+)\}")


@dataclass(frozen=True)
class Placement:
    """One rendering of one fact. `fmt` (how a value is written: pct, frac, count, cell_pct, cell_raw,
    relative) is internal, for the fidelity check; it is not written to ground_truth.json."""
    fact: str
    role: str
    paper: str
    start: int
    end: int
    exact: str
    fmt: str | None = None

    def json(self) -> dict:
        out = asdict(self)
        del out["fmt"]
        return out


@dataclass(frozen=True)
class Seg:
    """A piece of text that renders a fact."""
    fact: str
    role: str
    text: str
    fmt: str | None = None


@dataclass(frozen=True)
class Decoy:
    """A stated value that contradicts the data (contradictory level); not a placement of the fact."""
    measurement: str
    stated_value: float
    exact: str
    start: int = -1
    end: int = -1


class Doc:
    def __init__(self, paper: str) -> None:
        self.paper = paper
        self.parts: list[str] = []
        self.pos = 0
        self.placements: list[Placement] = []
        self.decoys: list[Decoy] = []

    def add(self, text: str) -> None:
        if "\r" in text:
            raise ValueError("papers are LF only")
        self.parts.append(text)
        self.pos += len(text)

    def seg(self, piece: str | Seg | Decoy) -> None:
        if isinstance(piece, str):
            self.add(piece)
            return
        start = self.pos
        if isinstance(piece, Decoy):
            self.add(piece.exact)
            self.decoys.append(Decoy(piece.measurement, piece.stated_value, piece.exact, start, self.pos))
            return
        self.add(piece.text)
        self.placements.append(Placement(piece.fact, piece.role, self.paper, start, self.pos, piece.text, piece.fmt))

    def fill(self, template: str, **slots: str | Seg | Decoy) -> None:
        """Write `template` with its {slots}; a Seg or Decoy slot records where it landed."""
        for i, piece in enumerate(SLOT.split(template)):
            self.seg(slots[piece] if i % 2 else piece)

    def line(self, *pieces: str | Seg | Decoy) -> None:
        for p in pieces:
            self.seg(p)
        self.add("\n")

    def heading(self, title: str, level: int = 2) -> None:
        self.add(f"\n{'#' * level} {title}\n\n")

    @property
    def text(self) -> str:
        return "".join(self.parts)
