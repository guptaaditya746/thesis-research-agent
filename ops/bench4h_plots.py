"""Plots and a metrics table for the bench4h runs (4 domains x 6 systems). Code only, no LLM calls.

    python ops/bench4h_plots.py            # needs matplotlib; reads runs/evqa/bench4h-*, writes runs/evqa/bench4h-compare/plots/

Layers (the scorer leaves L1/L2 n/a for paperfactory domains: their gold has no L0 spans, so these are simpler stand-ins):
  L1 paper recall   answerable questions: gold papers (gold answer table/entities papers that are in the corpus) that the
                    system's find.jsonl passed on (screen != "no", at least one passage) / gold papers. All systems.
                    Long-context reads every paper, so its recall is 1 by construction. A system that wrote no
                    find.jsonl at all (PaperQA2 agent) gets None (unknown), not 0.
  L1 precision      found gold papers / found papers (same questions).
  L2 value recall   ours only: gold table rows with a value for which ours extracted a non-dropped row from one of the
                    row's papers with the same number (half a unit of the gold's last printed decimal). The quote
                    position and the names are not checked (no L0 spans), so this is an upper bound of the scorer's L2.
                    List and conflict-entity questions have no gold values and are left out.
  L3 answer score   eval.json totals.l3_text (scorer, LLM reader + judge), with its 95% bootstrap interval.
"""
from __future__ import annotations

import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs/evqa"
OUT = RUNS / "bench4h-compare/plots"
DOMAINS = ["law", "llm", "materials", "medicine"]
SYSTEMS = ["ours", "pqa-rag", "pqa-agent", "pqa-agent-fixed", "long-context", "closed-book"]
LABEL = {"ours": "ours", "pqa-rag": "PaperQA2 rag", "pqa-agent": "PaperQA2 agent",
         "pqa-agent-fixed": "PaperQA2 agent-fixed", "long-context": "long-context", "closed-book": "closed-book"}
TYPES = ["lookup", "effect", "best", "trend", "list", "conflict", "absent", "near_miss", "out_of_scope"]
# reference categorical palette (dataviz skill), validated light: all checks pass, contrast WARN -> values printed on bars
COLOR = {"ours": "#2a78d6", "pqa-rag": "#eb6834", "pqa-agent": "#1baf7a", "pqa-agent-fixed": "#eda100",
         "long-context": "#6250d6", "closed-book": "#a3a29c"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def run_dir(domain: str, system: str) -> Path:
    hits = [p for p in RUNS.glob(f"bench4h-{domain}-{system}-*") if p.is_dir()
            and p.name.removeprefix(f"bench4h-{domain}-{system}-").isalnum()]   # pqa-agent must not take pqa-agent-fixed
    assert len(hits) == 1, (domain, system, hits)
    return hits[0]


def gold(domain: str) -> dict[str, dict]:
    d = ROOT / f"data/seed/bench_{domain}/gold"
    return {p.stem: json.loads(p.read_text("utf-8")) for p in sorted(d.glob("*.json"))}


def corpus(domain: str) -> set[str]:
    return {p.name for p in (ROOT / f"data/seed/bench_{domain}/papers").iterdir()}


def jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]


def gold_papers(q: dict, papers: set[str]) -> set[str]:
    a = q.get("answer") or {}
    ps = {p for r in a.get("table", []) for p in r.get("papers") or [r.get("paper")]}
    ps |= {p for e in a.get("entities", []) for p in e.get("papers", [])}
    return ps & papers


def same(gold_value: str, got: object) -> bool:
    try:
        g, v = Decimal(str(gold_value)), Decimal(str(got))
    except (InvalidOperation, ValueError):
        return False
    half = Decimal(1).scaleb(g.as_tuple().exponent) / 2
    return abs(g - v) <= half


