"""Model calls for every job, one layer for every backend (also used by PaperOrchestra, see write.py).

call(role, step, system, user, out, check=None) -> the checked output dict, or None (parse_error).
  * The model per role comes from the settings (config.RoleModel): backend "claude_cli" (`claude -p` from an
    empty folder: no tools, no settings, no MCP) or "openai" (an OpenAI-compatible server through modelcall:
    the LiteLLM gateway, vLLM, Ollama). Both get the output's JSON schema (structured output).
  * `out` is a pydantic model (parsed and validated here) or a plain JSON schema (checked with jsonschema).
    `check(output) -> error or None` adds the caller's own rules. A rejected answer is asked again, at most twice,
    with the error added to the prompt; then the call returns None and calls.jsonl records a parse_error.
    Nothing is ever filled in with a default.
  * A transport failure (no answer, timeout) is retried once, then raises LLMError.
  * Cost: what the backend reports, else tokens x the role's price, else 0 for local models, else None
    ("unknown"); never 0 for unknown.
  * At most `max_parallel` calls per endpoint at once, across threads and processes (flock'ed slot files; the
    claude_cli slots are shared with PaperOrchestra's --lock_dir).
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
import threading
import time
import warnings
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

import jsonschema
from pydantic import BaseModel, ValidationError

from paperfactory import files
from paperfactory.config import RoleModel

T, R = TypeVar("T"), TypeVar("R")
MAX_SLOTS = 3          # default parallel calls (pmap threads); per endpoint the role's max_parallel applies
RETRIES_ON_REJECT = 2
CHARS_PER_TOKEN = 3.0  # preflight estimate (D3); low on purpose, so long prompts are caught early
CACHE_VERSION = 2
IO_LOG_ROLES = ("judge",)      # raise when the call protocol changes (retry prompt, parsing); part of the cache key


class LLMError(RuntimeError):
    """The backend gave no answer (twice)."""


class Rejected(Exception):
    """The backend answered, but not in the required form."""


# ------------------------------------------------------------------ slots
@contextmanager
def slot(directory: Path, n: int = MAX_SLOTS, poll: float = 0.1) -> Iterator[int]:
    directory.mkdir(parents=True, exist_ok=True)
    while True:
        for i in range(n):
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


def slot_dir(base: Path, rm: RoleModel) -> Path:
    """claude_cli: the shared folder itself (same files as PaperOrchestra). openai: one subfolder per server."""
    if rm.backend == "claude_cli":
        return base
    return base / ("openai-" + hashlib.sha256(str(rm.url).encode()).hexdigest()[:12])


# ------------------------------------------------------------------ schemas
def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """The schema with every local $ref replaced by its definition (pydantic writes $defs; some structured-output
    backends do not follow references)."""
    defs = schema.get("$defs", {})

    def walk(x: Any) -> Any:
        if isinstance(x, dict):
            if "$ref" in x:
                return walk(defs[x["$ref"].rsplit("/", 1)[1]])
            return {k: walk(v) for k, v in x.items() if k != "$defs"}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x
    return walk(schema)


def json_schema(out: type[BaseModel] | dict[str, Any]) -> dict[str, Any]:
    return inline_refs(out.model_json_schema()) if isinstance(out, type) else out


def parse(out: type[BaseModel] | dict[str, Any], raw: Any) -> dict[str, Any]:
    """raw -> output dict, or Rejected with a short reason."""
    if not isinstance(raw, dict):
        raise Rejected(f"the answer must be one JSON object, got {type(raw).__name__}")
    try:
        if isinstance(out, type):
            return out.model_validate(raw).model_dump(mode="json")
        jsonschema.validate(raw, out)
        return raw
    except ValidationError as e:
        raise Rejected("; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()[:5])) from None
    except jsonschema.ValidationError as e:
        raise Rejected(f"{'.'.join(map(str, e.absolute_path))}: {e.message}"[:300]) from None


# ------------------------------------------------------------------ backends
def run_claude(rm: RoleModel, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="paperfactory-") as empty:
        cmd = ["claude", "-p", "--model", rm.model, "--tools", "", "--setting-sources", "", "--strict-mcp-config",
               "--no-session-persistence", "--system-prompt", system, "--output-format", "json",
               "--json-schema", json.dumps(schema)]
        try:
            done = subprocess.run(cmd, input=user, capture_output=True, text=True, cwd=empty, timeout=rm.timeout)
        except subprocess.TimeoutExpired as e:
            raise LLMError(f"claude timed out after {rm.timeout}s") from e
    try:
        out = json.loads(done.stdout)
    except json.JSONDecodeError as e:
        raise LLMError(f"claude gave no JSON (exit {done.returncode}): {done.stderr[-500:]}") from e
    if out.get("is_error"):
        raise LLMError(f"claude failed: {str(out.get('result'))[:500]!r}")
    usage = out.get("usage") or {}
    return {"raw": out.get("structured_output"), "cost_usd": out.get("total_cost_usd"),
            "served_model": next(iter(out.get("modelUsage") or {}), rm.model),
            "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")}


def openai_model(rm: RoleModel) -> Any:
    """The pydantic-ai model of an openai-backend role (tests replace this with a fake)."""
    from modelcall import openai_model as gateway_model
    return gateway_model(rm.model, url=rm.url)


def run_openai(rm: RoleModel, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Through modelcall (pydantic-ai, structured output, redacted errors), without its cache: the run's own cache
    is in Caller. A reply that is not valid JSON for the schema comes back as raw=None (asked again)."""
    os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
    from pydantic_ai import StructuredDict
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    from modelcall import CallSettings, ModelCallError, Prompt, ask_sync
    out_type = StructuredDict(schema, name="answer")
    try:
        a = ask_sync(Prompt.inline(system, out_type), user, model=openai_model(rm),
                     settings=CallSettings(max_tokens=rm.max_tokens), timeout_s=rm.timeout)
    except ModelCallError as e:
        if isinstance(e.cause, (UnexpectedModelBehavior, ValidationError)):
            return {"raw": None, "reject_reason": e.reason, "cost_usd": None, "served_model": rm.model,
                    "input_tokens": None, "output_tokens": None}
        raise LLMError(e.reason) from None
    return {"raw": a.output, "cost_usd": None, "served_model": a.served_model or rm.model,
            "input_tokens": a.input_tokens, "output_tokens": a.output_tokens}


