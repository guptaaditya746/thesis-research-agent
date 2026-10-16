"""The LLM judge as scoring uses it: gold/judge.py (package C2), imported lazily and never required.

Its questions (docs/earlier-work.md, "Gold files, answer key, judge, scores"):
- support(fact, quote, *, context=None) -> {label: supports | partial | no, rationale, model, prompt_sha256,
  cached}; support_pair(pair, corpus) asks the same for a line of pairs.jsonl with the context the judge
  was calibrated with (the paper id and the text around the quote, gold.judge.context_for);
- same_fact(run_fact, key_fact, concept) -> {match: bool, ...}, for the soft fact level;
- same_row(run_row, key_row, concept) -> {match: bool, ...}, for soft row matching.
gold.judge caches every decision in $GOLD/judge-cache.jsonl, keyed by its input, model and prompt
hash, so a rescore costs no model calls.

`load()` wraps gold.judge's `default_judge()`, whose methods have async twins (`asupport`, ...). Scoring
awaits those on one event loop in a background thread, at most `workers` at a time: the pydantic-ai
models behind the judge keep one HTTP client each, and a client used from a second event loop fails
("Event loop is closed", "bound to a different event loop"), which the sync API (asyncio.run per
call, from several threads) would do. A judge without async twins (the fakes in tests) is called in
worker threads instead.

`Judge` accepts a pydantic model or a dict as the reply and turns a failed call, a missing verdict or a
malformed one into a pending decision: scoring never stops because the judge is unreachable, it
reports what is pending (the labelling repo's `judge_pending`), and the scores that need the decision
say so. Errors are kept without HTTP bodies and with anything key-like removed: a LiteLLM 401 echoes
part of the key. `fork()` gives each scored run its own counters on the same judge and loop.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import os
import re
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

LABELS = ("supports", "partial", "no")
MAX_ERRORS = 20
WORKERS = 6  # 3 active sequences per sub-model replica (STATE.md, L3)
SECRET = re.compile(r"sk-[\w-]+|key hash \(token\)\s*=?\s*\S*|\bbearer\s+\S+|\b[0-9a-f]{32,}\b", re.I)


def plain(reply: Any) -> Any:
    """A reply as plain JSON data (pydantic models dumped)."""
    if hasattr(reply, "model_dump"):
        return reply.model_dump(mode="json")
    return reply


def describe(method: str, exc: BaseException) -> str:
    """A failed call as score.json records it: the type and HTTP status, never a response body or a key."""
    status = getattr(exc, "status_code", None)
    if status is not None or hasattr(exc, "body"):
        return f"{method}: {type(exc).__name__}" + (f" {status}" if status is not None else "")
    text = str(exc)
    key = os.environ.get("LITELLM_MASTER_KEY")
    if key:
        text = text.replace(key, "[redacted]")
    return f"{method}: {type(exc).__name__}: {SECRET.sub('[redacted]', text)}"[:300]


def problem(method: str, reply: dict[str, Any]) -> str | None:
    """Why a reply is not a usable verdict, or None."""
    if method in ("support", "support_pair") and reply.get("label") not in LABELS:
        return f"label {reply.get('label')!r} is not one of {LABELS}"
    if method in ("same_fact", "same_row") and not isinstance(reply.get("match"), bool):
        return "no boolean 'match' in the reply"
    return None


class Loop:
    """One event loop in a daemon thread, started on first use; every judge coroutine runs on it."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def run(self, coro: Any) -> Any:
        with self._lock:
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
                threading.Thread(target=self._loop.run_forever, name="judge-loop", daemon=True).start()
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()


