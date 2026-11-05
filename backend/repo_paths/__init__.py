"""Where the repo's top folders are: one place, so a folder move changes one line (docs/architecture.md, layout).

Not hashed into any extractor id (evidence/extractors/base.py hashes paths relative to backend/), so it may change.
"""
from __future__ import annotations

from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]     # every Python package
REPO = BACKEND.parent
DATA = REPO                                     # checked-in inputs
DOMAINS = DATA / "domains"                      # domain packs
QUESTIONS_FILE = DATA / "questions" / "questions.json"   # the 12 questions of the earlier work
CONCEPTS = DATA / "concepts"                    # concept sessions of the earlier work
CORPUS_MANIFEST = DATA / "corpus" / "manifest.json"      # the frozen corpus of the earlier work (D5)
TESTS = REPO / "tests"                          # test results and the EV corpora (tests/EV*), not pytest code
EV2_CORPORA = TESTS / "EV2" / "corpora"
FRONTEND = REPO / "frontend"
REPORTS = REPO / "reports"
SCRIPTS = REPO / "scripts"