BACKENDS: dict[str, Callable[[RoleModel, str, str, dict[str, Any]], dict[str, Any]]] = {
    "claude_cli": run_claude, "openai": run_openai}


def price(rm: RoleModel, got: dict[str, Any]) -> tuple[float | None, str]:
    """(cost in USD or None, where it came from: reported | price | local | unknown)."""
    if got.get("cost_usd") is not None:
        return float(got["cost_usd"]), "reported"
    if rm.local:
        return 0.0, "local"
    ti, to = got.get("input_tokens"), got.get("output_tokens")
    if rm.price_in_per_mtok is not None and rm.price_out_per_mtok is not None and ti is not None and to is not None:
        return (ti * rm.price_in_per_mtok + to * rm.price_out_per_mtok) / 1e6, "price"
    return None, "unknown"


def preflight(rm: RoleModel, system: str, user: str, schema: dict[str, Any]) -> str | None:
    """None, or why the request would not fit the role's context_window (estimated tokens in + max_tokens out)."""
    if not rm.context_window:
        return None
    est = int((len(system) + len(user) + len(json.dumps(schema))) / CHARS_PER_TOKEN)
    if est + rm.max_tokens > rm.context_window:
        return (f"about {est} input tokens + {rm.max_tokens} output tokens > context_window {rm.context_window} of "
                f"{rm.model}: skipped (shorten the input or use a model with a larger window)")
    return None


