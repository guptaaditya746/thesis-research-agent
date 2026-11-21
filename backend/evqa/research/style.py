"""Style examples for the v2 paper writer, chosen by code (the model never searches).

Input:  data/style/<domain>/<id>/{excerpts.md, source.json} (short CC BY / CC0 excerpts of real trial reports) and
        the brief (experimental_log.md), from which code builds one Semantic Scholar query (evqa.research.s2).
Output: [{id, about, license, source, sections: {section name: text}}]:
        2 stored excerpt sets (picked by a hash of the paper title, so papers see different examples) and
        up to 2 retrieved real abstracts (CC BY / CC0 only) as Abstract examples.
The writer receives these as 'style_examples' (manner only); fact_check.exemplar_leaks checks nothing was copied.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from repo_paths import REPO

STYLE = REPO / "data" / "style"
SECTIONS = ("Methods: participants", "Results: mean difference vs placebo", "Results: table",
            "Discussion: limitations")


def style_dir(domain: str) -> Path:
    """data/style/<domain>; a variant domain such as medical_holdout uses its base domain's examples."""
    return STYLE / domain.split("_")[0]


def load_excerpts(sdir: Path) -> list[dict[str, Any]]:
    out = []
    for d in sorted(p for p in Path(sdir).iterdir() if p.is_dir()) if Path(sdir).is_dir() else []:
        md = d / "excerpts.md"
        if not md.is_file():
            continue
        src = json.loads((d / "source.json").read_text(encoding="utf-8")) if (d / "source.json").is_file() else {}
        text = md.read_text(encoding="utf-8")
        secs = {m.group(1).strip(): m.group(2).strip()
                for m in re.finditer(r"^## (.+?)\n(.*?)(?=^## |\Z)", text, re.M | re.S)
                if m.group(1).strip() in SECTIONS and not m.group(2).strip().startswith("Note (not an excerpt)")}
        if secs:
            # 'about' = the drug's name only (its first word): the header of the example and the name leak check
            about = (src.get("drug") or "").split(" ")[0].strip(",;()")
            out.append({"id": d.name, "about": about, "license": src.get("license", ""),
                        "source": src.get("source_url") or src.get("doi", ""), "sections": secs,
                        "s2_paperId": src.get("s2_paperId")})
    return out


def pick(items: list[dict[str, Any]], key: str, n: int) -> list[dict[str, Any]]:
    if len(items) <= n:
        return list(items)
    start = int(hashlib.sha256(key.encode()).hexdigest(), 16) % len(items)
    return [items[(start + i) % len(items)] for i in range(n)]


def retrieved_abstracts(log_md: str, n: int = 2, *, search=None) -> list[dict[str, Any]]:
    """Up to n CC BY / CC0 abstracts from one code-built S2 query. A failed search returns [] (logged by caller)."""
    from evqa.research import s2
    search = search or s2.search
    full = s2.query_from_brief(log_md)
    words = full.split()
    # S2 search is keyword based and returns nothing for long queries: drop words after the design words one at
    # a time (keeping the last two, measure + "trial") until something comes back. Deterministic, cached.
    rows, q = [], full
    for cut in range(0, max(len(words) - 4, 0) + 1):
        q = " ".join(words[:2] + words[2 + cut:])
        rows = [r for r in search(q, 10)
                if r.get("abstract") and len(r["abstract"].split()) >= 120]
        if len(rows) >= n:
            break
    out = []
    for r in rows:
        if r.get("abstract") and r.get("oa_license") in s2.OPEN_LICENSES and len(r["abstract"].split()) >= 120:
            out.append({"id": f"S2:{r['paperId']}", "about": "", "license": r["oa_license"],
                        "source": r.get("url") or "", "query": q, "sections": {"Abstract": r["abstract"].strip()}})
        if len(out) == n:
            break
    return out


def build(paper_dir: Path, domain: str, *, n_excerpts: int = 2, n_abstracts: int = 2, search=None,
          sdir: Path | None = None) -> list[dict[str, Any]]:
    paper_dir = Path(paper_dir)
    idea = (paper_dir / "idea_sparse.md").read_text(encoding="utf-8")
    log_md = (paper_dir / "experimental_log.md").read_text(encoding="utf-8")
    title = idea.splitlines()[0] if idea else paper_dir.name
    ex = pick(load_excerpts(sdir or style_dir(domain)), title, n_excerpts)
    if not ex:
        raise FileNotFoundError(f"no style excerpts under {sdir or style_dir(domain)}")
    try:
        ab = retrieved_abstracts(log_md, n_abstracts, search=search) if n_abstracts else []
    except Exception:  # noqa: BLE001 - the stored excerpts are enough to write; retrieval is a bonus
        ab = []
    return ex + ab


def build_with_research(paper_dir: Path, domain: str, *, log_path: Path | None = None, lm=None, search=None,
                        n_excerpts: int = 2, sdir: Path | None = None) -> tuple[list, list, dict]:
    """v2r (C8): the research loop (evqa.research.agent, Qwen picks) instead of the one code-built query.
    Returns (style examples = stored excerpts + picked style abstracts, references for citing, loop result)."""
    from evqa.research import agent
    paper_dir = Path(paper_dir)
    idea = (paper_dir / "idea_sparse.md").read_text(encoding="utf-8")
    title = idea.splitlines()[0] if idea else paper_dir.name
    ex = pick(load_excerpts(sdir or style_dir(domain)), title, n_excerpts)
    if not ex:
        raise FileNotFoundError(f"no style excerpts under {sdir or style_dir(domain)}")
    stored = {e["s2_paperId"] for e in load_excerpts(sdir or style_dir(domain)) if e.get("s2_paperId")}
    res = agent.research(paper_dir, lm=lm, search=search, log_path=log_path, skip_style_ids=stored)
    return ex + agent.as_style(res["style"]), agent.as_references(res["references"]), res
