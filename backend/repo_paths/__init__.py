"""Where the repo's top folders are: one place, so a folder move changes one line (docs/architecture.md, layout).

Not hashed into any extractor id (evidence/extractors/base.py hashes paths relative to backend/), so it may change.
"""
from __future__ import annotations

from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]     # every Python package
REPO = BACKEND.parent
DATA = REPO / "data"                            # submodule thesis-benchmark (seed, dataset)
FRONTEND = REPO / "frontend"                    # submodule thesis-workbench (its dist/ is served)
