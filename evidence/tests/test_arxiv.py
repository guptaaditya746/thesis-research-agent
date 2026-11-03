"""evidence fetch (evidence/arxiv.py) against a recorded arXiv Atom response and a tiny PDF; no network."""
from __future__ import annotations

import json
import sys
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
LTX_PAGE = b'<html><div class="ltx_page_main">' + b"Accuracy rose from 0.61 to 0.74 on the benchmark. " * 60 + b"</div></html>"
SHORT_LTX = b'<html><div class="ltx_page_main">Accuracy rose from 0.61 to 0.74.</div></html>'
PDF_TEXT = "Accuracy rose from 0.61 to 0.74 in the PDF."


def fake_convert(data: bytes, kind: str) -> str:
    """Stands in for Docling: the HTML page as its own text, the PDF as a fixed sentence."""
    return data.decode("utf-8") if kind == "html" else PDF_TEXT


class Recorded:
    """An httpx transport answering from the recordings; it keeps every request and the fake clock's sleeps."""

    def __init__(self, broken: tuple[str, ...] = ("9901001",), feed: bytes = FEED, html: bytes | None = LTX_PAGE,
                 pdf: bytes | None = PDF) -> None:
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []
        self.broken, self.feed, self.html, self.pdf = broken, feed, html, pdf
        self.t = 0.0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=self.feed)
        if any(b in request.url.path for b in self.broken):
            return httpx.Response(404, content=b"not found")
        page = self.html if request.url.path.startswith("/html/") else self.pdf
        return httpx.Response(404, content=b"not found") if page is None else httpx.Response(200, content=page)

    def client(self) -> arxiv.Client:
        def sleep(s: float) -> None:
            self.sleeps.append(s)
            self.t += s
        return arxiv.Client(transport=httpx.MockTransport(self.handler), sleep=sleep, clock=lambda: self.t)


def fetch_with(tmp_path: Path, html: bytes | None = LTX_PAGE, pdf: bytes | None = PDF, convert=fake_convert,
               ids: list[str] | None = None, lines: list[str] | None = None) -> tuple[dict, Recorded]:
    """One paper (the feed's first) through fetch(); returns source.json and the recorded requests."""
    rec = Recorded(broken=(), html=html, pdf=pdf)
    log = lines.append if lines is not None else (lambda _: None)
    query = None if ids else "retrieval"
    source = arxiv.fetch(query, tmp_path / "c", max_papers=1, ids=ids, client=rec.client(), log=log, convert=convert,
                         now=lambda: NOW)
    return source, rec


def manifest(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "c" / "manifest.json").read_text(encoding="utf-8"))


def test_html_is_preferred(tmp_path: Path):
    src, rec = fetch_with(tmp_path)
    paper = manifest(tmp_path)["papers"][0]
    assert src["html"] == 1 and src["pdf"] == 0 and src["fallbacks"] == []
    assert paper["source"] == "html" and paper["html_sha256"] == sha256_hex(LTX_PAGE) and "pdf_sha256" not in paper
    assert [r.url.path for r in rec.requests[1:]] == ["/html/2507.23334v2"]   # the PDF is never asked for


@pytest.mark.parametrize("html,reason", [(None, "html 404"), (b"<html>Error</html>", "html: no LaTeXML page"),
                                         (SHORT_LTX, "html: ")])
def test_bad_html_falls_back_to_pdf_with_reason(tmp_path: Path, html: bytes | None, reason: str):
    src, _ = fetch_with(tmp_path, html=html)
    paper = manifest(tmp_path)["papers"][0]
    assert src["pdf"] == 1 and src["html"] == 0 and src["fallbacks"][0]["reason"].startswith(reason)
    assert src["fallbacks"][0]["id"] == "2507.23334v2"
    assert paper["source"] == "pdf" and paper["pdf_sha256"] == sha256_hex(PDF) and "html_sha256" not in paper
    if html == SHORT_LTX:
        assert src["fallbacks"][0]["reason"] == f"html: {len(SHORT_LTX.decode())} chars"


def test_both_failing_skips_with_both_reasons(tmp_path: Path):
    lines: list[str] = []
    with pytest.raises(arxiv.FetchError, match="no paper could be fetched"):
        fetch_with(tmp_path, html=None, pdf=None, lines=lines)
    skipped = next(line for line in lines if "skipped 2507.23334v2" in line)
    assert "html 404" in skipped and "pdf" in skipped and "404" in skipped.split("pdf", 1)[1]


def test_ids_fetch_uses_id_list(tmp_path: Path):
    source, rec = fetch_with(tmp_path, ids=["2411.18583v1"])
    params = rec.requests[0].url.params
    assert params["id_list"] == "2411.18583v1" and "search_query" not in params and params["max_results"] == "1"
    assert source["ids"] == ["2411.18583v1"] and source["query"] is None


def test_an_id_the_api_does_not_return_is_skipped_with_a_reason(tmp_path: Path):
    source, _ = fetch_with(tmp_path, ids=["2411.18583v1", "2501.00001v1"])
    assert [s["id"] for s in source["skipped"]] == ["2501.00001v1"]
    assert source["skipped"][0]["reason"] == "not returned by the arXiv API"


