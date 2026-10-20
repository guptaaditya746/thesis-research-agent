"""A fake `Processes` (webapp/procs.py) for the job manager's tests: no real subprocess, no sleeping."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import BinaryIO, Literal


class FakeProc:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.returncode: int | None = None
        self._done = asyncio.Event()

    async def wait(self) -> int:
        await self._done.wait()
        assert self.returncode is not None
        return self.returncode

    def end(self, code: int) -> None:
        self.returncode = code
        self._done.set()


class FakeProcesses:
    def __init__(self, *, fail_start: bool = False, ignore_term: bool = False) -> None:
        self.started: list[list[str]] = []
        self.signals: list[tuple[int, str]] = []
        self.fail_start = fail_start      # start() raises OSError
        self.ignore_term = ignore_term    # "term" does nothing (a command that must be killed)
        self._procs: dict[int, FakeProc] = {}
        self._tokens: dict[int, str | None] = {}
        self._next = 1000

    async def start(self, argv: list[str], *, log: BinaryIO, cwd: Path, env: dict[str, str]) -> FakeProc:
        if self.fail_start:
            raise OSError("no such command")
        self._next += 1
        proc = FakeProc(self._next)
        self._procs[proc.pid] = proc
        self._tokens[proc.pid] = f"tick{proc.pid}"
        self.started.append(list(argv))
        return proc

    def start_token(self, pid: int) -> str | None:
        return self._tokens.get(pid)

    def signal(self, pid: int, how: Literal["term", "kill"]) -> None:
        self.signals.append((pid, how))
        if how == "term" and self.ignore_term:
            return
        self.finish(pid, -15 if how == "term" else -9)

    def finish(self, pid: int, code: int = 0) -> None:
        """End that fake process (an unknown pid, e.g. an orphan, just stops being alive)."""
        self._tokens[pid] = None
        proc = self._procs.get(pid)
        if proc is not None and proc.returncode is None:
            proc.end(code)

    def set_alive(self, pid: int, token: str | None) -> None:
        self._tokens[pid] = token
