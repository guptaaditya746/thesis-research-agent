"""The process seam under the job manager: start a command in a process group of its own, tell whether a
process is the one a job recorded, signal its whole group. `PosixProcesses` is the real adapter (the code the
job manager used to hold); tests inject `webapp/tests/fakes.py:FakeProcesses`. The job manager never touches
`signal` constants (SIGKILL does not exist on Windows): it says "term" or "kill" and the adapter maps them."""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
from pathlib import Path
from typing import BinaryIO, Literal, Protocol


class Proc(Protocol):
    pid: int
    returncode: int | None

    async def wait(self) -> int: ...


class Processes(Protocol):
    async def start(self, argv: list[str], *, log: BinaryIO, cwd: Path, env: dict[str, str]) -> Proc:
        """Run `argv` with its output to `log`, in a session and process group of its own (its pid is the
        group's id); OSError when it cannot start."""
        ...

    def start_token(self, pid: int) -> str | None:
        """The identity of a live process (its start time), so a reused pid is never mistaken for it; None when gone."""
        ...

    def signal(self, pid: int, how: Literal["term", "kill"]) -> None:
        """`how` to the whole process group `pid` leads; a group that is gone is ignored."""
        ...


class PosixProcesses:
    async def start(self, argv: list[str], *, log: BinaryIO, cwd: Path, env: dict[str, str]) -> Proc:
        return await asyncio.create_subprocess_exec(
            *argv, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, cwd=cwd, env=env,
            start_new_session=True)  # a Ctrl-C at the server is not sent to it

    def start_token(self, pid: int) -> str | None:
        """The process's start time in clock ticks since boot (/proc/<pid>/stat field 22); None when it is gone, a
        zombie, or there is no /proc (then no process outlives its server as far as the app can tell)."""
        try:
            data = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        fields = data.rsplit(")", 1)[-1].split()   # after "pid (comm)": state is field 3, starttime field 22
        if len(fields) < 20 or fields[0] in ("Z", "X"):
            return None
        return fields[19]

    def signal(self, pid: int, how: Literal["term", "kill"]) -> None:
        sig = signal.SIGTERM if how == "term" else signal.SIGKILL
        try:
            os.killpg(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass
