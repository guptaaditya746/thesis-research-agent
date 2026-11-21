"""Semantic Scholar Graph API client: the writer's research tool (style examples from real papers).

Input:  a query string chosen by code (never by the model), a result limit.
Output: [{paperId, title, year, abstract, oa_license, url, externalIds}] - open-access papers only.

Rules kept in code:
  * the API key comes from S2_API_KEY (environment, else the repo's git-ignored .env) and is sent only as the
    `x-api-key` header; it is never logged, cached or returned;
  * at most one request per 1.1 s across all threads of the process (one shared throttle), retry on 429/5xx
    with backoff;
  * every response is cached under data/cache/s2/, keyed by the request URL (which never holds the key).
The HTTP layer is one function (`fetch`), replaced by a fake in tests, so tests make no network calls.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from evqa.paths import CACHE
from repo_paths import REPO

BASE = "https://api.semanticscholar.org/graph/v1"
CACHE_DIR = CACHE / "s2"
MIN_GAP = 1.1                 # seconds between two requests (limit: 1 request per second)
FIELDS = "title,year,abstract,externalIds,isOpenAccess,openAccessPdf,url"
FIELDS_FULL = FIELDS + ",venue,authors"     # research agent (C8): also venue and authors for citing
OPEN_LICENSES = {"CCBY", "CC0", "CC-BY", "PUBLIC-DOMAIN"}

_lock = threading.Lock()
_last = [0.0]

Fetch = Callable[[str, dict[str, str]], tuple[int, bytes]]


def api_key() -> str | None:
    """S2_API_KEY from the environment, else from REPO/.env. Never printed."""
    if os.environ.get("S2_API_KEY"):
        return os.environ["S2_API_KEY"]
    env = REPO / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == "S2_API_KEY":
                return v.strip().strip("'\"") or None
    return None


def _urllib_fetch(url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:   # noqa: S310 - fixed https host
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _throttle(gap: float = MIN_GAP) -> None:
    """Block until `gap` seconds have passed since the previous request of this process (all threads)."""
    with _lock:
        wait = _last[0] + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()


def get(path: str, params: dict[str, Any], *, fetch: Fetch | None = None, cache_dir: Path | None = None,
        retries: int = 6, gap: float = MIN_GAP) -> dict[str, Any]:
    """GET BASE/path?params as JSON, cached on disk by URL. Raises RuntimeError after `retries` failed tries."""
    url = f"{BASE}/{path.lstrip('/')}?{urllib.parse.urlencode(params)}"
    cdir = Path(cache_dir or CACHE_DIR)
    cfile = cdir / f"{hashlib.sha256(url.encode()).hexdigest()}.json"
    if cfile.is_file():
        return json.loads(cfile.read_text(encoding="utf-8"))["response"]
    headers = {"User-Agent": "research-client"}
    key = api_key()
    if key:
        headers["x-api-key"] = key
    fetch = fetch or _urllib_fetch
    status, body = 0, b""
    for attempt in range(retries):
        _throttle(gap)
        status, body = fetch(url, headers)
        if status == 200:
            data = json.loads(body)
            cdir.mkdir(parents=True, exist_ok=True)
            tmp = cfile.with_suffix(f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps({"url": url, "response": data}, ensure_ascii=False), encoding="utf-8")
            tmp.replace(cfile)
            return data
        if status in (429, 500, 502, 503, 504):
            time.sleep(min(2 ** attempt * 2 * gap, 60))
            continue
        break
    raise RuntimeError(f"S2 {path}: HTTP {status}: {body[:200]!r}")


def _license(p: dict[str, Any]) -> str | None:
    oa = p.get("openAccessPdf") or {}
    lic = (oa.get("license") or "").upper().replace(" ", "")
    return lic or None


def _row(p: dict[str, Any]) -> dict[str, Any]:
    return {"paperId": p.get("paperId"), "title": p.get("title"), "year": p.get("year"),
            "abstract": p.get("abstract"), "oa_license": _license(p),
            "url": (p.get("openAccessPdf") or {}).get("url") or p.get("url"),
            "externalIds": p.get("externalIds") or {}, "venue": p.get("venue") or "",
            "authors": [a.get("name", "") for a in p.get("authors") or []]}


def search(query: str, limit: int = 10, *, open_license_only: bool = True, fields: str = FIELDS,
           open_access_only: bool = True, **kw: Any) -> list[dict[str, Any]]:
    """Papers for `query` (relevance order). open_access_only: only papers with an open-access PDF (S2 filter).
    open_license_only: also only CC BY / CC0 and only papers with an abstract. The request (and cache key) for the
    default arguments is the same as before C8."""
    params = {"query": query, "limit": min(max(limit * 3, limit), 100), "fields": fields}
    if open_access_only:
        params["openAccessPdf"] = ""
    data = get("paper/search", params, **kw)
    rows = [_row(p) for p in data.get("data") or []]
    if open_license_only:
        rows = [r for r in rows if r["oa_license"] in OPEN_LICENSES and r["abstract"]]
    return rows[:limit]


def paper(paper_id: str, **kw: Any) -> dict[str, Any]:
    """One paper by S2 id or 'DOI:...' / 'PMCID:...' / 'PMID:...'."""
    return _row(get(f"paper/{urllib.parse.quote(paper_id, safe=':')}", {"fields": FIELDS}, **kw))


# ---------- the writer's query, built by code from the brief ----------

DESIGN_WORDS = ("randomised", "randomized", "placebo", "dose-ranging", "parallel", "crossover", "open-label")


def query_from_brief(log_md: str, idea_md: str = "") -> str:
    """A search query from the brief's setup lines: population, comparator, design and measures; never the
    made-up drug name (the subject of the brief). Deterministic."""
    import re
    setup = {}
    for m in re.finditer(r"^\*\s*\*\*(.+?):\*\*\s*(.+)$", log_md, re.M):
        setup[m.group(1).strip().lower()] = m.group(2).strip()
    drug_names = set()
    for m in re.finditer(r"^\|\s*R-[^|]+\|\s*([^|]+?)\s*\|", log_md, re.M):
        drug_names |= {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9-]+", m.group(1))}
    parts = []
    design = setup.get("design", "").lower()
    parts += [w for w in DESIGN_WORDS if w in design][:2] or ["randomized"]
    pop = setup.get("patients", "")
    parts.append(pop)
    metrics = setup.get("evaluation metrics", "")
    first = re.split(r",| and ", metrics)[0]
    first = re.sub(r"\b(change in|from baseline|in percentage points|in kg|in mmol/l)\b", "", first, flags=re.I)
    parts.append(first)
    words = " ".join(parts).split()
    words = [w.strip(",.;()") for w in words]
    return " ".join(w for w in words if w and w.lower() not in drug_names) + " trial"
