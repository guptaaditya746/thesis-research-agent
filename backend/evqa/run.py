"""Run orchestrator: one RunConfig -> runs/evqa/<run_id>/ with spec, find, rows and answer per question.

    from evqa.run import run
    run(RunConfig.load(Path("configs/evqa/slice1-qwen.yaml")))      # CLI: evqa run --config X.yaml

Per question the steps spec, find, extract, link, answer run in order; each writes its file (contracts.py docstring;
Extract also writes settings.jsonl, its setting-reading audit; link writes links.jsonl, extract/links.py) and logs a start and an end
Event (seconds, output count, LLM requests / real calls / cache hits) to events.jsonl. A step whose output file
exists is skipped, so a rerun resumes; after a step that ran, the later steps run again. A failing step logs a "problem" Event and stops that question only.
Questions run in a pool of QUESTION_WORKERS; LLM calls are capped at 3 at once (EVQA_MAX_CALLS) by evqa.lm anyway.
closed_book: Find is not called (no papers) and Extract is skipped, so Answer says "not reported".
manifest.json (written on first start): git commit, dirty flag and a hash of the code (evqa + modelcall sources,
tests left out). A resume whose code hash differs stops with an error, unless EVQA_ALLOW_CODE_CHANGE=1 (then an
info Event "code changed" is logged): a run's outputs should all come from the same code.
Progress: one line on stderr per finished question, e.g. `[12/78] Q-med-05 ok 34.2s  eta 41m` (or
`problem: <error type>`); EVQA_QUIET=1 turns it off. events.jsonl stays as it is.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from evqa import corpus, lm
from evqa.contracts import Answer, Event, FindHit, Link, Row, RunConfig, Spec, read_jsonl
from evqa.llm import MAX_WORKERS
from evqa.paths import REPO

ROOT = REPO / "runs" / "evqa"
CODE_DIRS = [Path(__file__).resolve().parent, Path(__file__).resolve().parents[1] / "modelcall"]
QUESTION_WORKERS = MAX_WORKERS     # 3 unless EVQA_MAX_CALLS is set
_event_lock = threading.Lock()


def _step(name: str):
    """The step function `evqa.<name>.run`, imported when first needed (the steps live in their own packages)."""
    return importlib.import_module(f"evqa.{name}").run


def _write_atomic(path: Path, text: str) -> None:
    """Write via a temp file and rename, so a killed run never leaves a half file that resume would take as done."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _dump(path: Path, out: BaseModel | list[BaseModel]) -> None:
    if isinstance(out, list):
        _write_atomic(path, "".join(m.model_dump_json() + "\n" for m in out))
    else:
        _write_atomic(path, out.model_dump_json(indent=2) + "\n")


