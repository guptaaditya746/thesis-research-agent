"""The one canonical JSON form. Every writer and every checker in the package uses it."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def canonical(obj: Any) -> str:
    """Sorted keys, UTF-8 kept as is, no whitespace, no NaN or Infinity."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def canonical_bytes(obj: Any) -> bytes:
    return canonical(obj).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, obj: Any) -> str:
    """Write `obj` in canonical form plus a newline; return the file's sha256."""
    data = canonical_bytes(obj) + b"\n"
    path.write_bytes(data)
    return sha256_hex(data)
