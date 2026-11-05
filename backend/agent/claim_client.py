#!/usr/bin/env python3
"""The `claim` command (row 1.7): runs inside the sandbox, standard library only.

Reads one JSON object {s, p, o, file, quote} on stdin, sends it to the broker over the inherited
descriptor in $CLAIM_FD, and prints the broker's reply: {"ok": true, "claim_id": ...} or
{"ok": false, "reason": ...}. Exit status 0 when accepted, 1 when rejected, 2 on a usage error.
It never creates a socket (the sandbox's seccomp filter forbids that); it only uses CLAIM_FD.
"""
from __future__ import annotations

import json
import os
import socket
import sys
from typing import Any


def submit(sock: socket.socket, request: dict[str, Any]) -> dict[str, Any]:
    with sock.makefile("rwb") as stream:
        stream.write(json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
        stream.flush()
        reply = stream.readline()
    if not reply:
        return {"ok": False, "reason": "broker closed the claim channel"}
    return json.loads(reply.decode("utf-8"))


def fail(reason: str) -> int:
    print(json.dumps({"ok": False, "reason": reason}, ensure_ascii=False))
    return 2


def main() -> int:
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except ValueError as exc:
        return fail(f"stdin is not one JSON object: {exc}")
    if not isinstance(request, dict):
        return fail("stdin must be one JSON object with s, p, o, file, quote")
    fd = os.environ.get("CLAIM_FD", "")
    if not fd.isdigit():
        return fail("CLAIM_FD is not set; claims only work inside an agent command")
    sock = socket.socket(fileno=int(fd))
    try:
        reply = submit(sock, request)
    finally:
        sock.detach()  # leave the descriptor open for a later `claim` in the same command
    print(json.dumps(reply, ensure_ascii=False))
    return 0 if reply.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
