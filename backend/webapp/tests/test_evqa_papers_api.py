"""/api/evqa/papers: the Workbench paper pane over the medical briefs, with and without a paper.md."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from evqa.eval import dataset
from evqa.seed import pview
from evqa.seed import questions as seed_questions
from webapp.evqa_papers_api import router

FIXTURE = Path(__file__).resolve().parents[2] / "evqa" / "tests" / "fixtures" / "P-med-01" / "paper.md"


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


@pytest.fixture
def dataset_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The real briefs (data/seed/medical/papers), and a temp dataset folder holding only the fixture paper.md
    for P-med-01, so the other papers count as not written yet."""
    root = tmp_path / "data" / "dataset"
    (root / "medical" / "P-med-01").mkdir(parents=True)
    shutil.copy(FIXTURE, root / "medical" / "P-med-01" / "paper.md")
    monkeypatch.setattr(pview, "paper_file", lambda d, p: root / d / p / "paper.md")
    monkeypatch.setattr(dataset, "DATASET", root)
    monkeypatch.setattr(dataset, "domain_dir", lambda d: tmp_path / "data" / "seed" / d)
    return root


def test_paper_list_and_briefs(dataset_copy: Path) -> None:
    c = client()
    rows = {p["id"]: p for p in c.get("/api/evqa/papers/medical").json()}
    seed = {p["id"] for p in seed_questions._blueprint("medical")["papers"]}     # every paper the seed plans
    assert seed <= set(rows) and len(rows) >= 5 and all(p["has_brief"] for p in rows.values())
    assert rows["P-med-01"]["has_paper"] and rows["P-med-01"]["l0"]["found"] == 18
    assert not rows["P-med-02"]["has_paper"] and rows["P-med-02"]["l0"] is None
    p2 = c.get("/api/evqa/papers/medical/P-med-02").json()
    assert p2["paper"] is None and p2["l0"] is None
    assert p2["briefs"]["experimental_log.md"].startswith("# Experimental Log")


def test_paper_with_l0_spans(dataset_copy: Path) -> None:
    p = client().get("/api/evqa/papers/medical/P-med-01").json()
    assert p["paper"].startswith("# Brenoxalin") and p["l0"]["stored"] is False
    span = p["l0"]["facts"][0]["spans"][0]
    assert p["paper"][span["start"]:span["end"]] == "−0.46"
    dataset.check("medical", "P-med-01")       # once L0 is written, the view reads the file
    assert client().get("/api/evqa/papers/medical/P-med-01").json()["l0"]["stored"] is True


def test_refuses_unknown_things() -> None:
    c = client()
    assert c.get("/api/evqa/papers/nope").status_code == 404
    assert c.get("/api/evqa/papers/medical/P-med-99").status_code == 404