def test_ids_and_query_are_mutually_exclusive(tmp_path: Path):
    for query, ids in (("retrieval", ["2411.18583v1"]), (None, None), (None, ["not an id"])):
        with pytest.raises(ValueError):
            arxiv.fetch(query, tmp_path / "x", ids=ids, client=Recorded().client(), log=lambda _: None,
                        convert=fake_convert)


def test_source_names_docling(tmp_path: Path):
    assert fetch_with(tmp_path)[0]["converter"].startswith("docling ")


def test_a_missing_docling_is_a_fetch_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(sys.modules, "docling", None)
    with pytest.raises(arxiv.FetchError, match="uv sync --group fetch"):
        arxiv.docling_markdown(b"<html></html>", "html")


def test_the_cli_reads_ids_from_a_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    rec = Recorded()
    real = arxiv.Client
    monkeypatch.setattr(arxiv, "Client", lambda **_: real(transport=httpx.MockTransport(rec.handler), delay=0))
    monkeypatch.setattr(arxiv, "docling_markdown", fake_convert)
    ids = tmp_path / "ids.txt"
    ids.write_text("2507.23334v2\n\n 2411.18583v1 \n", encoding="utf-8")
    assert cli.main(["fetch", "--ids", str(ids), "--out", str(tmp_path / "c")]) == 0
    assert rec.requests[0].url.params["id_list"] == "2507.23334v2,2411.18583v1"
    with pytest.raises(SystemExit):   # argparse: --ids and --query exclude each other
        cli.main(["fetch", "--ids", str(ids), "--query", "x", "--out", str(tmp_path / "d")])
    assert cli.main(["fetch", "--ids", str(tmp_path / "none.txt"), "--out", str(tmp_path / "e")]) == 2


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
                         log=lines.append, now=lambda: NOW, convert=fake_convert)
    corpus = Corpus(out)   # the engine's own reader: ids, files and sha256 agree
    assert [p.id for p in corpus.papers] == ["2507.23334v2", "2411.18583v1"]
    text = corpus.text(corpus.papers[0])
    assert text.startswith("# MUST-RAG: MUSical Text Question Answering")
    assert "Accuracy rose from 0.61 to 0.74" in text
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    entry = manifest["papers"][0]
    assert entry["authors"] == ["Daeyong Kwon", "SeungHeon Doh", "Juhan Nam"]
    assert entry["url"] == "https://arxiv.org/abs/2507.23334v2" and entry["published"] == "2025-07-31T08:31:05Z"
    assert entry["source"] == "html" and entry["html_sha256"] == sha256_hex(LTX_PAGE)
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
    arxiv.fetch("retrieval", tmp_path / "c", max_papers=3, client=rec.client(), log=lambda _: None,
                convert=fake_convert)
    assert len(rec.requests) == 5   # the search, three HTML pages, the PDF of the one whose page is missing
    assert rec.sleeps == [arxiv.DELAY_S] * 4
    assert all(r.headers["User-Agent"] == arxiv.USER_AGENT for r in rec.requests)
    search = rec.requests[0].url.params
    assert search["search_query"] == "all:retrieval" and search["max_results"] == "3"


def test_fetch_refuses_an_existing_directory_and_leaves_nothing_when_every_pdf_fails(tmp_path: Path):
    with pytest.raises(FileExistsError):
        arxiv.fetch("x", tmp_path, client=Recorded().client(), log=lambda _: None, convert=fake_convert)
    rec = Recorded(html=None, pdf=None)
    with pytest.raises(arxiv.FetchError, match="no paper could be fetched"):
        arxiv.fetch("x", tmp_path / "none", client=rec.client(), log=lambda _: None, convert=fake_convert)
    assert list(tmp_path.iterdir()) == []


def test_the_cli_exit_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    rec = Recorded()
    real = arxiv.Client
    monkeypatch.setattr(arxiv, "Client", lambda **_: real(transport=httpx.MockTransport(rec.handler), delay=0))
    monkeypatch.setattr(arxiv, "docling_markdown", fake_convert)
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


def test_a_pmc_id_given_with_an_arxiv_id_reaches_the_pmc_rung(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    rec = Recorded()
    real = arxiv.Client
    monkeypatch.setattr(arxiv, "Client", lambda **_: real(transport=httpx.MockTransport(rec.handler), delay=0))
    seen: list[str] = []

    def fake_ladder(entry, client, convert):
        seen.append(entry.pmcid)
        return "# body", "pdf", "0" * 64, None

    monkeypatch.setattr(arxiv, "ladder", fake_ladder)
    ids = tmp_path / "ids.txt"
    ids.write_text("2507.23334v2 PMC1234567\n2411.18583v1\n", encoding="utf-8")
    assert cli.main(["fetch", "--ids", str(ids), "--out", str(tmp_path / "c")]) == 0
    assert "PMC1234567" in seen and seen.count("") == len(seen) - 1   # only the paper given a PMC id gets one
    assert rec.requests[0].url.params["id_list"] == "2507.23334v2,2411.18583v1"
