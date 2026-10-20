"""Evidence document D for one question (M3, plan "Gold"): chunk -> screen -> extract, resumable.

The method of github.com/guptaaditya746/labelling (every paper screened, question-scoped extraction,
absence recorded per paper), re-implemented for the Markdown corpus with the picked concept as the
reading of the question. Per paper of the manifest (in manifest order; `--max-papers N` keeps the
first N, `--only-papers` names some, both for trials):

1. chunks (gold/chunks.py): the file cut at headings into chunks of at most GOLD_CHUNK_CHARS;
2. screening (gold/screen.py): every chunk, one call each; the paper's status from its chunks;
3. extraction (gold/extract.py): every relevant chunk, rows of the concept's answer shape, each fact
   with a quote checked as the broker checks a claim, one retry per rejected quote.

Chunks run as one pipeline each (screen, then extract when relevant), under one limit of
GOLD_CONCURRENCY calls in flight (default 6) and a per-call timeout (GOLD_CALL_TIMEOUT_S, default
300 s); at most twice that many papers are open at once, which bounds the anchor indexes in memory.
Every result is in cache.jsonl (gold/calls.py), so a stopped build resumes where it stopped, a
finished one is rebuilt without model calls, and a trial's papers are not paid for again.

Failures. A call that failed for a reason that may pass (timeout, server error) is not cached: run
the build again to retry it (`coverage.error`, `counts.chunks_error`, `extraction_errors`,
`retry_errors`; `gold build` exits 1 while any is left). A chunk too long for one call (the reply hit
max_tokens, or the prompt did not fit the context) fails the same way every time, so it is not
retried as it is: that chunk alone is cut in halves at a paragraph break and each half asked again,
down to pieces of MIN_PIECE_CHARS (`chunks_split`); a piece still too long is recorded as
`too_long` (`gold build` exits 3: a rerun cannot fix it, a smaller GOLD_CHUNK_CHARS can).

Outputs in $GOLD/<qid>/ (rewritten whole at the end of each build): chunks.jsonl, screening.jsonl,
candidates.jsonl, doc.json, doc.md; progress.json while it runs (with pid and host, so `gold status`
tells a dead build from a running one; SIGTERM, which Slurm sends at the time limit, stops the build
as `stopped`). ids.jsonl keeps candidate ids stable: an id names one extracted fact (paper, chunk
span, row, fact, quote) under one concept, so triage labels survive a trial followed by a full build,
and a rebuild under another concept gives new ids. The folder belongs to one concept: a build for
another concept, or a trial over a whole-corpus D, is refused unless `replace` (`--replace`), which
moves the old D and everything made from it to superseded/ (the call cache and ids.jsonl stay).
doc.json.built.invocations lists every build that made this D (calls, tokens, seconds);
counts.model_calls.total counts every call D rests on, the cached ones too.

doc.json `rows` merges the candidates across papers by a generic rule (`merge_rows`):
- table shapes: rows with the same normalised value in the first string column (the key; NFKC,
  casefold, letters and digits only, so "Natural Questions" = "natural-questions") are one row; list
  columns are unioned (same normalisation, first spelling kept); an integer column that counts a list
  column is recomputed as the length of the union (`count_columns`: the column is named as a count of
  that list, `paper_count`, `num_papers`, `n_papers`, `number_of_papers`, `total_papers`, or ends in
  the list's own name, `first_author_papers`; or it is named just `count`/`n`/`num`/`number`/`total`
  and there is one list column; a shared word alone, as in `paper_year` or `num_parameters`, is not
  enough); an extracted count that disagrees with its own row's list is kept under `conflicts`; other
  cells keep the first non-null value, and differing values are listed under `conflicts`.
  Rows without a key value are never merged; a shape without a string column merges identical rows.
- graph shapes: identical edges (same types and predicate, same normalised source and target) are one
  row; attributes merge as table cells do.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import socket
import subprocess
import unicodedata
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any

from agent.broker import Rejected
from jsonio import canonical, canonical_bytes, file_sha256, sha256_hex
from agent.concept import concept_sha256
from agent.rundir import utc_now

from . import docmd, extract, llm, screen
from .calls import Caller, CallError
from .chunks import MAX_CHARS, Chunk, GoldCorpus, halve, paper_chunks
from .screen import Task

REPO = Path(__file__).resolve().parents[1]
STATUSES = ("relevant", "not_relevant", "no_text", "error")
NUMERIC = ("integer", "number", "boolean")
COUNT_WORDS = frozenset({"count", "n", "num", "number", "total"})
KEEP_ON_REPLACE = ("cache.jsonl", "ids.jsonl", "superseded")  # concept-independent: stay in the folder


# --- settings and files ----------------------------------------------------------------------------

@dataclass(frozen=True)
class BuildSettings:
    concurrency: int = 6
    call_timeout_s: float = 300.0
    chunk_chars: int = MAX_CHARS
    temperature: float = 0.0
    seed: int = 0
    max_papers: int | None = None
    only_papers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.concurrency < 1:
            raise ValueError(f"concurrency must be at least 1, not {self.concurrency}")
        if self.call_timeout_s <= 0:
            raise ValueError(f"the call timeout must be positive, not {self.call_timeout_s}")
        if self.chunk_chars < 1:
            raise ValueError(f"chunk_chars must be positive, not {self.chunk_chars}")
        if self.max_papers is not None and self.max_papers < 1:
            raise ValueError(f"max_papers must be at least 1, not {self.max_papers} (leave it out for every paper)")

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ, **overrides: Any) -> BuildSettings:
        """GOLD_CONCURRENCY, GOLD_CALL_TIMEOUT_S, GOLD_CHUNK_CHARS; overrides (CLI flags) win when not None."""
        values: dict[str, Any] = {"concurrency": int(env.get("GOLD_CONCURRENCY", 6)),
                                  "call_timeout_s": float(env.get("GOLD_CALL_TIMEOUT_S", 300)),
                                  "chunk_chars": int(env.get("GOLD_CHUNK_CHARS", MAX_CHARS))}
        values.update({k: v for k, v in overrides.items() if v is not None})
        values["only_papers"] = tuple(values.get("only_papers") or ())
        return cls(**values)

    def json(self) -> dict[str, Any]:
        return {**asdict(self), "only_papers": list(self.only_papers),
                "max_tokens": {"screen": screen.MAX_TOKENS, "extract": extract.MAX_TOKENS,
                               "retry": extract.RETRY_MAX_TOKENS}}


class QuestionDir:
    """$GOLD/<qid>/ and its files (plan "Gold"); key.json is C2's, read here only for `gold status`."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.qid = self.root.name
        self.chunks = self.root / "chunks.jsonl"
        self.screening = self.root / "screening.jsonl"
        self.candidates = self.root / "candidates.jsonl"
        self.doc = self.root / "doc.json"
        self.doc_md = self.root / "doc.md"
        self.triage = self.root / "triage.jsonl"
        self.triage_runs = self.root / "triage.json"
        self.pool = self.root / "pool.jsonl"
        self.strata = self.root / "pool.strata.json"
        self.draft = self.root / "key.draft.json"
        self.key = self.root / "key.json"
        self.cache = self.root / "cache.jsonl"
        self.progress = self.root / "progress.json"
        self.ids = self.root / "ids.jsonl"
        self.superseded = self.root / "superseded"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """The lines of a JSONL file; a line that does not parse (cut by a killed process) is skipped."""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """Append lines, first ending a line a killed process left cut, so it cannot swallow a new one."""
    data = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows).encode("utf-8")
    if not data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as fh:
        if fh.tell() > 0:
            with path.open("rb") as last:
                last.seek(-1, os.SEEK_END)
                if last.read(1) != b"\n":
                    data = b"\n" + data
        fh.write(data)


