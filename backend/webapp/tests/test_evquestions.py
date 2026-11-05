"""The ten questions in the app: each entry carries its kind (webapp/evquestions.py over evidence/questions.py)."""
from __future__ import annotations

from pathlib import Path

import repo_paths

import pytest
from fastapi.testclient import TestClient

from evidence.tests.propose_support import QUESTION
from webapp.app import create_app
from webapp.evquestions import load
from webapp.settings import REPO, Settings

PACK = repo_paths.DOMAINS / "rag"   # question files name protocols relative to the pack folder
PROTOCOLS = PACK / "protocols"
KINDS = {"rag-factuality": "effect", "rag-hallucination": "effect", "rag-latency": "effect",
         "inv-metrics": "inventory", "inv-methods": "inventory", "inv-datasets": "inventory",
         "cons-accuracy": "consistency", "cons-hallucination": "consistency",
         "best-accuracy": "best", "best-hallucination": "best"}


def test_questions_api_lists_ten_with_kind(ev_world) -> None:  # noqa: ANN001
    with TestClient(create_app(Settings(EV=ev_world.root))) as c:  # type: ignore[call-arg]
        listed = c.get("/api/ev/questions").json()
    assert {q["id"]: q["kind"] for q in listed} == KINDS
    assert all(q["protocol"] == q["id"] for q in listed)


def test_an_entry_whose_kind_differs_from_its_protocol_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "questions.yaml"
    path.write_text(f"questions:\n  - {{id: a, question: '{QUESTION}', kind: best, truth: {{metric: factual_accuracy}},"
                    " protocol: protocols/rag-factuality.yaml}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="kind"):
        load(path, PROTOCOLS, base=PACK)


@pytest.mark.parametrize(("entry", "message"), [
    ("kind: nope", "kind"),
    ("kind: effect, truth: {target: metric}", "target"),
    ("kind: inventory, truth: {target: method}", "target"),
    ("kind: best, truth: {min_effect: 0.01}", "min_effect"),
    ("kind: effect, truth: {metric: x, min_effect: 0}", "min_effect"),
])
def test_truth_must_fit_the_kind(tmp_path: Path, entry: str, message: str) -> None:
    path = tmp_path / "questions.yaml"
    path.write_text(f"questions:\n  - {{id: a, question: 'Q?', {entry}}}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load(path, PROTOCOLS, base=PACK)
