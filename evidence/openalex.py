"""Builds-on links through OpenAlex (Task 5.2).

`resolve` turns one cited work (a DOI, an arXiv id or just the cited text) into a `LinkRecord`: OpenAlex finds the
work (`/works/doi:...`, or a title search), and the work is matched to a paper of the run by its DOI or its title in
the paper's head (`run_docs` maps doc id -> the paper's text). A work that is not a paper of the run is kept with
`outside_set=True`, never dropped. `references` lists a work's `referenced_works` (for scoring). `read_link` reads the
open relation of a citing sentence with the DSPy step `ReadLink`.

Every HTTP answer is recorded in a `JsonlCache` keyed by its URL, like a model call: a replay (`offline=True`) answers
from the record and never touches the network; a request missing from the record raises `NotRecorded`.

A request that fails (no network, a timeout, HTTP 429 or 5xx, any HTTP error but 404, a body that is not JSON) is never
put in the record: a later run asks again. `resolve` keeps the link, `object_doc` None, `outside_set` True and
`resolve_failed` the reason. So that a replay fails it the same way, the failure is written to the run folder's
`openalex-failed.jsonl`, which only an offline replay reads (final review C3)."""
from __future__ import annotations

import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from collections.abc import Callable, Mapping
from typing import Any

import dspy

from modelcall.cache import JsonlCache, cache_key
from .claims import run_step
from .contract import Span
from .records import LinkRecord
from .steps import Step

__all__ = ["NotRecorded", "OpenAlex", "ReadLink", "ResolveFailed", "read_link", "references", "resolve"]

BASE = "https://api.openalex.org/"
RECORD_FILE = "openalex.jsonl"
FAILED_FILE = "openalex-failed.jsonl"   # failed requests, read by an offline replay only
Fetch = Callable[[str], "dict[str, Any] | None"]   # url -> parsed JSON, or None for a 404


class NotRecorded(RuntimeError):
    """A replay needs an OpenAlex answer the record does not hold."""


