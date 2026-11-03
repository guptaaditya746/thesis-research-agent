"""`evidence fetch`: a demonstration corpus of real papers from the arXiv API, in the layout the engine reads.

    evidence fetch --query "<search words>" --max 30 --out corpora/<name> [--category cs.CL]
    evidence fetch --ids ids.txt --out corpora/<name>          (one arXiv id per line, instead of --query)

One request to the arXiv API (https://info.arxiv.org/help/api/index.html, an Atom feed: a search, or `id_list`
for --ids), then each paper's arXiv HTML page (https://arxiv.org/html/<id>, LaTeXML), else its PDF; at most one
request every three seconds as its terms of use ask, with a User-Agent naming this tool. The HTML is used when
it is a LaTeXML page (`ltx_page_main`) with at least MIN_HTML_CHARS characters of text, else the PDF, and the
reason is kept. Docling turns either into Markdown, written as `papers/<arxiv id>.md` (a short header with
the title, authors, date and link, then the converted text). The corpus directory holds:

- manifest.json: `corpus_id` and per paper `id`, `file`, `sha256` (what evidence/rundir.py `Corpus` reads),
  plus `title`, `authors`, `published`, `url`, `source` ("html" or "pdf") and `html_sha256` or `pdf_sha256`;
- source.json: `{"kind": "arxiv", "query", "category", "fetched", "ground_truth": false, ...}`, how many
  papers came from HTML and from the PDF, the `fallbacks` (why a paper's HTML was not used) and the papers
  that were skipped and why. There is no ground_truth.json: these are real papers, nobody knows the right
  answer, so the web app lists the corpus as a demonstration and refuses to score a run on it.

A paper whose HTML and PDF both fail, or convert to no text, is skipped and logged. The
corpus is built in a hidden sibling directory and renamed into place at the end, so a half-fetched corpus is
never listed. Docling is in the `fetch` dependency group (`uv sync --group fetch`). Exit status: 0 ok, 1 the
search failed, Docling is missing or no paper could be fetched, 2 usage errors (an output directory that
exists, a bad ids file).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

import httpx

from jsonio import sha256_hex

API_URL = "https://export.arxiv.org/api/query"
THANKS = "Thank you to arXiv for use of its open access interoperability."
USER_AGENT = "thesis-research-agent/0.2 (evidence fetch; demonstration corpora; +https://info.arxiv.org/help/api/)"
DELAY_S = 3.0           # the API's terms: no more than one request every three seconds
TIMEOUT_S = 60.0
BACKOFF_S = (15.0, 30.0, 60.0)   # waits after a 429/503 without Retry-After, one per retry
MAX_RETRY_AFTER_S = 120.0
MAX_PAPERS = 100        # one search request; arXiv asks for slices of at most 2000, a demo needs far fewer
MAX_PDF_BYTES = 40 * 1024 * 1024
MIN_HTML_CHARS = 2000   # a converted HTML page shorter than this is an error page or a stub: use the PDF
HTML_MARKER = b"ltx_page_main"   # the LaTeXML page body; arXiv may answer 200 with a plain page for a paper without HTML
ATOM = "{http://www.w3.org/2005/Atom}"
CATEGORY = re.compile(r"^[a-z][a-z-]*(\.[A-Za-z][A-Za-z-]*)?$")   # cs.CL, stat.ML, hep-th, astro-ph.CO
WORD = re.compile(r"[\w-]+")
ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5}|[a-z-]+(\.[A-Za-z-]+)?/\d{7})(v\d+)?")   # 2411.18583v1, hep-th/9901001


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class Entry:
    """One paper of the feed: `id` is the arXiv id with its version (2411.18583v1; an old-style id's `/` is `_`)."""

    id: str
    title: str
    authors: list[str]
    published: str
    url: str
    pdf_url: str
    pmcid: str = ""   # PMC id (PMC1234567) when the paper is also in PubMed Central: the PMC XML rung needs it


def search_query(query: str, category: str | None = None) -> str:
    """The API's `search_query`: every word of the text in any field (`all:`), ANDed, and the category if given."""
    words = WORD.findall(query)
    if not words:
        raise ValueError("the query has no words")
    terms = [f"all:{w}" for w in words]
    if category:
        if not CATEGORY.fullmatch(category):
            raise ValueError(f"not an arXiv category: {category!r} (e.g. cs.CL, stat.ML, hep-th)")
        terms.append(f"cat:{category}")
    return " AND ".join(terms)


def _text(node: ET.Element | None) -> str:
    return " ".join((node.text or "").split()) if node is not None else ""


def parse_feed(data: bytes) -> list[Entry]:
    """The entries of an API response; FetchError for the API's error entry (a malformed query)."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise FetchError(f"the arXiv API answered something that is not an Atom feed ({exc})") from exc
    out: list[Entry] = []
    for e in root.iter(f"{ATOM}entry"):
        ident = _text(e.find(f"{ATOM}id"))
        if "/api/errors" in ident:
            raise FetchError(f"the arXiv API refused the query: {_text(e.find(f'{ATOM}summary'))}")
        arxiv_id = ident.rsplit("/abs/", 1)[-1].replace("/", "_")
        links = e.findall(f"{ATOM}link")
        pdf = next((ln.get("href", "") for ln in links if ln.get("title") == "pdf"), "")
        abstract = next((ln.get("href", "") for ln in links if ln.get("rel") == "alternate"), ident)
        if not arxiv_id or not pdf:
            continue
        out.append(Entry(id=arxiv_id, title=_text(e.find(f"{ATOM}title")),
                         authors=[_text(a.find(f"{ATOM}name")) for a in e.findall(f"{ATOM}author")],
                         published=_text(e.find(f"{ATOM}published")),
                         url=abstract.replace("http://", "https://", 1),
                         pdf_url=pdf.replace("http://", "https://", 1)))
    return list({e.id: e for e in out}.values())


class Client:
    """GETs spaced at least DELAY_S apart (the API and the PDFs alike), with this tool's User-Agent. A 429 or 503
    (arXiv's "slow down") is tried again after its Retry-After, else after BACKOFF_S, at most len(BACKOFF_S) times."""

    def __init__(self, transport: httpx.BaseTransport | None = None, delay: float = DELAY_S,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 log: Callable[[str], None] = lambda _: None) -> None:
        self.http = httpx.Client(transport=transport, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S,
                                 follow_redirects=True)
        self.delay, self.sleep, self.clock, self.log = delay, sleep, clock, log
        self.last: float | None = None

    def _once(self, url: str, params: dict[str, Any] | None) -> httpx.Response:
        if self.last is not None:
            wait = self.delay - (self.clock() - self.last)
            if wait > 0:
                self.sleep(wait)
        try:
            return self.http.get(url, params=params)
        finally:
            self.last = self.clock()

    def get(self, url: str, params: dict[str, Any] | None = None) -> bytes:
        for backoff in (*BACKOFF_S, None):
            try:
                response = self._once(url, params)
            except httpx.TimeoutException:
                if backoff is None:
                    raise
                self.log(f"arXiv did not answer in {TIMEOUT_S:.0f} s; waiting {backoff:.0f} s before asking again")
                self.sleep(backoff)
                continue
            if response.status_code not in (429, 503) or backoff is None:
                break
            after = response.headers.get("Retry-After", "")
            wait = min(max(float(after), backoff), MAX_RETRY_AFTER_S) if after.isdigit() else backoff
            self.log(f"arXiv answered {response.status_code}; waiting {wait:.0f} s before asking again")
            self.sleep(wait)
        response.raise_for_status()
        return response.content

    def close(self) -> None:
        self.http.close()


def docling_markdown(data: bytes, kind: Literal["html", "pdf"]) -> str:
    """The page or PDF as Markdown (Docling), NUL characters dropped. FetchError when Docling is not installed;
    ValueError for a file Docling cannot read."""
    try:
        from docling.datamodel.base_models import DocumentStream, InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as exc:
        raise FetchError("Docling is not installed: uv sync --group fetch") from exc
    options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)   # as scripts/build-corpus.py
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    try:
        result = converter.convert(DocumentStream(name=f"paper.{kind}", stream=BytesIO(data)))
        text = result.document.export_to_markdown()
    except Exception as exc:   # Docling raises its own ConversionError and format errors
        raise ValueError(f"Docling could not read the {kind} ({type(exc).__name__}: {exc})") from exc
    return text.replace("\x00", "").encode("utf-8", "replace").decode("utf-8")


Convert = Callable[[bytes, Literal["html", "pdf"]], str]
Source = Literal["latex", "pmc_xml", "html", "pdf"]
PMC_OAI = ("https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/?verb=GetRecord"
           "&identifier=oai:pubmedcentral.nih.gov:{num}&metadataPrefix=pmc")


def paper_body(entry: Entry, client: Client, convert: Convert = docling_markdown
               ) -> tuple[str, Literal["html", "pdf"], str, str | None]:
    """(Markdown, "html" or "pdf", sha256 of that source file, why the HTML was not used or None).

    The HTML page first; the PDF when the page is missing, is not a LaTeXML page or converts to under
    MIN_HTML_CHARS characters. ValueError when neither works, naming both reasons."""
    html_url = entry.url.replace("/abs/", "/html/", 1)
    try:
        page = client.get(html_url)
        if HTML_MARKER not in page:
            reason = "html: no LaTeXML page"
        else:
            body = convert(page, "html")
            if len(body.strip()) >= MIN_HTML_CHARS:
                return body, "html", sha256_hex(page), None
            reason = f"html: {len(body.strip())} chars"
    except httpx.HTTPStatusError as exc:
        reason = f"html {exc.response.status_code}"
    except httpx.HTTPError as exc:
        reason = f"html: {type(exc).__name__}"
    except ValueError as exc:
        reason = f"html: {exc}"
    try:
        pdf = client.get(entry.pdf_url)
        if len(pdf) > MAX_PDF_BYTES:
            raise ValueError(f"PDF over {MAX_PDF_BYTES // (1024 * 1024)} MB")
        body = convert(pdf, "pdf")
        if not body.strip():
            raise ValueError("the PDF has no extractable text (a scan?)")
    except (httpx.HTTPError, ValueError) as exc:
        raise ValueError(f"{reason}; pdf: {type(exc).__name__}: {exc}") from exc
    return body, "pdf", sha256_hex(pdf), reason


def _why(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return str(exc.response.status_code)
    return f"{type(exc).__name__}: {exc}" if isinstance(exc, ValueError) else type(exc).__name__


def ladder(entry: Entry, client: Client, convert: Convert = docling_markdown
           ) -> tuple[str, Source, str, str]:
    """(Markdown, source, why the earlier rungs were not used ("" when the first worked), sha256 of the source).

    The rungs in order: arXiv LaTeX source (`/e-print/<id>`), PMC XML (only when `entry.pmcid` is set), the arXiv
    HTML page, the PDF through Docling. Each failure is kept as "<rung>: <why>", joined with "; ". ValueError
    when every rung fails."""
    from evidence.sources.latex import latex_markdown
    from evidence.sources.pmc import jats_markdown

    reasons: list[str] = []
    rungs: list[tuple[str, str, Callable[[bytes], str]]] = [
        ("latex", entry.url.replace("/abs/", "/e-print/", 1), latex_markdown)]
    if entry.pmcid:
        rungs.append(("pmc_xml", PMC_OAI.format(num=entry.pmcid.removeprefix("PMC")), jats_markdown))
    for name, url, to_markdown in rungs:
        try:
            blob = client.get(url)
            body = to_markdown(blob)
            return body, name, "; ".join(reasons), sha256_hex(blob)   # type: ignore[return-value]
        except (httpx.HTTPError, ValueError) as exc:
            reasons.append(f"{name}: {_why(exc)}")
    try:
        body, kind, sha, why = paper_body(entry, client, convert)
    except ValueError as exc:
        raise ValueError("; ".join([*reasons, str(exc)])) from exc
    return body, kind, "; ".join([*reasons, *([why] if why else [])]), sha


def fetch_paper(ref: Entry, client: Client | None = None, convert: Convert = docling_markdown
                ) -> tuple[str, Source, str]:
    """(Markdown, source, reason): `ladder` without the source hash."""
    own = client is None
    client = client or Client()
    try:
        body, source, reason, _ = ladder(ref, client, convert)
        return body, source, reason
    finally:
        if own:
            client.close()


def paper_text(entry: Entry, body: str) -> str:
    header = (f"# {entry.title}\n\n{', '.join(entry.authors)}. arXiv:{entry.id}, {entry.published[:10]}. "
              f"{entry.url}\n\n---\n\n")
    return header + body.strip() + "\n"


def fetch(query: str | None, out: Path, max_papers: int = 30, category: str | None = None,
          client: Client | None = None, log: Callable[[str], None] = print,
          now: Callable[[], datetime] = lambda: datetime.now(timezone.utc), ids: list[str] | None = None,
          convert: Convert | None = None, structured: bool = False) -> dict[str, Any]:
    """Look the papers up (a search for `query`, or exactly `ids`; one of the two), download, convert, write the
    corpus into `out` (which must not exist). `convert` defaults to docling_markdown. `structured` tries LaTeX and PMC XML
    before the HTML and the PDF (`ladder`); off, as before. Returns source.json."""
    if (query is None) == (ids is None):
        raise ValueError("give a query or a list of ids, not both and not neither")
    if ids is not None:
        bad = [i for i in ids if not ARXIV_ID.fullmatch(i)]
        if not ids or bad:
            raise ValueError(f"not arXiv ids: {bad[:3]}" if bad else "the list of ids is empty")
        if category:
            raise ValueError("a category goes with a query, not with ids")
        max_papers = len(ids)
    if not 1 <= max_papers <= MAX_PAPERS:
        raise ValueError(f"--max must be between 1 and {MAX_PAPERS}" if ids is None else f"at most {MAX_PAPERS} ids")
    if out.exists():
        raise FileExistsError(f"{out} exists; choose another output directory")
    q = search_query(query, category) if query is not None else None
    convert = convert or docling_markdown
    own = client is None
    client = client or Client(log=log)
    tmp = out.parent / f".{out.name}.partial-{secrets.token_hex(3)}"
    try:
        if ids is not None:
            log(f"arXiv lookup: {len(ids)} ids")
            params: dict[str, Any] = {"id_list": ",".join(ids), "start": 0, "max_results": max_papers}
        else:
            log(f"arXiv search: {q} (at most {max_papers})")
            params = {"search_query": q, "start": 0, "max_results": max_papers,
                      "sortBy": "relevance", "sortOrder": "descending"}
        entries = parse_feed(client.get(API_URL, params))[:max_papers]
        if not entries:
            raise FetchError(f"the arXiv API found no papers for {q or ids!r}")
        (tmp / "papers").mkdir(parents=True)
        papers: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        if ids is not None:   # an id the API did not return is reported, not dropped quietly
            got = {re.sub(r"v\d+$", "", e.id) for e in entries}
            for want in ids:
                if re.sub(r"v\d+$", "", want).replace("/", "_") not in got:
                    skipped.append({"id": want, "url": "", "reason": "not returned by the arXiv API"})
                    log(f"skipped {want}: not returned by the arXiv API")
        fallbacks: list[dict[str, str]] = []
        for n, entry in enumerate(entries, start=1):
            try:
                body, kind, source_sha, fallback = (
                    ladder(entry, client, convert) if structured else paper_body(entry, client, convert))
            except ValueError as exc:
                reason = f"{type(exc).__name__}: {exc}"
                skipped.append({"id": entry.id, "url": entry.pdf_url, "reason": reason})
                log(f"[{n}/{len(entries)}] skipped {entry.id}: {reason}")
                continue
            data = paper_text(entry, body).encode("utf-8")
            file = f"papers/{entry.id}.md"
            (tmp / file).write_bytes(data)
            papers.append({"id": entry.id, "file": file, "sha256": sha256_hex(data), "title": entry.title,
                           "authors": entry.authors, "published": entry.published, "url": entry.url,
                           "source": kind, f"{kind}_sha256": source_sha})
            if fallback:
                fallbacks.append({"id": entry.id, "reason": fallback})
            log(f"[{n}/{len(entries)}] {entry.id} {entry.title[:70]} ({kind}, {len(data) // 1024} KB"
                f"{', ' + fallback if fallback else ''})")
        if not papers:
            raise FetchError(f"no paper could be fetched ({len(skipped)} skipped)")
        names = "\n".join([q or "ids", *(p["id"] for p in papers)])
        corpus_id = f"arxiv-{hashlib.sha256(names.encode('utf-8')).hexdigest()[:8]}"
        source = {"kind": "arxiv", "query": query, "ids": ids, "category": category, "search_query": q, "max": max_papers,
                  "fetched": now().isoformat(timespec="seconds"), "ground_truth": False, "api": API_URL,
                  "converter": f"docling {_version('docling')}", "papers": len(papers),
                  "html": sum(p["source"] == "html" for p in papers), "pdf": sum(p["source"] == "pdf" for p in papers),
                  **({"latex": sum(p["source"] == "latex" for p in papers),
                      "pmc_xml": sum(p["source"] == "pmc_xml" for p in papers)} if structured else {}),
                  "fallbacks": fallbacks, "skipped": skipped,
                  "note": "real papers from arXiv: a demonstration corpus with no ground truth; runs on it are not scored"}
        (tmp / "source.json").write_text(json.dumps(source, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest = {"corpus_id": corpus_id, "papers": papers}
        (tmp / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.rename(out)
        return source
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        if own:
            client.close()
        log(THANKS)


def _version(package: str) -> str:
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version(package)
    except PackageNotFoundError:
        return "unknown"


def add_parser(sub: argparse._SubParsersAction) -> None:
    f = sub.add_parser("fetch", help="a demonstration corpus of real papers from the arXiv API (no ground truth)")
    what = f.add_mutually_exclusive_group(required=True)
    what.add_argument("--query", help="search words; every word must occur (arXiv `all:` field)")
    what.add_argument("--ids", type=Path, metavar="FILE", help="a file with one arXiv id per line (2411.18583v1)")
    f.add_argument("--max", type=int, default=30, help=f"papers to fetch, 1-{MAX_PAPERS} (default 30; ignored with --ids)")
    f.add_argument("--out", required=True, type=Path, help="the corpus directory to write; must not exist")
    f.add_argument("--category", help="arXiv category, e.g. cs.CL")


def run(args: argparse.Namespace) -> int:
    def log(line: str) -> None:
        print(line, flush=True)

    try:
        ids = None
        if args.ids is not None:
            ids = [line.strip() for line in args.ids.read_text(encoding="utf-8").splitlines() if line.strip()]
        source = fetch(args.query, args.out, args.max, args.category, log=log, ids=ids, structured=True)
    except (ValueError, FileExistsError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (FetchError, httpx.HTTPError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"corpus": str(args.out), "papers": source["papers"], "skipped": len(source["skipped"]),
                      "ground_truth": False}, indent=1))
    return 0
