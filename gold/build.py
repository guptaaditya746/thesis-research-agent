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
finished one is rebuilt without model calls, and a trial's papers are not paid for again. Failed
calls are not cached: run the build again to retry them (`coverage.error`, `counts.chunks_error`).

Outputs in $GOLD/<qid>/ (rewritten whole at the end of each build): chunks.jsonl, screening.jsonl,
candidates.jsonl, doc.json, doc.md; progress.json while it runs; ids.jsonl keeps candidate ids stable
(`<qid>-c000001` always names the same extracted fact, so triage labels survive a wider rebuild).

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
import subprocess
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import monotonic
from typing import Any

from agent.broker import Rejected
from agent.canonical import canonical, canonical_bytes, file_sha256, sha256_hex
from agent.concept import concept_sha256
from agent.rundir import git_head, utc_now

from . import docmd, extract, llm, screen
from .calls import Caller, CallError
from .chunks import MAX_CHARS, Chunk, GoldCorpus, paper_chunks
from .screen import Task

REPO = Path(__file__).resolve().parents[1]
STATUSES = ("relevant", "not_relevant", "no_text", "error")
NUMERIC = ("integer", "number", "boolean")
COUNT_WORDS = frozenset({"count", "n", "num", "number", "total"})


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
        self.pool = self.root / "pool.jsonl"
        self.strata = self.root / "pool.strata.json"
        self.draft = self.root / "key.draft.json"
        self.key = self.root / "key.json"
        self.cache = self.root / "cache.jsonl"
        self.progress = self.root / "progress.json"
        self.ids = self.root / "ids.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _replace(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data.encode("utf-8"))  # bytes: LF on every platform
    tmp.replace(path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _replace(path, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))


