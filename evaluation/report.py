"""report.json and report.md for one run, and the comparison over several corpora (per level).

report.json holds every number score.py computed, floats rounded to 4 places, keys sorted, so two
evaluations of the same inputs give the same bytes. report.md is the same numbers as tables
(tabulate, GitHub format) for reading and for the thesis appendix.
"""
from __future__ import annotations

import json
import re
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


def _cell(row: dict[str, Any], column: str) -> Any:
    """A null precision means nothing was given (score.prf, share): undefined, shown as n/a."""
    value = row.get(column)
    return "n/a" if value is None and column.endswith("precision") else _fmt(value)


def table(rows: list[dict[str, Any]], columns: list[str], headers: list[str] | None = None) -> str:
    return tabulate([[_cell(r, c) for c in columns] for r in rows], headers=headers or columns,
                    tablefmt="github", disable_numparse=True)


def _ci(row: dict[str, Any] | None) -> str:
    """`0.812 [0.74, 0.88]` from an interval row ({point, low, high}; stats.interval_row)."""
    if not row:
        return "-"
    return interval_text(row.get("point"), row.get("low"), row.get("high"))


def _method(row: dict[str, Any] | None) -> str | None:
    return (row or {}).get("method")


def render_intervals(intervals: dict[str, Any]) -> list[str]:
    """The `## Intervals` section (F4): extraction F1 per type, direction accuracy per system, paired difference;
    for another kind, its C metrics per system (score.kind_intervals)."""
    out = ["## Intervals", "", "95 % bootstrap intervals over papers (2,000 resamples, seed 0; evaluation/stats.py), "
           "`point [low, high]`; `method` is BCa, or percentile where BCa is undefined; `[n/a]`: a degenerate "
           "sample (fewer than two papers, or no spread), the point value only.", ""]
    if intervals.get("extraction"):
        rows = [{"evidence_type": r["evidence_type"], "f1": _ci(r), "method": _method(r)} for r in intervals["extraction"]]
        out += ["Extraction F1 (all levels):", "", table(rows, ["evidence_type", "f1", "method"]), ""]
    kinds = [r for r in intervals.get("synthesis") or [] if r.get("metric")]   # a kind other than effect
    if kinds:
        rows = [{"system": r["system"], "metric": r["metric"], "interval": _ci(r), "method": _method(r),
                 "n": r.get("n_rows")} for r in kinds]
        out += ["C per system (`n`: the decidable papers resampled; inventory: the names, truth's and the "
                "answer's):", "", table(rows, ["system", "metric", "interval", "method", "n"]), ""]
    elif intervals.get("synthesis"):
        paired = {r["system"]: r for r in intervals.get("paired") or []}
        rows = [{"system": r["system"], "direction_accuracy": _ci(r), "method": _method(r),
                 "engine_minus_system": _ci(paired.get(r["system"])) if r["system"] != ENGINE else "-",
                 "paired_method": _method(paired.get(r["system"])) if r["system"] != ENGINE else None}
                for r in intervals["synthesis"]]
        for row in rows:
            p = paired.get(row["system"]) or {}
            row["paired_n"] = p.get("n_rows")
        out += ["Direction accuracy, and the paired difference engine minus system (per study; paired_n: papers in "
                "both systems):", "",
                table(rows, ["system", "direction_accuracy", "method", "engine_minus_system", "paired_method",
                             "paired_n"]), ""]
        out += [f"- paired {n}: excluded (not in both systems) {', '.join(p['excluded_ids'])}"
                for n, p in paired.items() if p.get("excluded_ids")]
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
        if report["extraction"].get("scored_types"):
            out[-1:-1] = ["", "Evidence types scored (the protocol's own; the `all` rows pool these only): "
                          + ", ".join(report["extraction"]["scored_types"]) + "."]
    kind = report.get("kind", "effect")
    if kind != "effect":
        out[3:3] = [f"Question id: {report.get('question_id')} (kind {kind})"]
        out += render_integration_kind(kind, report.get("integration"))
        out += render_synthesis_kind(kind, report.get("synthesis") or [])
    elif report.get("integration"):
        rows = sorted(report["integration"]["rows"], key=lambda r: _level_key(r["level"]))
        out += ["## B. Integration", "", table(rows, ["level", "matched_measurements", "association_accuracy",
                                                     "condition_role_accuracy", "metric_accuracy", "condition_exact",
                                                     "metric_exact", "studies", "true_pair"]), ""]
    if report.get("synthesis") and kind == "effect":
        out += ["## C. Synthesis", ""]
        summary = []
        for system in report["synthesis"]:
            overall = next((r for r in system["rows"] if r["level"] == "all"), {})
            summary.append({"system": system["system"], "label": system["label"], "expected": system["expected_label"],
                            "label_correct": system["label_correct"], "studies": overall.get("studies"),
                            "determined": overall.get("determined"),
                            "direction_accuracy": overall.get("direction_accuracy"),
                            "direction_accuracy_all_papers": overall.get("direction_accuracy_all_papers"),
                            "accuracy_answered": overall.get("accuracy_answered"),
                            "completeness": overall.get("completeness"),
                            "traceability": overall.get("traceability"), "overlap": overall.get("overlap")})
        out += [table(summary, ["system", "label", "expected", "label_correct", "studies", "determined",
                                "direction_accuracy", "completeness", "accuracy_answered",
                                "direction_accuracy_all_papers", "traceability", "overlap"]), "",
                *[f"- {s['system']}: {e}" for s in report["synthesis"] for e in s.get("errors") or []],
                *([""] if any(s.get("errors") for s in report["synthesis"]) else []),
                "direction_accuracy, completeness and accuracy_answered are over the determined studies only (the "
                "studies truth can decide): a determined study the system leaves out or calls undetermined is wrong, "
                "and a study whose expected direction is undetermined (missing information, an irrelevant paper) is "
                "not counted, so an empty answer scores 0. completeness (the supervisor's word: the share of the "
                "`determined` studies the system gives a direction for) and accuracy_answered (accuracy over those) "
                "split it: direction_accuracy = completeness x accuracy_answered. direction_accuracy_all_papers is "
                "the old number over all scored studies, where silence on an undetermined study counts as right. "
                "traceability is the share of a baseline's cited passages that "
                "overlap a value, metric-label or claim placement of the paper they cite, dropped citations counted "
                "as untraced (span overlap only: not \"same study or condition\", not entailment; the passage need "
                "not support the claim); overlap is the lenient share, over a placement of any role, a condition "
                "label included (none for the engine: its spans are scored in A).", ""]
        levels = [{"system": s["system"], **r} for s in report["synthesis"] for r in s["rows"] if r["level"] != "all"]
        if levels:
            levels.sort(key=lambda r: (_level_key(r["level"]), r["system"]))
            out += ["Per level:", "", table(levels, ["level", "system", "studies", "determined", "direction_accuracy",
                                                     "completeness", "accuracy_answered",
                                                     "direction_accuracy_all_papers", "traceability", "overlap"]), ""]
        flagged = [s for s in report["synthesis"] if s.get("flags")]
        if flagged:
            rows = [{"system": s["system"], **r} for s in flagged for r in s["flags"]["rows"]]
            verdicts = [{"system": s["system"], "counts_correct": s["flags"]["counts_correct"],
                         "duplicates_correct": s["flags"]["duplicates_correct"]} for s in flagged]
            out += ["Flags (F1; a system without `flags` is not listed):", "",
                    table(rows, ["system", "flag", "tp", "fp", "fn", "precision", "recall"]), "",
                    table(verdicts, ["system", "counts_correct", "duplicates_correct"]), ""]
    costs = [{"system": s["system"], **s["cost"]} for s in report.get("synthesis") or [] if s.get("cost")]
    if costs:
        out += ["## Cost per system", "", table(costs, ["system", "model_calls", "input_tokens", "output_tokens",
                                                        "tokens"]), "",
                "Model calls and tokens each system recorded (D41): the engine's run.json `cost`, a baseline's "
                "answering and mapping calls, the agent baseline's agent (its tokens not split into in and out). "
                "The engine's counts include calls replayed from its record cache (the system's cost, not this "
                "rerun's spend: `made_model_calls` under Cost is that). `-`: not recorded.", ""]
    if report.get("attribution"):
        att = report["attribution"]
        rows = sorted(({"system": s["system"], **r} for s in att["systems"] for r in s["rows"]),
                      key=lambda r: (r["system"], _level_key(r["level"])))
        out += ["## Attribution", "", f"Wrong studies against the oracle `{att['oracle']}`: upstream when the oracle "
                "is right (extraction or passage search), downstream when it is wrong too (synthesis or "
                "reasoning).", "",
                table(rows, ["system", "level", "studies", "system_correct", "oracle_correct", "upstream",
                             "downstream"]), ""]
        if att.get("not_attributed"):
            out += ["Not attributed (not this oracle's counterpart): " + ", ".join(att["not_attributed"]), ""]
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


