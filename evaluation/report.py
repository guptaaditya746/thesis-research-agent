"""report.json and report.md for one run, and the comparison over several corpora (per level).

report.json holds every number score.py computed, floats rounded to 4 places, keys sorted, so two
evaluations of the same inputs give the same bytes. report.md is the same numbers as tables
(tabulate, GitHub format) for reading and for the thesis appendix.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tabulate import tabulate

LEVEL_ORDER = ("explicit", "paraphrased", "distributed", "complex", "contradictory", "mixed", "all")


def rounded(obj: Any, places: int = 4) -> Any:
    if isinstance(obj, float):
        return round(obj, places)
    if isinstance(obj, dict):
        return {k: rounded(v, places) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [rounded(v, places) for v in obj]
    return obj


def dumps(obj: Any) -> str:
    return json.dumps(rounded(obj), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _level_key(level: str) -> tuple[int, str]:
    return (LEVEL_ORDER.index(level) if level in LEVEL_ORDER else len(LEVEL_ORDER), level)


def _fmt(value: Any) -> Any:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.3f}"
    return value


def table(rows: list[dict[str, Any]], columns: list[str], headers: list[str] | None = None) -> str:
    return tabulate([[_fmt(r.get(c)) for c in columns] for r in rows], headers=headers or columns,
                    tablefmt="github", disable_numparse=True)


def render(report: dict[str, Any]) -> str:
    """report.md for one run."""
    out = [f"# Evaluation of run {report.get('run_id') or '(baselines only)'} on {report['corpus_id']}", "",
           f"Question: {report.get('question', '')}", f"Levels: {', '.join(report['levels'])}", ""]
    if report.get("extraction"):
        rows = sorted(report["extraction"]["rows"], key=lambda r: (r["evidence_type"], _level_key(r["level"])))
        out += ["## A. Extraction", "", table(rows, ["evidence_type", "level", "items", "facts", "matched", "precision",
                                                    "recall", "f1", "span_accuracy"]), "",
                f"Facts no item matched: {len(report['extraction']['missed'])}; items matching no fact: "
                f"{len(report['extraction']['unmatched_items'])}.", ""]
    if report.get("integration"):
        rows = sorted(report["integration"]["rows"], key=lambda r: _level_key(r["level"]))
        out += ["## B. Integration", "", table(rows, ["level", "matched_measurements", "association_accuracy",
                                                     "condition_role_accuracy", "metric_accuracy", "condition_exact",
                                                     "metric_exact", "studies", "true_pair"]), ""]
    if report.get("synthesis"):
        out += ["## C. Synthesis", ""]
        summary = []
        for system in report["synthesis"]:
            overall = next((r for r in system["rows"] if r["level"] == "all"), {})
            summary.append({"system": system["system"], "label": system["label"], "expected": system["expected_label"],
                            "label_correct": system["label_correct"], "studies": overall.get("studies"),
                            "direction_accuracy": overall.get("direction_accuracy"),
                            "answered": overall.get("answered"),
                            "accuracy_answered": overall.get("accuracy_answered"),
                            "completeness": overall.get("completeness"),
                            "traceability": overall.get("traceability")})
        out += [table(summary, ["system", "label", "expected", "label_correct", "studies", "direction_accuracy",
                                "answered", "accuracy_answered", "completeness", "traceability"]), "",
                "direction_accuracy counts a study the system did not answer as wrong; accuracy_answered is the "
                "accuracy over the studies it answered (a baseline may cite only some papers); completeness is the "
                "share of studies with a determined true direction the system gives a stance for; traceability is "
                "the share of a baseline's cited passages that overlap a ground-truth placement of the paper they "
                "cite (none for the engine: its spans are scored in A).", ""]
        levels = [{"system": s["system"], **r} for s in report["synthesis"] for r in s["rows"] if r["level"] != "all"]
        if levels:
            levels.sort(key=lambda r: (_level_key(r["level"]), r["system"]))
            out += ["Per level:", "", table(levels, ["level", "system", "studies", "direction_accuracy", "answered",
                                                     "accuracy_answered", "completeness", "traceability"]), ""]
    if report.get("locate"):
        rows = sorted(report["locate"]["rows"], key=lambda r: (r["evidence_type"], _level_key(r["level"])))
        out += ["## Locate recall", "", table(rows, ["evidence_type", "level", "placements", "inside", "recall"]), ""]
    if report.get("cascade"):
        out += ["## Cascade contribution", "", table(report["cascade"]["rows"], ["extractor", "found", "found_matched",
                                                                               "only", "only_matched"]), "",
                "Facts no extractor found: " + (", ".join(f"{k} {v}" for k, v in
                                                       report["cascade"]["missed_by_all"].items()) or "none"), ""]
    if report.get("cost"):
        cost = report["cost"]
        rows = [{"measure": k, "total": v, "per_paper": cost["per_paper"].get(k)} for k, v in cost["total"].items()]
        out += ["## Cost", "", table(rows, ["measure", "total", "per_paper"]), ""]
    if report.get("stability"):
        out += ["## Re-execution stability", "", table(report["stability"]["rows"], ["extractor", "calls", "identical",
                                                                                  "identical_share", "item_stability"]),
                ""]
    return "\n".join(line.rstrip() for line in out)


def _write(obj: dict[str, Any], markdown: str, out: Path, name: str) -> tuple[Path, Path]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    js, md = out / f"{name}.json", out / f"{name}.md"
    js.write_text(dumps(obj), encoding="utf-8", newline="\n")
    md.write_text(markdown, encoding="utf-8", newline="\n")
    return js, md


def write_report(report: dict[str, Any], out: Path) -> tuple[Path, Path]:
    """report.json and report.md in `out`."""
    return _write(report, render(report), out, "report")


# --- several corpora -------------------------------------------------------------------------------

def corpus_level(report: dict[str, Any]) -> str:
    levels = report.get("levels") or []
    return levels[0] if len(levels) == 1 else "mixed"


def _overall(rows: list[dict[str, Any]] | None, **match: str) -> dict[str, Any]:
    return next((r for r in rows or [] if all(r.get(k) == v for k, v in match.items())), {})


def compare(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """One row per corpus and system: the headline numbers of A, B and C, ordered by difficulty level."""
    rows = []
    for report in reports:
        level = corpus_level(report)
        a = _overall((report.get("extraction") or {}).get("rows"), evidence_type="all", level="all")
        b = _overall((report.get("integration") or {}).get("rows"), level="all")
        for system in report.get("synthesis") or []:
            c = _overall(system["rows"], level="all")
            engine = system["system"] == "evidence-engine"
            rows.append({"level": level, "corpus_id": report["corpus_id"], "system": system["system"],
                         "extraction_f1": a.get("f1") if engine else None,
                         "span_accuracy": a.get("span_accuracy") if engine else None,
                         "association_accuracy": b.get("association_accuracy") if engine else None,
                         "true_pair": b.get("true_pair") if engine else None,
                         "direction_accuracy": c.get("direction_accuracy"), "answered": c.get("answered"),
                         "accuracy_answered": c.get("accuracy_answered"), "completeness": c.get("completeness"),
                         "traceability": None if engine else c.get("traceability"),  # the engine's spans: A
                         "label_correct": system["label_correct"]})
    rows.sort(key=lambda r: (_level_key(r["level"]), r["corpus_id"], r["system"]))
    return {"rows": rows}


COMPARE_COLUMNS = ["level", "corpus_id", "system", "extraction_f1", "span_accuracy", "association_accuracy",
                   "true_pair", "direction_accuracy", "answered", "accuracy_answered", "completeness", "traceability",
                   "label_correct"]


def render_compare(comparison: dict[str, Any]) -> str:
    return "\n".join(["# Comparison over corpora", "", table(comparison["rows"], COMPARE_COLUMNS), ""])


def write_compare(comparison: dict[str, Any], out: Path) -> tuple[Path, Path]:
    """compare.json and compare.md in `out`."""
    return _write(comparison, render_compare(comparison), out, "compare")
