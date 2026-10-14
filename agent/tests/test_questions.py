"""The 12 questions (row 2.3) and the run manifests built on them (row 2.9)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from agent import schema
from agent.batch import Manifest
from agent.concept_step import QUESTIONS_FILE, load_questions

from .conftest import REPO

QUESTIONS = REPO / QUESTIONS_FILE
MANIFESTS = REPO / "agent" / "manifests"
# The slots of docs/e2e-build-plan.md, "The 12 questions": a question may be replaced (questions/README.md),
# its id and category stay.
SLOTS = {f"q{n:02d}": "corpus_wide" if n <= 6 else "ambiguous" for n in range(1, 13)}


def test_questions_file_has_the_twelve_slots() -> None:
    raw = QUESTIONS.read_bytes()
    assert b"\r" not in raw
    assert schema.check("questions", json.loads(raw)) == []
    questions = load_questions(QUESTIONS)
    assert {q["id"]: q["category"] for q in questions} == SLOTS
    assert [q["id"] for q in questions] == sorted(SLOTS)
    texts = [q["question"] for q in questions]
    assert len(set(texts)) == 12 and all(t == t.strip() for t in texts)
    # Every question says where it comes from and how it was reworded; no search index any more.
    assert all(re.fullmatch(r"nlp\d+|own", q["source"]) and q["notes"] for q in questions)
    assert not any("indexed" in t for t in texts)


def test_questions_are_the_ones_the_plan_lists() -> None:
    """Until a question is replaced: the 12 of the plan, with their labelling-repo ids."""
    plan = (REPO / "docs" / "e2e-build-plan.md").read_text(encoding="utf-8")
    for q in load_questions(QUESTIONS):
        assert f"| {q['id']} | {q['category']} | {q['question']} | {q['source']} |" in plan, q["id"]


@pytest.mark.parametrize("change, problem", [
    ({"id": "Q1"}, "does not match"), ({"category": "hard"}, "is not one of"), ({"question": "No question mark"},
                                                                                "does not match"),
    ({"extra": 1}, "Additional properties"), ({"notes": None}, "is not of type"),
])
def test_questions_schema_problems(change: dict, problem: str) -> None:
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    data["questions"][0] |= change
    assert any(problem in p for p in schema.check("questions", data))


def test_manifests_name_the_questions_and_validate() -> None:
    questions = {q["id"]: q for q in load_questions(QUESTIONS)}
    for path in sorted(MANIFESTS.glob("*.json")):
        assert b"\r" not in path.read_bytes(), path
        manifest = Manifest.load(path)  # the batch schema, plus unique ids
        for entry in manifest.data["questions"]:
            assert entry["id"] in questions, (path.name, entry["id"])
            assert Path(entry["concept"]).as_posix() == f"concepts/{entry['id']}/concept.json"
    full = Manifest.load(MANIFESTS / "m4-72.json")
    assert [q["id"] for q in full.data["questions"]] == list(questions)
    assert len(full.plan()) == 72


def test_smoke_manifest_is_one_question_of_each_kind() -> None:
    questions = {q["id"]: q for q in load_questions(QUESTIONS)}
    smoke = Manifest.load(MANIFESTS / "e2e-smoke.json")
    ids = [q["id"] for q in smoke.data["questions"]]
    assert ids == ["q01", "q10"]
    assert [questions[i]["category"] for i in ids] == ["corpus_wide", "ambiguous"]
    # claim_on only: claim_off and the attach step are dropped from the design (14 Oct).
    assert smoke.data["conditions"] == ["claim_on"] and smoke.data["repeats"] == 2
    plan = smoke.plan()
    assert [e.key for e in plan] == ["q01-claim_on-r1", "q10-claim_on-r1", "q01-claim_on-r2", "q10-claim_on-r2"]
    assert len({e.seed for e in plan}) == 4
    # No budget of its own: the runs take the `agent run` defaults (work package A owns them).
    assert "budget" not in smoke.data and "attach_budget" not in smoke.data
    assert smoke.runs_root.as_posix() == "runs/e2e-smoke"
