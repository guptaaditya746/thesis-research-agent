from __future__ import annotations

import random
import tempfile
from pathlib import Path

from anchor import anchor, resolve


def main() -> None:
    rng = random.Random(20261008)
    repo = Path(__file__).resolve().parents[2]
    source = repo / "final-final-frontend/UI/files/harness/corpus_data/outlines"
    files = sorted(source.glob("*.md"))[:20]
    assert len(files) == 20, f"found {len(files)} corpus outline files"
    selectors = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        chosen: set[tuple[int, int]] = set()
        while len(chosen) < 10:
            start = rng.randrange(len(text) - 80)
            end = min(start + rng.randrange(25, 60), len(text))
            quote = text[start:end]
            if text.count(quote) == 1:
                chosen.add((start, end))
        selectors.extend(anchor(path, start, end) for start, end in chosen)
    assert all(resolve(s) == s.quote for s in selectors)
    offsets = sum(Path(s.file).read_text(encoding="utf-8")[s.start:s.end] == s.quote for s in selectors)
    originals = {path: path.read_text(encoding="utf-8") for path in files}
    for path, text in originals.items():
        path.write_text("0123456789" + text, encoding="utf-8")
    assert all(resolve(s) == s.quote for s in selectors)
    moved = sum(Path(s.file).read_text(encoding="utf-8")[s.start:s.end] != s.quote for s in selectors)
    for s in selectors:
        path = Path(s.file)
        text = path.read_text(encoding="utf-8")
        pos = text.find(s.quote)
        assert pos >= 0
        path.write_text(text[:pos] + text[pos + len(s.quote):], encoding="utf-8")
        assert resolve(s) is None
        path.write_text(text, encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        duplicate = Path(tmp) / "duplicate.md"
        duplicate.write_text("left context " + "same quote" + " middle " + "same quote" + " right context", encoding="utf-8")
        second = duplicate.read_text(encoding="utf-8").rfind("same quote")
        s = anchor(duplicate, second, second + len("same quote"))
        assert resolve(s) == "same quote"
        duplicate.write_text("PREFIX " + duplicate.read_text(encoding="utf-8"), encoding="utf-8")
        assert resolve(s) == "same quote"
    print(f"PASS corpus_spans={len(selectors)} files={len(files)} offsets={offsets}/{len(selectors)} shifted_to_quote={moved}/{len(selectors)} deletion={len(selectors)}/{len(selectors)} duplicate=PASS")


if __name__ == "__main__":
    main()