def layers(domain: str, system: str, golds: dict[str, dict], papers: set[str]) -> dict:
    rd = run_dir(domain, system)
    ev = json.loads((rd / "eval.json").read_text("utf-8"))
    rec, prec, l2hit, l2n = [], [], 0, 0
    logged = any((rd / qid / "find.jsonl").is_file() and (rd / qid / "find.jsonl").stat().st_size for qid in golds)
    for qid, q in golds.items():
        if not q.get("answerable"):
            continue
        gp = gold_papers(q, papers)
        found = {h["paper"] for h in jsonl(rd / qid / "find.jsonl") if h.get("screen") != "no" and h.get("passages")}
        if gp and logged:   # PaperQA2 agent writes no find.jsonl: its L1 is unknown, not 0
            rec.append(len(gp & found) / len(gp))
            if found:
                prec.append(len(gp & found) / len(found))
        if system == "ours":
            rows = [r for r in jsonl(rd / qid / "rows.jsonl") if not r.get("dropped")]
            for g in (q.get("answer") or {}).get("table", []):
                if g.get("value") in (None, ""):
                    continue
                l2n += 1
                gps = set(g.get("papers") or [g.get("paper")])
                l2hit += any(r.get("paper") in gps and same(g["value"], (r.get("std") or {}).get("value"))
                             for r in rows)
    t = ev["totals"]
    lo, hi = ev.get("intervals", {}).get("l3_text", [None, None])
    nr = t.get("text_not_reported", {})
    return {"domain": domain, "system": system,
            "l1_paper_recall": sum(rec) / len(rec) if rec else None,
            "l1_paper_precision": sum(prec) / len(prec) if prec else None,
            "l2_value_recall": l2hit / l2n if l2n else None, "l2_values": l2n or None,
            "l3_text": t["l3_text"], "l3_lo": lo, "l3_hi": hi, "l3_exact": t.get("l3_text_exact"),
            "nr_accuracy": nr.get("accuracy"), "nr_hallucination": nr.get("hallucination"),
            **{f"type_{k}": (t.get("per_type", {}).get(k) or {}).get("l3_text") for k in TYPES}}


def style(ax: plt.Axes, ylabel: str | None = None) -> None:
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(INK2)
    ax.tick_params(colors=INK2, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2)


def save(fig: plt.Figure, name: str) -> None:
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=200, facecolor=SURFACE)
    plt.close(fig)


def grouped(rows: list[dict], key: str, systems: list[str], title: str, name: str, ci: bool = False,
            note: str = "") -> None:
    fig, ax = plt.subplots(figsize=(10, 4.2))
    w = 0.8 / len(systems)
    for i, s in enumerate(systems):
        xs, ys, err = [], [], [[], []]
        for j, d in enumerate(DOMAINS):
            r = next(r for r in rows if r["domain"] == d and r["system"] == s)
            if r[key] is None:
                continue
            x = j + (i - (len(systems) - 1) / 2) * w
            xs.append(x)
            ys.append(r[key])
            if ci:
                err[0].append(r[key] - r["l3_lo"])
                err[1].append(r["l3_hi"] - r[key])
            ax.text(x, r[key] + 0.015, f"{r[key]:.2f}", ha="center", va="bottom", fontsize=7, color=INK2)
        if not xs:   # no value in any domain (e.g. L1 of PaperQA2 agent): no bar and no legend entry
            continue
        ax.bar(xs, ys, w * 0.9, color=COLOR[s], label=LABEL[s], edgecolor=SURFACE, linewidth=1)
        if ci:
            ax.errorbar(xs, ys, yerr=err, fmt="none", ecolor=INK2, elinewidth=0.8, capsize=2, alpha=0.6)
    style(ax, key.replace("_", " "))
    ax.set_xticks(range(len(DOMAINS)), DOMAINS, color=INK)
    ax.set_ylim(0, 1.08)
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    ax.legend(frameon=False, ncol=len(systems), loc="upper left", bbox_to_anchor=(0, -0.08), fontsize=8,
              labelcolor=INK2)
    if note:
        fig.text(0.01, 0.005, note, fontsize=7, color=INK2)
    save(fig, name)


