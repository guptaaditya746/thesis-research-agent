"""Gold standard state per question, read from $GOLD/<qid>/ (docs/earlier-work.md, "Gold files, answer key, judge, scores").

The gold builder (C1) and the review (C2) write these files; this module only reads them, and any
of them may be missing (a question whose gold is not built yet): status `none`, then `building`
(the builder has written something, or a web-app gold job runs), `draft` (key.draft.json),
`reviewing` (key.json from an export half way through the review: `review.complete` false) and
`reviewed` (key.json of a finished review). The builder's own stage (progress.json: building, failed, done, ...) is
passed along, so `building` after a build that stopped (D there, no draft yet) can be told from
one in progress.

$GOLD also holds directories that are not questions (C2's judge/ calibration sample, a user's
_scratch/): a question directory is one whose name is a plain id and that holds a gold file.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .files import ID, NotFound, check_id, inside, read_json
from .models import GoldEntry, GoldStatus

KEY, DRAFT = "key.json", "key.draft.json"
PROGRESS = "progress.json"
BUILDER_FILES = ("chunks.jsonl", "screening.jsonl", "candidates.jsonl", "doc.json", "triage.jsonl", "pool.jsonl")
GOLD_FILES = (*BUILDER_FILES, PROGRESS, DRAFT, KEY)


def qdir(root: Path, qid: str) -> Path:
    return inside(root, check_id(qid, "question"))


def key(root: Path, qid: str) -> dict[str, Any]:
    """The reviewed key, else the draft key; NotFound when neither exists."""
    folder = qdir(root, qid)
    for name in (KEY, DRAFT):
        data = read_json(folder / name)
        if isinstance(data, dict):
            return data
    raise NotFound(f"no answer key for {qid} yet")


def counts(key_data: dict[str, Any] | None) -> tuple[int | None, int | None]:
    """(rows, facts) of an answer key."""
    if not isinstance(key_data, dict) or not isinstance(key_data.get("rows"), list):
        return None, None
    rows = key_data["rows"]
    return len(rows), sum(len(r.get("facts") or []) for r in rows if isinstance(r, dict))


def started(root: Path, qid: str) -> bool:
    """Whether anything of the gold build exists for the question (its concept is then in use)."""
    folder = qdir(root, qid)
    return folder.is_dir() and any(folder.iterdir())


def stage(folder: Path) -> str | None:
    progress = read_json(folder / PROGRESS)
    return str(progress["stage"]) if isinstance(progress, dict) and progress.get("stage") else None


def review_finished(key_data: dict[str, Any]) -> bool:
    """False for a key.json `gold export` wrote half way through the review (review.complete false);
    scoring marks scores against it provisional too (scoring/run_score.py)."""
    review = key_data.get("review")
    return not isinstance(review, dict) or review.get("complete") is not False


def status(root: Path, qid: str, building: bool = False) -> GoldStatus:
    folder = qdir(root, qid)
    for name, state in ((KEY, "reviewed"), (DRAFT, "draft")):
        data = read_json(folder / name)
        if isinstance(data, dict):
            rows, facts = counts(data)
            if state == "reviewed" and not review_finished(data):
                state = "reviewing"
            return GoldStatus(status=state, rows=rows, facts=facts, stage=stage(folder))
    if building or any((folder / name).exists() for name in (*BUILDER_FILES, PROGRESS)):
        doc = read_json(folder / "doc.json")
        rows = len(doc["rows"]) if isinstance(doc, dict) and isinstance(doc.get("rows"), list) else None
        return GoldStatus(status="building", rows=rows, stage=stage(folder))
    return GoldStatus(status="none")


def entry(root: Path, qid: str, building: bool = False) -> GoldEntry:
    folder = qdir(root, qid)
    state = status(root, qid, building)
    doc = read_json(folder / "doc.json")
    doc = doc if isinstance(doc, dict) else {}
    key_data = read_json(folder / KEY) or read_json(folder / DRAFT)
    report = read_json(folder / "report.json")
    return GoldEntry(qid=qid, status=state.status, stage=state.stage, coverage=doc.get("coverage"),
                     counts=doc.get("counts"), key_version=key_data.get("version") if isinstance(key_data, dict) else None,
                     report=report if isinstance(report, dict) else None, rows=state.rows, facts=state.facts)


def qids(root: Path) -> list[str]:
    """Question ids with a gold directory: a plain id that holds a gold file (others are skipped)."""
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and ID.fullmatch(p.name) and any((p / n).exists() for n in GOLD_FILES))
