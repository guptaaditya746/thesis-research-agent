"""DSPy language models for the pipeline steps: Qwen through the llm-setup gateway, a free OpenRouter model
(backend "openrouter", OPENROUTER_API_KEY), or Claude Code headless.

    lm = make_lm(StepLLM(backend="qwen", model="orch-model"))
    with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
        out = dspy.Predict(MySignature)(...)

Every call is recorded in a JsonlCache (runs/evqa/llm-cache.jsonl by default; rerun = no new call) via
modelcall's RecordedLM. Calls also use the paper writer's three shared process-wide lock files.
Qwen needs LITELLM_MASTER_KEY and runs where the gateway is (on the GPU job: srun --jobid <job> --overlap).
A connection error, timeout, HTTP 429/5xx (claude: a timeout or no JSON) is retried up to RETRIES times with growing
waits; the call slot is let go while waiting. Token usage of real calls is counted (COUNTS "prompt_tokens",
"completion_tokens") and stored in the cache record. EVQA_MODEL_REVISION (optional, e.g. the weights' hash or date)
goes into the cache key, so answers cached from other weights behind the same alias are not reused; unset = old keys.
"""
from __future__ import annotations

import http.client
import json
import os
import random
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

import dspy
from modelcall.cache import JsonlCache
from modelcall.dspy_lm import RecordedLM

from evqa.contracts import StepLLM
from evqa.llm import ServiceError
from evqa.paths import REPO
from evqa.slots import MAX_SLOTS, MAX_SLOTS_QWEN, model_slot

# in-process caps, the same as the cross-process slot caps (slots.py): Qwen may have its own (EVQA_MAX_CALLS_QWEN)
SLOTS = threading.BoundedSemaphore(MAX_SLOTS)
QWEN_SLOTS = threading.BoundedSemaphore(MAX_SLOTS_QWEN)
RETRIES = 4          # extra tries after a transient service failure
BACKOFF = 5.0        # seconds before the first retry; doubled each time, plus up to 50% jitter
SLEEP = time.sleep   # tests replace it
CACHE_FILE = Path(os.environ.get("EVQA_LM_CACHE", REPO / "runs" / "evqa" / "llm-cache.jsonl"))
_caches: dict[str, JsonlCache] = {}
RETRY_TEMPERATURE = 0.7
_LABEL: ContextVar[str] = ContextVar("evqa_lm_label", default="")
_COUNT_LOCK = threading.Lock()
COUNTS: dict[str, Counter] = {}     # label -> {"requests", "cache_hits", "calls" (real model calls), "prompt_tokens",
                                    # "completion_tokens" (of real calls that reported usage)}


@contextmanager
def counting(label: str) -> Iterator[Counter]:
    """Count the LM requests of every LM made (make_lm) inside this block under `label`, also when the LM is later
    used from worker threads. The runner wraps each step in it (label "<qid>/<step>") and logs the counts."""
    token = _LABEL.set(label)
    with _COUNT_LOCK:
        counts = COUNTS.setdefault(label, Counter())
    try:
        yield counts
    finally:
        _LABEL.reset(token)


def _bump(label: str, key: str, n: int = 1) -> None:
    if label:
        with _COUNT_LOCK:
            COUNTS.setdefault(label, Counter())[key] += n


