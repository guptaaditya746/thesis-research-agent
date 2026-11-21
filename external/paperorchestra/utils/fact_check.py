# Added for the thesis vendoring (not upstream). See VENDORED.md, change C5.
"""Deterministic check that every value of experimental_log.md is in the paper, exactly and in its place.

Rule checked (the same rule the prompts state):
  * a fact with placement "table" must appear as the exact value string inside a Markdown table whose
    header or cells contain the fact's unit;
  * a fact with placement "text" must appear in a sentence (a non-table, non-heading line) as
    "<value> <unit>" (one optional space between), and must not also sit in a table;
  * "exact" = same characters: same decimals, same ASCII minus sign. "-0.570", "0.57" or "−0.57" do not match "-0.57".
Several facts can share one value and unit; the check then counts occurrences (a multiset), not just presence.

Also reported (not repaired): decimal numbers in the paper that occur in neither input file ("extra numbers"),
and row ids that leaked into the paper.

Stdlib only, so the main project's tests can load this file directly.
"""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

ROW_ID = re.compile(r"\bR-[A-Za-z]+-\d+-\d+\b")
NUMBER = re.compile(r"(?<![\w.])[-−+]?\d+(?:\.\d+)?(?![\w])")
MAX_PARALLEL = 3


# ---------------------------------------------------------------------------------------------------------------
# Reading the facts out of experimental_log.md
# ---------------------------------------------------------------------------------------------------------------
def _placement(text: str) -> str | None:
    t = text.lower()
    if "table" in t:
        return "table"
    if any(w in t for w in ("sentence", "text", "prose")):
        return "text"
    return None


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_facts(log_md: str) -> list[dict[str, str]]:
    """Every seed fact of the log: {id, value, unit, placement, line}.

    Accepts a Markdown table with columns for the row id, value, unit and placement (header names containing
    "id"/"row", "value", "unit", "place"/"where"), or one line per fact such as
    `- R-med-01-02: ... value: -0.57; unit: pp; placement: state in a sentence`.
    Raises ValueError when a line with a row id gives no value or no placement (fail loudly, never guess)."""
    facts: list[dict[str, str]] = []
    header: list[str] | None = None
    seen: set[str] = set()
    for line in log_md.splitlines():
        s = line.strip()
        if s.startswith("|"):
            cells = _cells(s)
            if not ROW_ID.search(s):
                if not all(set(c) <= set("-: ") for c in cells):
                    header = [c.lower() for c in cells]
                continue
            if header is not None and len(cells) == len(header):
                col = {name: i for i, name in enumerate(header)}

                def pick(*keys: str) -> str | None:
                    for name, i in col.items():
                        if any(k in name for k in keys):
                            return cells[i]
                    return None
                rid = ROW_ID.search(s).group(0)
                value, unit, place = pick("value"), pick("unit"), pick("place", "where")
                m = re.match(r"`?([-+]?\d+(?:\.\d+)?)`?\s*(.*)", (value or "").strip())
                if m is None or place is None or _placement(place) is None:
                    raise ValueError(f"fact line without value or placement: {line!r}")
                unit = (unit or m.group(2) or "").strip("` ")
                fact = {"id": rid, "value": m.group(1), "unit": unit, "placement": _placement(place), "line": s}
            else:
                fact = _fact_from_free_line(s)
        elif ROW_ID.search(s):
            fact = _fact_from_free_line(s)
        else:
            continue
        if fact["id"] in seen:
            raise ValueError(f"row id {fact['id']} appears twice in experimental_log.md")
        seen.add(fact["id"])
        facts.append(fact)
    return facts


def _fact_from_free_line(s: str) -> dict[str, str]:
    rid = ROW_ID.search(s).group(0)
    value = re.search(r"value\W{0,3}\s*`?([-+]?\d+(?:\.\d+)?)`?", s, re.I)
    unit = re.search(r"unit\W{0,3}\s*`?([^;,|`]+?)`?\s*(?:[;,|]|$)", s, re.I)
    place = re.search(r"(?:placement|place|where)\W{0,3}\s*([^;|]+)", s, re.I)
    p = _placement(place.group(1)) if place else _placement(s)
    if value is None or p is None:
        raise ValueError(f"fact line without value or placement: {s!r}")
    return {"id": rid, "value": value.group(1), "unit": unit.group(1).strip() if unit else "",
            "placement": p, "line": s}


