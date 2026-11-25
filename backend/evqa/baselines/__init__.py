"""Baseline answering systems (PaperQA2, long context) run on the same questions, papers and model as evqa, so
`evqa compare` can put them side by side. The systems live in the thesis-baselines repo (submodule `baselines/`,
own uv environment); this module only calls it and turns its output into evqa run files.

    evqa run --config configs/evqa/practice-pqa-rag.yaml     (RunConfig.system: paperqa2-rag | paperqa2-agent |
                                                              long-context; RunConfig.baseline.settings)

Run folder runs/evqa/<run_id>/ (same layout as an evqa run, see contracts.py):
  baseline/questions.jsonl   the questions handed to the system: corpus.questions (qid, question, intent card
                             answers), nothing else, the same records evqa's steps see
  baseline/answers/<qid>.json, baseline/run_info.json   the system's raw output (thesis-baselines contract.py)
  <qid>/find.jsonl           one FindHit per paper the system read: each chunk located in paper.md (exact text,
                             so offsets are exact; a chunk not found is kept with start = end = -1 and counted);
                             an empty chunk text means the whole paper (long context). Gives prism its L1.
  <qid>/answer_text.json     TextAnswer: the answer text, cannot-answer flag, citations, tokens
  events.jsonl               per question a "find" and an "answer" end event: seconds and tokens of the system
                             (the whole question's tokens go on "answer"), so `evqa compare` shows cost
There is no spec/rows/answer.json: the structured layers (L2, structured L3, advisor) are n/a for a baseline.
The comparable answer score is L3-text (`evqa eval --text`, thesis_scorer.text), made the same way for evqa runs.

Pipeline rule: this module reads only the dataset folder (corpus.py), never the seed (seed wall test).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from evqa import corpus
from evqa.contracts import FindHit, Passage, RunConfig, TextAnswer
from evqa.paths import DATASET, REPO

BASELINES_DIR = Path(os.environ.get("EVQA_BASELINES_DIR") or REPO / "baselines")


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def command(cfg: RunConfig, out: Path, baselines_dir: Path = BASELINES_DIR) -> list[str]:
    """The thesis-baselines command for this config (run inside baselines_dir, its own uv environment)."""
    settings = {"model": cfg.llm.model, "think": cfg.llm.think, **(cfg.baseline.settings if cfg.baseline else {})}
    return ["uv", "run", "--locked", "--project", str(baselines_dir), "python", "-m", "thesis_baselines", "run",
            "--system", str(cfg.system), "--questions", str(out / "baseline" / "questions.jsonl"),
            "--papers", str(DATASET / cfg.domain), "--out", str(out / "baseline"),
            "--settings", json.dumps(settings, sort_keys=True)]


def baseline_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """The environment of the thesis-baselines command. A shared UV_PROJECT_ENVIRONMENT (ops/local-venv.sh puts
    evqa's venv in /tmp) gets a "-baselines" twin: else `uv run --project baselines` syncs the baselines' packages
    into evqa's venv and uninstalls evqa's own while evqa runs (24 Nov 2026)."""
    env = dict(os.environ if env is None else env)
    env.pop("VIRTUAL_ENV", None)
    if env.get("UV_PROJECT_ENVIRONMENT"):
        env["UV_PROJECT_ENVIRONMENT"] = env["UV_PROJECT_ENVIRONMENT"].rstrip("/") + "-baselines"
    return env


def locate(chunk: str, paper: str) -> tuple[int, int]:
    """[start, end) of the chunk in the paper text; the whole paper for an empty chunk; (-1, -1) when not found."""
    if not chunk:
        return 0, len(paper)
    i = paper.find(chunk)
    if i >= 0:
        return i, i + len(chunk)
    stripped = chunk.strip()
    i = paper.find(stripped) if stripped else -1
    return (i, i + len(stripped)) if i >= 0 else (-1, -1)


def find_hits(raw: dict[str, Any], papers: dict[str, str]) -> tuple[list[FindHit], int]:
    """FindHits (one per paper, in reading order) from the system's contexts; also the count of chunks not found."""
    hits: dict[str, FindHit] = {}
    missing = 0
    for c in raw.get("contexts") or []:
        pid = str(c.get("paper", ""))
        text = papers.get(pid)
        if text is None:
            missing += 1
            continue
        start, end = locate(str(c.get("text", "")), text)
        missing += start < 0
        hit = hits.setdefault(pid, FindHit(paper=pid, sources=[], screen="yes",
                                           details={"system": raw.get("system"), "chunks": 0}))
        hit.details["chunks"] += 1
        if start >= 0 and any(p.start == start and p.end == end for p in hit.passages):
            continue                                       # the same chunk read twice
        hit.passages.append(Passage(start=start, end=end, text=text[start:end] if start >= 0 else c.get("text", ""),
                                    quote=str(c.get("summary", ""))[:500]))
    return list(hits.values()), missing


def import_answers(cfg: RunConfig, out: Path, events: Any) -> dict[str, int]:
    """Turn baseline/answers/<qid>.json into <qid>/find.jsonl and <qid>/answer_text.json (module doc)."""
    papers = corpus.papers(cfg.domain)
    counts = {"imported": 0, "system_failed": 0, "not_answered": 0}
    for q in read_questions(out):
        qid = q["qid"]
        raw_path = out / "baseline" / "answers" / f"{qid}.json"
        if not raw_path.is_file():
            counts["not_answered"] += 1
            continue
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        if raw.get("error"):
            counts["system_failed"] += 1
            events.log("run", "problem", qid, error=raw["error"], system=cfg.system)
            continue
        hits, not_found = find_hits(raw, papers)
        qdir = out / qid
        _write_atomic(qdir / "find.jsonl", "".join(h.model_dump_json() + "\n" for h in hits))
        tokens = raw.get("tokens") or {}
        ta = TextAnswer(qid=qid, system=str(raw.get("system")), text=str(raw.get("answer", "")),
                        cannot_answer=bool(raw.get("cannot_answer")), citations=list(raw.get("citations") or []),
                        tokens={k: int(tokens.get(k) or 0) for k in ("prompt", "completion")},
                        seconds=float(raw.get("seconds") or 0.0))
        _write_atomic(qdir / "answer_text.json", ta.model_dump_json(indent=2) + "\n")
        events.log("find", "end", qid, seconds=0.0, count=len(hits), chunks_not_found=not_found,
                   llm={"requests": 0, "calls": 0, "cache_hits": 0})
        events.log("answer", "end", qid, seconds=ta.seconds, count=1,
                   llm={"requests": 1, "calls": 1, "cache_hits": 0, "prompt_tokens": ta.tokens["prompt"],
                        "completion_tokens": ta.tokens["completion"]})
        counts["imported"] += 1
    return counts


def read_questions(out: Path) -> list[dict[str, Any]]:
    path = out / "baseline" / "questions.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(cfg: RunConfig, root: Path, baselines_dir: Path = BASELINES_DIR, runner=subprocess.run) -> Path:
    """Run the baseline system on the config's questions (resumable: the system skips answered questions), then
    import its answers. Returns the run folder. `runner` is subprocess.run (tests pass a fake)."""
    from evqa.run import Events, check_manifest   # run.py dispatches here; imported late to avoid a cycle
    if not cfg.is_baseline():
        raise ValueError(f"{cfg.name}: not a baseline config (system {cfg.system!r})")
    out = root / cfg.run_id()
    out.mkdir(parents=True, exist_ok=True)
    conf = out / "config.yaml"
    if not conf.is_file():
        _write_atomic(conf, yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False, allow_unicode=True))
    events = Events(out / "events.jsonl")
    check_manifest(out, events, cfg)
    questions = corpus.questions(cfg.domain, cfg.split)
    if cfg.questions:
        unknown = set(cfg.questions) - {q["qid"] for q in questions}
        if unknown:
            raise ValueError(f"questions not in {cfg.domain}/{cfg.split}: {sorted(unknown)}")
        questions = [q for q in questions if q["qid"] in cfg.questions]
    _write_atomic(out / "baseline" / "questions.jsonl",
                  "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in questions))
    if not (baselines_dir / "thesis_baselines").is_dir():
        raise FileNotFoundError(f"{baselines_dir} has no thesis_baselines package: run "
                                "`git submodule update --init baselines` (or set EVQA_BASELINES_DIR)")
    cmd = command(cfg, out, baselines_dir)
    events.log("run", "start", run_id=cfg.run_id(), system=cfg.system, questions=[q["qid"] for q in questions],
               command=cmd)
    t0 = time.monotonic()
    proc = runner(cmd, cwd=baselines_dir, stdout=sys.stdout, stderr=sys.stderr, check=False, env=baseline_env())
    counts = import_answers(cfg, out, events)
    failed = [q["qid"] for q in questions if not (out / q["qid"] / "answer_text.json").is_file()]
    events.log("run", "end", seconds=round(time.monotonic() - t0, 3), questions=len(questions),
               answered=len(questions) - len(failed), failed=failed, exit_code=proc.returncode, **counts)
    return out
