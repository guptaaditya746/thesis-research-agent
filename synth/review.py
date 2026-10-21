"""Human review sheet: a seeded sample of papers with every fact and where it is rendered.

The person checking fidelity by hand opens the paper, finds each rendering at its line and offsets, and
ticks whether it is there, states the truth, and cannot be read as anything else. Markdown for reading,
CSV (same rows) for ticking and counting. In each paper the priority-1 rows come first: the measurements and the
authors' claims, which decide what a paper says. The name mentions follow as priority 2. The CSV starts with a
UTF-8 byte-order mark so that Excel opens it as UTF-8, and its check columns follow the text they judge.
"""
from __future__ import annotations

import csv
import io
import json
import random
from pathlib import Path
from typing import Any

from agent.anchor import read_text

CHECKS = ("present", "states_truth", "unambiguous")
COLUMNS = ("paper", "fact", "kind", "role", "truth", "line", "start", "end", "exact", "context", *CHECKS, "notes")
# The sheet as written: COLUMNS (what evaluation/review.py needs) plus the priority and the paper's file, in filling order.
SHEET_COLUMNS = ("paper", "priority", "kind", "fact", "truth", "exact", "context", *CHECKS, "notes",
                 "line", "start", "end", "role", "file")
PRIORITY = {"measurement": 1, "author_claim": 1, "condition": 2, "metric": 2}


def describe(study: dict[str, Any]) -> dict[str, str]:
    """Fact id -> what the ground truth says it is, in words."""
    conds = {c["id"]: c for c in study["conditions"]}
    mets = {k["id"]: k for k in study["metrics"]}
    out = {c["id"]: f"condition, role {c['role']}: {c['label']!r}" + (f" (also {', '.join(c['aliases'])})"
                                                                       if c["aliases"] else "")
           for c in study["conditions"]}
    out |= {k["id"]: f"metric {k['canonical']}: {k['name']!r}" for k in study["metrics"]}
    for m in study["measurements"]:
        c, k = conds[m["condition"]], mets[m["metric"]]
        out[m["id"]] = f"{c['role']} {c['label']!r} / {k['name']!r} / {m['dataset']} = {m['value']}"
    claim = study["author_claim"]
    if claim is not None:            # an irrelevant paper (--irrelevant) has no claim and no facts
        out[claim["id"]] = f"author claim: {claim['direction']} (data: {study['effect']['direction']})"
    return out


def context(text: str, start: int, end: int, width: int = 40) -> str:
    snippet = text[max(0, start - width):start] + "[[" + text[start:end] + "]]" + text[end:end + width]
    return snippet.replace("\n", " / ")


def rows(corpus: Path, n: int, seed: int) -> list[dict[str, Any]]:
    truth = json.loads((corpus / "ground_truth.json").read_text(encoding="utf-8"))
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    paper_file = {p["id"]: p["file"] for p in manifest["papers"]}
    files = {pid: corpus / f for pid, f in paper_file.items()}
    ids = sorted(files)
    picked = sorted(random.Random(seed).sample(ids, min(n, len(ids))))
    studies = {s["paper"]: s for s in truth["studies"]}
    out = []
    for pid in picked:
        text, what = read_text(files[pid]), describe(studies[pid])
        for p in (p for p in truth["placements"] if p["paper"] == pid):
            kind = {"value": "measurement", "condition_label": "condition", "metric_label": "metric",
                    "claim": "author_claim"}[p["role"]]
            out.append({"paper": pid, "priority": PRIORITY[kind], "file": paper_file[pid],
                        "fact": p["fact"], "kind": kind, "role": p["role"], "truth": what[p["fact"]],
                        "line": text.count("\n", 0, p["start"]) + 1, "start": p["start"], "end": p["end"],
                        "exact": p["exact"], "context": context(text, p["start"], p["end"]),
                        **{c: "" for c in CHECKS}, "notes": ""})
    return sorted(out, key=lambda r: (r["paper"], r["priority"], r["start"]))


def markdown(corpus: Path, sheet: list[dict[str, Any]], seed: int) -> str:
    lines = [f"# Fidelity review: {corpus.name} (sample seed {seed})", "",
             "For each rendering: open the paper at the line, tick **present** if the exact text is there, "
             "**states_truth** if it says what the truth column says, **unambiguous** if a reader could not "
             "take it for another fact. Note anything else (a fact stated somewhere not listed, a wrong number).",
             "", "In each paper, priority 1 (the numbers and the authors' claims) comes first; do those rows first.", ""]
    for pid in sorted({r["paper"] for r in sheet}):
        lines += [f"## {pid}", "", "| prio | fact | role | truth | line | exact | " + " | ".join(CHECKS) + " |",
                  "|---|---|---|---|---|---|" + "---|" * len(CHECKS)]
        for r in (r for r in sheet if r["paper"] == pid):
            cells = [str(r["priority"]), r["fact"], r["role"], r["truth"], str(r["line"]),
                     "`" + r["exact"].replace("|", "\\|") + "`"]
            lines.append("| " + " | ".join(c.replace("|", "\\|") if i < 4 else c for i, c in enumerate(cells))
                         + " | " + " | ".join("[ ]" for _ in CHECKS) + " |")
        lines.append("")
    return "\n".join(lines)


def write_sample(corpus: Path, n: int, seed: int, out: Path | None = None) -> tuple[Path, Path]:
    out = out or corpus / "review"
    out.mkdir(parents=True, exist_ok=True)
    sheet = rows(corpus, n, seed)
    md, cs = out / f"review-s{seed}.md", out / f"review-s{seed}.csv"
    md.write_bytes((markdown(corpus, sheet, seed) + "\n").encode("utf-8"))
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=SHEET_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(sheet)
    cs.write_bytes(buf.getvalue().encode("utf-8-sig"))   # the byte-order mark makes Excel read UTF-8
    return md, cs