# ---------------------------------------------------------------------------------------------------------------
# Splitting the paper
# ---------------------------------------------------------------------------------------------------------------
def split_sections(md: str) -> list[tuple[str, str]]:
    """[(title, text)] at level-2 headings ("## ..."). Text includes its heading line. The part before the
    first "## " is returned with title "" (paper title)."""
    parts: list[tuple[str, str]] = []
    title, buf = "", []
    for line in md.splitlines(keepends=True):
        if line.startswith("## "):
            if buf or title:
                parts.append((title, "".join(buf)))
            title, buf = line[3:].strip(), [line]
        else:
            buf.append(line)
    parts.append((title, "".join(buf)))
    return parts


def join_sections(parts: list[tuple[str, str]]) -> str:
    out = []
    for _, text in parts:
        out.append(text if text.endswith("\n") else text + "\n")
    return "".join(out)


def norm_title(t: str) -> str:
    t = re.sub(r"^[\s#]*(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s*", "", t.strip())
    return re.sub(r"\s+", " ", t).strip().lower()


def find_section(parts: list[tuple[str, str]], title: str) -> int | None:
    want = norm_title(title)
    for i, (t, _) in enumerate(parts):
        if t and norm_title(t) == want:
            return i
    for i, (t, _) in enumerate(parts):
        if t and (want in norm_title(t) or norm_title(t) in want) and want:
            return i
    return None


def _blocks(md: str) -> tuple[list[str], list[str]]:
    """(tables, prose_lines). A table is a run of lines starting with '|'. Headings are neither."""
    tables, prose, cur = [], [], []
    for line in md.splitlines():
        if line.strip().startswith("|"):
            cur.append(line)
            continue
        if cur:
            tables.append("\n".join(cur))
            cur = []
        if line.lstrip().startswith("#") or not line.strip():
            continue
        prose.append(line)
    if cur:
        tables.append("\n".join(cur))
    return tables, prose


def _value_re(value: str) -> str:
    return rf"(?<![\w.\-−–+]){re.escape(value)}(?!\d|\.\d)"


def _unit_re(unit: str) -> str:
    return rf"(?<![A-Za-z]){re.escape(unit)}(?![A-Za-z])"


def count_places(md: str, value: str, unit: str) -> dict[str, int]:
    tables, prose = _blocks(md)
    in_table = 0
    for t in tables:
        if unit and not re.search(_unit_re(unit), t):
            continue
        in_table += len(re.findall(_value_re(value), t))
    with_unit = _value_re(value) + (r"[  ]?" + _unit_re(unit) if unit else "")
    in_text = sum(len(re.findall(with_unit, line)) for line in prose)
    return {"table": in_table, "text": in_text}


def check_facts(md: str, facts: list[dict[str, str]]) -> list[dict[str, Any]]:
    """One result per fact, in input order: {id, value, unit, placement, ok, reason}."""
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for f in facts:
        groups[(f["value"], f["unit"])].append(f)
    result: dict[str, dict[str, Any]] = {}
    for (value, unit), fs in groups.items():
        got = count_places(md, value, unit)
        need_table = [f for f in fs if f["placement"] == "table"]
        need_text = [f for f in fs if f["placement"] == "text"]
        for i, f in enumerate(need_table):
            ok = i < got["table"]
            result[f["id"]] = {**_pub(f), "ok": ok, "found": got,
                               "reason": None if ok else
                               f"not found in a table: the exact string {value} must be a table cell, "
                               f"and the unit {unit} must be in that table's header or cells"}
        extra_in_table = got["table"] > len(need_table)
        for i, f in enumerate(need_text):
            if i >= got["text"]:
                reason = (f"not found in a sentence: write exactly \"{value} {unit}\" in a sentence"
                          if unit else f"not found in a sentence: write exactly {value} in a sentence")
                ok = False
            elif extra_in_table:
                reason = f"{value} {unit} also appears in a table; this value must be stated in a sentence only"
                ok = False
            else:
                reason, ok = None, True
            result[f["id"]] = {**_pub(f), "ok": ok, "found": got, "reason": reason}
    return [result[f["id"]] for f in facts]


def _pub(f: dict[str, str]) -> dict[str, str]:
    return {k: f[k] for k in ("id", "value", "unit", "placement")}


def extra_numbers(md: str, *allowed_texts: str) -> list[str]:
    """Decimal numbers (and percentages) in the paper that occur in none of the input texts."""
    allowed = set()
    for t in allowed_texts:
        allowed |= {m.group(0).lstrip("+").replace("−", "-") for m in NUMBER.finditer(t)}
        allowed |= {m.group(0).lstrip("+-−") for m in NUMBER.finditer(t)}
    out = []
    md = "\n".join(l for l in md.splitlines() if not l.lstrip().startswith("#"))   # headings: section numbers
    for m in NUMBER.finditer(md):
        n = m.group(0).lstrip("+").replace("−", "-")
        if "." not in n and not md[m.end():m.end() + 1] == "%":
            continue
        if n not in allowed and n.lstrip("-") not in allowed:
            out.append(m.group(0))
    return sorted(set(out))