def code_hash(dirs: list[Path] = CODE_DIRS) -> str:
    """sha256 over the path and text of every .py file under `dirs` (the prompts and signature docstrings are in
    them), tests left out."""
    h = hashlib.sha256()
    for d in dirs:
        for f in sorted(d.rglob("*.py")):
            rel = f.relative_to(d)
            if "tests" in rel.parts or "__pycache__" in rel.parts:
                continue
            h.update(f"{d.name}/{rel.as_posix()}\n".encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def _git(*args: str) -> str | None:
    """Output of a git command in the repo, or None when git is missing or fails (no repo, shallow clone)."""
    try:
        done = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip()


def manifest() -> dict[str, Any]:
    status = _git("status", "--porcelain")
    return {"git_sha": _git("rev-parse", "HEAD") or None, "git_dirty": None if status is None else bool(status),
            "code_hash": code_hash()}


def check_manifest(out: Path, events: "Events") -> None:
    """Write <run>/manifest.json on first start; on resume refuse changed code (module doc)."""
    path, now = out / "manifest.json", manifest()
    if not path.is_file():
        _write_atomic(path, json.dumps(now, indent=2) + "\n")
        return
    old = json.loads(path.read_text(encoding="utf-8"))
    if old.get("code_hash") == now["code_hash"]:
        return
    if os.environ.get("EVQA_ALLOW_CODE_CHANGE") != "1":
        raise RuntimeError(f"{out.name}: the code changed since this run started (code hash {old.get('code_hash')} "
                           f"-> {now['code_hash']}). Start a new run, or set EVQA_ALLOW_CODE_CHANGE=1 to resume anyway.")
    events.log("run", "info", message="code changed", old=old, new=now)


class Events:
    def __init__(self, path: Path) -> None:
        self.path = path

    def log(self, step: str, kind: str, qid: str | None = None, **data: Any) -> None:
        line = Event(ts=time.time(), qid=qid, step=step, kind=kind, data=data).model_dump_json() + "\n"
        with _event_lock, self.path.open("a", encoding="utf-8") as fh:
            fh.write(line)


class Progress:
    """Prints one line on stderr per finished question. The time left is a plain guess: seconds so far / questions
    done x questions left (the pool size is already inside the seconds so far)."""

    def __init__(self, total: int, out=None, clock=time.monotonic) -> None:
        self.total, self.done, self.clock = total, 0, clock
        self.out = out if out is not None else sys.stderr
        self.quiet = os.environ.get("EVQA_QUIET") == "1"
        self.t0 = clock()
        self._lock = threading.Lock()

    def finished(self, qid: str, seconds: float, problem: str | None = None) -> None:
        with self._lock:
            self.done += 1
            if self.quiet:
                return
            left = self.total - self.done
            eta = (self.clock() - self.t0) / self.done * left
            status = f"problem: {problem}" if problem else "ok"
            print(f"[{self.done}/{self.total}] {qid} {status} {seconds:.1f}s  eta {_minutes(eta)}",
                  file=self.out, flush=True)


def _minutes(seconds: float) -> str:
    """Time left in short words: 45s, 41m, 2h05m."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    m = round(seconds / 60)
    return f"{m}m" if m < 60 else f"{m // 60}h{m % 60:02d}m"


def _do(step: str, qid: str, path: Path, events: Events, fn, load, redo: list[bool]):
    """Run one step unless its output exists; returns the output (loaded from disk when skipped). Once a step has
    run, every later step of the question runs again too (`redo`), so no output is built on a stale input."""
    if path.is_file() and not redo[0]:
        events.log(step, "info", qid, skipped=True, file=path.name)
        return load(path)
    redo[0] = True
    events.log(step, "start", qid)
    t0 = time.monotonic()
    with lm.counting(f"{qid}/{step}") as counts:
        out = fn()
    _dump(path, out)
    events.log(step, "end", qid, seconds=round(time.monotonic() - t0, 3),
               count=len(out) if isinstance(out, list) else 1, llm=dict(counts))
    return out


def run_question(q: dict[str, Any], cfg: RunConfig, qdir: Path, events: Events,
                 progress: Progress | None = None) -> bool:
    """The four steps for one question. True when answer.json exists at the end. The steps see only the
    pipeline-facing part of the record (corpus.pipeline_record: qid, question, intent card answers)."""
    q = corpus.pipeline_record(q)
    qid, redo, t0 = q["qid"], [False], time.monotonic()
    try:
        spec = _do("spec", qid, qdir / "spec.json", events,
                   lambda: _step("spec")(q, cfg), lambda p: Spec.model_validate_json(p.read_text(encoding="utf-8")), redo)
        if cfg.closed_book:
            hits = _do("find", qid, qdir / "find.jsonl", events, list, lambda p: read_jsonl(p, FindHit), redo)
        else:
            hits = _do("find", qid, qdir / "find.jsonl", events,
                       lambda: _step("find")(spec, cfg.domain, cfg), lambda p: read_jsonl(p, FindHit), redo)
        audit: list[dict] = []
        rows = _do("extract", qid, qdir / "rows.jsonl", events,
                   lambda: _step("extract")(spec, hits, cfg.domain, cfg, audit=audit) if hits else [],
                   lambda p: read_jsonl(p, Row), redo)
        if audit:   # every candidate setting set and failed check (extract ran this time)
            _write_atomic(qdir / "settings.jsonl", "".join(json.dumps(a, ensure_ascii=False) + "\n" for a in audit))
        links = _do("link", qid, qdir / "links.jsonl", events,
                    lambda: _step("extract.links")(spec, rows, cfg) if rows else [],
                    lambda p: read_jsonl(p, Link), redo)
        _do("answer", qid, qdir / "answer.json", events,
            lambda: _step("answer")(spec, rows, links),
            lambda p: Answer.model_validate_json(p.read_text(encoding="utf-8")), redo)
    except Exception as e:   # noqa: BLE001 - one question's failure must not stop the others
        events.log("run", "problem", qid, error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-4000:])
        if progress:
            progress.finished(qid, time.monotonic() - t0, problem=type(e).__name__)
        return False
    if progress:
        progress.finished(qid, time.monotonic() - t0)
    return True


def run(cfg: RunConfig, *, root: Path = ROOT) -> Path:
    """Run every question of the config (resumable) and return the run folder runs/evqa/<run_id>/."""
    out = root / cfg.run_id()
    out.mkdir(parents=True, exist_ok=True)
    conf = out / "config.yaml"
    text = yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
    if not conf.is_file():
        _write_atomic(conf, text)
    events = Events(out / "events.jsonl")
    check_manifest(out, events)
    questions = corpus.questions(cfg.domain, cfg.split)
    if cfg.questions:
        unknown = set(cfg.questions) - {q["qid"] for q in questions}
        if unknown:
            raise ValueError(f"questions not in {cfg.domain}/{cfg.split}: {sorted(unknown)}")
        questions = [q for q in questions if q["qid"] in cfg.questions]
    events.log("run", "start", run_id=cfg.run_id(), questions=[q["qid"] for q in questions])
    t0, progress = time.monotonic(), Progress(len(questions))
    with ThreadPoolExecutor(QUESTION_WORKERS) as pool:
        done = list(pool.map(lambda q: run_question(q, cfg, out / q["qid"], events, progress), questions))
    events.log("run", "end", seconds=round(time.monotonic() - t0, 3), questions=len(questions),
               answered=sum(done), failed=[q["qid"] for q, ok in zip(questions, done, strict=True) if not ok])
    return out


# ---------------------------------------------------------------- CLI hook (wire into evqa/cli.py)
def add_cli(sub: argparse._SubParsersAction) -> None:
    """Adds `evqa run --config X.yaml`."""
    p = sub.add_parser("run", help="run the QA pipeline on a config (resumable)")
    p.add_argument("--config", type=Path, required=True)
    p.set_defaults(fn=cli_run)


def cli_run(a: argparse.Namespace) -> int:
    folder = run(RunConfig.load(a.config), root=ROOT)
    end = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()
           if line.strip()][-1]
    print(f"{folder}\n{json.dumps(end.get('data', {}))}")
    return 0 if not end.get("data", {}).get("failed") else 1
