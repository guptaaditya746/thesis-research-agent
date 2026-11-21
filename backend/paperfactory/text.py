"""Markdown normalization, sentence splitting and name matching (code only).

One normalization (`norm_text`) is used for paper text, QA quotes and gold spans, so offsets and matches agree.
`normalize_paper` also cuts the paper into units (heading, paragraph, list item, table cell); a sentence never
crosses a unit. Sentences come from pysbd, corrected by the field pack's abbreviations and allowed lowercase
sentence starts (pack key "text")."""
from __future__ import annotations

import re
import threading
import warnings
from dataclasses import dataclass
from typing import Any

with warnings.catch_warnings():               # pysbd 0.3.4 has invalid escape sequences (harmless SyntaxWarnings)
    warnings.simplefilter("ignore", SyntaxWarning)
    import pysbd

CHAR_MAP = {"‘": "'", "’": "'", "‚": "'", "“": '"', "”": '"', "„": '"',
            "–": "-", "—": "-", "−": "-"}
EMPHASIS = set("*_`")


# ------------------------------------------------------------------ normalization
def _norm(chars: list[tuple[str, int]]) -> tuple[str, list[int]]:
    """(char, original offset) pairs -> normalized text + the original offset of every output char."""
    out: list[str] = []
    idx: list[int] = []
    for c, i in chars:
        if c in EMPHASIS:
            continue
        c = CHAR_MAP.get(c, c)
        if c.isspace():
            if not out or out[-1] == " ":
                continue
            c = " "
        out.append(c)
        idx.append(i)
    while out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def norm_text(s: str) -> str:
    """The one normalization: no emphasis markers, straight quotes, plain dashes, single spaces."""
    return _norm([(c, i) for i, c in enumerate(s)])[0]


def norm(s: str) -> str:
    """norm_text, lower-cased (for case-blind comparisons)."""
    return norm_text(s).lower()


@dataclass(frozen=True)
class Unit:
    kind: str            # heading | paragraph | item | cell
    start: int           # offsets in Paper.text
    end: int


@dataclass(frozen=True)
class Paper:
    text: str            # normalized text, units separated by "\n"
    units: list[Unit]
    back: list[int]      # back[i] = offset in the original Markdown of text[i]; back[len(text)] = len(original)


HEADING = re.compile(r" {0,3}#{1,6}\s+(.*?)\s*#*\s*$")
ITEM = re.compile(r"\s*(?:[-*+]|\d+[.)])\s+")
TABLE_SEP = re.compile(r"\|?[\s:|-]+\|?")


def normalize_paper(md: str) -> Paper:
    blocks: list[tuple[str, list[tuple[int, int]]]] = []
    open_block: tuple[str, list[tuple[int, int]]] | None = None

    def close() -> None:
        nonlocal open_block
        if open_block:
            blocks.append(open_block)
        open_block = None

    pos = 0
    for raw in md.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        s = line.strip()
        if not s:
            close()
        elif m := HEADING.match(line):
            close()
            blocks.append(("heading", [(pos + m.start(1), pos + m.end(1))]))
        elif s.startswith("|"):
            close()
            if not TABLE_SEP.fullmatch(s):
                start = pos + line.index("|")
                for cell in re.finditer(r"[^|]+", line[line.index("|"):]):
                    if cell.group().strip():
                        blocks.append(("cell", [(start + cell.start(), start + cell.end())]))
        elif m := ITEM.match(line):
            close()
            open_block = ("item", [(pos + m.end(), pos + len(line))])
        elif open_block:
            lead = len(line) - len(line.lstrip())
            open_block[1].append((pos + lead, pos + len(line)))
        else:
            lead = len(line) - len(line.lstrip())
            open_block = ("paragraph", [(pos + lead, pos + len(line))])
        pos += len(raw)
    close()

    text: list[str] = []
    back: list[int] = []
    units: list[Unit] = []
    for kind, pieces in blocks:
        chars: list[tuple[str, int]] = []
        for a, b in pieces:
            if chars:
                chars.append((" ", a))              # a wrapped line joins with one space
            chars += [(md[i], i) for i in range(a, b)]
        t, idx = _norm(chars)
        if not t:
            continue
        if text:
            text.append("\n")
            back.append(back[-1] + 1 if back else 0)
        start = sum(len(x) for x in text)
        text.append(t)
        back += idx
        units.append(Unit(kind, start, start + len(t)))
    back.append(len(md))
    return Paper("".join(text), units, back)


# ------------------------------------------------------------------ sentences
@dataclass(frozen=True)
class SplitRules:
    abbrev_end: re.Pattern[str]          # a segment ending like this continues in the next one
    lower_start: re.Pattern[str] | None  # a sentence may start with this although it is lower case


def split_rules(f: Any, w: dict[str, Any]) -> SplitRules:
    """From the field pack ("text": abbreviations, lowercase_starts) and the world (names written in lower case)."""
    t = f.raw.get("text")
    if not t or "abbreviations" not in t or "lowercase_starts" not in t:
        raise KeyError(f"field pack {f.raw.get('field')!r} needs a 'text' section with 'abbreviations' and "
                       "'lowercase_starts'")
    abbrev = "|".join(re.escape(a) for a in sorted(t["abbreviations"], key=len, reverse=True))
    starts = list(t["lowercase_starts"]) + sorted(
        {re.escape(n) + r"\b" for e in w.get("entities", {}).values() for n in [e["label"]] + e.get("alt", [])
         if n[:1].islower()}, key=len, reverse=True)
    return SplitRules(re.compile(rf"(?:^|(?<=[\s(\[\"']))(?:{abbrev})$"),
                      re.compile("|".join(starts)) if starts else None)


