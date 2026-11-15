"""Full template run: every corpus of a synth2 grid as renamed real papers with a code-written planted section.

Per corpus (`run_corpus`): study inputs from the grid's ground truth (`study_inputs`), one screened real source per
study whose own leftover results agree with the study's claim (`assign`), then realedit.prepare (rename),
templedit.write_edits, realedit.apply_study with the claim rules, and written.assemble into a corpus folder.
`run_all` does this for every corpus under a grid root, in parallel, and skips corpora already written.

The source pool is {paper id: claims it may carry}: a paper with no retrieval-vs-no-retrieval result left (screen.py)
may carry any claim; one whose leftover results all say "helps" only a "helps" claim, and so on.
"""
from __future__ import annotations

import hashlib
import json
import random
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import yaml

from synth2 import realedit, templedit
from synth2.written import assemble

TREAT = ["RAG", "the RAG pipeline", "the retrieval-augmented LLM", "retrieve-then-read"]
CTRL = ["the closed-book LLM", "the no-retrieval baseline", "the vanilla LLM", "the parametric-only LLM"]


def _draw(key: str, n: int) -> int:
    return int.from_bytes(hashlib.sha256(f"synth2-full:{key}".encode()).digest()[:4], "big") % n


def study_inputs(grid: Path, recipe: dict, phrases: dict) -> dict[str, dict]:
    """{study id: input} for one grid corpus: counts per cell with a seeded other wording per level, the claim
    sentence of the grid paper's abstract, and seeded system names."""
    truth = json.loads((grid / "ground_truth.json").read_text(encoding="utf-8"))
    cond = {c["id"]: c for c in truth["conditions"]}
    name_of = {lv["id"]: lv["name"] for c in truth["conditions"] for lv in c["levels"]}
    out = {}
    for s in truth["studies"]:
        sid, key = s["id"], f"{truth['corpus_id']}:{s['id']}"
        text = (grid / "papers" / f"{sid}.md").read_text(encoding="utf-8")
        place = next(p for p in truth["placements"] if p["paper"] == sid and p["fact"].endswith("claim.abstract"))
        cells = [{"levels": [{"condition": cond[cid]["name"], "name": name_of[lv],
                              "suggested": phrases[cid][lv][_draw(f"{key}:{lv}", len(phrases[cid][lv]))]}
                             for cid, lv in c["levels"].items()],
                  "treatment_correct": c["k_t"], "treatment_total": c["n_t"],
                  "control_correct": c["k_c"], "control_total": c["n_c"]} for c in s["cells"]]
        out[sid] = {"label": s["label"],
                    "treatment": {"name": recipe["treatment"]["label"],
                                  "description": recipe["treatment"]["description"]},
                    "control": {"name": recipe["control"]["label"], "description": recipe["control"]["description"]},
                    "system_names": {"treatment": TREAT[_draw(f"{key}:t", len(TREAT))],
                                     "control": CTRL[_draw(f"{key}:c", len(CTRL))]},
                    "benchmark": s["dataset"],
                    "metric": f"{recipe['metric']} (number of {recipe['unit']} answered correctly)",
                    "claim_sentence": text[place["start"]:place["end"]], "cells": cells}
    return out


def assign(claims: dict[str, str], pool: dict[str, set[str]], seed: str) -> tuple[dict[str, str], list[str]]:
    """({study: source}, studies that share a source with an earlier study). Each study gets a source that allows
    its claim; the studies with the fewest allowed sources choose first, each takes an unused source if there is
    one, and the most restricted such source (so sources that allow every claim stay free). Ties are seeded."""
    rnd = random.Random(f"synth2-full-assign:{seed}")
    order = sorted(pool)
    rnd.shuffle(order)
    rank = {p: i for i, p in enumerate(order)}
    used: Counter = Counter()
    got, shared = {}, []

    def allowed(claim: str) -> list[str]:
        return [p for p in pool if claim in pool[p]]

    for sid in sorted(claims, key=lambda s: (len(allowed(claims[s])), s)):
        cands = allowed(claims[sid])
        if not cands:
            raise ValueError(f"{sid}: no source allows a '{claims[sid]}' claim")
        p = min(cands, key=lambda q: (used[q], len(pool[q]), rank[q]))
        if used[p]:
            shared.append(sid)
        used[p] += 1
        got[sid] = p
    return dict(sorted(got.items())), sorted(shared)


def _redraw(work: Path, grid: Path, sid: str, key: str) -> dict:
    """Retry a study that fails the checks with the other system-name pairs, in a seeded order: a template line
    such as "{T} and {C}" can repeat four words of the grid's claim sentence. Returns the last apply result."""
    path = work / "inputs" / f"{sid}.json"
    inp = json.loads(path.read_text(encoding="utf-8"))
    pairs = [(t, c) for t in TREAT for c in CTRL
             if {"treatment": t, "control": c} != inp["system_names"]]
    random.Random(f"synth2-full-names:{key}").shuffle(pairs)
    r: dict = {}
    for t, c in pairs:
        inp["system_names"] = {"treatment": t, "control": c}
        path.write_text(json.dumps(inp, indent=1, ensure_ascii=False), encoding="utf-8")
        templedit.write_edits(work, grid, [sid])
        r = realedit.apply_study(work, sid, claim_rules=True)
        if not r["problems"]:
            break
    return r


def load_extras(path: Path) -> dict[str, list[dict]]:
    """The hand list of known extras. YAML reads an unquoted id such as 2305.14251 as a number, which would match no
    source (and could lose a trailing zero), so every id must be a quoted string."""
    extras = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    bad = [k for k in extras if not isinstance(k, str)]
    if bad:
        raise ValueError(f"{path}: quote the paper id(s) {bad} so YAML reads them as text")
    return extras