class Judge:
    """Calls into a judge implementation; counts replies, cache hits, pending decisions and errors.

    `corpus`: makes the object a judge's support_pair expects from a corpus directory (gold.review.Corpus
    for the real judge); None passes the path itself.
    """

    def __init__(self, impl: Any, name: str | None = None, *, workers: int = WORKERS,
                 corpus: Callable[[Path], Any] | None = None, loop: Loop | None = None) -> None:
        self.impl = impl
        self.name = name or getattr(impl, "__name__", type(impl).__name__)
        self.workers = max(1, workers)
        self.corpus_type = corpus
        self.loop = loop or Loop()
        self.calls = 0
        self.cached = 0
        self.pending = 0
        self.errors: list[str] = []
        self.models: set[str] = set()
        self.prompts: set[str] = set()
        self._corpora: dict[str, Any] = {}

    def fork(self) -> Judge:
        """The same judge, loop and corpus cache with counters of its own (one per scored run)."""
        twin = Judge(self.impl, self.name, workers=self.workers, corpus=self.corpus_type, loop=self.loop)
        twin._corpora = self._corpora
        return twin

    # --- what the judge is -------------------------------------------------------------------------------

    def has(self, method: str) -> bool:
        return callable(getattr(self.impl, f"a{method}", None)) or callable(getattr(self.impl, method, None))

    def context_mode(self, corpus: Path | None) -> str:
        """`calibrated`: support_pair with the corpus (the calibration's input); `none`: the quote alone."""
        return "calibrated" if corpus is not None and self.has("support_pair") else "none"

    def identity(self) -> dict[str, Any]:
        """What makes two verdicts comparable: the judge, its model and its prompt hashes (when it says)."""
        hashes = getattr(self.impl, "prompt_hashes", None)
        try:
            prompts = dict(hashes()) if callable(hashes) else None
        except Exception:  # an identity that cannot be read is not the identity of a working judge
            prompts = None
        model = getattr(self.impl, "model_id", None)
        return {"name": self.name, "model": str(model) if model else None, "prompts": prompts}

    # --- calls -------------------------------------------------------------------------------------------

    async def _one(self, method: str, args: tuple[Any, ...], kwargs: dict[str, Any],
                   gate: asyncio.Semaphore) -> dict[str, Any] | None:
        async with gate:
            try:
                twin = getattr(self.impl, f"a{method}", None)
                if twin is not None and inspect.iscoroutinefunction(twin):
                    reply = await twin(*args, **kwargs)
                else:
                    fn = getattr(self.impl, method, None)
                    if fn is None:
                        raise AttributeError(f"{self.name} has no {method}()")
                    reply = await asyncio.to_thread(fn, *args, **kwargs)
                    if inspect.isawaitable(reply):
                        reply = await reply
                reply = plain(reply)
                if isinstance(reply, bool):  # a bare yes/no from same_fact or same_row
                    reply = {"match": reply}
                if reply is None:
                    raise LookupError("no verdict")
                if not isinstance(reply, dict):
                    raise TypeError(f"returned {type(reply).__name__}, not a verdict")
                if why := problem(method, reply):
                    raise ValueError(why)
            except Exception as exc:  # the judge failing must not stop scoring: the decision stays pending
                self.pending += 1
                if len(self.errors) < MAX_ERRORS:
                    self.errors.append(describe(method, exc))
                return None
            self.calls += 1
            self.cached += bool(reply.get("cached"))
            if reply.get("model"):
                self.models.add(str(reply["model"]))
            if reply.get("prompt_sha256"):
                self.prompts.add(str(reply["prompt_sha256"]))
            return reply

    def ask(self, asks: list[tuple[str, tuple[Any, ...], dict[str, Any]]]) -> list[dict[str, Any] | None]:
        """Run (method, args, kwargs) asks concurrently on the judge's loop; replies in order, None = pending."""
        if not asks:
            return []

        async def every() -> list[dict[str, Any] | None]:
            gate = asyncio.Semaphore(self.workers)
            return list(await asyncio.gather(*(self._one(m, a, k, gate) for m, a, k in asks)))

        return self.loop.run(every())

    def supports(self, lines: list[dict[str, Any]], corpus: Path | None = None) -> list[dict[str, Any] | None]:
        """Verdicts for pairs.jsonl lines: with the calibrated context when the judge and corpus allow."""
        if self.context_mode(corpus) == "calibrated":
            where = self._corpus(Path(corpus))  # type: ignore[arg-type]
            return self.ask([("support_pair", (line, where), {}) for line in lines])
        return self.ask([("support", ({k: line[k] for k in ("s", "p", "o")}, line["quote"]), {"context": None})
                         for line in lines])

    def matches(self, method: str, pairs: list[tuple[dict[str, Any], dict[str, Any]]],
                concept: dict[str, Any]) -> list[bool | None]:
        """same_fact or same_row for each (run, key) pair; None = pending."""
        replies = self.ask([(method, (run, key, concept), {}) for run, key in pairs])
        return [None if r is None else r["match"] for r in replies]

    def support(self, fact: dict[str, Any], quote: str, *, context: str | None = None) -> dict[str, Any] | None:
        return self.ask([("support", (fact, quote), {"context": context})])[0]

    def same_fact(self, run_fact: dict[str, Any], key_fact: dict[str, Any], concept: dict[str, Any]) -> bool | None:
        return self.matches("same_fact", [(run_fact, key_fact)], concept)[0]

    def same_row(self, run_row: dict[str, Any], key_row: dict[str, Any], concept: dict[str, Any]) -> bool | None:
        return self.matches("same_row", [(run_row, key_row)], concept)[0]

    def _corpus(self, path: Path) -> Any:
        key = str(path)
        if key not in self._corpora:
            self._corpora[key] = self.corpus_type(path) if self.corpus_type else path
        return self._corpora[key]

    def summary(self) -> dict[str, Any]:
        return {"used": True, "name": self.name, "identity": self.identity(), "models": sorted(self.models),
                "prompt_sha256": sorted(self.prompts), "calls": self.calls, "cached": self.cached,
                "pending": self.pending, "errors": list(self.errors)}


def load(enabled: bool = True, *, workers: int = WORKERS, log: Callable[[str], None] = print) -> Judge | None:
    """gold.judge as a Judge (its default_judge() when it has one); None when disabled or unavailable."""
    if not enabled:
        return None
    try:
        module = importlib.import_module("gold.judge")
        impl = module.default_judge() if callable(getattr(module, "default_judge", None)) else module
    except Exception as exc:  # ImportError, or a judge that cannot start (prompts missing, ...)
        log(f"score: no judge ({describe('load', exc)}); judged decisions stay pending")
        return None
    try:
        corpus = importlib.import_module("gold.review").Corpus
    except (ImportError, AttributeError):
        corpus = None
    return Judge(impl, "gold.judge", workers=workers, corpus=corpus)


def summary(judge: Judge | None) -> dict[str, Any]:
    return judge.summary() if judge else {"used": False, "name": None, "identity": None, "models": [],
                                          "prompt_sha256": [], "calls": 0, "cached": 0, "pending": 0, "errors": []}
