"""Clean stop on SIGTERM (row 2.9): the batch runner, or Slurm at the job limit, ends a run or an attach step.

`install()` makes the first SIGTERM raise SystemExit(143) in the main thread; mini-swe-agent and the
loop catch only Exception, so their `finally` blocks run: the broker is closed (its chain head
printed) and a running sandboxed command is killed with its process group. Library code may
swallow that SystemExit (e.g. an HTTP client turning it into a connection error that is then
retried), so the request is also remembered, and `check()` raises it again at the harness's safe
points: before every model call and before every command. Later SIGTERMs do nothing more, so
cleanup is not interrupted.
"""
from __future__ import annotations

import signal

EXIT_CODE = 128 + signal.SIGTERM
_requested = False


def requested() -> bool:
    return _requested


def check() -> None:
    if _requested:
        raise SystemExit(EXIT_CODE)


def _handler(signum: int, frame: object) -> None:
    global _requested
    if _requested:
        return
    _requested = True
    raise SystemExit(EXIT_CODE)


def install() -> None:
    signal.signal(signal.SIGTERM, _handler)
