"""The gold working directory as the review reads and writes it (plan "Gold", work package C2), and the
people's answers pulled out of Argilla into it (labelling README, workflow steps 5-7).

Per question, `$GOLD/<qid>/` (contracts in docs/e2e-build-plan.md):
- from C1: candidates.jsonl, pool.jsonl, pool.strata.json, triage.jsonl, screening.jsonl, doc.json;
- review/<dataset>.jsonl: the Argilla records with their responses as last pulled (`gold pull`), one line
  per record, `{id, dataset, metadata, responses: [{question, value, user, status}]}`, for the datasets
  review, overlap, missing and screening (gold/argilla_io.py);
- snapshots/overlap-<time>.json: the overlap records as they stood at a pull. Agreement is computed from
  the earliest snapshot in which both people had answered a record, so editing an answer to settle a
  disagreement afterwards does not raise kappa (labelling README, step 6b);
- screening.sample.json, key.json, export.json, report.json (written by C2's other modules).
At the root: overlap.json (which questions two people review), judge/ (the calibration sample and its
pulled responses), judge-cache.jsonl, judge-report.json and report.json.

C1 writes its files in parallel on another branch, so readers here take only the contract's fields and
fill what a file leaves out (the stratum of a pool record, the stratum sizes) from the others.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from agent import anchor

DEFAULT_ROOT = "gold-data"
REVIEW_DIR = "review"
SNAPSHOT_DIR = "snapshots"
QUESTION_DATASETS = ("review", "overlap", "missing", "screening")
TIERS = ("answers", "context")  # triage labels whose candidates are all reviewed; the rest is sampled


def gold_root(path: str | os.PathLike[str] | None = None) -> Path:
    return Path(path or os.environ.get("GOLD") or DEFAULT_ROOT)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# --- files ------------------------------------------------------------------------------------------

def read_json(path: Path) -> Any | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def write_json(path: Path, obj: Any) -> Path:
    """Indented JSON with LF line ends (reports and keys are read by people too)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(json.dumps(r, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
                              for r in rows))
    return path


def seeded_order(ids: Iterable[str], seed: str) -> list[str]:
    """A deterministic shuffle: ids ranked by sha256(seed:id). The first n are a seeded sample of size n,
    and adding ids to the frame never changes the relative order of the others (labelling sample_ids)."""
    return sorted(ids, key=lambda value: hashlib.sha256(f"{seed}:{value}".encode()).hexdigest())


# --- questions, concepts, C1's files ------------------------------------------------------------------

def qdir(root: Path, qid: str) -> Path:
    return Path(root) / qid


def question_ids(root: Path) -> list[str]:
    """Questions with a gold directory from C1 (candidates, pool or D)."""
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and any(
        (p / name).is_file() for name in ("candidates.jsonl", "pool.jsonl", "doc.json")))


def select(root: Path, which: str) -> list[str]:
    """`all`, one question id, or a comma-separated list."""
    return question_ids(root) if which == "all" else [q for q in which.split(",") if q]


def questions(path: Path | None) -> dict[str, dict[str, Any]]:
    """questions/questions.json (work package B) by id; empty when the file is not there."""
    data = read_json(Path(path)) if path else None
    return {q["id"]: q for q in (data or {}).get("questions", [])}


def question_text(qid: str, *, questions_file: Path | None = None, concepts: Path | None = None) -> str:
    """The question's wording: questions.json, else the concept session's question, else the id."""
    found = questions(questions_file).get(qid)
    if found:
        return str(found["question"])
    session = read_json(Path(concepts) / qid / "session.json") if concepts else None
    return str((session or {}).get("question") or qid)


def concept(concepts: Path | None, qid: str) -> dict[str, Any] | None:
    """The picked concept, `$CONCEPTS/<qid>/concept.json` (agent/concept_step.py)."""
    return read_json(Path(concepts) / qid / "concept.json") if concepts else None


def candidates(root: Path, qid: str) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in read_jsonl(qdir(root, qid) / "candidates.jsonl")}


def triage(root: Path, qid: str) -> dict[str, str]:
    return {t["id"]: t["label"] for t in read_jsonl(qdir(root, qid) / "triage.jsonl")}


def stratum(item: dict[str, Any], labels: dict[str, str] | None = None) -> str:
    """`triaged` (triage put it in answers or context, or left it unsorted) or `sample` (drawn from the rest)."""
    if item.get("stratum"):
        return str(item["stratum"])
    label = item.get("triage") or (labels or {}).get(item["id"])
    return "sample" if label is not None and label not in TIERS else "triaged"


