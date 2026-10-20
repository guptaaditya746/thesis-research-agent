"""Provenance broker (docs/earlier-work.md, build row 1.6; Provenance model).

One broker process per run, outside the sandbox. It is the only writer of events.jsonl and
claims.jsonl and keeps one hash chain over all records (agent/chain.py), fsync'ed per record.

Input A, the harness channel: an AF_UNIX SOCK_SEQPACKET socket from the parent process. One JSON
object per message, one reply per message:
  {"op": "record", "record": {...}}           -> {"ok": true, "task_id": ..., "hash": ...}
  {"op": "claim_channel", "step_id": n, "agent_id": "main", "origin": "research",
   "source_agent_id": null, "spawned_by_step": null} plus one fd
                                              -> {"ok": true}
  {"op": "head"}                              -> {"ok": true, "head": ..., "records": n, "claims": n}
  {"op": "close"}                             -> same as head, then the broker exits
Harness records are ai_model_invocation, agent_tool, spawn and coverage, plus concept_pick (the
user's pick of a concept brief, row 2.2); the harness assigns step ids. Claims cannot be sent on
this channel. A broker without a corpus (the corpus-blind concept step) rejects every claim.

Input B, one claim channel per command: a stream socket whose other end the sandbox gets as
CLAIM_FD. Newline-delimited JSON {s, p, o, file, quote}; every request is tagged with the step id
(and agent) the channel was opened for, whatever the request says. A subagent's channel (row
2.12, agent/spawn.py) also carries its parent (`source_agent_id`) and the parent's step that
spawned it (`custom_metadata.spawned_by_step`). Each claim's quote is anchored in the
corpus file named by `file` (agent/anchor.py), after checking the file against its manifest hash.
Reply {"ok": true, "claim_id": ...} or {"ok": false, "reason": ...}; both outcomes are logged.

Only the POSIX transport (SEQPACKET + SCM_RIGHTS) is Linux-specific; the core (Broker) and the
claim-stream loop run on any stream socket, which is how the tests exercise them on Windows.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from .anchor import AnchorError, Index, find
from jsonio import canonical_bytes, sha256_hex
from .chain import line, seal, task_id, verify
from .rundir import RunDir, utc_now

HARNESS_SUBTYPES = ("ai_model_invocation", "agent_tool", "spawn", "coverage", "concept_pick")
HARNESS_KEYS = {"subtype", "step_id", "used", "generated", "parent_task_id", "group_id", "agent_id",
                "source_agent_id", "started_at", "ended_at", "status", "custom_metadata"}
CLAIM_KEYS = ("s", "p", "o", "file", "quote")
MAX_LINE = 64 * 1024
MAX_MESSAGE = 1 << 20


class Rejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class Corpus:
    """The frozen corpus: Markdown files named <id>.md, checked against manifest.json hashes."""

    def __init__(self, root: Path, manifest: Path) -> None:
        self.root = Path(root)
        data = json.loads(Path(manifest).read_text(encoding="utf-8"))
        self.hashes = {f"{p['id']}.md": p["markdown_sha256"] for p in data["papers"] if p.get("failure") is None}
        self._indexes: dict[str, Index] = {}
        self._lock = threading.Lock()

    def name(self, file: str) -> str:
        """Accept `p12.md`, `p12`, or an absolute path inside the corpus directory."""
        name = file
        if "/" in file or "\\" in file:
            path = Path(file)
            if not path.is_absolute() or path.parent.resolve() != self.root.resolve():
                raise Rejected("file_outside_corpus")
            name = path.name
        if name not in self.hashes and f"{name}.md" in self.hashes:
            name = f"{name}.md"
        if name not in self.hashes:
            raise Rejected("unknown_file")
        return name

    def index(self, name: str) -> Index:
        with self._lock:
            cached = self._indexes.get(name)
        if cached is not None:
            return cached
        data = (self.root / name).read_bytes()
        if sha256_hex(data) != self.hashes[name]:
            raise Rejected("corpus_file_hash_mismatch")
        index = Index(data.decode("utf-8"))
        with self._lock:
            self._indexes[name] = index
        return index


@dataclass(frozen=True)
class Channel:
    """What the broker binds to one claim channel; nothing in a request can change it."""
    step_id: int
    agent_id: str = "main"
    origin: str = "research"
    source_agent_id: str | None = None  # a subagent's parent (row 2.12)
    spawned_by_step: int | None = None  # ... and the parent's step that spawned it


def channel_of(request: dict[str, Any]) -> Channel | None:
    """The Channel a claim_channel request asks for, or None if a field has the wrong type."""
    channel = Channel(request.get("step_id"), request.get("agent_id", "main"), request.get("origin", "research"),
                      request.get("source_agent_id"), request.get("spawned_by_step"))
    ints = [channel.step_id] + ([channel.spawned_by_step] if channel.spawned_by_step is not None else [])
    texts = [channel.agent_id, channel.origin] + ([channel.source_agent_id] if channel.source_agent_id is not None else [])
    ok = (all(isinstance(i, int) and not isinstance(i, bool) for i in ints)
          and all(isinstance(t, str) and t for t in texts))
    return channel if ok else None


class Broker:
    """Single writer of a run's events.jsonl and claims.jsonl. Thread-safe."""

    def __init__(self, run: RunDir, corpus: Corpus | None) -> None:
        self.run = run
        self.corpus = corpus
        report = verify(run.events, run.claims)
        if not report.ok:
            raise RuntimeError(f"refusing to extend a broken chain: {report.errors}")
        self.records = report.records
        self.claims = report.claims
        self.head = report.head
        self._next_claim = 1 + self.claims_accepted()
        self._lock = threading.Lock()
        self._events: BinaryIO = open(run.events, "ab")
        self._claims: BinaryIO = open(run.claims, "ab")

    def claims_accepted(self) -> int:
        lines = self.run.claims.read_bytes().splitlines() if self.run.claims.exists() else []
        return sum(json.loads(raw)["status"] == "accepted" for raw in lines)

    def close(self) -> None:
        with self._lock:
            self._events.close()
            self._claims.close()

    def _append(self, record: dict[str, Any], claim_id: bool = False) -> dict[str, Any]:
        with self._lock:
            if claim_id:
                record["generated"] = {"claim_id": f"claim-{self._next_claim:06d}"}
                self._next_claim += 1
            record["task_id"] = task_id(self.records + 1)
            sealed = seal(record, self.head)
            data = line(sealed)
            self._events.write(data)
            self._events.flush()
            os.fsync(self._events.fileno())
            if sealed["subtype"] == "claim":
                self._claims.write(data)
                self._claims.flush()
                os.fsync(self._claims.fileno())
                self.claims += 1
            self.records += 1
            self.head = sealed["hash"]
            return sealed

    def record(self, rec: Any) -> dict[str, Any]:
        """Input A: append one harness record. Returns the reply."""
        if not isinstance(rec, dict):
            return {"ok": False, "reason": "record must be an object"}
        unknown = sorted(set(rec) - HARNESS_KEYS)
        if unknown:
            return {"ok": False, "reason": f"unknown fields {unknown}"}
        if rec.get("subtype") not in HARNESS_SUBTYPES:
            return {"ok": False, "reason": f"subtype must be one of {list(HARNESS_SUBTYPES)}"}
        step = rec.get("step_id")
        if not isinstance(step, int) or isinstance(step, bool) or step < 0:
            return {"ok": False, "reason": "step_id must be a non-negative integer"}
        for key in ("used", "generated", "custom_metadata"):
            if not isinstance(rec.get(key, {}), dict):
                return {"ok": False, "reason": f"{key} must be an object"}
        now = utc_now()
        record = {
            "subtype": rec["subtype"], "step_id": step,
            "used": rec.get("used", {}), "generated": rec.get("generated", {}),
            "parent_task_id": rec.get("parent_task_id"), "group_id": rec.get("group_id", f"step-{step}"),
            "agent_id": rec.get("agent_id", "main"), "source_agent_id": rec.get("source_agent_id"),
            "workflow_id": self.run.run_id,
            "started_at": rec.get("started_at", now), "ended_at": rec.get("ended_at", now),
            "status": rec.get("status", "finished"), "custom_metadata": rec.get("custom_metadata", {}),
        }
        try:
            sealed = self._append(record)
        except ValueError as exc:  # e.g. NaN in a payload
            return {"ok": False, "reason": f"record not serialisable: {exc}"}
        return {"ok": True, "task_id": sealed["task_id"], "hash": sealed["hash"]}

    def claim(self, channel: Channel, raw: bytes) -> dict[str, Any]:
        """Input B: check and log one claim request received on `channel`. Returns the reply."""
        started = utc_now()
        meta: dict[str, Any] = {"origin": channel.origin}
        if channel.spawned_by_step is not None:
            meta["spawned_by_step"] = channel.spawned_by_step
        used: dict[str, Any] = {}
        try:
            request = self._parse(raw, meta)
            meta.update({k: request[k] for k in ("s", "p", "o", "quote")})
            used = {"file": request["file"], "quote": request["quote"]}
            if self.corpus is None:
                raise Rejected("unknown_file")
            name = self.corpus.name(request["file"])
            selector = find(self.corpus.index(name), request["quote"], file=name)
            used = {"anchor": selector.json()}
            status, reason = "accepted", None
        except Rejected as exc:
            status, reason = "rejected", exc.reason
        except AnchorError as exc:
            status, reason = "rejected", exc.reason
        if reason:
            meta["reason"] = reason
        record = {
            "subtype": "claim", "step_id": channel.step_id, "used": used, "generated": {},
            "parent_task_id": None, "group_id": f"step-{channel.step_id}",
            "agent_id": channel.agent_id, "source_agent_id": channel.source_agent_id,
            "workflow_id": self.run.run_id, "started_at": started, "ended_at": utc_now(),
            "status": status, "custom_metadata": meta,
        }
        sealed = self._append(record, claim_id=status == "accepted")
        if status == "accepted":
            return {"ok": True, "claim_id": sealed["generated"]["claim_id"]}
        return {"ok": False, "reason": reason}

    @staticmethod
    def _parse(raw: bytes, meta: dict[str, Any]) -> dict[str, Any]:
        meta["request_sha256"] = sha256_hex(raw)
        if len(raw) > MAX_LINE:
            raise Rejected("request_too_large")
        try:
            request = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise Rejected("malformed_json") from None
        if not isinstance(request, dict):
            raise Rejected("malformed_json")
        ignored = sorted(k for k in request if k not in CLAIM_KEYS)
        if ignored:
            meta["ignored_fields"] = ignored  # e.g. a forged step_id; logged, never used
        for key in CLAIM_KEYS:
            if key not in request:
                raise Rejected(f"missing_field:{key}")
        for key in ("s", "p", "file", "quote"):
            if not isinstance(request[key], str) or not request[key].strip():
                raise Rejected(f"bad_field:{key}")
        o = request["o"]
        if not isinstance(o, (str, int, float, bool)) or (isinstance(o, str) and not o.strip()):
            raise Rejected("bad_field:o")
        if isinstance(o, float) and o != o:
            raise Rejected("bad_field:o")
        return request


