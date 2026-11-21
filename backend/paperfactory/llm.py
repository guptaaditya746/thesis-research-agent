"""Model calls: `claude -p` (Claude Code headless) with a JSON schema, cached on disk, cost logged, at most 3 at once.

The model is chosen per role (config.Settings.model). Every call is a fresh call from an empty folder: no tools,
no settings, no MCP, so no repo CLAUDE.md reaches the model. The 3 slots are lock files shared with
PaperOrchestra (its --lock_dir), so the whole run never has more than 3 calls in flight.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

T, R = TypeVar("T"), TypeVar("R")
MAX_SLOTS = 3


class LLMError(RuntimeError):
    pass


@contextmanager
def slot(directory: Path, poll: float = 0.1) -> Iterator[int]:
    directory.mkdir(parents=True, exist_ok=True)
    while True:
        for i in range(MAX_SLOTS):
            with (directory / f"slot-{i}.lock").open("a+") as f:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                try:
                    yield i
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
                return
        time.sleep(poll)


def claude(model: str, system: str, user: str, schema: dict[str, Any], *, slots: Path, timeout: int) -> dict:
    with slot(slots), tempfile.TemporaryDirectory(prefix="paperfactory-") as empty:
        cmd = ["claude", "-p", "--model", model, "--tools", "", "--setting-sources", "", "--strict-mcp-config",
               "--no-session-persistence", "--system-prompt", system, "--output-format", "json",
               "--json-schema", json.dumps(schema)]
        done = subprocess.run(cmd, input=user, capture_output=True, text=True, cwd=empty, timeout=timeout)
    try:
        out = json.loads(done.stdout)
    except json.JSONDecodeError as e:
        raise LLMError(f"claude gave no JSON (exit {done.returncode}): {done.stderr[-500:]}") from e
    if out.get("is_error") or not isinstance(out.get("structured_output"), dict):
        raise LLMError(f"claude failed: {out.get('result')!r}")
    return {"output": out["structured_output"], "cost_usd": out.get("total_cost_usd")}


class Caller:
    """call(role, step, system, user, schema) -> output dict. Cache key = model + prompt + input + schema."""

    def __init__(self, settings, backend: Callable[..., dict] | None = None):
        self.s = settings
        self.cache = settings.out_dir / "cache" / "llm"
        self.log = settings.out_dir / "calls.jsonl"
        self.backend = backend or (lambda m, sy, u, sc: claude(m, sy, u, sc, slots=settings.slots,
                                                                timeout=settings.timeout))

    def __call__(self, role: str, step: str, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        model = self.s.model(role)
        key = hashlib.sha256(json.dumps([model, system, user, schema], sort_keys=True).encode()).hexdigest()
        path = self.cache / f"{key}.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))["output"]
        start = time.time()
        for attempt in range(2):
            try:
                got = self.backend(model, system, user, schema)
                break
            except (LLMError, subprocess.TimeoutExpired):
                if attempt:
                    raise
        rec = {"role": role, "step": step, "model": model, "cost_usd": got.get("cost_usd"),
               "seconds": round(time.time() - start, 1), "output": got["output"]}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        with self.log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({k: v for k, v in rec.items() if k != "output"}) + "\n")
        return got["output"]

    def cost(self, prefix: str = "") -> float:
        if not self.log.is_file():
            return 0.0
        rows = [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()]
        return round(sum(r["cost_usd"] or 0 for r in rows if r["step"].startswith(prefix)), 3)


def pmap(fn: Callable[[T], R], items: Iterable[T]) -> list[R]:
    with ThreadPoolExecutor(MAX_SLOTS) as ex:
        return list(ex.map(fn, items))
