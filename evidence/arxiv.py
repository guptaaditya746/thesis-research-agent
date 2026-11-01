"""`evidence fetch`: a demonstration corpus of real papers from the arXiv API, in the layout the engine reads.

    evidence fetch --query "<search words>" --max 30 --out corpora/<name> [--category cs.CL]

One search request to the arXiv API (https://info.arxiv.org/help/api/index.html, an Atom feed), then each
paper's PDF, at most one request every three seconds as its terms of use ask, with a User-Agent naming this
tool. Each PDF becomes Markdown with pymupdf4llm and is written as `papers/<arxiv id>.md` (a short header with
the title, authors, date and link, then the converted text). The corpus directory holds:

- manifest.json: `corpus_id` and per paper `id`, `file`, `sha256` (what evidence/rundir.py `Corpus` reads),
  plus `title`, `authors`, `published`, `url` and `pdf_sha256`;
- source.json: `{"kind": "arxiv", "query", "category", "fetched", "ground_truth": false, ...}` and the papers
  that were skipped and why. There is no ground_truth.json: these are real papers, nobody knows the right
  answer, so the web app lists the corpus as a demonstration and refuses to score a run on it.

A paper whose PDF cannot be downloaded or converted, or converts to no text, is skipped and logged. The
corpus is built in a hidden sibling directory and renamed into place at the end, so a half-fetched corpus is
never listed. Exit status: 0 ok, 1 the search failed or no paper could be fetched, 2 usage errors (an output
directory that exists).
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
from pathlib import Path
from typing import Any

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
ATOM = "{http://www.w3.org/2005/Atom}"
CATEGORY = re.compile(r"^[a-z][a-z-]*(\.[A-Za-z][A-Za-z-]*)?$")   # cs.CL, stat.ML, hep-th, astro-ph.CO
WORD = re.compile(r"[\w-]+")


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


def pdf_markdown(data: bytes) -> str:
    """The PDF's text as Markdown (pymupdf4llm), NUL characters dropped; ValueError for a PDF that will not open."""
    import pymupdf
    import pymupdf4llm

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:   # pymupdf raises its own FileDataError and RuntimeErrors
        raise ValueError(f"not a readable PDF ({type(exc).__name__}: {exc})") from exc
    try:
        text = pymupdf4llm.to_markdown(doc, show_progress=False, use_ocr=False)
    finally:
        doc.close()
    return text.replace("\x00", "").encode("utf-8", "replace").decode("utf-8")


def paper_text(entry: Entry, body: str) -> str:
    header = (f"# {entry.title}\n\n{', '.join(entry.authors)}. arXiv:{entry.id}, {entry.published[:10]}. "
              f"{entry.url}\n\n---\n\n")
    return header + body.strip() + "\n"


def fetch(query: str, out: Path, max_papers: int = 30, category: str | None = None,
          client: Client | None = None, log: Callable[[str], None] = print,
          now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict[str, Any]:
    """Search, download, convert, write the corpus into `out` (which must not exist). Returns source.json."""
    if not 1 <= max_papers <= MAX_PAPERS:
        raise ValueError(f"--max must be between 1 and {MAX_PAPERS}")
    if out.exists():
        raise FileExistsError(f"{out} exists; choose another output directory")
    q = search_query(query, category)
    own = client is None
    client = client or Client(log=log)
    tmp = out.parent / f".{out.name}.partial-{secrets.token_hex(3)}"
    try:
        log(f"arXiv search: {q} (at most {max_papers})")
        feed = client.get(API_URL, {"search_query": q, "start": 0, "max_results": max_papers,
                                    "sortBy": "relevance", "sortOrder": "descending"})
        entries = parse_feed(feed)[:max_papers]
        if not entries:
            raise FetchError(f"the arXiv API found no papers for {q!r}")
        (tmp / "papers").mkdir(parents=True)
        papers: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        for n, entry in enumerate(entries, start=1):
            try:
                pdf = client.get(entry.pdf_url)
                if len(pdf) > MAX_PDF_BYTES:
                    raise ValueError(f"PDF over {MAX_PDF_BYTES // (1024 * 1024)} MB")
                body = pdf_markdown(pdf)
                if not body.strip():
                    raise ValueError("the PDF has no extractable text (a scan?)")
            except (httpx.HTTPError, ValueError) as exc:
                reason = f"{type(exc).__name__}: {exc}"
                skipped.append({"id": entry.id, "url": entry.pdf_url, "reason": reason})
                log(f"[{n}/{len(entries)}] skipped {entry.id}: {reason}")
                continue
            data = paper_text(entry, body).encode("utf-8")
            file = f"papers/{entry.id}.md"
            (tmp / file).write_bytes(data)
            papers.append({"id": entry.id, "file": file, "sha256": sha256_hex(data), "title": entry.title,
                           "authors": entry.authors, "published": entry.published, "url": entry.url,
                           "pdf_sha256": sha256_hex(pdf)})
            log(f"[{n}/{len(entries)}] {entry.id} {entry.title[:70]} ({len(data) // 1024} KB)")
        if not papers:
            raise FetchError(f"no paper could be fetched ({len(skipped)} skipped)")
        ids = "\n".join([q, *(p["id"] for p in papers)])
        corpus_id = f"arxiv-{hashlib.sha256(ids.encode('utf-8')).hexdigest()[:8]}"
        source = {"kind": "arxiv", "query": query, "category": category, "search_query": q, "max": max_papers,
                  "fetched": now().isoformat(timespec="seconds"), "ground_truth": False, "api": API_URL,
                  "converter": f"pymupdf4llm {_version('pymupdf4llm')}", "papers": len(papers), "skipped": skipped,
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
    f.add_argument("--query", required=True, help="search words; every word must occur (arXiv `all:` field)")
    f.add_argument("--max", type=int, default=30, help=f"papers to fetch, 1-{MAX_PAPERS} (default 30)")
    f.add_argument("--out", required=True, type=Path, help="the corpus directory to write; must not exist")
    f.add_argument("--category", help="arXiv category, e.g. cs.CL")


def run(args: argparse.Namespace) -> int:
    def log(line: str) -> None:
        print(line, flush=True)

    try:
        source = fetch(args.query, args.out, args.max, args.category, log=log)
    except (ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (FetchError, httpx.HTTPError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"corpus": str(args.out), "papers": source["papers"], "skipped": len(source["skipped"]),
                      "ground_truth": False}, indent=1))
    return 0
