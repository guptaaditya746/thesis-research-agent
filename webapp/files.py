"""Safe file access for the web app: every path a request names stays inside its root.

Ids from URLs (corpus, run, score, proposal, question and job names) must match `ID` (no separators, no
leading dot or dash); a run or score id joins two such names with `~` (`<group>~<name>`). Every path built
from request data or from a record is resolved and checked to lie inside the root it was built from, so `..`,
absolute paths and symlinks out of a root are refused. The server itself writes only job state and logs
($EV/.jobs/) and a proposal's decisions.yaml (webapp/evjobs.py); the jobs write what their commands write.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
RUN_SEP = "~"  # unreserved in URLs, never in a directory name the commands make


class NotFound(LookupError):
    """A missing (or refused) file or id; the API answers 404 with this message."""


class Conflict(RuntimeError):
    """The request cannot be done in the current state; the API answers 409."""


class BadRequest(ValueError):
    """The request is malformed; the API answers 400."""


class Damaged(ValueError):
    """A file the request needs is damaged (a bad line in the middle of a JSON-lines file); the API answers 422
    with the file (relative to its configured root) and the line."""


def check_id(value: str, what: str = "id") -> str:
    if not ID.fullmatch(value or ""):
        raise NotFound(f"no such {what}: {value!r}")
    return value


def inside(root: Path, *parts: str) -> Path:
    """root/parts resolved; NotFound unless it stays inside root (symlinks resolved too)."""
    base = Path(root).resolve()
    path = base.joinpath(*parts).resolve()
    if path != base and not path.is_relative_to(base):
        raise NotFound(f"{'/'.join(parts)} is outside {base.name}/")
    return path


def read_json(path: Path) -> Any | None:
    """The file's JSON, or None when it is missing or unreadable (a file still being written)."""
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Every complete JSON line; a torn last line (a writer mid-append) is left out."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return []
    out = []
    for raw in data.splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue
    return out


def signature(*paths: Path) -> tuple[Any, ...]:
    """(size, mtime) of each path, None when missing: a cache key that changes with the files."""
    out: list[Any] = []
    for path in paths:
        try:
            st = Path(path).stat()
            out.append((st.st_size, st.st_mtime_ns))
        except OSError:
            out.append(None)
    return tuple(out)
