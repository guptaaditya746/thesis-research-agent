"""The LLM judge as scoring uses it: gold/judge.py (package C2), imported lazily and never required.

Its three questions (docs/e2e-build-plan.md, Judge):
- support(fact, quote, *, context=None) -> {label: supports | partial | no, rationale, model, ...}
- same_fact(run_fact, key_fact, concept) -> {match: bool, ...}, for the soft fact level;
- same_row(run_row, key_row, concept) -> {match: bool, ...}, for soft row matching.
gold.judge caches every decision in $GOLD/judge-cache.jsonl, keyed by its input, model and prompt
hash, so a rescore costs no model calls.

`Judge` wraps any object with those callables (the gold.judge module, or a fake in tests). It accepts a
pydantic model or a dict as the reply, runs a coroutine to completion, and turns a failed call into a
pending decision: scoring never stops because the judge is unreachable, it reports what is pending
(the labelling repo's `judge_pending`), and the soft level and support share stay open until then.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

LABELS = ("supports", "partial", "no")
MAX_ERRORS = 20
T = TypeVar("T")


def plain(reply: Any) -> Any:
    """A reply as plain JSON data (pydantic models dumped)."""
    if hasattr(reply, "model_dump"):
        return reply.model_dump(mode="json")
    return reply


async def _wait(awaitable: Any) -> Any:
    return await awaitable


class Judge:
    """Calls into a judge implementation; counts calls, pending decisions and errors (thread-safe)."""

    def __init__(self, impl: Any, name: str | None = None) -> None:
        self.impl = impl
        self.name = name or getattr(impl, "__name__", type(impl).__name__)
        self.calls = 0
        self.pending = 0
        self.errors: list[str] = []
        self.models: set[str] = set()
        self._lock = threading.Lock()

    def _call(self, method: str, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        fn = getattr(self.impl, method, None)
        try:
            if fn is None:
                raise AttributeError(f"{self.name} has no {method}()")
            reply = fn(*args, **kwargs)
            if inspect.isawaitable(reply):
                reply = asyncio.run(_wait(reply))
            reply = plain(reply)
            if isinstance(reply, bool):  # a bare yes/no from same_fact or same_row
                reply = {"match": reply}
            if not isinstance(reply, dict):
                raise TypeError(f"{method}() returned {type(reply).__name__}, not a verdict")
        except Exception as exc:  # the judge failing must not stop scoring: the decision stays pending
            with self._lock:
                self.pending += 1
                if len(self.errors) < MAX_ERRORS:
                    self.errors.append(f"{method}: {type(exc).__name__}: {exc}"[:300])
            return None
        with self._lock:
            self.calls += 1
            if reply.get("model"):
                self.models.add(str(reply["model"]))
        return reply

    def support(self, fact: dict[str, Any], quote: str, *, context: str | None = None) -> dict[str, Any] | None:
        """The verdict on one quote for one fact, or None (pending)."""
        reply = self._call("support", fact, quote, context=context)
        if reply is not None and reply.get("label") not in LABELS:
            self._fail(f"support: label {reply.get('label')!r} is not one of {LABELS}")
            return None
        return reply

    def same_fact(self, run_fact: dict[str, Any], key_fact: dict[str, Any], concept: dict[str, Any]) -> bool | None:
        return self._match("same_fact", run_fact, key_fact, concept)

    def same_row(self, run_row: dict[str, Any], key_row: dict[str, Any], concept: dict[str, Any]) -> bool | None:
        return self._match("same_row", run_row, key_row, concept)

    def _match(self, method: str, *args: Any) -> bool | None:
        reply = self._call(method, *args)
        if reply is None:
            return None
        if not isinstance(reply.get("match"), bool):
            self._fail(f"{method}: no boolean 'match' in the reply")
            return None
        return reply["match"]

    def _fail(self, text: str) -> None:
        with self._lock:
            self.calls -= 1
            self.pending += 1
            if len(self.errors) < MAX_ERRORS:
                self.errors.append(text)

    def summary(self) -> dict[str, Any]:
        return {"used": True, "name": self.name, "models": sorted(self.models), "calls": self.calls,
                "pending": self.pending, "errors": list(self.errors)}


def load(enabled: bool = True, *, log: Callable[[str], None] = print) -> Judge | None:
    """The gold.judge module as a Judge; None when disabled or when it cannot be imported."""
    if not enabled:
        return None
    try:
        impl = importlib.import_module("gold.judge")
    except ImportError as exc:
        log(f"score: no judge ({exc}); judged decisions stay pending")
        return None
    return Judge(impl, "gold.judge")


def summary(judge: Judge | None) -> dict[str, Any]:
    return judge.summary() if judge else {"used": False, "name": None, "models": [], "calls": 0, "pending": 0,
                                          "errors": []}


def run_all(calls: list[Callable[[], T]], workers: int = 1) -> list[T]:
    """Run independent judge calls, in parallel threads when workers > 1; results in input order.

    gold/llm.py spreads concurrent calls over both sub-model replicas, and the judge's cache makes the
    result independent of the order the calls finish in.
    """
    if workers <= 1 or len(calls) <= 1:
        return [call() for call in calls]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda call: call(), calls))
