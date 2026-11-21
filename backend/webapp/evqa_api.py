"""/api/evqa: the Workbench's read API over the evqa files. S1: the dataset pane (seed table, folder tree)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from evqa import holdout
from evqa.paths import SEED
from evqa.seed import view

router = APIRouter(prefix="/evqa")


def _domain(domain: str) -> str:
    if not (domain.isidentifier() and (SEED / domain / "seed.ttl").is_file()):
        raise HTTPException(404, f"no seed for domain {domain!r}")
    return domain


@router.get("/dataset")
def domains() -> list[str]:
    return sorted(p.parent.name for p in SEED.glob("*/seed.ttl"))


@router.get("/dataset/{domain}")
def overview(domain: str) -> dict[str, Any]:
    return view.overview(_domain(domain))


@router.get("/files")
def files() -> list[dict[str, Any]]:
    return view.tree()


@router.get("/file")
def file(path: str) -> dict[str, Any]:
    parts = path.split("/")   # data/seed/<domain>/gold/...: a hold-out domain's gold stays closed
    if len(parts) > 3 and parts[:2] == ["data", "seed"] and parts[3] == "gold" and holdout.gold_closed(parts[2]):
        raise HTTPException(403, holdout.gold_closed(parts[2]))
    try:
        return view.read_file(path)
    except KeyError:
        raise HTTPException(404, f"{path} is not a dataset file") from None
