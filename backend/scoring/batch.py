"""`score batch <runs_root> --gold $GOLD [--manifest <batch manifest>]`: score every finished run.

Which runs: with a run manifest (agent/batch.py, row 2.9), each run key <qid>-<condition>-r<repeat>
contributes its finished attempt (the latest, if there were several); keys with none are listed with
the state of their last attempt. The attempts are where `agent batch` wrote them, the manifest's own
runs_root (relative to the working directory, as agent batch reads it); scripts/e2e-batch.sh writes the
effective manifest to $RUNS/<name>/manifest.json with runs_root $RUNS/<name> and prints that root
(RUNS_ROOT=...), which is the runs root scoring and the web app take for the manifest
(docs/earlier-work.md, Environment), so on the cluster:
`score batch $RUNS/m4-72 --manifest $RUNS/m4-72/manifest.json`. A manifest whose runs_root does not
exist is an error, not 72 runs "not started". The report goes to <runs_root>/report/, where the web
app started with RUNS=$RUNS/m4-72 reads it. Without a manifest, every run directory below runs_root
(nested roots included, as `score store` walks them) whose name is a batch run key
(<qid>-<condition>-r<n>-a<n>) is a candidate, and its question is the key whose concept_sha256 is the
run's; `include_all` (--all) also takes runs with other names (ad hoc runs from the web app). A second
directory with a run id already seen is listed as `duplicate` and not scored (from_tree).

Finished is the batch runner's own test (agent.batch.run_state): an answer, no cut or run_error record,
a finished attach step for claim_off, and `agent verify` passing. Without a corpus at hand the verify
part is skipped (verify_ok stays null in score.json, and the report says so).

Which key: $GOLD/<qid>/key.json (reviewed), else key.draft.json; a key file that does not parse is
recorded and the next one is tried. Scores against a draft key are marked provisional and so is the
report built from them.

Reuse: a run's score.json is kept unless --force or it is out of date: another scoring version or key
file (by hash); a corpus now at hand where verify_ok was null; and, when a judge is at hand, a
different judge (model or prompt hashes), a different judge input (context mode), another calibration
(judge-report.json), or any decision still pending. Rescoring costs no model calls for decisions the
judge's cache already holds. A score made with a judge is not replaced by one without.

A run that cannot be scored (any error) is recorded as score_failed and the batch goes on, so
report/scores.jsonl and report/batch.json are always rewritten together.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.batch import CUT_REASONS, Manifest, attempts
from jsonio import canonical, file_sha256, write_json
from agent.rundir import RunDir, attach_state, utc_now

from .judge import Judge
from .run_score import RUN_KEY, SCHEMA_VERSION, read_score, records, score_run
from .support import calibration

REPORT_DIR = "report"
SCORES_FILE = "scores.jsonl"
BATCH_FILE = "batch.json"
KEY_FILES = ("key.json", "key.draft.json")


class BatchError(ValueError):
    pass


@dataclass(frozen=True)
class Key:
    qid: str
    path: Path
    concept_sha256: str | None
    sha256: str


def find_keys(gold: Path, problems: list[str] | None = None) -> dict[str, Key]:
    """The key to score each question with, by question directory: key.json, else key.draft.json.

    A key file that cannot be read is skipped for the next one and listed in `problems`."""
    out: dict[str, Key] = {}
    for qdir in sorted(Path(gold).iterdir()) if Path(gold).is_dir() else []:
        for name in KEY_FILES:
            path = qdir / name
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("not a JSON object")
            except (OSError, ValueError) as exc:
                if problems is not None:
                    problems.append(f"{path}: {exc}")
                continue
            out[qdir.name] = Key(str(data.get("qid") or qdir.name), path, data.get("concept_sha256"),
                                 file_sha256(path))
            break
    return out


def key_for(gold: Path, run: RunDir) -> Key | None:
    """The key for one run: by its run id's question, else by its concept hash."""
    keys = find_keys(gold)
    m = RUN_KEY.match(run.run_id)
    if m and m.group("qid") in keys:
        return keys[m.group("qid")]
    concept = run.load_config()["hashes"]["concept_sha256"]
    return next((k for k in keys.values() if k.concept_sha256 == concept), None)


