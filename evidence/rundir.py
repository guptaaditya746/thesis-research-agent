"""The corpus the engine reads and the run directory it writes (docs/evidence-system.md A1, A3).

The engine reads only a corpus's `manifest.json` and the paper files it lists, each checked against its
manifest sha256; never `ground_truth.json`, `corpus.json` or `fidelity.json` (a test enforces it).

The run directory holds canonical JSON files whose hashes go into run.json `outputs`; none of them carries
a timestamp or the run id, so a replay of the run hashes the same. events.jsonl is the hash chain
(agent/chain.py): its records carry times and the run id, so it is not an output; its head is in run.json.
"""
from __future__ import annotations

import json
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from jsonio import GENESIS, canonical_bytes, file_sha256, sha256_hex
from agent.chain import FIELDS, line, seal, task_id
from agent.rundir import utc_now

from modelcall import JsonlCache

from .contract import DocumentRef, Item

RUN_FILE, PROTOCOL_FILE, EVENTS_FILE = "run.json", "protocol.yaml", "events.jsonl"
LOCATE_FILE, EVIDENCE_FILE, GRAPH_FILE, ANSWER_FILE = "locate.json", "evidence.jsonl", "graph.json", "answer.json"
CALLS_DIR, REEXEC_FILE, PROV_FILE = "calls", "reexec.json", "prov.ttl"
FUNNEL_FILE = "funnel.json"   # the funnel's steps and decisions per document (Part D)
NAMES_FILE = "names.json"     # the corpus-wide name groups (D38; `names: on` only)
CACHE_FILE = "extractor_calls.jsonl"
RUN_CALLS_FILE = "calls.jsonl"   # the run's own copy of every model-backed call (RunCalls); not an output
ENGINE_MARKERS = (EVENTS_FILE, PROTOCOL_FILE, FUNNEL_FILE, CALLS_DIR, NAMES_FILE)   # what only the engine writes in a run dir
REEXEC_GLOB = "{name}-reexec-*"   # sibling directories `evidence reexec` writes next to a run


SERVICE_REASONS = ("model_call", "service_call")   # error reasons of a call the model gateway / GLiNER did not answer


def service_failed(result: Any) -> bool:
    """Whether an extraction result (as JSON) failed, in whole or in part, because the model gateway (`model_call`:
    the LLM extractors and the LLM screen) or the GLiNER service (`service_call`) did not answer for some or all of
    its chunks. An agentic run that ran out of budget (`no_final_answer`) or an extractor's own exception is not
    one: asking the same service again would not change it."""
    if not isinstance(result, dict) or result.get("status") not in ("error", "partial"):
        return False
    error = result.get("error")
    return isinstance(error, dict) and error.get("reason") in SERVICE_REASONS


class CorpusError(RuntimeError):
    pass


class RunDirExists(FileExistsError):
    """A run would be written into a directory that is already there: a run dir is never written over. The
    message says which case it is and what to do."""

    def __init__(self, root: Path) -> None:
        self.root = root
        if RunDir(root).complete:
            why = (f"{root} exists and holds a finished run (run.json); a run dir is never written over: give "
                   "another --run-id or --out")
        else:
            why = (f"{root} exists without run.json: a run that was killed or crashed (or one still running). Move "
                   "it aside, to $RUNS/failed/<corpus>/ in the runbooks, and run again; the record cache keeps the "
                   "calls it finished")
        super().__init__(why)


@dataclass(frozen=True)
class Paper:
    id: str
    file: str
    sha256: str
    path: Path

    @property
    def ref(self) -> DocumentRef:
        return DocumentRef(id=self.id, file=self.file, sha256=self.sha256)


