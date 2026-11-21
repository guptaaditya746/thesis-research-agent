"""Sentence splitting and name matching (code only)."""
from __future__ import annotations

import re
from typing import Any

ABBREV = re.compile(r"(\bv|\bs|\bNo|\be\.g|\bi\.e|\bcf|\bvs|\bpara|\bArt|\bSec|\bet al|\bFig|\bal)\.$")


def split_sents(md: str) -> list[tuple[int, int, str]]:
    """(start, end, text) of every sentence of 4+ words outside headings and tables. Does not split after v. / s. /
    No. / e.g. / i.e. and similar."""
    res: list[tuple[int, int, str]] = []
    pos = 0
    for line in md.splitlines(keepends=True):
        s = line.strip()
        if s and not s.startswith(("#", "|")):
            start = 0
            for m in re.finditer(r"[.!?][\"')\]]*\s+(?=[A-Z(\"'§*])", line):
                if ABBREV.search(line[max(0, m.start() - 6):m.start() + 1]):
                    continue
                _add(res, pos + start, line[start:m.end()])
                start = m.end()
            _add(res, pos + start, line[start:])
        pos += len(line)
    return res


def _add(res: list, offset: int, seg: str) -> None:
    txt = seg.strip()
    if len(txt.split()) >= 4:
        st = offset + (len(seg) - len(seg.lstrip()))
        res.append((st, st + len(txt), txt))


def names(w: dict[str, Any], eid: str) -> list[str]:
    e = w["entities"][eid]
    return [e["label"]] + e.get("alt", [])


def mentions(w: dict[str, Any], text: str, eid: str) -> bool:
    t = norm(text)
    return any(norm(n) in t for n in names(w, eid))


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", s)).strip().lower()
