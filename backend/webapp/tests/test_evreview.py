"""The review API (webapp/evreview.py): worlds, answer sheets and the judge test on a small synth3 data folder.
No model is called."""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from jsonio import write_json_atomic
from synth3.answers import AnswerRecord, PulledFact, save_answer
from synth3.corpus import build_folder
from synth3.marking import marks_path
from synth3.questions import load_questions, question_sha256
from synth3.report import save_sample
from synth3.sheetfacts import load_folder, relevant_facts
from synth3.sheets import make_sheet, save_sheet, sheet_sha256
from synth3.spec import load_spec
from synth3.tests.conftest import good, write
from synth3.world import draw_world, save_world
from webapp.app import create_app
from webapp.evplan import PlanBackend
from webapp.evreview import ReviewFiles
from webapp.files import BadRequest, NotFound
from webapp.settings import Settings

FIX = Path(__file__).resolve().parents[2] / "synth3" / "tests" / "fixtures" / "questions" / "demo.yaml"
ITEM = "demo/s1/engine/d01"
JUDGE_KEYS = {"met", "score", "ticks", "A", "B", "C", "judge", "system", "item"}
SYSTEMS = ("engine", "rag-baseline")


@pytest.fixture
def review_root(tmp_path: Path) -> Path:
    root = tmp_path / "synth3"
    write(root, good())
    spec = load_spec("demo", root)
    save_world(root / "worlds" / "demo" / "s1.json", draw_world(spec, 1))
    build_folder(root / "built" / "demo" / "s1", spec, replace(draw_world(spec, 1), approved=True), 40, "table")
    (root / "questions").mkdir()
    shutil.copy(FIX, root / "questions" / "demo.yaml")
    folder = load_folder(root / "built" / "demo" / "s1")
    q = load_questions("demo", spec, root / "questions").get("d01")
    fact = relevant_facts(folder.spec, folder.truth, q)[0].id
    sheet = make_sheet(folder, q, [("Targeted therapy does better.", [fact])], {"model": "x"})
    save_sheet(root / "sheets", sheet)
    pulled = [PulledFact(paper="S001", kind="measurement", fields={"value": 1}, quote="first quote"),
              PulledFact(paper="S002", kind="measurement", fields={"value": 2}, quote="second quote")]
    rec = AnswerRecord(domain="demo", seed=1, corpus_id=folder.corpus_id, question_id="d01",
                       question_sha256=question_sha256(q), system="engine", text="Targeted therapy does better.",
                       text_cut=False, cited=[], facts=pulled, passages=[], source="fake")
    save_answer(root / "results", rec)
    write_json_atomic(marks_path(root / "results", "demo", 1, "engine", "d01"), {
        "item": ITEM, "question_id": "d01", "seed": 1, "system": "engine", "corpus_id": folder.corpus_id,
        "answer_sha256": "x",
        "sheet": {"sha256": sheet_sha256(sheet), "status": "drafted", "cant_tell": False,
                  "points": [{"id": "p1", "text": "Targeted therapy does better."}]},
        "A": {"score": 0.5, "papers": {}, "pending_papers": []},
        "B": {"score": 1.0, "status": "ok", "invented": 0, "contradicted": 0, "claims": []},
        "C": {"score": 1.0, "status": "ok", "ticks": [{"point": "p1", "met": True, "quote": "Targeted",
                                                       "reason": ""}], "missed": []},
        "judge": {"model": "fake", "prompts": {}}, "calls": 3})
    save_sample(root / "judge-test", [ITEM])
    return root


def client(root: Path) -> TestClient:
    return TestClient(create_app(Settings(SYNTH3_DATA=root, WEBAPP_USER="aditya"),  # type: ignore[call-arg]
                                 plan_backend=PlanBackend()))


def keys(obj) -> set:
    """Every dict key in a JSON value, at any depth."""
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in keys(v)}
    return set()


def edit_question(root: Path, qid: str, text: str) -> None:
    """Rewrite the question file with question `qid` changed (ruling F16: a test helper, not an endpoint)."""
    path = root / "questions" / "demo.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for q in data["questions"]:
        if q["id"] == qid:
            q["question"] = text
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_the_overview_lists_each_approved_spec(review_root):
    (review_root / "drafts").mkdir()
    write(review_root / "drafts", good())   # a draft spec is not a domain
    got = client(review_root).get("/api/ev/review").json()
    assert got == {"domains": [{"domain": "demo", "questions": 3, "seeds": [1], "worlds": [1]}]}


def test_worlds_show_the_plain_table_and_approve(review_root):
    c = client(review_root)
    rows = c.get("/api/ev/review/demo/worlds").json()
    assert rows[0]["seed"] == 1 and not rows[0]["approved"] and "World of demo, seed 1" in rows[0]["text"]
    assert c.put("/api/ev/review/demo/worlds/1", json={"approved": True}).json()["approved"]
    assert json.loads((review_root / "worlds" / "demo" / "s1.json").read_text(encoding="utf-8"))["approved"] is True