class Corpus:
    """manifest.json and papers/ of a corpus directory, nothing else."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        manifest = self.root / "manifest.json"
        self.manifest_sha256 = file_sha256(manifest)
        data = json.loads(manifest.read_bytes().decode("utf-8"))
        self.corpus_id = str(data.get("corpus_id", ""))
        self.papers: list[Paper] = []
        for entry in data["papers"]:
            file = str(entry["file"])
            path = self.root / file
            if not path.is_file():
                path = self.root / "papers" / Path(file).name
            self.papers.append(Paper(str(entry["id"]), file, str(entry["sha256"]), path))
        ids = [p.id for p in self.papers]
        if len(set(ids)) != len(ids):
            raise CorpusError("manifest.json lists a paper id twice")

    def text(self, paper: Paper) -> str:
        data = paper.path.read_bytes()
        if sha256_hex(data) != paper.sha256:
            raise CorpusError(f"{paper.file}: sha256 differs from manifest.json")
        return data.decode("utf-8")


def new_run_id(protocol_id: str, suffix: str = "") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{protocol_id}-{stamp}-{secrets.token_hex(3)}{suffix}"


class Events:
    """The run's hash-chained events.jsonl (agent/chain.py records, verified by chain.verify)."""

    def __init__(self, path: Path, workflow_id: str) -> None:
        self.path = path
        self.workflow_id = workflow_id
        self.n = 0
        self.head = GENESIS
        path.write_bytes(b"")

    def next_id(self) -> str:
        return task_id(self.n + 1)

    def add(self, subtype: str, *, used: list[str], generated: list[str], agent_id: str, status: str = "ok",
            custom: dict[str, Any] | None = None, group_id: str | None = None, started_at: str | None = None) -> str:
        self.n += 1
        record = dict.fromkeys(FIELDS)
        record.update(task_id=task_id(self.n), subtype=subtype, used=used, generated=generated, agent_id=agent_id,
                      workflow_id=self.workflow_id, group_id=group_id, status=status,
                      custom_metadata=custom or {}, started_at=started_at or utc_now(), ended_at=utc_now())
        sealed = seal(record, self.head)
        with self.path.open("ab") as fh:
            fh.write(line(sealed))
        self.head = sealed["hash"]
        return sealed["task_id"]


