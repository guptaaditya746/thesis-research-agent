"""Real papers in one cleaned markdown shape: JATS XML from PubMed Central, or Docling markdown, then `tidy`."""
from __future__ import annotations

import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

from evidence.sources.pmc import _first, _local, _text, jats_markdown
from synth2.realpool import clean_text, words
from synth3.realspec import _NUMBER, RealSpec
from synth3.rename import lower_names

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
TOOL = "synth3-pool"
USER_AGENT = "synth3-pool/1 (open-access corpus builder)"
DELAY_S = 1.0
BATCH = 20
BACKOFF_S = (5.0, 30.0, 60.0)
PAGE = 500

_DROP_TAGS = {"fig", "supplementary-material", "fn-group", "ref-list", "ack"}
_EMPTY_BRACKETS = re.compile(r"\s*\[[\s,;–-]*\]|\s*\([\s,;–-]*\)")
_CAPTION = re.compile(r"^\*\*(Table\b[^*]*?)\*\*$")
_REFERENCES = re.compile(r"^#+\s*(?:\d+\.?\s*)?(?:references|bibliography)\s*$", re.I)
_ABSTRACT = re.compile(r"^#+\s*abstract\s*$", re.I)
_URL = re.compile(r"(?:https?://|www\.)\S+")
# a suspended hyphen: "low- to", "short- and", "pre- or", "low- vs"
_SUSPENDED = re.compile(r"(?<=[A-Za-z0-9])-(?= (?:and|or|nor|to|vs|versus|through|plus|und)\b)")


@dataclass(frozen=True)
class PoolPaper:
    id: str
    title: str
    year: int | None
    journal: str
    license: str
    article_type: str
    text: str


def _detach(parent: ET.Element, child: ET.Element) -> None:
    """Remove `child`, keeping its tail (the text after it) in the tree."""
    kids = list(parent)
    i = kids.index(child)
    tail = child.tail or ""
    if i == 0:
        parent.text = (parent.text or "") + tail
    else:
        kids[i - 1].tail = (kids[i - 1].tail or "") + tail
    parent.remove(child)


