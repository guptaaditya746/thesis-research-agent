"""The corpus the engine reads and the run directory it writes (docs/evidence-interfaces.md sections 1, 3).

The engine reads only a corpus's `manifest.json` and the paper files it lists, each checked against its
manifest sha256; never `ground_truth.json`, `corpus.json` or `fidelity.json` (a test enforces it).

The run directory holds canonical JSON files whose hashes go into run.json `outputs`; none of them carries
a timestamp or the run id, so a replay of the run hashes the same. events.jsonl is the hash chain
(agent/chain.py): its records carry times and the run id, so it is not an output; its head is in run.json.
"""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.canonical import GENESIS, canonical_bytes, file_sha256, sha256_hex
from agent.chain import FIELDS, line, seal, task_id
from agent.rundir import utc_now

from .contract import DocumentRef

RUN_FILE, PROTOCOL_FILE, EVENTS_FILE = "run.json", "protocol.yaml", "events.jsonl"
LOCATE_FILE, EVIDENCE_FILE, GRAPH_FILE, ANSWER_FILE = "locate.json", "evidence.jsonl", "graph.json", "answer.json"
CALLS_DIR, REEXEC_FILE, PROV_FILE = "calls", "reexec.json", "prov.ttl"
CACHE_FILE = "extractor_calls.jsonl"


class CorpusError(RuntimeError):
    pass


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


def write_canonical(path: Path, obj: Any) -> str:
    """Canonical JSON plus a newline (agent/canonical.write_json); returns the sha256 of the bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(obj) + b"\n"
    path.write_bytes(data)
    return sha256_hex(data)


def write_lines(path: Path, rows: list[Any]) -> str:
    data = b"".join(canonical_bytes(r) + b"\n" for r in rows)
    path.write_bytes(data)
    return sha256_hex(data)


def read_json(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8"))


def read_lines(path: Path) -> list[Any]:
    return [json.loads(raw) for raw in path.read_bytes().decode("utf-8").splitlines() if raw.strip()]
