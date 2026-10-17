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

from .stats import interval_text
from .truth import ENGINE

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


def _ci(row: dict[str, Any] | None) -> str:
    """`0.812 [0.74, 0.88]` from an interval row ({point, low, high}; stats.interval_row)."""
    if not row:
        return "-"
    return interval_text(row.get("point"), row.get("low"), row.get("high"))


def _method(row: dict[str, Any] | None) -> str | None:
    return (row or {}).get("method")


def render_intervals(intervals: dict[str, Any]) -> list[str]:
    """The `## Intervals` section (F4): extraction F1 per type, direction accuracy per system, paired difference."""
    out = ["## Intervals", "", "95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), "
           "`point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate "
           "sample (fewer than two papers, or no spread), the point value only.", ""]
    if intervals.get("extraction"):
        rows = [{"evidence_type": r["evidence_type"], "f1": _ci(r), "method": _method(r)} for r in intervals["extraction"]]
        out += ["Extraction F1 (all levels):", "", table(rows, ["evidence_type", "f1", "method"]), ""]
    if intervals.get("synthesis"):
        paired = {r["system"]: r for r in intervals.get("paired") or []}
        rows = [{"system": r["system"], "direction_accuracy": _ci(r), "method": _method(r),
                 "engine_minus_system": _ci(paired.get(r["system"])) if r["system"] != ENGINE else "-",
                 "paired_method": _method(paired.get(r["system"])) if r["system"] != ENGINE else None}
                for r in intervals["synthesis"]]
        out += ["Direction accuracy, and the paired difference engine minus system (per study):", "",
                table(rows, ["system", "direction_accuracy", "method", "engine_minus_system", "paired_method"]), ""]
    return out


EXTRACTOR_COLUMNS = ["extractor", "evidence_type", "level", "items", "facts", "matched", "precision", "recall", "f1",
                     "span_accuracy", "association_accuracy", "only", "only_matched"]
EXTRACTOR_COST_COLUMNS = ["extractor", "calls", "model_calls", "input_tokens", "output_tokens", "seconds"]


def render_extractors(extractors: dict[str, Any]) -> list[str]:
    """The `## Per extractor` section (F4 / B11): every extractor's rows over all levels, and its cost."""
    rows = sorted((r for r in extractors.get("rows", []) if r["level"] == "all"),
                  key=lambda r: (r["extractor"], r["evidence_type"] == "all", r["evidence_type"]))
    scope = ("the facts of the documents and types the extractor was called on (its extractor_call events)"
             if extractors.get("recall_scope") == "called" else "every fact of the type (the run has no events)")
    out = ["## Per extractor", "", f"An item counts for every extractor in its `found_by`; recall is against {scope}. "
           "`evaluate benchmark` pools these rows per level over corpora.", "",
           table(rows, EXTRACTOR_COLUMNS), ""]
    if extractors.get("cost"):
        out += ["Cost per extractor (tokens need the record cache, seconds the events):", "",
                table(extractors["cost"], EXTRACTOR_COST_COLUMNS), ""]
    return out


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
                            "determined": overall.get("determined"),
                            "direction_accuracy": overall.get("direction_accuracy"),

                            "accuracy_answered": overall.get("accuracy_answered"),
                            "completeness": overall.get("completeness"),
                            "traceability": overall.get("traceability")})
        out += [table(summary, ["system", "label", "expected", "label_correct", "studies", "determined",
                                "direction_accuracy", "completeness", "accuracy_answered", "traceability"]), "",
                "direction_accuracy is over all scored studies: a study whose expected direction is undetermined "
                "(missing information, an irrelevant paper) is right when the system says undetermined or leaves it "
                "out, a determined study is wrong then. completeness (the supervisor's word: the share of the "
                "`determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) "
                "are over the determined studies only, so a baseline that cites only some papers, or guesses on "
                "undeterminable ones, is seen in both. traceability is the share of a baseline's cited passages that "
                "overlap a ground-truth placement of the paper they cite, dropped citations counted as untraced "
                "(none for the engine: its spans are scored in A).", ""]
        levels = [{"system": s["system"], **r} for s in report["synthesis"] for r in s["rows"] if r["level"] != "all"]
        if levels:
            levels.sort(key=lambda r: (_level_key(r["level"]), r["system"]))
            out += ["Per level:", "", table(levels, ["level", "system", "studies", "determined", "direction_accuracy",
                                                     "completeness", "accuracy_answered", "traceability"]), ""]
        flagged = [s for s in report["synthesis"] if s.get("flags")]
        if flagged:
            rows = [{"system": s["system"], **r} for s in flagged for r in s["flags"]["rows"]]
            verdicts = [{"system": s["system"], "counts_correct": s["flags"]["counts_correct"],
                         "duplicates_correct": s["flags"]["duplicates_correct"]} for s in flagged]
            out += ["Flags (F1; a system without `flags` is not listed):", "",
                    table(rows, ["system", "flag", "tp", "fp", "fn", "precision", "recall"]), "",
                    table(verdicts, ["system", "counts_correct", "duplicates_correct"]), ""]
    if report.get("intervals"):
        out += render_intervals(report["intervals"])
    if report.get("locate"):
        rows = sorted(report["locate"]["rows"], key=lambda r: (r["evidence_type"], _level_key(r["level"])))
        out += ["## Locate recall", "", table(rows, ["evidence_type", "level", "placements", "inside", "recall"]), ""]
    if report.get("cascade"):
        out += ["## Cascade contribution", "", table(report["cascade"]["rows"], ["extractor", "found", "found_matched",
                                                                               "only", "only_matched"]), "",
                "Facts no extractor found: " + (", ".join(f"{k} {v}" for k, v in
                                                       report["cascade"]["missed_by_all"].items()) or "none"), ""]
    if report.get("extractors"):
        out += render_extractors(report["extractors"])
    if report.get("cost"):
        cost = report["cost"]
        rows = [{"measure": k, "total": v, "per_paper": cost["per_paper"].get(k)} for k, v in cost["total"].items()]
        out += ["## Cost", "", table(rows, ["measure", "total", "per_paper"]), ""]
    if report.get("stability"):
        out += ["## Re-execution stability", "", table(report["stability"]["rows"], ["extractor", "calls", "identical",
                                                                                  "identical_share", "item_stability"]),
                ""]
    if report.get("funnel"):
        out += render_funnel(report["funnel"])
    return "\n".join(line.rstrip() for line in out)


def render_funnel(funnel: dict[str, Any]) -> list[str]:
    """The `## Funnel` section (Part D): cost per document, where the funnel stopped, the screen's scores."""
    means = funnel.get("per_document") or {}
    rows = [{"measure": k, "per_document": means.get(k)} for k in ("calls", "model_calls", "input_tokens", "output_tokens")]
    stops = [{"stopped_after": k, "documents": v} for k, v in (funnel.get("stop_positions") or {}).items()]
    out = ["## Funnel", "", f"Strategy `{funnel.get('strategy')}` over {funnel.get('documents')} documents "
           "(docs/evidence-system.md Part D). Cost per document from the extractor_call events (tokens need the "
           "record cache); `stopped_after` is the cascade position after which the study was complete, `exhausted` "
           "when the funnel ran out of positions (every document in `all` mode), `skipped` a screened-out document.",
           "", table(rows, ["measure", "per_document"]), "", table(stops, ["stopped_after", "documents"]), ""]
    screen = funnel.get("screen")
    if screen:
        out += ["Screen (the decision `relevant` against the ground truth's `relevant`; recall is the share of the "
                "relevant papers kept):", "",
                table([screen], ["documents", "tp", "fp", "fn", "tn", "precision", "recall"]), "",
                "Screened out wrongly: " + (", ".join(screen.get("screened_out_wrongly") or []) or "none"), ""]
    return out