def run_backend(rm: RoleModel, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
    """One raw call, retried once on a transport failure. Also PaperOrchestra's backend (write.py), which holds
    its own slot while calling."""
    for attempt in range(2):
        try:
            got = BACKENDS[rm.backend](rm, system, user, schema)
            break
        except LLMError:
            if attempt:
                raise
    cost, source = price(rm, got)
    return got | {"cost_usd": cost, "cost_source": source}


# ------------------------------------------------------------------ the caller
class Caller:
    """call(role, step, system, user, out, check=None) -> output dict or None.

    Cache (#7): key = CACHE_VERSION, backend, model, server, output params (max_tokens), prompt, input and schema.
    Only checked outputs are cached, and a cached output is checked again on reading (the caller's rules may have
    changed). Writes are atomic; a broken cache file gives a warning and the call is made again.
    use_cache=False: never read the cache (the new answers still replace the old ones)."""

    def __init__(self, settings, backend: Callable[..., dict[str, Any]] | None = None, use_cache: bool = True):
        self.s = settings
        self.cache = settings.out_dir / "cache" / "llm"
        self.log = settings.out_dir / "calls.jsonl"
        self.backend = backend or run_backend
        self.use_cache = use_cache
        self._log_lock = threading.Lock()

    def key(self, rm: RoleModel, system: str, user: str, schema: dict[str, Any]) -> str:
        # the configured base_url, not rm.url: $LITELLM_BASE_URL differs between shells (review finding 8); claude_cli
        # ignores max_tokens
        mt = rm.max_tokens if rm.backend != "claude_cli" else None
        return hashlib.sha256(json.dumps([CACHE_VERSION, rm.backend, rm.model, rm.base_url, mt, system, user,
                                          schema], sort_keys=True).encode()).hexdigest()

    def cached(self, path: Path, out: type[BaseModel] | dict[str, Any],
               check: Callable[[dict[str, Any]], str | None] | None) -> dict[str, Any] | None:
        """The cached output, or None (no file, broken file, or the output fails today's checks)."""
        if not self.use_cache or not path.is_file():
            return None
        try:
            output = parse(out, json.loads(path.read_text(encoding="utf-8"))["output"])
            if check and (msg := check(output)):
                raise Rejected(msg)
            return output
        except (json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError, Rejected) as e:
            warnings.warn(f"cache file {path.name} unusable ({type(e).__name__}: {str(e)[:120]}); calling again",
                          stacklevel=3)
            return None

    def _write_log(self, rec: dict[str, Any]) -> None:
        with self._log_lock, self.log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def __call__(self, role: str, step: str, system: str, user: str, out: type[BaseModel] | dict[str, Any],
                 check: Callable[[dict[str, Any]], str | None] | None = None) -> dict[str, Any] | None:
        rm = self.s.role(role)
        schema = json_schema(out)
        path = self.cache / f"{self.key(rm, system, user, schema)}.json"
        if (hit := self.cached(path, out, check)) is not None:
            self._io(role, step, user, hit, cached=True)
            return hit
        self.log.parent.mkdir(parents=True, exist_ok=True)
        if too_long := preflight(rm, system, user, schema):
            warnings.warn(f"{step}: {too_long}", stacklevel=2)
            self._write_log({"role": role, "step": step, "backend": rm.backend, "model": rm.model, "cost_usd": 0.0,
                             "cost_source": "skipped", "attempts": 0, "rejections": [too_long],
                             "parse_error": True, "skipped": "context_window", "seconds": 0.0})
            return None
        start, prompt, errors, costs = time.time(), user, [], []
        output: dict[str, Any] | None = None
        got: dict[str, Any] = {}
        for _ in range(1 + RETRIES_ON_REJECT):
            with slot(slot_dir(self.s.slots, rm), rm.max_parallel):
                got = self.backend(rm, system, prompt, schema)
            costs.append(got.get("cost_usd"))
            try:
                if got.get("raw") is None:
                    raise Rejected(got.get("reject_reason") or "no JSON object in the answer")
                output = parse(out, got["raw"])
                if check and (msg := check(output)):
                    raise Rejected(msg)
                break
            except Rejected as e:
                errors.append(str(e))
                output = None
                prompt = (user + "\n\nYOUR LAST ANSWER WAS REJECTED: " + str(e)
                          + "\nAnswer again, in the required form.")
        cost = None if any(c is None for c in costs) else round(sum(costs), 6)
        rec = {"role": role, "step": step, "key": path.stem, "backend": rm.backend, "model": rm.model,
               "served_model": got.get("served_model"), "cost_usd": cost,
               "cost_source": got.get("cost_source") if cost is not None else "unknown",
               "input_tokens": got.get("input_tokens"), "output_tokens": got.get("output_tokens"),
               "attempts": len(costs), "rejections": errors, "parse_error": output is None,
               "seconds": round(time.time() - start, 1)}
        if output is not None:
            files.write_json(path, rec | {"output": output})
        self._write_log(rec)
        self._io(role, step, user, output, cached=False)
        return output

    def _io(self, role: str, step: str, user: str, output: dict[str, Any] | None, cached: bool) -> None:
        """Inputs and outputs of the roles in IO_LOG_ROLES (D2: the judge) -> <role>.jsonl in the run folder."""
        if role in IO_LOG_ROLES:
            with self._log_lock, (self.s.out_dir / f"{role}.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({"step": step, "input": user, "output": output, "cached": cached},
                                   ensure_ascii=False) + "\n")

    def clear(self, step_prefix: str) -> int:
        """Delete the cached answers of every step starting with step_prefix; returns how many."""
        n = 0
        for p in self.cache.glob("*.json") if self.cache.is_dir() else []:
            try:
                step = json.loads(p.read_text(encoding="utf-8")).get("step", "")
            except (json.JSONDecodeError, UnicodeDecodeError):
                step = step_prefix                    # a broken file goes too
            if step.startswith(step_prefix):
                p.unlink()
                n += 1
        return n

    def cost(self, prefix: str = "") -> dict[str, Any]:
        """{"usd": total, or "unknown" if any call's cost is unknown; "usd_known"; "calls"; "calls_unknown_cost"}."""
        rows = [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()] \
            if self.log.is_file() else []
        rows = [r for r in rows if r["step"].startswith(prefix)]
        known = round(sum(r["cost_usd"] for r in rows if r.get("cost_usd") is not None), 3)
        unknown = sum(r.get("cost_usd") is None for r in rows)
        return {"usd": known if not unknown else "unknown", "usd_known": known, "calls": len(rows),
                "calls_unknown_cost": unknown}