def write_json(path: Path, obj: Any) -> None:
    _replace(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def git_commit() -> str | None:
    try:
        return git_head(REPO)
    except (OSError, subprocess.CalledProcessError):
        return None


# --- candidate ids -----------------------------------------------------------------------------------

class IdRegistry:
    """ids.jsonl: each extracted fact's fingerprint gets `<qid>-cNNNNNN` once and keeps it.

    Numbering in output order alone would renumber everything when a trial on 20 papers is followed
    by the full build, silently re-pointing triage labels at other facts."""

    def __init__(self, path: Path, qid: str) -> None:
        self.path, self.qid = path, qid
        self.ids = {row["fingerprint"]: row["id"] for row in read_jsonl(path)}
        self.next = 1 + max((int(i.rsplit("-c", 1)[1]) for i in self.ids.values()), default=0)
        self.new: list[dict[str, str]] = []

    @staticmethod
    def fingerprint(item: dict[str, Any], chunk: Chunk) -> str:
        return sha256_hex(canonical_bytes({
            "paper_id": chunk.paper_id, "start": chunk.start, "end": chunk.end, "row": item["extracted_row"],
            "fact": item["fact"], "s": item["s"], "p": item["p"], "o": item["o"],
            "quote": item.get("first_quote", item["quote"])}))

    def get(self, fingerprint: str) -> str:
        if fingerprint not in self.ids:
            self.ids[fingerprint] = f"{self.qid}-c{self.next:06d}"
            self.next += 1
            self.new.append({"fingerprint": fingerprint, "id": self.ids[fingerprint]})
        return self.ids[fingerprint]

    def save(self) -> None:
        if self.new:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.writelines(json.dumps(row, sort_keys=True) + "\n" for row in self.new)
            self.new = []


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
                                                        item["extracted_row"]), []).append(item)
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
    every 5% of the papers."""
    path: Path
    qid: str
    log: Callable[[str], None] = print
    caller: Caller | None = None
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.started = monotonic()
        self.started_at = utc_now()
        self.last_write = 0.0
        self.state = {"qid": self.qid, "stage": "starting",
                      "papers": {"total": 0, "done": 0, **dict.fromkeys(STATUSES, 0)},
                      "chunks": {"total": 0, "screened": 0, "relevant": 0, "screen_errors": 0,
                                 "extracted": 0, "extraction_errors": 0},
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


# --- the build ---------------------------------------------------------------------------------------

def select_papers(corpus: GoldCorpus, settings: BuildSettings) -> list[str]:
    papers = corpus.papers
    if settings.only_papers:
        only = set(settings.only_papers)
        unknown = sorted(only - set(papers))
        if unknown:
            raise ValueError(f"not in the manifest: {', '.join(unknown)}")
        papers = [p for p in papers if p in only]
    return papers[:settings.max_papers] if settings.max_papers else papers


@dataclass
class _Build:
    task: Task
    corpus: GoldCorpus
    settings: BuildSettings
    caller: Caller
    progress: Progress

    def __post_init__(self) -> None:
        self.prompt, self.output_type = extract.extract_prompt(self.task.concept)

    async def chunk(self, chunk: Chunk, parts: int, text: str) -> dict[str, Any]:
        """Screen one chunk and, when relevant, extract it: {screen, candidates, extraction_error?}."""
        try:
            screened = await screen.screen_chunk(self.caller, self.task, chunk, parts, text)
        except CallError as exc:
            self.progress.chunk("screen_errors")
            return {"screen": {"chunk": chunk.chunk, "status": "error", "error": exc.reason}, "candidates": []}
        self.progress.chunk("screened")
        if screened["status"] != "relevant":
            return {"screen": screened, "candidates": []}
        self.progress.chunk("relevant")
        try:
            found = await extract.extract_chunk(self.caller, self.task, self.prompt, self.output_type, chunk,
                                                parts, text, self.corpus)
        except CallError as exc:
            self.progress.chunk("extraction_errors")
            return {"screen": screened, "candidates": [], "extraction_error": exc.reason}
        self.progress.chunk("extracted")
        for item in found:
            item["_chunk"] = chunk
        return {"screen": screened, "candidates": found}

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
        results = await asyncio.gather(*(self.chunk(c, len(chunks), text[c.start:c.end]) for c in chunks))
        record = screen.paper_record(paper_id, file, [r["screen"] for r in results])
        failed = [r["screen"]["chunk"] for r in results if "extraction_error" in r]
        if failed:
            record["extraction_errors"] = failed
            record["extraction_error"] = "; ".join(f"chunk {r['screen']['chunk']}: {r['extraction_error']}"
                                                   for r in results if "extraction_error" in r)[:1000]
        return self._done(record, chunks, [c for r in results for c in r["candidates"]])

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
        "candidates": len(candidates),
        "anchored": sum(c["anchor_status"] == "ok" for c in candidates),
        "rejected": dict(sorted(rejected.items())),
        "retried": len(retried),
        "fixed_by_retry": sum(c["anchor_status"] == "ok" for c in retried),
        "rows": len(rows),
        "papers_with_candidates": sum(r["candidates"] > 0 for r in records),
        "model_calls": caller.counters.json(),
    }


async def _build(task: Task, corpus: GoldCorpus, qdir: QuestionDir, rotation: llm.Rotation,
                 settings: BuildSettings, log: Callable[[str], None]) -> dict[str, Any]:
    started_at = utc_now()
    progress = Progress(qdir.progress, task.qid, log)
    caller = Caller(rotation, llm.JsonlCache(qdir.cache), concurrency=settings.concurrency,
                    timeout_s=settings.call_timeout_s, temperature=settings.temperature, seed=settings.seed,
                    on_change=progress.write)
    progress.caller = caller
    papers = select_papers(corpus, settings)
    progress.state["papers"]["total"] = len(papers)
    progress.stage("building")
    log(f"{task.qid}: {len(papers)} of {len(corpus.papers)} papers, {settings.concurrency} calls at a time, "
        f"chunks of at most {settings.chunk_chars} characters -> {qdir.root}")
    work = _Build(task, corpus, settings, caller, progress)
    try:
        done = await work.run(papers)
    except BaseException:
        progress.stage("failed")
        raise
    progress.stage("writing")

    registry = IdRegistry(qdir.ids, task.qid)
    candidates: list[dict[str, Any]] = []
    for item in (c for d in done for c in d["candidates"]):
        chunk = item.pop("_chunk")
        candidates.append({"id": registry.get(IdRegistry.fingerprint(item, chunk)), **item})
    registry.save()
    records = [d["record"] for d in done]
    rows = merge_rows(task.concept, candidates)
    by_id = {c["id"]: c for c in candidates}
    for row in rows:
        row["anchored"] = sum(by_id[i]["anchor_status"] == "ok" for i in row["candidates"])
    coverage = Counter(r["status"] for r in records)
    doc = {
        "qid": task.qid, "question": task.question, "concept_sha256": concept_sha256(task.concept),
        "kind": task.concept["answer_shape"]["kind"], "concept": task.concept,
        "built": {
            "git_commit": git_commit(),
            "models": {"aliases": [llm.model_name(m) for m in rotation.models], "served": sorted(caller.served),
                       "model_key": caller.model_key, "base_url": llm.base_url()},
            "prompts": {"screen": screen.PROMPT.json(), "extract": work.prompt.json(),
                        "retry": extract.RETRY_PROMPT.json()},
            "settings": settings.json(),
            "started_at": started_at, "ended_at": utc_now(),
            "corpus": {"root": str(corpus.root), "manifest_sha256": corpus.manifest_sha256,
                       "papers": len(corpus.papers)},
            "screening_scope": "every chunk of every selected paper (chunks cut at headings), no ranker",
            "extraction_scope": "every chunk the screening marked relevant",
        },
        "coverage": {"papers": len(records), **{s: coverage.get(s, 0) for s in STATUSES},
                     "papers_in_corpus": len(corpus.papers), "partial": len(records) < len(corpus.papers)},
        "rows": rows,
        "counts": counts(candidates, records, rows, caller),
    }
    write_jsonl(qdir.chunks, (c.json() for d in done for c in d["chunks"]))
    write_jsonl(qdir.screening, records)
    write_jsonl(qdir.candidates, candidates)
    write_json(qdir.doc, doc)
    _replace(qdir.doc_md, docmd.render(doc, candidates, records))
    progress.stage("done", ended_at=doc["built"]["ended_at"])
    log(progress.line())
    log(f"{task.qid}: {len(candidates)} candidates ({doc['counts']['anchored']} anchored), {len(rows)} rows "
        f"-> {qdir.doc}")
    return doc


def build(qid: str, concept: dict[str, Any], corpus: GoldCorpus, out_root: Path, *, rotation: llm.Rotation,
          settings: BuildSettings | None = None, question: str | None = None,
          log: Callable[[str], None] = print) -> dict[str, Any]:
    """Build D for one question into out_root/<qid>/ and return doc.json's content."""
    task = Task(qid, question, concept)
    return asyncio.run(_build(task, corpus, QuestionDir(Path(out_root) / qid), rotation,
                              settings or BuildSettings.from_env(), log))


def load_doc(qdir: QuestionDir) -> dict[str, Any]:
    if not qdir.doc.exists():
        raise FileNotFoundError(f"{qdir.doc} does not exist: run `gold build {qdir.root.name}` first")
    return json.loads(qdir.doc.read_text(encoding="utf-8"))


def file_hash(path: Path) -> str | None:
    return file_sha256(path) if path.exists() else None
