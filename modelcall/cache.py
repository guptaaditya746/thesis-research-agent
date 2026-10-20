"""The append-only result cache and its key."""
from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Iterator
from typing import Any, TypeVar

from pydantic import BaseModel

from jsonio import canonical_bytes, sha256_hex

# One cache line starts `{"key": "<key>"`: json.dumps(sort_keys=True) puts "key" before "value". A reader can
# find a key's line without parsing every value.
KEY_LINE = re.compile(rb'^\s*\{"key":\s*"([^"]+)"')
T = TypeVar("T", bound=BaseModel)


def cache_key(payload: dict[str, Any]) -> str:
    """Key for a result cache line: sha256 of the canonical call input (prompt hash, model, inputs)."""
    return sha256_hex(canonical_bytes(payload))


class JsonlCache:
    """Append-only `{key, value}` lines; a rerun with the same inputs costs no model call.

    A process killed in the middle of an append (a Slurm time limit, a full quota) leaves a cut last
    line. Loading skips lines that do not parse (counted in `skipped`; their calls are simply made
    again), and the first append after such a load starts on a new line, so the cut line never
    swallows a good one."""

    def __init__(self, path: os.PathLike[str] | str) -> None:
        self.path = os.fspath(path)
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self.skipped = 0
        self._newline = False  # the file does not end with a line break: start the next append with one
        if os.path.exists(self.path):
            with open(self.path, "rb") as fh:
                data = fh.read()
            self._newline = bool(data) and not data.endswith(b"\n")
            for line in data.split(b"\n"):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    self._data[row["key"]] = row["value"]
                except (ValueError, KeyError, TypeError):
                    self.skipped += 1

    def get(self, key: str) -> Any | None:
        return self._data.get(key)

    def items(self) -> Iterator[tuple[str, Any]]:
        """Every (key, value): the last line of a key wins, as for `get`."""
        return iter(list(self._data.items()))

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            line = json.dumps({"key": key, "value": value}, ensure_ascii=False, sort_keys=True) + "\n"
            with open(self.path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(("\n" if self._newline else "") + line)
            self._newline = False


def decode(value: Any, output_type: type[T]) -> tuple[T, str | None, str | None, int, int]:
    """A cached value as (output, model, served_model, input_tokens, output_tokens).

    `ask` stores `{"output", "model", "served_model", "usage": {"input_tokens", "output_tokens"}, **extra}`;
    the older shapes are read too (modelcall/tests/test_golden_keys.py pins them):
    - no `"output"`: the value holds the output's own fields beside other metadata (judge, propose);
    - tokens in `value["usage"]` or at the top level (synth);
    - `served_model` at the top level or inside `usage` (baselines)."""
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