KIND_B: dict[str, tuple[str, list[str], str]] = {
    "inventory": ("Synonym merging", ["entries", "keyed_entries", "keys", "split", "merged", "clean_share"],
                  "Each answer entry holds the truth keys of the facts its items matched in A; `split`: keys spread "
                  "over more than one entry, `merged`: entries holding more than one key, `clean_share`: entries "
                  "holding one key no other entry holds, of the entries with a key."),
    "best": ("Kind assignment", ["conditions", "kind_correct", "kind_accuracy"],
             "Matched conditions whose label vocab gives a method kind, and the share the engine gave that kind."),
    "consistency": ("Claim to result", ["claims", "claim_correct", "claim_accuracy"],
                    "Author-claim items whose claim span overlaps a true claim, and the share with its direction."),
    "chaining": ("Comparisons", ["comparisons", "expected_comparisons", "matched_comparisons", "comparison_precision",
                                 "comparison_recall"],
                 "The run's comparisons (comparisons.json) against the truth network's, as (document, the two things "
                 "by name key, metric, context); duplicate studies left out."),
    "limitations": ("Thing links", ["items", "linked", "link_share"],
                    "Limitation items and the share that link a compared thing (a wrong link shows in A)."),
    "builds_on": ("Dependency links", ["links", "expected_links", "matched_links", "link_precision", "link_recall"],
                  "The answer's links (from, to, reuses) against the planted dependencies.")}
