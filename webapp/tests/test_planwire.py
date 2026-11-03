"""The plan page's real parts (webapp/planwire.py): create_app wires the planner model, the saved templates, the plan
run, its result and the links review."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from evidence import engine, stages
from evidence.planner import confirm_all
from evidence.tests.conftest import make_corpus, provider_of
from evidence.tests.test_plan_run import fake_model, make_plan
from modelcall.dspy_lm import RecordedLM
from modelcall.pins import ORCH_ALIAS
from webapp.app import create_app
from webapp.evplan import PlanBackend
from webapp.planwire import PLAN_CORPUS, PlanRuns, default_backend
from webapp.settings import Settings


def page_plan():
    """The test plan as the planner writes it, minus its line that fails at run time (this test wants a clean run)."""
    plan = make_plan()
    return plan.model_copy(update={"lines": [x for x in plan.lines if x.id != "l3"]})


@pytest.fixture(autouse=True)
def clean_registry():
    with stages.registered():
        yield


def test_the_default_backend_wires_every_part(tmp_path):
    be = default_backend(Settings(EV=tmp_path))  # type: ignore[call-arg]
    assert {"effect", "oversell", "rank"} <= set(be.templates) and "SELECT" in be.templates["effect"]
    lm = be.model()
    assert isinstance(lm, RecordedLM) and lm.alias == ORCH_ALIAS
    assert be.run.__self__.__class__ is PlanRuns and be.result.__self__ is be.run.__self__  # type: ignore[attr-defined]


def test_without_a_corpus_the_run_answers_501(tmp_path, monkeypatch):
    monkeypatch.delenv(PLAN_CORPUS, raising=False)
    runs = PlanRuns(Settings(EV=tmp_path))  # type: ignore[call-arg]
    be = PlanBackend(clarify=lambda q: [], propose=lambda q, a: (page_plan(), {}), critic=lambda p: confirm_all(p, "x"),
                     run=runs.run, result=runs.result, links=runs.links)
    with TestClient(create_app(Settings(EV=tmp_path), plan_backend=be)) as c:  # type: ignore[call-arg]
        pid = c.post("/api/ev/plan", json={"question": "Does it help?"}).json()["id"]
        r = c.post(f"/api/ev/plan/{pid}/run", json={})
        assert r.status_code == 501 and PLAN_CORPUS in r.json()["detail"]


def test_a_plan_runs_from_the_page_and_its_result_and_links_review_come_back(tmp_path, monkeypatch):
    monkeypatch.setenv(PLAN_CORPUS, str(make_corpus(tmp_path / "corpus")))
    monkeypatch.setattr(engine, "default_provider", provider_of(fake_model([])))
    settings = Settings(EV=tmp_path / "ev")  # type: ignore[call-arg]
    runs = PlanRuns(settings)
    be = PlanBackend(clarify=lambda q: [], propose=lambda q, a: (page_plan(), {}), critic=lambda p: confirm_all(p, "x"),
                     run=runs.run, result=runs.result, links=runs.links)
    with TestClient(create_app(settings, plan_backend=be)) as c:
        pid = c.post("/api/ev/plan", json={"question": "Does it help?"}).json()["id"]
        rid = c.post(f"/api/ev/plan/{pid}/run", json={}).json()["run"]
        runs.threads[rid].join(timeout=600)
        assert rid not in runs.errors, runs.errors.get(rid)
        result = c.get(f"/api/ev/plan/{pid}/result").json()
        assert result["status"] == "done"
        lines = {x["id"]: x for x in result["lines"]}
        assert lines["l1"]["status"] == "done" and result["answer"]["missing"] == []
        assert result["labels"] and result["reruns"]
        review = c.post(f"/api/ev/run/{rid}/links", json={"accepted": [], "rejected": ["a -> b"]}).json()
        assert review["review"]["rejected"] == ["a -> b"] and {x["id"] for x in review["lines"]} == set(lines)
        assert (settings.ev_runs_dir / rid / "links_review.json").is_file()


def test_a_run_with_no_seal_and_no_live_thread_says_it_stopped(tmp_path):
    settings = Settings(EV=tmp_path)  # type: ignore[call-arg]
    (settings.ev_runs_dir / "plan-x").mkdir(parents=True)
    out = PlanRuns(settings).result("plan-x")
    assert out["status"] == "done" and out["answer"]["text"] == "failed: run stopped"
