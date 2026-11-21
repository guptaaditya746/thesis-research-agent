"""/api/evqa/runs: the Workbench runs pane. Read-only over runs/evqa/<run_id>/ (contracts in evqa/contracts.py).

    GET /api/evqa/runs             every run folder: run_id, config name, system (evqa or a baseline such as
                                   paperqa2-rag, evqa/baselines), mtime, has eval.json
    GET /api/evqa/runs/{run_id}    config, per question spec/find/rows/answer (evqa) or find/answer_text (baseline),
                                   claims (`evqa eval --text`), events tail, eval.json if present;
                                   for a hold-out run (evqa/holdout.py) only config, run-level events and eval totals,
                                   with `closed` saying why (otherwise null)
    GET /api/evqa/runs/{run_id}/graph/{qid}   the question's rows drawn inside its piece of the seed graph
                                   (Cytoscape elements, evqa/eval/qgraph.py); 404 for an unknown run or question,
                                   403 for a hold-out run
    GET /api/evqa/runs/{run_id}/explain/{qid} why each true fact is right or wrong (evqa/explain.py, data form);
                                   403 for a run that is not a practice run (bench-*, holdout-*, split != practice);
                                   409 for a baseline run (no evqa steps to explain)

A run_id must name an existing direct child folder of RUNS_ROOT (no paths, no dots); files are read as JSON, never
validated, so a half-written run still shows. Mount with `app.include_router(router, prefix="/api")`.
"""
from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException

from evqa import explain as evqa_explain
from evqa import holdout
from evqa.eval import qgraph
from evqa.paths import REPO

RUNS_ROOT = REPO / "runs" / "evqa"      # module variable so tests can monkeypatch it
EVENTS_TAIL = 200
QFILES = ("spec.json", "answer.json", "answer_text.json", "claims.json")   # absent file -> null
NOT_QUESTIONS = ("baseline",)   # run sub-folders that are not questions (a baseline system's own files)
BASELINE_SYSTEMS = ("paperqa2-rag", "paperqa2-agent", "long-context")   # evqa/contracts.py BASELINE_SYSTEMS
QLINES = ("find.jsonl", "rows.jsonl")
QID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$")
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$")

router = APIRouter(prefix="/evqa")


def _config(run: Path) -> dict[str, Any]:
    p = run / "config.yaml"
    if not p.is_file():
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {"_error": "config.yaml is not valid YAML"}
    return data if isinstance(data, dict) else {}


def _json(p: Path) -> Any:
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_error": f"{p.name} is not valid JSON"}


def _lines(p: Path, tail: int | None = None) -> list[Any]:
    if not p.is_file():
        return []
    with p.open(encoding="utf-8") as fh:
        raw = deque(fh, maxlen=tail) if tail else list(fh)
    out = []
    for line in raw:
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                out.append({"_error": "line is not valid JSON"})
    return out


def _run(run_id: str) -> Path:
    root = Path(RUNS_ROOT)
    if not RUN_ID.match(run_id) or ".." in run_id:
        raise HTTPException(404, f"no run {run_id!r}")
    path = root / run_id
    if not (path.is_dir() and not path.is_symlink() and path.resolve().parent == root.resolve()):
        raise HTTPException(404, f"no run {run_id!r}")
    return path


def _open(run: Path) -> None:
    """403 for a hold-out run: its per-question outputs stay closed (score only)."""
    why = holdout.run_closed(_config(run), run.name)
    if why:
        raise HTTPException(403, why)


@router.get("/runs")
def runs() -> list[dict[str, Any]]:
    root = Path(RUNS_ROOT)
    if not root.is_dir():
        return []
    out = []
    for d in root.iterdir():
        if not d.is_dir() or d.is_symlink() or not RUN_ID.match(d.name):
            continue
        cfg = _config(d)
        out.append({"run_id": d.name, "name": cfg.get("name"), "domain": cfg.get("domain"),
                    "system": cfg.get("system") or "evqa",
                    "closed_book": bool(cfg.get("closed_book", False)), "mtime": d.stat().st_mtime,
                    "has_eval": (d / "eval.json").is_file()})
    return sorted(out, key=lambda r: r["mtime"], reverse=True)


@router.get("/runs/{run_id}")
def run(run_id: str) -> dict[str, Any]:
    d = _run(run_id)
    cfg, ev = _config(d), _json(d / "eval.json")
    closed = holdout.run_closed(cfg, d.name)
    if closed:   # totals only: no question folders, no per-question events or scores
        if isinstance(ev, dict):
            ev = {**ev, "questions": {}}
        events = [e for e in _lines(d / "events.jsonl") if isinstance(e, dict) and not e.get("qid")][-EVENTS_TAIL:]
        return {"run_id": d.name, "config": cfg, "questions": {}, "events": events, "eval": ev, "closed": closed}
    questions = {}
    for q in sorted(p for p in d.iterdir() if p.is_dir() and not p.is_symlink() and p.name not in NOT_QUESTIONS):
        item: dict[str, Any] = {f.split(".")[0]: _json(q / f) for f in QFILES}
        item.update({f.split(".")[0]: _lines(q / f) for f in QLINES})
        questions[q.name] = item
    return {"run_id": d.name, "config": cfg, "questions": questions,
            "events": _lines(d / "events.jsonl", EVENTS_TAIL), "eval": ev, "closed": None}


@router.get("/runs/{run_id}/graph/{qid}")
def graph(run_id: str, qid: str) -> dict[str, Any]:
    d = _run(run_id)
    _open(d)
    if not QID.match(qid):
        raise HTTPException(404, f"no question {qid!r}")
    cfg = _config(d)
    domain = cfg.get("domain") if isinstance(cfg.get("domain"), str) and cfg["domain"].isidentifier() else "medical"
    try:
        return qgraph.question_graph(d, qid, domain)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(404, f"no true answer for {qid!r} in the {domain} seed") from exc


@router.get("/runs/{run_id}/explain/{qid}")
def explain(run_id: str, qid: str) -> dict[str, Any]:
    d = _run(run_id)
    _open(d)
    if not QID.match(qid):
        raise HTTPException(404, f"no question {qid!r}")
    if _config(d).get("system") in BASELINE_SYSTEMS:
        raise HTTPException(409, "a baseline run has no evqa steps to explain; see its answer_text and claims")
    try:
        return evqa_explain.explain_data(d, qid)
    except evqa_explain.Refused as exc:
        raise HTTPException(403, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
