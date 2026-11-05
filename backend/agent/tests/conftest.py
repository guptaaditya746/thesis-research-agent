from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path

import repo_paths
from typing import Any

REPO = repo_paths.REPO
FIXTURES = Path(__file__).resolve().parent / "fixtures"
DOCLING = repo_paths.TESTS / "D1" / "docling"
MANIFEST = repo_paths.CORPUS_MANIFEST


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@cache
def papers() -> dict[str, str]:
    """The 10 D1 Docling papers with LF line ends, as in the frozen corpus.

    A Windows checkout with core.autocrlf=true has CRLF in the working copy; the corpus on the
    Linux node has LF, and the column-break offsets in tests/RESULTS.md (appendix D1 column order) are LF offsets.
    """
    return {p.stem: p.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
            for p in sorted(DOCLING.glob("*.md"))}


def write_corpus(root: Path) -> tuple[Path, Path]:
    """A corpus dir with the 10 papers as p1.md..p10.md and a manifest in the D5 format."""
    corpus = root / "corpus"
    corpus.mkdir()
    entries = []
    for n, (name, text) in enumerate(papers().items(), 1):
        data = text.encode("utf-8")
        (corpus / f"p{n}.md").write_bytes(data)
        entries.append({"id": f"p{n}", "source_pdf": f"/pdfs/{name}.pdf", "source_sha256": "0" * 64,
                        "markdown_sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                        "docling_version": "2.110.0", "conversion_seconds": 1.0, "failure": None})
    entries.append({"id": "p99", "source_pdf": "/pdfs/scanned.pdf", "source_sha256": "0" * 64,
                    "markdown_sha256": None, "bytes": 0, "docling_version": "2.110.0",
                    "conversion_seconds": 1.0, "failure": "scanned"})
    manifest = corpus / "manifest.json"
    manifest.write_text(json.dumps({"docling_version": "2.110.0", "paper_count": len(entries),
                                    "papers": entries}, indent=2), encoding="utf-8")
    return corpus, manifest


def paper_file(name: str) -> str:
    """Corpus file name that write_corpus gives the D1 paper `name`."""
    return f"p{list(papers()).index(name) + 1}.md"
