"""Human review sheet: a seeded sample of papers with every fact and where it is rendered.

The person checking fidelity by hand opens the paper, finds each rendering at its line and offsets, and
ticks whether it is there, states the truth, and cannot be read as anything else. Markdown for reading,
CSV (same rows) for ticking and counting.
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
    out[claim["id"]] = f"author claim: {claim['direction']} (data: {study['effect']['direction']})"
    return out


def context(text: str, start: int, end: int, width: int = 40) -> str:
    snippet = text[max(0, start - width):start] + "[[" + text[start:end] + "]]" + text[end:end + width]
    return snippet.replace("\n", " / ")


def rows(corpus: Path, n: int, seed: int) -> list[dict[str, Any]]:
    truth = json.loads((corpus / "ground_truth.json").read_text(encoding="utf-8"))
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    files = {p["id"]: corpus / p["file"] for p in manifest["papers"]}
    ids = sorted(files)
    picked = sorted(random.Random(seed).sample(ids, min(n, len(ids))))
    studies = {s["paper"]: s for s in truth["studies"]}
    out = []
    for pid in picked:
        text, what = read_text(files[pid]), describe(studies[pid])
        for p in (p for p in truth["placements"] if p["paper"] == pid):
            kind = {"value": "measurement", "condition_label": "condition", "metric_label": "metric",
                    "claim": "author_claim"}[p["role"]]
            out.append({"paper": pid, "fact": p["fact"], "kind": kind, "role": p["role"], "truth": what[p["fact"]],
                        "line": text.count("\n", 0, p["start"]) + 1, "start": p["start"], "end": p["end"],
                        "exact": p["exact"], "context": context(text, p["start"], p["end"]),
                        **{c: "" for c in CHECKS}, "notes": ""})
    return out


def markdown(corpus: Path, sheet: list[dict[str, Any]], seed: int) -> str:
    lines = [f"# Fidelity review: {corpus.name} (sample seed {seed})", "",
             "For each rendering: open the paper at the line, tick **present** if the exact text is there, "
             "**states_truth** if it says what the truth column says, **unambiguous** if a reader could not "
             "take it for another fact. Note anything else (a fact stated somewhere not listed, a wrong number).",
             ""]
    for pid in sorted({r["paper"] for r in sheet}):
        lines += [f"## {pid}", "", "| fact | role | truth | line | exact | " + " | ".join(CHECKS) + " |",
                  "|---|---|---|---|---|" + "---|" * len(CHECKS)]
        for r in (r for r in sheet if r["paper"] == pid):
            cells = [r["fact"], r["role"], r["truth"], str(r["line"]), "`" + r["exact"].replace("|", "\\|") + "`"]
            lines.append("| " + " | ".join(c.replace("|", "\\|") if i < 3 else c for i, c in enumerate(cells))
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
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(sheet)
    cs.write_bytes(buf.getvalue().encode("utf-8"))
    return md, cs
