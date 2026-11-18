"""A local pool of real papers: `raw/<id>.xml` (PMC only), `full/<id>.md` (tidy papers that fit), `index.json`."""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Callable

import hashlib
import json
from collections import Counter
from random import Random

from jsonio import write_json_atomic, write_text_atomic
from synth2.realpool import cut_pieces, md_blocks, words, write_pieces
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


def _used_by_split(pool: Path, pid: str) -> bool:
    path = pool / "split.json"
    if not path.is_file():
        return False
    split = json.loads(path.read_text(encoding="utf-8"))
    return pid in split["test"] or pid in split["sources"]


def _refuse_change(pool: Path, pid: str, what: str) -> ValueError:
    return ValueError(f"{pid}: {what}, but split.json lists it, so full/{pid}.md must stay as it is. Restore the "
                      "real config that made the split and run again (a new split needs a new pool folder)")


def add_paper(pool: Path, paper: PoolPaper, rs: RealSpec) -> dict:
    """Tidy the paper, write `full/<id>.md` only when it fits, and return its index row. Once split.json exists, a
    paper it lists is never removed or changed (ValueError)."""
    paper = replace(paper, text=tidy(paper.text, rs))
    why = unfit(paper, rs)
    target = pool / "full" / f"{paper.id}.md"
    if _used_by_split(pool, paper.id):
        if why is not None:
            raise _refuse_change(pool, paper.id, f"the config now finds it unfit ({why})")
        if not target.is_file() or target.read_text(encoding="utf-8") != paper.text:
            raise _refuse_change(pool, paper.id, "the config now tidies it differently")
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
            if _used_by_split(pool, pid):
                raise _refuse_change(pool, pid, f"its raw file no longer reads ({err})") from err
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


def split_pool(pool: Path, rs: RealSpec) -> dict:
    """Seeded split of the kept papers into test and sources; cuts the test papers into pieces."""
    path = pool / "split.json"
    if path.exists():
        raise ValueError(f"{path}: refusing to overwrite: a new split could move test papers into sources")
    ids = sorted(r["id"] for r in load_index(pool) if r["kept"])
    if len(ids) < rs.n_test + 1:
        raise ValueError(f"pool has {len(ids)} kept papers; need at least {rs.n_test + 1} "
                         f"({rs.n_test} test and one source)")
    seed = f"synth3:pool:{rs.domain}:split"
    Random(seed).shuffle(ids)
    test, sources = ids[:rs.n_test], ids[rs.n_test:]
    canon = json.dumps({"test": test, "sources": sources}, sort_keys=True, separators=(",", ":"))
    out = {"seed": seed, "test": test, "sources": sources,
           "counts": {"test": len(test), "sources": len(sources)},
           "sha256": hashlib.sha256(canon.encode("utf-8")).hexdigest()}
    dst = pool / "pieces"
    dst.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []
    notes: list[str] = []
    for pid in test:
        bl = md_blocks((pool / "full" / f"{pid}.md").read_text(encoding="utf-8"))
        title = next((b for _, b in bl if b.startswith("# ")), f"# {pid}")
        abstract = [b for s, b in bl if s == "Abstract"]
        body = [(s, b) for s, b in bl if s not in ("", "Abstract")]
        write_pieces(pid, cut_pieces(title, abstract, body), dst, index, notes)
    write_json_atomic(dst / "index.json", index)
    write_json_atomic(path, out)
    return out


def load_split(pool: Path) -> dict:
    path = pool / "split.json"
    if not path.is_file():
        raise ValueError(f"{path}: not found; run synth3 pool-split first")
    return json.loads(path.read_text(encoding="utf-8"))


def source_order(split: dict, domain: str) -> list[str]:
    order = list(split["sources"])
    Random(f"synth3:pool:{domain}:sources").shuffle(order)
    return order


def folder_sources(order: list[str], seed: int, n: int) -> list[str]:
    """`order` rotated to start at this folder's place: the first `n` are its sources, the rest are reserves."""
    if len(order) < n:
        raise ValueError(f"pool has {len(order)} source papers; a folder of {n} studies needs at least {n}")
    k = ((seed - 1) * n) % len(order)
    return order[k:] + order[:k]
