"""The source ladder: LaTeX and PMC XML tables come out cell for cell; the order and the reasons."""
from __future__ import annotations

import gzip
import io
import json
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


MESSY = r"""\documentclass{article}
\title{A Title}
\begin{document}
\maketitle
\newcommand\foobar{\textbf{x}}
\renewcommand{\arraystretch}{1.2}
\vspace{-2mm}
We test three things.\footnote{Code at \url{https://example.org}.} See \href{https://a.b}{our page}.
\begin{itemize}
\item Accuracy rose from 0.61 to 0.74.
\item[(b)] Latency fell by 20\%.
\end{itemize}
\begin{equation}
y = \frac{a}{b} \label{eq:1}
\end{equation}
\begin{figure}[t]\includegraphics[width=\linewidth]{fig.pdf}\end{figure}
\noindent The end of the \textsc{Results} part.
\bibliographystyle{plain}
\bibliography{refs}
\begin{thebibliography}{9}\bibitem{x} Someone. A paper. 2020.\end{thebibliography}
\end{document}
"""


def test_latex_leaves_no_commands_and_no_second_title() -> None:
    md = latex_markdown(gzip.compress(MESSY.encode()))
    assert "\\" not in md and "# A Title" not in md   # the title comes from the arXiv entry (paper_text)
    assert "- Accuracy rose from 0.61 to 0.74." in md and "- (b) Latency fell by 20%." in md
    assert "Code at https://example.org." in md and "our page" in md and "The end of the Results part." in md
    assert "Someone" not in md and "refs" not in md and "frac" not in md and "2mm" not in md


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


# --- fetch(structured=True): the composed path (manifest fields) ---------------------------------------------------

def test_fetch_structured_manifest(tmp_path) -> None:
    from evidence.tests.test_arxiv import FEED, Recorded
    from jsonio import sha256_hex

    blob = eprint()

    class WithEprint(Recorded):
        def handler(self, request):
            if request.url.path.startswith("/e-print/"):
                self.requests.append(request)
                return httpx.Response(200, content=blob)
            return super().handler(request)

    rec = WithEprint(broken=(), feed=FEED)
    source = arxiv.fetch("retrieval augmented", tmp_path / "c", max_papers=1, client=rec.client(), log=lambda _: None,
                         convert=lambda data, kind: "x", structured=True)
    paper = json.loads((tmp_path / "c" / "manifest.json").read_text(encoding="utf-8"))["papers"][0]
    assert paper["source"] == "latex" and paper["latex_sha256"] == sha256_hex(blob) and "html_sha256" not in paper
    assert source["fallbacks"] == [] and source["latex"] == 1 and source["html"] == 0


def test_fetch_structured_fallback_reason_is_text_not_hash(tmp_path) -> None:
    from evidence.tests.test_arxiv import FEED, LTX_PAGE, Recorded

    class NoEprint(Recorded):
        def handler(self, request):
            if request.url.path.startswith("/e-print/"):
                return httpx.Response(404)
            return super().handler(request)

    rec = NoEprint(broken=(), feed=FEED, html=LTX_PAGE)
    source = arxiv.fetch("retrieval augmented", tmp_path / "c", max_papers=1, client=rec.client(),
                         log=lambda _: None, convert=lambda data, kind: data.decode(), structured=True)
    assert source["fallbacks"][0]["reason"] == "latex: 404" and source["html"] == 1


# --- the PDF path: Docling's cells that pdfplumber cannot confirm carry "table unsure" --------------------------------

PDF_MD = "Results.\n\n| System | EM |\n|---|---|\n| Baseline | 61.2 |\n| RAG | 74.5 |\n\nEnd.\n"
PDF_RAW = [(1, [["System", "EM"], ["Baseline", "61.2"], ["RAG", "74.5"]])]


def _pdf_ladder(monkeypatch, plumber):
    monkeypatch.setattr(arxiv, "_docling_convert", lambda data, kind: (PDF_MD, PDF_RAW))
    monkeypatch.setattr(arxiv, "plumber_bytes", lambda data: plumber)
    client = arxiv.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=b"%PDF-1.4 fake") if "/pdf/" in r.url.path else httpx.Response(404)), delay=0)
    body, source, _, _ = arxiv.ladder(ENTRY, client)
    assert source == "pdf"
    return body


def _checked(markdown: str, quote: str, number: float):
    from agent.anchor import Index, selector_at, text_sha256
    from evidence import checks, protocol
    from evidence.contract import DocumentRef, ExtractionResult, ExtractionTask, Item, ProtocolRef, Scope, Span
    from evidence.tests.conftest import PROTOCOL

    proto = protocol.load(PROTOCOL)
    doc = DocumentRef(id="P", file="papers/P.md", sha256=text_sha256(markdown))

    def span(q, role):
        at = markdown.index(q)
        return Span.of(role, selector_at(markdown, at, at + len(q), file=doc.file, sha256=doc.sha256))

    cond = Item.build("condition", {"label": "Baseline", "role": "baseline"}, [span("Baseline", "condition_label")])
    metric = Item.build("metric", {"name": "EM", "canonical": "factual_accuracy", "higher_is_better": True},
                        [span("EM", "metric_label")])
    value = Item.build("measurement", {"value": number, "dataset": None}, [span(quote, "value")],
                       links={"condition": cond.item_id, "metric": metric.item_id})
    spec = proto.evidence_types["measurement"]
    t = ExtractionTask(protocol=ProtocolRef(id=proto.id, sha256=proto.sha256), evidence_type="measurement",  # type: ignore[arg-type]
                       field_schema_sha256=spec.schema_sha256, document=doc, scope=Scope(), context=(cond.item_id, metric.item_id))
    result = ExtractionResult(extractor_id="x@1#0", task_sha256=t.task_sha256, status="ok", items=(value,))
    return checks.check(result, t, Index(markdown), spec, {cond.item_id: cond, metric.item_id: metric})


def test_pdf_disagreeing_cell_is_marked_end_to_end(monkeypatch) -> None:
    md = _pdf_ladder(monkeypatch, [(1, [["System", "EM"], ["Baseline", "61.2"], ["RAG", "74.6"]])])
    assert md.count("<!-- table unsure:") == 1 and "<!-- table unsure: 2,1 -->" in md
    [kept] = _checked(md, "74.5", 0.745).items
    assert kept.fields["table_unsure"] is True
    [sure] = _checked(md, "61.2", 0.612).items
    assert "table_unsure" not in sure.fields


def test_pdf_page_without_pdfplumber_table_keeps_docling_all_unsure(monkeypatch) -> None:
    md = _pdf_ladder(monkeypatch, [])
    assert md.count("<!-- table unsure:") == 6 and "| RAG | 74.5 |" in md
    [kept] = _checked(md, "74.5", 0.745).items          # kept, not dropped
    assert kept.fields["table_unsure"] is True


def test_pdf_block_count_mismatch_marks_everything_unsure() -> None:
    from evidence.tables import annotate
    out = annotate(PDF_MD + "\n| a | b |\n|---|---|\n| 1 | 2 |\n", PDF_RAW, PDF_RAW)
    assert out.count("<!-- table unsure:") == 6 + 4
