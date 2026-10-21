"""Summary of a filled-in fidelity review sheet (synth/review.py CSV): Tim M2 §6, the documents checked by hand.

A check cell holds yes/y or no/n (any case) or is empty; anything else is an error naming the row. A row is
reviewed when all three checks are filled; a `no` in any check is listed as a problem with the reviewer's notes.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from synth.review import CHECKS, COLUMNS

YES, NO = {"yes", "y"}, {"no", "n"}


def summarise(csv_path: Path) -> dict[str, Any]:
    """Counts over the sheet: rows, reviewed rows, rows ticked `yes` per check (among filled cells), problems."""
    with Path(csv_path).open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{csv_path}: not a review sheet, missing columns {', '.join(missing)}")
        sheet = list(reader)
    counts = dict.fromkeys(CHECKS, 0)
    reviewed, problems = 0, []
    for number, row in enumerate(sheet, start=2):       # line 1 is the header
        filled = 0
        for check in CHECKS:
            cell = (row[check] or "").strip()
            if not cell:
                continue
            if cell.lower() not in YES | NO:
                raise ValueError(f"row {number} ({row['paper']} {row['fact']}): {check} is {cell!r}; "
                                 "write yes or no (y or n), or leave it empty")
            filled += 1
            if cell.lower() in YES:
                counts[check] += 1
            else:
                problems.append({"paper": row["paper"], "fact": row["fact"], "check": check, "notes": row["notes"]})
        reviewed += filled == len(CHECKS)
    return {"rows": len(sheet), "reviewed": reviewed, **counts, "problems": problems}


def render(summary: dict[str, Any]) -> str:
    """The summary as text lines for the CLI."""
    out = [f"rows: {summary['rows']}", f"reviewed: {summary['reviewed']}",
           *[f"{c}: {summary[c]}" for c in CHECKS], f"problems: {len(summary['problems'])}"]
    out += [f"  {p['paper']} {p['fact']} {p['check']}: {p['notes'] or '(no notes)'}" for p in summary["problems"]]
    return "\n".join(out)
