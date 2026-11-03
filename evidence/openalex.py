"""Builds-on links through OpenAlex (Task 5.2).

`resolve` turns one cited work (a DOI, an arXiv id or just the cited text) into a `LinkRecord`: OpenAlex finds the
work (`/works/doi:...`, or a title search), and the work is matched to a paper of the run by its DOI or its title in
the paper's head (`run_docs` maps doc id -> the paper's text). A work that is not a paper of the run is kept with
`outside_set=True`, never dropped. `references` lists a work's `referenced_works` (for scoring). `read_link` reads the
open relation of a citing sentence with the DSPy step `ReadLink`.

Every HTTP answer is recorded in a `JsonlCache` keyed by its URL, like a model call: a replay (`offline=True`) answers
from the record and never touches the network; a request missing from the record raises `NotRecorded`."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

import dspy

from modelcall.cache import JsonlCache, cache_key
from .claims import run_step
from .contract import Span
from .records import LinkRecord
from .steps import Step

__all__ = ["NotRecorded", "OpenAlex", "ReadLink", "configure", "read_link", "references", "resolve"]

BASE = "https://api.openalex.org/"
Fetch = Callable[[str], "dict[str, Any] | None"]   # url -> parsed JSON, or None for a 404


class NotRecorded(RuntimeError):
    """A replay needs an OpenAlex answer the record does not hold."""


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


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _bare_doi(doi: str) -> str:
    return re.sub(r"(?i)^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", doi.strip()).lower()


class OpenAlex:
    """An OpenAlex client whose every answer goes through `cache` (the run's record of HTTP calls)."""

    def __init__(self, cache: JsonlCache | None = None, *, fetch: Fetch | None = None, offline: bool = False) -> None:
        self.cache, self._fetch, self.offline = cache, fetch or _urlopen, offline

    def get(self, url: str) -> dict[str, Any] | None:
        key = cache_key({"openalex": url})
        hit = self.cache.get(key) if self.cache is not None else None
        if hit is not None:
            return json.loads(hit["output"])
        if self.offline:
            raise NotRecorded(f"offline replay: no recorded OpenAlex answer for {url}")
        body = self._fetch(url)
        if self.cache is not None:
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
            return results[0] if results else None
        return None

    def resolve(self, cited_text: str, doi: str | None, arxiv_id: str | None, run_docs: Mapping[str, str], *,
                subject_doc: str, span: Span, relation: str = "cites") -> LinkRecord:
        """The link from `subject_doc` to the cited work. `object_doc` is the run paper the work is, else None and
        `outside_set` is True (the work is kept either way)."""
        work = self.work(cited_text, doi, arxiv_id)
        object_doc = self._run_doc(work, run_docs) if work else None
        work_doi = _bare_doi(work["doi"]) if work and work.get("doi") else None
        ref = doi.strip() if doi else arxiv_id.strip() if arxiv_id else work_doi or cited_text
        return LinkRecord(subject_doc=subject_doc, relation=relation, object_ref=ref, object_doc=object_doc,
                          outside_set=object_doc is None, span=span)

    @staticmethod
    def _run_doc(work: Mapping[str, Any], run_docs: Mapping[str, str]) -> str | None:
        doi = _bare_doi(work["doi"]) if work.get("doi") else None
        title = _norm(work.get("title") or work.get("display_name") or "")
        for doc_id, text in run_docs.items():
            if doi and doi in text[:3000].casefold():
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


_CLIENT: OpenAlex | None = None


def configure(client: OpenAlex) -> None:
    """Set the client the module functions use (the run's recorded one)."""
    global _CLIENT
    _CLIENT = client


def _client() -> OpenAlex:
    if _CLIENT is None:
        raise RuntimeError("no OpenAlex client: call evidence.openalex.configure(OpenAlex(cache)) first")
    return _CLIENT


def resolve(cited_text: str, doi: str | None, arxiv_id: str | None, run_docs: Mapping[str, str], *,
            subject_doc: str, span: Span, relation: str = "cites") -> LinkRecord:
    return _client().resolve(cited_text, doi, arxiv_id, run_docs, subject_doc=subject_doc, span=span, relation=relation)


def references(doc_id: str) -> list[str]:
    return _client().references(doc_id)