# Added 21 Nov 2026 (VENDORED.md, C7): stricter number audit for the v2 writer (style examples from real papers).
LABEL_BEFORE = re.compile(r"(?:table|tables|section|sections|figure|type|phase|week|weeks|and|or|to|,)\s*$", re.I)


def unsupported_numbers(md: str, *allowed_texts: str) -> list[str]:
    """Every number of the paper (integers too) that occurs in none of the input texts, except heading lines,
    labels ('Table 2', 'Section 3', 'type 2') and years 1900-2100. Stricter than extra_numbers: also catches an
    invented sample size or a number copied from a style example. Returns the distinct offending strings."""
    allowed = set()
    for t in allowed_texts:
        allowed |= {m.group(0).lstrip("+-−") for m in NUMBER.finditer(t)}
    out = set()
    for line in md.splitlines():
        if line.lstrip().startswith("#"):
            continue
        for m in NUMBER.finditer(line):
            n = m.group(0).lstrip("+-−")
            if n in allowed or re.search(r"\bsections?\s*$", line[:m.start()], re.I):   # 'Section 4.1'
                continue
            if "." not in n and (1900 <= int(n) <= 2100 or (int(n) < 20 and re.search(
                    r"(?:table|tables|section|sections|figure|type|phase)\s*(?:\d+\s*(?:,|and|or)\s*)*$",
                    line[:m.start()], re.I))):
                continue
            out.add(m.group(0))
    return sorted(out)


def exemplar_leaks(md: str, exemplar_texts: list[str], brief_texts: list[str], names: list[str] = ()) -> dict:
    """What the paper took from a style example: numbers that occur in an example but in no brief text, and
    example drug names (`names`) that the paper uses. Both lists should be empty."""
    brief_nums = {m.group(0).lstrip("+-−") for t in brief_texts for m in NUMBER.finditer(t)}
    ex_nums = {m.group(0).lstrip("+-−") for t in exemplar_texts for m in NUMBER.finditer(t)}
    body = "\n".join(l for l in md.splitlines() if not l.lstrip().startswith("#"))   # headings: section numbers
    paper_nums = {m.group(0).lstrip("+-−") for m in NUMBER.finditer(body)}
    # only numbers that carry information: decimals, or integers of 3+ digits (not 12, 24, 2)
    nums = sorted(n for n in (paper_nums & ex_nums) - brief_nums if "." in n or len(n) >= 3)
    low = md.lower()
    brief_low = " ".join(brief_texts).lower()
    used = sorted({n for n in names if n and n.lower() in low and n.lower() not in brief_low})
    return {"numbers": nums, "names": used}


# Added 21 Nov 2026 (VENDORED.md, C8): citations of the v2r writer.
CITE = re.compile(r"([A-Z][A-Za-z'\u00C0-\u017F-]+)(?: et al\.?| and [A-Z][A-Za-z'\u00C0-\u017F-]+)?,?\s*\(?((?:19|20)\d{2})[a-z]?\b")


def _ref_key(author: str, year) -> tuple[str, str]:
    import unicodedata
    a = unicodedata.normalize("NFKD", author).encode("ascii", "ignore").decode().lower()
    return a, str(year)


def check_citations(md: str, refs: list[dict]) -> dict:
    """Citations "(Surname et al., 2020)" in the paper (References section excluded) against the provided refs
    ({id, first_author, year}). Returns {cited: [ref ids in first-cited order], unknown: [citation strings]}.
    Only text inside parentheses or "Surname et al. (2020)" counts, so years in prose are not citations."""
    body = re.split(r"^## +References\s*$", md, flags=re.M)[0]
    by_key = {_ref_key(r["first_author"], r["year"]): r["id"] for r in refs}
    cited, unknown = [], []
    spans = [m.group(1) for m in re.finditer(r"\(([^()]*?(?:19|20)\d{2}[^()]*)\)", body)]
    spans += [m.group(0) for m in re.finditer(r"[A-Z][\w'-]+ et al\.? \((?:19|20)\d{2}\)", body)]
    for sp in spans:
        for m in CITE.finditer(sp):
            if " et al" not in m.group(0) and " and " not in m.group(0) and "," not in m.group(0):
                continue          # "week 2024"-like false hits: need "et al", "and" or "Surname, 2020"
            rid = by_key.get(_ref_key(m.group(1), m.group(2)))
            if rid is None:
                unknown.append(m.group(0))
            elif rid not in cited:
                cited.append(rid)
    return {"cited": cited, "unknown": sorted(set(unknown))}


