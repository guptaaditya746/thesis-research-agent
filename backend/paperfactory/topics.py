"""Real topic lists and number ranges, fetched ONCE by code and saved as seed files (22 Nov 2026).

Why: asked for "1-2 real conditions", Qwen picked type 2 diabetes for all 25 medicine papers and one privacy act for
all 30 law papers (outside review of the 40-paper pilot). Now code samples one topic per cluster from a real list.
Qwen never calls an API; runs read only the saved files, so they are repeatable.

  packs/topics/<field>.json   {"source", "fetched", "query", "topics": [{"id", "name", "subfield", "description",
                               "keywords", "works"}]}
  packs/topics/ranges.json     number ranges measured from real records (ClinicalTrials.gov enrolment), with the
                               query and the date, read by the field packs' "numbers" specs ("from": "<key>").

The field pack says what to fetch ("topics": {"openalex": {"subfields": [...], "include": [...], "exclude": [...]},
"keep": N}); this file has no field names. The OpenAlex key is read from the environment or the repo .env
(OPENALEX_API_KEY) and is never printed or logged.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import statistics
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from repo_paths import REPO

from paperfactory.packs import PACKS, Field

TOPICS = PACKS / "topics"
UA = {"User-Agent": "research-client/1.0"}


def _key() -> str:
    if os.environ.get("OPENALEX_API_KEY"):
        return os.environ["OPENALEX_API_KEY"]
    env = REPO / ".env"
    for line in env.read_text(encoding="utf-8").splitlines() if env.is_file() else []:
        if line.startswith("OPENALEX_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("OPENALEX_API_KEY is not set (environment or repo .env)")


def _get(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def openalex_topics(spec: dict[str, Any], keep: int) -> list[dict[str, Any]]:
    """Topics of the given OpenAlex subfields, most-studied first, filtered by include / exclude words (any case,
    in the name or keywords)."""
    key, out = _key(), []
    inc = [x.lower() for x in spec.get("include", [])]
    exc = [x.lower() for x in spec.get("exclude", [])]
    for sub in spec["subfields"]:
        cursor = "*"
        while cursor:
            q = urllib.parse.urlencode({"filter": f"subfield.id:{sub}", "per-page": 200, "cursor": cursor,
                                        "sort": "works_count:desc", "api_key": key})
            d = _get(f"https://api.openalex.org/topics?{q}")
            for t in d["results"]:
                kws = [k if isinstance(k, str) else k.get("display_name", "") for k in t.get("keywords") or []]
                text = " ".join([t["display_name"], *kws]).lower()
                if inc and not any(w in text for w in inc):
                    continue
                if any(w in text for w in exc):
                    continue
                out.append({"id": t["id"].rsplit("/", 1)[-1], "name": t["display_name"],
                            "subfield": t["subfield"]["display_name"], "description": t.get("description", ""),
                            "keywords": kws[:8], "works": t.get("works_count", 0)})
            cursor = d["meta"].get("next_cursor")
    out.sort(key=lambda t: -t["works"])
    seen, uniq = set(), []
    for t in out:
        if t["id"] not in seen:
            seen.add(t["id"])
            uniq.append(t)
    return uniq[:keep]


def ctgov_enrolment(query: dict[str, str], pages: int = 5) -> dict[str, Any]:
    """Actual enrolment of completed trials matching the query: percentiles. ClinicalTrials.gov API v2, no key."""
    sizes, token = [], None
    for _ in range(pages):
        q = {"pageSize": "1000", "fields": "EnrollmentInfo", "countTotal": "true"} | query
        if token:
            q["pageToken"] = token
        d = _get("https://clinicaltrials.gov/api/v2/studies?" + urllib.parse.urlencode(q))
        for st in d.get("studies", []):
            info = st.get("protocolSection", {}).get("designModule", {}).get("enrollmentInfo", {})
            if info.get("type") == "ACTUAL" and isinstance(info.get("count"), int) and info["count"] > 0:
                sizes.append(info["count"])
        token = d.get("nextPageToken")
        if not token:
            break
    sizes.sort()
    pct = lambda p: sizes[min(len(sizes) - 1, int(p / 100 * len(sizes)))]  # noqa: E731
    return {"n": len(sizes), "p10": pct(10), "p25": pct(25), "median": int(statistics.median(sizes)),
            "p75": pct(75), "p90": pct(90)}


def fetch(f: Field) -> Path:
    spec = f.raw.get("topics")
    if not spec:
        raise SystemExit(f"field pack {f.name!r} has no 'topics' spec")
    topics = openalex_topics(spec["openalex"], spec.get("keep", 40))
    TOPICS.mkdir(parents=True, exist_ok=True)
    path = TOPICS / f"{f.name}.json"
    path.write_text(json.dumps({"source": "OpenAlex topics API", "fetched": dt.date.today().isoformat(),
                                "query": spec["openalex"], "topics": topics}, indent=1, ensure_ascii=False),
                    encoding="utf-8")
    return path


def fetch_ranges() -> Path:
    """Number ranges from real records. Phase 3 interventional trials, completed (ClinicalTrials.gov)."""
    query = {"filter.overallStatus": "COMPLETED", "query.term": "AREA[Phase]PHASE3 AND AREA[StudyType]INTERVENTIONAL"}
    path = TOPICS / "ranges.json"
    path.write_text(json.dumps({"fetched": dt.date.today().isoformat(), "ranges": {
        "phase3_enrolment": {"source": "ClinicalTrials.gov API v2", "query": query, **ctgov_enrolment(query)}}},
        indent=1), encoding="utf-8")
    return path


def load(f: Field) -> list[dict[str, Any]]:
    path = TOPICS / f"{f.name}.json"
    if not path.is_file():
        raise ValueError(f"no topic list for {f.name}: run `paperfactory fetch-topics --field {f.name}`")
    return json.loads(path.read_text(encoding="utf-8"))["topics"]


def ranges() -> dict[str, Any]:
    path = TOPICS / "ranges.json"
    return json.loads(path.read_text(encoding="utf-8"))["ranges"] if path.is_file() else {}


def pick(f: Field, seed: Any, n: int) -> list[dict[str, Any]]:
    """n different topics for one world, the same for the same seed. Topics of different subfields first, so the
    clusters of a world differ in more than wording."""
    topics = load(f)
    rng = random.Random(f"{seed}:topics:{f.name}")
    pool = topics[:]
    rng.shuffle(pool)
    out, subs = [], set()
    for t in pool:
        if len(out) < n and t["subfield"] not in subs:
            out.append(t)
            subs.add(t["subfield"])
    for t in pool:
        if len(out) < n and t not in out:
            out.append(t)
    if len(out) < n:
        raise ValueError(f"{f.name}: {len(out)} topics in the list, {n} clusters asked")
    return out