class RunCalls:
    """The run's calls.jsonl: one row per model-backed extractor or screen call, with the call's full model-call
    records (evidence/recording.py), so the run's trace keeps its prompts and replies when the shared record
    cache is moved or deleted. Rows are appended as calls complete (the warm pass's threads too, under the
    lock), so a reader sees progress; a row whose `key` (the cache key) was already written is skipped. Not
    in the hash chain nor in run.json `outputs`, and the row order may vary with workers."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.keys: set[str] = set()

    def add(self, row: dict[str, Any]) -> None:
        with self.lock:
            if row["key"] in self.keys:
                return
            with self.path.open("ab") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
            self.keys.add(row["key"])


def write_lines(path: Path, rows: list[Any]) -> str:
    data = b"".join(canonical_bytes(r) + b"\n" for r in rows)
    path.write_bytes(data)
    return sha256_hex(data)


def read_json(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8"))


def read_lines(path: Path) -> list[Any]:
    """The JSON lines of a file. A process killed mid-append leaves a cut last line with no line break: that
    one is skipped. A bad line anywhere else is damage and raises ValueError naming `path:line`."""
    data = path.read_bytes().decode("utf-8")
    rows = data.split("\n")
    out: list[Any] = []
    for n, raw in enumerate(rows, 1):
        if not raw.strip():
            continue
        try:
            out.append(json.loads(raw))
        except ValueError as exc:
            if n == len(rows):   # no line break after it: the torn tail of an interrupted append
                continue
            raise ValueError(f"{path}:{n}: {exc}") from exc
    return out


class RunDir:
    """The read side of a run directory: what the engine (or a baseline) wrote, optional files as None.

    Readers (scoring, the web app) go through this instead of repeating the layout. A torn last line of
    events.jsonl or evidence.jsonl is skipped (read_lines); a malformed required file raises."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    @property
    def complete(self) -> bool:
        """True when run.json parses to a non-empty object: the engine writes it last, so a directory without
        one (or with a cut or empty one) crashed or is still running."""
        run = self.try_json(RUN_FILE)
        return isinstance(run, dict) and bool(run)

    @property
    def kind(self) -> Literal["engine", "baseline"] | None:
        """"engine" when run.json parses to an object (even an empty one) or the directory holds something only
        the engine writes (ENGINE_MARKERS); "baseline" when answer.json is an object naming its `system`; else
        None. An unparsable run.json or answer.json counts as absent, so a listing never fails on one."""
        if isinstance(self.try_json(RUN_FILE), dict) or any(self.file(m).exists() for m in ENGINE_MARKERS):
            return "engine"
        answer = self.try_json(ANSWER_FILE)
        return "baseline" if isinstance(answer, dict) and answer.get("system") else None

    def file(self, name: str) -> Path:
        return self.root / name

    def json(self, name: str) -> Any | None:
        path = self.file(name)
        return read_json(path) if path.is_file() else None

    def try_json(self, name: str) -> Any | None:
        """The file's JSON, or None when it is missing or unreadable (cut, being written, not UTF-8)."""
        try:
            return self.json(name)
        except (OSError, ValueError):
            return None

    def items(self) -> list[Item]:
        path = self.file(EVIDENCE_FILE)
        return [Item.model_validate(row) for row in read_lines(path)] if path.is_file() else []

    def events(self) -> list[dict[str, Any]] | None:
        path = self.file(EVENTS_FILE)
        return [e for e in read_lines(path) if isinstance(e, dict)] if path.is_file() else None

    def events_of(self, subtype: str) -> list[dict[str, Any]] | None:
        events = self.events()
        return None if events is None else [e for e in events if e.get("subtype") == subtype]

    def calls(self) -> list[dict[str, Any]] | None:
        folder = self.file(CALLS_DIR)
        return [read_json(p) for p in sorted(folder.glob("*.json"))] if folder.is_dir() else None

    def error_calls(self) -> int:
        """Calls whose checked result is an error (calls/<call_id>.json status "error"); an unreadable file is not one."""
        return self._count(lambda c: c.get("status") == "error")

    def failed_calls(self) -> int:
        """Calls the model gateway or the GLiNER service failed, in whole or in part (`service_failed`: status
        "error" or "partial" with reason `model_call` or `service_call`). `evidence run` exits 2 on a count above 0,
        the web app shows it, and `--retry-errors` asks them again. An agentic call that ran out of budget is not one."""
        return self._count(service_failed)

    def _count(self, test: Any) -> int:
        folder = self.file(CALLS_DIR)
        if not folder.is_dir():
            return 0
        found = (self.try_json(f"{CALLS_DIR}/{p.name}") for p in sorted(folder.glob("*.json")))
        return sum(1 for c in found if isinstance(c, dict) and test(c))

    def cache_file(self) -> Path | None:
        """The record cache run.json names (`settings.cache`, a directory or the jsonl file), when it exists."""
        cache = (((self.json(RUN_FILE) or {}).get("settings")) or {}).get("cache")
        if not cache:
            return None
        path = Path(cache)
        if path.is_dir():
            path = path / CACHE_FILE
        return path if path.is_file() else None

    def usage(self) -> dict[str, dict[str, int]] | None:
        """Model-call record id -> token usage, from the cache run.json names (None without one)."""
        path = self.cache_file()
        if path is None:
            return None
        usage: dict[str, dict[str, int]] = {}
        for _, value in JsonlCache(path).items():
            for record in (value.get("model_calls") if isinstance(value, dict) else None) or []:
                if isinstance(record, dict) and record.get("id") and isinstance(record.get("usage"), dict):
                    usage[record["id"]] = {k: int(record["usage"].get(k) or 0)
                                           for k in ("input_tokens", "output_tokens")}
        return usage

    def latest_reexec(self) -> Path | None:
        """The newest sibling `<name>-reexec-<stamp>/reexec.json` (stamps sort by time); symlinks are left out."""
        found = sorted(p / REEXEC_FILE for p in self.root.parent.glob(REEXEC_GLOB.format(name=self.root.name))
                       if (p / REEXEC_FILE).is_file() and not p.is_symlink())
        return found[-1] if found else None

    def watched(self) -> tuple[Path, ...]:
        """The files whose change a reader's cache must notice."""
        return tuple(self.file(n) for n in (RUN_FILE, ANSWER_FILE, *ENGINE_MARKERS))