def test_a_world_that_does_not_load_is_422(review_root):
    path = review_root / "worlds" / "demo" / "s1.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"approved": false', '"approved": "yes"'),
                    encoding="utf-8")
    c = client(review_root)
    r = c.put("/api/ev/review/demo/worlds/1", json={"approved": True})
    assert r.status_code == 422 and "approved" in r.json()["detail"]
    assert c.put("/api/ev/review/demo/worlds/2", json={"approved": True}).status_code == 404


def test_a_sheet_is_shown_with_its_facts_and_saved_as_checked(review_root):
    c = client(review_root)
    got = c.get("/api/ev/review/demo/sheets/1/d01").json()
    assert got["scope"]["arms"] == ["Standard care", "Targeted therapy"] and got["facts"] and got["stale"] is None
    assert got["question"].startswith("Does Targeted therapy") and got["sheet"]["status"] == "drafted"
    saved = c.put("/api/ev/review/demo/sheets/1/d01", json={"points": [{"text": "Edited.", "facts": []}]}).json()
    assert saved["status"] == "checked" and saved["checked_by"] and saved["points"][0]["text"] == "Edited."


def test_a_bad_point_is_400(review_root):
    r = client(review_root).put("/api/ev/review/demo/sheets/1/d01",
                                json={"points": [{"text": "x", "facts": ["pair:zz:m9"]}]})
    assert r.status_code == 400 and "pair:zz:m9" in r.json()["detail"]


def test_saving_a_stale_sheet_makes_a_new_unchecked_one(review_root):
    c = client(review_root)
    edit_question(review_root, "d01", "Does Targeted therapy change the Response rate?")
    assert c.get("/api/ev/review/demo/sheets/1/d01").json()["stale"]
    saved = c.put("/api/ev/review/demo/sheets/1/d01", json={"points": [{"text": "New.", "facts": []}]}).json()
    assert saved["status"] == "drafted" and saved["drafted_by"]["person"]
    assert c.get("/api/ev/review/demo/sheets/1/d01").json()["stale"] is None
    assert (review_root / "sheets" / "demo" / "s1" / "d01.stale-1.json").is_file()
    again = c.put("/api/ev/review/demo/sheets/1/d01", json={"points": [{"text": "New.", "facts": []}]}).json()
    assert again["status"] == "checked"


def test_a_bad_point_on_a_stale_sheet_archives_nothing(review_root):
    c = client(review_root)
    edit_question(review_root, "d01", "Does Targeted therapy change the Response rate?")
    r = c.put("/api/ev/review/demo/sheets/1/d01", json={"points": [{"text": "x", "facts": ["pair:zz:m9"]}]})
    assert r.status_code == 400
    assert not (review_root / "sheets" / "demo" / "s1" / "d01.stale-1.json").exists()
    assert (review_root / "sheets" / "demo" / "s1" / "d01.json").is_file()


def test_a_missing_sheet_can_be_written_on_the_page(review_root):
    c = client(review_root)
    got = c.get("/api/ev/review/demo/sheets/1/d02").json()
    assert got["sheet"] is None and got["facts"]
    saved = c.put("/api/ev/review/demo/sheets/1/d02", json={"points": [{"text": "Written by hand.", "facts": []}]})
    assert saved.status_code == 200 and saved.json()["status"] == "checked"


def test_queue_marks_the_full_folder(review_root):
    edit_question(review_root, "d01", "Does Targeted therapy change the Response rate?")
    rows = client(review_root).get("/api/ev/review/demo/sheets").json()
    assert [r["question_id"] for r in rows] == ["d01", "d02", "d03"]
    assert all(r["seed"] == 1 and r["must_check"] == "full" for r in rows)
    by = {r["question_id"]: r for r in rows}
    assert by["d01"]["status"] == "drafted" and by["d01"]["stale"] and by["d02"]["status"] == "missing"


def blind(value) -> bool:
    """No judge key and no system name anywhere in a JSON value."""
    text = json.dumps(value)
    return not keys(value) & JUDGE_KEYS and not any(name in text for name in SYSTEMS)


def test_the_judge_test_item_shows_the_facts_but_not_the_judge(review_root):
    c = client(review_root); item = c.get("/api/ev/review/judge-test/0").json()
    assert blind(item) and (item["domain"], item["seed"], item["question_id"]) == ("demo", 1, "d01")
    assert item["facts"][0]["n"] == 1 and item["facts"][0]["quote"]
    assert all(set(f) == {"n", "paper", "quote"} for f in item["facts"])   # `kind: passage` would name the baseline
    assert [f["quote"] for f in item["facts"]] == ["first quote", "second quote"] and item["facts_cut"] is False
    assert item["points"] == [{"id": "p1", "text": "Targeted therapy does better."}] and item["marked"] is None
    assert item["answer"] == "Targeted therapy does better." and item["question"].startswith("Does Targeted")
    listed = c.get("/api/ev/review/judge-test").json()
    assert listed == [{"n": 0, "domain": "demo", "seed": 1, "question_id": "d01", "done": False}] and blind(listed)
    assert c.put("/api/ev/review/judge-test/0", json={"points": {"p9": True}, "faithful": None}).status_code == 400
    assert c.put("/api/ev/review/judge-test/0", json={"points": {}, "faithful": None}).status_code == 400
    saved = c.put("/api/ev/review/judge-test/0", json={"points": {"p1": True}, "faithful": True})
    assert saved.status_code == 200 and saved.json()["by"] == "aditya" and saved.json()["points"] == {"p1": True}
    assert c.get("/api/ev/review/judge-test").json()[0]["done"]
    again = c.get("/api/ev/review/judge-test/0").json()
    assert again["marked"]["faithful"] is True and blind(again)
    hand = json.loads((review_root / "judge-test" / "marks.json").read_text(encoding="utf-8"))
    assert hand[ITEM]["points"] == {"p1": True} and hand[ITEM]["at"].endswith("+00:00")