def known_extras(work: Path, sources: dict[str, str], full: Path, extras: dict[str, list[dict]]) -> list[dict]:
    """The real results about retrieval vs none that stay in each built paper, from a hand list
    {source id: [{id, quote, direction}]}: each quote renamed with that paper's map, kept only if the edits left it
    in the paper. A system that reports one is not wrong, though it is not a planted study. A quote missing from its
    source is an error in the list."""
    found = []
    for sid, src in sorted(sources.items()):
        items = extras.get(src) or []
        if not items:
            continue
        source = (full / f"{src}.md").read_text(encoding="utf-8")
        mapping = json.loads((work / "maps" / f"{sid}.json").read_text(encoding="utf-8"))["map"]
        paper = (work / "papers" / f"{sid}.md").read_text(encoding="utf-8")
        for e in items:
            if e["quote"] not in source:
                raise ValueError(f"known extra {e['id']}: quote not in source {src}")
            text = realedit.apply_map(e["quote"], mapping, "")
            if text in paper:
                found.append({"study": sid, "id": e["id"], "direction": e["direction"], "text": text})
    return found


def run_corpus(grid: Path, work: Path, out: Path, pool: dict[str, set[str]], full: Path, recipe: dict,
               phrases: dict, extras: dict[str, list[dict]] | None = None) -> dict:
    """Build one corpus. Work files go to `work` (inputs, renamed sources, maps, edits, papers, run.json); the
    corpus goes to `out` only when every paper passes the code checks, its ground truth with the `known_extras`
    left in the papers. Returns the run summary."""
    truth = json.loads((grid / "ground_truth.json").read_text(encoding="utf-8"))
    inputs = study_inputs(grid, recipe, phrases)
    claim_of = {s["id"]: s["claim"] for s in truth["studies"]}
    got, shared = assign(claim_of, pool, truth["corpus_id"])
    assigned = work / "inputs-assigned"
    assigned.mkdir(parents=True, exist_ok=True)
    for sid, inp in inputs.items():
        (assigned / f"{sid}.json").write_text(json.dumps(
            {**inp, "skeleton_source": str((full / f"{got[sid]}.md").resolve())}, indent=1, ensure_ascii=False),
            encoding="utf-8")
    realedit.prepare(assigned, work)
    templedit.write_edits(work, grid)
    studies = {}
    for sid in sorted(inputs):
        r = realedit.apply_study(work, sid, claim_rules=True)
        redrawn = bool(r["problems"])
        if redrawn:
            r = _redraw(work, grid, sid, f"{truth['corpus_id']}:{sid}")
        studies[sid] = {"source": got[sid], "claim": claim_of[sid], "redrawn": redrawn, **r}
    ok = all(not r["problems"] for r in studies.values())
    if ok:
        found = known_extras(work, got, full, extras or {})
        assemble(grid, work / "papers", out)
        gt = json.loads((out / "ground_truth.json").read_text(encoding="utf-8"))
        (out / "ground_truth.json").write_text(json.dumps({**gt, "known_extras": found}, indent=2,
                                                          ensure_ascii=False), encoding="utf-8")
    summary = {"corpus_id": truth["corpus_id"], "grid": str(grid), "assembled": ok, "shared": shared,
               "studies": studies}
    (work / "run.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return summary


def _one(args: tuple) -> dict:
    grid, work, out, pool, full, recipe, phrases, extras = args
    try:
        s = run_corpus(grid, work, out, pool, full, recipe, phrases, extras)
        bad = {k: v["problems"] for k, v in s["studies"].items() if v["problems"]}
        return {"corpus": str(out), "assembled": s["assembled"], "studies": len(s["studies"]),
                "shared": s["shared"], "problems": bad}
    except Exception as err:  # noqa: BLE001  one broken corpus must not stop the run; it is reported
        return {"corpus": str(out), "assembled": False, "error": f"{err!r}", "trace": traceback.format_exc()[-800:]}


def run_all(grid_root: Path, out_root: Path, work_root: Path, pool: dict[str, set[str]], full: Path,
            recipe_path: Path, phrases_path: Path, jobs: int = 4, only: list[str] | None = None,
            extras_path: Path | None = None) -> dict:
    """run_corpus for every <family>/<seed>/<variant> under grid_root (or the relative paths in `only`); a corpus
    whose out folder already has a ground truth is skipped. Both roots get a .gitignore of "*" (the papers are
    built from real papers and stay local). `extras_path` is the hand list of known extras (YAML, kept local: it
    quotes real papers). Writes and returns <out_root>/run-summary.json."""
    recipe = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    phrases = yaml.safe_load(phrases_path.read_text(encoding="utf-8"))
    extras = load_extras(extras_path) if extras_path else {}
    for root in (out_root, work_root):
        root.mkdir(parents=True, exist_ok=True)
        (root / ".gitignore").write_text("*\n", encoding="utf-8")
    rels = only or sorted(str(g.parent.relative_to(grid_root)).replace("\\", "/")
                          for g in grid_root.glob("*/s*/*/ground_truth.json"))
    todo = [r for r in rels if not (out_root / r / "ground_truth.json").is_file()]
    results = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(_one, (grid_root / r, work_root / r, out_root / r, pool, full, recipe, phrases, extras))
                for r in todo]
        for k, f in enumerate(as_completed(futs), 1):
            results.append(f.result())
            if k % 25 == 0 or k == len(futs):
                print(f"{k}/{len(futs)} corpora", flush=True)
    summary = {"corpora": len(rels), "skipped": len(rels) - len(todo),
               "assembled": sum(r["assembled"] for r in results),
               "failed": sorted((r for r in results if not r["assembled"]), key=lambda r: r["corpus"]),
               "shared_studies": sum(len(r.get("shared", [])) for r in results)}
    (out_root / "run-summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary
