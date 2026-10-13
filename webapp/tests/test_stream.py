"""The live run stream (`/api/runs/{id}/stream`): records as events.jsonl grows, then done."""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

from fastapi.testclient import TestClient

from agent.canonical import write_json
from agent.concept import concept_sha256
from agent.rundir import RunDir
from agent.tests.conftest import fixture
from agent.tests.runs import Driver
from agent.tests.test_rundir import SETTINGS
from webapp.app import create_app

from .world import World


def events(response: Any) -> list[dict[str, Any]]:
    """Parse a text/event-stream body into [{event, id, data}]."""
    out, current = [], {}
    for line in response.iter_lines():
        if not line:
            if current:
                out.append(current)
            current = {}
        elif line.startswith(":"):
            continue
        else:
            name, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            current[name] = current[name] + "\n" + value if name == "data" and name in current else value
    if current:
        out.append(current)
    return out


def test_a_finished_run_streams_every_record_then_done(client: TestClient, world: World) -> None:
    with client.stream("GET", "/api/runs/research-r1/stream") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        got = events(response)
    lines = world.research.run.events.read_text(encoding="utf-8").splitlines()
    records = [e for e in got if e.get("event") == "record"]
    assert [json.loads(e["data"]) for e in records] == [json.loads(line) for line in lines]
    assert [e["id"] for e in records] == [str(n) for n in range(1, len(lines) + 1)]
    done = got[-1]
    assert done["event"] == "done" and json.loads(done["data"]) == {"run_id": "research-r1", "records": len(lines),
                                                                      "exit_status": "submitted"}


def test_reconnect_resumes_after_the_last_event_id(client: TestClient) -> None:
    with client.stream("GET", "/api/runs/research-r1/stream", headers={"Last-Event-ID": "15"}) as response:
        got = events(response)
    assert [e["id"] for e in got if e.get("event") == "record"] == ["16", "17", "18"]


def test_unknown_run(client: TestClient) -> None:
    assert client.get("/api/runs/nope/stream").status_code == 404


def test_a_live_run_streams_as_it_grows(fresh: World) -> None:
    """A run that writes its records while the stream is open: each arrives, then done at answer.json."""
    concept = fixture("concept_graph.json")
    run = RunDir.create(fresh.runs, "live-r1", concept, corpus_manifest=fresh.manifest, **SETTINGS)

    def agent() -> None:
        driver = Driver(run, fresh.corpus, fresh.manifest)
        for step in (1, 2, 3):
            time.sleep(0.15)
            driver.model_call(step)
        driver.model_call(4, final_answer=True)
        driver.close()
        time.sleep(0.15)
        write_json(run.answer, {"concept_sha256": concept_sha256(concept), "kind": "graph", "rows": []})

    writer = threading.Thread(target=agent)
    with TestClient(create_app(fresh.settings)) as c:
        assert c.get("/api/runs/live-r1").json()["summary"]["live"] is True
        writer.start()
        t0 = time.monotonic()
        with c.stream("GET", "/api/runs/live-r1/stream") as response:
            got = events(response)
        writer.join()
        assert time.monotonic() - t0 < 10
        summary = c.get("/api/runs/live-r1").json()["summary"]
    assert [json.loads(e["data"])["step_id"] for e in got if e.get("event") == "record"] == [1, 2, 3, 4]
    assert got[-1]["event"] == "done" and json.loads(got[-1]["data"])["exit_status"] == "submitted"
    assert (summary["live"], summary["exit_status"]) == (False, "submitted")


def test_a_stalled_run_ends_as_incomplete(fresh: World) -> None:
    run = RunDir.create(fresh.runs, "stalled-r1", fixture("concept_graph.json"), corpus_manifest=fresh.manifest,
                        **SETTINGS)
    driver = Driver(run, fresh.corpus, fresh.manifest)
    driver.model_call(1)
    driver.close()
    old = time.time() - 3600
    os.utime(run.events, (old, old))
    with TestClient(create_app(fresh.settings)) as c:
        with c.stream("GET", "/api/runs/stalled-r1/stream") as response:
            got = events(response)
        summary = c.get("/api/runs/stalled-r1").json()["summary"]
    assert [e["event"] for e in got] == ["record", "done"]
    assert json.loads(got[-1]["data"])["exit_status"] == "incomplete"
    assert (summary["live"], summary["exit_status"], summary["verify"]) == (False, "incomplete", "failed")


def test_a_cut_run_is_not_live(fresh: World) -> None:
    from agent.batch import mark_cut

    # Not q01's picked concept: the question id comes from the batch runner's run id.
    run = RunDir.create(fresh.runs, "q01-claim_on-r1-a1", fixture("concept_table.json"),
                        corpus_manifest=fresh.manifest, **SETTINGS)
    assert mark_cut(run, "job_time_limit", {"phase": "research"})
    with TestClient(create_app(fresh.settings)) as c:
        summary = c.get("/api/runs/q01-claim_on-r1-a1").json()["summary"]
    assert (summary["live"], summary["exit_status"], summary["qid"]) == (False, "cut", "q01")
