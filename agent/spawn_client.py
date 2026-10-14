#!/usr/bin/env python3
"""The `spawn` command (row 2.12): runs inside the sandbox, standard library only.

    spawn --task "TEXT" [--files a.md,b.md] [--steps N]

Sends one request {task, files, steps} to the harness over the inherited descriptor in
$SPAWN_FD and prints the subagent's result when it is done: {"ok": true, "agent_id": "sub-01",
"status": ..., "summary": ..., "claims": [...], ...} for a subagent that ran, whatever its
status (submitted, budget, error, ...), or {"ok": false, "reason": ...} when none ran. Exit
status 0 when a subagent ran, 1 when the harness refused the request or could not run it, 2 on
a usage error or without $SPAWN_FD (spawn is off in this run, or this is a subagent, which
cannot spawn).

Several spawns may share one command's descriptor (`spawn ... & spawn ... & wait`), so the reply
does not come back on it: SPAWN_FD is a SOCK_SEQPACKET socket, each request is one message, and
it carries the write end of a pipe this process made, on which the harness writes the result.
Neither creates a socket, which the sandbox's seccomp filter forbids (pipes are allowed).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys

MAX_REQUEST = 64 * 1024  # what the harness reads of one request


def fail(reason: str, code: int = 2) -> int:
    print(json.dumps({"ok": False, "reason": reason}, ensure_ascii=False))
    return code


def request(sock: socket.socket, body: dict[str, object]) -> dict[str, object]:
    """Send `body` with a fresh pipe's write end; read the reply from its read end until EOF."""
    data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    read_end, write_end = os.pipe()
    try:
        socket.send_fds(sock, [data], [write_end])
    finally:
        os.close(write_end)  # the harness holds the only write end now, so EOF means it is done
    with os.fdopen(read_end, "rb") as reply:
        raw = reply.read()
    if not raw.strip():
        return {"ok": False, "reason": "no_reply: the harness closed the request without a result"}
    return json.loads(raw.decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="spawn", description="Start a subagent and print its result.")
    parser.add_argument("--task", required=True, help="what the subagent should find and report")
    parser.add_argument("--files", default="", help="corpus files to start from, comma-separated: a.md,b.md")
    parser.add_argument("--steps", type=int, help="the subagent's step budget (at most the run's)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse printed the usage
        return 2 if exc.code else 0
    if not args.task.strip():
        return fail("bad_request: --task is empty")
    fd = os.environ.get("SPAWN_FD", "")
    if not fd.isdigit():
        return fail("spawn is not available here: it is off in this run, or this is a subagent (subagents cannot spawn)")
    body = {"task": args.task, "files": [f.strip() for f in args.files.split(",") if f.strip()], "steps": args.steps}
    if len(json.dumps(body, ensure_ascii=False).encode("utf-8")) > MAX_REQUEST:
        return fail("bad_request: the task is over 64 KB")
    sock = socket.socket(fileno=int(fd))
    try:
        reply = request(sock, body)
    except OSError as exc:
        return fail(f"the spawn channel failed: {exc}", 1)
    finally:
        sock.detach()  # leave the descriptor open for the other spawns of this command
    print(json.dumps(reply, ensure_ascii=False))
    return 0 if reply.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
