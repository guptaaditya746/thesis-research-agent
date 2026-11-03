"""The plan API (webapp/evplan.py) with a fake planner: one test per route, plus the locks and the model rules."""
from __future__ import annotations

import itertools
import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence import steps
from evidence.plan import Decision, EvidenceLine, Plan, WordList
from evidence.planner import confirm_all
from modelcall.cache import JsonlCache
from modelcall.dspy_lm import RecordedLM
from webapp.app import create_app
from webapp.evplan import PlanBackend
from webapp.settings import Settings

Q = "SELECT ?x WHERE { ?x a ev:Claim . FILTER(?n >= $threshold) }"
H = {"X-Requested-With": "test"}  # the guard wants JSON or this header on a write


def make_plan(question: str, clar: list[dict[str, str]]) -> tuple[Plan, dict[str, list[str]]]:
    plan = Plan(question=question, field="cs", main_rule="any_line",
                words=WordList(things={"a": ["a"]}, cues=[], written_by="fake", ontology_names={}),
                lines=[EvidenceLine(id="l1", question="Does it help?", query=Q, template=None),
                       EvidenceLine(id="oversell", question="Oversold?", query=Q, template=None, removable=False)],
                decisions=[Decision(id="d1", type="threshold", value="0.01", reason="noise"),
                           Decision(id="d2", type="include", value="all", reason="small"),
                           Decision(id="main_rule", type="counts_as", value="any_line", reason="fixed set")],
                clarifications=clar)
    return plan, {"l1": ["It looks at claims."]}


def flag_first(plan: Plan) -> Plan:
    d = plan.decisions[0].model_copy(update={"flagged": True, "flag_reason": "maybe too small"})
    return plan.model_copy(update={"decisions": [d, *plan.decisions[1:]]})


class Fake:
    def __init__(self, ask: bool = False, slow: float = 0) -> None:
        self.ask, self.slow = ask, slow
        self.ran: list[Plan] = []
        self.reviewed: list[tuple] = []

    def backend(self) -> PlanBackend:
        def run(plan: Plan, folder: Path | None) -> str:
            time.sleep(self.slow)
            if folder is not None:
                assert (folder / "plan.frozen.json").is_file() and (folder / "protocol.json").is_file()  # before the run
            self.ran.append(plan)
            return "run-1"

        def links(rid: str, accepted: list[str], rejected: list[str]) -> dict:
            self.reviewed.append((rid, accepted, rejected))
            return {"reruns": [{"setting": "threshold", "flips": True}]}

        clar = [{"question": "Better at what?", "options": ["accuracy", "speed"]}] if self.ask else []
        return PlanBackend(clarify=lambda q: clar, propose=make_plan, critic=flag_first, run=run, links=links,
                           result=lambda rid: {"status": "done", "lines": [], "answer": {"text": "No evidence found"}})


@pytest.fixture
def world(tmp_path):
    fake = Fake()
    with TestClient(create_app(Settings(EV=tmp_path), plan_backend=fake.backend())) as c:  # type: ignore[call-arg]
        yield c, fake, tmp_path


def start(c, q="Does it help?"):
    return c.post("/api/ev/plan", json={"question": q}).json()


def test_start_returns_the_plan_with_flags_how_and_ready(world):
    c, _, _ = world
    r = start(c)
    assert r["plan"]["decisions"][0]["flagged"] and r["clarifications"] == [] and r["id"]
    assert r["how"]["l1"][0] == "It looks at claims." and r["problems"] == [] and r["ready"] is False
    assert not any("SELECT" in s for sentences in r["how"].values() for s in sentences)


def test_questions_first_then_clarify_once(tmp_path):
    fake = Fake(ask=True)
    with TestClient(create_app(Settings(EV=tmp_path), plan_backend=fake.backend())) as c:  # type: ignore[call-arg]
        r = start(c)
        assert r["plan"] is None and r["clarifications"][0]["options"] == ["accuracy", "speed"]
        pid = r["id"]
        wrong = c.post(f"/api/ev/plan/{pid}/clarify", json={"answers": [{"question": "Better at what?", "answer": "x"}]})
        assert wrong.status_code == 400
        right = {"answers": [{"question": "Better at what?", "answer": "speed"}]}
        plan = c.post(f"/api/ev/plan/{pid}/clarify", json=right).json()
        assert plan["plan"]["clarifications"] == right["answers"]
        assert c.post(f"/api/ev/plan/{pid}/clarify", json=right).status_code == 409  # no silent re-plan


def test_decision_confirm_and_change(world):
    c, _, _ = world
    pid = start(c)["id"]
    r = c.post(f"/api/ev/plan/{pid}/decision/d1", json={"confirm": True}).json()
    assert r["plan"]["decisions"][0]["confirmed_by"] and r["plan"]["decisions"][1]["confirmed_by"] is None
    r = c.post(f"/api/ev/plan/{pid}/decision/d2", json={"change": ["P1"]}).json()
    assert r["plan"]["decisions"][1]["value"] == ["P1"] and r["plan"]["decisions"][1]["confirmed_by"]
    assert c.post(f"/api/ev/plan/{pid}/decision/zz", json={"confirm": True}).status_code == 404
    assert c.post(f"/api/ev/plan/{pid}/decision/d1", json={}).status_code == 400


