"""The protocols and the question list live in the domain pack (domains/<pack>/), not in the evidence code."""
from __future__ import annotations

import inspect
from pathlib import Path

from evidence import questions
from evidence.pack import DOMAINS, load_pack, protocol_path, questions_path
from evidence.propose import frame

REPO = Path(__file__).resolve().parents[2]
OLD = "/".join(("evidence", "protocols"))   # spelled in two parts so this file does not match itself
SKIP = {".venv", "node_modules", ".git"}


def test_pack_paths_point_into_the_pack_folder() -> None:
    assert protocol_path("rag", "rag-factuality") == DOMAINS / "rag" / "protocols" / "rag-factuality.yaml"
    assert questions_path("rag") == DOMAINS / "rag" / "questions.yaml"


def test_no_code_refers_to_old_protocol_folder() -> None:
    hits = [p for p in REPO.rglob("*.py")
            if not SKIP & set(p.relative_to(REPO).parts) and OLD in p.read_text(encoding="utf-8")]
    assert hits == []


def test_questions_point_to_existing_pack_protocols() -> None:
    assert questions.DEFAULT == questions_path("rag")
    for q in questions.load():
        assert q.protocol is not None
        assert protocol_path("rag", Path(q.protocol).stem).exists()
        assert (questions.DEFAULT.parent / q.protocol).resolve() == protocol_path("rag", q.id).resolve()


def test_propose_frame_examples_come_from_pack() -> None:
    assert "factual_accuracy" not in inspect.getsource(frame)


def test_agentic_task_takes_its_examples_from_the_pack() -> None:
    from evaluation.tests.agentic_fakes import MEASUREMENT_SCHEMA, task as make_task

    from evidence.agentic import task

    source = inspect.getsource(task).casefold()
    assert "retriev" not in source and "hallucination" not in source
    words = load_pack("rag").extractor_config("condition", "agentic")
    assert words == {"display": {"treatment": "RAG system", "control": "closed-book model"},
                     "metric_names": ["factual_accuracy", "hallucination_rate"]}
    t = make_task("condition")
    item = task.concept_for(t, MEASUREMENT_SCHEMA, {}, [], "S001.md", 10, words=words)["scope"]["item"]
    assert "closed-book model" in item and "RAG system" in item
    bare = task.concept_for(t, MEASUREMENT_SCHEMA, {}, [], "S001.md", 10)["scope"]["item"]
    assert "RAG" not in bare and "a system or setting the paper compares" in bare
