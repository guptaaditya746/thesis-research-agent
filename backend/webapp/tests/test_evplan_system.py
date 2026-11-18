"""The plan API's synth3 parts (webapp/evplan.py, evsystem.py, planwire.py): sub-questions, the answer kind, a built
synth3 folder to run on, batch plan files and the written answer's text. No model is called."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence import planrun
from evidence.plan import load_plan
from synth3.questions import load_questions
from synth3.sheetfacts import load_folder
from synth3.spec import load_spec
from synth3.tests.conftest import SPEC, folder, q  # noqa: F401  (fixtures)
from synth3.tests.systemrun import FACT_REPLY, demo_plan, make_system_run, write_demo_plans
from webapp.app import create_app
from webapp.evplan import PlanBackend
from webapp.planwire import PlanRuns
from webapp.settings import Settings
from webapp.tests.test_evplan import make_plan as old_make_plan
from webapp.tests.test_evreview import review_root  # noqa: F401  (fixture)


def plan_of(question: str):
    """A plan with no decision confirmed."""
    return old_make_plan(question, [])[0]


def fake_backend(**parts) -> PlanBackend:
    """A PlanBackend of fakes: `propose` returns a plan (it is wrapped into the pair the backend wants, and the
    sub-questions it was given are put on the plan, as the real planner does), `critic` is the identity."""
    given = parts.pop("propose", None)

    def propose(question, answers, **kw):
        plan = (given or (lambda question, answers, **_: plan_of(question)))(question, answers, **kw)
        subs = list(kw.get("sub_questions", ()))
        return (plan.model_copy(update={"sub_questions": subs}) if subs else plan), {}

    base = dict(clarify=lambda question: [], propose=propose, critic=lambda plan: plan,
                run=lambda plan, d, corpus=None: "r1",
                result=lambda rid: {"status": "done", "lines": [], "answer": {"text": "x"}})
    return PlanBackend(**{**base, **parts})


def client(tmp_path: Path, be: PlanBackend, **env) -> TestClient:
    return TestClient(create_app(Settings(EV=tmp_path / "ev", **env), plan_backend=be))  # type: ignore[call-arg]


def confirmed_plan(c: TestClient) -> str:
    pid = c.post("/api/ev/plan", json={"question": "Q?"}).json()["id"]
    assert c.post(f"/api/ev/plan/{pid}/confirm-all", json={}).json()["ready"]
    return pid


def test_sub_questions_reach_the_planner_and_the_view(tmp_path):
    seen = {}
    be = fake_backend(propose=lambda q, a, sub_questions=(): (seen.update(sub=list(sub_questions)), plan_of(q))[1])
    v = client(tmp_path, be).post("/api/ev/plan", json={"question": "Q?", "sub_questions": ["S1?"]}).json()
    assert seen["sub"] == ["S1?"] and v["sub_questions"] == ["S1?"] and v["plan"]["sub_questions"] == ["S1?"]


def test_an_empty_sub_question_is_refused(tmp_path):
    r = client(tmp_path, fake_backend()).post("/api/ev/plan", json={"question": "Q?", "sub_questions": [" "]})
    assert r.status_code == 400 and "a sub-question is empty" in r.text


def test_an_old_style_propose_fake_still_works_without_sub_questions(tmp_path):
    be = fake_backend(propose=lambda q, a: plan_of(q))
    assert client(tmp_path, be).post("/api/ev/plan", json={"question": "Q?"}).status_code == 200


def test_the_answer_kind_survives_clarifying_questions(tmp_path):
    be = fake_backend(clarify=lambda q: [{"question": "Which?", "options": ["a", "b"]}])
    c = client(tmp_path, be)
    v = c.post("/api/ev/plan", json={"question": "Q?", "answer_by": "inventory", "target": "metric"}).json()
    assert v["plan"] is None
    v = c.post(f"/api/ev/plan/{v['id']}/clarify", json={"answers": [{"question": "Which?", "answer": "a"}]}).json()
    assert v["plan"]["answer_by"] == "inventory" and v["plan"]["target"] == "metric"


def test_the_answer_kind_is_set_and_checked(tmp_path):
    c = client(tmp_path, fake_backend()); pid = c.post("/api/ev/plan", json={"question": "Q?"}).json()["id"]
    assert c.post(f"/api/ev/plan/{pid}/answer", json={"answer_by": "inventory", "target": "metric"}).json()["plan"]["target"] == "metric"
    assert c.post(f"/api/ev/plan/{pid}/answer", json={"answer_by": "written", "target": "metric"}).status_code == 400
    assert c.post("/api/ev/plan", json={"question": "Q?", "answer_by": "chaining"}).status_code == 400


def test_the_answer_kind_with_no_plan_yet_is_kept_with_a_409(tmp_path):
    be = fake_backend(clarify=lambda q: [{"question": "Which?", "options": ["a"]}])
    c = client(tmp_path, be); pid = c.post("/api/ev/plan", json={"question": "Q?"}).json()["id"]
    assert c.post(f"/api/ev/plan/{pid}/answer", json={"answer_by": "effect"}).status_code == 409
    v = c.post(f"/api/ev/plan/{pid}/clarify", json={"answers": [{"question": "Which?", "answer": "a"}]}).json()
    assert v["plan"]["answer_by"] == "effect"


def test_a_best_plan_without_a_measure_is_not_ready_and_does_not_run(tmp_path):
    c = client(tmp_path, fake_backend())
    pid = c.post("/api/ev/plan", json={"question": "Q?", "answer_by": "best"}).json()["id"]
    v = c.post(f"/api/ev/plan/{pid}/confirm-all", json={}).json()
    assert not v["ready"] and any("best answer" in p for p in v["problems"])
    assert c.post(f"/api/ev/plan/{pid}/run", json={}).status_code == 409


def test_a_batch_plan_opens_and_its_edits_are_saved_to_its_file(review_root, tmp_path):
    qs = load_questions("demo", load_spec("demo", review_root), review_root / "questions")
    write_demo_plans(review_root / "plans", qs, load_spec("demo", review_root), confirmed=None)
    c = client(tmp_path, fake_backend(), SYNTH3_DATA=review_root)
    v = c.post("/api/ev/plan/batch/demo/d01", json={}).json()
    assert v["batch"] == "demo/d01" and not v["ready"]
    c.post(f"/api/ev/plan/{v['id']}/confirm-all", json={})
    saved = load_plan(review_root / "plans" / "demo" / "d01.json")
    assert saved.ready() and {d.confirmed_by for d in saved.decisions} == {Settings().user}
    assert c.post(f"/api/ev/plan/{v['id']}/answer", json={"answer_by": "effect"}).status_code == 409
    assert c.post("/api/ev/plan/batch/demo/d09", json={}).status_code == 404


def test_a_batch_plan_of_a_changed_question_shows_it_is_stale(review_root, tmp_path):
    qs = load_questions("demo", load_spec("demo", review_root), review_root / "questions")
    write_demo_plans(review_root / "plans", qs, load_spec("demo", review_root), confirmed="aditya")
    path = review_root / "plans" / "demo" / "d01.json"
    plan = load_plan(path)
    path.write_text(plan.model_copy(update={"question": "An older wording?"}).model_dump_json(), encoding="utf-8")
    c = client(tmp_path, fake_backend(), SYNTH3_DATA=review_root)
    v = c.post("/api/ev/plan/batch/demo/d01", json={}).json()
    assert "the question changed after planning" in v["problems"] and not v["ready"]


def test_a_run_on_a_synth3_folder_passes_the_folder(review_root, tmp_path):
    got = {}
    be = fake_backend(run=lambda plan, d, corpus=None: (got.update(corpus=corpus), "r1")[1])
    c = client(tmp_path, be, SYNTH3_DATA=review_root); pid = confirmed_plan(c)
    assert c.post(f"/api/ev/plan/{pid}/run", json={"domain": "demo", "seed": 1}).json() == {"run": "r1"}
    assert Path(got["corpus"]).resolve() == (review_root / "built" / "demo" / "s1").resolve()


def test_a_run_without_a_folder_is_todays_run(tmp_path):
    got = []
    be = fake_backend(run=lambda plan, d: (got.append(d), "r1")[1])
    c = client(tmp_path, be); pid = confirmed_plan(c)
    assert c.post(f"/api/ev/plan/{pid}/run", json={}).json() == {"run": "r1"} and len(got) == 1


@pytest.mark.parametrize("body", [{"domain": "demo"}, {"seed": 1}, {"domain": "demo", "seed": 9},
                                  {"domain": "..", "seed": 1}])
def test_a_bad_folder_is_refused(review_root, tmp_path, body):
    called = []
    be = fake_backend(run=lambda plan, d, corpus=None: (called.append(1), "r1")[1])
    c = client(tmp_path, be, SYNTH3_DATA=review_root); pid = confirmed_plan(c)
    assert c.post(f"/api/ev/plan/{pid}/run", json=body).status_code in (400, 404, 409) and called == []
    assert c.post(f"/api/ev/plan/{pid}/run", json={}).json() == {"run": "r1"}   # the plan is open again


def test_plan_runs_on_a_given_corpus_turn_reasoning_and_links_off(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(planrun, "run", lambda path, corpus, out, **kw: seen.update(corpus=corpus, **kw))
    runs = PlanRuns(Settings(EV=tmp_path / "ev"))
    rid = runs.run(plan_of("Q?"), None, corpus=tmp_path / "c")
    runs.threads[rid].join(5)
    assert seen["reason"] == "off" and seen["links"] == "off" and seen["corpus"] == tmp_path / "c"


def test_a_written_result_shows_the_written_text(folder, tmp_path, SPEC):  # noqa: F811
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    run = make_system_run(tmp_path / "ev" / "runs", f, qq, demo_plan(SPEC, qq), writer_reply=FACT_REPLY, run_id="r1")
    want = json.loads((run / "written-answer.json").read_text(encoding="utf-8"))["answer_text"]
    assert want and PlanRuns(Settings(EV=tmp_path / "ev")).result("r1")["answer"]["text"] == want


def test_a_failed_writer_call_shows_as_a_failed_result(folder, tmp_path, SPEC):  # noqa: F811
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    run = make_system_run(tmp_path / "ev" / "runs", f, qq, demo_plan(SPEC, qq),
                          writer_reply=lambda p: RuntimeError("gateway down"), run_id="r1")
    written = json.loads((run / "written-answer.json").read_text(encoding="utf-8"))
    assert set(written) == {"failed"}
    out = PlanRuns(Settings(EV=tmp_path / "ev")).result("r1")
    assert out["status"] == "done"
    assert out["answer"]["text"] == f"failed: the written answer's model call failed: {written['failed']}"


def test_a_batch_plan_runs_only_on_a_built_folder_of_its_own_domain(review_root, tmp_path):
    """Review round 1, web-I2: the plan page sent a bare Run, and the server ran the synth3 batch plan on the RAG
    corpus ($EV_PLAN_CORPUS) with the reasoner and links on."""
    spec = load_spec("demo", review_root)
    write_demo_plans(review_root / "plans", load_questions("demo", spec, review_root / "questions"), spec)
    build = review_root / "built" / "demo" / "s1"
    got = []
    be = fake_backend(run=lambda plan, d, corpus=None: (got.append(corpus), "r1")[1])
    c = client(tmp_path, be, SYNTH3_DATA=review_root)
    pid = c.post("/api/ev/plan/batch/demo/d01", json={}).json()["id"]
    for body in ({}, {"domain": "other", "seed": 1}):
        r = c.post(f"/api/ev/plan/{pid}/run", json=body)
        assert r.status_code == 409 and got == [], body
        assert "a batch plan of demo runs only on a built folder of demo" in r.json()["detail"]
        assert "System page" in r.json()["detail"]
    assert c.post(f"/api/ev/plan/{pid}/run", json={"domain": "demo", "seed": 1}).json() == {"run": "r1"}
    assert Path(got[0]).resolve() == build.resolve()