def pool(root: Path, qid: str) -> list[dict[str, Any]]:
    """The review records of one question: each pool line over its candidate, with `stratum` set."""
    by_id = candidates(root, qid)
    labels = triage(root, qid)
    out = []
    for line in read_jsonl(qdir(root, qid) / "pool.jsonl"):
        item = {"qid": qid, **by_id.get(line["id"], {}), **line}
        out.append({**item, "stratum": stratum(item, labels)})
    return out


def strata(root: Path, qid: str) -> dict[str, Any]:
    """Stratum sizes: `reviewed_tiers` (records triage put in answers/context), `rest` (candidates outside
    those tiers), `sampled` (records drawn from the rest). pool.strata.json wins where it gives a size."""
    items = pool(root, qid)
    labels = triage(root, qid)
    counted = Counter(item["stratum"] for item in items)
    rest = (sum(label not in TIERS for label in labels.values()) if labels
            else max(0, len(candidates(root, qid)) - counted["triaged"]))
    given = read_json(qdir(root, qid) / "pool.strata.json") or {}
    if qid in given and isinstance(given[qid], dict):  # labelling's form: sizes per question id
        given = given[qid]
    computed = {"triaged": bool(labels) or "sample" in counted, "reviewed_tiers": counted["triaged"],
                "rest": rest, "sampled": counted["sample"]}
    return {**computed, **{k: given[k] for k in ("reviewed_tiers", "rest", "sampled") if k in given}}


def screening(root: Path, qid: str) -> list[dict[str, Any]]:
    return read_jsonl(qdir(root, qid) / "screening.jsonl")


OVERLAP_FILE = "overlap.json"
OVERLAP_SHARE = 0.2


def overlap_questions(root: Path, qids: list[str], *, share: float = OVERLAP_SHARE, seed: str = "gold-v1") -> list[str]:
    """The agreement subset: ceil(share x questions) of `qids`, a seeded choice made once and kept in
    $GOLD/overlap.json, so a later push of one question puts it in the same dataset."""
    path = Path(root) / OVERLAP_FILE
    kept = read_json(path)
    if kept is not None:
        return list(kept["overlap"])
    n = min(len(qids), max(1, math.ceil(share * len(qids)))) if qids else 0
    chosen = sorted(seeded_order(qids, f"{seed}:overlap")[:n])
    write_json(path, {"seed": seed, "share": share, "questions": sorted(qids), "overlap": chosen,
                      "chosen_at": utc_now()})
    return chosen


# --- corpus -------------------------------------------------------------------------------------------

class Corpus:
    """The frozen Markdown corpus as the review reads it: file text exactly as stored (anchor offsets
    refer to it) and anchor Indexes, the last INDEXES of them kept (one holds two ints per character)."""

    INDEXES = 8

    def __init__(self, root: Path | str | None) -> None:
        self.root = Path(root) if root else None
        self._texts: dict[str, str] = {}
        self._indexes: OrderedDict[str, anchor.Index] = OrderedDict()

    @staticmethod
    def file_name(file_or_paper: str) -> str:
        """`p12`, `p12.md` and `corpus/p12.md` all name `p12.md`."""
        name = Path(file_or_paper.strip()).name
        return name if name.endswith(".md") else f"{name}.md"

    @staticmethod
    def paper_id(file: str) -> str:
        return Path(file).stem

    def has(self, file: str) -> bool:
        return self.root is not None and (self.root / self.file_name(file)).is_file()

    def text(self, file: str) -> str:
        name = self.file_name(file)
        if name not in self._texts:
            if self.root is None:
                raise FileNotFoundError("no corpus directory: give --corpus or set $CORPUS")
            self._texts[name] = anchor.read_text(self.root / name)
        return self._texts[name]

    def index(self, file: str) -> anchor.Index:
        name = self.file_name(file)
        if name in self._indexes:
            self._indexes.move_to_end(name)
        else:
            self._indexes[name] = anchor.Index(self.text(name))
            while len(self._indexes) > self.INDEXES:
                self._indexes.popitem(last=False)
        return self._indexes[name]

    def locate(self, item: dict[str, Any]) -> tuple[str, int, int] | None:
        """(file text, start, end) of a candidate's quote: its selector when the offsets still hold the
        exact text, else the quote anchored again; None when the file or the quote is not found."""
        file = item.get("file") or (f"{item['paper_id']}.md" if item.get("paper_id") else None)
        if not file or not self.has(file):
            return None
        text = self.text(file)
        sel = item.get("anchor") or {}
        if sel and text[sel.get("start", 0):sel.get("end", 0)] == sel.get("exact") and sel.get("exact"):
            return text, int(sel["start"]), int(sel["end"])
        try:
            found = anchor.find(self.index(file), str(item.get("quote") or ""), file=self.file_name(file))
        except anchor.AnchorError:
            return None
        return text, found.start, found.end


