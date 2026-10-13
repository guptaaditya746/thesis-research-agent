"""gold/argilla_io.py without a server: settings from the specs, record content, idempotent push, pull."""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from agent.tests.conftest import fixture
from gold import argilla_io, review

from .fixtures import ANSWERS, CONCEPT, QID, Env, FakeArgilla, cid, env, fake  # noqa: F401


def test_settings_follow_the_specs(fake: FakeArgilla) -> None:
    for dataset, spec in argilla_io.SPECS.items():
        built = argilla_io.settings(dataset, fake)
        assert [(f.name, f.required, f.use_markdown) for f in built.fields] == [(n, True, True) for n, _ in spec.fields]
        assert [(q.name, q.required) for q in built.questions] == [(n, r) for n, _, _, r in spec.questions]
        labels = {q.name: q.labels for q in built.questions if hasattr(q, "labels")}
        assert labels == {n: list(lab) for n, _, lab, _ in spec.questions if lab}
        assert [(m.name, m.visible_for_annotators) for m in built.metadata] == [(n, v) for n, _, _, v in spec.metadata]
        assert built.distribution.min_submitted == (2 if dataset == "overlap" else 1)
    hidden = {d: [n for n, _, _, v in s.metadata if not v] for d, s in argilla_io.SPECS.items()}
    assert hidden["review"] == ["stratum"] and hidden["judge"] == ["condition"]
    assert set(argilla_io.SPECS) == set(argilla_io.DATASETS)


def review_items(e: Env) -> dict[str, dict]:
    return {item["id"]: item for item in review.pool(e.root, QID)}


def test_review_record_shows_the_quote_in_its_passage(env: Env) -> None:
    corpus = review.Corpus(env.corpus)
    item = review_items(env)[cid(3)]
    passage = argilla_io.candidate_passage(corpus, item)
    assert "<mark>math reasoning using GSM8K</mark>" in passage
    record = argilla_io.review_record(item, question="Q?", concept_md=argilla_io.concept_markdown(CONCEPT),
                                      passage_md=passage)
    assert record["id"] == cid(3) and record["question_id"] == QID and record["stratum"] == "triaged"
    assert record["fact"].startswith("**p5** — _evaluatesOn_ — **GSM8K**") and "target = GSM8K" in record["fact"]
    assert record["quote"] == "`p5.md`\n\n> math reasoning using GSM8K"
    moved = {**item, "anchor": {**item["anchor"], "start": item["anchor"]["start"] + 3}}  # offsets no longer hold
    assert argilla_io.candidate_passage(corpus, moved) == passage  # found again by its quote
    missing = argilla_io.candidate_passage(corpus, review_items(env)[cid(6)])
    assert "could not be found in `p3.md` (not_found)" in missing


def test_passage_window_cuts_at_line_ends() -> None:
    text = "intro line\n" + "a" * 50 + "\nthe quote is here\n" + "b" * 50 + "\nlast"
    start = text.index("quote")
    assert argilla_io.window(text, start, start + 5, chars=30) == (text.index("the quote"), text.index("\nlast") - 51)
    assert argilla_io.passage_markdown(text, start, start + 5, chars=1000) == \
        text[:start] + "<mark>quote</mark>" + text[start + 5:]


def test_concept_and_scope_markdown() -> None:
    graph = argilla_io.concept_markdown(CONCEPT)
    assert "**Benchmarks used by RAG papers**" in graph and "Paper —evaluatesOn→ Dataset [metric]" in graph
    table = argilla_io.concept_markdown(fixture("concept_table.json"))
    assert "one row per author" in table and "first_author_papers (integer)" in table
    assert "No concept" in argilla_io.concept_markdown(None)
    scope = argilla_io.scope_markdown({"rows": [{"key": "p1 evaluatesOn Spider"}]},
                                      [{"paper_id": "p1", "status": "relevant"}, {"paper_id": "p2", "status": "no_text"}])
    assert scope.startswith("D has 1 rows from 1 papers screened relevant.") and "`p1.md`" in scope


def test_push_is_idempotent_and_keeps_responses(env: Env, fake: FakeArgilla) -> None:
    corpus = review.Corpus(env.corpus)
    records = [argilla_io.review_record(i, question="Q?", concept_md="C", passage_md=argilla_io.candidate_passage(corpus, i))
               for i in review_items(env).values()]
    assert argilla_io.push(fake, "review", records) == 7
    dataset = fake.dataset("review")
    dataset.answer(cid(1), "aditya", **ANSWERS[cid(1)])
    assert argilla_io.push(fake, "review", [{**r, "question": "Q, reworded?"} for r in records]) == 7
    assert len(dataset.rows) == 7 and dataset.rows[cid(1)]["fields"]["question"] == "Q, reworded?"
    assert len(dataset.responses[cid(1)]) == 2  # label and vital stay
    assert argilla_io.push(fake, "missing", []) == 0 and ("thesis", "gold-v1-missing") not in fake.store


def test_pull_gives_plain_records_with_user_names(env: Env, fake: FakeArgilla) -> None:
    argilla_io.push(fake, "missing", [argilla_io.missing_record(QID, question="Q?", concept_md="C", scope_md="S")])
    fake.dataset("missing").answer(f"missing-{QID}", "aditya", missing="a | b | c | p1.md | q", done="yes")
    out = argilla_io.pull(fake)
    assert set(out) == {"missing"}  # datasets that do not exist are left out
    record = out["missing"][0]
    assert record["id"] == f"missing-{QID}" and record["metadata"] == {"question_id": QID}
    assert sorted((r["question"], r["user"], r["status"]) for r in record["responses"]) == [
        ("done", "aditya", "submitted"), ("missing", "aditya", "submitted")]
    assert review.submitted(record) == {"aditya": {"missing": "a | b | c | p1.md | q", "done": "yes"}}


def test_client_reads_the_environment_when_made(monkeypatch: pytest.MonkeyPatch) -> None:
    import argilla as rg

    seen = []
    monkeypatch.setattr(rg, "Argilla", lambda **kw: seen.append(kw) or SimpleNamespace(**kw))
    monkeypatch.setenv("ARGILLA_API_URL", "http://127.0.0.1:36901")
    monkeypatch.setenv("ARGILLA_API_KEY", "secret")
    argilla_io.client()
    assert seen == [{"api_url": "http://127.0.0.1:36901", "api_key": "secret"}]

    def refuse(**kw: object) -> None:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(rg, "Argilla", refuse)
    with pytest.raises(SystemExit, match="omen-tunnels") as exc:
        argilla_io.client()
    assert "secret" not in str(exc.value)