def references_section(refs: list[dict], cited: list[str]) -> str:
    """A '## References' section with only the cited refs, in first-cited order."""
    by_id = {r["id"]: r for r in refs}
    lines = ["## References", ""]
    for i, rid in enumerate(cited, 1):
        r = by_id[rid]
        venue = f" {r['venue']}." if r.get("venue") else ""
        lines.append(f"{i}. {r['authors_text']} ({r['year']}). {r['title'].rstrip('.')}.{venue}")
    return "\n".join(lines) + "\n"


def leaked_row_ids(md: str) -> list[str]:
    return sorted(set(ROW_ID.findall(md)))


def summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {"facts": len(results), "ok": sum(r["ok"] for r in results),
            "failed": [r["id"] for r in results if not r["ok"]]}


# ---------------------------------------------------------------------------------------------------------------
# One bounded repair round
# ---------------------------------------------------------------------------------------------------------------
def section_for_fact(parts: list[tuple[str, str]], fact: dict[str, str], assigned: dict[str, str]) -> int:
    """Where a failing fact should be repaired: its planned section if the paper has it, else a section whose
    title says "result", else the longest section."""
    if fact["id"] in assigned:
        i = find_section(parts, assigned[fact["id"]])
        if i is not None:
            return i
    for i, (t, _) in enumerate(parts):
        if "result" in t.lower():
            return i
    return max(range(len(parts)), key=lambda i: len(parts[i][1]))


RepairFn = Callable[[str, str, list[dict[str, Any]]], str]


def repair_round(md: str, facts: list[dict[str, str]], assigned: dict[str, str], repair: RepairFn,
                 *, max_workers: int = MAX_PARALLEL) -> tuple[str, list[dict[str, Any]]]:
    """Check, then give ONE repair call per failing section (only that section's text and only its failed
    facts), at most 3 at once. A repaired section is accepted only if, after re-checking the whole paper, there
    are fewer failures and no fact that passed before now fails. No second round. Returns (paper, attempts)."""
    before = check_facts(md, facts)
    failed = [r for r in before if not r["ok"]]
    if not failed:
        return md, []
    parts = split_sections(md)
    by_section: dict[int, list[dict[str, Any]]] = defaultdict(list)
    fact_by_id = {f["id"]: f for f in facts}
    for r in failed:
        by_section[section_for_fact(parts, fact_by_id[r["id"]], assigned)].append(r)
    jobs = sorted(by_section.items())

    def run(job: tuple[int, list[dict[str, Any]]]) -> tuple[int, str | None, str | None]:
        i, fs = job
        try:
            return i, repair(parts[i][0], parts[i][1], fs), None
        except Exception as e:  # a failed repair call keeps the section as it was
            return i, None, f"{type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=min(max_workers, MAX_PARALLEL)) as pool:
        outs = list(pool.map(run, jobs))

    attempts = []
    ok_before = {r["id"] for r in before if r["ok"]}
    for (i, fs), (_, new_text, err) in zip(jobs, outs):
        entry: dict[str, Any] = {"section": parts[i][0], "failed_facts": [r["id"] for r in fs], "error": err}
        if new_text is None:
            entry["accepted"] = False
            attempts.append(entry)
            continue
        if not new_text.lstrip().startswith("## ") and parts[i][0]:
            new_text = parts[i][1].splitlines(keepends=True)[0] + new_text.lstrip("\n")
        trial = list(parts)
        trial[i] = (parts[i][0], new_text if new_text.endswith("\n") else new_text + "\n")
        cur = check_facts(join_sections(parts), facts)
        after = check_facts(join_sections(trial), facts)
        n_cur, n_after = sum(not r["ok"] for r in cur), sum(not r["ok"] for r in after)
        broke = sorted(r["id"] for r in after if not r["ok"] and r["id"] in ok_before)
        entry.update({"failures_before": n_cur, "failures_after": n_after, "newly_broken": broke,
                      "still_failed": [r["id"] for r in after if not r["ok"] and r["id"] in entry["failed_facts"]]})
        entry["accepted"] = n_after < n_cur and not broke
        if entry["accepted"]:
            parts = trial
        attempts.append(entry)
    return join_sections(parts), attempts
