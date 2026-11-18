"""The system API (webapp/evsystem.py): domains with their questions and plan states, the four rows of a plan run
(find, pull, combine, answer) and a paper with the run's items marked. Read-only; no model is called."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence.kindtext import RULE_TEXT
from evidence.readable import LINES
from evidence.readable.rules.common import CHECK_OK
from synth3.questions import load_questions
from synth3.sheetfacts import load_folder
from synth3.spec import load_spec
from synth3.tests.systemrun import FACT_REPLY, demo_plan, make_system_run
from webapp.app import create_app
from webapp.evplan import PlanBackend
from webapp.settings import Settings
from webapp.tests.test_evreview import review_root  # noqa: F401  (fixture)


def client(tmp_path: Path, review_root: Path) -> TestClient:
    return TestClient(create_app(Settings(EV=tmp_path / "ev", SYNTH3_DATA=review_root),  # type: ignore[call-arg]
                                 plan_backend=PlanBackend()))


@pytest.fixture
def system_runs(tmp_path, review_root) -> dict[str, str]:
    spec = load_spec("demo", review_root)
    qs = load_questions("demo", spec, review_root / "questions")
    folder = load_folder(review_root / "built" / "demo" / "s1")
    runs = tmp_path / "ev" / "runs"
    q = qs.get("d01")
    make_system_run(runs, folder, q, demo_plan(spec, q), writer_reply=FACT_REPLY)
    e = q.model_copy(update={"kind": "effect", "id": "d01e"})
    make_system_run(runs, folder, e, demo_plan(spec, e, "effect"), run_id="d01e")
    lines = q.model_copy(update={"id": "d01l"})
    make_system_run(runs, folder, lines, demo_plan(spec, lines, "lines"), run_id="d01l")
    return {"written": "d01", "effect": "d01e", "lines": "d01l"}


def test_domains_list_folders_questions_and_plan_states(review_root, tmp_path):
    rows = client(tmp_path, review_root).get("/api/ev/system/domains").json()
    demo = next(r for r in rows if r["domain"] == "demo")
    assert demo["seeds"] == [1] and [q["id"] for q in demo["questions"]] == ["d01", "d02", "d03"]
    assert {q["plan"] for q in demo["questions"]} == {"missing"}


def test_a_question_file_that_is_missing_gives_the_error(review_root, tmp_path):
    (review_root / "questions" / "demo.yaml").unlink()
    demo = next(r for r in client(tmp_path, review_root).get("/api/ev/system/domains").json()
                if r["domain"] == "demo")
    assert demo["questions"] == [] and demo["error"]


def test_plan_states_follow_the_batch_plan(review_root, tmp_path):
    from synth3.tests.systemrun import write_demo_plans
    spec = load_spec("demo", review_root)
    qs = load_questions("demo", spec, review_root / "questions")
    write_demo_plans(review_root / "plans", qs, spec, confirmed=None)
    plans = review_root / "plans" / "demo"
    shutil.copy(plans / "d02.json", plans / "d03.json")   # d03 now holds d02's question: stale
    (plans / "d01.json").write_text(
        (plans / "d01.json").read_text(encoding="utf-8").replace('"confirmed_by": null', '"confirmed_by": "aditya"'),
        encoding="utf-8")
    write = {q["id"]: q["plan"] for r in client(tmp_path, review_root).get("/api/ev/system/domains").json()
             if r["domain"] == "demo" for q in r["questions"]}
    assert write["d02"] == "draft" and write["d03"] == "stale" and write["d01"] in ("confirmed", "draft")


def test_the_four_rows_of_a_written_run(system_runs, tmp_path, review_root):
    s = client(tmp_path, review_root).get(f"/api/ev/system/runs/{system_runs['written']}/steps").json()
    assert s["status"] == "done" and s["answer_by"] == "written"
    assert s["pull"]["count"] == len(s["pull"]["facts"]) >= 1 and s["find"]["count"] >= 1
    assert s["combine"]["rule"].startswith("A model (orch-model) wrote the answer")
    assert s["answer"]["lines"][0]["facts"] == [1] and s["combine"]["rows"][0]["facts"] == [1]


def test_an_effect_run_shows_the_kind_rule(system_runs, tmp_path, review_root):
    s = client(tmp_path, review_root).get(f"/api/ev/system/runs/{system_runs['effect']}/steps").json()
    assert s["combine"]["rule"] == RULE_TEXT["effect"]
    assert s["answer"]["lines"][0]["text"].startswith("Targeted therapy against Standard care on Response rate: ")


def test_a_paper_shows_the_run_items_marked(system_runs, tmp_path, review_root):
    c = client(tmp_path, review_root)
    fact = c.get(f"/api/ev/system/runs/{system_runs['written']}/steps").json()["pull"]["facts"][0]
    page = c.get(f"/api/ev/system/runs/{system_runs['written']}/papers/{fact['paper']}").json()
    assert page["text"] and any(fact["item"] in (seg.get("marks") or []) for seg in page["segments"])


def test_a_running_run_says_running(system_runs, tmp_path, review_root):
    (tmp_path / "ev" / "runs" / system_runs["written"] / "manifest.json").unlink()
    s = client(tmp_path, review_root).get(f"/api/ev/system/runs/{system_runs['written']}/steps").json()
    assert s["status"] == "running" and s["pull"]["facts"] == [] and s["answer"]["lines"] == []


def test_a_failed_seal_says_failed_with_its_reason(system_runs, tmp_path, review_root):
    from evidence import seal as sealing
    run = tmp_path / "ev" / "runs" / system_runs["written"]
    sha = json.loads((run / "manifest.json").read_text(encoding="utf-8"))["corpus_manifest_sha256"]
    sealing.seal(run, sha, status="failed", error="RuntimeError: disk full")
    s = client(tmp_path, review_root).get(f"/api/ev/system/runs/{system_runs['written']}/steps").json()
    assert s["status"] == "failed" and s["error"] == "RuntimeError: disk full"
    assert s["pull"]["facts"] == [] and s["combine"]["rows"] == [] and s["answer"]["lines"] == []


def test_a_failed_writer_call_says_failed_with_its_reason(tmp_path, review_root):
    spec = load_spec("demo", review_root)
    q = load_questions("demo", spec, review_root / "questions").get("d01")
    run = make_system_run(tmp_path / "ev" / "runs", load_folder(review_root / "built" / "demo" / "s1"), q,
                          demo_plan(spec, q), writer_reply=lambda p: RuntimeError("gateway down"))
    written = json.loads((run / "written-answer.json").read_text(encoding="utf-8"))
    assert set(written) == {"failed"}
    s = client(tmp_path, review_root).get(f"/api/ev/system/runs/{run.name}/steps").json()
    assert s["status"] == "failed" and s["error"] == f"the written answer's model call failed: {written['failed']}"
    assert s["pull"]["facts"] == [] and s["combine"]["rows"] == [] and s["answer"]["lines"] == []


@pytest.mark.parametrize("path", ["/api/ev/system/runs/..%2F..%2Fetc/steps", "/api/ev/system/runs/-x/steps",
                                  "/api/ev/system/runs/nope/steps", "/api/ev/system/runs/d01/papers/S999",
                                  "/api/ev/system/runs/d01/papers/..%2Fmanifest"])
def test_bad_ids_are_refused(system_runs, tmp_path, review_root, path):
    assert client(tmp_path, review_root).get(path).status_code in (400, 404, 422)


def test_the_program_downloads_and_rebuilds_the_answer(system_runs, tmp_path, review_root):
    c = client(tmp_path, review_root)
    for rid in (system_runs["written"], system_runs["effect"]):
        r = c.get(f"/api/ev/system/runs/{rid}/program")
        assert r.status_code == 200 and r.headers["content-disposition"] == f'attachment; filename="{rid}-answer.py"'
        assert r.headers["content-type"] == "text/x-python; charset=utf-8"
        path = tmp_path / f"{rid}-answer.py"; path.write_bytes(r.content)
        done = subprocess.run([sys.executable, "-I", "-S", str(path)], capture_output=True, timeout=120)
        assert done.returncode == 0 and done.stdout.decode("utf-8").splitlines()[-1] == CHECK_OK
        assert c.get(f"/api/ev/system/runs/{rid}/steps").json()["program_refused"] is None


def test_a_lines_run_has_no_program(system_runs, tmp_path, review_root):
    c = client(tmp_path, review_root)
    assert c.get(f"/api/ev/system/runs/{system_runs['lines']}/steps").json()["program_refused"] == LINES
    r = c.get(f"/api/ev/system/runs/{system_runs['lines']}/program")
    assert r.status_code == 409 and r.json()["detail"] == LINES


def test_a_running_run_has_no_program_and_nothing_is_written(system_runs, tmp_path, review_root):
    run = tmp_path / "ev" / "runs" / system_runs["written"]
    (run / "manifest.json").unlink()
    before = sorted(str(p) for p in run.rglob("*"))
    c = client(tmp_path, review_root)
    refused = c.get(f"/api/ev/system/runs/{system_runs['written']}/steps").json()["program_refused"]
    assert refused and refused.startswith("the run is not complete")
    r = c.get(f"/api/ev/system/runs/{system_runs['written']}/program")
    assert r.status_code == 409 and r.json()["detail"] == refused
    assert sorted(str(p) for p in run.rglob("*")) == before


def test_a_bad_id_gets_no_program(system_runs, tmp_path, review_root):
    assert client(tmp_path, review_root).get("/api/ev/system/runs/..%2Fx/program").status_code in (400, 404, 422)
