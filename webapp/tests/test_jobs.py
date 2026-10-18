"""The job manager (webapp/jobs.py) with small Python commands: steps, lanes, cancel, restart, the log tail."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import pytest

from webapp.files import Conflict
from webapp.jobs import JobManager, process_start, step
from webapp.models import Job
from webapp.settings import Settings


def py(code: str, *args: str) -> list[str]:
    return [sys.executable, "-c", code, *args]


async def finished(manager: JobManager, job: Job, timeout: float = 20) -> Job:
    end = time.monotonic() + timeout
    while job.state in ("queued", "running"):
        assert time.monotonic() < end, "job did not finish"
        await asyncio.sleep(0.02)
    return job


def settings_in(tmp_path: Path, **more: object) -> Settings:
    return Settings(EV=tmp_path / "ev", **more)  # type: ignore[arg-type]


def test_steps_run_in_order_with_needs_and_optional_failures(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> Job:
        manager = JobManager(settings)
        job = manager.submit("demo", {"n": 1}, [
            step("hello", py("print('hello from step 1')")),
            step("optional", py("import sys; print('broken'); sys.exit(3)"), required=False),
            step("needs", py("print('never')"), needs=[tmp_path, tmp_path / "missing.json"]),
            step("last", py("import sys; print('last', sys.argv[1])", "arg with spaces"), needs=tmp_path),
        ], refs={"corpus": "c1"})
        assert job.state == "queued" and (settings.jobs_dir / f"{job.id}.json").is_file()
        assert manager.busy("corpus", "c1") is job and manager.busy("corpus", "c2") is None
        return await finished(manager, job)

    job = asyncio.run(main())
    assert (job.state, job.exit_code, job.error, job.lane) == ("done", 0, None, "cpu")
    assert job.warnings == ["optional failed (exit 3); see the log"]  # done, but not silently
    assert [(s.name, s.state, s.exit_code) for s in job.steps] == [
        ("hello", "done", 0), ("optional", "failed", 3), ("needs", "skipped", None), ("last", "done", 0)]
    log = (settings.jobs_dir / f"{job.id}.log").read_text(encoding="utf-8")
    assert "hello from step 1\n" in log and "# optional exit 3" in log and "never" not in log
    assert f"# skipped needs: {tmp_path / 'missing.json'} does not exist" in log
    assert "last arg with spaces" in log and "'arg with spaces'" in log  # the command line, shell-quoted
    saved = Job.model_validate_json((settings.jobs_dir / f"{job.id}.json").read_text(encoding="utf-8"))
    assert saved == job


def test_no_jobs_without_ev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EV", raising=False)

    async def main() -> None:
        with pytest.raises(Conflict, match=r"\$EV"):
            JobManager(Settings()).submit("demo", {}, [step("x", py("pass"))])

    asyncio.run(main())


def test_a_failed_required_step_fails_the_job(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> Job:
        manager = JobManager(settings)
        return await finished(manager, manager.submit("demo", {}, [step("bad", py("import sys; sys.exit(5)")),
                                                                    step("next", py("pass"))]))

    job = asyncio.run(main())
    assert (job.state, job.exit_code) == ("failed", 5)
    assert [s.state for s in job.steps] == ["failed", "done"]  # later steps still run


SLEEPER = ("import sys, time; f = open(sys.argv[1], 'a'); f.write(sys.argv[2] + ' start\\n'); f.flush(); "
           "time.sleep(0.4); f.write(sys.argv[2] + ' end\\n')")


def test_model_jobs_queue_one_at_a_time_and_cpu_jobs_run_beside_them(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)
    trace = tmp_path / "trace.txt"

    async def main() -> list[Job]:
        manager = JobManager(settings)
        models = [manager.submit("run", {}, [step("s", py(SLEEPER, str(trace), f"m{n}"))], lane="model") for n in range(3)]
        cpu = manager.submit("synth", {}, [step("s", py(SLEEPER, str(trace), "c0"))], lane="cpu")
        assert [j.state for j in models] == ["queued"] * 3
        for job in [*models, cpu]:
            await finished(manager, job)
        return [*models, cpu]

    jobs = asyncio.run(main())
    assert {j.state for j in jobs} == {"done"}
    lines = trace.read_text().splitlines()
    model_lines = [ln for ln in lines if ln.startswith("m")]
    assert model_lines == ["m0 start", "m0 end", "m1 start", "m1 end", "m2 start", "m2 end"]  # never interleaved
    assert lines.index("c0 start") < lines.index("m0 end")   # the cpu job did not wait for the model queue
    m0, m1 = jobs[0], jobs[1]
    assert m0.ended_at <= m1.started_at


def test_more_model_jobs_at_a_time_when_configured(tmp_path: Path) -> None:
    settings = settings_in(tmp_path, WEBAPP_MODEL_JOBS=2)
    trace = tmp_path / "trace.txt"

    async def main() -> None:
        manager = JobManager(settings)
        jobs = [manager.submit("run", {}, [step("s", py(SLEEPER, str(trace), f"m{n}"))], lane="model") for n in range(2)]
        for job in jobs:
            await finished(manager, job)

    asyncio.run(main())
    lines = trace.read_text().splitlines()
    assert lines.index("m1 start") < lines.index("m0 end")


def test_cancel(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> tuple[Job, Job]:
        manager = JobManager(settings)
        running = manager.submit("run", {}, [step("sleep", py("import time; time.sleep(30)")),
                                             step("after", py("print('after')"))], lane="model")
        queued = manager.submit("run", {}, [step("never", py("print('never')"))], lane="model")
        while running.steps[0].state != "running":
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.2)
        manager.cancel(queued.id)
        assert queued.state == "failed" and queued.error == "cancelled"  # at once
        t0 = time.monotonic()
        manager.cancel(running.id)
        await finished(manager, running)
        assert time.monotonic() - t0 < 10
        return running, queued

    running, queued = asyncio.run(main())
    assert (running.state, running.error) == ("failed", "cancelled")
    assert [s.state for s in running.steps] == ["failed", "skipped"] and running.steps[0].exit_code != 0
    assert [s.state for s in queued.steps] == ["skipped"] and queued.started_at is None


def test_jobs_survive_a_restart(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> Job:
        manager = JobManager(settings)
        return await finished(manager, manager.submit("demo", {"a": 1}, [step("ok", py("pass"))]))

    done = asyncio.run(main())
    lost = done.model_copy(deep=True, update={"id": "20260101T000000-run-abcdef", "state": "running", "ended_at": None})
    lost.steps[0].state = "running"
    (settings.jobs_dir / f"{lost.id}.json").write_text(lost.model_dump_json(), encoding="utf-8")
    (settings.jobs_dir / "garbage.json").write_text("{not json", encoding="utf-8")
    manager = JobManager(settings)
    manager.load()
    assert manager.get(done.id) == done
    again = manager.get(lost.id)
    assert again.state == "failed" and "server stopped" in again.error and again.steps[0].state == "failed"
    assert json.loads((settings.jobs_dir / f"{lost.id}.json").read_text())["state"] == "failed"
    assert [j.id for j in manager.list()] == [done.id, lost.id]   # newest first


def test_log_tail(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> Job:
        manager = JobManager(settings)
        return await finished(manager, manager.submit("demo", {}, [step("count", py("for n in range(500): print(n)"))]))

    job = asyncio.run(main())
    manager = JobManager(settings)
    manager.load()
    tail = manager.tail(job.id, 3)
    assert tail == "498\n499\n# count exit 0\n"
    assert manager.tail(job.id, 1000).startswith("$ ")


GRANDCHILD = ("import subprocess, sys, time; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
              "open(sys.argv[1], 'w').write(str(p.pid)); time.sleep(60)")


def gone(pid: int, timeout: float = 10) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if process_start(pid) is None:
            return True
        time.sleep(0.05)
    return False


@pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="process groups and /proc (Linux)")
def test_cancel_stops_the_whole_process_group(tmp_path: Path) -> None:
    """A command's children (the agent's sandboxed commands, the broker) end with it."""
    settings = settings_in(tmp_path)
    pidfile = tmp_path / "grandchild.pid"

    async def main() -> Job:
        manager = JobManager(settings)
        job = manager.submit("run", {}, [step("spawns", py(GRANDCHILD, str(pidfile)))], lane="model")
        while not pidfile.exists() or not pidfile.read_text():
            await asyncio.sleep(0.05)
        assert job.steps[0].pid is not None and job.steps[0].pid_start == process_start(job.steps[0].pid)
        manager.cancel(job.id)
        return await finished(manager, job)

    job = asyncio.run(main())
    assert (job.state, job.error) == ("failed", "cancelled")
    assert gone(int(pidfile.read_text()))


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM (POSIX)")
def test_the_tool_turns_sigterm_into_a_clean_exit(tmp_path: Path) -> None:
    """`python -m webapp.tool` installs agent/stopping.py before the package's main: SIGTERM raises
    SystemExit(143), so finally blocks (broker, sandbox) run."""
    import subprocess

    from webapp.settings import REPO
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


@pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="process start times from /proc (Linux)")
def test_a_job_whose_process_outlives_its_server_stays_running_and_cancellable(tmp_path: Path) -> None:
    import subprocess

    settings = settings_in(tmp_path)
    settings.jobs_dir.mkdir(parents=True)
    orphan = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
    s = step("evidence run", ["python", "-m", "webapp.tool", "evidence", "run"])
    s.state, s.pid, s.pid_start = "running", orphan.pid, process_start(orphan.pid)
    live = Job(id="20260101T000000-run-aaaaaa", kind="run", lane="model", args={}, refs={"run": "cascade~c1"},
               state="running", created_at="2026-01-01T00:00:00Z", steps=[s, step("next", ["true"])])
    dead_step = s.model_copy(update={"pid_start": "1"})   # the same pid with another start time: a reused pid
    dead = live.model_copy(update={"id": "20260101T000000-run-bbbbbb", "refs": {"run": "cascade~c2"}, "steps": [dead_step]})
    for job in (live, dead):
        (settings.jobs_dir / f"{job.id}.json").write_text(job.model_dump_json(), encoding="utf-8")

    async def main() -> tuple[Job, Job, bool]:
        manager = JobManager(settings)
        manager.load()
        kept, lost = manager.get(live.id), manager.get(dead.id)
        assert (kept.state, kept.orphaned) == ("running", True)
        assert manager.busy("run", "cascade~c1") is kept and manager.busy("run", "cascade~c2") is None
        queued = manager.submit("run", {}, [step("waits", py("pass"))], lane="model")
        await asyncio.sleep(0.5)
        waited = queued.state == "queued"           # the orphan holds the model lane
        manager.cancel(kept.id)                     # SIGTERM to its process group
        await finished(manager, kept)
        await finished(manager, queued)
        return kept, lost, waited

    kept, lost, waited = asyncio.run(main())
    orphan.wait(10)
    assert waited and (kept.state, kept.error) == ("failed", "cancelled") and kept.steps[1].state == "skipped"
    assert lost.state == "failed" and "server stopped" in (lost.error or "")
