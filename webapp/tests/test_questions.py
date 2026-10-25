"""The questions file (evidence/questions.yaml, webapp/evquestions.py) and /api/ev/questions."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence.tests.propose_support import QUESTION
from webapp.app import create_app
from webapp.evquestions import load
from webapp.settings import REPO, Settings

PROTOCOLS = REPO / "evidence" / "protocols"


def test_the_committed_file_offers_the_rag_question() -> None:
    q = load(REPO / "evidence" / "questions.yaml", PROTOCOLS)[0]
    assert (q.id, q.question, q.protocol, q.agentic_protocol, q.vocab) == (
        "rag-factuality", QUESTION, "rag-factuality", "rag-factuality-agentic", "rag-factuality")


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "questions.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(("text", "message"), [
    ("questions: []", "questions"),
    ("questions:\n  - {id: ../x, question: 'Q?'}", "id"),
    ("questions:\n  - {id: a, question: ''}", "question"),
    ("questions:\n  - {id: a, question: ' Q?'}", "spaces"),
    ("questions:\n  - {id: a, question: 'Q?'}\n  - {id: a, question: 'R?'}", "unique"),
    ("questions:\n  - {id: a, question: 'Q?', extra: 1}", "extra"),
    ("questions:\n  - {id: a, question: 'Q?', vocab: ../v}", "vocab"),
    ("questions: [unclosed", "not YAML"),
    ("questions:\n  - {id: a, question: 'Q?', protocol: evidence/protocols/rag-factuality.yaml}", "asks"),
    (f"questions:\n  - {{id: a, question: '{QUESTION}', protocol: evidence/protocols/nope.yaml}}", "no such file"),
    (f"questions:\n  - {{id: a, question: '{QUESTION}', protocol: pyproject.toml}}", "directly in"),
    (f"questions:\n  - {{id: a, question: '{QUESTION}', protocol: evidence/protocols/../../pyproject.toml}}",
     "directly in"),
])
def test_a_broken_file_is_refused_with_its_problem(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load(write(tmp_path, text), PROTOCOLS)


def test_a_question_without_a_protocol_needs_a_proposal(tmp_path: Path) -> None:
    [q] = load(write(tmp_path, "questions:\n  - {id: new-q, question: 'Does X improve Y?'}"), PROTOCOLS)
    assert q.protocol is None and q.agentic_protocol is None and q.vocab is None


def test_a_protocol_that_does_not_parse_is_refused(tmp_path: Path) -> None:
    protocols = tmp_path / "protocols"
    protocols.mkdir()
    (protocols / "bad.yaml").write_text("id: bad\nversion: 2\nquestion: Q?\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not validate"):
        load(write(tmp_path, "questions:\n  - {id: a, question: 'Q?', protocol: protocols/bad.yaml}"), protocols,
             base=tmp_path)


def test_the_api_lists_questions_with_their_proposals(ev_world, tmp_path: Path) -> None:  # noqa: ANN001
    with TestClient(create_app(Settings(EV=ev_world.root))) as c:  # type: ignore[call-arg]
        q = c.get("/api/ev/questions").json()[0]
        assert q["id"] == "rag-factuality" and q["protocol"] == "rag-factuality"
        assert q["proposals"] == ["rag-factuality"]   # the world's proposal asks the same question
        assert c.get("/api/ev/questions/rag-factuality").json() == q
        assert c.get("/api/ev/questions/nope").status_code == 404
    broken = write(tmp_path, "questions: [unclosed")
    with TestClient(create_app(Settings(EV=ev_world.root, EV_QUESTIONS=broken))) as c:  # type: ignore[call-arg]
        response = c.get("/api/ev/questions")
        assert response.status_code == 409 and "not YAML" in response.json()["detail"]
    with TestClient(create_app(Settings(EV=ev_world.root, EV_QUESTIONS=tmp_path / "none.yaml"))) as c:  # type: ignore[call-arg]
        assert c.get("/api/ev/questions").json() == []