def run_state(run: RunDir, corpus: Path | None, manifest: Path | None) -> tuple[str, str]:
    """agent.batch.run_state with a corpus; without one, the same rules minus `agent verify`."""
    if corpus is not None:
        from agent.batch import run_state as full

        return full(run, Path(corpus), Path(manifest or Path(corpus) / "manifest.json"))
    if not run.config.is_file():
        return "incomplete", "no config.json"
    reasons = [(r.get("generated") or {}).get("reason") for r in records(run) if r.get("subtype") == "coverage"]
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


def safe_state(run: RunDir, corpus: Path | None, corpus_manifest: Path | None) -> tuple[str, str]:
    try:
        return run_state(run, corpus, corpus_manifest)
    except Exception as exc:  # a malformed run is listed, not fatal
        return "failed", f"{type(exc).__name__}: {exc}"[:300]


def from_manifest(manifest: Path, corpus: Path | None, corpus_manifest: Path | None) -> tuple[Path, list[Item]]:
    """The manifest's run keys, with their attempts under the manifest's runs_root (where agent batch put them)."""
    m = Manifest.load(manifest)
    root = m.runs_root
    if not root.is_dir():
        raise BatchError(f"the manifest's runs_root {root} does not exist (from {os.getcwd()}): give the "
                         f"manifest agent batch ran (scripts/e2e-batch.sh: $RUNS/<name>/manifest.json)")
    items = []
    for entry in m.plan():
        states = [(run, *safe_state(run, corpus, corpus_manifest)) for run in attempts(root, entry.key)]
        done = [s for s in states if s[1] == "finished"]
        run, state, detail = (done or states or [(None, "not_started", "")])[-1]
        items.append(Item(entry.key, entry.question_id, entry.condition, entry.repeat, run, state, detail))
    return root, items


def run_dirs(runs_root: Path) -> list[Path]:
    """Every run directory (one with config.json) below runs_root; hidden directories and report/ skipped."""
    found = []
    for top, dirs, files in os.walk(runs_root):
        if "config.json" in files and Path(top) != Path(runs_root):
            found.append(Path(top))
            dirs[:] = []
            continue
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (Path(top) == Path(runs_root)
                                                                           and d == REPORT_DIR))
    return sorted(found)


def from_tree(runs_root: Path, corpus: Path | None, corpus_manifest: Path | None,
              include_all: bool = False) -> list[Item]:
    """Every run directory below runs_root. Run ids are directory names, so a second directory with an id
    already seen (two batch roots under one root: e2e-smoke and m4-72 both have q01-claim_on-r1-a1) is
    listed as `duplicate` and not scored, never mixed in; score one batch root at a time."""
    items = []
    seen: dict[str, Path] = {}
    for d in run_dirs(runs_root):
        run = RunDir(d)
        if d.name in seen:
            items.append(Item(d.name, None, None, None, run, "duplicate",
                              f"{seen[d.name]} has the same run id; score one batch root at a time"))
            continue
        seen[d.name] = d
        m = RUN_KEY.match(d.name)
        if not m and not include_all:
            items.append(Item(d.name, None, None, None, run, "not_a_batch_run",
                              "the name is not <qid>-<condition>-r<n>-a<n>; --all includes it"))
            continue
        try:
            condition = run.load_config().get("condition")
        except (OSError, ValueError, AttributeError) as exc:
            items.append(Item(d.name, None, None, None, run, "failed", f"config.json: {exc}"))
            continue
        state, detail = safe_state(run, corpus, corpus_manifest)
        items.append(Item(d.name, None, condition, int(m.group("repeat")) if m else None, run, state, detail))
    return items