KIND_C: dict[str, tuple[str, list[str], str]] = {
    "inventory": ("Inventory", ["system", "target", "entries", "expected_entries", "matched", "precision", "recall",
                                "f1", "paper_precision", "paper_recall", "paper_f1"],
                  "Sets of keys (`canon.key` of a name or alias; a name vocab does not know matches a truth entry vocab "
                  "does not know by its folded name, else it is a false positive), and of (key, paper) pairs."),
    "best": ("Best", ["system", "winner", "expected_winner", "winner_correct", "studies_scored",
                      "per_study_accuracy", "completeness", "studies_all_papers", "per_study_accuracy_all_papers"],
             "`winner_correct`: the winner (or the tie) is truth's; per-study accuracy of the paper's winner and tie "
             "over the studies truth can decide (a winner or a tie): a decidable paper left out or given neither is "
             "wrong, a paper with no comparison is not counted; completeness is the share of them given a winner or "
             "tie. `*_all_papers`: the old number over truth's studies not screened out and not a duplicate, where "
             "silence on a no-comparison paper is right (the engine does not leave duplicates out, which shows in its "
             "wins)."),
    "consistency": ("Consistency", ["system", "metric", "studies_scored", "per_study_accuracy", "completeness",
                                    "studies_all_papers", "per_study_accuracy_all_papers", "agreeing_precision",
                                    "agreeing_recall", "disagreeing_precision", "disagreeing_recall"],
                    "Over the studies truth can decide (its question metric is the claim metric and `agrees` is not "
                    "null: duplicates and papers with missing data or no claim drop out): a decidable paper left out "
                    "or called undetermined is wrong; completeness is the share given true or false; the agreeing and "
                    "disagreeing sets are over the same studies. `*_all_papers`: the old number over every study "
                    "truth lists, `agrees` null right when truth's is null too."),
    "chaining": ("Chaining", ["system", "source", "target", "verdict", "expected_verdict", "reason", "expected_reason",
                              "verdict_correct", "inferred_correct", "path_correct", "refusal_correct", "headline"],
                 "`path_correct`: the `via` things (by name key) and the studies are truth's; `refusal_correct`: truth "
                 "refuses and the answer refuses for the same reason (null when truth concludes); headline: the mean "
                 "of verdict_correct and path_correct."),
    "limitations": ("Limitations", ["system", "thing", "things_scored", "jaccard_mean", "exact_match",
                                    "unlinked_exact", "headline"],
                    "Per compared thing (by name key), the category sets of truth and the answer: Jaccard and exact "
                    "match; headline: the mean Jaccard."),
    "builds_on": ("Builds on", ["system", "thing", "things_scored", "follower_f1_mean", "ranking_tau", "top1_correct",
                                "headline"],
                  "Per compared thing (by name key), F1 of the follower sets; Kendall tau of the influence over "
                  "truth's things; top1: the answer's first thing is one of truth's most influential; headline: the "
                  "mean F1.")}


