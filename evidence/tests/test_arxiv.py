"""evidence fetch (evidence/arxiv.py) against a recorded arXiv Atom response and a tiny PDF; no network."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from evidence import arxiv, cli
from evidence.rundir import Corpus
from jsonio import sha256_hex

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "arxiv"
FEED = (FIXTURES / "feed.xml").read_bytes()
PDF = (FIXTURES / "tiny.pdf").read_bytes()
NOW = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)


class Recorded:
    """An httpx transport answering from the recordings; it keeps every request and the fake clock's sleeps."""

    def __init__(self, broken: tuple[str, ...] = ("9901001",), feed: bytes = FEED) -> None:
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []
        self.broken, self.feed = broken, feed
        self.t = 0.0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=self.feed)
        if any(b in request.url.path for b in self.broken):
            return httpx.Response(404, content=b"not found")
        return httpx.Response(200, content=PDF)

    def client(self) -> arxiv.Client:
        def sleep(s: float) -> None:
            self.sleeps.append(s)
            self.t += s
        return arxiv.Client(transport=httpx.MockTransport(self.handler), sleep=sleep, clock=lambda: self.t)


def test_parse_feed_reads_ids_titles_authors_and_pdf_links():
    entries = arxiv.parse_feed(FEED)
    assert [e.id for e in entries] == ["2507.23334v2", "2411.18583v1", "hep-th_9901001v1"]
    first = entries[0]
    assert first.title == "MUST-RAG: MUSical Text Question Answering with Retrieval Augmented Generation"
    assert first.authors == ["Daeyong Kwon", "SeungHeon Doh", "Juhan Nam"]
    assert first.published == "2025-07-31T08:31:05Z"
    assert first.pdf_url == "https://arxiv.org/pdf/2507.23334v2"
    assert entries[2].pdf_url == "https://arxiv.org/pdf/hep-th/9901001v1"   # http made https


def test_the_api_error_entry_is_a_fetch_error():
    error = (b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors#bad</id>'
             b"<summary>incorrect id format</summary></entry></feed>")
    with pytest.raises(arxiv.FetchError, match="incorrect id format"):
        arxiv.parse_feed(error)


def test_search_query_ands_the_words_and_the_category():
    assert arxiv.search_query("Retrieval-augmented  generation!", "cs.CL") == \
        "all:Retrieval-augmented AND all:generation AND cat:cs.CL"
    with pytest.raises(ValueError):
        arxiv.search_query("x", "cs.CL; rm")
    with pytest.raises(ValueError):
        arxiv.search_query("  ?! ")


def test_fetch_writes_the_corpus_the_engine_reads(tmp_path: Path):
    rec = Recorded()
    lines: list[str] = []
    out = tmp_path / "arxiv-rag"
    source = arxiv.fetch("retrieval augmented", out, max_papers=3, category="cs.CL", client=rec.client(),
                         log=lines.append, now=lambda: NOW)
    corpus = Corpus(out)   # the engine's own reader: ids, files and sha256 agree
    assert [p.id for p in corpus.papers] == ["2507.23334v2", "2411.18583v1"]
    text = corpus.text(corpus.papers[0])
    assert text.startswith("# MUST-RAG: MUSical Text Question Answering")
    assert "Accuracy rose from 0.61 to 0.74" in text
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    entry = manifest["papers"][0]
    assert entry["authors"] == ["Daeyong Kwon", "SeungHeon Doh", "Juhan Nam"]
    assert entry["url"] == "https://arxiv.org/abs/2507.23334v2" and entry["published"] == "2025-07-31T08:31:05Z"
    assert entry["pdf_sha256"] == sha256_hex(PDF)
    assert manifest["corpus_id"].startswith("arxiv-")
    on_disk = json.loads((out / "source.json").read_text(encoding="utf-8"))
    assert on_disk == source
    assert source["kind"] == "arxiv" and source["ground_truth"] is False
    assert source["query"] == "retrieval augmented" and source["fetched"] == "2026-10-28T09:00:00+00:00"
    assert [s["id"] for s in source["skipped"]] == ["hep-th_9901001v1"]   # the broken PDF, logged
    assert any("skipped hep-th_9901001v1" in line for line in lines)
    assert lines[-1] == arxiv.THANKS
    assert not (out / "ground_truth.json").exists()
    assert [p.name for p in tmp_path.iterdir()] == ["arxiv-rag"]   # no partial directory left behind


def test_fetch_is_polite_one_request_every_three_seconds(tmp_path: Path):
    rec = Recorded()
    arxiv.fetch("retrieval", tmp_path / "c", max_papers=3, client=rec.client(), log=lambda _: None)
    assert len(rec.requests) == 4   # the search and three PDFs
    assert rec.sleeps == [arxiv.DELAY_S] * 3
    assert all(r.headers["User-Agent"] == arxiv.USER_AGENT for r in rec.requests)
    search = rec.requests[0].url.params
    assert search["search_query"] == "all:retrieval" and search["max_results"] == "3"


def test_fetch_refuses_an_existing_directory_and_leaves_nothing_when_every_pdf_fails(tmp_path: Path):
    with pytest.raises(FileExistsError):
        arxiv.fetch("x", tmp_path, client=Recorded().client(), log=lambda _: None)
    rec = Recorded(broken=("pdf",))
    with pytest.raises(arxiv.FetchError, match="no paper could be fetched"):
        arxiv.fetch("x", tmp_path / "none", client=rec.client(), log=lambda _: None)
    assert list(tmp_path.iterdir()) == []


def test_the_cli_exit_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    rec = Recorded()
    real = arxiv.Client
    monkeypatch.setattr(arxiv, "Client", lambda **_: real(transport=httpx.MockTransport(rec.handler), delay=0))
    assert cli.main(["fetch", "--query", "retrieval", "--max", "2", "--out", str(tmp_path / "c")]) == 0
    printed = capsys.readouterr().out
    assert arxiv.THANKS in printed
    assert json.loads(printed[printed.index("{"):]) == {"corpus": str(tmp_path / "c"), "papers": 2, "skipped": 0,
                                                        "ground_truth": False}
    assert cli.main(["fetch", "--query", "retrieval", "--out", str(tmp_path / "c")]) == 2   # exists
    assert cli.main(["fetch", "--query", "retrieval", "--max", "0", "--out", str(tmp_path / "d")]) == 2
    empty = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    rec.feed = empty
    assert cli.main(["fetch", "--query", "nothing", "--out", str(tmp_path / "e")]) == 1


def test_a_429_a_503_or_a_timeout_is_asked_again_after_the_longer_of_retry_after_and_the_backoff():
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)
    answers = [lambda r: httpx.Response(429, headers={"Retry-After": "40"}), lambda r: httpx.Response(503, headers={"Retry-After": "0"}),
               timeout, lambda r: httpx.Response(200, content=b"ok")]
    sleeps: list[float] = []
    client = arxiv.Client(transport=httpx.MockTransport(lambda r: answers.pop(0)(r)), delay=0, sleep=sleeps.append)
    assert client.get("https://export.arxiv.org/api/query") == b"ok"
    assert sleeps == [40.0, arxiv.BACKOFF_S[1], arxiv.BACKOFF_S[2]]
    always = arxiv.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429)), delay=0, sleep=sleeps.append)
    with pytest.raises(httpx.HTTPStatusError):
        always.get("https://export.arxiv.org/api/query")
