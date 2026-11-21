"""DSPy language models for the pipeline steps: Qwen through the llm-setup gateway, a free OpenRouter model
(backend "openrouter", OPENROUTER_API_KEY), or Claude Code headless.

    lm = make_lm(StepLLM(backend="qwen", model="orch-model"))
    with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
        out = dspy.Predict(MySignature)(...)

Every call is recorded in a JsonlCache (runs/evqa/llm-cache.jsonl by default; rerun = no new call) via
modelcall's RecordedLM. Calls also use the paper writer's three shared process-wide lock files.
Qwen needs LITELLM_MASTER_KEY and runs where the gateway is (on the GPU job: srun --jobid <job> --overlap).
"""
from __future__ import annotations

import json
import os
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
from evqa.llm import MAX_WORKERS
from evqa.paths import REPO
from evqa.slots import model_slot

SLOTS = threading.BoundedSemaphore(MAX_WORKERS)
CACHE_FILE = Path(os.environ.get("EVQA_LM_CACHE", REPO / "runs" / "evqa" / "llm-cache.jsonl"))
_caches: dict[str, JsonlCache] = {}
RETRY_TEMPERATURE = 0.7
_LABEL: ContextVar[str] = ContextVar("evqa_lm_label", default="")
_COUNT_LOCK = threading.Lock()
COUNTS: dict[str, Counter] = {}     # label -> {"requests": n, "cache_hits": n, "calls": n} (calls = real model calls)


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


def _bump(label: str, key: str) -> None:
    if label:
        with _COUNT_LOCK:
            COUNTS.setdefault(label, Counter())[key] += 1


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
        return out


def _cache() -> JsonlCache:
    key = str(CACHE_FILE)
    if key not in _caches:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _caches[key] = JsonlCache(CACHE_FILE)
    return _caches[key]


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
        with SLOTS, model_slot(), urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 - loopback gateway
            return json.loads(r.read())["choices"][0]["message"]["content"] or ""
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
                with SLOTS, model_slot(), urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
                    out = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or wait == waits:
                    raise
                time.sleep(30 * (wait + 1))
        if "choices" not in out:
            raise RuntimeError(f"openrouter error: {out.get('error')!r}")
        return out["choices"][0]["message"]["content"] or ""
    return ask


def claude_ask(model: str, timeout: int = 600):
    def ask(text: str, *, attempt: int = 0, settings: dict | None = None) -> str:
        with SLOTS, model_slot(), tempfile.TemporaryDirectory(prefix="evqa-lm-") as empty:
            done = subprocess.run(["claude", "-p", "--model", model, "--tools", "", "--setting-sources", "",
                                   "--strict-mcp-config", "--no-session-persistence", "--output-format", "json"],
                                  input=text, capture_output=True, text=True, cwd=empty, timeout=timeout)
        out = json.loads(done.stdout)
        if out.get("is_error"):
            raise RuntimeError(f"claude failed: {out.get('result')!r}")
        return out["result"]
    return ask


def make_lm(cfg: StepLLM, ask=None) -> dspy.BaseLM:
    """A recorded DSPy LM for one step's backend. `ask` overrides the raw call (tests pass a fake)."""
    with_call = ask is None   # the built-in asks also get the attempt number (a retry samples); test fakes do not
    if ask is None:
        ask = (qwen_ask(cfg.model, think=cfg.think) if cfg.backend == "qwen" else
               openrouter_ask(cfg.model) if cfg.backend == "openrouter" else claude_ask(cfg.model))
    name = f"{cfg.backend}:{cfg.model}" + ("" if cfg.think else ":nothink")   # the cache key keeps them apart
    return _CountedLM(name, ask, _cache(), label=_LABEL.get(), with_call=with_call)
