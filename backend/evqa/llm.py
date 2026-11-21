"""LLM backends of evqa. Every call takes (system, user, JSON schema) and returns one JSON object.

Backends: Claude Code headless (`claude_code`, cheapest model by default) and, from S4, Qwen via llm-setup
(`modelcall`). Every call is cached on disk by its hash and appended to the call log, so a rerun costs nothing and
every output can be traced. At most `MAX_WORKERS` calls run at once (Aditya, 20 Nov: pool of 3).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol, TypeVar

from evqa.paths import CACHE, LLM_LOG
from evqa.slots import MAX_SLOTS, model_slot

MAX_WORKERS = MAX_SLOTS              # 3 unless EVQA_MAX_CALLS is set (slots.py)
CHEAPEST_CLAUDE = "claude-haiku-5-5"
T = TypeVar("T")
R = TypeVar("R")


class LLMError(RuntimeError):
    pass


class JsonLM(Protocol):
    model: str

    def __call__(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]: ...


def call_key(model: str, system: str, user: str, schema: dict[str, Any]) -> str:
    blob = json.dumps([model, system, user, schema], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


class ClaudeCode:
    """`claude -p` from an empty folder: no tools, no settings, no MCP, so no repo CLAUDE.md reaches the model.
    (`--bare` would be cleaner but skips the login, so it cannot be used with a subscription login.)"""

    def __init__(self, model: str = CHEAPEST_CLAUDE, timeout: int = 300):
        self.model, self.timeout = model, timeout

    def __call__(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        with model_slot(), tempfile.TemporaryDirectory(prefix="evqa-llm-") as empty:
            cmd = ["claude", "-p", "--model", self.model, "--tools", "", "--setting-sources", "",
                   "--strict-mcp-config", "--no-session-persistence", "--system-prompt", system,
                   "--output-format", "json", "--json-schema", json.dumps(schema)]
            done = subprocess.run(cmd, input=user, capture_output=True, text=True, cwd=empty, timeout=self.timeout)
        try:
            out = json.loads(done.stdout)
        except json.JSONDecodeError as e:
            raise LLMError(f"claude gave no JSON (exit {done.returncode}): {done.stderr[-500:]}") from e
        if out.get("is_error") or not isinstance(out.get("structured_output"), dict):
            raise LLMError(f"claude failed: {out.get('result')!r}")
        return {"output": out["structured_output"], "cost_usd": out.get("total_cost_usd"),
                "served_model": next(iter(out.get("modelUsage") or {}), self.model)}


def call(lm: Any, system: str, user: str, schema: dict[str, Any], *, step: str) -> dict[str, Any]:
    """One recorded, cached call. Returns the JSON output object."""
    key = call_key(lm.model, system, user, schema)
    path = CACHE / "llm" / f"{key}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))["output"]
    start = time.time()
    got = lm(system, user, schema)
    record = {"key": key, "step": step, "model": lm.model, "served_model": got.get("served_model"),
              "cost_usd": got.get("cost_usd"), "seconds": round(time.time() - start, 2),
              "system": system, "user": user, "schema": schema, "output": got["output"]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    LLM_LOG.parent.mkdir(parents=True, exist_ok=True)
    with LLM_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({k: v for k, v in record.items() if k not in ("system", "user", "schema")},
                           ensure_ascii=False) + "\n")
    return got["output"]


def pmap(fn: Callable[[T], R], items: Iterable[T], workers: int = MAX_WORKERS) -> list[R]:
    """`fn` over `items`, at most `workers` (capped at 3) at once, results in input order."""
    with ThreadPoolExecutor(max_workers=min(workers, MAX_WORKERS)) as pool:
        return list(pool.map(fn, items))