def pmap(fn: Callable[[T], R], items: Iterable[T], workers: int = MAX_SLOTS) -> list[R]:
    with ThreadPoolExecutor(max(1, workers)) as ex:
        return list(ex.map(fn, items))


def po_runner(fields: dict[str, Any]) -> tuple[Callable[[str, str, dict[str, Any]], dict[str, Any]], str]:
    """PaperOrchestra's backend (its --backend_json): (runner, label for its cache key and log). PaperOrchestra holds
    its own slot (its --lock_dir is slot_dir(...) of this role) and keeps its own cache and call log."""
    rm = RoleModel(**fields)

    def runner(system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        if too_long := preflight(rm, system, user, schema):
            raise LLMError(too_long)
        got = run_backend(rm, system, user, schema)
        return {"output": got.get("raw"), "reject_reason": got.get("reject_reason"), "cost_usd": got["cost_usd"],
                "cost_source": got["cost_source"], "served_model": got.get("served_model"),
                "input_tokens": got.get("input_tokens"), "output_tokens": got.get("output_tokens")}
    # the label is PaperOrchestra's cache key: it must change whenever the answers can (review finding 3); claude_cli
    # gets no max_tokens (run_claude does not pass it), the openai backend does
    label = rm.model if rm.backend == "claude_cli" else \
        f"{rm.backend}:{rm.model}@{rm.base_url or 'gateway'}#max_tokens={rm.max_tokens}"
    return runner, label
