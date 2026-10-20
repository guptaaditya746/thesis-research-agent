"""A keep-alive OpenAI-compatible chat server for tests that drive the real model class over HTTP.

`keepalive_server(reply)` serves `POST .../chat/completions` with HTTP/1.1 keep-alive, as LiteLLM does, so a
second call in the same process reuses the pooled connection of the first (EV1: that failed with "Event loop
is closed" when each call ran in its own `asyncio.run`). `reply` maps the last user message to the JSON object
the model returns; the server's `prompts` are the messages it received, in order."""
from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class KeepAliveServer(str):
    """The base URL (`http://127.0.0.1:PORT/v1`), carrying the prompts the server received."""
    prompts: list[str]


@contextmanager
def keepalive_server(reply: Callable[[str], dict[str, Any]]) -> Iterator[KeepAliveServer]:
    prompts: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"  # keep the connection open between requests

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            prompt = body["messages"][-1]["content"]
            prompts.append(prompt)
            content = json.dumps(reply(prompt))
            data = json.dumps({"id": f"c{len(prompts)}", "object": "chat.completion", "created": 0, "model": "m",
                               "choices": [{"index": 0, "finish_reason": "stop",
                                            "message": {"role": "assistant", "content": content}}],
                               "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = KeepAliveServer(f"http://127.0.0.1:{server.server_address[1]}/v1")
    url.prompts = prompts
    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()