def write_pair(obj: dict[str, Any], markdown: str, out: Path, name: str) -> tuple[Path, Path]:
    """`<out>/<name>.json` (rounded, sorted keys) and `<out>/<name>.md`; the paths written."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    js, md = out / f"{name}.json", out / f"{name}.md"
    js.write_text(dumps(obj), encoding="utf-8", newline="\n")
    md.write_text(markdown, encoding="utf-8", newline="\n")
    return js, md


def write_report(report: dict[str, Any], out: Path) -> tuple[Path, Path]:
    """report.json and report.md in `out`."""
    return write_pair(report, render(report), out, "report")


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
        funnel = report.get("funnel") or {}
        per_doc, screen = funnel.get("per_document") or {}, funnel.get("screen") or {}
        for system in report.get("synthesis") or []:
            c = _overall(system["rows"], level="all")
            engine = system["system"] == ENGINE
            rows.append({"level": level, "corpus_id": report["corpus_id"], "system": system["system"],
                         "run_id": report.get("run_id") if engine else None,
                         "strategy": funnel.get("strategy") if engine else None,
                         "extraction_f1": a.get("f1") if engine else None,
                         "span_accuracy": a.get("span_accuracy") if engine else None,
                         "association_accuracy": b.get("association_accuracy") if engine else None,
                         "true_pair": b.get("true_pair") if engine else None,
                         "direction_accuracy": c.get("direction_accuracy"),
                         "accuracy_answered": c.get("accuracy_answered"), "completeness": c.get("completeness"),
                         "traceability": None if engine else c.get("traceability"),  # the engine's spans: A
                         "label_correct": system["label_correct"],
                         # the funnel (Part D): an `all` and a `gaps` run of one protocol stand in two rows
                         "calls_per_document": per_doc.get("calls") if engine else None,
                         "tokens_per_document": per_doc.get("tokens") if engine else None,
                         "screen_precision": screen.get("precision") if engine else None,
                         "screen_recall": screen.get("recall") if engine else None})
    rows.sort(key=lambda r: (_level_key(r["level"]), r["corpus_id"], r["system"], r.get("strategy") or "", r.get("run_id") or ""))
    return {"rows": rows, "intervals": compare_intervals(reports)}


def compare_intervals(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per corpus and system with the interval rows of report.json `intervals` (F4): the engine's
    extraction F1 over all types, the system's direction accuracy and the paired difference engine minus
    system; each `{point, low, high}` or null."""
    rows = []
    for report in reports:
        intervals = report.get("intervals") or {}
        level = corpus_level(report)
        f1 = _overall(intervals.get("extraction"), evidence_type="all") or None
        paired = {r["system"]: r for r in intervals.get("paired") or []}
        for system in intervals.get("synthesis") or []:
            name = system["system"]
            rows.append({"level": level, "corpus_id": report["corpus_id"], "system": name,
                         "extraction_f1": _strip(f1) if name == ENGINE else None,
                         "direction_accuracy": _strip(system),
                         "engine_minus_system": _strip(paired.get(name)) if name != ENGINE else None})
    rows.sort(key=lambda r: (_level_key(r["level"]), r["corpus_id"], r["system"]))
    return rows


def _strip(row: dict[str, Any] | None) -> dict[str, Any] | None:
    return {k: row.get(k) for k in ("point", "low", "high", "method")} if row else None


COMPARE_COLUMNS = ["level", "corpus_id", "system", "strategy", "extraction_f1", "span_accuracy", "association_accuracy",
                   "true_pair", "direction_accuracy", "completeness", "accuracy_answered", "traceability",
                   "label_correct", "calls_per_document", "tokens_per_document", "screen_precision", "screen_recall"]
COMPARE_INTERVAL_COLUMNS = ["level", "corpus_id", "system", "extraction_f1", "direction_accuracy", "engine_minus_system"]


def render_compare(comparison: dict[str, Any]) -> str:
    out = ["# Comparison over corpora", "", table(comparison["rows"], COMPARE_COLUMNS), ""]
    if comparison.get("intervals"):
        rows = [{**r, **{k: _ci(r.get(k)) for k in ("extraction_f1", "direction_accuracy", "engine_minus_system")}}
                for r in comparison["intervals"]]
        out += ["## Intervals", "", "95 % bootstrap over papers, `point [low, high]` (BCa, or percentile where BCa is "
                "undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample.",
                "", table(rows, COMPARE_INTERVAL_COLUMNS), ""]
    return "\n".join(out)


def write_compare(comparison: dict[str, Any], out: Path) -> tuple[Path, Path]:
    """compare.json and compare.md in `out`."""
    return write_pair(comparison, render_compare(comparison), out, "compare")
