"""Builds-on through OpenAlex (Task 5.2): recorded HTTP fixtures, no network."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from agent.anchor import selector_at, text_sha256
from evidence import openalex, steps
from evidence.contract import Span
from modelcall.cache import JsonlCache
from modelcall.dspy_lm import RecordedLM

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "openalex" / "http.json").read_text(encoding="utf-8"))
RUN_DOCS = {"S001": "# Retrieval-Augmented Generation for Knowledge-Intensive NLP\n\nDOI 10.1234/rag.2020\n\nWe study...",
            "S002": "# Another Study Entirely\n\nBody."}


def fetch(url: str):
    return FIXTURE.get(url)     # None = 404


def span() -> Span:
    text = "We build on Lewis et al. (2020)."
    return Span.of("link", selector_at(text, 0, len(text), file="papers/S002.md", sha256=text_sha256(text)))


def client(tmp_path, f=fetch) -> openalex.OpenAlex:
    return openalex.OpenAlex(JsonlCache(tmp_path / "http.jsonl"), fetch=f)


def test_doi_resolves_to_run_doc(tmp_path):
    rec = client(tmp_path).resolve("Lewis et al. 2020", "10.1234/rag.2020", None, RUN_DOCS, subject_doc="S002", span=span())
    assert (rec.object_doc, rec.outside_set, rec.object_ref) == ("S001", False, "10.1234/rag.2020")
    assert rec.subject_doc == "S002" and rec.relation == "cites"


def test_arxiv_id_resolves_through_the_arxiv_doi(tmp_path):
    rec = client(tmp_path).resolve("Lewis et al.", None, "2005.11401", RUN_DOCS, subject_doc="S002", span=span())
    assert rec.object_doc == "S001" and rec.object_ref == "2005.11401"


def test_outside_set_kept(tmp_path):
    rec = client(tmp_path).resolve("Somebody 2019", "10.9999/outside.2019", None, RUN_DOCS, subject_doc="S002", span=span())
    assert (rec.object_doc, rec.outside_set, rec.object_ref) == (None, True, "10.9999/outside.2019")


def test_title_search_and_unknown_work_kept(tmp_path):
    c = client(tmp_path)
    found = c.resolve("Dense Passage Retrieval for Open-Domain QA", None, None, RUN_DOCS, subject_doc="S002", span=span())
    assert found.outside_set and found.object_ref == "Dense Passage Retrieval for Open-Domain QA"
    lost = c.resolve("Totally Unknown Work", None, None, RUN_DOCS, subject_doc="S002", span=span())
    assert lost.outside_set and lost.object_doc is None and lost.object_ref == "Totally Unknown Work"


def test_offline_replay_uses_record(tmp_path):
    first = client(tmp_path)
    a = first.resolve("x", "10.1234/rag.2020", None, RUN_DOCS, subject_doc="S002", span=span())
    first.references("doi:10.1234/rag.2020")
    calls: list[str] = []

    def never(url: str):
        calls.append(url)
        raise AssertionError("network used")

    replay = openalex.OpenAlex(JsonlCache(tmp_path / "http.jsonl"), fetch=never, offline=True)
    assert replay.resolve("x", "10.1234/rag.2020", None, RUN_DOCS, subject_doc="S002", span=span()) == a
    assert replay.references("doi:10.1234/rag.2020") == ["https://openalex.org/W5", "https://openalex.org/W6"]
    assert calls == []
    with pytest.raises(openalex.NotRecorded):
        replay.resolve("x", "10.9999/outside.2019", None, RUN_DOCS, subject_doc="S002", span=span())


def test_a_request_is_made_once(tmp_path):
    seen: list[str] = []
    c = client(tmp_path, lambda u: seen.append(u) or fetch(u))
    c.resolve("x", "10.1234/rag.2020", None, RUN_DOCS, subject_doc="S002", span=span())
    c.resolve("x", "10.1234/rag.2020", None, RUN_DOCS, subject_doc="S002", span=span())
    assert len(seen) == 1


def test_module_functions_use_the_configured_client(tmp_path):
    openalex.configure(client(tmp_path))
    rec = openalex.resolve("x", "10.1234/rag.2020", None, RUN_DOCS, subject_doc="S002", span=span())
    assert rec.object_doc == "S001"
    assert openalex.references("doi:10.1234/rag.2020") == ["https://openalex.org/W5", "https://openalex.org/W6"]


def test_read_link_open_relation(tmp_path, monkeypatch):
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    asked: list[str] = []

    def ask(prompt: str, **_) -> str:
        asked.append(prompt)
        return json.dumps({"relation": "builds on", "object": "Lewis et al. (2020)"})

    steps.configure(RecordedLM("alias", ask, cache=None))
    assert openalex.read_link("We build on Lewis et al. (2020).") == ("builds on", "Lewis et al. (2020)")


def test_read_link_calls_stay_under_their_own_ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    seen: dict[str, list[str]] = {"a": [], "b": []}

    class Ctx:
        def __init__(self, name: str):
            self.name = name

        def dspy_lm(self, purpose: str):
            def ask(prompt: str, **_):
                seen[self.name].append(prompt[prompt.index("[user]"):])
                return json.dumps({"relation": "extends", "object": "X"})
            return RecordedLM("alias", ask, cache=None)

    barrier = threading.Barrier(2)

    def work(n: str) -> None:
        barrier.wait()
        for i in range(6):
            openalex.read_link(f"We extend work {n}{i}.", ctx=Ctx(n.lower()))

    ts = [threading.Thread(target=work, args=(n,)) for n in "AB"]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(seen["a"]) == 6 and len(seen["b"]) == 6
    assert all("work A" in p for p in seen["a"]) and all("work B" in p for p in seen["b"])