_local = threading.local()


def _segments(t: str) -> list[str]:
    seg = getattr(_local, "seg", None)
    if seg is None:
        seg = _local.seg = pysbd.Segmenter(language="en", clean=False)
    return [x for x in seg.segment(t) if x.strip()]


def _split_unit(t: str, rules: SplitRules) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cur = 0
    for seg in _segments(t):                         # locate segments in order (pysbd offsets are unreliable)
        a = t.index(seg.strip(), cur)
        spans.append((a, a + len(seg.strip())))
        cur = spans[-1][1]
    merged: list[tuple[int, int]] = []
    for a, b in spans:
        if merged and rules.abbrev_end.search(t[merged[-1][0]:merged[-1][1]]):
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    if not rules.lower_start:
        return merged
    out: list[tuple[int, int]] = []
    for a, b in merged:
        for m in re.finditer(r"[.!?][\"')\]]*\s+", t[a:b]):
            cut = a + m.end()
            if rules.lower_start.match(t, cut) and not rules.abbrev_end.search(t[a:a + m.start() + 1]):
                out.append((a, a + m.start() + len(m.group().rstrip())))
                a = cut
        out.append((a, b))
    return out


def split_sents(md: str, rules: SplitRules) -> list[tuple[int, int, str]]:
    """(start, end, text) of every sentence of 4+ words in paragraphs, list items and table cells, with offsets in
    normalize_paper(md).text. Headings are not sentences; no sentence crosses a unit."""
    p = normalize_paper(md)
    res: list[tuple[int, int, str]] = []
    for u in p.units:
        if u.kind == "heading":
            continue
        t = p.text[u.start:u.end]
        for a, b in _split_unit(t, rules):
            s = t[a:b]
            if len(s.split()) >= 4:
                res.append((u.start + a, u.start + b, s))
    return res


# ------------------------------------------------------------------ names
@dataclass(frozen=True)
class Mention:
    start: int
    end: int
    eid: str
    surface: str
    subsection: str | None = None     # "(1)" when the name is followed by a subsection mark: counts as the entity


@dataclass(frozen=True)
class AliasTable:
    by_key: dict[str, str]            # surface with lower-cased first char -> entity id
    regex: re.Pattern[str] | None


SUBSECTION = re.compile(r"\([0-9A-Za-z]{1,4}\)")


def _key(name: str) -> str:
    name = norm_text(name)
    return name[:1].lower() + name[1:]


def name_variants(f: Any, kind: str, label: str) -> list[str]:
    """Extra names from the pack's patterns ("text"."name_variants"), e.g. "s. 9" for "section 9 of the ... Act"."""
    out = []
    for v in f.raw.get("text", {}).get("name_variants", []):
        if v["kind"] == kind and (m := re.search(v["match"], label)):
            out += [x.format(**m.groupdict()) for x in v["variants"]]
    return out


def all_names(w: dict[str, Any], f: Any, eid: str) -> list[str]:
    e = w["entities"][eid]
    return list(dict.fromkeys([e["label"]] + e.get("alt", []) + name_variants(f, e["kind"], e["label"])))


def alias_table(w: dict[str, Any], f: Any, extra: dict[str, str] | None = None) -> AliasTable:
    """Every name of every entity (label, alt, pack variants, plus `extra` surface -> id). A name used by two
    entities is dropped here; world.check reports it."""
    by_key: dict[str, str] = {}
    clash: set[str] = set()
    pairs = [(n, eid) for eid in w["entities"] for n in all_names(w, f, eid)] + list((extra or {}).items())
    for n, eid in pairs:
        k = _key(n)
        if not k:
            continue
        if by_key.get(k, eid) != eid:
            clash.add(k)
        by_key[k] = eid
    for k in clash:
        del by_key[k]
    if not by_key:
        return AliasTable({}, None)
    alts = "|".join("[" + re.escape(k[0]) + re.escape(k[0].upper()) + "]" + re.escape(k[1:]) if k[0].isalpha()
                    else re.escape(k) for k in sorted(by_key, key=len, reverse=True))
    return AliasTable(by_key, re.compile(rf"(?<!\w)(?:{alts})(?!\w)(?![-.]\d)"))


def find_mentions(text: str, table: AliasTable) -> list[Mention]:
    """Leftmost-longest whole-name matches in norm_text(text). A name must not touch a letter, digit or "_", and
    must not be followed by "-" or "." plus a digit ("section 9" never matches "section 91" or "section 9.1").
    Case is exact except for the first character. "section 9(1)" is section 9, with subsection "(1)"."""
    if table.regex is None:
        return []
    t = norm_text(text)
    out = []
    for m in table.regex.finditer(t):
        sub = SUBSECTION.match(t, m.end())
        out.append(Mention(m.start(), m.end(), table.by_key[_key(m.group())], m.group(), sub.group() if sub else None))
    return out


def names(w: dict[str, Any], eid: str) -> list[str]:
    e = w["entities"][eid]
    return [e["label"]] + e.get("alt", [])
