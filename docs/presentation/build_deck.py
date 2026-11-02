"""Build docs/presentation/tim-2026-10-22.pptx (meeting with Tim, 22 Oct 2026) from real run files.

Every runtime number and excerpt on the slides is read from files at build time: the EV1 live rerun in
tests/EV1/live-rerun/ (frozen, in git) and one offline engine run on its LLM-written corpus (made by
--prepare, no GPU and no model: regex extractors only).

How to run (Git Bash, from the repo root; python-pptx lives in a scratch venv, not in the project):

    uv venv "$W/pptx-venv"
    uv pip install --python "$W/pptx-venv/Scripts/python.exe" python-pptx matplotlib networkx pyyaml
    "$W/pptx-venv/Scripts/python.exe" docs/presentation/build_deck.py --work "$W/demo" \
        --prepare --project-python <project venv>/Scripts/python.exe   # --prepare once; it runs the engine

Windows: matplotlib fails to import from a venv under a very long path (MAX_PATH), so map the scratch dir
to a drive first (PowerShell: subst P: "<scratch dir>") and use P:\pptx-venv\Scripts\python.exe,
--work P:\demo. The committed deck was built with --work P:\demo --screenshot P:\pipeline.png, the
project venv being the main checkout's .venv (worktrees have none).

--prepare copies tests/EV1/live-rerun/corpora/rag-llm-s1-mixed to <work>/llm-corpus (line endings
normalised to LF, so the manifest sha256 match on Windows checkouts), then runs, with the project venv:
    python -m evidence.cli run --protocol domains/rag/protocols/rag-factuality.yaml --corpus <work>/llm-corpus
        --out <work>/runs-llm --extractors regex-only --run-id regex-llm
    evaluation oracle  --protocol ... --corpus <work>/llm-corpus --out <work>/oracle-llm
    evaluation score   --run <work>/runs-llm/regex-llm --corpus <work>/llm-corpus
        --oracle <work>/oracle-llm/answer.json --out <work>/scores-llm
Optional: --screenshot <png> of thesis_pipeline.html (branch ev3/demo) for the appendix slide.
Outputs: docs/presentation/tim-2026-10-22.pptx and docs/presentation/img/*.png.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EV1 = REPO / "tests" / "EV1" / "live-rerun"
LLM_CORPUS_SRC = EV1 / "corpora" / "rag-llm-s1-mixed"
PROTOCOL = REPO / "domains" / "rag" / "protocols" / "rag-factuality.yaml"
IMG = HERE / "img"
OUT = HERE / "tim-2026-10-22.pptx"
STUDY = "S005"

# palette (hex without '#')
INK, TEAL, TEAL_L, AMBER, RED, GREEN = "1B2B3A", "0E7C7B", "D5EFEE", "C2410C", "B42318", "15803D"
SLATE, MUTED, PANEL, CODE_BG, WHITE = "475569", "64748B", "EEF2F5", "F3F4F6", "FFFFFF"
HEAD_FONT, BODY_FONT, MONO = "Cambria", "Calibri", "Consolas"


def hx(c: str) -> str:
    return "#" + c


# ---------------------------------------------------------------- data

def run(cmd: list[str], env: dict) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=REPO, env=env)


def prepare(work: Path, py: str) -> None:
    work.mkdir(parents=True, exist_ok=True)
    corpus = work / "llm-corpus"
    if corpus.exists():
        shutil.rmtree(corpus)
    shutil.copytree(LLM_CORPUS_SRC, corpus)
    for p in (corpus / "papers").glob("*.md"):
        p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n"))
    for d in ("runs-llm", "oracle-llm", "scores-llm"):
        shutil.rmtree(work / d, ignore_errors=True)
    env = dict(os.environ, PYTHONPATH=str(REPO), PYDANTIC_AI_NO_BANNER="1")
    ev = [py, "-c", "import sys; from evaluation.cli import main; sys.exit(main(sys.argv[1:]))"]
    run([py, "-m", "evidence.cli", "run", "--protocol", str(PROTOCOL), "--corpus", str(corpus),
         "--out", str(work / "runs-llm"), "--extractors", "regex-only", "--run-id", "regex-llm"], env)
    run(ev + ["oracle", "--protocol", str(PROTOCOL), "--corpus", str(corpus), "--out", str(work / "oracle-llm")], env)
    run(ev + ["score", "--run", str(work / "runs-llm" / "regex-llm"), "--corpus", str(corpus),
              "--oracle", str(work / "oracle-llm" / "answer.json"), "--out", str(work / "scores-llm")], env)


def jload(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def table_row(md: Path, *needles: str) -> list[str]:
    for line in md.read_text(encoding="utf-8").splitlines():
        if all(n in line for n in needles):
            return [c.strip() for c in line.strip().strip("|").split("|")]
    raise KeyError(f"{md}: no row with {needles}")


def load(work: Path) -> dict:
    d: dict = {}
    run_dir = work / "runs-llm" / "regex-llm"
    gt = jload(LLM_CORPUS_SRC / "ground_truth.json")
    d["gt"] = next(s for s in gt["studies"] if s["study_id"] == STUDY)
    d["gt_answer"] = gt["answer"]
    d["corpus"] = jload(LLM_CORPUS_SRC / "corpus.json")
    d["paper"] = (work / "llm-corpus" / "papers" / f"{STUDY}.md").read_bytes().decode("utf-8")
    items = [json.loads(line) for line in (run_dir / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    d["items"] = [i for i in items if i["spans"] and i["spans"][0]["selector"]["file"] == f"papers/{STUDY}.md"]
    d["answer"] = jload(run_dir / "answer.json")
    d["graph"] = jload(run_dir / "graph.json")
    d["run"] = jload(run_dir / "run.json")
    calls = []
    for c in sorted((run_dir / "calls").glob("*.json")):
        j = jload(c)
        if f"papers/{STUDY}.md" in json.dumps(j):
            calls.append(j)
    d["calls"] = calls
    d["score_local"] = jload(work / "scores-llm" / "report.json")
    d["score_local_md"] = work / "scores-llm" / "report.md"
    d["cascade"] = jload(EV1 / "scores" / "cascade" / "rag-llm-s1-mixed" / "report.json")
    d["cmp"] = {k: EV1 / "scores" / k / "compare.md"
                for k in ("compare-cascade", "compare-cascade-gaps", "compare-regex-only")}
    fid = {}
    for lvl in ("explicit", "paraphrased", "distributed", "complex", "contradictory"):
        f = jload(EV1 / "corpora" / f"rag-llm-s1-{lvl}" / "fidelity.json")
        fid[lvl] = (sum(p["ok"] for p in f["papers"]), len(f["papers"]))
    d["fidelity"] = fid
    d["summary"] = jload(EV1 / "run-summary.json")
    d["protocol_text"] = PROTOCOL.read_text(encoding="utf-8")
    return d


# ---------------------------------------------------------------- images

STAGES = ["Paper from\nground truth", "Protocol\n(the IR)", "Extract\n+ check", "Evidence\ngraph",
          "Rules →\nanswer", "Score vs\ntruth"]
STAGE_REF = ["§5", "§2", "§3", "§8.4", "§8.5", "§5 §7"]


def img_strip(active: int | None, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12.0, 1.0), dpi=200)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 1)
    ax.axis("off")
    w, gap = 1.62, 0.4
    for i, (name, ref) in enumerate(zip(STAGES, STAGE_REF)):
        x = 0.05 + i * (w + gap)
        on = i == active
        done = active is not None and i < active
        fc = hx(TEAL) if on else (hx(TEAL_L) if done else hx(PANEL))
        tc = "white" if on else hx(INK)
        ax.add_patch(FancyBboxPatch((x, 0.1), w, 0.8, boxstyle="round,pad=0.0,rounding_size=0.12",
                                    fc=fc, ec=hx(TEAL) if (on or done) else "#CBD5E1", lw=1.4))
        ax.text(x + w / 2, 0.56, name, ha="center", va="center", fontsize=10.5, color=tc,
                fontweight="bold" if on else "normal", family="Calibri", linespacing=1.0)
        ax.text(x + w - 0.08, 0.2, ref, ha="right", va="center", fontsize=7.5,
                color="white" if on else hx(MUTED), family="Calibri")
        if i < len(STAGES) - 1:
            ax.add_patch(FancyArrowPatch((x + w + 0.04, 0.5), (x + w + gap - 0.04, 0.5),
                                         arrowstyle="-|>", mutation_scale=12, color=hx(MUTED), lw=1.2))
    fig.savefig(path, transparent=True, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def img_compiler(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12.0, 3.3), dpi=200)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3.3)
    ax.axis("off")
    boxes = [("Research question", "“Does RAG improve\nfactual accuracy?” (§4)", PANEL, False),
             ("Protocol generation", "LLM + user dialogue\noptional (§8)", WHITE, True),
             ("Executable protocol", "one YAML file: evidence,\nextractors, checks, rules", TEAL, False),
             ("Execution engine", "Python: extractors §3,\nchecks, rules §8.5", PANEL, False),
             ("Evidence graph\n+ answer", "supporting and\ncontradicting studies", PANEL, False)]
    w, gap, y, h = 2.0, 0.42, 1.25, 1.75
    for i, (t, s, fc, dashed) in enumerate(boxes):
        x = 0.05 + i * (w + gap)
        on = fc == TEAL
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.14", fc=hx(fc),
                                    ec=hx(AMBER) if dashed else (hx(TEAL) if on else "#94A3B8"),
                                    lw=1.8, ls=(0, (4, 3)) if dashed else "-"))
        ax.text(x + w / 2, y + h - 0.42, t, ha="center", va="center", fontsize=12.5, fontweight="bold",
                color="white" if on else hx(INK), family="Calibri", linespacing=1.0)
        ax.text(x + w / 2, y + 0.55, s, ha="center", va="center", fontsize=10,
                color="white" if on else hx(SLATE), family="Calibri", linespacing=1.15)
        if i < len(boxes) - 1:
            ax.add_patch(FancyArrowPatch((x + w + 0.03, y + h / 2), (x + w + gap - 0.03, y + h / 2),
                                         arrowstyle="-|>", mutation_scale=16, color=hx(INK), lw=1.6))
    # written by hand path
    ax.annotate("", xy=(2 * (w + gap) + 0.05 + 0.3, y - 0.02), xytext=(0.05 + 0.3 + w * 0.6, y - 0.02),
                arrowprops=dict(arrowstyle="-|>", color=hx(TEAL), lw=1.6, connectionstyle="arc3,rad=0.35"))
    ax.text(0.05 + w + gap + w / 2, 0.42, "today: written by hand (§8 step 1)", ha="center", va="center",
            fontsize=10.5, color=hx(TEAL), family="Calibri", fontweight="bold")
    ax.text(2 * (w + gap) + 0.05 + w / 2, y + h + 0.17, "the intermediate representation", ha="center",
            fontsize=10, color=hx(TEAL), family="Calibri", style="italic")
    fig.savefig(path, transparent=True, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def short(s: str, n: int = 22) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def img_graph(d: dict, path: Path) -> None:
    g = d["graph"]
    nodes = {n["id"]: n for n in g["nodes"]}
    mine = {n["id"] for n in g["nodes"] if n.get("document") == STUDY or n["id"] == STUDY}
    color = {"document": INK, "condition": TEAL, "metric": "7C3AED", "measurement": "2563EB",
             "author_claim": AMBER}
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.1, 3.6), dpi=200, gridspec_kw={"width_ratios": [1.9, 1]})
    # left: the study's own subgraph, laid out by role: paper | conditions | measurements | metrics
    G = nx.DiGraph()
    for e in g["edges"]:
        if e["src"] in mine and e["dst"] in mine:
            G.add_edge(e["src"], e["dst"], rel=e["rel"])
    by_type: dict[str, list[str]] = {}
    for nid in sorted(mine):
        by_type.setdefault(nodes[nid]["type"], []).append(nid)
    pos = {STUDY: (-2.35, 0.55)}
    conds = by_type.get("condition", [])
    ys = [0.75 - 1.5 * k / max(1, len(conds) - 1) for k in range(len(conds))]
    for nid, y in zip(sorted(conds, key=lambda n: nodes[n]["fields"]["role"]), ys):  # baseline above rag
        pos[nid] = (-0.75, y)
    linked_metrics = set()
    for nid in by_type.get("measurement", []):
        links = nodes[nid].get("links", {})
        cy = pos.get(links.get("condition"), (0, 0))[1]
        pos[nid] = (0.75, cy)
        linked_metrics.add(links.get("metric"))
    spare = iter([1.2, -1.2, 1.6])
    for nid in by_type.get("metric", []):
        pos[nid] = (2.65, 0.0) if nid in linked_metrics else (2.65, next(spare))
    for k, nid in enumerate(by_type.get("author_claim", [])):
        pos[nid] = (-2.35, -0.75 - 0.5 * k)

    def label(nid: str) -> str:
        n = nodes[nid]
        f = n.get("fields", {})
        if n["type"] == "document":
            return f"paper {nid}"
        if n["type"] == "condition":
            return f"{f['label']}\nrole: {f['role']}"
        if n["type"] == "metric":
            return f"metric\n“{f['name']}”"
        if n["type"] == "measurement":
            return f"value {f['value']}"
        return f"claim: {f['direction']}"

    edge_style = {"in_document": ("#CBD5E1", 0.9, (0, (3, 3))), "condition": (hx(TEAL), 1.8, "-"),
                  "metric": ("#7C3AED", 1.5, "-"), "supports": (hx(GREEN), 2.8, "-"),
                  "contradicts": (hx(RED), 2.8, "-")}
    for u, v, a in G.edges(data=True):
        c, lw, ls = edge_style.get(a["rel"], ("#94A3B8", 1, "-"))
        pair = a["rel"] in ("supports", "contradicts")
        ax.add_patch(FancyArrowPatch(pos[u], pos[v], arrowstyle="-|>", mutation_scale=14, color=c, lw=lw,
                                     ls=ls, shrinkA=16 if pair else 8, shrinkB=16 if pair else 26,
                                     connectionstyle="arc3,rad=0.9" if pair else "arc3", zorder=1))
        if pair:
            my = (pos[u][1] + pos[v][1]) / 2
            ax.text(pos[u][0] + 0.6, my, a["rel"], color=c, fontsize=12, fontweight="bold", family="Calibri",
                    va="center", ha="left")
    for nid in mine:
        t = nodes[nid]["type"]
        ax.text(*pos[nid], label(nid), ha="center", va="center", fontsize=11, family="Calibri",
                color="white", fontweight="bold", linespacing=1.1, zorder=3,
                bbox=dict(boxstyle="round,pad=0.4", fc=hx(color[t]), ec="none"))
    ax.text(-2.35, 1.55, "dashed: in_document", ha="center", fontsize=10, color=hx(MUTED), family="Calibri")
    ax.set_xlim(-2.95, 3.3)
    ax.set_ylim(-1.45, 1.75)
    ax.axis("off")
    ax.set_title(f"{STUDY}: all its nodes and edges in graph.json", fontsize=13, family="Calibri",
                 color=hx(INK), loc="left")
    # right: the whole run's graph, this study highlighted
    H = nx.Graph()
    for n in g["nodes"]:
        H.add_node(n["id"])
    for e in g["edges"]:
        H.add_edge(e["src"], e["dst"])
    p2 = nx.spring_layout(H, seed=3, k=0.32)
    nx.draw_networkx_edges(H, p2, ax=ax2, edge_color="#CBD5E1", width=0.7)
    others = [n for n in H if n not in mine]
    nx.draw_networkx_nodes(H, p2, nodelist=others, ax=ax2, node_size=28,
                           node_color=[hx(color[nodes[n]["type"]]) for n in others], alpha=0.35)
    nx.draw_networkx_nodes(H, p2, nodelist=list(mine), ax=ax2, node_size=70,
                           node_color=[hx(color[nodes[n]["type"]]) for n in mine], edgecolors=hx(INK),
                           linewidths=1.0)
    ax2.axis("off")
    ax2.set_title(f"whole run: {len(g['nodes'])} nodes, {len(g['edges'])} edges (11 papers)", fontsize=13,
                  family="Calibri", color=hx(INK), loc="left")
    handles = [plt.Line2D([0], [0], marker="o", ls="", color=hx(c), label=t.replace("_", " "), markersize=9)
               for t, c in color.items()]
    ax2.legend(handles=handles, loc="center left", bbox_to_anchor=(0.86, 0.5), ncol=1, frameon=False,
               prop={"family": "Calibri", "size": 11})
    fig.tight_layout()
    fig.savefig(path, transparent=False, facecolor="white")
    plt.close(fig)


def img_fidelity(d: dict, path: Path) -> None:
    fid = d["fidelity"]
    kept = len(d["corpus"]["papers"])
    total = d["corpus"]["settings"]["studies"]
    labels = list(fid) + ["kept at\nevery level"]
    vals = [fid[k][0] for k in fid] + [kept]
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=200)
    colors = [hx(TEAL_L)] * len(fid) + [hx(TEAL)]
    bars = ax.bar(range(len(vals)), vals, color=colors, edgecolor=[hx(TEAL)] * len(vals), width=0.68)
    ax.axhline(total, color=hx(MUTED), lw=1, ls=(0, (4, 3)))
    ax.text(len(vals) - 0.5, total + 0.4, f"{total} planned studies", ha="right", fontsize=11,
            color=hx(MUTED), family="Calibri")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v - 0.6, str(v), ha="center", va="top", fontsize=13, fontweight="bold",
                color=hx(INK), family="Calibri")
    ax.set_xticks(range(len(vals)), labels, fontsize=11, family="Calibri", color=hx(INK))
    ax.set_ylim(0, total + 3)
    ax.set_yticks([])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#CBD5E1")
    ax.set_title("LLM-written papers that passed the fidelity check, per level", fontsize=12.5,
                 family="Calibri", color=hx(INK), loc="left")
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def parse_iv(s: str) -> tuple[float, float | None, float | None]:
    pt, _, rest = s.partition(" ")
    if "n/a" in rest or not rest:
        return float(pt), None, None
    lo, hi = rest.strip("[]").split(",")
    return float(pt), float(lo), float(hi)


def eval_numbers(d: dict) -> dict:
    corpus_id = d["corpus"]["corpus_id"]
    c, g, r = d["cmp"]["compare-cascade"], d["cmp"]["compare-cascade-gaps"], d["cmp"]["compare-regex-only"]
    # interval rows (second table) have 7 columns; metric rows have 17
    def iv(md, system, strategy):
        rows = [ln for ln in md.read_text(encoding="utf-8").splitlines()
                if corpus_id in ln and system in ln and f" {strategy} " in ln]
        row = [x.strip() for x in rows[-1].strip().strip("|").split("|")]
        return row
    def met(md, system, strategy):
        rows = [ln for ln in md.read_text(encoding="utf-8").splitlines()
                if corpus_id in ln and system in ln and f" {strategy} " in ln]
        return [x.strip() for x in rows[0].strip().strip("|").split("|")]
    out = {}
    for key, md, sysname, strat in [("regex", r, "evidence-engine", "all"), ("cascade", c, "evidence-engine", "all"),
                                    ("gaps", g, "evidence-engine", "gaps"), ("rag", c, "rag-baseline", "-"),
                                    ("agent", c, "agent-baseline", "-")]:
        i, m = iv(md, sysname, strat), met(md, sysname, strat)
        out[key] = {"dir": parse_iv(i[5]), "f1": m[4], "true_pair": m[7], "complete": m[9],
                    "calls": m[13], "tokens": m[14], "diff": i[6]}
    return out


def img_eval(ev: dict, path: Path) -> None:
    names = [("regex", "Engine, regex only"), ("gaps", "Engine, cascade “gaps”"),
             ("cascade", "Engine, cascade “all”"), ("rag", "RAG baseline (answer level)"),
             ("agent", "Research agent (ours)")]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13, 4.6), dpi=200, gridspec_kw={"width_ratios": [1.45, 1]})
    cols = {"regex": TEAL_L, "gaps": "5FB3B1", "cascade": TEAL, "rag": "94A3B8", "agent": SLATE}
    for k, (key, lab) in enumerate(names):
        pt, lo, hi = ev[key]["dir"]
        y = len(names) - 1 - k
        ax.barh(y, pt, color=hx(cols[key]), height=0.62)
        if lo is not None:
            ax.plot([lo, hi], [y, y], color=hx(INK), lw=2)
            ax.plot([lo, lo], [y - 0.13, y + 0.13], color=hx(INK), lw=2)
            ax.plot([hi, hi], [y - 0.13, y + 0.13], color=hx(INK), lw=2)
        txt = f"{pt:.3f}" + (f"  [{lo:.2f}, {hi:.2f}]" if lo is not None else "  (all 11 right)")
        ax.text(1.03, y, txt, va="center", fontsize=12.5, family="Calibri", color=hx(INK))
        ax.text(-0.02, y, lab, va="center", ha="right", fontsize=12.5, family="Calibri", color=hx(INK))
    ax.set_xlim(0, 1.0)
    ax.set_yticks([])
    ax.set_xticks([0, 0.5, 1.0])
    ax.tick_params(labelsize=11)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_title("C · per-study direction accuracy, 95 % interval", fontsize=13, family="Calibri",
                 loc="left", color=hx(INK))
    # paired differences
    diffs = [("Engine − RAG", parse_iv(ev["rag"]["diff"])), ("Engine − agent", parse_iv(ev["agent"]["diff"]))]
    for k, (lab, (pt, lo, hi)) in enumerate(diffs):
        y = 1 - k
        ax2.plot([lo, hi], [y, y], color=hx(TEAL), lw=5, solid_capstyle="round")
        ax2.plot(pt, y, "o", color=hx(INK), markersize=11)
        ax2.text(0.3, y + 0.3, f"{pt:+.3f}  [{lo:.2f}, {hi:.2f}]", ha="center", fontsize=13, family="Calibri",
                 fontweight="bold", color=hx(INK), zorder=3,
                 bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
        ax2.text(-0.62, y, lab, ha="left", va="center", fontsize=12.5, family="Calibri", color=hx(INK))
    ax2.axvline(0, color=hx(RED), lw=1.2, ls=(0, (4, 3)))
    ax2.text(0.01, -0.62, "no difference", color=hx(RED), fontsize=11, family="Calibri")
    ax2.set_xlim(-0.62, 0.85)
    ax2.set_ylim(-0.75, 1.65)
    ax2.set_yticks([])
    ax2.set_xticks([0, 0.25, 0.5, 0.75])
    ax2.tick_params(labelsize=11)
    for s in ("top", "right", "left"):
        ax2.spines[s].set_visible(False)
    ax2.set_title("Paired difference (cascade “all” minus baseline)", fontsize=13, family="Calibri",
                  loc="left", color=hx(INK))
    fig.tight_layout(w_pad=4)
    fig.subplots_adjust(left=0.2)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def img_screenshot(src: Path, path: Path) -> bool:
    if not src or not src.exists():
        return False
    from PIL import Image
    im = Image.open(src)
    w, h = im.size
    im.crop((int(w * 0.012), int(h * 0.215), int(w * 0.985), int(h * 0.975))).save(path, optimize=True)
    return True


# ---------------------------------------------------------------- pptx helpers

def rgb(c: str) -> RGBColor:
    return RGBColor.from_string(c)


class Deck:
    def __init__(self) -> None:
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(13.333), Inches(7.5)
        self.blank = self.prs.slide_layouts[6]
        self.n = 0

    def slide(self, dark: bool = False):
        s = self.prs.slides.add_slide(self.blank)
        bg = s.background.fill
        bg.solid()
        bg.fore_color.rgb = rgb(INK if dark else WHITE)
        self.n += 1
        return s

    @staticmethod
    def text(s, x, y, w, h, paras, size=18, color=INK, font=BODY_FONT, bold=False, italic=False,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=4, name=None):
        """paras: str | list of str | list of list of (text, {opts}) runs."""
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        if name:
            tb.name = name
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.04)
        tf.margin_top = tf.margin_bottom = Inches(0.02)
        tf.vertical_anchor = anchor
        if isinstance(paras, str):
            paras = [paras]
        for k, para in enumerate(paras):
            p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
            p.alignment = align
            p.space_after = Pt(spacing)
            runs = [(para, {})] if isinstance(para, str) else para
            for t, o in runs:
                r = p.add_run()
                r.text = t
                f = r.font
                f.name = o.get("font", font)
                f.size = Pt(o.get("size", size))
                f.bold = o.get("bold", bold)
                f.italic = o.get("italic", italic)
                f.color.rgb = rgb(o.get("color", color))
        return tb

    @staticmethod
    def box(s, x, y, w, h, fill=PANEL, line=None, radius=0.06, dash=False):
        shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        shp.adjustments[0] = radius
        shp.fill.solid()
        shp.fill.fore_color.rgb = rgb(fill)
        if line:
            shp.line.color.rgb = rgb(line)
            shp.line.width = Pt(1.5)
            if dash:
                from pptx.enum.dml import MSO_LINE_DASH_STYLE
                shp.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        else:
            shp.line.fill.background()
        shp.shadow.inherit = False
        return shp

    def title(self, s, t, sub=None):
        self.text(s, 0.6, 0.32, 12.1, 0.75, t, size=29, font=HEAD_FONT, bold=True, name="Title")
        if sub:
            self.text(s, 0.6, 0.98, 12.1, 0.4, sub, size=17, color=MUTED, name="Subtitle")

    def code(self, s, x, y, w, h, lines, size=13, label=None):
        self.box(s, x, y, w, h, fill=CODE_BG, line="D1D5DB", radius=0.03)
        top = y + 0.08
        if label:
            self.text(s, x + 0.15, y + 0.08, w - 0.3, 0.3, label, size=12, color=MUTED, bold=True)
            top = y + 0.38
        paras = []
        for ln in lines:
            if isinstance(ln, tuple):
                paras.append([(ln[0], {"color": ln[1], "bold": True})])
            else:
                paras.append(ln)
        self.text(s, x + 0.15, top, w - 0.3, h - (top - y) - 0.05, paras, size=size, font=MONO, spacing=0)

    def quote(self, s, x, y, w, h, q, cite, size=17):
        self.box(s, x, y, w, h, fill=TEAL_L, radius=0.08)
        self.text(s, x + 0.12, y - 0.12, 0.6, 0.7, "“", size=44, font=HEAD_FONT, color=TEAL, bold=True)
        self.text(s, x + 0.6, y + 0.14, w - 0.8, h - 0.5, q, size=size, italic=True, color=INK, spacing=0)
        self.text(s, x + 0.6, y + h - 0.4, w - 0.8, 0.32, cite, size=13, color=TEAL, bold=True)

    def tag(self, s, x, y, label="ours"):
        shp = self.box(s, x, y, 0.85 if label == "ours" else 1.6, 0.32, fill=WHITE, line=AMBER, radius=0.5,
                       dash=True)
        tf = shp.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = label
        r.font.size, r.font.bold, r.font.name = Pt(12), True, BODY_FONT
        r.font.color.rgb = rgb(AMBER)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE

    def source(self, s, t, dark=False):
        self.text(s, 0.6, 7.0, 12.1, 0.35, t, size=11, color="94A3B8" if dark else MUTED, name="Source")

    def strip(self, s, k):
        s.shapes.add_picture(str(IMG / f"stage-{k}.png"), Inches(0.6), Inches(1.42), width=Inches(12.1))

    @staticmethod
    def notes(s, t):
        s.notes_slide.notes_text_frame.text = t


# ---------------------------------------------------------------- slides

def build(d: dict, have_shot: bool) -> None:
    D = Deck()
    gt, paper, ans = d["gt"], d["paper"], d["answer"]
    st = next(x for x in ans["studies"] if x["document"] == STUDY)
    cas = d["cascade"]
    cas_row = next(r for r in cas["funnel"]["rows"] if r["document"] == STUDY)
    per_sys = {}
    for b in cas["synthesis"]:
        name = b.get("system") or "evidence-engine"
        per_sys[name] = next(x for x in b["studies"] if x["study"] == STUDY)
    sys_order = [x for x in per_sys]
    ev = eval_numbers(d)
    retained, total = len(d["corpus"]["papers"]), d["corpus"]["settings"]["studies"]
    models = d["corpus"]["models"]
    cond = {c["id"]: c for c in gt["conditions"]}
    meas = gt["measurements"]
    eff = gt["effect"]
    loc = d["score_local"]
    att_all = table_row(d["score_local_md"], "| evidence-engine |", "| all ", "| 11 ")
    loc_all = table_row(d["score_local_md"], "| all ", "| all ", "| 124 ")
    run_id_note = "offline run regex-llm (regex extractors, no model) on tests/EV1/live-rerun/corpora/rag-llm-s1-mixed"

    # 1 -------------------------------------------------------------- title
    s = D.slide(dark=True)
    D.text(s, 0.8, 0.7, 11.5, 0.4, "Master’s thesis · progress meeting · 22 October 2026",
           size=16, color="94A3B8")
    D.text(s, 0.8, 1.2, 11.7, 1.7, "From a research question to a traceable answer", size=40,
           font=HEAD_FONT, bold=True, color=WHITE)
    D.text(s, 0.8, 2.95, 11.5, 0.9, "Your 14 October direction, running end to end: one real paper followed "
           "through the system, then the first live evaluation", size=22, color="CBD5E1")
    D.box(s, 0.8, 4.0, 11.7, 1.35, fill="243B53", radius=0.08)
    D.text(s, 1.0, 3.87, 0.6, 0.7, "“", size=44, font=HEAD_FONT, color="5EEAD4", bold=True)
    D.text(s, 1.55, 4.17, 10.8, 0.75, "we should investigate how to operationalize research questions into "
           "explicit evidence requirements.", size=22, italic=True, color=WHITE)
    D.text(s, 1.55, 4.87, 10.8, 0.35, "Tim, message 1, 14 Oct", size=14, bold=True, color="5EEAD4")
    s.shapes.add_picture(str(IMG / "stage-none.png"), Inches(0.8), Inches(5.75), width=Inches(11.7))
    D.source(s, "Aditya Kumar Gupta · use case (your §4): Does RAG improve the factual accuracy of "
             "LLM-generated answers?  ·  dashed amber “ours” tags mark our additions", dark=True)
    D.notes(s, "Open with Tim's own framing (M1, 14 Oct): evidence-level reasoning, a protocol as the plan, the "
            "synthetic benchmark as the main instrument (M2 §8-§9).\n\nPlan for 20 minutes: (1) his compiler "
            "picture as it runs (1 slide); (2) one real paper, study S005 of the LLM-written EV1 corpus, followed "
            "stage by stage through the real files (6 slides); (3) the benchmark and the first live evaluation, "
            "EV1 = Slurm job 7588, 20-21 Oct (2 slides); (4) what changed on 21 Oct and the question for him.\n\n"
            "Legend: anything with a dashed amber 'ours' tag is our addition, not something he asked for. Quotes "
            "are verbatim from his two messages of 14 Oct (M1, M2 §1-§9).")

    # 2 -------------------------------------------------------------- compiler
    s = D.slide()
    D.title(s, "Your compiler analogy, as it runs today",
            "The research protocol is the intermediate representation (§2)")
    s.shapes.add_picture(str(IMG / "compiler.png"), Inches(0.6), Inches(1.55), width=Inches(12.1))
    D.quote(s, 0.6, 5.0, 7.3, 1.75, "The research question is the high-level input, while the research protocol "
            "acts as an intermediate representation specifying how the investigation should be conducted.",
            "Tim, M2 §2", size=16)
    D.text(s, 8.25, 5.0, 4.5, 1.9, [
        [("Protocol: ", {"bold": True}), ("hand-written YAML, as in §8 step 1.", {})],
        [("Record and replay (ours): ", {"bold": True}), ("every call recorded, so a run replays identically "
                                          f"(EV1: {d['summary']['engine_replay_ok']} replays, "
                                          f"{d['summary']['engine_replay_mismatch']} mismatches).", {})],
    ], size=17, spacing=8)
    D.source(s, "Dashed amber box = optional extension (§8); our proposal flow with a critic implements it. Replay counts: tests/EV1/live-rerun/run-summary.json.")
    D.notes(s, "Walk left to right. The protocol is the IR (§2: declarative YAML or JSON, executed by a Python "
            "engine; SPARQL optional for querying the graph). Protocol generation exists as an LLM proposal flow "
            "with a critic and choice cards, but that flow is OURS and he made it optional (§8: 'I would not "
            "make either of these extensions a requirement'), so all runs today use the hand-written protocol "
            "domains/rag/protocols/rag-factuality.yaml.\n\nProvenance and replay are ours. Motivation, reported by "
            "Aditya on 16 Oct (not in his written messages): an answer without its steps is like a calculator "
            "result, hard to check and trust. EV1: 43 engine replays, 0 mismatches (run-summary.json).\n\n"
            "Next six slides: one paper through these boxes, from the real files.")

    # 3 -------------------------------------------------------------- ground truth + paper
    s = D.slide()
    D.title(s, "Ground truth first, then the paper (§5)",
            f"Study {STUDY} of the first live run: planned as data, then written by an LLM")
    D.strip(s, 0)
    c1 = cond[meas[0]["condition"]]
    gt_lines = [f'"study_id": "{gt["study_id"]}",  "level": "{gt["level"]}",',
                '"conditions": [']
    for c in gt["conditions"]:
        gt_lines.append(f'  {{"label": "{c["label"]}", "role": "{c["role"]}"}},')
    gt_lines.append(f'"metric": "{gt["metrics"][0]["name"]}"  ({gt["metrics"][0]["canonical"]}),')
    gt_lines.append('"measurements" on ' + meas[0]["dataset"] + ":")
    for m in meas:
        gt_lines.append(f'  {cond[m["condition"]]["label"]:<26} {m["value"]}')
    gt_lines.append(("\"author_claim\": \"" + gt["author_claim"]["direction"] + "\"", AMBER))
    gt_lines.append((f'"effect": "{eff["direction"]}", "delta": +{eff["delta"]}', GREEN))
    D.code(s, 0.6, 2.55, 6.25, 4.3, gt_lines, size=12, label="ground_truth.json (excerpt)")
    # paper excerpt: the claim sentence of the abstract, the table, the conclusion sentence
    lines = paper.splitlines()
    tbl = [ln for ln in lines if ln.startswith("|") and ":---" not in ln]
    abstract_claim = next(ln for ln in lines if "does not make the answers" in ln).split(". ")[-1]
    concl = d["items"][-1]["spans"][0]["selector"]["exact"] if d["items"][-1]["evidence_type"] == "author_claim" \
        else next(i for i in d["items"] if i["evidence_type"] == "author_claim")["spans"][0]["selector"]["exact"]
    pl = ["## Abstract", ("… " + abstract_claim, AMBER), "", "## Results"]
    pl += [ln.replace(" |", "|").replace("| ", "|")[:44] for ln in tbl]
    pl += ["", "## Conclusion", ("… " + concl, AMBER)]
    D.code(s, 7.05, 2.55, 5.7, 4.3, pl, size=12, label=f"papers/{STUDY}.md, written by {models['renderer'].split('@')[0]} (excerpt)")
    D.source(s, "tests/EV1/live-rerun/corpora/rag-llm-s1-mixed/ (ground_truth.json, papers/S005.md, corpus.json); "
             "EV1, Slurm job 7588")
    D.notes(s, f"Tim §5: 'Ground-truth scientific data → Synthetic papers'. We first planned study {STUDY} as "
            f"data: {c1['label']} {meas[0]['value']} vs retrieval-augmented model {meas[1]['value']} on "
            f"{meas[0]['dataset']}, so the truth is '{eff['direction']}' with delta +{eff['delta']}. Then the LLM "
            f"writer ({models['renderer']}) wrote the paper.\n\nThis study is at the 'contradictory' level of his "
            "§6 list: the authors' conclusion ('no effect', amber) does not agree with their own numbers. "
            "That is exactly his §7 test case: 'An answer-level system might reproduce these conclusions, "
            "while an evidence-level system should ideally identify the discrepancy.'\n\nThe paper also has two "
            "distractor conditions (fine-tuned model, RAG without reranking) that do not belong in the RAG-vs-"
            "baseline pair. Everything on this slide is copied from the files at build time, not retyped.")

    # 4 -------------------------------------------------------------- protocol
    s = D.slide()
    D.title(s, "The protocol: the evidence this question needs (§2, §4)",
            "One YAML file, written by hand before any run; the engine runs it as it stands")
    D.strip(s, 1)
    pt = d["protocol_text"].splitlines()

    def grab(prefix: str, n: int = 1) -> list[str]:
        i = next(k for k, ln in enumerate(pt) if ln.startswith(prefix))
        return [ln.split("  #")[0].rstrip() for ln in pt[i:i + n]]
    y_lines = ["id: rag-factuality", "evidence_types:", "  condition:    {label, role: rag|baseline|other}",
               "  metric:       {name, canonical, higher_is_better}",
               "  measurement:  {value, dataset}  links: condition, metric",
               "    bounds: value in [0, 1] for accuracy/rates",
               "  author_claim: {direction: improves|no_effect|worsens}"]
    import yaml
    syn_spec = yaml.safe_load(d["protocol_text"])["synthesis"]
    cm = syn_spec["claim_map"]
    y_lines += ["synthesis:"] + [ln for ln in grab("  compare:")] + [ln for ln in grab("  min_effect:")]
    pairs = [f"{k}→{v}" for k, v in cm.items()]
    y_lines += ["  claim_map: " + ", ".join(pairs[:2]) + ",", "             " + ", ".join(pairs[2:])]
    for k, row in enumerate(syn_spec["label"][:2]):
        cond_ = " & ".join(f"{a}{b}" for a, b in row.get("when", {}).items())
        y_lines.append(("  label:  " if k == 0 else "          ") + f"[{cond_}] → {row['then']}")
    y_lines.append("          …")
    D.code(s, 0.6, 2.55, 6.5, 4.3, y_lines, size=13, label="domains/rag/protocols/rag-factuality.yaml (condensed)")
    rows = [("Which models and experimental conditions were compared?", "condition"),
            ("Was RAG compared against a baseline without retrieval?", "synthesis.compare: rag vs baseline"),
            ("Which metrics were used to measure factual accuracy?", "metric"),
            ("What were the reported results?", "measurement (+ links)"),
            ("Which experiments showed improvements, no effect, or deterioration?", "rules: min_effect, label")]
    D.text(s, 7.4, 2.5, 5.4, 0.4, "Your §4 questions → protocol entries", size=17, bold=True, color=TEAL)
    yy = 2.95
    for q, a in rows:
        D.box(s, 7.4, yy, 5.35, 0.7, fill=PANEL, radius=0.1)
        D.text(s, 7.5, yy + 0.04, 3.45, 0.64, "“" + q + "”", size=13, italic=True, anchor=MSO_ANCHOR.MIDDLE)
        D.text(s, 10.95, yy + 0.04, 1.75, 0.64, a, size=13, bold=True, color=TEAL, font=BODY_FONT,
               anchor=MSO_ANCHOR.MIDDLE)
        yy += 0.78
    D.source(s, "Quoted questions: Tim, M2 §4. Protocol sha256 6b360bca…, the same file for every EV1 run and this one.")
    D.notes(s, "Tim §2: 'I would currently favor a declarative protocol representation (e.g., YAML or JSON), "
            "executed by a Python-based engine.' That is what we have. The left side is a condensed view of the "
            "real file (field lists shortened; the compare, min_effect, claim_map and first label row are copied "
            "from the file).\n\nRight side: his §4 bullets, verbatim, mapped to protocol entries. Note: "
            "'Was RAG compared against a baseline without retrieval?' is not an extractor; it is the rule that "
            "pairs the rag and baseline conditions.\n\nThe bounds line matters: an accuracy of 175 % is rejected "
            "(the EV1 proposal flow had accepted it; fixed 21 Oct). The engine also has a screen step and a "
            "locate step; those are ours (the funnel), omitted here.")

    # 5 -------------------------------------------------------------- extraction + checks
    s = D.slide()
    D.title(s, "Reusable extractors (§3): each value keeps its passage",
            f"What the regex extractors found in {STUDY}, and what the engine checked")
    D.strip(s, 2)
    m_rag = next(i for i in d["items"] if i["evidence_type"] == "measurement" and i["fields"]["value"] == meas[1]["value"])
    vsel = next(sp["selector"] for sp in m_rag["spans"] if sp["role"] == "value")
    csel = next(sp["selector"] for sp in m_rag["spans"] if sp["role"] == "condition_label")
    ex = ['"evidence_type": "measurement",',
          f'"fields": {{"value": {m_rag["fields"]["value"]}, "dataset": {json.dumps(m_rag["fields"]["dataset"])}}},',
          f'"links": condition → "{csel["exact"]}"',
          '         metric    → "answer accuracy"',
          '"spans": [ { "role": "value",',
          (f'   "exact": "{vsel["exact"]}",  "start": {vsel["start"]}, "end": {vsel["end"]},', TEAL),
          f'   "file": "{vsel["file"]}", "sha256": "{vsel["sha256"][:8]}…" }} … ]',
          f'"found_by": ["{m_rag["found_by"][0].split("#")[0]}"]']
    D.code(s, 0.6, 2.55, 7.0, 2.85, ex, size=14, label="runs/regex-llm/evidence.jsonl (one item, trimmed)")
    n_items = len(d["items"])
    n_rej = sum(len(c["rejected"]) for c in d["calls"])
    counts: dict[str, int] = {}
    for i in d["items"]:
        counts[i["evidence_type"]] = counts.get(i["evidence_type"], 0) + 1
    D.box(s, 0.6, 5.6, 7.0, 1.25, fill=TEAL_L, radius=0.1)
    D.text(s, 0.75, 5.65, 6.75, 1.15, [[("Checks on every item: ", {"bold": True}),
           ("quote re-anchored at its offsets in the paper (sha256), schema and bounds, links, scope. ", {}),
           (f"{STUDY}: {len(d['calls'])} extractor calls, {n_items} items, {n_rej} rejected.", {"bold": True, "color": TEAL})]],
           size=17, anchor=MSO_ANCHOR.MIDDLE)
    D.text(s, 7.9, 2.5, 4.9, 0.4, "Regex only (this run)", size=18, bold=True, color=TEAL)
    found_c = [i["fields"]["label"] for i in d["items"] if i["evidence_type"] == "condition"]
    missed = [c["label"] for c in gt["conditions"] if c["label"] not in found_c]
    D.text(s, 7.9, 2.9, 4.9, 1.6, [
        f"Found: {counts.get('condition', 0)} conditions, {counts.get('measurement', 0)} measurements, "
        f"{counts.get('metric', 0)} metrics, {counts.get('author_claim', 0)} claim; no model call.",
        [("Missed: ", {"bold": True, "color": RED}), (", ".join(missed) + " (and their values).", {})],
        [("False hit: ", {"bold": True, "color": RED}), ("metric “accuracy” from “citation accuracy” in the discussion.", {})]],
        size=15, spacing=6)
    D.box(s, 7.9, 4.65, 4.85, 2.2, fill=WHITE, line=AMBER, radius=0.06, dash=True)
    D.text(s, 8.05, 4.72, 3.6, 0.4, "Cascade, EV1 live run", size=18, bold=True, color=AMBER)
    D.tag(s, 11.75, 4.78)
    miss_cas = [f for f in cas["extraction"]["missed"] if f.startswith(STUDY)]
    D.text(s, 8.05, 5.15, 4.6, 1.65, [
        "Regex first, then LLM extractors for what is still missing.",
        f"On {STUDY}: {cas_row['calls']} calls, {cas_row['model_calls']} to the model, "
        f"{cas_row['tokens']:,} tokens.",
        f"Still missed: {', '.join(cond[f]['label'] if f in cond else f for f in miss_cas) or 'nothing'}."],
        size=15, spacing=5)
    D.source(s, f"Left and top right: {run_id_note}. Bottom right: tests/EV1/live-rerun/scores/cascade/rag-llm-s1-mixed/report.json.")
    D.notes(s, "Tim §3: 'These extractors could use regular expressions, specialized models, LLMs, or other "
            "methods. Their implementations should be interchangeable.' We have one interface; regex and LLM "
            "extractors per evidence type, plus an agentic extractor (ours).\n\nThe item on the left is real: the "
            f"value 53.8 % becomes {m_rag['fields']['value']}, linked to its condition and metric, with the exact "
            f"passage at characters {vsel['start']}-{vsel['end']} of the paper and the paper's sha256. That is his "
            "§5A 'accuracy of evidence provenance'.\n\nChecks (the implementation is ours): R1 every quote is "
            "re-anchored in the text and may not cut a number; R2 JSON schema plus bounds (accuracy in [0,1]); "
            f"R3 inside the located scope. Here: 0 rejected.\n\nRegex alone missed the two distractor conditions "
            "(role 'other') and picked up a spurious metric. The cascade (OURS) runs the LLM extractors after the "
            f"regex: on this paper {cas_row['model_calls']} model calls and {cas_row['tokens']} tokens in EV1, "
            "and it still missed 'RAG without reranking'. We did not see the LLM outputs themselves here, only the "
            "scored counts, so the slide shows only those.")

    # 6 -------------------------------------------------------------- graph
    s = D.slide()
    D.title(s, "Evidence representation: the connections are kept (§8 step 4)",
            "Study → measurement → condition and metric → source passage, one graph per run")
    D.strip(s, 3)
    s.shapes.add_picture(str(IMG / "graph.png"), Inches(0.6), Inches(2.4), width=Inches(12.1))
    D.quote(s, 0.6, 6.0, 12.1, 0.92, "Preserve the connections between studies, experiments, measurements, and "
            "source passages.", "Tim, M2 §8, step 4", size=16)
    D.source(s, f"Drawn from runs/regex-llm/graph.json of the {run_id_note.split(' (')[0]}.")
    D.notes(s, "Left: every node and edge of study S005 in graph.json, nothing added. The two measurements link "
            "to their condition (teal) and metric (purple); the green 'supports' edge is the pair the rules "
            "formed: RAG 0.538 against closed-book 0.406. The second metric node 'accuracy' is the regex false "
            "hit from 'citation accuracy'; it has no measurement, so it does not affect the answer.\n\nRight: the "
            "whole run, 11 papers. Each node keeps its spans (passage offsets) in evidence.jsonl; the graph can "
            "also be exported as PROV-O / queried with SPARQL (ours, §2 says SPARQL is optional).\n\nThe "
            "'experiment' level (several experiments per paper) is in the harder benchmark planned for EV2.")

    # 7 -------------------------------------------------------------- rules -> answer
    s = D.slide()
    D.title(s, "Explicit rules derive the answer (§4, §8 step 5)",
            f"{STUDY}: the numbers say ‘supports’, the authors say ‘no effect’, and both are recorded")
    D.strip(s, 4)
    a_lines = [f'"document": "{st["document"]}",',
               f'"treatment": {{"value": {st["treatment"]["value"]}}},   (retrieval-augmented)',
               f'"control":   {{"value": {st["control"]["value"]}}},   (closed-book)',
               (f'"delta": {st["delta"]},  "direction": "{st["direction"]}",', GREEN),
               f'"author_claim": {{"direction": "{st["author_claim"]["direction"]}",',
               (f'                 "agrees_with_data": {str(st["author_claim"]["agrees_with_data"]).lower()}}},', RED),
               (f'"flags": {json.dumps(st["flags"])}', RED)]
    D.code(s, 0.6, 2.55, 7.0, 2.75, a_lines, size=14, label="runs/regex-llm/answer.json (study entry)")
    D.text(s, 0.6, 5.55, 7.0, 1.3, [
        [("Rule: ", {"bold": True}), (f"pair rag vs baseline on the same dataset; |delta| < 0.01 is neutral; "
                                       "otherwise supports or contradicts. The claim is mapped by claim_map "
                                       "and compared, never used as the result.", {})]], size=16)
    D.text(s, 7.95, 2.5, 4.8, 0.4, "Answer over all 11 papers", size=18, bold=True, color=TEAL)
    ca = cas["synthesis"][0]["flags"]["counts"]
    c_reg = ans["counts"]
    rows = [("", "label", "sup.", "contra.", "neutral", "undet."),
            ("Truth", d["gt_answer"]["label"], len(d["gt_answer"]["supporting"]), len(d["gt_answer"]["contradicting"]),
             len(d["gt_answer"]["neutral"]), len(d["gt_answer"]["undetermined"])),
            ("Cascade (EV1)", cas["synthesis"][0]["label"], ca["given"]["supporting"], ca["given"]["contradicting"],
             ca["given"]["neutral"], ca["given"]["undetermined"]),
            ("Regex only", ans["label"], c_reg["supporting"], c_reg["contradicting"], c_reg["neutral"],
             c_reg["undetermined"])]
    tb = s.shapes.add_table(len(rows), 6, Inches(7.95), Inches(2.95), Inches(4.8), Inches(1.6)).table
    widths = [1.4, 0.7, 0.55, 0.75, 0.75, 0.65]
    for j, wv in enumerate(widths):
        tb.columns[j].width = Inches(wv)
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            cell = tb.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = rgb(TEAL if i == 0 else (PANEL if i % 2 else WHITE))
            cell.margin_left = cell.margin_right = Inches(0.05)
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            run_ = p.add_run()
            run_.text = str(v)
            run_.font.size = Pt(14)
            run_.font.name = BODY_FONT
            run_.font.bold = i == 0 or j == 0
            run_.font.color.rgb = rgb(WHITE if i == 0 else INK)
    D.text(s, 7.95, 4.7, 4.8, 0.4, "claim_disagrees flagged: " + ", ".join(ans["flags"]["claim_disagrees"]) +
           " (truth: " + ", ".join(d["gt_answer"]["flags"]["claim_disagrees"]) + ")", size=15, color=INK)
    D.quote(s, 7.95, 5.3, 4.8, 1.45, "the synthesis can initially be implemented using deterministic procedures.",
            "Tim, M2 §4", size=16)
    D.source(s, "Truth: ground_truth.json ‘answer’. Cascade counts: EV1 scores/cascade/rag-llm-s1-mixed/report.json. "
             "Regex: this offline run.")
    D.notes(s, f"The study entry is copied from answer.json. Treatment {st['treatment']['value']} vs control "
            f"{st['control']['value']}, delta {st['delta']}, so 'supports'. The authors' claim is extracted too "
            "('no_effect') and compared with the data: agrees_with_data false, flag claim_disagrees. This is the "
            "§7 discrepancy he wanted the evidence-level system to find.\n\nRules are all in the protocol's "
            "synthesis block (compare, min_effect 0.01, pairing same_dataset, claim_map, label rows). Label: "
            "'mixed' when there are supporting and contradicting studies.\n\nTable: the regex-only run gets the "
            "right label but for the wrong reason: 8 of 11 studies undetermined. The cascade in EV1 gets all "
            "counts right (5/3/3). The label alone is too coarse a score; next slide shows per study.")

    # 8 -------------------------------------------------------------- score vs truth
    s = D.slide()
    D.title(s, "Scored against the truth, and where it failed (§5 C, §7)",
            f"{STUDY} through four systems on the same LLM-written corpus")
    D.strip(s, 5)
    names = {"evidence-engine": "Evidence engine, cascade", "rag-baseline": "RAG baseline (answer level)",
             "agent-baseline": "Research agent (answer level)"}
    D.text(s, 0.6, 2.5, 6.9, 0.4, f"Truth for {STUDY}: {eff['direction']} (+{eff['delta']})", size=18, bold=True,
           color=GREEN)
    yy = 2.98
    entries = [(names[k], per_sys[k]["given"], per_sys[k]["correct"], k == "agent-baseline") for k in sys_order]
    entries.insert(1, ("Evidence engine, regex only", st["direction"], st["direction"] == eff["direction"], False))
    for lab, given, ok, ours in entries:
        D.box(s, 0.6, yy, 6.9, 0.62, fill=PANEL, radius=0.12)
        D.text(s, 0.75, yy + 0.04, 4.2, 0.55, lab, size=17, anchor=MSO_ANCHOR.MIDDLE)
        D.text(s, 4.85, yy + 0.04, 2.1, 0.55, given, size=17, bold=True, color=GREEN if ok else RED,
               anchor=MSO_ANCHOR.MIDDLE)
        D.text(s, 6.85, yy + 0.04, 0.6, 0.55, "✓" if ok else "✗", size=22, bold=True,
               color=GREEN if ok else RED, anchor=MSO_ANCHOR.MIDDLE)
        if ours:
            D.tag(s, 3.85, yy + 0.15)
        yy += 0.72
    D.text(s, 0.6, 5.95, 6.9, 0.9, "The agent answered ‘neutral’: the authors’ conclusion. The RAG "
           "baseline left the study undetermined.", size=16, color=INK)
    D.text(s, 7.85, 2.5, 4.9, 0.4, "Where the errors come from", size=18, bold=True, color=TEAL)
    D.text(s, 7.85, 2.92, 4.9, 1.9, [
        [("Regex-only run, all 11 studies: ", {}), (f"{att_all[3]} right", {"bold": True}),
         (f"; the perfect-evidence oracle gets {att_all[4]} right.", {})],
        [(f"{att_all[5]} wrong studies are upstream (extraction), {att_all[6]} downstream (synthesis).",
          {"bold": True, "color": TEAL})],
        [(f"Extraction F1 {loc_all[7]}, the same as the EV1 regex-only run ({ev['regex']['f1']}).", {})]],
        size=16, spacing=7)
    D.quote(s, 7.85, 5.2, 4.9, 1.6, "this also allows us to distinguish extraction errors from synthesis errors.",
            "Tim, M2 §5 C", size=16)
    D.source(s, "Cascade, RAG, agent: EV1 scores/cascade/rag-llm-s1-mixed/report.json (synthesis.studies). "
             "Regex only and attribution: this offline run, scores-llm/report.md.")
    D.notes(s, "Per-study result for S005, read from the EV1 score report: the cascade engine says supports "
            "(right, and flags the disagreeing claim); the RAG baseline (his §7 answer-level baseline) says "
            "undetermined; our research agent (ours, an extra baseline) says neutral, i.e. it reproduced the "
            "authors' conclusion. That is the §7 prediction, on one study. Do not over-sell one study; the "
            "aggregate is on slide 10.\n\nRight: the oracle runs our own synthesis on perfect evidence taken from "
            "the ground truth. When the oracle is right and the system wrong, the error is upstream "
            "(extraction). Here all wrong studies are upstream. Caveat to say aloud: the oracle and the generator "
            "share the same rules, so this checks the code path, not whether the rules are a good synthesis.\n\n"
            "The offline regex-only run reproduces EV1's regex-only numbers exactly (F1 0.660, direction 0.273), "
            "which is the replay property in practice.")

    # 9 -------------------------------------------------------------- benchmark + fidelity
    s = D.slide()
    D.title(s, "Your synthetic benchmark (§5, §6): what survives fidelity",
            "Ground truth → papers at five levels → checked against the ground truth → corpus")
    s.shapes.add_picture(str(IMG / "fidelity.png"), Inches(0.6), Inches(1.55), height=Inches(4.15))
    D.text(s, 7.15, 1.6, 5.6, 3.3, [
        [("Checks per paper: ", {"bold": True}), ("every planned value present and tied to its condition; no "
                                                    "extra numbers or claims; a second model "
                                                    "re-reads the paper blind.", {})],
        [("Shared-set rule: ", {"bold": True}), (f"a study failing one level is dropped from all, so every level "
                                                   f"holds the same studies: {retained} of {total} kept.", {})],
        [("The drop shifts the mix: ", {"bold": True}), ("12 / 4 / 4 supporting / neutral / contradicting "
                                                           "planned, 5 / 3 / 3 kept. Now reported as a result.", {})],
        [("Still open: ", {"bold": True, "color": AMBER}), ("the human fidelity review (342 rows, sheet ready).", {})]],
        size=16, spacing=9)
    D.quote(s, 0.6, 5.85, 12.1, 1.05, "The generator’s intended content alone is not sufficient; the final "
            "documents must be checked for unintended additions, omissions, or contradictions.", "Tim, M2 §6",
            size=16)
    D.source(s, "tests/EV1/live-rerun/corpora/rag-llm-s1-*/fidelity.json and corpus.json; drop and mix: tests/EV1/failures.md "
             f"(21 Oct review). Writer {models['renderer'].split('@')[0]}, verifier {models['verifier'].split('@')[0]}.")
    D.notes(s, "Tim §5: 'Ground-truth scientific data → Synthetic papers', and the LLM should not "
            "generate arbitrary papers. The five levels are his §6 list (explicit, paraphrased, distributed, "
            "complex, contradictory); knobs for duplicates, missing values, outliers and irrelevant papers exist.\n\n"
            f"Per level the LLM writer passed {', '.join(str(v[0]) for v in d['fidelity'].values())} of 20; "
            "distributed is hardest. Because of the shared-set rule only 11 studies survive at every level. The "
            "supporting share drops from 60 % to about 45 %, which changes what the benchmark measures, so we "
            "report it.\n\nOpen: the 342-row human review sheet for the 11-paper sample is generated but not "
            "filled. Controlled variants (flip one study, the answer must move): the LLM variant for S002 failed "
            "fidelity in EV1 and is not presented as a result (failures.md).")

    # 10 ------------------------------------------------------------- evaluation
    s = D.slide()
    D.title(s, "A · B · C separately, and the answer-level baseline (§5, §7)",
            "First live run, LLM-written mixed corpus, 11 studies: promising, not conclusive")
    s.shapes.add_picture(str(IMG / "eval.png"), Inches(0.6), Inches(1.5), width=Inches(12.1))
    D.text(s, 0.6, 5.85, 5.6, 1.1, [
        [("A extraction F1: ", {"bold": True}), (f"regex {ev['regex']['f1']}, cascade all {ev['cascade']['f1']}, "
                                                   f"gaps {ev['gaps']['f1']}", {})],
        [("B true pair: ", {"bold": True}), (f"{ev['regex']['true_pair']} / {ev['cascade']['true_pair']} / "
                                               f"{ev['gaps']['true_pair']}", {})],
        [("Cost per paper: ", {"bold": True}), (f"all {float(ev['cascade']['calls']):.0f} calls, "
                                                  f"{float(ev['cascade']['tokens']) / 1000:.1f}k tokens; gaps "
                                                  f"{float(ev['gaps']['calls']):.0f} calls, "
                                                  f"{float(ev['gaps']['tokens']) / 1000:.1f}k", {})]],
        size=15, spacing=3)
    D.quote(s, 6.45, 5.75, 6.3, 1.17, "We should not assume that the evidence-level approach will necessarily "
            "perform better.", "Tim, M2 §7", size=16)
    D.source(s, "EV1, Slurm job 7588, corpus rag-llm-s1-mixed; tests/EV1/live-rerun/scores/compare-*/compare.md; "
             "BCa bootstrap over papers, 2,000 resamples. Agent baseline and cascade/gaps are ours.")
    D.notes(s, f"A = extraction against the planted facts; B = integration (association, true pair); C = per-study "
            f"direction against the computed ground truth. Answer-level baseline per §7: retrieve passages "
            f"and answer directly (RAG baseline); we also ran a research agent (ours).\n\nOne clear result: engine "
            f"minus RAG {ev['rag']['diff']} (paired). Engine minus agent {ev['agent']['diff']}: touches zero, not "
            f"conclusive. Cascade all is right on all 11 studies, so no interval (n/a). The RAG baseline's "
            f"completeness is {ev['rag']['complete']}: it leaves several studies undetermined.\n\nSay plainly: "
            "11 parent studies are a diagnostic set, not a population; direction at 1.0 on most corpora means "
            "the benchmark is too easy to separate good from better. Hence the larger, harder set next. His "
            "line: 'Establishing whether, and under which conditions, it provides an advantage would be an "
            "interesting research result.'")

    # 11 ------------------------------------------------------------- added 21 Oct
    s = D.slide()
    D.title(s, "Added or repaired on 21 October, after the first live run",
            "Each item comes from an EV1 failure we reproduced offline and has a regression test")
    groups = [("Extraction (§3)", False, ["Keyword miss can go on to the LLM screen (ours)",
                                              "“RAG (no retrieval)” is read as the control",
                                              "Tables found by their headers, not column order",
                                              "“75 out of 100” read as 0.75"]),
              ("Protocol proposal (optional, §8)", True, ["Accuracy metrics always bounded to [0, 1]",
                                                               "Blocking checks only a person can waive",
                                                               "Records whether a person or the model decided"]),
              ("Synthetic papers (§5, §6)", False, ["Blind re-read checks condition, metric, dataset, value",
                                                             "Results sentences written and checked one at a time",
                                                             "Dropped papers counted and reported",
                                                             "Harder set: several experiments per paper"]),
              ("Evaluation (§5, §7)", False, ["Perfect-evidence oracle: extraction vs synthesis errors",
                                                       "Intervals over parent studies, with their n",
                                                       "Traceability counted strictly",
                                                       "Template vs LLM papers on the same studies"])]
    for k, (head, ours, items) in enumerate(groups):
        x = 0.6 + (k % 2) * 6.15
        y = 1.6 + (k // 2) * 2.7
        D.box(s, x, y, 5.95, 2.5, fill=PANEL, radius=0.06)
        D.text(s, x + 0.25, y + 0.15, 4.6, 0.45, head, size=20, bold=True, color=TEAL)
        if ours:
            D.tag(s, x + 4.9, y + 0.2)
        D.text(s, x + 0.25, y + 0.68, 5.5, 1.8, ["•  " + t for t in items], size=16, spacing=4)
    D.source(s, "Plan: docs/superpowers/plans/2026-10-21-ev1-repairs.md (workstreams A–E). Not yet merged "
             "to main and not yet run live: that is EV2.")
    D.notes(s, "Tie each block to Tim. Extraction fixes come from EV1 failures we reproduced offline "
            "(tests/EV1/diagnostics). The screen escalation and the cascade are ours. Protocol proposal is the "
            "optional extension (§8) and ours, so keep it short; the important repair is that 175 % "
            "accuracy is now rejected. Synthetic papers: his §6 request that the final documents are "
            "checked; we now report the drop rate instead of hiding it. Evaluation: his §5 C point, "
            "'distinguish extraction errors from synthesis errors', via the oracle (with the shared-rules "
            "caveat).\n\nStatus to say honestly: the changes are on ev3/* branches with offline tests; the "
            "second live run (EV2) has not happened yet.")

    # 12 ------------------------------------------------------------- next + question
    s = D.slide(dark=True)
    D.text(s, 0.6, 0.35, 12.1, 0.8, "Next: the same vertical slice, on a harder benchmark", size=32,
           font=HEAD_FONT, bold=True, color=WHITE)
    D.text(s, 0.6, 1.25, 6.0, 3.2, [
        [("1  ", {"bold": True, "color": "5EEAD4"}), ("EV2 live run on Slurm with the 21 Oct repairs", {})],
        [("2  ", {"bold": True, "color": "5EEAD4"}), ("Larger, harder set: about 100 studies, several experiments "
                                                        "per paper, duplicates, missing values", {})],
        [("3  ", {"bold": True, "color": "5EEAD4"}), ("Human fidelity review of the sample (342 rows)", {})],
        [("4  ", {"bold": True, "color": "5EEAD4"}), ("Real papers kept as the optional extension (§8)", {})]],
        size=19, color=WHITE, spacing=12)
    D.box(s, 6.95, 1.3, 5.8, 2.85, fill="243B53", radius=0.06)
    D.text(s, 7.2, 1.42, 5.3, 0.4, "Question for you", size=18, bold=True, color="FDBA74")
    D.text(s, 7.2, 1.85, 5.35, 2.7, "For the next run I plan a larger and harder synthetic benchmark (about 100 "
           "studies, several experiments per paper, duplicates and missing values) plus the human fidelity check, "
           "and keep real papers as the optional extension you mentioned. Is that the right priority?",
           size=18, color=WHITE)
    D.box(s, 0.6, 4.75, 12.15, 1.7, fill="243B53", radius=0.08)
    D.text(s, 0.8, 4.62, 0.6, 0.7, "“", size=44, font=HEAD_FONT, color="5EEAD4", bold=True)
    D.text(s, 1.35, 4.92, 11.2, 1.0, "For now, I think we should focus on implementing and evaluating a complete "
           "vertical slice of this architecture rather than trying to solve the general problem of automatic "
           "research question operationalization immediately.", size=17, italic=True, color=WHITE)
    D.text(s, 1.35, 5.95, 11.0, 0.35, "Tim, M2 §9", size=13, bold=True, color="5EEAD4")
    D.source(s, "Question text: docs/presentation-runbook.md. Likely questions and short answers are in the notes.",
             dark=True)
    D.notes(s, "Ask the question verbatim, then stop talking.\n\nLikely questions (from the runbook):\n- How do "
            "you know the synthetic papers say what you planned? Deterministic checks plus a blind re-read by a "
            "second model that must return condition, metric, dataset and value; the 342-row human review is "
            "ready but not filled.\n- Is the engine just matching its own generator? Partly: generator truth and "
            "synthesis share the rules file. That is why the oracle is called a code check, and why the harder "
            "set and a human check come next.\n- Why not real papers yet? You made them optional (§8); the "
            "plan keeps them last.\n- What did the LLM cost? Cascade 'all': about 10 calls and 10.6k tokens per "
            "paper; 'gaps': 7 calls and 4.3k tokens, with lower accuracy (EV1, LLM mixed corpus).")

    # 13 ------------------------------------------------------------- appendix
    if have_shot:
        s = D.slide()
        D.title(s, "Appendix: the whole pipeline, and where the work is now",
                "Solid boxes follow your 14 Oct message; dashed boxes are our additions; grey lane is optional")
        pic = s.shapes.add_picture(str(IMG / "pipeline-lanes.png"), Inches(0.6), Inches(1.5), height=Inches(5.4))
        pic.left = int((D.prs.slide_width - pic.width) / 2)
        D.source(s, "Screenshot of thesis_pipeline.html (branch ev3/demo), headless Edge.")
        D.notes(s, "Backup only. Use it if Tim asks how the parts fit or what is ours: dashed outline = our "
                "addition, not in his message; orange = where the work is on 21 Oct (fidelity check, EV2 run "
                "ready but not run). The optional lane (protocol generator, critic, real papers) is his §8 "
                "'if time permits'.")

    D.prs.save(str(OUT))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.2f} MB, {D.n} slides)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, type=Path, help="scratch dir for the offline run")
    ap.add_argument("--prepare", action="store_true", help="copy the EV1 LLM corpus and run engine, oracle, score")
    ap.add_argument("--project-python", default=str(REPO / ".venv" / "Scripts" / "python.exe"))
    ap.add_argument("--screenshot", type=Path, default=None, help="PNG of thesis_pipeline.html")
    a = ap.parse_args()
    if a.prepare:
        prepare(a.work, a.project_python)
    d = load(a.work)
    IMG.mkdir(exist_ok=True)
    img_strip(None, IMG / "stage-none.png")
    for k in range(len(STAGES)):
        img_strip(k, IMG / f"stage-{k}.png")
    img_compiler(IMG / "compiler.png")
    img_graph(d, IMG / "graph.png")
    img_fidelity(d, IMG / "fidelity.png")
    img_eval(eval_numbers(d), IMG / "eval.png")
    have = img_screenshot(a.screenshot, IMG / "pipeline-lanes.png") if a.screenshot else (IMG / "pipeline-lanes.png").exists()
    build(d, have)
    return 0


if __name__ == "__main__":
    sys.exit(main())
