"""/api/evqa/review: the optional human review queue (evqa/seed/review.py). Labels are the only thing written.

    GET  /api/evqa/review/tasks                      every task: title, question, choices with rubric, parts
    GET  /api/evqa/review/{task}/summary?scope=      coverage and label counts (Evaluation page)
    GET  /api/evqa/review/{task}/items?scope=&reviewer=   the sample; automated verdicts only on items this
                                                     reviewer already labelled
    POST /api/evqa/review/{task}/labels              {scope, item_id, item_version, reviewer, choice, parts, note}
                                                     -> {saved, automated}: the verdict is shown after the label

scope = a domain (fidelity) or a run id (population). 404 for an unknown task,
item or run, 409 when the item changed since it was shown, 422 for a bad choice or an empty reviewer name.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from evqa.seed import review

router = APIRouter(prefix="/evqa/review")


class LabelIn(BaseModel):
    scope: str
    item_id: str
    item_version: str
    reviewer: str
    choice: str
    parts: list[str] = []
    note: str = ""


def _call(fn: Any, *args: Any, **kw: Any) -> Any:
    try:
        return fn(*args, **kw)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except (KeyError, FileNotFoundError) as e:
        raise HTTPException(404, f"not found: {e}") from None
    except ValueError as e:
        raise HTTPException(409 if "changed" in str(e) else 422, str(e)) from None


def _task(task: str) -> str:
    if task not in review.TASKS:
        raise HTTPException(404, f"no review task {task!r}")
    return task


@router.get("/tasks")
def tasks() -> list[dict[str, Any]]:
    return [{"task": k, **v} for k, v in review.TASKS.items()]


@router.get("/{task}/summary")
def summary(task: str, scope: str) -> dict[str, Any]:
    return _call(review.summary, _task(task), scope)


@router.get("/{task}/items")
def items(task: str, scope: str, reviewer: str = "") -> list[dict[str, Any]]:
    return _call(review.items_for, _task(task), scope, reviewer.strip())


@router.post("/{task}/labels")
def add(task: str, body: LabelIn) -> dict[str, Any]:
    return _call(review.add_label, _task(task), body.scope, body.item_id, body.item_version, body.reviewer,
                 body.choice, body.parts, body.note)
