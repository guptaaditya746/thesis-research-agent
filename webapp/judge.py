"""The quote-supports-fact judge for the claim walk: gold/judge.py, if it is there.

The judge (milestone 3, `support(fact, quote, *, context=None) -> Verdict`) caches every verdict in
$GOLD/judge-cache.jsonl, keyed by its inputs, so asking it here with the same inputs scoring uses
(the fact's s/p/o and the claim's exact quote, no context) costs no model call once a run is
scored. It is imported only when asked for, and anything going wrong (no judge module yet, no
model reachable, a verdict of another shape) leaves the verdict out instead of failing the walk.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

import anyio
from pydantic import ValidationError

from .models import Verdict

TIMEOUT_S = 90.0
RANK = {"supports": 2, "partial": 1, "no": 0}
logger = logging.getLogger("webapp.judge")


async def support(fact: dict[str, Any], quote: str) -> Verdict | None:
    try:
        from gold import judge
    except ImportError:
        return None
    fn = getattr(judge, "support", None)
    if fn is None:
        return None
    spo = {k: fact[k] for k in ("s", "p", "o")}
    try:
        async with asyncio.timeout(TIMEOUT_S):
            if inspect.iscoroutinefunction(fn):
                result = await fn(spo, quote)
            else:
                result = await anyio.to_thread.run_sync(lambda: fn(spo, quote))
                if inspect.isawaitable(result):
                    result = await result
    except Exception as exc:  # the walk is still useful without a verdict
        logger.warning("judge failed: %s: %s", type(exc).__name__, exc)
        return None
    data = result.model_dump() if hasattr(result, "model_dump") else result
    try:
        return Verdict.model_validate(data)
    except ValidationError as exc:
        logger.warning("judge verdict of an unexpected shape: %s", exc)
        return None


def best(verdicts: list[Verdict | None]) -> Verdict | None:
    """The strongest verdict over a fact's quotes (supports > partial > no)."""
    found = [v for v in verdicts if v is not None]
    return max(found, key=lambda v: RANK.get(v.label, -1)) if found else None
