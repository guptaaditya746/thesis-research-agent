"""The real process adapter (webapp/procs.py) on a POSIX machine: a command's whole process group ends together;
and the tool wrapper turns SIGTERM into a clean exit."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from webapp.procs import PosixProcesses
from webapp.settings import REPO

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="process groups, /proc and SIGTERM (POSIX)")


def test_term_ends_the_whole_group_and_its_token_goes(tmp_path: Path) -> None:
    procs = PosixProcesses()
    pidfile = tmp_path / "child.pid"
    script = f"sleep 30 & echo $! > {pidfile}; sleep 30"

    async def main() -> tuple[str | None, int, int]:
        with open(tmp_path / "log", "wb") as log:
            proc = await procs.start(["sh", "-c", script], log=log, cwd=tmp_path, env=dict(os.environ))
            end = time.monotonic() + 10
            while not (pidfile.exists() and pidfile.read_text().strip()):
                assert time.monotonic() < end, "the child never started"
                await asyncio.sleep(0.02)
            token = procs.start_token(proc.pid)
            procs.signal(proc.pid, "term")
            code = await asyncio.wait_for(proc.wait(), 10)
        return token, code, proc.pid

    token, code, leader = asyncio.run(main())
    child = int(pidfile.read_text())
    assert token is not None and code != 0
    end = time.monotonic() + 10
    while procs.start_token(child) is not None and time.monotonic() < end:
        time.sleep(0.05)
    assert procs.start_token(child) is None      # the grandchild went with its group
    assert procs.start_token(leader) is None
    procs.signal(leader, "kill")                 # a gone group is ignored


def test_the_tool_turns_sigterm_into_a_clean_exit(tmp_path: Path) -> None:
    """`python -m webapp.tool` installs agent/stopping.py before the package's main: SIGTERM raises
    SystemExit(143), so finally blocks (broker, sandbox) run."""
    code = ("import sys, time\n"
            "import webapp.tool as tool\n"
            "from evidence import cli\n"
            "def main(argv):\n"
            "    try:\n        print('ready', flush=True); time.sleep(30)\n"
            "    finally:\n        open(argv[0], 'w').write('cleaned up')\n"
            "cli.main = main\n"
            "sys.exit(tool.main(['evidence', sys.argv[1]]))\n")
    marker = tmp_path / "marker"
    proc = subprocess.Popen([sys.executable, "-c", code, str(marker)], cwd=REPO, stdout=subprocess.PIPE, text=True)
    assert proc.stdout is not None and proc.stdout.readline().strip() == "ready"
    proc.terminate()
    assert proc.wait(10) == 143 and marker.read_text() == "cleaned up"
