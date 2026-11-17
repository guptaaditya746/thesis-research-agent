"""A local pool of real papers: `raw/<id>.xml` (PMC only), `full/<id>.md` (tidy papers that fit), `index.json`."""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Callable

import json
from collections import Counter

from jsonio import write_json_atomic, write_text_atomic
from synth2.realpool import words
from synth3.pmc import PoolPaper, jats_paper, tidy, unfit
from synth3.realspec import RealSpec


def load_index(pool: Path) -> list[dict]:
    path = pool / "index.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def save_index(pool: Path, rows: list[dict]) -> None:
    write_json_atomic(pool / "index.json", sorted(rows, key=lambda r: r["id"]))


def _row(paper: PoolPaper, text: str, kept: bool, why: str) -> dict:
    tables = sum(b.lstrip().startswith("|") for b in re.split(r"\n\s*\n", text))
    return {"id": paper.id, "title": paper.title, "year": paper.year, "journal": paper.journal,
            "license": paper.license, "words": words(text), "tables": tables, "kept": kept, "why": why}


def _failed(pid: str, why: str) -> dict:
    return {"id": pid, "title": "", "year": None, "journal": "", "license": "", "words": 0, "tables": 0,
            "kept": False, "why": why}


def add_paper(pool: Path, paper: PoolPaper, rs: RealSpec) -> dict:
    """Tidy the paper, write `full/<id>.md` only when it fits, and return its index row."""
    paper = replace(paper, text=tidy(paper.text, rs))
    why = unfit(paper, rs)
    target = pool / "full" / f"{paper.id}.md"
    if why is None:
        target.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(target, paper.text)
    else:
        target.unlink(missing_ok=True)
    return _row(paper, paper.text, why is None, why or "")


def rebuild(pool: Path, rs: RealSpec, missing: list[str]) -> list[dict]:
    """Rows for every raw file, the earlier rows that have no raw file, and `missing` ids ('not returned')."""
    raws = {p.stem: p for p in (pool / "raw").glob("*.xml")}
    rows = {r["id"]: r for r in load_index(pool) if r["id"] not in raws}
    for pid in missing:
        rows[pid] = _failed(pid, "not returned")
    for pid, path in sorted(raws.items()):
        try:
            paper = jats_paper(path.read_bytes())
        except ValueError as err:
            (pool / "full" / f"{pid}.md").unlink(missing_ok=True)
            rows[pid] = _failed(pid, str(err))
            continue
        rows[pid] = add_paper(pool, replace(paper, id=pid), rs)
    out = list(rows.values())
    save_index(pool, out)
    return out


def _docling_pdf(data: bytes) -> str:
    from evidence.arxiv import docling_markdown
    return docling_markdown(data, "pdf")


def _markdown_paper(pid: str, text: str) -> PoolPaper:
    title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), "")
    return PoolPaper(id=pid, title=title, year=None, journal="", license="", article_type="research-article",
                     text=text)


def import_files(src: Path, pool: Path, rs: RealSpec,
                 convert_pdf: Callable[[bytes], str] | None = None) -> dict:
    """Add every `.md`, `.xml` and `.pdf` file of `src` to the pool; the id is the file stem."""
    convert_pdf = convert_pdf or _docling_pdf
    rows = {r["id"]: r for r in load_index(pool)}
    mine: list[str] = []
    for path in sorted(p for p in src.iterdir() if p.is_file() and p.suffix.lower() in (".md", ".xml", ".pdf")):
        mine.append(path.stem)
        pid, kind = path.stem, path.suffix.lower()
        try:
            if kind == ".md":
                paper = _markdown_paper(pid, path.read_text(encoding="utf-8"))
            elif kind == ".xml":
                paper = replace(jats_paper(path.read_bytes()), id=pid, article_type="research-article")
            else:
                paper = _markdown_paper(pid, convert_pdf(path.read_bytes()))
        except (ValueError, OSError, RuntimeError) as err:
            rows[pid] = _failed(pid, str(err))
            continue
        rows[pid] = add_paper(pool, paper, rs)
    out = list(rows.values())
    save_index(pool, out)
    got = [rows[i] for i in mine]
    return {"fetched": len(got), "cached": 0, "kept": sum(r["kept"] for r in got),
            "unfit": dict(Counter(r["why"] for r in got if not r["kept"]))}
