"""Support verdicts for the claim walk: the ones scoring counted, and the judge only when asked.

The verdict a fact's badge shows must be the one behind the primary outcome (support_share), so it
is read from the run's score.json: scoring (WP D, scoring/support.py) writes every fact's label and
every claim's verdict to `detail.support` ([{row_id, fact_id, label, claims: [{claim_id, label,
rationale, model}]}]). Reading them costs no model call and cannot disagree with the score.

Only when the request asks for it (`?judge=true`), claims that have no scored verdict (the run is
not scored yet, or the judge was unreachable then) are put to the judge (WP C2, gold/judge.py:
`support(fact, quote, *, context=None)`) live, with the inputs scoring gives it through
`support_pair`: the fact's s/p/o, the claim's exact quote and the calibrated context
(gold.judge.context_for: the paper id and the text around the quote, read through gold.review.Corpus,
the frozen corpus with its manifest check). So the verdict is the one the judge was calibrated on, and
the judge's cache ($GOLD/judge-cache.jsonl, keyed by those inputs) is shared with scoring. A quote
whose context the corpus cannot give is not asked, as scoring leaves it pending. Those verdicts are
marked `source: judge`; the calls run concurrently, each with a timeout, and a judge call appends to
the judge's cache, the one write a GET can cause.

Both modules are looked up with importlib (which honours sys.modules) when needed, and the app can
be given its own judge callable instead (tests use a fake); anything going wrong (no judge yet, no
model reachable, a reply of another shape) leaves the verdict out instead of failing the walk.
"""
from __future__ import annotations

import asyncio
import functools
import importlib
import inspect
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anyio
from pydantic import ValidationError

from .models import FactWalk, Verdict

TIMEOUT_S = 90.0
RANK = {"supports": 2, "partial": 1, "no": 0}
logger = logging.getLogger("webapp.judge")


def _attr(module: str, name: str) -> Any:
    try:
        return getattr(importlib.import_module(module), name, None)
    except ImportError:
        return None


def default_support() -> Callable[..., Any] | None:
    """gold.judge.support (WP C2), or None while that module does not exist."""
    return _attr("gold.judge", "support")


NO_CONTEXT = object()  # the corpus cannot give the quote's context: the quote is not asked


@functools.lru_cache(maxsize=4)
def _corpus(root: str) -> Any:
    """gold.review.Corpus over the corpus directory (manifest-checked reads, bounded text caches)."""
    return importlib.import_module("gold.review").Corpus(root)


def calibrated_context(file: str | None, anchor: Any, corpus: Path | None) -> Any:
    """The context scoring's support_pair gives the judge with a quote (gold.judge.context_for over
    the anchor's raw offsets); None when gold.judge has no context_for (a stand-in judge module);
    NO_CONTEXT when there is no corpus, no anchor, or the corpus refuses the file."""
    fn = _attr("gold.judge", "context_for")
    if fn is None:
        return None
    if corpus is None or not file or anchor is None:
        return NO_CONTEXT
    try:
        return fn(_corpus(str(corpus)), file, int(anchor.start), int(anchor.end))
    except Exception as exc:  # review.Rejected, a missing manifest: scoring would leave it pending too
        logger.warning("no judge context for %s: %s: %s", file, type(exc).__name__, exc)
        return NO_CONTEXT


def verdict(data: Any, source: str) -> Verdict | None:
    data = data.model_dump() if hasattr(data, "model_dump") else data
    if not isinstance(data, dict) or data.get("label") not in RANK:
        return None
    try:
        return Verdict.model_validate({**data, "source": source})
    except ValidationError as exc:
        logger.warning("verdict of an unexpected shape: %s", exc)
        return None


def best(verdicts: list[Verdict | None]) -> Verdict | None:
    """The strongest verdict over a fact's quotes (supports > partial > no)."""
    found = [v for v in verdicts if v is not None]
    return max(found, key=lambda v: RANK.get(v.label, -1)) if found else None


def fact_label(verdicts: list[Verdict | None]) -> str:
    """scoring.support.fact_label: unsourced without claims; the best verdict when one supports or
    all are known; else pending."""
    if not verdicts:
        return "unsourced"
    top = best(verdicts)
    if top is not None and (top.label == "supports" or all(v is not None for v in verdicts)):
        return top.label
    return "pending"


# --- the verdicts scoring counted -----------------------------------------------------------------------

def add_scored(walk: FactWalk, score: Any) -> None:
    """Each claim's verdict and the fact's label from score.json's detail.support, when it has them."""
    detail = ((score.get("detail") or {}).get("support") if isinstance(score, dict) else None) or []
    fact = next((f for f in detail if isinstance(f, dict) and f.get("fact_id") == walk.fact.id
                 and f.get("row_id") in (None, walk.row_id)), None)
    if fact is None:
        return
    claims = {c.get("claim_id"): {k: v for k, v in c.items() if k not in ("claim_id", "file")}
              for c in fact.get("claims") or [] if isinstance(c, dict)}
    for item in walk.claims:
        item.support = verdict(claims.get(item.claim_id), "score")
    walk.support = best([item.support for item in walk.claims])
    label = fact.get("label")
    walk.label = label if label in ("supports", "partial", "no", "unsourced", "pending") else None


# --- asking the judge -------------------------------------------------------------------------------------

async def ask(fn: Callable[..., Any], fact: dict[str, Any], quote: str, context: str | None) -> Verdict | None:
    spo = {k: fact[k] for k in ("s", "p", "o")}
    try:
        async with asyncio.timeout(TIMEOUT_S):
            if inspect.iscoroutinefunction(fn):
                result = await fn(spo, quote, context=context)
            else:
                result = await anyio.to_thread.run_sync(lambda: fn(spo, quote, context=context))
                if inspect.isawaitable(result):
                    result = await result
    except Exception as exc:  # the walk is still useful without a verdict
        logger.warning("judge failed: %s: %s", type(exc).__name__, exc)
        return None
    return verdict(result, "judge")


async def add_live(walk: FactWalk, fn: Callable[..., Any] | None, corpus: Path | None) -> None:
    """Ask the judge, concurrently, about every quote without a verdict yet; then the fact's label."""
    todo = [item for item in walk.claims if item.support is None and item.claim is not None and item.claim.quote]
    if fn is None or not todo:
        return
    fact = walk.fact.model_dump()
    contexts = [calibrated_context(item.claim.file, item.claim.anchor, corpus) for item in todo]
    todo, contexts = ([t for t, c in zip(todo, contexts) if c is not NO_CONTEXT],
                      [c for c in contexts if c is not NO_CONTEXT])
    found = await asyncio.gather(*(ask(fn, fact, item.claim.quote, context) for item, context in zip(todo, contexts)))
    for item, v in zip(todo, found):
        item.support = v
    verdicts = [item.support for item in walk.claims if item.claim is not None]  # scoring's pairs: accepted claims
    walk.support = best(verdicts)
    walk.label = fact_label(verdicts)
