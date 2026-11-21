"""/api/evqa/questions: the Workbench questions pane (S2). Read-only over the frozen questions and gold files.

A hold-out domain (evqa/holdout.py) shows only its question list, without `answerable`; a question's detail (gold
SPARQL, rows, answer) is 403."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from evqa import holdout
from evqa.seed import qview, questions

router = APIRouter(prefix="/evqa")


def _domain(domain: str) -> str:
    if not (domain.isidentifier() and (questions.gold_dir(domain) / "manifest.json").is_file()):
        raise HTTPException(404, f"no questions for domain {domain!r}")
    return domain


@router.get("/questions/{domain}")
def listing(domain: str) -> dict[str, Any]:
    out = qview.listing(_domain(domain))
    if holdout.gold_closed(domain):
        out["questions"] = [{k: v for k, v in q.items() if k != "answerable"} for q in out["questions"]]
    return out


@router.get("/questions/{domain}/{qid}")
def detail(domain: str, qid: str) -> dict[str, Any]:
    why = holdout.gold_closed(_domain(domain))
    if why:
        raise HTTPException(403, why)
    try:
        return qview.detail(domain, qid)
    except KeyError:
        raise HTTPException(404, f"no question {qid!r} in {domain!r}") from None