def _replace(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data.encode("utf-8"))  # bytes: LF on every platform
    tmp.replace(path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _replace(path, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))


def write_json(path: Path, obj: Any) -> None:
    _replace(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def git_state(log: Callable[[str], None] | None = print) -> dict[str, Any]:
    """{commit, dirty, diff_sha256} of the checkout the code runs from (tracked files only: the
    cluster session fixes code live, so a dirty tree is recorded with the hash of `git diff HEAD`).
    When git cannot tell (no .git, "dubious ownership" on a shared checkout) every field is None and
    a warning is logged: the outputs then do not say which code made them."""
    def git(*args: str) -> bytes:
        return subprocess.run(["git", "-C", str(REPO), *args], check=True, capture_output=True).stdout

    try:
        commit = git("rev-parse", "HEAD").decode().strip()
        changed = git("status", "--porcelain", "--untracked-files=no").strip()
        diff = git("diff", "HEAD") if changed else b""
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = (getattr(exc, "stderr", b"") or b"").decode(errors="replace").strip().splitlines()
        if log is not None:
            log(f"WARNING: git cannot tell which commit runs ({detail[0] if detail else type(exc).__name__}); "
                "the outputs record git_commit null")
        return {"commit": None, "dirty": None, "diff_sha256": None}
    return {"commit": commit, "dirty": bool(changed), "diff_sha256": sha256_hex(diff) if diff else None}


def git_commit() -> str | None:
    return git_state(log=None)["commit"]


class FolderInUse(ValueError):
    """$GOLD/<qid>/ holds a D that this build would silently replace (see the module docstring)."""


class BuildStopped(Exception):
    """The build was stopped by SIGTERM (progress.json: stopped); what it finished is in the cache."""


# --- candidate ids -----------------------------------------------------------------------------------

class IdRegistry:
    """ids.jsonl: each extracted fact's fingerprint gets `<qid>-cNNNNNN` once and keeps it.

    Numbering in output order alone would renumber everything when a trial on 20 papers is followed
    by the full build, silently re-pointing triage labels at other facts. The fingerprint includes
    the concept hash, so a fact extracted again under another concept gets a new id and no label
    judged under the old concept follows it. The file is rewritten whole (atomically), never
    appended, so a killed build cannot leave a cut line that would make a number be given twice."""

    def __init__(self, path: Path, qid: str, concept_hash: str) -> None:
        self.path, self.qid, self.concept_hash = path, qid, concept_hash
        self.ids = {row["fingerprint"]: row["id"] for row in read_jsonl(path)}
        self.next = 1 + max((int(i.rsplit("-c", 1)[1]) for i in self.ids.values()), default=0)
        self.changed = False

    def fingerprint(self, item: dict[str, Any], chunk: Chunk) -> str:
        return sha256_hex(canonical_bytes({
            "concept_sha256": self.concept_hash, "paper_id": chunk.paper_id, "start": chunk.start,
            "end": chunk.end, "row": item["extracted_row"], "fact": item["fact"], "s": item["s"], "p": item["p"],
            "o": item["o"], "quote": item.get("first_quote", item["quote"])}))

    def get(self, fingerprint: str) -> str:
        if fingerprint not in self.ids:
            self.ids[fingerprint] = f"{self.qid}-c{self.next:06d}"
            self.next += 1
            self.changed = True
        return self.ids[fingerprint]

    def save(self) -> None:
        if self.changed:
            write_jsonl(self.path, ({"fingerprint": f, "id": i} for f, i in self.ids.items()))
            self.changed = False


# --- row merging -------------------------------------------------------------------------------------

def norm(value: Any) -> str:
    """Key form of a value: NFKC, casefold, letters and digits only; the casefolded text if none."""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    return "".join(ch for ch in text if ch.isalnum()) or text.strip()


def _is_list(type_name: str) -> bool:
    return type_name.startswith("list<")


def key_column(columns: list[dict[str, str]]) -> str | None:
    """The first string-valued column (string, date or a class label), the table's merge key."""
    return next((c["name"] for c in columns if not _is_list(c["type"]) and c["type"] not in NUMERIC), None)


def _forms(name: str) -> set[str]:
    """A list column's name and its singular (papers -> paper, studies -> study)."""
    if name.endswith("ies"):
        return {name, name[:-3] + "y"}
    return {name, name[:-1]} if name.endswith("s") else {name}


def counts_list(column: str, list_name: str) -> bool:
    """Is the integer column `column` named as the count of the list column `list_name`?
    paper_count, papers_count, num_papers, n_papers, number_of_papers, total_papers; or a name that
    ends in the plural list name itself (first_author_papers)."""
    tokens = [t for t in column.split("_") if t and t != "of"]
    forms = _forms(list_name)
    if len(tokens) == 2 and ({tokens[0], tokens[1]} & COUNT_WORDS) and ({tokens[0], tokens[1]} & forms):
        return True
    return list_name.endswith("s") and len(tokens) > 1 and tokens[-1] == list_name


def count_columns(columns: list[dict[str, str]]) -> dict[str, str]:
    """integer column -> the list column it counts (see the module docstring)."""
    lists = [c["name"] for c in columns if _is_list(c["type"])]
    out: dict[str, str] = {}
    for col in columns:
        if col["type"] != "integer":
            continue
        hits = [name for name in lists if counts_list(col["name"], name)]
        if not hits and col["name"] in COUNT_WORDS and len(lists) == 1:
            hits = lists
        if len(hits) == 1:
            out[col["name"]] = hits[0]
    return out


def _union(values: list[Any]) -> list[Any]:
    seen: dict[str, Any] = {}
    for listed in values:
        for item in listed or []:
            seen.setdefault(norm(item), item)
    return list(seen.values())


def merge_cells(columns: list[dict[str, str]], rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, list]]:
    """Cells of several rows as one: list columns unioned, counts of a list recomputed, else first non-null.

    A recomputed count lists under `conflicts` (after the recomputed value, which is kept) every
    extracted count that disagrees with its own row: with the length of that row's list, or, for a
    row that listed nothing, with the recomputed count. Counts that differ only because rows were
    merged (1 and 1 from two papers, 2 after the union) are not conflicts."""
    counts = count_columns(columns)
    cells: dict[str, Any] = {}
    conflicts: dict[str, list[Any]] = {}
    for col in columns:
        name = col["name"]
        values = [row.get(name) for row in rows]
        if _is_list(col["type"]):
            cells[name] = _union(values)
            continue
        present = [v for v in values if v is not None]
        cells[name] = present[0] if present else None
        distinct = list({norm(v): v for v in reversed(present)}.values())[::-1]
        if len(distinct) > 1:
            conflicts[name] = distinct
    for name, listed in counts.items():
        if not cells[listed]:
            continue  # nothing listed: the extracted count stands (first value, conflicts as above)
        recomputed = len(cells[listed])
        odd: list[Any] = []
        for row in rows:
            own, value = _union([row.get(listed)]), row.get(name)
            if value is not None and value != (len(own) if own else recomputed) and value not in odd:
                odd.append(value)
        cells[name] = recomputed
        conflicts.pop(name, None)
        if odd:
            conflicts[name] = [recomputed, *odd]
    return cells, conflicts


