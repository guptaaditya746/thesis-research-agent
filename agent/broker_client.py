"""Harness side of the broker (what row 1.8's main loop calls).

`BrokerProcess` starts the real broker (python -m agent.broker) as a child process and talks to it
over an AF_UNIX SOCK_SEQPACKET socketpair (Linux). `InProcessBroker` has the same interface but
runs the broker core in this process; it works on any OS and serves as the stub broker for tests.

Per command:
    claim_sock = broker.claim_channel(step_id)        # fresh socketpair, tagged with step_id
    subprocess.Popen(..., pass_fds=(claim_sock.fileno(),),
                     env={..., "CLAIM_FD": str(claim_sock.fileno())})
    claim_sock.close()                                # the sandbox now holds the only copy
    ... wait for the command ...
    broker.record({"subtype": "agent_tool", "step_id": step_id, ...})
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from .broker import MAX_MESSAGE, Broker, Channel, Corpus, serve_claims
from .canonical import canonical_bytes
from .rundir import RunDir


class BrokerError(RuntimeError):
    pass


def _checked(reply: dict[str, Any]) -> dict[str, Any]:
    if not reply.get("ok"):
        raise BrokerError(reply.get("reason", "broker refused"))
    return reply


class BrokerProcess:
    """The broker as its own process (POSIX only: SEQPACKET and descriptor passing)."""

    def __init__(self, process: subprocess.Popen[bytes], sock: socket.socket) -> None:
        self.process = process
        self.sock = sock
        self._lock = threading.Lock()

    @classmethod
    def start(cls, run_dir: Path, corpus: Path, manifest: Path, stdout: Any = None) -> BrokerProcess:
        """Start the broker; its stdout (start line and chain head) defaults to ours, i.e. the Slurm log."""
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        process = subprocess.Popen(
            [sys.executable, "-m", "agent.broker", "--fd", str(child.fileno()), "--run-dir", str(run_dir),
             "--corpus", str(corpus), "--manifest", str(manifest)],
            pass_fds=(child.fileno(),), stdout=stdout)
        child.close()
        return cls(process, parent)

    def _call(self, message: dict[str, Any], fds: list[int] | None = None) -> dict[str, Any]:
        try:
            with self._lock:
                if fds:
                    socket.send_fds(self.sock, [canonical_bytes(message)], fds)
                else:
                    self.sock.send(canonical_bytes(message))
                reply = self.sock.recv(MAX_MESSAGE)
        except OSError as exc:
            raise BrokerError(f"broker exited ({exc}); see its stderr") from exc
        if not reply:
            raise BrokerError("broker exited; see its stderr")
        return json.loads(reply.decode("utf-8"))

    def record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Append a harness record; returns {"ok": true, "task_id", "hash"} or raises BrokerError."""
        return _checked(self._call({"op": "record", "record": record}))

    def claim_channel(self, step_id: int, agent_id: str = "main", origin: str = "research",
                      source_agent_id: str | None = None, spawned_by_step: int | None = None) -> socket.socket:
        """A fresh claim socketpair for one step; returns the end to hand to the sandbox as CLAIM_FD.

        A subagent's channel (row 2.12) names its parent and the parent's spawning step too.
        """
        broker_end, sandbox_end = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        extra = {k: v for k, v in (("source_agent_id", source_agent_id), ("spawned_by_step", spawned_by_step))
                 if v is not None}
        try:
            _checked(self._call({"op": "claim_channel", "step_id": step_id, "agent_id": agent_id,
                                 "origin": origin, **extra}, [broker_end.fileno()]))
        finally:
            broker_end.close()
        return sandbox_end

    def head(self) -> dict[str, Any]:
        return _checked(self._call({"op": "head"}))

    def close(self, timeout: float = 60) -> dict[str, Any]:
        """Wait for open claim channels, stop the broker, return its final head and counts."""
        reply = _checked(self._call({"op": "close"}))
        self.sock.close()
        self.process.wait(timeout=timeout)
        return reply


class InProcessBroker:
    """Same interface as BrokerProcess, with the broker core running on threads in this process."""

    def __init__(self, run_dir: Path, corpus: Path, manifest: Path) -> None:
        self.broker = Broker(RunDir(Path(run_dir)), Corpus(corpus, manifest))
        self._threads: list[threading.Thread] = []

    def record(self, record: dict[str, Any]) -> dict[str, Any]:
        return _checked(self.broker.record(record))

    def claim_channel(self, step_id: int, agent_id: str = "main", origin: str = "research",
                      source_agent_id: str | None = None, spawned_by_step: int | None = None) -> socket.socket:
        broker_end, sandbox_end = socket.socketpair()
        channel = Channel(step_id, agent_id, origin, source_agent_id, spawned_by_step)
        thread = threading.Thread(target=serve_claims, daemon=True, args=(self.broker, broker_end, channel))
        thread.start()
        self._threads.append(thread)
        return sandbox_end

    def head(self) -> dict[str, Any]:
        b = self.broker
        return {"ok": True, "head": b.head, "records": b.records, "claims": b.claims}

    def close(self, timeout: float = 60) -> dict[str, Any]:
        for thread in self._threads:
            thread.join(timeout=timeout)
        reply = self.head()
        self.broker.close()
        return reply
