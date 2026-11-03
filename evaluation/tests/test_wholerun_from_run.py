"""The engine run -> wholerun.Answer adapter (Wave 2 Task 8.1): what a plan run's answer.json and claims say, in the
shape `score` reads."""
from __future__ import annotations

import json
from pathlib import Path

from evaluation.wholerun import Answer, RealQuestion, from_run, score


def run_dir(tmp: Path, lines: list[dict], claims: list[dict] | None = None, synthesis: dict | None = None) -> Path:
    root = tmp / "run"
    root.mkdir()
    answer = {"system": "plan", "lines": lines, "answer": {"text": "x"}, "synthesis": synthesis or {"studies": []}}
    (root / "answer.json").write_text(json.dumps(answer), encoding="utf-8")
    rows = [{"item_id": f"cl-{n}", "evidence_type": "claim", "fields": c, "spans": [], "links": {}}
            for n, c in enumerate(claims or [])]
    (root / "evidence.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return root


def q(kind: str, gold: dict) -> RealQuestion:
    return RealQuestion("q1", "Which?", "cs", Path("."), gold, kind)  # type: ignore[arg-type]


def done(rows: list[dict], lid: str = "l1") -> dict:
    return {"id": lid, "question": "?", "status": "done", "rows": rows, "text": f"{len(rows)} found"}


def test_rank_reads_the_first_answered_line_paper_column_first(tmp_path: Path) -> None:
    root = run_dir(tmp_path, [{"id": "l0", "question": "?", "status": "failed", "rows": [], "text": "failed: x"},
                              done([{"thing": "m1", "paper": "P2", "score": 0.9}, {"thing": "m2", "paper": "P1", "score": 0.8},
                                    {"thing": "m3", "paper": "P2", "score": 0.7}])])
    answer = from_run(root, q("rank", {"ranking": ["P2", "P1"]}))
    assert answer.ranking == ["P2", "P1"]
    assert score(answer, q("rank", {"ranking": ["P2", "P1"]}))["top1"] == 1


def test_list_takes_the_first_column_once_each(tmp_path: Path) -> None:
    root = run_dir(tmp_path, [done([{"item": "SQuAD", "papers": 2}, {"item": "MNLI", "papers": 1},
                                    {"item": "SQuAD", "papers": 1}])])
    assert from_run(root, q("list", {"items": []})).names == ["SQuAD", "MNLI"]


def test_compare_maps_effect_rows_to_directions_and_a_conclusion(tmp_path: Path) -> None:
    rows = [{"paper": "S1", "direction": "supports"}, {"paper": "S2", "direction": "contradicts"},
            {"paper": "S3", "direction": "supports"}, {"paper": "S4", "direction": "undetermined"}]
    answer = from_run(run_dir(tmp_path, [done(rows)]), q("compare", {"directions": {}}))
    assert answer.directions == {"S1": "improves", "S2": "worsens", "S3": "improves"}
    assert answer.conclusion == "improves"


def test_compare_falls_back_to_the_synthesis_studies(tmp_path: Path) -> None:
    synthesis = {"studies": [{"document": "S1", "direction": "neutral"}, {"document": "S2", "direction": "undetermined"}]}
    answer = from_run(run_dir(tmp_path, [], synthesis=synthesis), q("compare", {"directions": {}}))
    assert answer.directions == {"S1": "no_effect"} and answer.conclusion == "no_effect"


def test_claims_are_about_the_gold_conclusion_ids(tmp_path: Path) -> None:
    claims = [{"subject": "drug", "relation": "lowers", "direction": "improves"},
              {"subject": "drug", "relation": "helps", "direction": "improves"},
              {"subject": "drug", "relation": "hurts", "direction": "worsens"},
              {"subject": "drug", "relation": "is", "direction": None}]
    gold = {"conclusions": [{"id": "CD001", "direction": "improves"}]}
    answer = from_run(run_dir(tmp_path, [], claims=claims), q("claims", gold))
    assert answer.claims == [{"about": "CD001", "direction": "improves"}]
    assert score(answer, q("claims", gold))["recall"] == 1.0


def test_an_empty_run_gives_an_empty_answer(tmp_path: Path) -> None:
    assert from_run(run_dir(tmp_path, []), q("rank", {"ranking": ["a"]})) == Answer()