def stale(old: dict[str, Any] | None, key: Key, judge: Judge | None, *, corpus: Path | None,
          calibration_sha: str | None) -> list[str]:
    """Why an existing score.json must be redone; empty when it can be reused."""
    if not old:
        return ["no score.json"]
    if old.get("schema_version") != SCHEMA_VERSION:
        return ["another scoring version"]
    if old.get("key_sha256") != key.sha256:
        return ["another key file"]
    why = []
    if corpus is not None and old.get("verify_ok") is None:
        why.append("not verified")
    if judge is not None:
        was = old.get("judge") or {}
        support = old.get("support") or {}
        if not was.get("used"):
            why.append("scored without a judge")
        elif was.get("identity") != judge.identity():
            why.append("another judge model or prompt")
        if support.get("context") not in (None, judge.context_mode(corpus)):
            why.append("another judge context")
        if (support.get("calibration") or {}).get("sha256") != calibration_sha:
            why.append("another judge calibration")
        if any((old.get("pending") or {"unknown": 1}).values()):
            why.append("judge decisions pending")
    elif why and (old.get("judge") or {}).get("used"):
        return []  # rescoring without the judge would lose its verdicts
    return why


def score_batch(runs_root: Path, gold: Path, *, manifest: Path | None = None, corpus: Path | None = None,
                corpus_manifest: Path | None = None, force: bool = False, judge: Judge | None = None,
                include_all: bool = False, log: Callable[[str], None] = print) -> dict[str, Any]:
    runs_root = Path(runs_root)
    key_problems: list[str] = []
    keys = find_keys(gold, key_problems)
    for text in key_problems:
        log(f"score: key skipped: {text}")
    by_concept = {k.concept_sha256: k for k in keys.values() if k.concept_sha256}
    calibration_sha = calibration(gold)["sha256"]
    if manifest:
        attempts_root, items = from_manifest(manifest, corpus, corpus_manifest)
    else:
        attempts_root, items = runs_root, from_tree(runs_root, corpus, corpus_manifest, include_all)
        for item in items:
            if item.state == "duplicate":
                log(f"score: {item.run.root if item.run else item.key} skipped: {item.detail}")
    scores = []
    counts = {"scored": 0, "reused": 0, "skipped": 0, "failed": 0}
    for item in items:
        if item.state != "finished" or item.run is None:
            counts["skipped"] += 1
            continue
        try:
            concept = item.run.load_config()["hashes"]["concept_sha256"]
            key = (keys.get(item.qid) if item.qid else None) or by_concept.get(concept)
            if key is None:
                item.state, item.detail = "no_key", f"no key.json or key.draft.json for {item.qid or 'its concept'}"
                counts["skipped"] += 1
                continue
            item.qid = item.qid or key.qid
            old = read_score(item.run)
            why = ["--force"] if force else stale(old, key, judge, corpus=corpus, calibration_sha=calibration_sha)
            if why:
                score, how = score_run(item.run.root, key.path, judge=judge, corpus=corpus,
                                       manifest=corpus_manifest, gold=gold), "scored"
            else:
                score, how = old, "reused"
        except Exception as exc:  # one malformed run never stops the batch
            item.state, item.detail = "score_failed", f"{type(exc).__name__}: {exc}"[:500]
            counts["failed"] += 1
            log(f"score: {item.run.run_id}: {item.detail}")
            continue
        counts[how] += 1
        item.scored, item.provisional = True, bool(score["provisional"])
        scores.append(score)
        log(f"score: {item.run.run_id} {how}" + (f" ({', '.join(why)})" if why and how == "scored" else "")
            + (" (provisional key)" if score["provisional"] else ""))
    out = runs_root / REPORT_DIR
    out.mkdir(parents=True, exist_ok=True)
    scores.sort(key=lambda s: s["run_id"])
    (out / SCORES_FILE).write_bytes(b"".join(canonical(s).encode("utf-8") + b"\n" for s in scores))
    summary = {"schema_version": 1, "written_at": utc_now(), "runs_root": str(runs_root),
               "attempts_root": str(attempts_root), "gold": str(gold),
               "manifest": str(manifest) if manifest else None, "corpus": str(corpus) if corpus else None,
               "counts": counts, "provisional": any(s["provisional"] for s in scores), "key_problems": key_problems,
               "items": [{"key": i.key, "qid": i.qid, "condition": i.condition, "repeat": i.repeat,
                          "run_id": i.run.run_id if i.run else None,
                          "run_dir": str(i.run.root.resolve()) if i.run else None, "state": i.state, "detail": i.detail,
                          "scored": i.scored, "provisional": i.provisional} for i in items]}
    write_json(out / BATCH_FILE, summary)
    return summary