def serve_claims(broker: Broker, sock: socket.socket, channel: Channel) -> None:
    """Answer claim requests on one stream socket until the other side closes it."""
    with sock, sock.makefile("rwb") as stream:
        while True:
            raw = stream.readline(MAX_LINE + 1)
            if not raw:
                return
            if len(raw) > MAX_LINE and not raw.endswith(b"\n"):
                rest = raw
                while rest and not rest.endswith(b"\n"):  # drop the rest of an oversized line
                    rest = stream.readline(MAX_LINE)
                reply = broker.claim(channel, raw)  # rejected as request_too_large
            else:
                reply = broker.claim(channel, raw.rstrip(b"\r\n"))
            try:
                stream.write(canonical_bytes(reply) + b"\n")
                stream.flush()
            except OSError:
                return  # the command exited before reading its reply; the claim is logged


def serve_harness(broker: Broker, sock: socket.socket) -> dict[str, Any]:
    """POSIX: run the harness protocol on a SEQPACKET socket until "close" or EOF."""
    threads: list[threading.Thread] = []
    while True:
        msg, fds, _flags, _addr = socket.recv_fds(sock, MAX_MESSAGE, 4)
        if not msg:
            for fd in fds:
                os.close(fd)
            break
        try:
            request = json.loads(msg.decode("utf-8"))
            op = request.get("op") if isinstance(request, dict) else None
        except ValueError:
            request, op = {}, None
        if op == "record":
            reply = broker.record(request.get("record"))
        elif op == "claim_channel" and len(fds) == 1 and (channel := channel_of(request)) is not None:
            thread = threading.Thread(target=serve_claims, args=(broker, socket.socket(fileno=fds.pop()), channel),
                                      daemon=True)
            thread.start()
            threads.append(thread)
            reply = {"ok": True}
        elif op in ("head", "close"):
            if op == "close":
                for thread in threads:
                    thread.join(timeout=30)
            reply = {"ok": True, "head": broker.head, "records": broker.records, "claims": broker.claims}
        else:
            reply = {"ok": False, "reason": "unknown op or missing descriptor"}
        for fd in fds:
            os.close(fd)
        sock.send(canonical_bytes(reply))
        if op == "close":
            break
    return {"head": broker.head, "records": broker.records, "claims": broker.claims}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agent.broker")
    parser.add_argument("--fd", type=int, required=True, help="harness SEQPACKET socket")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    run = RunDir(args.run_dir)
    broker = Broker(run, Corpus(args.corpus, args.manifest))
    print(f"broker: start run={run.run_id} records={broker.records} head={broker.head}", flush=True)
    try:
        result = serve_harness(broker, socket.socket(fileno=args.fd))
    finally:
        broker.close()
    # The chain head goes to the Slurm log so a truncated log can be detected later.
    print(f"broker: close run={run.run_id} records={result['records']} claims={result['claims']} "
          f"head={result['head']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
