"""The plan API (webapp/evplan.py) with a fake planner: one test per route."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence.plan import Decision, EvidenceLine, Plan, WordList
from evidence.planner import confirm_all
from webapp.app import create_app
from webapp.evplan import PlanBackend
from webapp.settings import Settings


def make_plan(question: str, clar: list[dict[str, str]]) -> Plan:
    return Plan(question=question, field="cs", main_rule="majority",
                words=WordList(things={"a": ["a"]}, cues=[], written_by="fake", ontology_names={}),
                lines=[EvidenceLine(id="l1", question="Does it help?", query="SELECT ?x WHERE {?x a ?y}", template=None),
                       EvidenceLine(id="oversell", question="Oversold?", query="SELECT ?x WHERE {?x a ?y}",
                                    template="oversell", removable=False)],
                decisions=[Decision(id="d1", type="threshold", value="0.01", reason="noise"),
                           Decision(id="d2", type="include", value="all", reason="small")],
                clarifications=clar)


def flag_first(plan: Plan) -> Plan:
    d = plan.decisions[0].model_copy(update={"flagged": True, "flag_reason": "maybe too small"})
    return plan.model_copy(update={"decisions": [d, *plan.decisions[1:]]})


class Fake:
    def __init__(self, ask: bool = False) -> None:
        self.ask = ask
        self.ran: list[Plan] = []
        self.reviewed: list[tuple] = []

    def backend(self) -> PlanBackend:
        def run(plan: Plan, folder: Path | None) -> str:
            self.ran.append(plan)
            return "run-1"

        def links(rid: str, accepted: list[str], rejected: list[str]) -> dict:
            self.reviewed.append((rid, accepted, rejected))
            return {"reruns": [{"setting": "threshold", "flips": True}]}

        clar = [{"question": "Better at what?", "options": ["accuracy", "speed"]}] if self.ask else []
        return PlanBackend(clarify=lambda q: clar, propose=make_plan, critic=flag_first, run=run, links=links)


@pytest.fixture
def world(tmp_path):
    fake = Fake()
    with TestClient(create_app(Settings(EV=tmp_path), plan_backend=fake.backend())) as c:  # type: ignore[call-arg]
        yield c, fake, tmp_path


H = {"X-Requested-With": "test"}  # the guard wants JSON or this header on a write


def start(c, q="Does it help?"):
    return c.post("/api/ev/plan", json={"question": q}).json()


def test_start_returns_the_plan_with_flags(world):
    c, _, _ = world
    r = start(c)
    assert r["plan"]["decisions"][0]["flagged"] and r["clarifications"] == [] and r["id"]


def test_questions_first_then_clarify(tmp_path):
    fake = Fake(ask=True)
    with TestClient(create_app(Settings(EV=tmp_path), plan_backend=fake.backend())) as c:  # type: ignore[call-arg]
        r = start(c)
        assert r["plan"] is None and r["clarifications"][0]["options"] == ["accuracy", "speed"]
        plan = c.post(f"/api/ev/plan/{r['id']}/clarify",
                      json={"answers": [{"question": "Better at what?", "answer": "speed"}]}).json()
        assert plan["plan"]["clarifications"] == [{"question": "Better at what?", "answer": "speed"}]


def test_decision_confirm_and_change(world):
    c, _, _ = world
    pid = start(c)["id"]
    r = c.post(f"/api/ev/plan/{pid}/decision/d1", json={"confirm": True}).json()
    assert r["plan"]["decisions"][0]["confirmed_by"] and r["plan"]["decisions"][1]["confirmed_by"] is None
    r = c.post(f"/api/ev/plan/{pid}/decision/d2", json={"change": "only firm"}).json()
    assert r["plan"]["decisions"][1]["value"] == "only firm" and r["plan"]["decisions"][1]["confirmed_by"]
    assert c.post(f"/api/ev/plan/{pid}/decision/zz", json={"confirm": True}).status_code == 404
    assert c.post(f"/api/ev/plan/{pid}/decision/d1", json={}).status_code == 400


def test_confirm_all_includes_flagged(world):
    c, _, _ = world
    pid = start(c)["id"]
    plan = c.post(f"/api/ev/plan/{pid}/confirm-all", json={}).json()["plan"]
    assert all(d["confirmed_by"] for d in plan["decisions"])


def test_delete_line_refused_for_oversell(world):
    c, _, _ = world
    pid = start(c)["id"]
    assert c.delete(f"/api/ev/plan/{pid}/line/oversell", headers=H).status_code == 409
    r = c.delete(f"/api/ev/plan/{pid}/line/l1", headers=H)
    assert [x["id"] for x in r.json()["plan"]["lines"]] == ["oversell"]
    assert c.delete(f"/api/ev/plan/{pid}/line/l1", headers=H).status_code == 404


def test_run_409_until_ready_then_freezes_with_protocol(world):
    c, fake, root = world
    pid = start(c)["id"]
    assert c.post(f"/api/ev/plan/{pid}/run", json={}).status_code == 409 and not fake.ran
    c.post(f"/api/ev/plan/{pid}/confirm-all", json={})
    assert c.post(f"/api/ev/plan/{pid}/run", json={}).json() == {"run": "run-1"}
    assert fake.ran[0].ready()
    folder = root / "plans" / pid
    record = json.loads((folder / "protocol.json").read_text(encoding="utf-8"))
    assert record["decisions"][0]["confirmed_by"] and record["run"] == "run-1" and "clarifications" in record
    assert (folder / "plan.frozen.json").is_file()
    assert c.post(f"/api/ev/plan/{pid}/confirm-all", json={}).status_code == 409  # frozen


def test_links_go_to_review_and_rerun(world):
    c, fake, _ = world
    pid = start(c)["id"]
    c.post(f"/api/ev/plan/{pid}/confirm-all", json={})
    c.post(f"/api/ev/plan/{pid}/run", json={})
    r = c.post("/api/ev/run/run-1/links", json={"accepted": ["a"], "rejected": ["b"]})
    assert r.json()["reruns"][0]["flips"] and fake.reviewed == [("run-1", ["a"], ["b"])]
    assert c.post("/api/ev/run/other/links", json={}).status_code == 404


def test_unwired_parts_answer_501(tmp_path):
    with TestClient(create_app(Settings(EV=tmp_path),  # type: ignore[call-arg]
                               plan_backend=PlanBackend(clarify=lambda q: [], propose=make_plan,
                                                        critic=lambda p: confirm_all(p, "x")))) as c:
        pid = start(c)["id"]
        assert c.post(f"/api/ev/plan/{pid}/run", json={}).status_code == 501
