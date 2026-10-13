"""Jobs: the manager with fake commands, and the endpoints that start them with a fake interpreter."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from webapp.app import create_app
from webapp.jobs import JobManager, step
from webapp.models import Job
from webapp.settings import Settings

from .test_stream import events
from .world import World

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the fake interpreter is a #! script (POSIX)")

FAKE = '''#!{python}
"""Stands in for `python -m <module> ...`: logs its argv; `agent.cli run` makes a run directory."""
import json, os, sys, time
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps(args) + "\\n")
print("fake", *args[1:4], flush=True)
if args[1] == "gold.cli" and os.environ.get("FAKE_SLEEP"):
    time.sleep(float(os.environ["FAKE_SLEEP"]))
if args[1:3] == ["agent.cli", "run"]:
    run = Path(args[args.index("--runs-root") + 1]) / args[args.index("--run-id") + 1]
    run.mkdir(parents=True)
    (run / "config.json").write_text("{{}}")
    (run / "answer.json").write_text("{{}}")
if args[1:3] == ["agent.cli", "graph"]:
    (Path(args[3]) / "graph.json").write_text("{{}}")
sys.exit(2 if args[1] == "scoring.cli" else 0)  # no `score run` yet: an optional step that fails
'''


@pytest.fixture
def fake_python(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "fake-python"
    path.write_text(FAKE.format(python=sys.executable), encoding="utf-8")
    path.chmod(0o755)
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "fake.log"))
    return path


def calls(tmp_path: Path) -> list[list[str]]:
    log = tmp_path / "fake.log"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def wait(client: TestClient, job_id: str, timeout: float = 30) -> dict[str, Any]:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["state"] not in ("queued", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


# --- the manager ------------------------------------------------------------------------------------------

def py(code: str, *args: str) -> list[str]:
    return [sys.executable, "-c", code, *args]


async def finished(manager: JobManager, job: Job, timeout: float = 20) -> Job:
    end = time.monotonic() + timeout
    while job.state in ("queued", "running"):
        assert time.monotonic() < end, "job did not finish"
        await asyncio.sleep(0.02)
    return job


def test_steps_run_in_order_with_needs_and_optional_failures(tmp_path: Path) -> None:
    settings = Settings(runs=tmp_path / "runs", WEBAPP_POLL_S=0.02)

    async def main() -> Job:
        manager = JobManager(settings)
        job = manager.submit("demo", {"n": 1}, [
            step("hello", py("print('hello from step 1')")),
            step("optional", py("import sys; print('broken'); sys.exit(3)"), required=False),
            step("needs", py("print('never')"), needs=[tmp_path, tmp_path / "missing.json"]),
            step("last", py("import sys; print('last', sys.argv[1])", "arg with spaces"), needs=tmp_path),
        ])
        assert job.state == "queued" and (settings.jobs_dir / f"{job.id}.json").is_file()
        return await finished(manager, job)

    job = asyncio.run(main())
    assert (job.state, job.exit_code, job.error) == ("done", 0, None)
    assert job.warnings == ["optional failed (exit 3); see the log"]  # done, but not silently
    assert [(s.name, s.state, s.exit_code) for s in job.steps] == [
        ("hello", "done", 0), ("optional", "failed", 3), ("needs", "skipped", None), ("last", "done", 0)]
    log = (settings.jobs_dir / f"{job.id}.log").read_text(encoding="utf-8")
    assert "hello from step 1\n" in log and "# optional exit 3" in log and "never" not in log
    assert f"# skipped needs: {tmp_path / 'missing.json'} does not exist" in log
    assert "last arg with spaces" in log and "'arg with spaces'" in log  # the command line, shell-quoted
    saved = Job.model_validate_json((settings.jobs_dir / f"{job.id}.json").read_text(encoding="utf-8"))
    assert saved == job


def test_a_failed_required_step_fails_the_job(tmp_path: Path) -> None:
    settings = Settings(runs=tmp_path / "runs")

    async def main() -> Job:
        manager = JobManager(settings)
        return await finished(manager, manager.submit("demo", {}, [step("bad", py("import sys; sys.exit(5)")),
                                                                    step("next", py("pass"))]))

    job = asyncio.run(main())
    assert (job.state, job.exit_code) == ("failed", 5)
    assert [s.state for s in job.steps] == ["failed", "done"]  # later steps still run


def test_one_job_of_a_kind_at_a_time(tmp_path: Path) -> None:
    settings = Settings(runs=tmp_path / "runs")
    trace = tmp_path / "trace.txt"
    code = "import sys, time; f = open(sys.argv[1], 'a'); f.write('start\\n'); f.flush(); time.sleep(0.3); f.write('end\\n')"

    async def main() -> list[Job]:
        manager = JobManager(settings)
        jobs = [manager.submit("run", {}, [step("s", py(code, str(trace)))]) for _ in range(3)]
        assert [j.state for j in jobs] == ["queued"] * 3
        for job in jobs:
            await finished(manager, job)
        return jobs

    jobs = asyncio.run(main())
    assert {j.state for j in jobs} == {"done"}
    assert trace.read_text().split() == ["start", "end"] * 3  # never interleaved
    assert jobs[0].ended_at <= jobs[1].started_at and jobs[1].ended_at <= jobs[2].started_at


def test_cancel(tmp_path: Path) -> None:
    settings = Settings(runs=tmp_path / "runs")

    async def main() -> tuple[Job, Job]:
        manager = JobManager(settings)
        running = manager.submit("run", {}, [step("sleep", py("import time; time.sleep(30)")),
                                             step("after", py("print('after')"))])
        queued = manager.submit("run", {}, [step("never", py("print('never')"))])
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
    settings = Settings(runs=tmp_path / "runs")

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


# --- the endpoints ----------------------------------------------------------------------------------------

def test_start_a_run_with_its_post_steps(fresh: World, fake_python: Path, tmp_path: Path) -> None:
    settings = fresh.with_settings(WEBAPP_PYTHON=str(fake_python))
    with TestClient(create_app(settings)) as c:
        response = c.post("/api/runs", json={"qid": "q01", "condition": "claim_off", "seed": 7, "temperature": 0.5,
                                             "steps": 10, "sandbox": "unsandboxed"})
        assert response.status_code == 202, response.text
        job = response.json()
        assert job["kind"] == "run" and job["run_id"].startswith("q01-claim_off-s7-web") and job["qid"] == "q01"
        job = wait(c, job["id"])
        with c.stream("GET", f"/api/jobs/{job['id']}/log") as stream:
            log = events(stream)
        listed = c.get("/api/jobs").json()
    assert (job["state"], job["exit_code"]) == ("done", 0), job
    assert [(s["name"], s["state"]) for s in job["steps"]] == [
        ("run", "done"), ("attach", "done"), ("verify", "done"), ("pairs", "done"), ("graph", "done"),
        ("export-prov", "done"), ("score", "failed")]  # score is optional: the job is still done
    run_dir = fresh.runs / job["run_id"]
    argv = calls(tmp_path)
    assert [a[1:3] for a in argv] == [["agent.cli", "run"], ["agent.cli", "attach"], ["agent.cli", "verify"],
                                      ["agent.cli", "pairs"], ["agent.cli", "graph"], ["agent.cli", "export-prov"],
                                      ["scoring.cli", "run"]]
    run = argv[0]
    for flag, value in (("--concept", str(fresh.root / "concepts" / "q01" / "concept.json")), ("--run-id", job["run_id"]),
                        ("--runs-root", str(fresh.runs)), ("--corpus", str(fresh.corpus)), ("--condition", "claim_off"),
                        ("--temperature", "0.5"), ("--seed", "7"), ("--steps", "10"), ("--sandbox", "unsandboxed")):
        assert run[run.index(flag) + 1] == value, flag
    assert "--tokens" not in run and argv[1][3] == str(run_dir) and argv[4][-1] == str(fresh.manifest)
    lines = [e["data"] for e in log if e.get("event") == "line"]
    assert lines[0].startswith("$ ") and "agent.cli run" in lines[0]
    assert any(line.startswith("fake agent.cli run") for line in lines)
    assert json.loads(log[-1]["data"])["state"] == "done"
    assert [j["id"] for j in listed] == [job["id"]]
    with TestClient(create_app(settings)) as c:  # a restarted server still lists it
        assert c.get(f"/api/jobs/{job['id']}").json()["state"] == "done"


def test_a_claim_on_run_has_no_attach_step(fresh: World, fake_python: Path) -> None:
    with TestClient(create_app(fresh.with_settings(WEBAPP_PYTHON=str(fake_python)))) as c:
        job = wait(c, c.post("/api/runs", json={"qid": "q01", "condition": "claim_on", "seed": 1}).json()["id"])
    assert "attach" not in [s["name"] for s in job["steps"]]
    assert job["steps"][0]["argv"][job["steps"][0]["argv"].index("--sandbox") + 1] == "landlock"


def test_run_requests_that_cannot_start(fresh: World, fake_python: Path) -> None:
    with TestClient(create_app(fresh.with_settings(WEBAPP_PYTHON=str(fake_python)))) as c:
        assert c.post("/api/runs", json={"condition": "claim_on"}).status_code == 400  # no qid, no concept
        assert c.post("/api/runs", json={"qid": "q01", "concept_path": "x.json"}).status_code == 400
        assert c.post("/api/runs", json={"qid": "q02"}).status_code == 409  # nothing picked for q02
        assert c.post("/api/runs", json={"qid": "q01", "condition": "claim_maybe"}).status_code == 422
        other = c.post("/api/runs", json={"concept_path": "research-r1/concept.json", "condition": "claim_on"})
        assert other.status_code == 202 and other.json()["run_id"].startswith("research-r1-claim_on")
        wait(c, other.json()["id"])
    with TestClient(create_app(fresh.with_settings(corpus=None, WEBAPP_PYTHON=str(fake_python)))) as c:
        assert c.post("/api/runs", json={"qid": "q01"}).status_code == 409  # no corpus


def test_propose_and_gold_jobs(fresh: World, fake_python: Path, tmp_path: Path) -> None:
    with TestClient(create_app(fresh.with_settings(WEBAPP_PYTHON=str(fake_python)))) as c:
        assert c.post("/api/questions/q01/concepts/propose", json={}).status_code == 409  # already proposed
        assert c.post("/api/questions/q99/concepts/propose", json={}).status_code == 404
        job = c.post("/api/questions/q02/concepts/propose", json={"temperature": 0.5, "seed": 3}).json()
        assert (job["kind"], job["qid"], job["args"]) == ("concepts", "q02", {"qid": "q02", "temperature": 0.5, "seed": 3})
        assert wait(c, job["id"])["state"] == "done"
        gold = c.post("/api/gold/q02/build").json()
        assert wait(c, gold["id"])["state"] == "done"
    propose, build = calls(tmp_path)
    assert propose[1:5] == ["agent.cli", "concepts", "propose", "q02"]
    assert propose[propose.index("--question") + 1].startswith("What kinds of attacks")
    assert propose[propose.index("--root") + 1] == str(fresh.root / "concepts")
    assert (propose[propose.index("--temperature") + 1], propose[propose.index("--seed") + 1]) == ("0.5", "3")
    assert build[1:] == ["gold.cli", "build", "q02"]


def test_a_running_gold_build_shows_and_can_be_cancelled(fresh: World, fake_python: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_SLEEP", "30")
    (fresh.root / "gold-data" / "q02" / "key.draft.json").unlink()
    (fresh.root / "gold-data" / "q02" / "doc.json").unlink()
    with TestClient(create_app(fresh.with_settings(WEBAPP_PYTHON=str(fake_python)))) as c:
        job = c.post("/api/gold/q02/build").json()
        assert c.post("/api/gold/q02/build").status_code == 409  # one build per question at a time
        end = time.monotonic() + 10
        while c.get(f"/api/jobs/{job['id']}").json()["state"] != "running" and time.monotonic() < end:
            time.sleep(0.05)
        q02 = c.get("/api/questions").json()[1]
        assert q02["gold"]["status"] == "building"
        assert c.post(f"/api/jobs/{job['id']}/cancel").json()["id"] == job["id"]
        job = wait(c, job["id"])
        assert c.post("/api/jobs/nope/cancel").status_code == 404
        assert c.get("/api/jobs/nope/log").status_code == 404
    assert (job["state"], job["error"]) == ("failed", "cancelled")
