"""/api/evqa/papers: the Workbench "Paper" pane (S3). Read-only: briefs, paper.md, L0 spans.

Mount with `app.include_router(router, prefix="/api")`, like webapp/evqa_api.py.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from evqa.paths import SEED
from evqa.seed import pview

router = APIRouter(prefix="/evqa")


def _domain(domain: str) -> str:
    if not (domain.isidentifier() and (SEED / domain / "seed.ttl").is_file()):
        raise HTTPException(404, f"no seed for domain {domain!r}")
    return domain


@router.get("/papers/{domain}")
def papers(domain: str) -> list[dict[str, Any]]:
    return pview.papers(_domain(domain))


@router.get("/papers/{domain}/{paper}")
def paper(domain: str, paper: str) -> dict[str, Any]:
    try:
        return pview.paper(_domain(domain), paper)
    except KeyError:
        raise HTTPException(404, f"no paper {paper!r} in {domain!r}") from None
