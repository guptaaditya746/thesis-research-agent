from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
DOCLING = REPO / "tests" / "D1" / "docling"
MANIFEST = REPO / "corpus" / "manifest.json"


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def read_raw(path: Path) -> str:
    """File text exactly as stored (no newline translation), as the anchor library sees it."""
    return path.read_bytes().decode("utf-8")