def render_integration_kind(kind: str, integration: dict[str, Any] | None) -> list[str]:
    """The `## B` section of a question kind other than effect (score.integration_kind)."""
    if not integration:
        return []
    title, columns, text = KIND_B[kind]
    out = [f"## B. {title}", "", table([integration], columns), "", text, ""]
    if integration.get("rows"):
        rows = sorted(integration["rows"], key=lambda r: _level_key(r["level"]))
        out += ["Measurement linkage (no pair check: a consistency answer names no measurement pair):", "",
                table(rows, ["level", "matched_measurements", "association_accuracy", "condition_role_accuracy",
                             "metric_accuracy", "condition_exact", "metric_exact"]), ""]
    return out


def render_synthesis_kind(kind: str, systems: list[dict[str, Any]]) -> list[str]:
    """The `## C` section of a question kind other than effect (score.score_kind), one row per system."""
    if not systems:
        return []
    title, columns, text = KIND_C[kind]
    out = [f"## C. {title}", "", table(systems, columns), "", text, ""]
    if kind == "inventory":
        out += [f"- {s['system']}: false positives {', '.join(s['false_positives']) or 'none'}; missed "
                f"{', '.join(s['missed']) or 'none'}" for s in systems] + [""]
    return out


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


DIAGNOSTICS = ("oracle-synthesis", "rag-oracle-passages")   # E1: read ground_truth.json, never a baseline
RENDERERS = re.compile(r"^(?P<prefix>.+?)-(?P<renderer>tpl|llm)-(?P<rest>.+)$")


