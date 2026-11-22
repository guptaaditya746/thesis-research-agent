"""Workbench views of a paperfactory domain (data/seed/<domain>/paperfactory.json, made by paperfactory/workbench.py).

Paperfactory facts are relations between invented entities ("Laper v. Dravun Media relies_on section 1"), not
numbers, so the L0 numbers check does not apply. The paper pane gets the same L0 shape it always reads: each planted
fact is "found" where the tagger + verifier accepted a sentence for it (its spans), "missing" otherwise; no extra or
ignored numbers. Read-only; never imports paperfactory (engine may not import evaluation).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from evqa.paths import REPO, brief_dir, domain_dir, paper_file

MANIFEST = "paperfactory.json"
BRIEFS = ("idea_sparse.md", "experimental_log.md")


def is_pf(domain: str) -> bool:
    return (domain_dir(domain) / MANIFEST).is_file()


def _manifest(domain: str) -> dict[str, Any]:
    return json.loads((domain_dir(domain) / MANIFEST).read_text(encoding="utf-8"))


def _read(path: Any) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else path.as_posix()


def _measure(f: dict[str, Any]) -> str:
    return f"{f['subject']} {f['relation'].replace('_', ' ')} {f['object']} ({f['kind']})"


def l0(p: dict[str, Any], text: str) -> dict[str, Any]:
    facts = [{"id": f["id"], "value": "", "unit": "", "unit_text": "", "measure": _measure(f), "dose": None,
              "dose_text": None, "week": None, "placement": "text", "status": "found" if f["spans"] else "missing",
              "in_planned_place": bool(f["spans"]), "near": [],
              "spans": [{"start": a, "end": b, "raw": text[a:b], "where": "text", "keys": {}, "score": 1.0,
                         "ambiguous": False, "unit_stated": False} for a, b in f["spans"]]} for f in p["facts"]]
    found = sum(f["status"] == "found" for f in facts)
    return {"summary": {"facts": len(facts), "found": found, "in_planned_place": found, "missing": len(facts) - found,
                        "extra": 0, "ignored": 0},
            "facts": facts, "extra": [], "ignored": [], "stored": True,
            "paper_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def _role(p: dict[str, Any]) -> str:
    return f"{sum(f['kind'] == 'claim' for f in p['facts'])} claims, {sum(f['kind'] == 'decoy' for f in p['facts'])} decoys"


def papers(domain: str) -> list[dict[str, Any]]:
    out = []
    for p in _manifest(domain)["papers"]:
        text = _read(paper_file(domain, p["id"]))
        out.append({"id": p["id"], "title": p["title"], "role": _role(p), "split": "passed", "facts": len(p["facts"]),
                    "has_brief": all((brief_dir(domain, p["id"]) / b).is_file() for b in BRIEFS),
                    "has_paper": text is not None, "l0": l0(p, text)["summary"] if text is not None else None})
    return out


def paper(domain: str, pid: str) -> dict[str, Any]:
    p = next((x for x in _manifest(domain)["papers"] if x["id"] == pid), None)
    if p is None:
        raise KeyError(pid)
    text = _read(paper_file(domain, pid))
    folder = brief_dir(domain, pid)
    return {"id": pid, "title": p["title"], "split": "passed", "role": _role(p),
            "folder": _rel(paper_file(domain, pid).parent), "brief_folder": _rel(folder),
            "briefs": {b: _read(folder / b) for b in BRIEFS}, "paper": text,
            "l0": l0(p, text) if text is not None else None}


def overview(domain: str) -> dict[str, Any]:
    """The dataset pane: one row per planted fact (subject, relation as the measure, object as the comparator)."""
    m = _manifest(domain)
    rows = [{"id": f["id"], "paper": p["id"], "split": "passed", "subject": f["subject"], "comparator": f["object"],
             "measure": f["relation"], "context": f["kind"], "condition": None, "time": None, "statistic": "",
             "value": f"{len(f['spans'])} sentences", "unit": "", "placement": "text"}
            for p in m["papers"] for f in p["facts"]]
    papers_ = [{"id": p["id"], "title": p["title"], "role": _role(p), "split": "passed", "kind": m["field"],
                "rows": len(p["facts"])} for p in m["papers"]]
    return {"domain": domain, "papers": papers_, "rows": rows, "check": None}
