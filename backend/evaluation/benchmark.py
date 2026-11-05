"""`evaluate benchmark`: the record of B11 per extractor id, pooled from report.json files (F4).

The supervisor asks for a benchmarked extractor library (STATE.md §1, §3); B11 fixes the record: per
difficulty level precision, recall, F1; span accuracy; association accuracy; cost; re-execution
stability. The numbers come from `report.json` `extractors` (score.score_extractors: per extractor id,
evidence type and level, an item counting for every extractor in its `found_by`), `extractors.cost` and
`stability`; this module (our addition) pools them over the reports given:

- rows: counts summed per (evidence type, level) over the reports, P/R/F1 and the shares recomputed from
  the sums (micro, as score A), so a benchmark over one explicit, one paraphrased and one distributed
  corpus has one row per level. The recall denominator is what score_extractors recorded: the facts of
  the documents and types the extractor was called on (its extractor_call events), or every fact when a
  run has no events; `recall_scope` lists what each report used;
- cost: calls, model calls, tokens and seconds summed over the runs that record them, and per call
  (tokens and seconds divided by the calls of the runs that recorded them, so a run without a cache does
  not pull the average down);
- stability: a report's stability row applies to an extractor id when the row names the id, or the
  report's stability summary lists the id under `extractor_ids`, or the row names the id's bare name
  (the engine's reexec.json keys calls by extractor name, `name@version#hash` -> `name`) and exactly one
  extractor id of that report has that name; when several ids share the name the rows are ambiguous and
  are not counted (the record says so under `stability_ambiguous`, benchmark.md too). Calls, identical
  and item counts summed; null when no report has stability for it;
- pooled: `{"f1": Interval}`, the micro F1 over every level corpus with a cluster interval: the rows are
  the per-paper counts of `extractors.papers`, summed per parent study (`<seed>/<study id>`, a duplicate in
  its parent's cluster) so the same study at several levels is one resampling unit; null for reports
  without `papers`;
- corpora: `{corpus_id, run_id, levels}` of every report that mentions the extractor.

Written as `DIR/<extractor_id>/benchmark.json` and one `DIR/benchmark.md`.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .report import _level_key, dumps, table
from .score import prf, share
from .stats import cluster_bootstrap, interval_text, micro_f1

ROW_COLUMNS = ["evidence_type", "level", "items", "facts", "matched", "precision", "recall", "f1", "span_accuracy",
               "association_accuracy", "only", "only_matched"]
COST_COLUMNS = ["calls", "model_calls", "input_tokens", "output_tokens", "seconds"]
PER_CALL = ("model_calls", "input_tokens", "output_tokens", "seconds")
STABILITY_COLUMNS = ["calls", "identical", "identical_share", "items_original", "items_reproduced", "item_stability"]


def split_id(extractor_id: str) -> tuple[str, str | None]:
    """`name@version#hash` -> (name, version); an id without them gives (id, None)."""
    name, _, rest = extractor_id.partition("@")
    version = rest.partition("#")[0] if rest else None
    return name, version or None


def _stability_rows(report: dict[str, Any], extractor_id: str, ids: set[str]) -> tuple[list[dict[str, Any]], bool]:
    """(the report's stability rows for the id, whether rows keyed by its bare name were ambiguous)."""
    stability = report.get("stability") or {}
    name = split_id(extractor_id)[0]
    same_name = sum(split_id(e)[0] == name for e in ids)
    summary = stability.get("summary") if isinstance(stability.get("summary"), dict) else {}
    out, ambiguous = [], False
    for row in stability.get("rows") or []:
        key = row.get("extractor")
        entry = summary.get(key)
        listed = (entry.get("extractor_ids") or []) if isinstance(entry, dict) else []
        if key == extractor_id or extractor_id in listed:
            out.append(row)
        elif key == name:
            if same_name == 1:
                out.append(row)
            else:
                ambiguous = True
    return out, ambiguous


def benchmark(reports: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """extractor id -> benchmark record (module docstring), over the reports with `extractors`."""
    cells: dict[str, dict[tuple[str, str], Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    corpora: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cost: dict[str, Counter[str]] = defaultdict(Counter)
    covered: dict[str, Counter[str]] = defaultdict(Counter)   # calls of the runs that recorded a measure
    stable: dict[str, Counter[str]] = defaultdict(Counter)
    outcomes: dict[str, Counter[str]] = defaultdict(Counter)
    ambiguous: dict[str, list[str]] = defaultdict(list)
    scopes: dict[str, list[str]] = defaultdict(list)
    papers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for report in reports:
        extractors = report.get("extractors") or {}
        seen: set[str] = set()
        for row in extractors.get("rows") or []:
            e = row["extractor"]
            seen.add(e)
            c = cells[e][(row["evidence_type"], row["level"])]
            c.update(items=row.get("items") or 0, facts=row.get("facts") or 0, matched=row.get("matched") or 0,
                     span_hits=row.get("span_hits") or 0, only=row.get("only") or 0,
                     only_matched=row.get("only_matched") or 0, associated=row.get("associated") or 0)
        for row in extractors.get("papers") or []:
            papers[row["extractor"]].append(row)
        for row in extractors.get("cost") or []:
            e = row["extractor"]
            seen.add(e)
            cost[e].update(runs=1, calls=row.get("calls") or 0)
            for measure in PER_CALL:
                if row.get(measure) is not None:
                    cost[e][measure] += row[measure]
                    covered[e][measure] += row.get("calls") or 0
        for e in seen:
            corpora[e].append({"corpus_id": report.get("corpus_id"), "run_id": report.get("run_id"),
                               "levels": list(report.get("levels") or [])})
            scopes[e].append(extractors.get("recall_scope") or "all_facts")
            rows, unclear = _stability_rows(report, e, seen)
            if unclear:
                ambiguous[e].append(str(report.get("corpus_id")))
            for row in rows:
                stable[e].update(reports=1, calls=row.get("calls") or 0, identical=row.get("identical") or 0,
                                 items_original=row.get("items_original") or 0,
                                 items_reproduced=row.get("items_reproduced") or 0)
                outcomes[e].update(row.get("outcomes") or {})
    records = {}
    for e in sorted(set(cells) | set(cost)):
        rows = []
        for (kind, level), c in sorted(cells[e].items(), key=lambda kv: (kv[0][0], _level_key(kv[0][1]))):
            rows.append({"evidence_type": kind, "level": level, **prf(c["matched"], c["items"], c["facts"]),
                         "span_hits": c["span_hits"], "span_accuracy": share(c["span_hits"], c["matched"]),
                         "associated": c["associated"] if kind == "measurement" else None,
                         "association_accuracy": share(c["associated"], c["matched"]) if kind == "measurement" else None,
                         "only": c["only"], "only_matched": c["only_matched"]})
        name, version = split_id(e)
        records[e] = {"extractor_id": e, "name": name, "version": version, "corpora": corpora[e], "rows": rows,
                      "levels": sorted({r["level"] for r in rows if r["level"] != "all"}, key=_level_key),
                      "recall_scope": scopes[e], "cost": _cost(cost.get(e), covered.get(e)),
                      "stability": _stability(stable.get(e), outcomes.get(e)), "stability_ambiguous": ambiguous.get(e, []),
                      "pooled": {"f1": _pooled_f1(papers.get(e))}}
    return records


def _pooled_f1(rows: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not rows:
        return None
    return cluster_bootstrap(micro_f1, [(r["matched"], r["items"], r["facts"]) for r in rows],
                             [r["cluster"] for r in rows])


def _cost(c: Counter[str] | None, covered: Counter[str] | None) -> dict[str, Any] | None:
    if not c:
        return None
    covered = covered or Counter()
    totals = {m: (c[m] if covered[m] else None) for m in PER_CALL}
    per_call = {m: (c[m] / covered[m] if covered[m] else None) for m in PER_CALL}
    return {"runs": c["runs"], "calls": c["calls"], **totals, "per_call": per_call,
            "calls_recorded": {m: covered[m] for m in PER_CALL}}


def _stability(s: Counter[str] | None, outcomes: Counter[str] | None) -> dict[str, Any] | None:
    if not s:
        return None
    return {"reports": s["reports"], "calls": s["calls"], "identical": s["identical"],
            "identical_share": share(s["identical"], s["calls"]), "items_original": s["items_original"],
            "items_reproduced": s["items_reproduced"],
            "item_stability": share(s["items_reproduced"], s["items_original"]),
            "outcomes": dict(sorted((outcomes or Counter()).items()))}


def render(records: dict[str, dict[str, Any]]) -> str:
    """benchmark.md: one section per extractor id."""
    out = ["# Extractor benchmark", "", "Per extractor id (B11), pooled over the reports given; an item counts for "
           "every extractor in its `found_by`. Recall is against the facts of the documents and types the extractor "
           "was called on (its extractor_call events; `called`), or every fact of the type and level for a run "
           "without events (`all_facts`).", ""]
    for e, r in records.items():
        out += [f"## {e}", "", "Corpora: " + (", ".join(f"{c['corpus_id']} (run {c['run_id']}, recall scope {s})"
                                                         for c, s in zip(r["corpora"], r["recall_scope"])) or "-"), "",
                table(r["rows"], ROW_COLUMNS), ""]
        pooled = (r.get("pooled") or {}).get("f1")
        if pooled:
            clusters = f", {pooled['n_clusters']} clusters" if pooled.get("n_clusters") else ""
            out += [f"Pooled F1 (cluster bootstrap over parent studies): "
                    f"{interval_text(pooled.get('point'), pooled.get('low'), pooled.get('high'))}"
                    f" ({pooled.get('method') or '-'}{clusters}).", ""]
        if r["cost"]:
            c = r["cost"]
            out += [f"Cost over {c['runs']} run(s), {c['calls']} calls (per call in brackets; `-`: not recorded):",
                    "", table([{m: _with_per_call(c, m) for m in COST_COLUMNS}], COST_COLUMNS), ""]
        if r["stability"]:
            out += ["Re-execution stability:", "", table([r["stability"]], STABILITY_COLUMNS), ""]
        else:
            out += ["Re-execution stability: not measured.", ""]
        if r["stability_ambiguous"]:
            out += [f"Stability rows keyed by the bare name `{r['name']}` were left out for "
                    + ", ".join(r["stability_ambiguous"])
                    + ": several extractor ids there share that name, so the rows cannot be told apart.", ""]
    return "\n".join(line.rstrip() for line in out)


def _with_per_call(cost: dict[str, Any], measure: str) -> Any:
    total = cost.get(measure)
    if measure not in PER_CALL:
        return total
    per_call = cost["per_call"].get(measure)
    if total is None or per_call is None:
        return None
    return f"{total:.3f} [{per_call:.3f}]" if isinstance(total, float) else f"{total} [{per_call:.3f}]"


def write_benchmark(records: dict[str, dict[str, Any]], out: Path) -> list[Path]:
    """`out/<extractor_id>/benchmark.json` per extractor and `out/benchmark.md`; the paths written."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for e, record in records.items():
        folder = out / e
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "benchmark.json"
        path.write_text(dumps(record), encoding="utf-8", newline="\n")
        paths.append(path)
    md = out / "benchmark.md"
    md.write_text(render(records), encoding="utf-8", newline="\n")
    return paths + [md]
