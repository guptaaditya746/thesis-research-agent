"""The run trace: one row per step of a run, from calls.jsonl (the warm pass's model calls, as they complete)
and events.jsonl (the engine's steps), for the live run-trace tab.

Both files only grow while a run goes on, so each is read once from where the last read ended (complete lines
only: a half-written last line waits for the next poll) and kept as small rows; a poll costs the new bytes, not
the whole file. calls.jsonl carries full prompts and replies, so only its light fields are kept here, plus where
each line sits so one call can be read back (`call_row`). The file can be missing (regex-only, replay and
reexec runs, old runs): no rows, no error."""
from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from evidence.calls import cache_key
from evidence.recording import usage
from evidence.rundir import ANSWER_FILE, EVENTS_FILE, RUN_CALLS_FILE

from .evmodels import TracePage, TraceRow

STEPS = ("screen", "locate", "extractor_call", "merge", "completeness", "synthesis")


def _seconds(started: Any, ended: Any) -> float | None:
    try:
        return round((datetime.fromisoformat(str(ended)) - datetime.fromisoformat(str(started))).total_seconds(), 3)
    except ValueError:
        return None


class _Tail:
    """The complete JSON-object lines of a growing file, each turned into a small row by `light(parsed, pos, size)`."""

    def __init__(self, path: Path, light: Callable[[dict[str, Any], int, int], dict[str, Any] | None]) -> None:
        self.path, self.light = path, light
        self.offset = 0
        self.head = b""                      # the file's first bytes when last read: a rewritten file changes them
        self.rows: list[dict[str, Any]] = []

    def refresh(self) -> list[dict[str, Any]]:
        try:
            size = self.path.stat().st_size
            with self.path.open("rb") as fh:
                if self.offset and (size < self.offset or fh.read(len(self.head)) != self.head):
                    self.offset, self.head, self.rows = 0, b"", []     # shrunk or rewritten: read again from the start
                if size == self.offset:
                    return self.rows
                fh.seek(self.offset)
                data = fh.read()
        except OSError:
            return self.rows
        pos = self.offset
        for raw in data.splitlines(keepends=True):
            if not raw.endswith(b"\n"):
                break                        # half-written: read again next time
            try:
                parsed = json.loads(raw)
            except ValueError:
                parsed = None                 # damage is skipped, never an error
            row = self.light(parsed, pos, len(raw)) if isinstance(parsed, dict) else None
            if row is not None:
                self.rows.append(row)
            pos += len(raw)
        self.offset = pos
        if pos and not self.head:
            with self.path.open("rb") as fh:
                self.head = fh.read(min(pos, 64))
        return self.rows


def _light_call(row: dict[str, Any], pos: int, size: int) -> dict[str, Any] | None:
    if not isinstance(row.get("key"), str):
        return None
    tokens_in, tokens_out = usage([m for m in row.get("model_calls") or [] if isinstance(m, dict)])
    return {"key": row["key"], "phase": "warm" if row.get("phase") == "warm" else "run", "document": row.get("document"),
            "evidence_type": row.get("evidence_type"), "extractor": row.get("extractor_id"), "status": str(row.get("status", "")),
            "source": row.get("source"), "seconds": _seconds(row.get("started_at"), row.get("ended_at")),
            "input_tokens": tokens_in, "output_tokens": tokens_out, "pos": pos, "size": size}


def _light_event(event: dict[str, Any], pos: int, size: int) -> dict[str, Any] | None:
    meta = event.get("custom_metadata") if isinstance(event.get("custom_metadata"), dict) else {}
    step = event.get("subtype")
    if step not in STEPS:
        return None
    document = meta.get("document", event.get("group_id"))
    row: dict[str, Any] = {"step": step, "document": str(document) if document is not None else None,
                           "evidence_type": meta.get("evidence_type"), "status": str(event.get("status") or ""),
                           "source": meta.get("source"), "seconds": None,
                           "extractor": meta.get("extractor") or event.get("agent_id"), "call": None, "key": None}
    if step == "extractor_call":
        # only this event is given its real start (the others default to the time they are written)
        row["seconds"] = _seconds(event.get("started_at"), event.get("ended_at"))
        row["call"] = event.get("task_id")
        if isinstance(meta.get("task_sha256"), str) and event.get("agent_id"):
            row["key"] = cache_key(event["agent_id"], meta["task_sha256"], int(meta.get("attempt") or 0))
    elif step == "screen":
        calls = meta.get("calls")
        row["call"] = calls[0] if isinstance(calls, list) and calls else None
    return row


class TraceReader:
    def __init__(self) -> None:
        self._tails: dict[Path, _Tail] = {}
        self._lock = threading.Lock()

    def _rows(self, path: Path, light: Callable[[dict[str, Any], int, int], dict[str, Any] | None]) -> list[dict[str, Any]]:
        with self._lock:
            tail = self._tails.get(path)
            if tail is None:
                tail = self._tails[path] = _Tail(path, light)
            return list(tail.refresh())

    def call_row(self, run: Path, key: str) -> dict[str, Any] | None:
        """The full calls.jsonl row under `key`, read back from its place in the file."""
        where = next((r for r in reversed(self._rows(run / RUN_CALLS_FILE, _light_call)) if r["key"] == key), None)
        if where is None:
            return None
        try:
            with (run / RUN_CALLS_FILE).open("rb") as fh:
                fh.seek(where["pos"])
                row = json.loads(fh.read(where["size"]))
        except (OSError, ValueError):
            return None
        return row if isinstance(row, dict) and row.get("key") == key else None

    def page(self, run: Path, after: int = 0) -> TracePage:
        calls = self._rows(run / RUN_CALLS_FILE, _light_call)
        events = self._rows(run / EVENTS_FILE, _light_event)
        by_key = {c["key"]: c for c in calls}
        rows: list[TraceRow] = []
        # warm-pass rows come first; a `run`-phase row (workers=1) is the same call as its extractor_call event,
        # so it only fills that event's tokens
        for c in (c for c in calls if c["phase"] == "warm"):
            rows.append(TraceRow(n=len(rows) + 1, phase="warm", step="call", document=c["document"], evidence_type=c["evidence_type"],
                                 extractor=c["extractor"], status=c["status"], source=c["source"], seconds=c["seconds"],
                                 input_tokens=c["input_tokens"], output_tokens=c["output_tokens"], call=c["key"]))
        for e in events:
            match = by_key.get(e["key"]) if e["key"] else None
            rows.append(TraceRow(n=len(rows) + 1, phase="run", step=e["step"], document=e["document"],
                                 evidence_type=e["evidence_type"], extractor=e["extractor"], status=e["status"],
                                 source=e["source"], seconds=e["seconds"], call=e["call"],
                                 input_tokens=match["input_tokens"] if match else None,
                                 output_tokens=match["output_tokens"] if match else None))
        fresh = [r for r in rows if r.n > after]
        return TracePage(rows=fresh, next=fresh[-1].n if fresh else after, done=(run / ANSWER_FILE).is_file())
