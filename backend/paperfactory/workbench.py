"""Copy a paperfactory run's checked papers into the Workbench's folders (22 Nov 2026).

The Workbench reads a domain from data/seed/<domain>/ (truth) and data/dataset/<domain>/<paper>/paper.md (the paper).
A paperfactory domain carries `paperfactory.json` next to its seed.ttl; evqa/seed/pview.py and view.py read that file
instead of the evqa schema (paperfactory facts are relations between entities, not numbers, so the numbers check does
not apply). Only papers that passed the check (the ones in tagged.json) are copied.

Each fact's spans are the sentences the tagger + verifier accepted for it, moved from the normalized text the tagger
read to offsets in the original paper.md (text.Paper.back).

  uv run paperfactory export-workbench --config backend/paperfactory/configs/qwen/pilot40-law.json --domain pf_law
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from repo_paths import DATA

from paperfactory.text import normalize_paper

BRIEFS = ("idea_sparse.md", "experimental_log.md")


def _title(md: str, fallback: str) -> str:
    first = next((ln for ln in md.splitlines() if ln.strip()), "")
    return first.lstrip("# ").strip() if first.startswith("#") else fallback


def _raw_spans(md: str, spans: list[list[int]]) -> list[list[int]]:
    back = normalize_paper(md).back
    return [[back[a], back[b - 1] + 1] for a, b in spans]


def export(run: Path, domain: str, data: Path = DATA) -> dict[str, Any]:
    if not domain.isidentifier():
        raise ValueError(f"bad domain name {domain!r} (letters, digits and _ only)")
    w = json.loads((run / "world.json").read_text(encoding="utf-8"))
    tagged = json.loads((run / "tagged.json").read_text(encoding="utf-8"))["papers"]
    ents = w["entities"]
    seed_dir, ds_dir = data / "seed" / domain, data / "dataset" / domain
    if seed_dir.exists() and not (seed_dir / "paperfactory.json").is_file():
        raise ValueError(f"{seed_dir} exists and is not a paperfactory export; pick another domain name")
    for d in (seed_dir, ds_dir):
        if d.exists():
            shutil.rmtree(d)
    papers = []
    for pid in sorted(tagged):
        md = (run / "work" / pid / "paper.md").read_text(encoding="utf-8")
        plan, t = w["papers"][pid], tagged[pid]
        facts = []
        for kind in ("claims", "decoys"):
            for s, r, o in plan.get(kind, []):
                fid = f"{s}-{r}-{o}"
                facts.append({"id": fid, "kind": kind[:-1], "subject": ents[s]["label"], "relation": r,
                              "object": ents[o]["label"], "spans": _raw_spans(md, t["spans"].get(fid, []))})
        papers.append({"id": pid, "title": _title(md, plan.get("title_hint", pid)), "issue": plan.get("issue", ""),
                       "thesis": plan.get("thesis", ""), "facts": facts})
        (ds_dir / pid).mkdir(parents=True)
        (ds_dir / pid / "paper.md").write_text(md, encoding="utf-8")
        (seed_dir / "papers" / pid).mkdir(parents=True)
        for b in BRIEFS:
            src = run / "papers" / pid / b
            if src.is_file():
                shutil.copy2(src, seed_dir / "papers" / pid / b)
    shutil.copy2(run / "seed.ttl", seed_dir / "seed.ttl")
    manifest = {"source": "paperfactory", "run": str(run), "field": w["field"], "genre": w["genre"],
                "planned": len(w["papers"]), "papers": papers}
    (seed_dir / "paperfactory.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"domain": domain, "papers": len(papers), "planned": len(w["papers"])}
