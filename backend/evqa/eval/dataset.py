"""L0: did the writer put every seed fact into paper.md, in the planned place? No LLM.

For one paper.md and its seed facts, code records:
  facts    every seed fact: the character span(s) where its value is written (compared with evqa.norm: unicode
           minus, trailing zeros, units in words, unit from the table header), whether one span is in the planned
           place (table fact -> inside a Markdown table, text fact -> in a prose sentence), and near misses (same
           number with the other sign, or percent instead of percentage points);
  extra    numbers the writer added that are no seed fact (shown amber in the Workbench);
  ignored  numbers that are clearly no result: years, doses, time points, patient counts, p-values, CI levels,
           heading and table numbers. Kept in their own list, not dropped.

When two facts share a value (-1.2 kg at 20 mg week 24 and at 40 mg week 12), a span goes to the fact whose dose,
week and measure words are next to it (same table row and headers, or same sentence).
The result reveals the truth, so it is written to data/seed/<domain>/l0/<paper>.json, never next to paper.md.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from evqa import norm
from evqa.paths import DATASET, domain_dir

TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
LABEL_HEADER = re.compile(r"dose|week|time|arm|group|treatment|visit|day|month", re.I)
COUNT_WORDS = {"patients", "participants", "people", "subjects", "adults", "persons", "sites", "centres", "centers",
               "arms", "groups", "events", "doses", "visits", "countries", "randomised", "randomized", "per"}
LIST_JOIN = r"\s*(?:,|,?\s*and|,?\s*or|to)\s*"    # between the items of '4, 8, 12 and 26'
LABEL_WORDS = {"table", "tables", "figure", "figures", "fig", "section", "sections", "type", "phase", "step",
               "appendix", "supplementary", "model"}


@dataclass
class Cell:
    start: int
    end: int
    text: str


@dataclass
class Table:
    start: int
    end: int
    caption: str
    header: list[Cell]
    rows: list[list[Cell]] = field(default_factory=list)


def _cells(line: str, offset: int) -> list[Cell]:
    bars = [i for i, c in enumerate(line) if c == "|"]
    if line.strip().startswith("|") is False:
        bars = [-1, *bars]
    if not line.rstrip().endswith("|"):
        bars.append(len(line))
    out = []
    for a, b in zip(bars, bars[1:], strict=False):
        raw = line[a + 1:b]
        lead = len(raw) - len(raw.lstrip())
        out.append(Cell(offset + a + 1 + lead, offset + a + 1 + lead + len(raw.strip()), raw.strip()))
    return out


def tables(text: str) -> list[Table]:
    """Markdown (GFM) tables with their cells as character spans; the caption is the line just above."""
    lines = text.splitlines(keepends=True)
    starts, pos = [], 0
    for ln in lines:
        starts.append(pos)
        pos += len(ln)
    out: list[Table] = []
    i = 0
    while i + 1 < len(lines):
        if "|" in lines[i] and TABLE_SEP.match(lines[i + 1].rstrip("\n")):
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            caption = lines[j].strip() if j >= 0 and "|" not in lines[j] else ""
            t = Table(starts[i], 0, caption, _cells(lines[i].rstrip("\n"), starts[i]))
            k = i + 2
            while k < len(lines) and "|" in lines[k] and lines[k].strip():
                t.rows.append(_cells(lines[k].rstrip("\n"), starts[k]))
                k += 1
            t.end = starts[k] if k < len(lines) else len(text)
            out.append(t)
            i = k
        else:
            i += 1
    return out


def _sentence(text: str, pos: int) -> tuple[str, int]:
    """The sentence around `pos` (inside one paragraph) and its start."""
    a = max(text.rfind("\n\n", 0, pos), 0)
    b = text.find("\n\n", pos)
    b = len(text) if b < 0 else b
    para = text[a:b]
    rel = pos - a
    cuts = [0] + [m.end() for m in re.finditer(r"[.!?](?=\s+[A-Z(])", para)] + [len(para)]
    for x, y in zip(cuts, cuts[1:], strict=False):
        if x <= rel < y:
            return para[x:y], a + x
    return para, a


def _heading(text: str, pos: int) -> str:
    hs = [m.group(1) for m in re.finditer(r"^#+\s*(.*)$", text[:pos], re.M)]
    return hs[-1] if hs else ""


# ---------- where each number is, and what is around it ----------

def _header_unit(head: str) -> str | None:
    """The unit a column header names; None when it names two or more ('percentage points for HbA1c; kg for body
    weight'), so the row label decides."""
    pattern, lookup = norm._unit_words()
    named = {lookup[norm._key(m.group())] for m in pattern.finditer(head) if len(m.group()) > 1}
    return norm.unit_in(head) if len(named) <= 1 else None


@dataclass
class Spot:
    found: norm.Found
    where: str          # "table" | "text"
    context: str        # words next to it (same table row and column header, or same sentence)
    far: str            # table caption or section heading: used for the measure only
    before: str         # the text just before it, for ignore rules
    after: str
    heading_line: bool = False


def spots(text: str) -> list[Spot]:
    out: list[Spot] = []
    tabs = tables(text)
    for t in tabs:
        header = [c.text for c in t.header]
        for row in [t.header, *t.rows]:
            label_parts = [f"{header[i] if i < len(header) else ''}: {c.text}" for i, c in enumerate(row)
                           if i == 0 or (i < len(header) and LABEL_HEADER.search(header[i]))]
            for i, c in enumerate(row):
                head = header[i] if i < len(header) and row is not t.header else ""
                label_col = i == 0 or bool(LABEL_HEADER.search(head))
                # a value cell takes its unit from its column header, else the row label, else the caption
                unit = None if row is t.header else _header_unit(head) or (
                    None if label_col else norm.unit_in(row[0].text) or norm.unit_in(t.caption))
                ctx = " | ".join([head, *label_parts])
                for f in norm.find_values(c.text, default_unit=unit):
                    shifted = norm.Found(c.start + f.start, c.start + f.end, f.value, f.unit_from)
                    far = t.caption + " | " + _heading(text, t.start)
                    out.append(Spot(shifted, "table", ctx, far, (head + " " + c.text[:f.start])[-30:],
                                    c.text[f.end:][:30], heading_line=row is t.header))
    # prose: table lines blanked (offsets kept) so direction words never cross into a table
    chars = list(text)
    for t in tabs:
        for k in range(t.start, t.end):
            if chars[k] != "\n":
                chars[k] = " "
    prose = "".join(chars)
    for f in norm.find_values(prose):
        line_start = prose.rfind("\n", 0, f.start) + 1
        is_heading = prose[line_start:f.start].lstrip().startswith("#")
        sent, _ = _sentence(prose, f.start)
        out.append(Spot(f, "text", sent, _heading(prose, f.start), prose[max(line_start, f.start - 30):f.start],
                        prose[f.end:f.end + 30], heading_line=is_heading))
    return sorted(out, key=lambda s: s.found.start)


# ---------- fact keys ----------

def _measure_terms(facts: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Words that tell one measure from the others: label + other names, minus words all measures share."""
    names = {f["measure"]: [f["measure"], *f.get("measure_alt", [])] for f in facts}

    def words(xs: list[str]) -> set[str]:
        return {w for x in xs for w in re.findall(r"[a-z0-9δ]+", x.lower()) if len(w) > 2}
    common = set.intersection(*(words([m]) for m in names)) if len(names) > 1 else set()
    return {m: words(xs) - common - {"change", "from", "baseline", "reduction"} for m, xs in names.items()}


def _keys(fact: dict[str, Any], ctx: str, far: str, terms: set[str]) -> dict[str, bool]:
    """Which of the fact's measure / dose / week are named next to a span. Dose and week count only when they are
    next to it, since a caption like 'at week 12 and week 24' names every week."""
    low = ctx.lower()
    out = {"measure": any(re.search(rf"(?<![a-z]){re.escape(t)}(?![a-z])", (low + " " + far.lower()))
                          for t in terms)}
    if fact.get("dose"):
        words = norm.units().get(fact["dose_unit"], {}).get("words", ["mg"])
        alt = "|".join(re.escape(w) for w in words)
        out["dose"] = bool(re.search(rf"(?<![\d.]){re.escape(fact['dose'])}\s*-?\s*(?:{alt})(?![a-z])", low))
    if fact.get("week"):
        w = re.escape(fact["week"])
        out["week"] = bool(re.search(rf"\bweeks?\s*:?\s*{w}(?![\d.])|(?<![\d.]){w}\s*-?\s*(?:weeks?|wks?)\b", low))
    return out


def _not_a_result(s: Spot) -> str | None:
    """Numbers that are never a result value, whatever they equal: headers, p-values, counts, labels, years."""
    v = s.found.value
    before = s.before.lower()
    after = s.after.lower()
    words_before = re.findall(r"[a-z]+", before)
    words_after = re.findall(r"[a-z]+", after)
    if s.heading_line:
        return "heading or table header"
    if re.search(r"\bp\s*(?:-?value)?\s*[<=>≤≥]\s*$", before):
        return "p-value"
    if re.match(r"\s*%\s*(?:ci|confidence)", after):
        return "CI level"
    if re.search(r"\bn\s*=\s*$", before) or (words_after and words_after[0] in COUNT_WORDS):
        return "count"
    if words_before and words_before[-1] in LABEL_WORDS:
        return "label"
    m = re.search(rf"\b([a-z]+)\s+\d+(?:{LIST_JOIN}\d+)*{LIST_JOIN}$", before)
    if m and m.group(1) in LABEL_WORDS and v.decimals == 0:
        return "label"                                   # the 2 of 'Tables 1 and 2'

    if v.unit is None and v.decimals == 0 and v.value is not None and 1900 <= v.value <= 2100:
        return "year"
    return None


def _setting(s: Spot, dose_units: set[str]) -> str | None:
    """Numbers left over after matching that are a dose or a time point."""
    v = s.found.value
    words_before = re.findall(r"[a-z]+", s.before.lower())
    u = norm.units().get(v.unit or "", {})
    if v.unit in dose_units:
        return "dose"
    times = {"week", "weeks", "day", "days", "month", "months", "year", "years"}
    if u.get("dimension", "").endswith("T1D0") or (words_before and words_before[-1] in times):
        return "time"
    # a later item of 'weeks 12 and 24' or 'weeks 4, 8, 12, 26 and 52'
    if re.search(rf"\b(?:weeks?|days?|months?)\s+\d+(?:{LIST_JOIN}\d+)*{LIST_JOIN}$", s.before.lower()):
        return "time"
    return None


def _with_unit(v: norm.Value, unit: str) -> norm.Value:
    return norm.Value(v.value, unit, v.decimals, v.sign_basis, v.low, v.high, v.raw)


def _flip(v: norm.Value) -> norm.Value:
    def neg(d: Decimal | None) -> Decimal | None:
        return None if d is None else -d
    return norm.Value(neg(v.value), v.unit, v.decimals, v.sign_basis, neg(v.high), neg(v.low), v.raw)


def check_text(text: str, facts: list[dict[str, Any]]) -> dict[str, Any]:
    """L0 of one paper text against its seed facts (as from evqa.seed.brief.paper_facts)."""
    all_spots = spots(text)
    terms = _measure_terms(facts) if facts else {}
    seeds = {f["id"]: norm.seed_value(f["value"], f["unit"]) for f in facts}
    by_fact: dict[str, list[dict[str, Any]]] = {f["id"]: [] for f in facts}
    near: dict[str, list[dict[str, Any]]] = {f["id"]: [] for f in facts}
    extra, ignored = [], []
    dose_units = {f["dose_unit"] for f in facts if f.get("dose_unit")}
    for s in all_spots:
        v = s.found.value
        base = {"start": s.found.start, "end": s.found.end, "raw": v.raw, "where": s.where}
        cands = []
        kind = _not_a_result(s)
        if kind is None:
            for f in facts:
                pv = v if v.unit is not None else _with_unit(v, f["unit"])
                m = norm.same(pv, seeds[f["id"]])
                if m.verdict is norm.Verdict.SAME:
                    keys = _keys(f, s.context, s.far, terms[f["measure"]])
                    cands.append((sum(keys.values()), f, keys))
                elif norm.same(_flip(pv), seeds[f["id"]]).verdict is norm.Verdict.SAME:
                    near[f["id"]].append({**base, "why": "same number, other sign"})
                elif m.verdict is norm.Verdict.DIFFERENT and "percent" in m.reason and \
                        norm.same(_with_unit(pv, f["unit"]), seeds[f["id"]]).verdict is norm.Verdict.SAME:
                    near[f["id"]].append({**base, "why": m.reason})
        if cands:
            best = max(c[0] for c in cands)
            winners = [c for c in cands if c[0] == best]
            for score, f, keys in winners:
                by_fact[f["id"]].append({**base, "keys": keys, "score": score, "ambiguous": len(winners) > 1,
                                         "unit_stated": s.found.unit_from != "none"})
            continue
        kind = kind or _setting(s, dose_units)
        row = {**base, "value": v.as_json()}
        if kind:
            ignored.append({**row, "kind": kind})
        else:
            extra.append(row)
    out_facts = []
    for f in facts:
        sp = by_fact[f["id"]]
        found = bool(sp)
        out_facts.append({"id": f["id"], "value": f["value"], "unit": f["unit"],
                          "unit_text": norm.units().get(f["unit"], {}).get("write_as", f["unit"]),
                          "measure": f["measure"], "dose": f.get("dose"), "week": f.get("week"),
                          "dose_text": (f"{f['dose']} {norm.units().get(f['dose_unit'], {}).get('write_as', '')}"
                                        .strip() if f.get("dose") else None),
                          "placement": f["placement"], "status": "found" if found else "missing",
                          "in_planned_place": any(x["where"] == f["placement"] for x in sp),
                          "spans": sp, "near": near[f["id"]] if not found else []})
    summary = {"facts": len(facts), "found": sum(f["status"] == "found" for f in out_facts),
               "in_planned_place": sum(f["in_planned_place"] for f in out_facts),
               "missing": sum(f["status"] == "missing" for f in out_facts), "extra": len(extra),
               "ignored": len(ignored)}
    return {"summary": summary, "facts": out_facts, "extra": extra, "ignored": ignored}


# ---------- files ----------

def paper_path(domain: str, paper: str) -> Path:
    return DATASET / domain / paper / "paper.md"


def out_path(domain: str, paper: str) -> Path:
    return domain_dir(domain) / "l0" / f"{paper}.json"


def check_names(text: str, names: dict[str, dict[str, str]]) -> list[str]:
    """Problems with how the paper writes its made-up drugs: a code-only drug must never appear by name and its code
    must appear; a 'both' drug needs name and code. Empty list = fine (and for papers that use names only)."""
    low = text.lower()
    out = []
    for name, m in names.items():
        has_name = re.search(rf"(?<![a-z]){re.escape(name.lower())}(?![a-z])", low) is not None
        has_code = m["code"].lower() in low
        if not has_code:
            out.append(f"code {m['code']} missing")
        if m["written"] == "code" and has_name:
            out.append(f"{name} named although the paper may use only {m['code']}")
        if m["written"] == "both" and not has_name:
            out.append(f"{name} missing (name and code wanted)")
    return out


def check(domain: str, paper: str, text: str | None = None, write: bool = True) -> dict[str, Any]:
    """L0 of data/dataset/<domain>/<paper>/paper.md, written to data/seed/<domain>/l0/<paper>.json."""
    from evqa.seed.brief import paper_facts
    if text is None:
        text = paper_path(domain, paper).read_text(encoding="utf-8")
    p = paper_facts(domain)[paper]
    facts = p["facts"]
    result = {"domain": domain, "paper": paper, "made": datetime.datetime.now().isoformat(timespec="seconds"),
              "paper_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), **check_text(text, facts)}
    if p.get("names"):
        result["name_problems"] = check_names(text, p["names"])
    if write:
        path = out_path(domain, paper)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def check_domain(domain: str) -> list[dict[str, Any]]:
    """L0 of every paper of `domain` that has a paper.md; returns one summary per paper."""
    from evqa.seed.brief import paper_facts
    out = []
    for pid in paper_facts(domain):
        if paper_path(domain, pid).is_file():
            r = check(domain, pid)
            out.append({"paper": pid, **r["summary"], **({"name_problems": r["name_problems"]}
                                                          if "name_problems" in r else {})})
    return out