def test_the_judge_test_keeps_the_points_the_judge_used(review_root):
    c = client(review_root)
    two = [{"text": "A.", "facts": []}, {"text": "B.", "facts": []}]
    assert c.put("/api/ev/review/demo/sheets/1/d01", json={"points": two}).json()["status"] == "checked"
    item = c.get("/api/ev/review/judge-test/0").json()   # the marks file's points, not the edited sheet's
    assert item["points"] == [{"id": "p1", "text": "Targeted therapy does better."}]
    assert c.put("/api/ev/review/judge-test/0", json={"points": {"p1": False}, "faithful": None}).status_code == 200


def test_a_hand_mark_takes_only_true_or_false(review_root):
    c = client(review_root)
    assert c.put("/api/ev/review/judge-test/0", json={"points": {"p1": "yes"}, "faithful": None}).status_code == 422
    assert c.put("/api/ev/review/judge-test/0", json={"points": {"p1": True}, "faithful": 1}).status_code == 422
    assert c.put("/api/ev/review/demo/worlds/1", json={"approved": "true"}).status_code == 422


def test_a_bad_sample_row_is_flagged_and_the_rest_stay_markable(review_root):
    (review_root / "judge-test" / "sample.json").write_text(json.dumps(["nonsense", ITEM]), encoding="utf-8")
    rows = client(review_root).get("/api/ev/review/judge-test").json()
    assert rows[0]["n"] == 0 and rows[0]["problem"] and rows[1]["question_id"] == "d01"


def test_a_yaml_typo_is_a_409_naming_the_file_and_the_overview_lists_it(review_root):
    (review_root / "other.yaml").write_text("a: [unclosed\n", encoding="utf-8")
    c = client(review_root)
    got = c.get("/api/ev/review")
    assert got.status_code == 200
    rows = {r["domain"]: r for r in got.json()["domains"]}
    assert rows["demo"]["questions"] == 3 and "error" not in rows["demo"] and "other.yaml" in rows["other"]["error"]
    r = c.get("/api/ev/review/other/worlds")
    assert r.status_code == 409 and "other.yaml" in r.json()["detail"]
    (review_root / "questions" / "demo.yaml").write_text("domain: demo\nquestions: [unclosed\n", encoding="utf-8")
    r = c.get("/api/ev/review/demo/sheets/1/d01")
    assert r.status_code == 409 and "demo.yaml" in r.json()["detail"]
    assert c.get("/api/ev/review").json()["domains"][0]["questions"] is None


def test_a_damaged_sheet_file_is_a_409(review_root):
    (review_root / "sheets" / "demo" / "s1" / "d01.json").write_text("{not json", encoding="utf-8")
    c = client(review_root)
    for r in (c.get("/api/ev/review/demo/sheets/1/d01"), c.get("/api/ev/review/demo/sheets")):
        assert r.status_code == 409 and "d01.json" in r.json()["detail"]


def test_an_unknown_judge_test_number_is_404(review_root):
    c = client(review_root)
    assert c.get("/api/ev/review/judge-test/1").status_code == 404
    assert c.get("/api/ev/review/judge-test/-1").status_code == 404


@pytest.mark.parametrize("path", ["/api/ev/review/demo/sheets/1/a.b%20c", "/api/ev/review/demo/sheets/1/-x",
                                  "/api/ev/review/de%2E%2Emo/worlds", "/api/ev/review/demo/sheets/x/d01",
                                  "/api/ev/review/demo/sheets/9/d01", "/api/ev/review/nope/worlds"])
def test_bad_ids_are_refused(review_root, path):
    assert client(review_root).get(path).status_code in (400, 404, 422)


def test_the_review_routes_are_in_the_schema_with_their_own_names(review_root):
    schema = client(review_root).app.openapi()
    ids = [op["operationId"] for path in schema["paths"].values() for op in path.values()]
    assert len(ids) == len(set(ids))
    assert schema["paths"]["/api/ev/review/{domain}/sheets/{seed}/{qid}"]["put"]["operationId"] == "review_save_sheet"


def test_the_path_builder_stays_under_the_root(review_root):
    with pytest.raises((BadRequest, NotFound)):
        ReviewFiles(Settings(SYNTH3_DATA=review_root)).sheet_file("demo", 1, "..")  # type: ignore[call-arg]