class _CountedLM(RecordedLM):
    def __init__(self, *args, label: str = "", **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.label = label

    def forward(self, *args, **kwargs):
        out = super().forward(*args, **kwargs)
        _bump(self.label, "requests")
        if out.cache_hit:
            _bump(self.label, "cache_hits")
        else:
            _bump(self.label, "calls")
            for k in ("prompt_tokens", "completion_tokens"):
                if isinstance((out.usage or {}).get(k), int):
                    _bump(self.label, k, out.usage[k])
        return out


def _cache() -> JsonlCache:
    key = str(CACHE_FILE)
    if key not in _caches:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _caches[key] = JsonlCache(CACHE_FILE)
    return _caches[key]


class Reply(str):
    """A reply text that also carries the call's token usage (RecordedLM stores it next to the text)."""
    usage: dict


def _reply(text: str, usage: dict | None) -> str:
    out = Reply(text)
    out.usage = {k: usage[k] for k in ("prompt_tokens", "completion_tokens") if isinstance((usage or {}).get(k), int)}
    return out


def transient(exc: BaseException) -> bool:
    """A failure worth another try: no connection, a timeout, HTTP 429 or 5xx, a reply that is not the service's
    JSON. Other HTTP 4xx are not retried (the request itself is wrong)."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or exc.code >= 500
    return isinstance(exc, (urllib.error.URLError, ConnectionError, TimeoutError, http.client.HTTPException,
                            subprocess.TimeoutExpired, ServiceError))


def with_retries(call, *, retries: int | None = None, backoff: float | None = None, sleep=None):
    """`call()`, tried again up to `retries` times after a transient failure, waiting backoff * 2^n (+ jitter)
    between tries. `call` takes its slot itself, so no slot is held while waiting."""
    retries = RETRIES if retries is None else retries
    backoff = BACKOFF if backoff is None else backoff
    for n in range(retries + 1):
        try:
            return call()
        except Exception as e:
            if n == retries or not transient(e):
                raise
            (sleep or SLEEP)(backoff * 2 ** n * (1 + random.random() / 2))   # noqa: S311 - jitter, not crypto
    raise AssertionError("unreachable")


def _post_json(req: urllib.request.Request, timeout: int, slots: threading.BoundedSemaphore, limit: int) -> dict:
    """One POST under a slot; a reply that is not JSON is a service failure."""
    with slots, model_slot(limit=limit), urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
        raw = r.read()
    try:
        return json.loads(raw)
    except ValueError as e:
        raise ServiceError(f"no JSON from {req.full_url}: {raw[:300]!r}") from e


def qwen_ask(model: str, max_tokens: int = 4096, timeout: int = 600, think: bool = True):
    url = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1").rstrip("/") + "/chat/completions"

    def ask(text: str, *, attempt: int = 0, settings: dict | None = None) -> str:
        # attempt 0: greedy. A retry (attempt >= 1, after an empty or unparseable reply, e.g. a reasoning loop that
        # used up max_tokens) samples instead, with the attempt as seed: greedy would repeat the same reply.
        body = {"model": model, "messages": [{"role": "user", "content": text}],
                "temperature": 0.0 if attempt == 0 else RETRY_TEMPERATURE, "seed": attempt, "max_tokens": max_tokens}
        if not think:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {os.environ.get('LITELLM_MASTER_KEY', '')}"})
        out = with_retries(lambda: _post_json(req, timeout, QWEN_SLOTS, MAX_SLOTS_QWEN))
        if "choices" not in out:
            raise ServiceError(f"qwen gateway error: {out.get('error')!r}")
        return _reply(out["choices"][0]["message"]["content"] or "", out.get("usage"))
    return ask


def openrouter_ask(model: str, max_tokens: int = 4096, timeout: int = 600, waits: int = 6):
    """OpenRouter chat call (OPENROUTER_API_KEY from the environment). Only ":free" models: no step may cost money
    (codex-instructions STOP rule). A 429 (rate limit) waits and retries up to `waits` times, 30 s more each time."""
    if not model.endswith(":free"):
        raise ValueError(f"openrouter model {model!r} is not a :free model; paid models need Aditya's OK")
    url = "https://openrouter.ai/api/v1/chat/completions"

    def ask(text: str, *, attempt: int = 0, settings: dict | None = None) -> str:
        body = {"model": model, "messages": [{"role": "user", "content": text}],
                "temperature": 0.0 if attempt == 0 else RETRY_TEMPERATURE, "seed": attempt, "max_tokens": max_tokens}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}"})
        for wait in range(waits + 1):
            try:
                out = _post_json(req, timeout, SLOTS, MAX_SLOTS)
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or wait == waits:
                    raise
                SLEEP(30 * (wait + 1))
        if "choices" not in out:
            raise ServiceError(f"openrouter error: {out.get('error')!r}")
        return _reply(out["choices"][0]["message"]["content"] or "", out.get("usage"))
    return ask


def claude_ask(model: str, timeout: int = 600):
    def once(text: str) -> dict:
        with SLOTS, model_slot(), tempfile.TemporaryDirectory(prefix="evqa-lm-") as empty:
            done = subprocess.run(["claude", "-p", "--model", model, "--tools", "", "--setting-sources", "",
                                   "--strict-mcp-config", "--no-session-persistence", "--output-format", "json"],
                                  input=text, capture_output=True, text=True, cwd=empty, timeout=timeout)
        try:
            return json.loads(done.stdout)
        except ValueError as e:
            raise ServiceError(f"claude gave no JSON (exit {getattr(done, 'returncode', '?')}): "
                               f"{(getattr(done, 'stderr', '') or '')[-500:]}") from e

    def ask(text: str, *, attempt: int = 0, settings: dict | None = None) -> str:
        out = with_retries(lambda: once(text))
        if out.get("is_error"):
            raise ServiceError(f"claude failed: {out.get('result')!r}")
        usage = out.get("usage") or {}   # claude: input tokens split into new, cache-written and cache-read ones
        prompt = [usage.get(k) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")]
        return _reply(out["result"], {"prompt_tokens": sum(n for n in prompt if isinstance(n, int)) if "input_tokens"
                                      in usage else None, "completion_tokens": usage.get("output_tokens")})
    return ask


def make_lm(cfg: StepLLM, ask=None) -> dspy.BaseLM:
    """A recorded DSPy LM for one step's backend. `ask` overrides the raw call (tests pass a fake)."""
    with_call = ask is None   # the built-in asks also get the attempt number (a retry samples); test fakes do not
    if ask is None:
        ask = (qwen_ask(cfg.model, think=cfg.think) if cfg.backend == "qwen" else
               openrouter_ask(cfg.model) if cfg.backend == "openrouter" else claude_ask(cfg.model))
    name = f"{cfg.backend}:{cfg.model}" + ("" if cfg.think else ":nothink")   # the cache key keeps them apart
    return _CountedLM(name, ask, _cache(), label=_LABEL.get(), with_call=with_call,
                      model_revision=os.environ.get("EVQA_MODEL_REVISION") or None)
