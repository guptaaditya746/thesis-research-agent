"""TextQuoteSelector + TextPositionSelector anchors for UTF-8 Markdown."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Selector:
    file: str
    start: int
    end: int
    quote: str
    prefix: str
    suffix: str
    sha256: str

    def json(self) -> dict[str, str | int]:
        return asdict(self)


def anchor(file: Path, start: int, end: int, context: int = 32) -> Selector:
    text = file.read_text(encoding="utf-8")
    if not (0 <= start < end <= len(text)):
        raise ValueError("span must be a non-empty range inside the file")
    quote = text[start:end]
    return Selector(
        file=str(file), start=start, end=end, quote=quote,
        prefix=text[max(0, start - context):start],
        suffix=text[end:end + context],
        sha256=hashlib.sha256(quote.encode("utf-8")).hexdigest(),
    )


def resolve(selector: Selector) -> str | None:
    text = Path(selector.file).read_text(encoding="utf-8")
    digest = hashlib.sha256(selector.quote.encode("utf-8")).hexdigest()
    if digest != selector.sha256:
        return None
    if text[selector.start:selector.end] == selector.quote:
        return selector.quote
    hits: list[int] = []
    cursor = 0
    while (found := text.find(selector.quote, cursor)) >= 0:
        hits.append(found)
        cursor = found + 1
    if not hits:
        return None
    if len(hits) == 1:
        return selector.quote

    def score(pos: int) -> tuple[int, int, int]:
        before = text[max(0, pos - len(selector.prefix)):pos]
        after = text[pos + len(selector.quote):pos + len(selector.quote) + len(selector.suffix)]
        prefix_match = sum(a == b for a, b in zip(reversed(before), reversed(selector.prefix)))
        suffix_match = sum(a == b for a, b in zip(after, selector.suffix))
        return prefix_match + suffix_match, -abs(pos - selector.start), prefix_match

    ranked = sorted(((score(pos), pos) for pos in hits), reverse=True)
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        return None
    return selector.quote
