"""What the Workbench "Paper" pane shows. Read-only: the paper list, the writer's two brief files, paper.md if it
is written, and the L0 result (seed fact spans, extra numbers) so the UI can colour them.

The L0 file is used when it was made from the same paper.md (same sha256); otherwise L0 runs again in memory
(nothing is written by a view).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from evqa.eval import dataset
from evqa.paths import REPO, brief_dir, paper_file
from evqa.seed import pfview
from evqa.seed.brief import paper_facts

BRIEFS = ("idea_sparse.md", "experimental_log.md")


def _read(path: Any) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def l0(domain: str, paper: str, text: str) -> dict[str, Any]:
    stored = dataset.out_path(domain, paper)
    if stored.is_file():
        data = json.loads(stored.read_text(encoding="utf-8"))
        if data.get("paper_sha256") == hashlib.sha256(text.encode("utf-8")).hexdigest():
            return {**data, "stored": True}
    return {**dataset.check(domain, paper, text=text, write=False), "stored": False}


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else path.as_posix()


def papers(domain: str) -> list[dict[str, Any]]:
    if pfview.is_pf(domain):
        return pfview.papers(domain)
    out = []
    for pid, p in paper_facts(domain).items():
        folder = brief_dir(domain, pid)
        text = _read(paper_file(domain, pid))
        out.append({"id": pid, "title": p["title"], "role": p["role"], "split": p["split"], "facts": len(p["facts"]),
                    "has_brief": all((folder / b).is_file() for b in BRIEFS), "has_paper": text is not None,
                    "l0": l0(domain, pid, text)["summary"] if text is not None else None})
    return out


def paper(domain: str, pid: str) -> dict[str, Any]:
    if pfview.is_pf(domain):
        return pfview.paper(domain, pid)
    p = paper_facts(domain).get(pid)
    if p is None:
        raise KeyError(pid)
    folder = brief_dir(domain, pid)
    text = _read(paper_file(domain, pid))
    return {"id": pid, "title": p["title"], "split": p["split"], "role": p["role"],
            "folder": _rel(paper_file(domain, pid).parent), "brief_folder": _rel(folder),
            "briefs": {b: _read(folder / b) for b in BRIEFS}, "paper": text,
            "l0": l0(domain, pid, text) if text is not None else None}
