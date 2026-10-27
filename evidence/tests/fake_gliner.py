"""A stand-in for the GLiNER service (llm-setup, Task C4) for tests: the same HTTP contract, run in-process on a
free localhost port (threading http.server), with a deterministic regex entity finder in place of the model.

    GET  /info     -> {"model": <name>}
    POST /predict  {"text", "labels", "threshold"} -> {"entities": [{"start", "end", "text", "label", "score"}]}

Each label has a list of (pattern, score); an entity is a match of a requested label's pattern whose score is at
least the threshold. `requests` keeps every /predict body; `delay` makes /predict slow (a timeout test);
`info_fails` answers the first n GET /info with 503 (a service still loading).
"""
from __future__ import annotations

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PATTERNS: dict[str, list[tuple[str, float]]] = {
    "method": [(r"(?i)\bretrieval-augmented variant\b", 0.9), (r"\bcontrastive decoding\b", 0.8)],
    "system variant": [(r"(?i)\bretrieval-augmented variant\b", 0.7)],
    "baseline model": [(r"(?i)\bclosed-book baseline\b", 0.9)],
    "evaluation metric": [(r"(?i)\bfactual accuracy\b|\bhallucination rate\b", 0.9), (r"\bBLEU\b", 0.6),
                          (r"\bfluency\b", 0.3)],
    "dataset": [(r"\b[A-Z][A-Za-z]*QA\b", 0.9)],
}


def find(text: str, labels: list[str], threshold: float,
         patterns: dict[str, list[tuple[str, float]]]) -> list[dict[str, Any]]:
    out = []
    for label in labels:
        for pattern, score in patterns.get(label, []):
            if score < threshold:
                continue
            for m in re.finditer(pattern, text):
                out.append({"start": m.start(), "end": m.end(), "text": m.group(), "label": label, "score": score})
    return sorted(out, key=lambda e: (e["start"], e["end"], e["label"]))


class FakeGliner:
    """`with FakeGliner() as server:` serves on `server.url` until the block ends."""

    def __init__(self, model: str = "fake/gliner-test", patterns: dict[str, list[tuple[str, float]]] | None = None,
                 delay: float = 0.0, offsets: int = 0, info_fails: int = 0) -> None:
        self.model, self.patterns, self.delay = model, patterns or PATTERNS, delay
        self.info_fails = info_fails
        self.offsets = offsets       # added to every start and end: a server whose offsets are wrong
        self.requests: list[dict[str, Any]] = []
        self.info_calls = 0
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:   # quiet
                pass

            def _send(self, body: dict[str, Any]) -> None:
                data = json.dumps(body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:   # noqa: N802 - http.server's name
                if self.path != "/info":
                    self.send_error(404)
                    return
                fake.info_calls += 1
                if fake.info_calls <= fake.info_fails:
                    self.send_error(503, "loading")
                    return
                self._send({"model": fake.model})

            def do_POST(self) -> None:   # noqa: N802
                if self.path != "/predict":
                    self.send_error(404)
                    return
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
                fake.requests.append(body)
                if fake.delay:
                    time.sleep(fake.delay)
                entities = find(body["text"], body["labels"], body["threshold"], fake.patterns)
                for e in entities:
                    e["start"] += fake.offsets
                    e["end"] += fake.offsets
                self._send({"entities": entities})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> FakeGliner:
        self.thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.server.shutdown()
        self.server.server_close()


def closed_url() -> str:
    """A localhost URL nothing listens on (a port bound and released)."""
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}"
