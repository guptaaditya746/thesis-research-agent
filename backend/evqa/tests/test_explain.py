"""evqa.explain: plain-words error analysis of one practice question, from a hand-made run folder (no LLM, no seed)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evqa import explain as ex

PAPER = "Intro. At week 12, 50 mg lowered HbA1c by 0.52 percentage points. At week 24 it was 0.54. End."
S12 = PAPER.index("0.52")
S24 = PAPER.index("0.54")
Q12 = "At week 12, 50 mg lowered HbA1c by 0.52 percentage points."
PP = "https://w3id.org/evqa/seed#PercentagePoint"
SEED = {
    "R-1": {"id": "R-1", "paper": "P-1", "subject": "veloranide", "comparator": "placebo", "dose": "50",
            "dose_unit": "http://qudt.org/vocab/unit/MilliGM", "week": "12", "context": "adults", "value": "-0.52",
            "unit": PP, "measure": "change in HbA1c"},
    "R-2": {"id": "R-2", "paper": "P-1", "subject": "veloranide", "week": "24", "context": "adults",
            "value": "-0.54", "unit": PP},
    "R-3": {"id": "R-3", "paper": "P-2", "subject": "veloranide", "week": "24", "value": "-0.9", "unit": PP},
}


def _write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def make_run(root: Path, name: str = "practice-x", split: str = "practice") -> Path:
    run = root / name
    q = run / "Q-1"
    q.mkdir(parents=True)
    (run / "config.yaml").write_text(f"name: x\ndomain: medical\nsplit: {split}\n", encoding="utf-8")
    _write(q / "spec.json", {"qid": "Q-1", "question": "How much does veloranide 50 mg lower HbA1c?", "type": "lookup"})
    (q / "find.jsonl").write_text(json.dumps({"paper": "P-1", "passages": [
        {"start": 7, "end": len(PAPER), "text": PAPER[7:], "section": "Results"}]}) + "\n", encoding="utf-8")
    row = {"paper": "P-1", "subject": "veloranide", "dose": "50 mg", "time_point": "week 12", "patient_group": "adults",
           "std": {"value": "-0.52", "unit": PP}, "quote": Q12, "quote_start": PAPER.index(Q12),
           "quote_end": PAPER.index(Q12) + len(Q12), "quote_ok": True, "dropped": None}
    (q / "rows.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    _write(q / "answer.json", {"qid": "Q-1", "sentence": "veloranide 50 mg: -0.52 pp.", "not_reported": False,
                               "table": [{"cells": {"duration": "not stated"}, "value": "-0.52", "unit": PP, "rows": [0]}]})
    facts = [{"id": "R-1", "paper": "P-1", "rows": [0], "names": {"0": {"subject": True, "time_point": True}},
              "in_answer": False, "blame": "answer", "future_field": 1},
             {"id": "R-2", "paper": "P-1", "rows": [], "blame": "extract"},
             {"id": "R-3", "paper": "P-2", "blame": "find"}]
    _write(run / "eval.json", {"domain": "medical", "questions": {"Q-1": {
        "qid": "Q-1", "type": "lookup", "answerable": True, "facts": facts, "l3": {"score": 0.0, "exact": False},
        "advisor": {"mismatches": ["open point duration"]}}}})
    return run


@pytest.fixture(autouse=True)
def fake_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ex, "_seed_facts", lambda domain: SEED)
    spans = {"P-1": {"R-1": [(S12, S12 + 4)], "R-2": [(S24, S24 + 4)]}, "P-2": {"R-3": [(5, 10)]}}
    monkeypatch.setattr(ex, "_l0", lambda domain, paper: spans.get(paper, {}))
    monkeypatch.setattr(ex, "_paper", lambda domain, paper: "P-2 text. Weight fell 0.9 points at week 24." if paper == "P-2" else PAPER)


def test_one_block_per_fact_with_step_passage_row_and_quote(tmp_path: Path) -> None:
    d = ex.explain_data(make_run(tmp_path), "Q-1")
    f1, f2, f3 = d["facts"]
    assert (f1["blame"], f1["right"], f1["lost_at"]) == ("answer", False, "Answer")
    assert "0.52 percentage points" in f1["passage"]["text"]
    assert f1["rows"][0]["quote"] == Q12 and f1["rows"][0]["quote_ok"]
    assert f1["rows"][0]["used_by_answer"] == ["[duration = not stated] -0.52 pp"]
    assert f1["truth"].startswith("veloranide 50 mg vs placebo, week 12, adults")
    assert f2["rows"] == [] and "no row with this value" in f2["why"]
    assert f3["passage"] is None and "did not pick paper P-2" in f3["find"] and "Weight fell" in f3["in_paper"]
    text = ex.explain(make_run(tmp_path, "practice-y"), "Q-1")
    assert "Fact 1 of 3: R-1 in P-1: WRONG, lost at Answer" in text
    assert f"quote: \"{Q12}\"" in text and "Answer used row 0 as: [duration = not stated] -0.52 pp" in text
    assert "Fact 3 of 3: R-3 in P-2: WRONG, lost at Find" in text and "open point duration" in text


def test_not_reported_question(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    ev = json.loads((run / "eval.json").read_text())
    ev["questions"]["Q-1"] = {"qid": "Q-1", "type": "absent", "answerable": False, "facts": [],
                              "l3": {"score": 0, "hallucination": True, "near_miss_trap": True}}
    _write(run / "eval.json", ev)
    d = ex.explain_data(run, "Q-1")
    assert d["facts"] == [] and not d["not_reported"]["right"]
    assert d["not_reported"]["rows"][0]["index"] == 0
    assert "gave a value anyway" in ex.render(d) and "close but different fact" in ex.render(d)


def test_missing_eval_and_unknown_fields_are_tolerated(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "eval.json").unlink()
    d = ex.explain_data(run, "Q-1")
    assert not d["scored"] and d["facts"] == []
    assert "no score in eval.json" in ex.render(d)


@pytest.mark.parametrize(("name", "split"), [("bench-qwen-1", "practice"),
                                             ("practice-z", "test"), ("x", "")])
def test_refuses_runs_that_are_not_practice(tmp_path: Path, name: str, split: str) -> None:
    run = make_run(tmp_path, name, split)
    with pytest.raises(ex.Refused):
        ex.explain_data(run, "Q-1")
    assert ex.main([str(run), "Q-1"]) == 2


def test_main_text_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = make_run(tmp_path)
    assert ex.main([str(run), "Q-1", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["facts"][0]["id"] == "R-1"
    assert ex.main([str(run), "Q-1"]) == 0
    assert capsys.readouterr().out.startswith("Q-1 (lookup): How much does veloranide 50 mg lower HbA1c?")
    assert ex.main([str(run), "Q-9"]) == 2
