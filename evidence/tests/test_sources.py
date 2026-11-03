"""The source ladder: LaTeX and PMC XML tables come out cell for cell; the order and the reasons."""
from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path

import httpx

from evidence import arxiv
from evidence.sources.latex import latex_markdown
from evidence.sources.pmc import jats_markdown

FIX = Path(__file__).resolve().parent / "fixtures" / "sources"
ENTRY = arxiv.Entry(id="2411.18583v1", title="T", authors=["A"], published="2024-11-01T00:00:00Z",
                    url="https://arxiv.org/abs/2411.18583v1", pdf_url="https://arxiv.org/pdf/2411.18583v1")
LTX_PAGE = b'<html><div class="ltx_page_main">' + b"Accuracy rose from 0.61 to 0.74. " * 100 + b"</div></html>"


def eprint() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name in ("paper.tex", "extra.tex"):
            data = (FIX / name).read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def cells(markdown: str) -> list[list[str]]:
    rows = [ln for ln in markdown.splitlines() if ln.startswith("|") and "---" not in ln]
    return [[c.strip() for c in r.strip("|").split(" | ")] for r in rows]


EXPECTED = [["System", "EM (%)", "F1"], ["Baseline", "61.2", "70.4"], ["RAG-Seq", "74.5", "80.1*"],
            ["Ablations", "", ""], ["No retriever", "55.0", "63.3"]]


def test_latex_table_cells_exact() -> None:
    md = latex_markdown(eprint())
    got = cells(md)
    assert got[:3] == EXPECTED[:3]
    assert got[3] == ["Ablations", "", ""] and got[4] == EXPECTED[4]
    assert "Latency fell by 20% with caching." in md and "\\cite" not in md


def test_pmc_table_cells_exact() -> None:
    got = cells(jats_markdown((FIX / "paper.xml").read_bytes()))
    assert got[:3] == EXPECTED[:3] and got[3] == ["Ablations", "", ""]


def test_plain_gzip_and_garbage() -> None:
    assert "Baseline" in latex_markdown(gzip.compress((FIX / "paper.tex").read_bytes()))
    for bad in (b"%PDF-1.5 not latex", b""):
        try:
            latex_markdown(bad)
        except ValueError:
            continue
        raise AssertionError("garbage accepted")


def run_ladder(handler, entry=ENTRY):
    seen: list[str] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return handler(request)

    client = arxiv.Client(transport=httpx.MockTransport(wrapped), delay=0)
    return arxiv.fetch_paper(entry, client, convert=lambda data, kind: data.decode() if kind == "html" else "pdf text"), seen


def test_ladder_order_and_reason() -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        if r.url.path.startswith("/e-print/"):
            return httpx.Response(404)
        return httpx.Response(200, content=LTX_PAGE)

    (body, source, reason), seen = run_ladder(handler)
    assert source == "html" and reason == "latex: 404" and "Accuracy" in body
    assert seen == ["/e-print/2411.18583v1", "/html/2411.18583v1"]


def test_ladder_latex_first_and_pmc_before_html() -> None:
    (body, source, reason), _ = run_ladder(lambda r: httpx.Response(200, content=eprint()))
    assert source == "latex" and reason == "" and "RAG-Seq" in body

    def handler(r: httpx.Request) -> httpx.Response:
        if r.url.host == "arxiv.org":
            return httpx.Response(404)
        return httpx.Response(200, content=(FIX / "paper.xml").read_bytes())

    pmc = arxiv.Entry(**{**ENTRY.__dict__, "pmcid": "PMC123"})
    (body, source, reason), _ = run_ladder(handler, pmc)
    assert source == "pmc_xml" and reason == "latex: 404" and "RAG-Seq" in body


def test_ladder_pdf_last_with_every_reason() -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF") if "/pdf/" in r.url.path else httpx.Response(404)

    (body, source, reason), _ = run_ladder(handler)
    assert source == "pdf" and body == "pdf text" and reason.startswith("latex: 404; html 404")