def _edge_spec(shape: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    wanted = (row["source_type"], row["predicate"], row["target_type"])
    for edge in shape["edges"]:
        if (edge["source"], edge["predicate"], edge["target"]) == wanted:
            return edge
    return {"attributes": [{"name": n, "type": "string"} for n in row.get("attributes") or {}]}


def row_key(shape: dict[str, Any], row: dict[str, Any]) -> str | None:
    """The merge key of an extracted row; None for a row that is never merged (no key value)."""
    if shape["kind"] == "graph":
        if row.get("source") is None or row.get("target") is None:
            return None
        return (f"{row['source_type']}:{norm(row['source'])} {row['predicate']} "
                f"{row['target_type']}:{norm(row['target'])}")
    column = key_column(shape["columns"])
    if column is None:
        return canonical({k: [norm(x) for x in v] if isinstance(v, list) else (None if v is None else norm(v))
                          for k, v in row.items()})
    return None if row.get(column) is None else norm(row[column])


def merge_rows(concept: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group candidates (dicts with id, paper_id, chunk, extracted_row, row) into merged answer rows:
    [{key, cells, candidates, papers, conflicts?}] in order of first appearance."""
    shape = concept["answer_shape"]
    groups: dict[Any, list[dict[str, Any]]] = {}
    for item in items:
        key = row_key(shape, item["row"])
        groups.setdefault(key if key is not None else ("unkeyed", item["paper_id"], item["chunk"],
                                                        item.get("piece", ""), item["extracted_row"]),
                          []).append(item)
    out = []
    for key, members in groups.items():
        rows = [m["row"] for m in members]
        if shape["kind"] == "table":
            cells, conflicts = merge_cells(shape["columns"], rows)
        else:
            first = rows[0]
            attributes, conflicts = merge_cells(_edge_spec(shape, first).get("attributes", []),
                                                [r.get("attributes") or {} for r in rows])
            cells = {k: first[k] for k in ("source", "source_type", "predicate", "target", "target_type")}
            cells["attributes"] = attributes
        entry: dict[str, Any] = {"key": key if isinstance(key, str) else None, "cells": cells,
                                 "candidates": [m["id"] for m in members],
                                 "papers": list(dict.fromkeys(m["paper_id"] for m in members))}
        if conflicts:
            entry["conflicts"] = conflicts
        out.append(entry)
    return out


# --- progress ----------------------------------------------------------------------------------------

def _clock(seconds: float) -> str:
    seconds = int(max(0, seconds))
    return f"{seconds // 3600:d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


@dataclass
class Progress:
    """progress.json while a build runs (read by `gold status` and the web app), and a log line about
    every 5% of the papers. It names the process (pid, host) and the call timeout, so a reader can
    tell a build that died without a word (SIGKILL) from one that is waiting on slow calls."""
    path: Path
    qid: str
    log: Callable[[str], None] = print
    caller: Caller | None = None
    call_timeout_s: float = 300.0
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.started = monotonic()
        self.started_at = utc_now()
        self.last_write = 0.0
        self.state = {"qid": self.qid, "stage": "starting", "pid": os.getpid(), "host": socket.gethostname(),
                      "call_timeout_s": self.call_timeout_s,
                      "papers": {"total": 0, "done": 0, **dict.fromkeys(STATUSES, 0)},
                      "chunks": {"total": 0, "screened": 0, "relevant": 0, "screen_errors": 0,
                                 "extracted": 0, "extraction_errors": 0, "retry_errors": 0, "split": 0},
                      "candidates": 0}

    def stage(self, name: str, **extra: Any) -> None:
        self.state.update(stage=name, **extra)
        self.write(force=True)

    def chunk(self, key: str, amount: int = 1) -> None:
        self.state["chunks"][key] += amount
        self.write()

    def paper(self, status: str, candidates: int) -> None:
        papers = self.state["papers"]
        papers["done"] += 1
        papers[status] += 1
        self.state["candidates"] += candidates
        step = max(1, papers["total"] // 20)
        if papers["done"] % step == 0 or papers["done"] == papers["total"]:
            self.log(self.line())
        self.write()

    def eta(self) -> float | None:
        done, total = self.state["papers"]["done"], self.state["papers"]["total"]
        return (monotonic() - self.started) / done * (total - done) if done and total > done else None

    def line(self) -> str:
        p, c = self.state["papers"], self.state["chunks"]
        calls = self.caller.counters if self.caller else None
        eta = self.eta()
        return (f"[{_clock(monotonic() - self.started)}] {self.qid}: papers {p['done']}/{p['total']} "
                f"(relevant {p['relevant']}, error {p['error']}) · chunks screened {c['screened']}/{c['total']}, "
                f"extracted {c['extracted']} · candidates {self.state['candidates']}"
                + (f" · calls {calls.made} (cached {calls.cached}, failed {calls.failed})" if calls else "")
                + (f" · about {_clock(eta)} left" if eta is not None else ""))

    def write(self, force: bool = False) -> None:
        now = monotonic()
        if not force and now - self.last_write < 2.0:
            return
        self.last_write = now
        eta = self.eta()
        data = {**self.state, "started_at": self.started_at, "updated_at": utc_now(),
                "elapsed_s": round(now - self.started), "eta_s": round(eta) if eta is not None else None}
        if self.caller is not None:
            data["model_calls"] = self.caller.counters.json()
        try:
            write_json(self.path, data)
        except OSError:
            pass  # progress is advisory


def _parse_time(stamp: str) -> datetime | None:
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)  # signal 0: existence check (POSIX only; on Windows it would end the process)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # exists, owned by someone else
    return True


def live_stage(progress: dict[str, Any], now: datetime | None = None) -> str:
    """The stage of progress.json as it is now: a build that claims to run (starting, building,
    writing) is `dead` when its process is gone (same host, POSIX) and `stale` when progress.json has
    not changed for twice the call timeout plus a minute (the longest quiet stretch of a live build)."""
    stage = progress.get("stage") or "not started"
    if stage not in ("starting", "building", "writing"):
        return stage
    if os.name == "posix" and progress.get("host") == socket.gethostname() and isinstance(progress.get("pid"), int) \
            and not _alive(progress["pid"]):
        return "dead"
    updated = _parse_time(progress.get("updated_at"))
    limit = 2 * float(progress.get("call_timeout_s") or 300) + 60
    if updated is not None and ((now or datetime.now(timezone.utc)) - updated).total_seconds() > limit:
        return "stale"
    return stage


# --- the build ---------------------------------------------------------------------------------------

def select_papers(corpus: GoldCorpus, settings: BuildSettings) -> list[str]:
    papers = corpus.papers
    if settings.only_papers:
        only = set(settings.only_papers)
        unknown = sorted(only - set(papers))
        if unknown:
            raise ValueError(f"not in the manifest: {', '.join(unknown)}")
        papers = [p for p in papers if p in only]
    return papers[:settings.max_papers] if settings.max_papers is not None else papers


async def _all(aws: Iterable[Awaitable[Any]]) -> list[Any]:
    """gather that lets every sibling finish before the first error is raised (no orphaned calls)."""
    results = await asyncio.gather(*aws, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return results


@dataclass
class _Build:
    task: Task
    corpus: GoldCorpus
    settings: BuildSettings
    caller: Caller
    progress: Progress

    def __post_init__(self) -> None:
        self.prompt, self.output_type = extract.extract_prompt(self.task.concept)

    async def screen(self, chunk: Chunk, parts: int, text: str) -> dict[str, Any]:
        """Screening of a chunk (or piece) of the paper `text`; a too-long one is screened in halves."""
        try:
            return await screen.screen_chunk(self.caller, self.task, chunk, parts, text[chunk.start:chunk.end])
        except CallError as exc:
            halves = halve(text, chunk) if exc.kind == "too_long" else None
            if halves is None:
                raise
        results = await _all(self.screen(h, parts, text) for h in halves)
        relevant = any(r["status"] == "relevant" for r in results)
        return {**{k: results[0][k] for k in ("model", "served_model", "prompt_sha256", "cached")},
                "chunk": chunk.chunk, "status": "relevant" if relevant else "not_relevant",
                "findings": [f for r in results for f in r["findings"]],
                "pieces": [p for r, h in zip(results, halves, strict=True) for p in r.get("pieces") or [h.piece]]}

    async def extract(self, chunk: Chunk, parts: int, text: str) -> tuple[list[dict[str, Any]], list[str]]:
        """(candidates, pieces) of a relevant chunk (or piece); a too-long one is extracted in halves."""
        try:
            found = await extract.extract_chunk(self.caller, self.task, self.prompt, self.output_type, chunk,
                                                parts, text[chunk.start:chunk.end], self.corpus)
        except CallError as exc:
            halves = halve(text, chunk) if exc.kind == "too_long" else None
            if halves is None:
                raise
            results = await _all(self.extract(h, parts, text) for h in halves)
            return [c for found, _ in results for c in found], [p for _, pieces in results for p in pieces]
        for item in found:
            item["_chunk"] = chunk
        return found, [chunk.piece]

    async def chunk(self, chunk: Chunk, parts: int, text: str) -> dict[str, Any]:
        """Screen one chunk and, when relevant, extract it: {screen, candidates, extraction_error?, split?}."""
        try:
            screened = await self.screen(chunk, parts, text)
        except CallError as exc:
            self.progress.chunk("screen_errors")
            return {"screen": {"chunk": chunk.chunk, "status": "error", "error": exc.reason,
                               "too_long": exc.kind == "too_long"}, "candidates": []}
        self.progress.chunk("screened")
        if screened.get("pieces"):
            self.progress.chunk("split")
        if screened["status"] != "relevant":
            return {"screen": screened, "candidates": []}
        self.progress.chunk("relevant")
        try:
            found, pieces = await self.extract(chunk, parts, text)
        except CallError as exc:
            self.progress.chunk("extraction_errors")
            return {"screen": screened, "candidates": [], "extraction_error": exc.reason,
                    "extraction_too_long": exc.kind == "too_long"}
        self.progress.chunk("extracted")
        if any(extract.retry_failed(c) for c in found):
            self.progress.chunk("retry_errors")
        if len(pieces) > 1 and not screened.get("pieces"):
            self.progress.chunk("split")
        return {"screen": screened, "candidates": found, "split": len(pieces) > 1}

    async def paper(self, paper_id: str) -> dict[str, Any]:
        """{record (the screening.jsonl line), chunks, candidates}."""
        file = self.corpus.file(paper_id)
        if paper_id in self.corpus.failures:
            return self._done(screen.paper_record(paper_id, file, [], no_text=f"conversion failed: "
                                                  f"{self.corpus.failures[paper_id]}"), [], [])
        try:
            text = await asyncio.to_thread(self.corpus.text, paper_id)
        except Rejected as exc:
            return self._done(screen.paper_record(paper_id, file, [], error=exc.reason), [], [])
        except OSError as exc:
            return self._done(screen.paper_record(paper_id, file, [], error=f"unreadable: {type(exc).__name__}"),
                              [], [])
        chunks = paper_chunks(paper_id, text, self.settings.chunk_chars)
        if not chunks:
            return self._done(screen.paper_record(paper_id, file, [], no_text="empty file"), [], [])
        self.progress.state["chunks"]["total"] += len(chunks)
        results = await asyncio.gather(*(self.chunk(c, len(chunks), text) for c in chunks))
        record = screen.paper_record(paper_id, file, [r["screen"] for r in results])
        record["chunks_split"] = sorted(set(record["chunks_split"]) |
                                        {r["screen"]["chunk"] for r in results if r.get("split")})
        failed = [r for r in results if "extraction_error" in r]
        if failed:
            record["extraction_errors"] = [r["screen"]["chunk"] for r in failed]
            record["extraction_too_long"] = [r["screen"]["chunk"] for r in failed if r["extraction_too_long"]]
            record["extraction_error"] = "; ".join(f"chunk {r['screen']['chunk']}: {r['extraction_error']}"
                                                   for r in failed)[:1000]
        candidates = [c for r in results for c in r["candidates"]]
        retry_errors = sorted({c["chunk"] for c in candidates if extract.retry_failed(c)})
        if retry_errors:
            record["retry_errors"] = retry_errors
        return self._done(record, chunks, candidates)

    def _done(self, record: dict[str, Any], chunks: list[Chunk], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        record["candidates"] = len(candidates)
        self.progress.paper(record["status"], len(candidates))
        return {"record": record, "chunks": chunks, "candidates": candidates}

    async def run(self, papers: list[str]) -> list[dict[str, Any]]:
        open_papers = asyncio.Semaphore(2 * max(1, self.settings.concurrency))

        async def one(paper_id: str) -> dict[str, Any]:
            async with open_papers:
                return await self.paper(paper_id)

        return list(await asyncio.gather(*(one(p) for p in papers)))


def counts(candidates: list[dict[str, Any]], records: list[dict[str, Any]], rows: list[dict[str, Any]],
           caller: Caller) -> dict[str, Any]:
    rejected = Counter(c["anchor_status"] for c in candidates if c["anchor_status"] != "ok")
    retried = [c for c in candidates if c.get("attempts", 1) > 1]
    return {
        "chunks": sum(r["chunks"] for r in records),
        "chunks_relevant": sum(len(r["chunks_relevant"]) for r in records),
        "chunks_error": sum(len(r["chunks_error"]) for r in records),
        "extraction_errors": sum(len(r.get("extraction_errors", [])) for r in records),
        "retry_errors": sum(extract.retry_failed(c) for c in candidates),
        "too_long": sum(len(r.get("chunks_too_long", [])) + len(r.get("extraction_too_long", [])) for r in records),
        "papers_unreadable": sum(r["status"] == "error" and not r["chunks"] for r in records),
        "split_chunks": sum(len(r.get("chunks_split", [])) for r in records),
        "candidates": len(candidates),
        "anchored": sum(c["anchor_status"] == "ok" for c in candidates),
        "rejected": dict(sorted(rejected.items())),
        "retried": len(retried),
        "fixed_by_retry": sum(c["anchor_status"] == "ok" for c in retried),
        "rows": len(rows),
        "papers_with_candidates": sum(r["candidates"] > 0 for r in records),
        "model_calls": caller.counters.json(),
    }


def outcome(doc: dict[str, Any]) -> tuple[int, str]:
    """(exit code, what to do) of a built D: 0 complete; 1 calls failed that a rerun retries; 3 only
    failures a rerun cannot fix (a piece still too long, a paper that cannot be read)."""
    c = doc["counts"]
    retryable = c["chunks_error"] + c["extraction_errors"] - c.get("too_long", 0) + c.get("retry_errors", 0)
    if retryable:
        return 1, (f"{retryable} failed calls ({c['chunks_error']} screenings, {c['extraction_errors']} extractions, "
                   f"{c.get('retry_errors', 0)} quote retries): run `gold build {doc['qid']}` again to retry them")
    permanent = c.get("too_long", 0) + c.get("papers_unreadable", 0)
    if permanent:
        return 3, (f"{c.get('too_long', 0)} chunks too long even in pieces, {c.get('papers_unreadable', 0)} papers "
                   "unreadable: a rerun cannot fix these (a smaller GOLD_CHUNK_CHARS can fix the first, "
                   "the corpus the second)")
    return 0, ""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def claim_folder(qdir: QuestionDir, concept_hash: str, partial: bool, replace: bool,
                 log: Callable[[str], None]) -> None:
    """Refuse (FolderInUse) a build that would silently replace the folder's D: one for another concept
    (its ids, triage, pool and keys were judged under that concept) or a trial over a whole-corpus D.
    With `replace`: the other concept's files move to superseded/<concept sha256[:12]>-<time>/ (all but
    the call cache and ids.jsonl, which are keyed by concept); a trial simply rewrites D (a later full
    build restores it from the cache without model calls)."""
    old = _load_json(qdir.doc)
    if not isinstance(old, dict):
        return
    if old.get("concept_sha256") != concept_hash:
        title = (old.get("concept") or {}).get("title")
        if not replace:
            raise FolderInUse(
                f"{qdir.root} holds D for another concept ({str(old.get('concept_sha256'))[:12]}, {title!r}): its "
                "candidate ids, triage labels, pool and keys were judged under it. Pass --replace to move it all to "
                f"{qdir.superseded.name}/ (the call cache stays), or build into another --out")
        dest = qdir.superseded / f"{str(old.get('concept_sha256'))[:12]}-{utc_now()[:19].replace(':', '')}"
        dest.mkdir(parents=True, exist_ok=True)
        for entry in sorted(qdir.root.iterdir()):
            if entry.name not in KEEP_ON_REPLACE:
                shutil.move(str(entry), str(dest / entry.name))
        log(f"{qdir.qid}: D for concept {title!r} and everything made from it moved to {dest}")
    elif partial and not (old.get("coverage") or {}).get("partial", True) and not replace:
        raise FolderInUse(
            f"{qdir.root} holds D over the whole corpus; this trial would replace it with a subset that triage, "
            "pool and draft would then use. Build the trial into another --out, or pass --replace (a full "
            "`gold build` afterwards restores the whole D from the cache without model calls)")


async def _build(task: Task, corpus: GoldCorpus, qdir: QuestionDir, rotation: llm.Rotation,
                 settings: BuildSettings, log: Callable[[str], None], replace: bool) -> dict[str, Any]:
    papers = select_papers(corpus, settings)
    concept_hash = concept_sha256(task.concept)
    claim_folder(qdir, concept_hash, len(papers) < len(corpus.papers), replace, log)
    previous = _load_json(qdir.doc)
    invocations = list(((previous or {}).get("built") or {}).get("invocations") or [])
    started_at, clock = utc_now(), monotonic()
    git = git_state(log)
    progress = Progress(qdir.progress, task.qid, log, call_timeout_s=settings.call_timeout_s)
    cache = llm.JsonlCache(qdir.cache)
    if cache.skipped:
        log(f"{task.qid}: skipped {cache.skipped} cut lines of {qdir.cache} (their calls are made again)")
    caller = Caller(rotation, cache, concurrency=settings.concurrency, timeout_s=settings.call_timeout_s,
                    temperature=settings.temperature, seed=settings.seed, on_change=progress.write)
    progress.caller = caller
    progress.state["papers"]["total"] = len(papers)
    progress.stage("building")
    log(f"{task.qid}: {len(papers)} of {len(corpus.papers)} papers, {settings.concurrency} calls at a time, "
        f"chunks of at most {settings.chunk_chars} characters -> {qdir.root}")
    work = _Build(task, corpus, settings, caller, progress)
    loop, main = asyncio.get_running_loop(), asyncio.current_task()
    signals: list[str] = []

    def on_sigterm() -> None:  # Slurm's time limit: stop the calls, say so in progress.json
        signals.append("SIGTERM")
        if main is not None:
            main.cancel()

    try:
        loop.add_signal_handler(signal.SIGTERM, on_sigterm)
    except (NotImplementedError, RuntimeError, ValueError, AttributeError):
        pass  # Windows, or not the main thread: progress.json may then outlive a killed build (`gold status`: dead)
    try:
        done = await work.run(papers)
    except asyncio.CancelledError:
        progress.stage("stopped", reason=signals[0] if signals else "cancelled")
        if signals:
            raise BuildStopped(f"{task.qid}: stopped by {signals[0]}; run `gold build {task.qid}` again to resume") \
                from None
        raise
    except BaseException:
        progress.stage("failed")
        raise
    finally:
        try:
            loop.remove_signal_handler(signal.SIGTERM)
        except (NotImplementedError, RuntimeError, ValueError, AttributeError):
            pass
    progress.stage("writing")

    registry = IdRegistry(qdir.ids, task.qid, concept_hash)
    candidates: list[dict[str, Any]] = []
    for item in (c for d in done for c in d["candidates"]):
        chunk = item.pop("_chunk")
        candidates.append({"id": registry.get(registry.fingerprint(item, chunk)), **item})
    registry.save()
    records = [d["record"] for d in done]
    rows = merge_rows(task.concept, candidates)
    by_id = {c["id"]: c for c in candidates}
    for row in rows:
        row["anchored"] = sum(by_id[i]["anchor_status"] == "ok" for i in row["candidates"])
    coverage = Counter(r["status"] for r in records)
    ended_at = utc_now()
    calls = caller.counters
    invocations.append({"started_at": started_at, "ended_at": ended_at, "seconds": round(monotonic() - clock, 1),
                        "papers": len(papers), "made": calls.made, "cached": calls.cached, "failed": calls.failed,
                        "too_long": calls.too_long, "input_tokens": calls.input_tokens,
                        "output_tokens": calls.output_tokens, "git_commit": git["commit"]})
    doc = {
        "qid": task.qid, "question": task.question, "concept_sha256": concept_hash,
        "kind": task.concept["answer_shape"]["kind"], "concept": task.concept,
        "built": {
            "git_commit": git["commit"], "git": git,
            "models": {"aliases": [llm.model_name(m) for m in rotation.models], "served": sorted(caller.served),
                       "model_key": caller.model_key, "base_url": llm.base_url(),
                       "identity": "model_key is the pinned name@revision (agent/rundir.SUBAGENTS), not observed"},
            "prompts": {"screen": screen.PROMPT.json(), "extract": work.prompt.json(),
                        "retry": extract.RETRY_PROMPT.json()},
            "settings": settings.json(),
            "started_at": started_at, "ended_at": ended_at,
            "invocations": invocations,
            "corpus": {"root": str(corpus.root), "manifest_sha256": corpus.manifest_sha256,
                       "papers": len(corpus.papers)},
            "screening_scope": "every chunk of every selected paper (chunks cut at headings), no ranker",
            "extraction_scope": "every chunk the screening marked relevant",
        },
        "coverage": {"papers": len(records), **{s: coverage.get(s, 0) for s in STATUSES},
                     "papers_in_corpus": len(corpus.papers), "partial": len(records) < len(corpus.papers)},
        "rows": rows,
        "counts": {**counts(candidates, records, rows, caller),
                   "cost": {"invocations": len(invocations),
                            "seconds": round(sum(i["seconds"] for i in invocations), 1),
                            "calls_made": sum(i["made"] for i in invocations),
                            "input_tokens": sum(i["input_tokens"] for i in invocations),
                            "output_tokens": sum(i["output_tokens"] for i in invocations)}},
    }
    write_jsonl(qdir.chunks, (c.json() for d in done for c in d["chunks"]))
    write_jsonl(qdir.screening, records)
    write_jsonl(qdir.candidates, candidates)
    write_json(qdir.doc, doc)
    _replace(qdir.doc_md, docmd.render(doc, candidates, records))
    progress.stage("done", ended_at=ended_at)
    log(progress.line())
    log(f"{task.qid}: {len(candidates)} candidates ({doc['counts']['anchored']} anchored), {len(rows)} rows "
        f"-> {qdir.doc}")
    return doc


def build(qid: str, concept: dict[str, Any], corpus: GoldCorpus, out_root: Path, *, rotation: llm.Rotation,
          settings: BuildSettings | None = None, question: str | None = None,
          log: Callable[[str], None] = print, replace: bool = False) -> dict[str, Any]:
    """Build D for one question into out_root/<qid>/ and return doc.json's content."""
    task = Task(qid, question, concept)
    return asyncio.run(_build(task, corpus, QuestionDir(Path(out_root) / qid), rotation,
                              settings or BuildSettings.from_env(), log, replace))


def load_doc(qdir: QuestionDir) -> dict[str, Any]:
    if not qdir.doc.exists():
        raise FileNotFoundError(f"{qdir.doc} does not exist: run `gold build {qdir.root.name}` first")
    return json.loads(qdir.doc.read_text(encoding="utf-8"))


def doc_state(doc: dict[str, Any]) -> dict[str, Any]:
    """What a draft key or a review pool records about the D it was made from (and refuses on)."""
    cov, c, settings = doc["coverage"], doc["counts"], doc["built"]["settings"]
    return {"papers": cov["papers"], "papers_in_corpus": cov.get("papers_in_corpus"), "partial": cov.get("partial"),
            "error": cov["error"], "chunks_error": c["chunks_error"], "extraction_errors": c["extraction_errors"],
            "retry_errors": c.get("retry_errors", 0), "too_long": c.get("too_long", 0),
            "max_papers": settings.get("max_papers"), "only_papers": settings.get("only_papers"),
            "built_at": doc["built"].get("ended_at")}


def incomplete(state: dict[str, Any]) -> str | None:
    """Why a D (as doc_state gives it) is not complete, or None."""
    reasons = []
    if state["partial"]:
        reasons.append(f"a trial over {state['papers']} of {state['papers_in_corpus']} papers")
    failed = state["error"] + state["chunks_error"] + state["extraction_errors"] + state["retry_errors"]
    if failed:
        reasons.append(f"failed calls or papers ({state['error']} papers in error, {state['chunks_error']} screenings, "
                       f"{state['extraction_errors']} extractions, {state['retry_errors']} quote retries)")
    return "; ".join(reasons) or None


def file_hash(path: Path) -> str | None:
    return file_sha256(path) if path.exists() else None
