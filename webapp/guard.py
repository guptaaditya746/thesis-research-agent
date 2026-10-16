"""Keep other web pages out of the API: a Host check and a same-origin rule for every write.

The server has no authentication: it binds to 127.0.0.1 and the user reaches it through an SSH
tunnel (docs/earlier-work.md, Web app). That alone does not keep a web page the user has open elsewhere away:
- a plain HTML form can POST to http://127.0.0.1:8080/api/... from any site without a CORS
  preflight (a body-less POST such as `POST /api/gold/{qid}/build` starts a gold build, which also
  freezes the question's concept pick for good);
- DNS rebinding points a name the attacker controls at 127.0.0.1, so the attacker's page can read
  every response; its requests then carry that name in the Host header.

So (one ASGI middleware, before any route):
- a request whose Host is not one of `allowed_hosts` (the loopback names by default; the port is
  not checked) gets 400;
- a request under /api that is not GET, HEAD or OPTIONS gets 403 unless it is a JSON request
  (Content-Type application/json, which a cross-site page can only send after a CORS preflight the
  server never grants) or names itself with X-Requested-With, and, when the browser sends an Origin,
  that origin is the server's own host. The frontend's client (webapp/web/src/api/client.ts) and
  the chat transport send JSON bodies, so they pass.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, MutableMapping
from typing import Any
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

Scope = MutableMapping[str, Any]
ASGIApp = Callable[[Scope, Callable[[], Awaitable[Any]], Callable[[Any], Awaitable[None]]], Awaitable[None]]

DEFAULT_HOSTS = ("127.0.0.1", "localhost", "::1")
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def host_name(value: str) -> str:
    """The name in a Host header or an origin's netloc, without the port; IPv6 without brackets."""
    value = value.strip().lower()
    if value.startswith("["):
        return value[1:value.find("]")] if "]" in value else value
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


class Guard:
    def __init__(self, app: ASGIApp, allowed_hosts: Iterable[str] = DEFAULT_HOSTS) -> None:
        self.app = app
        self.allowed = {host_name(h) for h in allowed_hosts}

    async def __call__(self, scope: Scope, receive: Callable[[], Awaitable[Any]],
                       send: Callable[[Any], Awaitable[None]]) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers") or []}
        refused = self.refusal(scope, headers)
        if refused is not None:
            status, detail = refused
            await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def refusal(self, scope: Scope, headers: dict[str, str]) -> tuple[int, str] | None:
        host = headers.get("host", "")
        if host_name(host) not in self.allowed:
            return 400, (f"Host {host!r} is not served (the app answers on {', '.join(sorted(self.allowed))}); "
                         "reach it through the SSH tunnel at http://127.0.0.1:<port>")
        method = str(scope.get("method", "GET")).upper()
        if method in SAFE_METHODS or not str(scope.get("path", "")).startswith("/api"):
            return None
        origin = headers.get("origin")
        if origin and urlsplit(origin).netloc.lower() != host.strip().lower():  # "null" has no netloc
            return 403, f"cross-origin request from {origin!r} refused"
        content_type = headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type != "application/json" and "x-requested-with" not in headers:
            return 403, ("a request that changes something must be JSON (Content-Type: application/json) or "
                         "carry X-Requested-With")
        return None