# --- pulled responses ----------------------------------------------------------------------------------

def submitted(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Submitted answers by user: {user: {question: value}} (drafts and discarded ones do not count)."""
    by_user: dict[str, dict[str, Any]] = defaultdict(dict)
    for response in record.get("responses", []):
        if response.get("status") == "submitted":
            by_user[str(response["user"])][str(response["question"])] = response.get("value")
    return dict(by_user)


def record_qid(record: dict[str, Any]) -> str | None:
    qid = (record.get("metadata") or {}).get("question_id")
    return str(qid) if qid and qid != "unknown" else None


def store(root: Path, pulled: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    """Write pulled records: per question into <qid>/review/<dataset>.jsonl, the judge dataset into
    judge/responses.jsonl. A dataset that was pulled replaces its files; others are left as they are."""
    counts: dict[str, int] = {}
    for dataset, records in pulled.items():
        counts[dataset] = len(records)
        if dataset == "judge":
            write_jsonl(Path(root) / "judge" / "responses.jsonl", records)
            continue
        by_qid: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            by_qid[record_qid(record) or "_unknown"].append(record)
        for qid, rows in by_qid.items():
            write_jsonl(qdir(root, qid) / REVIEW_DIR / f"{dataset}.jsonl", rows)
    return counts


def reviews(root: Path, qid: str) -> dict[str, list[dict[str, Any]]]:
    """The last pulled records of one question, per dataset."""
    return {d: read_jsonl(qdir(root, qid) / REVIEW_DIR / f"{d}.jsonl") for d in QUESTION_DATASETS}


def _stamp(taken_at: str) -> str:
    return taken_at.replace("-", "").replace(":", "").replace(".", "")


def snapshot(root: Path, overlap: list[dict[str, Any]], *, taken_at: str | None = None) -> list[Path]:
    """Save the overlap records that have at least one submitted answer, per question, unless they are
    the same as that question's latest snapshot. Returns the files written."""
    taken_at = taken_at or utc_now()
    by_qid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in overlap:
        if submitted(record):
            by_qid[record_qid(record) or "_unknown"].append(record)
    written = []
    for qid, records in sorted(by_qid.items()):
        records = sorted(records, key=lambda r: r["id"])
        previous = snapshots(root, qid)
        if previous and previous[-1]["overlap"] == records:
            continue
        path = qdir(root, qid) / SNAPSHOT_DIR / f"overlap-{_stamp(taken_at)}.json"
        written.append(write_json(path, {"qid": qid, "taken_at": taken_at, "overlap": records}))
    return written


def snapshots(root: Path, qid: str) -> list[dict[str, Any]]:
    """Overlap snapshots of one question, oldest first, each `{taken_at, path, overlap}`."""
    folder = qdir(root, qid) / SNAPSHOT_DIR
    found = sorted(folder.glob("overlap-*.json")) if folder.is_dir() else []
    return [{**read_json(p), "path": str(p)} for p in found]


def overlap_records(root: Path, qid: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The independent round of the overlap (labelling overlap_from_snapshots): per record, its version in
    the earliest snapshot where two people had submitted it; records never complete in a snapshot come
    from the last pull."""
    live = reviews(root, qid)["overlap"]
    chosen: dict[str, dict[str, Any]] = {}
    snaps = snapshots(root, qid)
    for snap in snaps:
        for record in snap.get("overlap") or []:
            if record["id"] not in chosen and len(submitted(record)) >= 2:
                chosen[record["id"]] = record
    live_ids = {r["id"] for r in live}
    merged = [chosen.get(r["id"], r) for r in live] + [r for i, r in chosen.items() if i not in live_ids]
    return merged, {"snapshots": [s["path"] for s in snaps], "records_from_snapshots": len(chosen),
                    "records_from_live": sum(1 for r in live if r["id"] not in chosen and len(submitted(r)) >= 2)}
