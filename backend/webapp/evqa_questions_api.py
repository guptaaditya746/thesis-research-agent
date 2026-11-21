"""/api/evqa/questions: the Workbench questions pane (S2). Read-only over the frozen questions and gold files."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from evqa.seed import qview, questions

router = APIRouter(prefix="/evqa")


def _domain(domain: str) -> str:
    if not (domain.isidentifier() and (questions.gold_dir(domain) / "manifest.json").is_file()):
        raise HTTPException(404, f"no questions for domain {domain!r}")
    return domain


@router.get("/questions/{domain}")
def listing(domain: str) -> dict[str, Any]:
    return qview.listing(_domain(domain))


@router.get("/questions/{domain}/{qid}")
def detail(domain: str, qid: str) -> dict[str, Any]:
    try:
        return qview.detail(_domain(domain), qid)
    except KeyError:
        raise HTTPException(404, f"no question {qid!r} in {domain!r}") from None
