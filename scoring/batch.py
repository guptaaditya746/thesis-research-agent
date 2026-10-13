"""`score batch <runs_root> --gold $GOLD [--manifest <batch manifest>]`: score every finished run.

Which runs: with a run manifest (agent/batch.py, row 2.9), each run key <qid>-<condition>-r<repeat>
contributes its finished attempt (the latest, if there were several); keys with none are listed with
the state of their last attempt. Without a manifest, every run directory under runs_root is a
candidate, and its question is the key whose concept_sha256 is the run's.

Finished is the batch runner's own test (agent.batch.run_state): an answer, no cut or run_error record,
a finished attach step for claim_off, and `agent verify` passing. Without a corpus at hand the verify
part is skipped (verify_ok stays null in score.json).

Which key: $GOLD/<qid>/key.json (reviewed), else key.draft.json; scores against a draft key are marked
provisional and so is the report built from them. A run that already has a score.json against the same
key file (by hash), with nothing left pending that the judge could now decide, is not scored again
unless --force: a reviewed key replacing the draft rescored every run automatically.

Writes <runs_root>/report/scores.jsonl (one score.json per line, by run id) and report/batch.json
(every key or run with its state and whether it was scored), the inputs of `score report`.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.batch import CUT_REASONS, Manifest, attempts
from agent.canonical import canonical, file_sha256, write_json
from agent.rundir import RunDir, attach_state, utc_now

from .judge import Judge
from .run_score import SCHEMA_VERSION, ScoreError, read_score, records, score_run

REPORT_DIR = "report"
SCORES_FILE = "scores.jsonl"
BATCH_FILE = "batch.json"
KEY_FILES = ("key.json", "key.draft.json")


@dataclass(frozen=True)
class Key:
    qid: str
    path: Path
    concept_sha256: str | None
    sha256: str


def find_keys(gold: Path) -> dict[str, Key]:
    """The key to score each question with, by question directory: key.json, else key.draft.json."""
    out: dict[str, Key] = {}
    for qdir in sorted(Path(gold).iterdir()) if Path(gold).is_dir() else []:
        path = next((qdir / n for n in KEY_FILES if (qdir / n).is_file()), None)
        if path is None:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        out[qdir.name] = Key(str(data.get("qid") or qdir.name), path, data.get("concept_sha256"), file_sha256(path))
    return out


def run_state(run: RunDir, corpus: Path | None, manifest: Path | None) -> tuple[str, str]:
    """agent.batch.run_state with a corpus; without one, the same rules minus `agent verify`."""
    if corpus is not None:
        from agent.batch import run_state as full

        return full(run, Path(corpus), Path(manifest or Path(corpus) / "manifest.json"))
    if not run.config.is_file():
        return "incomplete", "no config.json"
    reasons = [r["generated"].get("reason") for r in records(run) if r.get("subtype") == "coverage"]
    cut = [r for r in reasons if r in CUT_REASONS]
    if cut:
        return "cut", cut[-1]
    if not run.answer.is_file():
        return "incomplete", "no answer.json"
    for reason in ("run_error", "attach_failed"):
        if reason in reasons:
            return "failed", reason
    attach = attach_state(run)
    if attach == "pending":
        return "attach_pending", "the run finished; its attach step has not started"
    if attach == "cut":
        return "incomplete", "the attach step started but did not finish"
    return "finished", "not verified (no corpus)"


@dataclass
class Item:
    """One run key (manifest) or run directory, and what became of it."""
    key: str
    qid: str | None
    condition: str | None
    repeat: int | None
    run: RunDir | None
    state: str
    detail: str = ""
    scored: bool = False
    provisional: bool | None = None


def from_manifest(runs_root: Path, manifest: Path, corpus: Path | None, corpus_manifest: Path | None) -> list[Item]:
    items = []
    for entry in Manifest.load(manifest).plan():
        runs = attempts(runs_root, entry.key)
        states = [(run, *run_state(run, corpus, corpus_manifest)) for run in runs]
        done = [s for s in states if s[1] == "finished"]
        run, state, detail = (done or states or [(None, "not_started", "")])[-1]
        items.append(Item(entry.key, entry.question_id, entry.condition, entry.repeat, run, state, detail))
    return items


def from_tree(runs_root: Path, corpus: Path | None, corpus_manifest: Path | None) -> list[Item]:
    items = []
    for d in sorted(Path(runs_root).iterdir()) if Path(runs_root).is_dir() else []:
        if d.is_dir() and not d.name.startswith(".") and d.name != REPORT_DIR and (d / "config.json").is_file():
            run = RunDir(d)
            state, detail = run_state(run, corpus, corpus_manifest)
            items.append(Item(d.name, None, run.load_config().get("condition"), None, run, state, detail))
    return items


def up_to_date(old: dict[str, Any] | None, key: Key, judge: Judge | None) -> bool:
    """A score.json against this key file, with nothing the judge (if there is one now) could add."""
    if not old or old.get("schema_version") != SCHEMA_VERSION or old.get("key_sha256") != key.sha256:
        return False
    if judge is None:
        return True
    used = (old.get("judge") or {}).get("used")
    pending = (old.get("judge") or {}).get("pending", 0) or (old.get("support") or {}).get("pending", 0)
    return bool(used) and not pending


def score_batch(runs_root: Path, gold: Path, *, manifest: Path | None = None, corpus: Path | None = None,
                corpus_manifest: Path | None = None, force: bool = False, judge: Judge | None = None,
                workers: int = 1, log: Callable[[str], None] = print) -> dict[str, Any]:
    runs_root = Path(runs_root)
    keys = find_keys(gold)
    by_concept = {k.concept_sha256: k for k in keys.values() if k.concept_sha256}
    items = (from_manifest(runs_root, manifest, corpus, corpus_manifest) if manifest
             else from_tree(runs_root, corpus, corpus_manifest))
    scores = []
    counts = {"scored": 0, "reused": 0, "skipped": 0, "failed": 0}
    for item in items:
        if item.state != "finished" or item.run is None:
            counts["skipped"] += 1
            continue
        concept = item.run.load_config()["hashes"]["concept_sha256"]
        key = (keys.get(item.qid) if item.qid else None) or by_concept.get(concept)
        if key is None:
            item.state, item.detail = "no_key", f"no key.json or key.draft.json for {item.qid or 'its concept'}"
            counts["skipped"] += 1
            continue
        item.qid = item.qid or key.qid
        old = read_score(item.run)
        try:
            if not force and up_to_date(old, key, judge):
                score, how = old, "reused"
            else:
                score, how = score_run(item.run.root, key.path, judge=judge, corpus=corpus,
                                       manifest=corpus_manifest, workers=workers), "scored"
        except ScoreError as exc:
            item.state, item.detail = "score_failed", str(exc)
            counts["failed"] += 1
            log(f"score: {item.run.run_id}: {exc}")
            continue
        counts[how] += 1
        item.scored, item.provisional = True, bool(score["provisional"])
        scores.append(score)
        log(f"score: {item.run.run_id} {how}" + (" (provisional key)" if score["provisional"] else ""))
    out = runs_root / REPORT_DIR
    out.mkdir(parents=True, exist_ok=True)
    scores.sort(key=lambda s: s["run_id"])
    (out / SCORES_FILE).write_bytes(b"".join(canonical(s).encode("utf-8") + b"\n" for s in scores))
    summary = {"schema_version": 1, "written_at": utc_now(), "runs_root": str(runs_root), "gold": str(gold),
               "manifest": str(manifest) if manifest else None, "counts": counts,
               "provisional": any(s["provisional"] for s in scores),
               "items": [{"key": i.key, "qid": i.qid, "condition": i.condition, "repeat": i.repeat,
                          "run_id": i.run.run_id if i.run else None, "state": i.state, "detail": i.detail,
                          "scored": i.scored, "provisional": i.provisional} for i in items]}
    write_json(out / BATCH_FILE, summary)
    return summary
