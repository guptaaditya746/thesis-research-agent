"""A local OpenAI-compatible gateway in front of the Claude CLI (`claude -p`), for runs without the GPU stack
(24 Nov 2026: gammaweb08 stuck, no free Ampere GPU). The scorer (thesis-scorer) and the baselines (thesis-baselines,
through LiteLLM) speak the OpenAI chat API to LITELLM_BASE_URL; pointed here, they answer with Claude.

    uv run python -m evqa.claude_gateway --port 4199 [--parallel 16]
    LITELLM_BASE_URL=http://127.0.0.1:4199/v1 evqa eval <run> --text --text-model claude:claude-haiku-5-5 ...

POST /v1/chat/completions takes {model, messages, tools?, tool_choice?, stream?}; the model must be a Claude model
("claude-haiku-5-5"): a Qwen alias such as "orch-model" is refused, so no record says Qwen when Claude answered.
The system messages become the CLI's system prompt; the other messages are written out as one transcript. Tools have
no native form in `claude -p --tools ""`, so they are described in the system prompt and the model replies with one
JSON object {"tool_calls": [{"name", "arguments"}]} or {"content": "..."}; an unreadable reply is asked once more,
then returned as plain content. temperature, seed and max_tokens are not passed on (the CLI has no such flags).
No request or reply text is logged; one line per call (model, ms, ok) goes to stderr. Bound to 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

TIMEOUT = 900
TOOL_PROTOCOL = """You can call tools. The tools, as JSON function definitions:
{tools}

Reply with exactly one JSON object and nothing else:
- to call tools: {{"tool_calls": [{{"name": "<tool name>", "arguments": {{...}}}}]}}
- {answer_rule}
Arguments follow the tool's parameter schema. Results of earlier calls appear in the transcript as [tool result]."""


def _text(content: Any) -> str:
    """OpenAI message content (a string or a list of parts) as text."""
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content or ""


def prompt_parts(body: dict[str, Any]) -> tuple[str, str]:
    """(system prompt, transcript) of one chat request."""
    system = [_text(m.get("content")) for m in body["messages"] if m.get("role") in ("system", "developer")]
    turns = []
    for m in body["messages"]:
        role = m.get("role")
        if role in ("system", "developer"):
            continue
        if role == "tool":
            turns.append(f"[tool result: {m.get('name') or m.get('tool_call_id', '')}]\n{_text(m.get('content'))}")
        elif role == "assistant" and m.get("tool_calls"):
            calls = [{"name": c["function"]["name"], "arguments": c["function"].get("arguments")}
                     for c in m["tool_calls"]]
            turns.append(f"[assistant]\n{json.dumps({'tool_calls': calls}, ensure_ascii=False)}")
        else:
            turns.append(f"[{role}]\n{_text(m.get('content'))}")
    tools = [] if body.get("tool_choice") == "none" else body.get("tools") or []
    if tools:
        # "auto" is treated as "required": the tool user here is the PaperQA2 agent, whose loop (aviary) wants a
        # tool call every turn (it finishes with its own "complete" tool); it sends "auto" only because vLLM 0.21
        # answered "required" with an empty reply (baselines paperqa2.py agent_tool_choice). "none" sends no tools.
        must = (body.get("tool_choice") or "auto") != "none"
        system.append(TOOL_PROTOCOL.format(
            tools=json.dumps([t.get("function", t) for t in tools], ensure_ascii=False, indent=1),
            answer_rule="you must call at least one tool." if must else
            'to answer without a tool: {"content": "<your answer>"}'))
    elif (body.get("response_format") or {}).get("type") in ("json_object", "json_schema"):
        system.append("Reply with one JSON object only, no other text.")
    transcript = turns[0].split("\n", 1)[1] if len(turns) == 1 and turns[0].startswith("[user]") else \
        "\n\n".join(turns)
    return "\n\n".join(s for s in system if s), transcript


def parse_tool_reply(text: str) -> tuple[str | None, list[dict[str, Any]]] | None:
    """(content, tool calls in OpenAI form) of a reply under the tool protocol; None when unreadable."""
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < a:
        return None
    try:
        got = json.loads(text[a:b + 1])
    except ValueError:
        return None
    if not isinstance(got, dict):
        return None
    calls = got.get("tool_calls")
    if isinstance(calls, list) and calls and all(isinstance(c, dict) and c.get("name") for c in calls):
        return None, [{"id": f"call_{uuid.uuid4().hex[:12]}", "type": "function",
                       "function": {"name": c["name"], "arguments": json.dumps(_args(c.get("arguments")))}}
                      for c in calls]
    if isinstance(got.get("content"), str):
        return got["content"], []
    return None


def _args(a: Any) -> dict[str, Any]:
    """Tool arguments as an object: the model sometimes writes them as a JSON string ("{\\"q\\": ...}")."""
    for _ in range(2):
        if isinstance(a, str):
            try:
                a = json.loads(a)
            except ValueError:
                return {}
    return a if isinstance(a, dict) else {}