def compare(reports: list[dict[str, Any]], base: Path | None = None) -> dict[str, Any]:
    """One row per corpus and system: the headline numbers of A, B and C, ordered by difficulty level; the
    selection of each corpus (corpus.json, found next to the report or under `base`), and template vs LLM on the
    study ids both corpora kept; `notes` says what could not be shown."""
    rows = []
    notes: list[str] = []
    other = [r for r in reports if r.get("kind", "effect") != "effect"]
    if other:   # their C has no per-level direction rows; they are read in their own report.md
        notes.append(f"{len(other)} reports of other question kinds ({', '.join(sorted({r['kind'] for r in other}))}) "
                     "left out: the comparison is over effect questions")
        reports = [r for r in reports if r.get("kind", "effect") == "effect"]
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
                         "diagnostic": system["system"] in DIAGNOSTICS,
                         "strategy": funnel.get("strategy") if engine else None,
                         **_protocol_columns(report, engine),
                         "extraction_f1": a.get("f1") if engine else None,
                         "span_accuracy": a.get("span_accuracy") if engine else None,
                         "association_accuracy": b.get("association_accuracy") if engine else None,
                         "true_pair": b.get("true_pair") if engine else None,
                         "direction_accuracy": c.get("direction_accuracy"),
                         "accuracy_answered": c.get("accuracy_answered"), "completeness": c.get("completeness"),
                         "traceability": None if engine else c.get("traceability"),  # the engine's spans: A
                         "overlap": None if engine else c.get("overlap"),
                         "label_correct": system["label_correct"],
                         # the funnel (Part D): an `all` and a `gaps` run of one protocol stand in two rows
                         "calls_per_document": per_doc.get("calls") if engine else None,
                         "tokens_per_document": per_doc.get("tokens") if engine else None,
                         "screen_precision": screen.get("precision") if engine else None,
                         "screen_recall": screen.get("recall") if engine else None})
    rows.sort(key=_row_key)
    corpora_of = _corpora(reports, base, notes)
    selection, excluded = selection_rows(reports, corpora_of)
    matched, matched_extraction = matched_pairs(reports, corpora_of, notes)
    return {"rows": rows, "intervals": compare_intervals(reports), "selection": selection,
            "selection_excluded": excluded, "matched": matched, "matched_extraction": matched_extraction,
            "notes": notes}


def _protocol_columns(report: dict[str, Any], engine: bool) -> dict[str, Any]:
    """The engine row's screen `lexical_miss` and protocol sha256 (first 12 hex digits): the reject and escalate
    arms of one corpus share run id and strategy and differ only here (report.json `protocol`)."""
    protocol = (report.get("protocol") or {}) if engine else {}
    sha = protocol.get("sha256")
    return {"lexical_miss": protocol.get("lexical_miss"), "protocol": sha[:12] if isinstance(sha, str) else None}


def _row_key(r: dict[str, Any]) -> tuple[Any, ...]:
    return (_level_key(r["level"]), r["corpus_id"], r["system"], r.get("strategy") or "", r.get("lexical_miss") or "",
            r.get("protocol") or "", r.get("run_id") or "")


def _corpus_name(report: dict[str, Any]) -> str:
    """The corpus directory's name: `corpus_name`, else the last part of `corpus_dir`, else the corpus_id."""
    return report.get("corpus_name") or (Path(report["corpus_dir"]).name if report.get("corpus_dir")
                                         else report["corpus_id"])


def _corpora(reports: list[dict[str, Any]], base: Path | None, notes: list[str]) -> dict[int, dict[str, Any] | None]:
    """report index -> its corpus.json (parsed), found next to the report (`corpus_dir` is relative to the
    report file, `_report_dir` set by the CLI) or under `base`/<corpus name>; None where it is not found, which
    is noted. A corpus.json that is not valid JSON raises, naming the path."""
    out: dict[int, dict[str, Any] | None] = {}
    missing = []
    for i, report in enumerate(reports):
        candidates = []
        if report.get("corpus_dir") and report.get("_report_dir"):
            candidates.append(Path(report["_report_dir"]) / report["corpus_dir"])
        if base is not None:
            candidates.append(Path(base) / _corpus_name(report))
        path = next((c / "corpus.json" for c in candidates if (c / "corpus.json").is_file()), None)
        if path is None:
            out[i] = None
            missing.append(_corpus_name(report))
            continue
        try:
            out[i] = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ValueError(f"{path}: not valid JSON ({exc})") from None
    if missing:
        notes.append(f"{len(set(missing))} corpora not found ({', '.join(sorted(set(missing)))}): Selection and "
                     "Matched are incomplete; give --corpora DIR (the directory holding the corpus directories), or "
                     "re-score so the report records where the corpus is")
    return out


