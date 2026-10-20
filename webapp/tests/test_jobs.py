"""The job manager (webapp/jobs.py) on a fake process seam (webapp/tests/fakes.py): lanes, needs, cancel, restart,
shutdown. No real subprocess and no sleeping, so it runs on any OS; the real adapter is test_procs_posix.py."""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import pytest

import webapp.jobs as jobs_module
from webapp.files import Conflict
from webapp.jobs import JobManager, step
from webapp.models import Job
from webapp.settings import Settings
from webapp.tests.fakes import FakeProcesses


def settings_in(tmp_path: Path, **more: object) -> Settings:
    return Settings(EV=tmp_path / "ev", **more)  # type: ignore[arg-type]


async def until(cond: Callable[[], bool], what: str = "condition") -> None:
    """Yield to the event loop until `cond` holds (fake processes only move when the test says so)."""
    for _ in range(10_000):
        if cond():
            return
        await asyncio.sleep(0)
    raise AssertionError(f"never: {what}")


def pid_of(job: Job, index: int = 0) -> int:
    pid = job.steps[index].pid
    assert pid is not None
    return pid


def test_model_lane_runs_one_at_a_time(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> None:
        fake = FakeProcesses()
        manager = JobManager(settings, processes=fake)
        models = [manager.submit("run", {}, [step("s", ["m", str(n)])], lane="model") for n in range(2)]
        cpu = manager.submit("synth", {}, [step("s", ["c"])], lane="cpu")
        await until(lambda: len(fake.started) == 2, "first model job and the cpu job started")
        assert fake.started == [["m", "0"], ["c"]]       # the cpu job runs beside the model queue
        assert [j.state for j in models] == ["running", "queued"]
        fake.finish(pid_of(models[0]))
        await until(lambda: models[1].state == "running", "second model job started")
        assert fake.started[-1] == ["m", "1"] and models[0].state == "done"
        fake.finish(pid_of(models[1]))
        fake.finish(pid_of(cpu))
        await until(lambda: {j.state for j in [*models, cpu]} == {"done"}, "all done")
        assert models[0].ended_at <= models[1].started_at

    asyncio.run(main())


def test_more_model_jobs_at_a_time_when_configured(tmp_path: Path) -> None:
    settings = settings_in(tmp_path, WEBAPP_MODEL_JOBS=2)

    async def main() -> None:
        fake = FakeProcesses()
        manager = JobManager(settings, processes=fake)
        jobs = [manager.submit("run", {}, [step("s", ["m"])], lane="model") for _ in range(2)]
        await until(lambda: len(fake.started) == 2, "both started")
        fake.finish(pid_of(jobs[0]))
        fake.finish(pid_of(jobs[1]))
        await until(lambda: all(j.state == "done" for j in jobs))

    asyncio.run(main())


def test_needs_missing_skips_step(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> Job:
        fake = FakeProcesses()
        manager = JobManager(settings, processes=fake)
        job = manager.submit("demo", {"n": 1}, [
            step("first", ["a"]),
            step("needs", ["never"], needs=[tmp_path, tmp_path / "missing.json"]),
            step("last", ["b", "arg with spaces"], needs=tmp_path),
        ], refs={"corpus": "c1"})
        assert job.state == "queued" and (settings.jobs_dir / f"{job.id}.json").is_file()
        assert manager.busy("corpus", "c1") is job and manager.busy("corpus", "c2") is None
        await until(lambda: len(fake.started) == 1)
        fake.finish(pid_of(job))
        await until(lambda: len(fake.started) == 2)
        fake.finish(pid_of(job, 2))
        await until(lambda: job.state == "done")
        assert fake.started == [["a"], ["b", "arg with spaces"]]
        return job

    job = asyncio.run(main())
    assert (job.state, job.exit_code, job.error, job.lane) == ("done", 0, None, "cpu")
    assert [(s.name, s.state, s.exit_code) for s in job.steps] == [
        ("first", "done", 0), ("needs", "skipped", None), ("last", "done", 0)]
    log = (settings.jobs_dir / f"{job.id}.log").read_text(encoding="utf-8")
    assert f"# skipped needs: {tmp_path / 'missing.json'} does not exist" in log and "never" not in log
    assert "'arg with spaces'" in log   # the command line, shell-quoted
    saved = Job.model_validate_json((settings.jobs_dir / f"{job.id}.json").read_text(encoding="utf-8"))
    assert saved == job


def test_failed_optional_step_warns(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> Job:
        fake = FakeProcesses()
        manager = JobManager(settings, processes=fake)
        job = manager.submit("demo", {}, [step("optional", ["x"], required=False), step("last", ["y"])])
        await until(lambda: len(fake.started) == 1)
        fake.finish(pid_of(job), 3)
        await until(lambda: len(fake.started) == 2)   # a failed step does not stop the next ones
        fake.finish(pid_of(job, 1))
        await until(lambda: job.state == "done")
        return job

    job = asyncio.run(main())
    assert (job.state, job.exit_code) == ("done", 0)
    assert job.warnings == ["optional failed (exit 3); see the log"]   # done, but not silently
    assert [(s.state, s.exit_code) for s in job.steps] == [("failed", 3), ("done", 0)]
    assert "# optional exit 3" in (settings.jobs_dir / f"{job.id}.log").read_text(encoding="utf-8")


def test_a_failed_required_step_fails_the_job(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> Job:
        fake = FakeProcesses()
        manager = JobManager(settings, processes=fake)
        job = manager.submit("demo", {}, [step("bad", ["x"]), step("next", ["y"])])
        await until(lambda: len(fake.started) == 1)
        fake.finish(pid_of(job), 5)
        await until(lambda: len(fake.started) == 2)
        fake.finish(pid_of(job, 1))
        await until(lambda: job.state != "running")
        return job

    job = asyncio.run(main())
    assert (job.state, job.exit_code) == ("failed", 5)
    assert [s.state for s in job.steps] == ["failed", "done"]


def test_a_command_that_cannot_start_fails_its_step(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> Job:
        manager = JobManager(settings, processes=FakeProcesses(fail_start=True))
        job = manager.submit("demo", {}, [step("nope", ["x"])])
        await until(lambda: job.state == "failed")
        return job

    job = asyncio.run(main())
    assert job.exit_code == 127
    assert "cannot start nope" in (settings.jobs_dir / f"{job.id}.log").read_text(encoding="utf-8")


def test_no_jobs_without_ev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EV", raising=False)

    async def main() -> None:
        with pytest.raises(Conflict, match=r"\$EV"):
            JobManager(Settings(), processes=FakeProcesses()).submit("demo", {}, [step("x", ["x"])])

    asyncio.run(main())


def test_cancel_queued_ends_at_once(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> Job:
        fake = FakeProcesses()
        manager = JobManager(settings, processes=fake)
        manager.submit("run", {}, [step("holds", ["h"])], lane="model")
        queued = manager.submit("run", {}, [step("never", ["n"])], lane="model")
        await until(lambda: len(fake.started) == 1)
        manager.cancel(queued.id)
        assert queued.state == "failed" and queued.error == "cancelled"   # at once
        return queued

    queued = asyncio.run(main())
    assert [s.state for s in queued.steps] == ["skipped"] and queued.started_at is None


def test_cancel_running_sends_term_and_skips_rest(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> tuple[Job, FakeProcesses]:
        fake = FakeProcesses()
        manager = JobManager(settings, processes=fake)
        job = manager.submit("run", {}, [step("sleep", ["s"]), step("after", ["a"])], lane="model")
        await until(lambda: len(fake.started) == 1)
        manager.cancel(job.id)
        await until(lambda: job.state != "running")
        return job, fake

    job, fake = asyncio.run(main())
    assert fake.signals == [(pid_of(job), "term")] and fake.started == [["s"]]
    assert (job.state, job.error) == ("failed", "cancelled")
    assert [s.state for s in job.steps] == ["failed", "skipped"] and job.steps[0].exit_code == -15


def _write_running(settings: Settings, pid: int, token: str | None, *, job_id: str, run: str) -> Job:
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    s = step("evidence run", ["python", "-m", "webapp.tool", "evidence", "run"])
    s.state, s.pid, s.pid_start = "running", pid, token
    job = Job(id=job_id, kind="run", lane="model", args={}, refs={"run": run}, state="running",
              created_at="2026-01-01T00:00:00Z", steps=[s, step("next", ["true"])])
    (settings.jobs_dir / f"{job.id}.json").write_text(job.model_dump_json(), encoding="utf-8")
    return job


def test_restart_keeps_live_orphan_and_watches_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs_module, "ORPHAN_POLL_S", 0)
    settings = settings_in(tmp_path)
    live = _write_running(settings, 4242, "tick4242", job_id="20260101T000000-run-aaaaaa", run="cascade~c1")

    async def main() -> tuple[Job, bool]:
        fake = FakeProcesses()
        fake.set_alive(4242, "tick4242")
        manager = JobManager(settings, processes=fake)
        manager.load()
        kept = manager.get(live.id)
        assert (kept.state, kept.orphaned) == ("running", True)
        assert manager.busy("run", "cascade~c1") is kept
        queued = manager.submit("run", {}, [step("waits", ["w"])], lane="model")
        for _ in range(50):
            await asyncio.sleep(0)
        waited = queued.state == "queued" and not fake.started    # the orphan holds the model lane
        fake.set_alive(4242, None)                                # its process ends
        await until(lambda: kept.state == "failed", "orphan noticed to be gone")
        await until(lambda: len(fake.started) == 1, "the lane is free again")
        fake.finish(pid_of(queued))
        await until(lambda: queued.state == "done")
        return kept, waited

    kept, waited = asyncio.run(main())
    assert waited
    assert "exit status unknown" in (kept.error or "")
    assert kept.steps[0].state == "failed" and kept.steps[1].state == "skipped"


def test_cancel_an_orphan_sends_term(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs_module, "ORPHAN_POLL_S", 0)
    settings = settings_in(tmp_path)
    live = _write_running(settings, 4242, "tick4242", job_id="20260101T000000-run-aaaaaa", run="cascade~c1")

    async def main() -> tuple[Job, FakeProcesses]:
        fake = FakeProcesses()
        fake.set_alive(4242, "tick4242")
        manager = JobManager(settings, processes=fake)
        manager.load()
        kept = manager.get(live.id)
        manager.cancel(kept.id)
        await until(lambda: kept.state == "failed")
        return kept, fake

    kept, fake = asyncio.run(main())
    assert fake.signals == [(4242, "term")] and kept.error == "cancelled"


def test_restart_fails_dead_job(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)
    reused = _write_running(settings, 4242, "old-token", job_id="20260101T000000-run-bbbbbb", run="cascade~c2")
    queued = reused.model_copy(deep=True, update={"id": "20260101T000000-run-cccccc", "state": "queued"})
    (settings.jobs_dir / f"{queued.id}.json").write_text(queued.model_dump_json(), encoding="utf-8")
    (settings.jobs_dir / "garbage.json").write_text("{not json", encoding="utf-8")

    fake = FakeProcesses()
    fake.set_alive(4242, "a-different-start-time")   # the pid was reused
    manager = JobManager(settings, processes=fake)
    manager.load()
    lost = manager.get(reused.id)
    assert lost.state == "failed" and "server stopped" in (lost.error or "")
    assert [s.state for s in lost.steps] == ["failed", "skipped"] and lost.orphaned is False
    assert manager.get(queued.id).state == "failed"
    assert json.loads((settings.jobs_dir / f"{reused.id}.json").read_text())["state"] == "failed"
    assert manager.busy("run", "cascade~c2") is None


def test_jobs_survive_a_restart_and_the_log_tail(tmp_path: Path) -> None:
    settings = settings_in(tmp_path)

    async def main() -> Job:
        fake = FakeProcesses()
        manager = JobManager(settings, processes=fake)
        job = manager.submit("demo", {"a": 1}, [step("count", ["c"])])
        await until(lambda: len(fake.started) == 1)
        fake.finish(pid_of(job))
        await until(lambda: job.state == "done")
        with open(settings.jobs_dir / f"{job.id}.log", "ab") as fh:   # more output after the job
            fh.write("".join(f"{n}\n" for n in range(500)).encode())
        return job

    done = asyncio.run(main())
    manager = JobManager(settings, processes=FakeProcesses())
    manager.load()
    assert manager.get(done.id) == done
    assert [j.id for j in manager.list()] == [done.id]
    assert manager.tail(done.id, 2) == "498\n499\n"
    assert manager.tail(done.id, 10_000).startswith("$ ")


def test_shutdown_kills_after_grace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs_module, "STOP_GRACE_S", 0)
    settings = settings_in(tmp_path)

    async def main() -> tuple[Job, FakeProcesses]:
        fake = FakeProcesses(ignore_term=True)
        manager = JobManager(settings, processes=fake)
        job = manager.submit("run", {}, [step("stubborn", ["s"])], lane="model")
        await until(lambda: len(fake.started) == 1)
        await manager.shutdown()
        return job, fake

    job, fake = asyncio.run(main())
    assert fake.signals == [(pid_of(job), "term"), (pid_of(job), "kill")]
    assert job.state == "failed" and job.error == "the server stopped"