def claude(model: str, system: str, transcript: str, timeout: int = TIMEOUT) -> dict[str, Any]:
    """One `claude -p` call: {"text", "usage"}. Raises RuntimeError on failure."""
    with tempfile.TemporaryDirectory(prefix="claude-gw-") as tmp:
        cmd = ["claude", "-p", "--model", model, "--tools", "", "--setting-sources", "", "--strict-mcp-config",
               "--no-session-persistence", "--output-format", "json"]
        if system:
            (Path(tmp) / "system.txt").write_text(system, encoding="utf-8")
            cmd += ["--system-prompt-file", str(Path(tmp) / "system.txt")]
        done = subprocess.run(cmd, input=transcript, capture_output=True, text=True, cwd=tmp, timeout=timeout)
    try:
        out = json.loads(done.stdout)
    except ValueError as e:
        raise RuntimeError(f"claude gave no JSON (exit {done.returncode}): {done.stderr[-300:]}") from e
    if out.get("is_error"):
        raise RuntimeError(f"claude failed: {str(out.get('result'))[:300]}")
    u = out.get("usage") or {}
    prompt = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return {"text": out.get("result") or "", "usage": {"prompt_tokens": prompt,
                                                        "completion_tokens": u.get("output_tokens") or 0,
                                                        "total_tokens": prompt + (u.get("output_tokens") or 0)}}


def complete(body: dict[str, Any], call=claude) -> dict[str, Any]:
    """An OpenAI chat.completion for one request (`call` replaces the CLI in tests)."""
    model = body.get("model", "")
    if not model.startswith("claude-"):
        raise ValueError(f"model {model!r}: this gateway serves Claude models only (e.g. claude-haiku-5-5)")
    system, transcript = prompt_parts(body)
    out = call(model, system, transcript)
    content, calls = out["text"], []
    if body.get("tools") and body.get("tool_choice") != "none":
        got = parse_tool_reply(out["text"])
        if got is None:   # once more, then the reply as plain content
            out = call(model, system, transcript + "\n\n[note] Your last reply was not one JSON object of the "
                                                  "required form. Reply again with only that JSON object.")
            got = parse_tool_reply(out["text"]) or (out["text"], [])
        content, calls = got
    msg: dict[str, Any] = {"role": "assistant", "content": content}
    if calls:
        msg["tool_calls"] = calls
    return {"id": f"chatcmpl-{uuid.uuid4().hex}", "object": "chat.completion", "created": int(time.time()),
            "model": model, "choices": [{"index": 0, "message": msg,
                                         "finish_reason": "tool_calls" if calls else "stop"}],
            "usage": out["usage"]}


def chunk(resp: dict[str, Any]) -> dict[str, Any]:
    """The whole reply as one streaming chunk."""
    msg = resp["choices"][0]["message"]
    delta: dict[str, Any] = {"role": "assistant", "content": msg.get("content")}
    if msg.get("tool_calls"):
        delta["tool_calls"] = [{"index": i, **c} for i, c in enumerate(msg["tool_calls"])]
    return {"id": resp["id"], "object": "chat.completion.chunk", "created": resp["created"], "model": resp["model"],
            "choices": [{"index": 0, "delta": delta, "finish_reason": resp["choices"][0]["finish_reason"]}],
            "usage": resp["usage"]}


def serve(port: int, parallel: int) -> None:
    gate = threading.BoundedSemaphore(parallel)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None:   # no default access log
            pass

        def _send(self, code: int, obj: dict[str, Any]) -> None:
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path.rstrip("/").endswith("/models"):
                self._send(200, {"object": "list", "data": [{"id": "claude-haiku-5-5", "object": "model"}]})
            else:
                self._send(200, {"ok": True})

        def do_POST(self) -> None:
            if not self.path.rstrip("/").endswith("/chat/completions"):
                return self._send(404, {"error": {"message": f"no route {self.path}"}})
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            t0, ok = time.time(), False
            try:
                with gate:
                    resp = complete(body)
                ok = True
            except ValueError as e:
                return self._send(400, {"error": {"message": str(e), "type": "invalid_request_error"}})
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                return self._send(502, {"error": {"message": str(e)[:500], "type": "upstream_error"}})
            finally:
                print(f"{time.strftime('%T')} {body.get('model')} {int((time.time() - t0) * 1000)}ms "
                      f"{'ok' if ok else 'fail'}{' tools' if body.get('tools') else ''}", file=sys.stderr, flush=True)
            if body.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(f"data: {json.dumps(chunk(resp))}\n\ndata: [DONE]\n\n".encode())
            else:
                self._send(200, resp)

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"claude gateway on http://127.0.0.1:{port}/v1 ({parallel} calls at a time)", file=sys.stderr, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=4199)
    ap.add_argument("--parallel", type=int, default=16)
    a = ap.parse_args()
    serve(a.port, a.parallel)