def test_main_rule_is_from_the_fixed_set(world):
    c, _, _ = world
    pid = start(c)["id"]
    bad = c.post(f"/api/ev/plan/{pid}/decision/main_rule", json={"change": "any way you like"})
    assert bad.status_code == 400 and "any_line" in bad.json()["detail"]
    assert c.post(f"/api/ev/plan/{pid}/main-rule", json={"rule": "free text"}).status_code == 400
    r = c.post(f"/api/ev/plan/{pid}/main-rule", json={"rule": "majority"}).json()["plan"]
    row = next(d for d in r["decisions"] if d["id"] == "main_rule")
    assert r["main_rule"] == "majority" and row["value"] == "majority" and row["confirmed_by"]
    r = c.post(f"/api/ev/plan/{pid}/decision/main_rule", json={"change": "all_lines"}).json()["plan"]
    assert r["main_rule"] == "all_lines"


def test_confirm_all_includes_flagged(world):
    c, _, _ = world
    pid = start(c)["id"]
    r = c.post(f"/api/ev/plan/{pid}/confirm-all", json={}).json()
    assert all(d["confirmed_by"] for d in r["plan"]["decisions"]) and r["ready"] is True


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
    assert c.post(f"/api/ev/plan/{pid}/run", json={}).status_code == 409  # not twice


def test_a_plan_with_a_problem_does_not_run(tmp_path):
    def empty(q, c):
        plan, how = make_plan(q, c)
        return plan.model_copy(update={"lines": []}), how

    fake = Fake()
    be = fake.backend()
    be.propose = empty
    with TestClient(create_app(Settings(EV=tmp_path), plan_backend=be)) as c:  # type: ignore[call-arg]
        r = start(c)
        assert any("no evidence line" in p for p in r["problems"])
        c.post(f"/api/ev/plan/{r['id']}/confirm-all", json={})
        assert c.post(f"/api/ev/plan/{r['id']}/run", json={}).status_code == 409 and not fake.ran


def test_two_runs_at_once_start_one_and_an_edit_during_the_run_is_refused(tmp_path):
    fake = Fake(slow=0.4)
    with TestClient(create_app(Settings(EV=tmp_path), plan_backend=fake.backend())) as c:  # type: ignore[call-arg]
        pid = start(c)["id"]
        c.post(f"/api/ev/plan/{pid}/confirm-all", json={})
        codes: list[int] = []
        threads = [threading.Thread(target=lambda: codes.append(c.post(f"/api/ev/plan/{pid}/run", json={}).status_code))
                   for _ in range(2)]
        [t.start() for t in threads]
        time.sleep(0.15)
        assert c.post(f"/api/ev/plan/{pid}/decision/d1", json={"change": "0.9"}).status_code == 409  # mid-run
        [t.join() for t in threads]
        assert sorted(codes) == [200, 409] and len(fake.ran) == 1
        assert fake.ran[0].decisions[0].value == "0.01"  # the plan that ran is the plan that was frozen


def test_links_go_to_review_and_rerun(world):
    c, fake, _ = world
    pid = start(c)["id"]
    c.post(f"/api/ev/plan/{pid}/confirm-all", json={})
    c.post(f"/api/ev/plan/{pid}/run", json={})
    r = c.post("/api/ev/run/run-1/links", json={"accepted": ["a"], "rejected": ["b"]})
    assert r.json()["reruns"][0]["flips"] and fake.reviewed == [("run-1", ["a"], ["b"])]
    assert c.post("/api/ev/run/other/links", json={}).status_code == 404


def test_result_has_a_model(world):
    c, _, _ = world
    pid = start(c)["id"]
    assert c.get(f"/api/ev/plan/{pid}/result").status_code == 409  # not run yet
    c.post(f"/api/ev/plan/{pid}/confirm-all", json={})
    c.post(f"/api/ev/plan/{pid}/run", json={})
    assert c.get(f"/api/ev/plan/{pid}/result").json()["answer"]["text"] == "No evidence found"


def test_unwired_parts_answer_501(tmp_path):
    be = PlanBackend(clarify=lambda q: [], propose=make_plan, critic=lambda p: confirm_all(p, "x"))
    with TestClient(create_app(Settings(EV=tmp_path), plan_backend=be)) as c:  # type: ignore[call-arg]
        pid = start(c)["id"]
        assert c.post(f"/api/ev/plan/{pid}/run", json={}).status_code == 501


def test_default_backend_without_a_model_answers_501_not_500(tmp_path):
    with TestClient(create_app(Settings(EV=tmp_path), plan_backend=PlanBackend())) as c:  # type: ignore[call-arg]
        r = c.post("/api/ev/plan", json={"question": "Does it help?"})
        assert r.status_code == 501 and "no model" in r.json()["detail"]


def test_word_writer_gets_the_lm_and_requests_record_on_their_own_model(tmp_path, monkeypatch):
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    prompts: dict[str, list[str]] = {}
    made: list[RecordedLM] = []
    counter = itertools.count()
    got_lm: list[object] = []

    def factory() -> RecordedLM:
        name = f"lm{next(counter)}"
        prompts[name] = []

        def ask(prompt: str) -> str:
            prompts[name].append(prompt)
            time.sleep(0.05)
            return json.dumps({"clarifications": [{"question": "Which?", "options": ["a", "b"]}]})

        lm = RecordedLM("orch-model", ask, cache=JsonlCache(tmp_path / f"{name}.jsonl"))
        made.append(lm)
        return lm

    be = PlanBackend(lm=factory, write_words=lambda q, things, *, lm: got_lm.append(lm))
    with TestClient(create_app(Settings(EV=tmp_path), plan_backend=be)) as c:  # type: ignore[call-arg]
        threads = [threading.Thread(target=start, args=(c, f"question {n}")) for n in ("one", "two")]
        [t.start() for t in threads]
        [t.join() for t in threads]
    assert len(made) == 2
    for name, texts in prompts.items():
        assert len(texts) == 1 and sum("question one" in t for t in texts) + sum("question two" in t for t in texts) == 1