def heatmap(rows: list[dict], systems: list[str], name: str) -> None:
    fig, axes = plt.subplots(1, len(DOMAINS), figsize=(14, 3.6), sharey=True)
    for ax, d in zip(axes, DOMAINS):
        types = [k for k in TYPES if any(r[f"type_{k}"] is not None for r in rows if r["domain"] == d)]
        grid = [[next(r for r in rows if r["domain"] == d and r["system"] == s)[f"type_{k}"] for k in types]
                for s in systems]
        vals = [[v if v is not None else float("nan") for v in row] for row in grid]
        ax.imshow(vals, cmap="Blues", vmin=0, vmax=1, aspect="auto")
        for i, row in enumerate(grid):
            for j, v in enumerate(row):
                ax.text(j, i, "–" if v is None else f"{v:.2f}", ha="center", va="center", fontsize=7,
                        color="white" if (v or 0) > 0.6 else INK)
        ax.set_xticks(range(len(types)), [t.replace("_", " ") for t in types], rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(systems)), [LABEL[s] for s in systems], fontsize=8)
        ax.set_title(d, loc="left", fontsize=10, color=INK)
        ax.tick_params(length=0, colors=INK2)
        for s in ax.spines.values():
            s.set_visible(False)
    fig.suptitle("L3 answer score by question type (absent / near miss / out of scope: said 'not reported')",
                 x=0.01, ha="left", fontsize=11, color=INK)
    save(fig, name)


def funnel(rows: list[dict], name: str) -> None:
    keys = [("l1_paper_recall", "L1 found gold papers"), ("l2_value_recall", "L2 extracted gold value"),
            ("l3_text", "L3 answer score")]
    shades = ["#9ec2ef", "#5c9be6", "#2a78d6"]   # one hue, light -> dark: the layers are steps of one pipeline
    fig, ax = plt.subplots(figsize=(8, 3.8))
    w = 0.26
    for i, ((k, lab), c) in enumerate(zip(keys, shades)):
        xs = [j + (i - 1) * w for j in range(len(DOMAINS))]
        ys = [next(r for r in rows if r["domain"] == d and r["system"] == "ours")[k] for d in DOMAINS]
        ax.bar(xs, ys, w * 0.9, color=c, label=lab, edgecolor=SURFACE, linewidth=1)
        for x, y in zip(xs, ys):
            ax.text(x, y + 0.015, f"{y:.2f}", ha="center", va="bottom", fontsize=7, color=INK2)
    style(ax, "share")
    ax.set_xticks(range(len(DOMAINS)), DOMAINS, color=INK)
    ax.set_ylim(0, 1.08)
    ax.set_title("Ours, layer by layer: where the answer is lost", loc="left", color=INK, fontsize=11)
    ax.legend(frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0, -0.08), fontsize=8, labelcolor=INK2)
    save(fig, name)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for d in DOMAINS:
        golds, papers = gold(d), corpus(d)
        rows += [layers(d, s, golds, papers) for s in SYSTEMS]
    with (OUT / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT / "metrics.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    shown = SYSTEMS[:-1]   # closed-book scores 0 everywhere: named in the notes, not drawn
    grouped(rows, "l3_text", shown, "L3 answer score per domain (95% bootstrap interval)", "l3_answer", ci=True,
            note="closed-book scores 0.00 in every domain (not drawn).")
    grouped(rows, "l1_paper_recall", shown, "L1: share of gold papers the system found", "l1_paper_recall",
            note="long-context reads all papers, so its recall is 1 by construction. "
                 "PaperQA2 agent / agent-fixed do not log the papers they read (not drawn).")
    grouped(rows, "l1_paper_precision", shown, "L1: share of found papers that are gold papers",
            "l1_paper_precision")
    grouped(rows, "nr_hallucination", shown, "Not-reported questions: share answered with a made-up value",
            "hallucination")
    funnel(rows, "ours_layers")
    heatmap(rows, SYSTEMS, "l3_by_type")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
