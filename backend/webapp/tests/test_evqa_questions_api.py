"""/api/evqa/questions: the Workbench questions pane over the frozen medical questions."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from webapp.evqa_questions_api import router


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_list_and_detail() -> None:
    c = client()
    listing = c.get("/api/evqa/questions/medical").json()
    assert listing["frozen"]["problems"] == [] and listing["frozen"]["set_sha256"]
    qids = [q["qid"] for q in listing["questions"]]
    assert qids[:4] == ["Q-med-01", "Q-med-02", "Q-med-03", "Q-med-04"]
    d = c.get("/api/evqa/questions/medical/Q-med-01").json()
    assert d["rerun_matches"] and len(d["answer"]["table"]) == 5 == len(d["rows"])
    assert [c["key"] for c in d["answer"]["columns"]] == ["time_point", "patient_group"]
    assert "SELECT" in d["sparql"] and "R-med-04-01" in {r["id"] for r in d["rows"]}
    best = c.get("/api/evqa/questions/medical/Q-med-04").json()["answer"]
    assert {g["status"] for g in best["groups"]} == {"winner", "not reported"}
    assert [e["point"] for e in d["intent_card"]][0] == "time_point"


def test_refuses_unknown_things() -> None:
    c = client()
    assert c.get("/api/evqa/questions/nope").status_code == 404
    assert c.get("/api/evqa/questions/medical/Q-nope").status_code == 404


def test_not_reported_question_shows_why_and_closest_rows(tmp_path, monkeypatch) -> None:
    import json

    from evqa.seed import questions as qs
    real_q, real_g = qs.questions_dir("medical"), qs.gold_dir("medical")
    qdir, gdir = tmp_path / "questions", tmp_path / "gold"
    qdir.mkdir()
    gdir.mkdir()
    rec = json.loads((real_q / "test.jsonl").read_text().splitlines()[0])
    g1 = json.loads((real_g / f"{rec['qid']}.json").read_text())
    nr = {**rec, "qid": "Q-med-90", "type": "near_miss", "answerable": False,
          "question": "How much does brenoxalin 30 mg lower HbA1c?"}
    gold = {**g1, "qid": "Q-med-90", "type": "near_miss", "answerable": False, "status": "not_reported",
            "sparql": g1["sparql"].replace("FILTER(?dose = 20)", "FILTER(?dose = 30)"), "row_ids": [],
            "near_rows": g1["row_ids"][:2], "rows_without_card": 0,
            "answer": {"status": "not_reported", "why": "no paper reports brenoxalin 30 mg on HbA1c", "columns": [],
                       "table": [], "text": "not reported"},
            "wording": {"template": "How much does brenoxalin 30 mg change HbA1c?", "source": "llm",
                        "text": nr["question"], "attempts": []}}
    (qdir / "test.jsonl").write_text(json.dumps({**rec, "answerable": True}) + "\n" + json.dumps(nr) + "\n")
    (gdir / f"{rec['qid']}.json").write_text(json.dumps(g1))
    (gdir / "Q-med-90.json").write_text(json.dumps(gold))
    (gdir / "manifest.json").write_text(json.dumps({"set_sha256": "x", "files": {}, "questions": {},
                                                    "generator": {"report": {"lookup": {"quota": 10}}}}))
    monkeypatch.setattr(qs, "questions_dir", lambda d: qdir)
    monkeypatch.setattr(qs, "gold_dir", lambda d: gdir)
    c = client()
    listing = c.get("/api/evqa/questions/medical").json()
    assert [q["answerable"] for q in listing["questions"]] == [True, False]
    assert listing["counts"] == {"lookup": {"test": 1}, "near_miss": {"test": 1}} and listing["report"]
    d = c.get("/api/evqa/questions/medical/Q-med-90").json()
    assert d["answerable"] is False and d["why"].startswith("no paper reports") and d["rows"] == []
    assert [r["id"] for r in d["near_rows"]] == g1["row_ids"][:2] and d["rerun_matches"]
    assert d["wording"]["template"].endswith("change HbA1c?")
