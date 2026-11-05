"""The live checker and the paper preview of the proposal form (webapp/evcheck.py)."""
from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence.propose import common
from evidence.tests.propose_support import Scripted, flow
from webapp.app import create_app
from webapp.settings import Settings

from .evidence_world import NAME, EvidenceWorld, paper_ids
from .test_evjobs import entries


@pytest.fixture
def world(ev_world: EvidenceWorld, tmp_path: Path) -> EvidenceWorld:
    return ev_world.copy(tmp_path / "world")


@pytest.fixture
def proposal(world: EvidenceWorld) -> Path:
    return flow(world.proposals / "p1", Scripted(), until="cards")


@pytest.fixture
def client(world: EvidenceWorld) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya"))) as c:  # type: ignore[call-arg]
        yield c


def test_check_endpoint_fast_and_modelless(client: TestClient, proposal: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_model(*a: object, **k: object) -> None:
        raise AssertionError("the check called a model")
    monkeypatch.setattr(common, "ask", no_model)
    monkeypatch.setattr("evidence.propose.critic.ask", no_model)
    start = time.monotonic()
    response = client.post("/api/ev/proposals/p1/check", json={"decisions": entries(proposal)})
    assert response.status_code == 200 and time.monotonic() - start < 1
    assert all(p["severity"] in ("serious", "advisory") for p in response.json()["problems"])


def test_check_reports_a_refused_decision_and_a_unknown_proposal(client: TestClient, proposal: Path) -> None:
    problems = client.post("/api/ev/proposals/p1/check", json={"decisions": entries(proposal)[1:]}).json()["problems"]
    assert problems and problems[0]["check"] == "decision" and problems[0]["severity"] == "serious"
    assert client.post("/api/ev/proposals/nope/check", json={"decisions": []}).status_code == 404


def test_check_finds_a_serious_problem_in_the_applied_draft(client: TestClient, proposal: Path) -> None:
    change = {"screen": {"choice": "custom", "value": {"question": "q?", "terms": ["zzzunrelated"]}, "by": "aditya"}}
    problems = client.post("/api/ev/proposals/p1/check", json={"decisions": entries(proposal, change)}).json()["problems"]
    found = [p for p in problems if p["check"] == "terms_cover_synonyms"]
    assert found and found[0]["card"] == "screen" and found[0]["severity"] == "serious"
    assert problems[0]["severity"] == "serious"


def test_preview_hits_terms(client: TestClient, proposal: Path, world: EvidenceWorld) -> None:
    corpus = f"{NAME}-mixed"
    hit = None
    for paper in paper_ids(world.corpora / corpus):
        data = client.get("/api/ev/proposals/p1/preview", params={"corpus": corpus, "paper": paper}).json()
        if data["hits"]:
            hit = data
            break
    assert hit is not None
    first = hit["hits"][0]
    assert hit["text"][first["start"]:first["end"]].casefold() == first["what"].casefold()
    assert first["card"] in {"screen", "roles", "metrics", "method_kinds"}
    assert [h["start"] for h in hit["hits"]] == sorted(h["start"] for h in hit["hits"])
    assert client.get("/api/ev/proposals/p1/preview", params={"corpus": corpus, "paper": "zzz"}).status_code == 404


def inventory_proposal(world: EvidenceWorld) -> Path:
    from evidence.tests.test_cards_kinds import _frame
    return flow(world.proposals / "inv", Scripted(frame_reply=_frame("inventory")), until="cards")


def test_check_survives_a_decision_that_cannot_be_applied(client: TestClient, proposal: Path) -> None:
    bad = {"cascade": {"choice": "custom", "value": {"extractors": {"zzz": ["regex_metric"]}, "strategy": "gaps"},
                       "by": "aditya"}}
    response = client.post("/api/ev/proposals/p1/check", json={"decisions": entries(proposal, bad)})
    assert response.status_code == 200
    problem = response.json()["problems"][0]
    assert (problem["check"], problem["severity"], problem["card"]) == ("decision", "serious", "cascade")
    assert "zzz" in problem["message"]


def test_every_check_maps_to_a_card_of_the_kind_or_none() -> None:
    from evidence.propose import cards as cards_module, critic
    from webapp import evcheck
    for kind in ("effect", "consistency", "inventory", "best"):
        ids = {c["id"] for c in cards_module.for_kind(kind)}
        for check in critic.DETERMINISTIC:
            assert evcheck.card_for(check, kind) in ids | {None}, (kind, check)
    assert evcheck.card_for("regex_matches_enums", "inventory") == "list_target"
    assert evcheck.card_for("label_complete", "inventory") is None
    assert evcheck.card_for("outcomes_complete", "effect") == "metrics"


def test_check_cards_of_an_inventory_proposal_exist(client: TestClient, world: EvidenceWorld) -> None:
    d = inventory_proposal(world)
    change = {"screen": {"choice": "custom", "value": {"question": "q?", "terms": ["zzzunrelated"]}, "by": "aditya"}}
    problems = client.post("/api/ev/proposals/inv/check", json={"decisions": entries(d, change)}).json()["problems"]
    ids = {c["id"] for c in __import__("evidence.propose.cards", fromlist=["x"]).for_kind("inventory")}
    assert problems and all(p["card"] in ids | {None} for p in problems)


def test_preview_tags_roles_and_metrics_only_for_effect_kinds(client: TestClient, world: EvidenceWorld) -> None:
    inventory_proposal(world)
    corpus = f"{NAME}-mixed"
    cards_seen: set[str] = set()
    for paper in paper_ids(world.corpora / corpus)[:5]:
        data = client.get("/api/ev/proposals/inv/preview", params={"corpus": corpus, "paper": paper}).json()
        cards_seen |= {h["card"] for h in data["hits"]}
    assert cards_seen and cards_seen <= {"screen", "method_kinds"}
