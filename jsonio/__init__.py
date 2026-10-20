"""The one canonical JSON form and the atomic file writers. Every writer and every checker uses it."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
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
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(obj) + b"\n"
    path.write_bytes(data)
    return sha256_hex(data)


def write_json_atomic(path: Path, obj: Any) -> str:
    """Canonical JSON plus newline, written to a temporary file and renamed over `path`; returns the sha256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(obj) + b"\n"
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return sha256_hex(data)


def write_text_atomic(path: Path, text: str) -> None:
    """Text with LF line ends, written to a temporary file and renamed over `path`."""
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
