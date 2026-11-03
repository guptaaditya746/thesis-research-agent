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


class Ctx:
    def __init__(self, run_dir, mode="run"):
        self.run_dir, self.mode = run_dir, mode


def client(tmp_path, f=fetch) -> openalex.OpenAlex:
    return openalex.OpenAlex(JsonlCache(tmp_path / "http.jsonl"), fetch=f)


def test_cache_is_required():
    with pytest.raises(ValueError):
        openalex.OpenAlex(None)  # type: ignore[arg-type]


def test_doi_resolves_to_run_doc(tmp_path):
    rec = client(tmp_path).resolve("Lewis et al. 2020", "10.1234/rag.2020", None, RUN_DOCS, subject_doc="S002", span=span())
    assert (rec.object_doc, rec.outside_set, rec.object_ref) == ("S001", False, "10.1234/rag.2020")
    assert rec.subject_doc == "S002" and rec.relation == "cites"


def test_doi_of_run_doc_unknown_to_openalex_still_matches_by_doi_boundary(tmp_path):
    docs = {"S001": "# Some Title Here For It\n\nDOI 10.1234/rag.20201\n"}
    rec = client(tmp_path).resolve("x", "10.1234/rag.2020", None, docs, subject_doc="S002", span=span())
    assert rec.outside_set   # 10.1234/rag.2020 is not the start of the longer DOI ...rag.20201


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


def test_synthetic_paper_unknown_to_openalex_is_in_the_set(tmp_path):
    docs = {"S007": "# A Synthetic Study Of Caching Layers\n\nBody."}
    seen: list[str] = []
    rec = client(tmp_path, lambda u: seen.append(u) or None).resolve(
        "Prior work: A Synthetic Study of Caching Layers (2024)", None, None, docs, subject_doc="S002", span=span())
    assert (rec.object_doc, rec.outside_set) == ("S007", False)
    assert seen == []   # found in the run itself


def test_wrong_first_search_hit_is_not_trusted(tmp_path):
    rec = client(tmp_path).resolve("Retrieval Study Quoted Wrongly", None, None, RUN_DOCS, subject_doc="S002", span=span())
    assert rec.outside_set and rec.object_ref == "Retrieval Study Quoted Wrongly"   # not the unrelated work's DOI


def test_offline_replay_uses_record(tmp_path):
    ctx = Ctx(tmp_path)
    a = openalex.resolve("x", "10.9999/outside.2019", None, RUN_DOCS, ctx, subject_doc="S002", span=span(), fetch=fetch)
    openalex.references("doi:10.1234/rag.2020", ctx, fetch=fetch)
    assert (tmp_path / "openalex.jsonl").exists()

    def never(url: str):
        raise AssertionError("network used")

    replay = Ctx(tmp_path, "replay")
    assert openalex.resolve("x", "10.9999/outside.2019", None, RUN_DOCS, replay, subject_doc="S002", span=span(),
                            fetch=never) == a
    assert openalex.references("doi:10.1234/rag.2020", replay, fetch=never) == [
        "https://openalex.org/W5", "https://openalex.org/W6"]


def test_replay_miss_raises_and_never_fetches(tmp_path):
    calls: list[str] = []
    with pytest.raises(openalex.NotRecorded):
        openalex.resolve("x", "10.9999/outside.2019", None, RUN_DOCS, Ctx(tmp_path, "replay"), subject_doc="S002",
                         span=span(), fetch=lambda u: calls.append(u))
    assert calls == []


def test_a_request_is_made_once(tmp_path):
    seen: list[str] = []
    c = client(tmp_path, lambda u: seen.append(u) or fetch(u))
    for _ in range(2):
        c.resolve("x", "10.9999/outside.2019", None, RUN_DOCS, subject_doc="S002", span=span())
    assert len(seen) == 1


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


# --- final review C3: a failed request keeps the link and is never recorded as an answer --------------------------

def _raise(exc: BaseException):
    def f(url: str):
        raise exc
    return f


@pytest.mark.parametrize("exc, why", [
    (__import__("urllib.error").error.URLError("no route to host"), "URLError: no route to host"),
    (TimeoutError("timed out"), "timeout"),
    (__import__("urllib.error").error.HTTPError("u", 429, "Too Many Requests", {}, None), "HTTP 429"),
    (__import__("urllib.error").error.HTTPError("u", 503, "Service Unavailable", {}, None), "HTTP 503"),
])
def test_a_failed_request_keeps_the_link_outside_the_set_with_its_reason(tmp_path, exc, why):
    failed = JsonlCache(tmp_path / openalex.FAILED_FILE)
    c = openalex.OpenAlex(JsonlCache(tmp_path / "http.jsonl"), fetch=_raise(exc), failed=failed)
    rec = c.resolve("Somebody 2019", "10.9999/outside.2019", None, RUN_DOCS, subject_doc="S002", span=span())
    assert (rec.object_doc, rec.outside_set, rec.resolve_failed) == (None, True, why)
    assert rec.object_ref == "10.9999/outside.2019"
    assert list(JsonlCache(tmp_path / "http.jsonl").items()) == []   # never recorded as an answer
    asked: list[str] = []
    again = openalex.OpenAlex(JsonlCache(tmp_path / "http.jsonl"), fetch=lambda u: asked.append(u) or None, failed=failed)
    assert again.resolve("Somebody 2019", "10.9999/outside.2019", None, RUN_DOCS, subject_doc="S002",
                         span=span()).resolve_failed is None and asked   # a later run asks again
    replay = openalex.OpenAlex(JsonlCache(tmp_path / "none.jsonl"), offline=True, failed=failed)
    assert replay.resolve("Somebody 2019", "10.9999/outside.2019", None, RUN_DOCS, subject_doc="S002",
                          span=span()).resolve_failed == why   # a replay fails it the same way, without the network


def test_a_replay_without_the_failure_on_record_still_refuses(tmp_path):
    replay = openalex.OpenAlex(JsonlCache(tmp_path / "none.jsonl"), offline=True,
                               failed=JsonlCache(tmp_path / openalex.FAILED_FILE))
    with pytest.raises(openalex.NotRecorded):
        replay.resolve("Somebody 2019", "10.9999/outside.2019", None, RUN_DOCS, subject_doc="S002", span=span())


def test_a_resolved_link_item_has_no_failure_field(tmp_path):
    from evidence.records import item
    rec = client(tmp_path).resolve("Somebody 2019", "10.9999/outside.2019", None, RUN_DOCS, subject_doc="S002", span=span())
    assert "resolve_failed" not in item(rec).fields