def selection_rows(reports: list[dict[str, Any]], corpora: dict[int, dict[str, Any] | None]
                   ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One row per corpus and fidelity level from corpus.json `selection` (C3), and per corpus the excluded
    studies with their levels; a corpus without a selection (built before C3) is left out."""
    rows, excluded, seen = [], [], set()
    for i, report in enumerate(reports):
        sel = (corpora.get(i) or {}).get("selection")
        if not sel or report["corpus_id"] in seen:
            continue
        seen.add(report["corpus_id"])
        for level, row in sorted(sel.get("per_level", {}).items(), key=lambda kv: _level_key(kv[0])):
            failed = ", ".join(f"{k}: {v}" for k, v in sorted(row.get("failed_checks", {}).items()))
            rows.append({"corpus_id": report["corpus_id"], "level": level, "requested": sel.get("requested_studies"),
                         "retained": sel.get("retained_studies"), "records": sel.get("records"),
                         "passed": row.get("passed"), "failed_checks": failed or "none",
                         "mean_attempts": row.get("mean_attempts")})
        excluded.append({"corpus_id": report["corpus_id"], "excluded": sel.get("excluded", {})})
    return rows, excluded


def _disagreement(tpl: dict[str, Any], llm: dict[str, Any]) -> str | None:
    """Why two corpora are not the same study set (seed, build settings but the name), else None."""
    if tpl.get("seed") != llm.get("seed"):
        return f"seeds differ ({tpl.get('seed')} and {llm.get('seed')})"
    rest = [{k: v for k, v in (c.get("settings") or {}).items() if k != "name"} for c in (tpl, llm)]
    if rest[0] != rest[1]:
        return "build settings differ"
    return None


def _share(num: int, den: int) -> float | None:
    return num / den if den else None


def _accuracies(studies: list[dict[str, Any]]) -> dict[str, float | None]:
    """direction_accuracy (over the determined studies), completeness and accuracy_answered (score.score_synthesis)
    over per-study rows."""
    determined = [s for s in studies if s.get("determined")]
    answered = [s for s in determined if s.get("given") != "undetermined"]
    return {"direction_accuracy": _share(sum(bool(s["correct"]) for s in determined), len(determined)),
            "completeness": _share(len(answered), len(determined)),
            "accuracy_answered": _share(sum(bool(s["correct"]) for s in answered), len(answered))}


def matched_pairs(reports: list[dict[str, Any]], corpora: dict[int, dict[str, Any] | None],
                  notes: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Template vs LLM corpora (`<prefix>-tpl-<rest>` and `<prefix>-llm-<rest>`, the same seed and level):
    per system the synthesis metrics, and per extractor the extraction precision and recall, recomputed over
    the study ids both corpora kept; the ids in only one are listed. A pair is matched only when both corpus.json
    are found and agree on the seed and the build settings (all but the name); a key with two different
    reports on one side is ambiguous, and both it and a pair that does not agree are noted, not matched."""
    by_key: dict[tuple[str, str, str, str | None], dict[str, dict[str, Any]]] = {}
    ambiguous: set[tuple[str, str, str, str | None]] = set()
    for i, report in enumerate(reports):
        m = RENDERERS.match(_corpus_name(report))
        if m:
            strategy = (report.get("funnel") or {}).get("strategy")
            for system in report.get("synthesis") or []:
                key = (m["prefix"], m["rest"], system["system"], strategy if system["system"] == ENGINE else None)
                slot = by_key.setdefault(key, {})
                if m["renderer"] in slot and slot[m["renderer"]]["index"] != i:
                    ambiguous.add(key)
                slot[m["renderer"]] = {"report": report, "system": system, "index": i}
    ambiguous = {k for k in ambiguous if set(by_key[k]) == {"tpl", "llm"}}   # only a pair that was to be matched
    for prefix, rest, name, strategy in sorted(ambiguous, key=str):
        notes.append(f"ambiguous: {prefix}-*-{rest} / {name}: two reports for one corpus name on one side; not matched")
    matched, extraction = [], []
    for (prefix, rest, name, strategy), both in sorted(
            by_key.items(), key=lambda kv: (kv[0][0], _level_key(kv[0][1]), kv[0][2], kv[0][3] or "")):
        if set(both) != {"tpl", "llm"} or (prefix, rest, name, strategy) in ambiguous:
            continue
        data = [corpora.get(both[r]["index"]) for r in ("tpl", "llm")]
        why = _disagreement(*data) if all(d is not None for d in data) else "corpus.json not found"
        if why:
            notes.append(f"not matched: {prefix}-(tpl|llm)-{rest} / {name}: {why}")
            continue
        studies = {r: {s["paper"]: s for s in both[r]["system"]["studies"]} for r in both}
        common = sorted(studies["tpl"].keys() & studies["llm"].keys())
        row = {"pair": f"{prefix}/{rest}", "level": corpus_level(both["tpl"]["report"]), "system": name,
               "diagnostic": name in DIAGNOSTICS, "strategy": strategy, "n_common": len(common), "common": common,
               "tpl_only": sorted(studies["tpl"].keys() - set(common)),
               "llm_only": sorted(studies["llm"].keys() - set(common))}
        for r in ("tpl", "llm"):
            for k, v in _accuracies([studies[r][i] for i in common]).items():
                row[f"{r}_{k}"] = v
        matched.append(row)
        if name != ENGINE:
            continue
        papers: dict[str, dict[str, dict[str, Any]]] = {r: {} for r in both}
        for r in both:
            for p in (both[r]["report"].get("extractors") or {}).get("papers") or []:
                papers[r].setdefault(p["extractor"], {})[p["paper"]] = p
        for extractor in sorted(papers["tpl"].keys() & papers["llm"].keys()):
            ids = sorted(papers["tpl"][extractor].keys() & papers["llm"][extractor].keys() & set(common))
            out: dict[str, Any] = {"pair": row["pair"], "level": row["level"], "strategy": strategy,
                                   "extractor": extractor, "n_common": len(ids)}
            for r in ("tpl", "llm"):
                cells = [papers[r][extractor][i] for i in ids]
                items, hit, facts = (sum(c[k] for c in cells) for k in ("items", "matched", "facts"))
                out |= {f"{r}_precision": _share(hit, items), f"{r}_recall": _share(hit, facts)}
            extraction.append(out)
    return matched, extraction


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
        strategy = (report.get("funnel") or {}).get("strategy")
        for system in intervals.get("synthesis") or []:
            name = system["system"]
            rows.append({"level": level, "corpus_id": report["corpus_id"], "system": name,
                         "run_id": report.get("run_id") if name == ENGINE else None,
                         "diagnostic": name in DIAGNOSTICS,
                         "strategy": strategy if name == ENGINE else None,   # Part D: all vs gaps rows
                         **_protocol_columns(report, name == ENGINE),
                         "extraction_f1": _strip(f1) if name == ENGINE else None,
                         "direction_accuracy": _strip(system),
                         "engine_minus_system": _strip(paired.get(name)) if name != ENGINE else None})
    rows.sort(key=_row_key)
    return rows


def _strip(row: dict[str, Any] | None) -> dict[str, Any] | None:
    return {k: row.get(k) for k in ("point", "low", "high", "method", "n_rows", "unit", "n_clusters")} if row else None


def _n(row: dict[str, Any] | None) -> str:
    """An interval's sample size: `n_rows`, with `(k clusters)` where it was resampled by cluster."""
    if not row or row.get("n_rows") is None:
        return "-"
    return f"{row['n_rows']} ({row['n_clusters']} clusters)" if row.get("n_clusters") is not None else str(row["n_rows"])


COMPARE_COLUMNS = ["level", "corpus_id", "system", "strategy", "lexical_miss", "protocol", "extraction_f1", "span_accuracy", "association_accuracy",
                   "true_pair", "direction_accuracy", "completeness", "accuracy_answered", "traceability",
                   "overlap", "label_correct", "calls_per_document", "tokens_per_document", "screen_precision", "screen_recall"]
COMPARE_INTERVAL_COLUMNS = ["level", "corpus_id", "system", "strategy", "lexical_miss", "protocol", "extraction_f1",
                            "extraction_n", "direction_accuracy", "direction_n", "engine_minus_system", "paired_n"]


SELECTION_COLUMNS = ["corpus_id", "level", "requested", "retained", "records", "passed", "failed_checks",
                     "mean_attempts"]
MATCHED_COLUMNS = ["pair", "level", "system", "strategy", "n_common", "tpl_direction_accuracy", "llm_direction_accuracy",
                   "tpl_completeness", "llm_completeness", "tpl_accuracy_answered", "llm_accuracy_answered"]
MATCHED_EXTRACTION_COLUMNS = ["pair", "extractor", "strategy", "n_common", "tpl_precision", "llm_precision",
                              "tpl_recall", "llm_recall"]


def _marked(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rows with ` (diagnostic)` after the system of an oracle (E1), so it is not read as a baseline."""
    return [{**r, "system": f"{r['system']} (diagnostic)"} if r.get("diagnostic") else r for r in rows]


def _excluded_text(excluded: dict[str, list[str]]) -> str:
    return ", ".join(f"{k} ({', '.join(v)})" for k, v in sorted(excluded.items())) or "none"


def render_compare(comparison: dict[str, Any]) -> str:
    out = ["# Comparison over corpora", "", table(_marked(comparison["rows"]), COMPARE_COLUMNS), ""]
    if any(r.get("diagnostic") for r in comparison["rows"]):
        out += ["`(diagnostic)`: oracle-synthesis and rag-oracle-passages read the ground truth; they bound what "
                "extraction or passage search could give and are not baselines.", ""]
    if comparison.get("notes"):
        out += ["**Not shown:**", "", *[f"- {n}" for n in comparison["notes"]], ""]
    if comparison.get("selection"):
        rows = comparison["selection"]
        out += ["## Selection", "", "Studies requested and retained after the fidelity gate (corpus.json `selection`; "
                "a corpus built before it is not listed); per level the papers passed, the checks that failed the "
                "final attempt of the failed ones and the mean attempts.", "", table(rows, SELECTION_COLUMNS), ""]
        out += [f"- {e['corpus_id']}: excluded {_excluded_text(e['excluded'])}"
                for e in comparison.get("selection_excluded") or []]
        out += [""]
    if comparison.get("matched"):
        rows = _marked(comparison["matched"])
        out += ["## Matched", "", "Template vs LLM corpora of one seed and level, recomputed on the study ids "
                "both kept (the metrics are those of the per-corpus reports, over the common studies only).", "",
                table(rows, MATCHED_COLUMNS), ""]
        out += [f"- {r['pair']} / {r['system']}: only in template {', '.join(r['tpl_only']) or 'none'}; only in LLM "
                f"{', '.join(r['llm_only']) or 'none'}" for r in rows]
        out += [""]
        if comparison.get("matched_extraction"):
            out += ["Extraction on the common studies, per extractor (precision and recall as in A):", "",
                    table(comparison["matched_extraction"], MATCHED_EXTRACTION_COLUMNS), ""]
    if comparison.get("intervals"):
        rows = [{**r, **{k: _ci(r.get(k)) for k in ("extraction_f1", "direction_accuracy", "engine_minus_system")},
                 "extraction_n": _n(r.get("extraction_f1")) if r.get("extraction_f1") else "-",
                 "direction_n": _n(r.get("direction_accuracy")),
                 "paired_n": _n(r.get("engine_minus_system")) if r.get("engine_minus_system") else "-"}
                for r in _marked(comparison["intervals"])]
        out += ["## Intervals", "", "95 % bootstrap, `point [low, high]` (BCa, or percentile where BCa is "
                "undefined: the method is in each report's Intervals section); `[n/a]`: degenerate sample. "
                "`extraction_n` papers and `direction_n` studies resampled (`k clusters` where whole parent studies "
                "were resampled), `paired_n` the studies both systems scored.",
                "", table(rows, COMPARE_INTERVAL_COLUMNS), ""]
    return "\n".join(out)


def write_compare(comparison: dict[str, Any], out: Path) -> tuple[Path, Path]:
    """compare.json and compare.md in `out`."""
    return write_pair(comparison, render_compare(comparison), out, "compare")
