# Added for the thesis vendoring (not upstream). See VENDORED.md, change C1.
"""LLM backend: Claude Code headless (`claude -p`), replacing the Gemini/OpenAI calls.

Every call:
  * runs `claude -p` from an empty temp folder with no tools, no settings, no MCP, no session file
    (not `--bare`: that drops the subscription login);
  * returns one JSON object that matches the given JSON schema (`--json-schema`);
  * is cached on disk by the sha256 of (model, system, user, schema), so a rerun costs nothing;
  * is appended to a JSONL call log (step, cost, seconds, cached or not);
  * holds one of MAX_PARALLEL slot locks while it runs. The slots are `flock`ed files in a shared folder,
    so the cap of 3 holds across threads AND across processes (several papers written at once).

Stdlib only, so the main project's tests can load this file directly.
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
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

MAX_PARALLEL = 3
DEFAULT_MODEL = "claude-haiku-5-5"


class ClaudeCodeError(RuntimeError):
    pass


def call_key(model: str, system: str, user: str, schema: dict[str, Any]) -> str:
    blob = json.dumps([model, system, user, schema], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


class ClaudeCodeLM:
    """One configured backend. Thread-safe; share one instance per process."""

    def __init__(self, model: str = DEFAULT_MODEL, *, cache_dir: str | os.PathLike, lock_dir: str | os.PathLike,
                 log_path: str | os.PathLike | None = None, timeout: int = 900,
                 claude_bin: str | None = None, max_parallel: int = MAX_PARALLEL, poll: float = 0.2):
        self.model = model
        self.cache_dir = Path(cache_dir)
        self.lock_dir = Path(lock_dir)
        self.log_path = Path(log_path) if log_path else None
        self.timeout = timeout
        self.claude_bin = claude_bin or os.environ.get("PO_CLAUDE_BIN", "claude")
        self.max_parallel = min(max_parallel, MAX_PARALLEL)   # never more than 3, whatever the caller asks
        self.poll = poll
        self._log_lock = threading.Lock()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    # -- the parallel cap ---------------------------------------------------------------------------------
    @contextmanager
    def slot(self) -> Iterator[int]:
        """Wait until one of the MAX_PARALLEL slot files can be locked; hold it for the call."""
        while True:
            for i in range(self.max_parallel):
                fh = open(self.lock_dir / f"slot-{i}.lock", "a+")
                try:
                    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    fh.close()
                    continue
                try:
                    yield i
                finally:
                    fcntl.flock(fh, fcntl.LOCK_UN)
                    fh.close()
                return
            time.sleep(self.poll)

    # -- one call ---------------------------------------------------------------------------------------------
    def _run_qwen(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """model "qwen:<alias>": the llm-setup LiteLLM gateway (LITELLM_BASE_URL, LITELLM_MASTER_KEY), thinking off,
        output held to the JSON schema by the server (vLLM structured output). Added 21 Nov 2026 (thesis C2)."""
        import urllib.request
        url = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1").rstrip("/") + "/chat/completions"
        body = {"model": self.model.split(":", 1)[1], "temperature": 0.0, "max_tokens": 12000,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_schema", "json_schema": {"name": "out", "schema": schema}},
                "chat_template_kwargs": {"enable_thinking": False}}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {os.environ.get('LITELLM_MASTER_KEY', '')}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:   # noqa: S310 - loopback gateway
                out = json.loads(r.read())
            parsed = json.loads(out["choices"][0]["message"]["content"] or "")
        except Exception as e:  # noqa: BLE001 - reported as a transport failure (one retry)
            raise ClaudeCodeError(f"qwen failed: {type(e).__name__}: {str(e)[:300]}") from e
        if not isinstance(parsed, dict):
            raise ClaudeCodeError("qwen gave no JSON object")
        usage = out.get("usage") or {}
        return {"output": parsed, "cost_usd": 0.0, "served_model": out.get("model", self.model),
                "input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens")}

    def _run_claude(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        if self.model.startswith("qwen:"):
            return self._run_qwen(system, user, schema)
        with tempfile.TemporaryDirectory(prefix="po-llm-") as empty:
            cmd = [self.claude_bin, "-p", "--model", self.model, "--tools", "", "--setting-sources", "",
                   "--strict-mcp-config", "--no-session-persistence", "--system-prompt", system,
                   "--output-format", "json", "--json-schema", json.dumps(schema)]
            done = subprocess.run(cmd, input=user, capture_output=True, text=True, cwd=empty, timeout=self.timeout)
        try:
            out = json.loads(done.stdout)
        except json.JSONDecodeError as e:
            raise ClaudeCodeError(f"claude gave no JSON (exit {done.returncode}): {done.stderr[-500:]}") from e
        if out.get("is_error") or not isinstance(out.get("structured_output"), dict):
            raise ClaudeCodeError(f"claude failed: {str(out.get('result'))[:500]!r}")
        usage = out.get("usage") or {}
        return {"output": out["structured_output"], "cost_usd": out.get("total_cost_usd"),
                "served_model": next(iter(out.get("modelUsage") or {}), self.model),
                "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")}

    def log(self, record: dict[str, Any]) -> None:
        if self.log_path is None:
            return
        with self._log_lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def __call__(self, system: str, user: str, schema: dict[str, Any], *, step: str) -> dict[str, Any]:
        """Return the JSON object the model gave. Cached calls cost nothing and are logged with cached=true."""
        key = call_key(self.model, system, user, schema)
        path = self.cache_dir / f"{key}.json"
        if path.is_file():
            rec = json.loads(path.read_text(encoding="utf-8"))
            self.log({"event": "call", "step": step, "key": key, "cached": True, "model": self.model,
                      "served_model": rec.get("served_model"), "cost_usd": 0.0,
                      "original_cost_usd": rec.get("cost_usd"), "seconds": 0.0})
            return rec["output"]
        last: Exception | None = None
        for attempt in (1, 2):       # one retry for a transport failure (no JSON / timeout), never for content
            start = time.time()
            try:
                with self.slot() as slot:
                    got = self._run_claude(system, user, schema)
                break
            except (ClaudeCodeError, subprocess.TimeoutExpired) as e:
                last = e
                self.log({"event": "call_error", "step": step, "key": key, "attempt": attempt,
                          "error": str(e)[:500], "seconds": round(time.time() - start, 2)})
        else:
            raise ClaudeCodeError(f"{step}: claude failed twice: {last}")
        seconds = round(time.time() - start, 2)
        rec = {"key": key, "step": step, "model": self.model, "served_model": got["served_model"],
               "cost_usd": got["cost_usd"], "seconds": seconds, "input_tokens": got["input_tokens"],
               "output_tokens": got["output_tokens"], "system": system, "user": user, "schema": schema,
               "output": got["output"]}
        tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        self.log({"event": "call", "step": step, "key": key, "cached": False, "model": self.model,
                  "served_model": got["served_model"], "cost_usd": got["cost_usd"], "seconds": seconds,
                  "slot": slot, "input_tokens": got["input_tokens"], "output_tokens": got["output_tokens"]})
        return got["output"]


def markdown_schema(field: str = "markdown", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Schema for a call that returns one Markdown text (plus optional extra fields)."""
    props: dict[str, Any] = {field: {"type": "string"}}
    props.update(extra or {})
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}