def _parents(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {c: p for p in root.iter() for c in p}


def _prepare(article: ET.Element) -> None:
    parents = _parents(article)
    for el in list(article.iter()):
        name = _local(el.tag)
        if el in parents and (name in _DROP_TAGS or (name == "xref" and el.get("ref-type") == "bibr")):
            _detach(parents[el], el)
    for p in [e for e in article.iter() if _local(e.tag) == "p"]:
        for tw in [e for e in p.iter() if _local(e.tag) == "table-wrap"]:
            _detach(_parents(p)[tw], tw)
            tw.tail = None
            holder = _parents(article)[p]
            holder.insert(list(holder).index(p) + 1, tw)
    abstract = _first(article, "abstract")
    if abstract is not None:
        for sec in [c for c in abstract if _local(c.tag) == "sec"]:
            title = next((c for c in sec if _local(c.tag) == "title"), None)
            body = " ".join(_text(c) for c in sec if _local(c.tag) == "p")
            p = ET.Element("p")
            p.text = f"{_text(title)}: {body}" if title is not None else body
            p.tail = sec.tail
            abstract.insert(list(abstract).index(sec), p)
            abstract.remove(sec)


def _plain_caption(block: str) -> str:
    m = _CAPTION.match(block.strip())
    if not m:
        return block
    return re.sub(r"^(Table\s+\d+)\.?\s*", r"\1. ", m.group(1).strip())


def _meta(article: ET.Element) -> dict:
    pmc = next((n for n in article.iter() if _local(n.tag) == "article-id"
                and n.get("pub-id-type") in ("pmc", "pmcid")), None)
    pid = _text(pmc) if pmc is not None else ""
    if pid and not pid.upper().startswith("PMC"):
        pid = f"PMC{pid}"
    year = next((n for n in article.iter() if _local(n.tag) == "year"), None)
    journal = _first(article, "journal-title")
    lic = _first(article, "license")
    href = ""
    if lic is not None:
        href = next((v for k, v in lic.attrib.items() if k.endswith("href")), "") or _text(lic)
    return {
        "id": pid,
        "year": int(_text(year)) if year is not None and _text(year).isdigit() else None,
        "journal": _text(journal) if journal is not None else "",
        "license": href,
        "article_type": article.get("article-type", ""),
    }


def jats_paper(data: bytes) -> PoolPaper:
    """One PubMed Central JATS article as a `PoolPaper`. `ValueError` when not XML or there is no body."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"not XML ({exc})") from exc
    article = root if _local(root.tag) == "article" else _first(root, "article")
    if article is None:
        raise ValueError("no <article> in the XML")
    _prepare(article)
    md = jats_markdown(ET.tostring(article))
    md = _EMPTY_BRACKETS.sub("", md)
    text = "\n\n".join(_plain_caption(b) for b in re.split(r"\n\s*\n", md.strip())) + "\n"
    title = _first(article, "article-title")
    return PoolPaper(title=_text(title) if title is not None else "", text=text, **_meta(article))


def _heading(block: str) -> tuple[int, str] | None:
    m = re.match(r"^(#{1,6})\s+(.*)$", block)
    return (len(m.group(1)), _NUMBER.sub("", m.group(2).strip())) if m and "\n" not in block else None


def tidy(text: str, rs: RealSpec) -> str:
    """The one cleaned shape for every source (see the module doc)."""
    text = re.sub(r"<!--.*?-->", "", text.replace("\r\n", "\n"), flags=re.S)
    out: list[str] = []
    skip_level = 0
    for raw in re.split(r"\n\s*\n", text):
        block = raw.strip()
        if not block:
            continue
        if _REFERENCES.match(block):
            break
        head = _heading(block)
        if head:
            level, name = head
            if skip_level and level <= skip_level:
                skip_level = 0
            if not skip_level and level >= 2 and re.search(rs.drop_sections, name, re.I):
                skip_level = level
            if skip_level:
                continue
            if _ABSTRACT.match(block):
                block = "## Abstract"
        elif skip_level:
            continue
        block = _URL.sub("", block)
        block = _EMPTY_BRACKETS.sub("", block)
        block = _plain_caption(block)
        if block.lstrip().startswith("|"):
            out.append(clean_text(block))
        else:   # clean_text joins "treat- ment" (a PDF line break) but must not join "low- to middle-income"
            out.append(clean_text(_SUSPENDED.sub("-\0", block)).replace("\0", ""))
    return "\n\n".join(b for b in out if b) + "\n"


def unfit(paper: PoolPaper, rs: RealSpec) -> str | None:
    """The first reason this paper cannot be a source or test paper, or None when it fits."""
    if paper.article_type not in rs.article_types:
        return f"article type {paper.article_type}"
    if re.search(rs.exclude_title, paper.title, re.I):
        return "title excluded"
    n = words(paper.text)
    if not rs.min_words <= n <= rs.max_words:
        return f"{n} words"
    blocks = re.split(r"\n\s*\n", paper.text)
    if sum(b.lstrip().startswith("|") for b in blocks) < rs.min_tables:
        return "no table"
    lines = paper.text.splitlines()
    if not any(_ABSTRACT.match(ln) for ln in lines):
        return "no abstract"
    if not (any(rs.heading("results", ln) for ln in lines) and any(rs.heading("conclusion", ln) for ln in lines)):
        return "no results or conclusion heading"
    # a paper about something else (a salt-meter education trial) does not fit the planted sentences about tablets
    if rs.min_names and len(lower_names(rs).findall(paper.text)) < rs.min_names:
        return "too few names from name_stems or name_words"
    return None


def _log(message: str) -> None:
    print(message, file=sys.stderr)


class Polite:
    """An HTTP client that spaces its requests by `delay` and waits out a 429 or 503 before trying again."""

    def __init__(self, transport: httpx.BaseTransport | None = None, delay: float = DELAY_S,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 log: Callable[[str], None] = _log):
        self._http = httpx.Client(transport=transport, headers={"User-Agent": USER_AGENT}, timeout=60.0)
        self._delay, self._sleep, self._clock, self._log = delay, sleep, clock, log
        self._last: float | None = None

    def _space(self) -> None:
        if self._last is not None:
            gap = self._delay - (self._clock() - self._last)
            if gap > 0:
                self._sleep(gap)
        self._last = self._clock()

    def get(self, url: str, params: dict) -> bytes:
        params = {"tool": TOOL, **params}
        for attempt in range(len(BACKOFF_S) + 1):
            self._space()
            resp = self._http.get(url, params=params)
            if resp.status_code not in (429, 503):
                resp.raise_for_status()
                return resp.content
            if attempt == len(BACKOFF_S):
                break
            try:
                wait = float(resp.headers["Retry-After"])
            except (KeyError, ValueError):
                wait = BACKOFF_S[attempt]
            self._log(f"HTTP {resp.status_code}; waiting {wait:g}s")
            self._sleep(wait)
        raise httpx.HTTPStatusError(f"still {resp.status_code} after {len(BACKOFF_S)} waits",
                                    request=resp.request, response=resp)


def search(client: Polite, query: str, limit: int) -> list[str]:
    """Up to `limit` PMC ids for `query`, in NCBI's order."""
    ids: list[str] = []
    while len(ids) < limit:
        want = min(PAGE, limit - len(ids))
        data = client.get(EUTILS + "esearch.fcgi", {"db": "pmc", "term": query, "retmode": "xml",
                                                    "retstart": len(ids), "retmax": want})
        page = [_text(n) for n in ET.fromstring(data).iter() if _local(n.tag) == "Id"]
        new = [i for i in dict.fromkeys(page) if i not in ids]
        ids += new
        if len(page) < want or not new:
            break
    return ids


def articles(data: bytes) -> list[bytes]:
    """One serialised `<article>` per article of an efetch `pmc-articleset`."""
    root = ET.fromstring(data)
    found = [root] if _local(root.tag) == "article" else [c for c in root if _local(c.tag) == "article"]
    return [ET.tostring(a, encoding="utf-8") for a in found]


def article_id(data: bytes) -> str | None:
    """The PMC id (`PMC123`) written inside one article, or None."""
    for node in ET.fromstring(data).iter():
        if _local(node.tag) == "article-id" and node.get("pub-id-type") in ("pmc", "pmcid"):
            return _pmc(_text(node))
    return None


def _pmc(i: str) -> str:
    return i if i.upper().startswith("PMC") else f"PMC{i}"


def fetch_pool(rs: RealSpec, pool: Path, client: Polite) -> dict:
    """Search, fetch only what is not saved yet, then rebuild `full/` and `index.json` from every raw file."""
    from jsonio import write_text_atomic
    from synth3.pool import load_index, rebuild

    raw = pool / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    ids = [_pmc(i) for i in search(client, rs.query, rs.max_fetch)]
    known = {r["id"] for r in load_index(pool)}
    have = {p.stem for p in raw.glob("*.xml")}
    todo = [i for i in ids if i not in have and i not in known]
    returned: set[str] = set()
    for k in range(0, len(todo), BATCH):
        batch = todo[k:k + BATCH]
        data = client.get(EUTILS + "efetch.fcgi", {"db": "pmc", "retmode": "xml",
                                                   "id": ",".join(i.removeprefix("PMC") for i in batch)})
        for art in articles(data):
            pid = article_id(art)
            if pid is None or not re.fullmatch(r"PMC\d+", pid):
                continue
            write_text_atomic(raw / f"{pid}.xml", art.decode("utf-8"))
            returned.add(pid)
    missing = [i for i in todo if i not in returned]
    rows = rebuild(pool, rs, missing=missing)
    return {"found": len(ids), "fetched": len(returned), "cached": sum(i in have for i in ids),
            "kept": sum(r["kept"] for r in rows), "unfit": dict(Counter(r["why"] for r in rows if not r["kept"]))}
