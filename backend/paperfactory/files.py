"""Safe file writes: a stopped run never leaves half a file behind (#7)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_text(path: Path, text: str) -> None:
    """Write to a temp file in the same folder, fsync, then os.replace (atomic on POSIX)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_json(path: Path, obj: Any, indent: int | None = 1) -> None:
    write_text(path, json.dumps(obj, indent=indent, ensure_ascii=False))