class ResolveFailed(RuntimeError):
    """An OpenAlex request failed (network, timeout, HTTP 429/5xx); `reason` is short and stable."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _failure(exc: BaseException) -> str:
    """The short reason of a failed request (the same failure gives the same words)."""
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, TimeoutError) or "timed out" in str(exc):
        return "timeout"
    if isinstance(exc, urllib.error.URLError):
        return f"URLError: {str(exc.reason)[:100]}"
    return f"{type(exc).__name__}: {str(exc)[:100]}"


class ReadLink(dspy.Signature):
    """Read how a paper builds on, uses or relates to earlier work in one sentence.

    relation is the paper's own verb or short phrase for the tie to the other work, copied from the sentence
    ("builds on", "extends", "uses the data of", "disagrees with"). object is the cited work as the sentence names it
    (author and year, a title, or a bracketed reference), or null when the sentence names none.

    Example: "We build on Lewis et al. (2020)." -> relation "builds on", object "Lewis et al. (2020)".
    Example: "Unlike [12], our reader sees the whole page." -> relation "unlike", object "[12]".
    Example: "We evaluate on three corpora." -> relation "", object null."""
    sentence: str = dspy.InputField(desc="one sentence of the paper, verbatim")
    relation: str = dspy.OutputField(desc="the paper's own verb or phrase for the tie to the other work; empty when none")
    object: str | None = dspy.OutputField(desc="the cited work as the sentence names it, or null")


_READ = Step(ReadLink, "openalex.read_link")


def read_link(sentence: str, ctx: Any | None = None) -> tuple[str, str | None]:
    """(relation, object) of one sentence, from the DSPy step `ReadLink` (recorded; under `ctx` when given)."""
    out = run_step(_READ, ctx, "openalex.read_link", sentence=sentence)
    return str(out.relation).strip(), (str(out.object).strip() or None) if out.object is not None else None


def _urlopen(url: str) -> dict[str, Any] | None:
    req = urllib.request.Request(url, headers={"User-Agent": "thesis-research-agent (mailto:a.gupta@firmway.eu)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def work_id(work: Mapping[str, Any] | None) -> str | None:
    """The last path segment of an OpenAlex work's `id` ("https://openalex.org/W2741809807" -> "W2741809807"); None
    without a work or an id."""
    ident = str((work or {}).get("id") or "").strip().rstrip("/")
    return ident.rsplit("/", 1)[-1] or None if ident else None


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _title_of(text: str) -> str:
    """The normalised first non-empty line of a paper (its title line)."""
    return next((_norm(ln) for ln in text.splitlines() if ln.strip()), "")


def _same_title(found: str, cited: str) -> bool:
    a, b = _norm(found), _norm(cited)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / len(ta | tb) >= 0.8


def _has_doi(text: str, doi: str) -> bool:
    """The DOI occurs in the text and is not the start of a longer one."""
    return re.search(re.escape(doi) + r"(?![\w/-]|\.\w)", text.casefold()) is not None


def _bare_doi(doi: str) -> str:
    return re.sub(r"(?i)^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", doi.strip()).lower()


class OpenAlex:
    """An OpenAlex client whose every answer goes through `cache` (required: the run's record of HTTP calls)."""

    def __init__(self, cache: JsonlCache, *, fetch: Fetch | None = None, offline: bool = False,
                 failed: JsonlCache | None = None) -> None:
        if cache is None:
            raise ValueError("OpenAlex needs the run's cache: an unrecorded call would break replay")
        self.cache, self._fetch, self.offline, self.failed = cache, fetch or _urlopen, offline, failed

    @classmethod
    def for_ctx(cls, ctx: Any, *, fetch: Fetch | None = None) -> OpenAlex:
        """The client of a run: record in `<run folder>/openalex.jsonl`, offline when `ctx.mode == "replay"`; a replay reads
        the RECORDED run's file (`ctx.record_dir`: its source folder), not the folder it writes."""
        folder = getattr(ctx, "record_dir", None) or ctx.run_dir
        return cls(JsonlCache(Path(folder) / RECORD_FILE), fetch=fetch, offline=ctx.mode == "replay",
                   failed=JsonlCache(Path(folder) / FAILED_FILE))

    def get(self, url: str) -> dict[str, Any] | None:
        key = cache_key({"openalex": url})
        hit = self.cache.get(key)
        if hit is not None:
            return json.loads(hit["output"])
        if self.offline:
            failed = self.failed.get(key) if self.failed is not None else None
            if failed is not None:   # the recorded run's request failed: fail it the same way
                raise ResolveFailed(failed["reason"])
            raise NotRecorded(f"offline replay: no recorded OpenAlex answer for {url}")
        try:
            body = self._fetch(url)
        except (OSError, ValueError, http.client.HTTPException) as exc:   # never recorded as an answer: asked again
            reason = _failure(exc)
            if self.failed is not None:
                self.failed.put(key, {"reason": reason, "url": url})
            raise ResolveFailed(reason) from None
        self.cache.put(key, {"output": json.dumps(body), "url": url})
        return body

    def work(self, cited_text: str, doi: str | None, arxiv_id: str | None) -> dict[str, Any] | None:
        """The OpenAlex work for a DOI, else an arXiv id (its DataCite DOI), else a title search; None when unknown."""
        if doi:
            return self.get(f"{BASE}works/doi:{_bare_doi(doi)}")
        if arxiv_id:
            return self.get(f"{BASE}works/doi:10.48550/arxiv.{arxiv_id.strip().lower()}")
        if cited_text.strip():
            found = self.get(f"{BASE}works?search={urllib.parse.quote_plus(cited_text.strip())}&per-page=1")
            results = (found or {}).get("results") or []
            # the first hit is only a guess: take it when its title is the cited title
            return results[0] if results and _same_title(results[0].get("title") or results[0].get("display_name") or "",
                                                         cited_text) else None
        return None

    def resolve(self, cited_text: str, doi: str | None, arxiv_id: str | None, run_docs: Mapping[str, str], *,
                subject_doc: str, span: Span, relation: str = "cites") -> LinkRecord:
        """The link from `subject_doc` to the cited work. `object_doc` is the run paper the work is, else None and
        `outside_set` is True (the work is kept either way)."""
        # a paper of the run is found locally first (the synthetic papers and many preprints are unknown to OpenAlex)
        object_doc = self._local_doc(cited_text, doi, run_docs)
        failed = None
        try:
            work = None if object_doc else self.work(cited_text, doi, arxiv_id)
        except ResolveFailed as exc:   # the link is kept, outside the set, with the reason
            work, failed = None, exc.reason
        if work and object_doc is None:
            object_doc = self._run_doc(work, run_docs)
        work_doi = _bare_doi(work["doi"]) if work and work.get("doi") else None
        ref = doi.strip() if doi else arxiv_id.strip() if arxiv_id else work_doi or cited_text
        return LinkRecord(subject_doc=subject_doc, relation=relation, object_ref=ref, object_doc=object_doc,
                          outside_set=object_doc is None, span=span, work=work_id(work),
                          **({"resolve_failed": failed} if failed is not None else {}))

    @staticmethod
    def _local_doc(cited_text: str, doi: str | None, run_docs: Mapping[str, str]) -> str | None:
        """The run paper a DOI or a cited title names, by the papers' own heads (no network)."""
        cited = _norm(cited_text)
        for doc_id, text in run_docs.items():
            if doi and _has_doi(text[:3000], _bare_doi(doi)):
                return doc_id
            title = _title_of(text)
            if len(cited) > 12 and len(title) > 12 and (title in cited or cited in _norm(text[:600])):
                return doc_id
        return None

    @staticmethod
    def _run_doc(work: Mapping[str, Any], run_docs: Mapping[str, str]) -> str | None:
        doi = _bare_doi(work["doi"]) if work.get("doi") else None
        title = _norm(work.get("title") or work.get("display_name") or "")
        for doc_id, text in run_docs.items():
            if doi and _has_doi(text[:3000], doi):
                return doc_id
            if title and len(title) > 12 and title in _norm(text[:600]):
                return doc_id
        return None

    def references(self, doc_id: str) -> list[str]:
        """`referenced_works` of a work: `doc_id` is an OpenAlex id (W123 or its URL) or a DOI ("doi:10..." / "10...")."""
        ident = doc_id.strip()
        if ident.startswith(BASE.replace("api.", "")):
            ident = ident.rsplit("/", 1)[1]
        if not re.fullmatch(r"(?i)w\d+", ident):
            ident = "doi:" + _bare_doi(ident)
        work = self.get(f"{BASE}works/{ident}")
        return list((work or {}).get("referenced_works") or [])


def resolve(cited_text: str, doi: str | None, arxiv_id: str | None, run_docs: Mapping[str, str], ctx: Any, *,
            subject_doc: str, span: Span, relation: str = "cites", fetch: Fetch | None = None) -> LinkRecord:
    """`OpenAlex.for_ctx(ctx).resolve(...)`: recorded in the run folder; a replay answers from the record only."""
    return OpenAlex.for_ctx(ctx, fetch=fetch).resolve(cited_text, doi, arxiv_id, run_docs, subject_doc=subject_doc,
                                                      span=span, relation=relation)


def references(doc_id: str, ctx: Any, *, fetch: Fetch | None = None) -> list[str]:
    return OpenAlex.for_ctx(ctx, fetch=fetch).references(doc_id)
