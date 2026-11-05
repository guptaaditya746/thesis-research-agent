"""The append-only result cache and its key."""
from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Iterator
from typing import Any, TypeVar

from filelock import FileLock, Timeout
from pydantic import BaseModel

from jsonio import canonical_bytes, sha256_hex

# One cache line starts `{"key": "<key>"`: json.dumps(sort_keys=True) puts "key" before "value". A reader can
# find a key's line without parsing every value.
KEY_LINE = re.compile(rb'^\s*\{"key":\s*"([^"]+)"')
T = TypeVar("T", bound=BaseModel)
LOCK_TIMEOUT = 600   # seconds an append waits for the cache's lock file


def cache_key(payload: dict[str, Any]) -> str:
    """Key for a result cache line: sha256 of the canonical call input (prompt hash, model, inputs)."""
    return sha256_hex(canonical_bytes(payload))


class JsonlCache:
    """Append-only `{key, value}` lines; a rerun with the same inputs costs no model call.

    A process killed in the middle of an append (a Slurm time limit, a full quota) leaves a cut last
    line. Loading skips lines that do not parse (counted in `skipped`; their calls are simply made
    again), and the first append after such a load starts on a new line, so the cut line never
    swallows a good one.

    Several processes may share one file (parallel question runs): an append holds `<file>.lock` (filelock) and
    writes its line with one O_APPEND write; a `get` miss first reads the lines other processes appended since
    (`_offset`: the bytes read so far), so their calls are not made again."""

    def __init__(self, path: os.PathLike[str] | str) -> None:
        self.path = os.fspath(path)
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self.skipped = 0
        self._offset = 0
        if os.path.exists(self.path):
            with open(self.path, "rb") as fh:
                data = fh.read()
            self._read(data, complete=True)
            # a last line without its break: cut by a killed writer (skipped; `put` starts a new line and reads past
            # it) or still being written by another process (a later read of the whole line takes it)
            self.skipped += bool(data[self._offset:].strip())

    def _read(self, data: bytes, *, complete: bool) -> None:
        """Parse `data` (the file from `_offset` on); `complete`: whole lines only (a line another process is still
        writing waits for the next read), else everything, a cut last line too."""
        end = data.rfind(b"\n") + 1 if complete else len(data)
        for line in data[:end].split(b"\n"):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                self._data[row["key"]] = row["value"]
            except (ValueError, KeyError, TypeError):
                self.skipped += 1
        self._offset += end

    def _catch_up(self) -> None:
        """Read what other processes appended since `_offset` (nothing to do when the file has not grown)."""
        try:
            if os.path.getsize(self.path) <= self._offset:
                return
            with open(self.path, "rb") as fh:
                fh.seek(self._offset)
                self._read(fh.read(), complete=True)
        except FileNotFoundError:
            return

    def get(self, key: str) -> Any | None:
        hit = self._data.get(key)
        if hit is None:
            with self._lock:
                self._catch_up()
            hit = self._data.get(key)
        return hit

    def items(self) -> Iterator[tuple[str, Any]]:
        """Every (key, value): the last line of a key wins, as for `get`."""
        return iter(list(self._data.items()))

    def put(self, key: str, value: Any) -> None:
        line = (json.dumps({"key": key, "value": value}, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        with self._lock:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            lock = FileLock(self.path + ".lock")
            try:
                lock.acquire(timeout=LOCK_TIMEOUT)
            except Timeout:
                raise TimeoutError(f"{self.path}.lock held for over {LOCK_TIMEOUT} s: another process writes this "
                                   "cache, or a killed job left the lock file; remove it if no job runs") from None
            try:
                self._catch_up()
                fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
                try:
                    size = os.fstat(fd).st_size
                    if size:   # a cut last line (a killed writer): start on a new line
                        with open(self.path, "rb") as fh:
                            fh.seek(size - 1)
                            line = (b"" if fh.read(1) == b"\n" else b"\n") + line
                    view = memoryview(line)
                    while view:
                        view = view[os.write(fd, view):]
                    self._offset = os.fstat(fd).st_size
                finally:
                    os.close(fd)
            finally:
                lock.release()
            self._data[key] = value


def decode(value: Any, output_type: type[T]) -> tuple[T, str | None, str | None, int, int]:
    """A cached value as (output, model, served_model, input_tokens, output_tokens).

    `ask` stores `{"output", "model", "served_model", "usage": {"input_tokens", "output_tokens"}, **extra}`;
    the older shapes are read too (modelcall/tests/test_golden_keys.py pins them):
    - no `"output"`: the value holds the output's own fields beside other metadata (judge, propose);
    - tokens in `value["usage"]` or at the top level (synth);
    - `served_model` at the top level or inside `usage` (baselines).
    It never makes an output up: a flat value whose fields do not validate raises pydantic's ValidationError.
    A cached failure (`"too_long": True`) is `call.ask`'s to handle and never reaches here."""
    if "output" in value:
        raw = value["output"]
    else:
        raw = {k: value[k] for k in output_type.model_fields if k in value}
    usage = value.get("usage") or {}

    def tokens(name: str) -> int:
        return int(usage.get(name, value.get(name)) or 0)

    return (output_type.model_validate(raw), value.get("model"),
            value.get("served_model") or usage.get("served_model"),
            tokens("input_tokens"), tokens("output_tokens"))
