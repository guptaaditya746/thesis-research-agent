"""Research tool loop for the writer (prompt version v2r, VENDORED.md C8): Qwen searches Semantic Scholar itself.

Input:  a brief (idea_sparse.md + experimental_log.md). Code turns it into a short study description in which the
        made-up drug names and codes are replaced by "the study drug" (the model never sees them).
Loop:   one DSPy call per step (ResearchStep): action "search" + query, or "done" + picks. Code enforces:
          * at most MAX_SEARCHES searches; when the cap is reached, one last FinalPicks call;
          * a query has at most 12 words, is new (case and spacing ignored), and names no brief drug or code;
          * at most MAX_STEPS model calls in all (rejected steps count), so a model that keeps failing stops;
          * a pick must be an id that appeared in the results; "style" needs a CC BY / CC0 licence and an abstract
            of >= 120 words; at most 2 style and 4 reference picks (first ones kept).
        Every step (query, results, picks, rejections) is appended to <work_dir>/research.jsonl.
Output: {"style": [result rows], "references": [result rows], "steps": [...], "queries": [...]}.
Search goes through evqa.research.s2 (shared 1.1 s throttle, disk cache); model calls through evqa.lm (recorded
cache) and the 3 shared slot files in data/cache/claude-slots, like the writer's own calls.
"""
from __future__ import annotations

import fcntl
import json
import re
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

import dspy
from pydantic import BaseModel

from evqa.contracts import StepLLM
from evqa.paths import CACHE

MAX_SEARCHES = 5
MIN_SEARCHES = 2          # r2: a "done" before 2 searches is rejected (r1 stopped after one copied query)
MAX_STEPS = MAX_SEARCHES + 3
MAX_QUERY_WORDS = 12
MAX_STYLE, MAX_REFS = 2, 4
RESULTS_PER_SEARCH = 8
ABSTRACT_CHARS = 300
STUDY_DRUG = "the study drug"


class Pick(BaseModel):
    id: str
    use: Literal["style", "reference"]
    why: str = ""


class ResearchStepR1(dspy.Signature):
    # r1 (first real run, 21 Nov): Qwen copied the Normal example query verbatim for both briefs and searched
    # once, also for a drug-naive brief (wrong population). Kept for the record; r2 below is used.
    """Decide the next step of a literature search for a trial report: search once more, or finish and pick papers.

    Inputs: study describes the trial (the drug is called "the study drug"). queries_tried lists earlier queries.
    results lists papers found so far: id, title, year, venue, license, abstract_start. searches_left is how many
    searches remain. feedback is empty, or says why the previous step was rejected; fix that in this step.
    Output: action "search" with query (at most 12 words, new, about the drug class, design, population or
    outcomes; never a drug name) and picks []; or action "done" with query "" and picks. Each pick is {id, use,
    why}: id copied from results; use "style" for an open-licensed (cc by / cc0) trial report whose abstract is a
    good model of how to write such a report, "reference" for a paper the Introduction or Related Work can cite
    (same disease, similar add-on design or outcomes). At most 2 style and 4 reference picks; why is one sentence.

    Normal: results empty -> action "search", query "placebo-controlled add-on to metformin type 2 diabetes HbA1c
    randomized trial".
    Confusing: results hold a meta-analysis and an unrelated obesity trial only -> action "search" with a different
    query (e.g. "dose-ranging trial glucose-lowering drug metformin background"); a style pick needs a licence.
    Missing: searches_left 0 or nothing relevant after several searches -> action "done" with the relevant picks
    found so far, or picks [] when none is relevant.
    """
    study: str = dspy.InputField()
    queries_tried: str = dspy.InputField()
    results: str = dspy.InputField()
    searches_left: int = dspy.InputField()
    feedback: str = dspy.InputField()
    action: Literal["search", "done"] = dspy.OutputField()
    query: str = dspy.OutputField()
    picks: list[Pick] = dspy.OutputField()


class ResearchStep(dspy.Signature):
    """Decide the next step of a literature search for a trial report: search once more, or finish and pick papers.

    Inputs: study describes the trial (the drug is called "the study drug"). queries_tried lists earlier queries.
    results lists papers found so far: id, title, year, venue, license, abstract_start. searches_left is how many
    searches remain. feedback is empty, or says why the previous step was rejected; fix that in this step.
    Output: action "search" with query and picks [], or action "done" with query "" and picks.
    Query rules: at most 12 words; never a drug name; built from THIS study's words: its population and background
    treatment exactly (e.g. "on metformin" vs "drug-naive, newly diagnosed"), its design, its main outcome. Each new
    query changes one aspect (population words, design words such as dose-ranging, or outcome) to find papers the
    earlier ones missed. Search at least twice before "done".
    Picks: each {id, use, why}; id copied from results. use "style": an open-licensed (cc by / cc0) trial report
    with the same kind of population and design, whose abstract is a good model of how to write such a report.
    use "reference": a paper the Introduction or Related Work can cite because it studies the same population and
    a similar question. At most 2 style and 4 reference picks; why names the shared population or design.

    Examples (an asthma study, to show the rules; never reuse these words for another disease):
    Normal: study "adults with asthma on inhaled corticosteroids; the study drug vs placebo; FEV1; week 12", nothing
    tried -> search "add-on inhaled corticosteroid asthma adults placebo-controlled FEV1 trial".
    Confusing: results are mostly trials in children or in drug-naive patients, but the study is in adults already
    treated -> search again with the population words changed ("adults uncontrolled on inhaled corticosteroids
    add-on trial"); do not pick the children trials as references.
    Missing: searches_left 0, or two searches found nothing with the same population -> action "done" with only
    the matching papers, or picks [].
    """
    study: str = dspy.InputField()
    queries_tried: str = dspy.InputField()
    results: str = dspy.InputField()
    searches_left: int = dspy.InputField()
    feedback: str = dspy.InputField()
    action: Literal["search", "done"] = dspy.OutputField()
    query: str = dspy.OutputField()
    picks: list[Pick] = dspy.OutputField()


class FinalPicks(dspy.Signature):
    """Pick the papers a trial report should use, from the search results (no more searching).

    Inputs: study describes the trial (the drug is called "the study drug"); results lists papers found: id, title,
    year, venue, license, abstract_start.
    Output: picks, each {id, use, why}: id copied from results; use "style" for an open-licensed (cc by / cc0) trial
    report whose abstract models how to write such a report, "reference" for a paper the Introduction or Related
    Work can cite because it studies the same population and a similar question. At most 2 style and 4 reference
    picks; why names the shared population or design.

    Normal: a CC BY placebo-controlled add-on trial with a full abstract -> {use "style"}; a similar trial with
    license "none" -> {use "reference"}.
    Confusing: a relevant paper whose license is empty -> it may be a reference, never style.
    Missing: no relevant paper in results -> picks [].
    """
    study: str = dspy.InputField()
    results: str = dspy.InputField()
    picks: list[Pick] = dspy.OutputField()


# ---------- brief -> study description (no drug names) ----------

def drug_names(idea_md: str, log_md: str) -> list[str]:
    """The brief's made-up drug names and codes: the Subject column of the value rows, codes like ORD-399."""
    names: set[str] = set()
    for m in re.finditer(r"^\|\s*R-[^|]+\|\s*([^|]+?)\s*\|", log_md, re.M):
        for part in re.split(r",|\band\b|\(|\)|/|\+", m.group(1)):
            part = part.strip()
            if part and part.lower() not in {"placebo"}:
                names.add(part)
    names |= set(re.findall(r"\b[A-Z]{2,5}-\d{2,5}\b", idea_md + "\n" + log_md))
    return sorted(names, key=len, reverse=True)


def study_text(idea_md: str, log_md: str) -> str:
    """Design, patients, arms, time points and measures from the brief, drug names replaced."""
    keep = ("design", "patients", "arms", "time points", "evaluation metrics", "baselines compared")
    lines = []
    for m in re.finditer(r"^\*\s*\*\*(.+?):\*\*\s*(.+)$", log_md, re.M):
        if m.group(1).strip().lower() in keep:
            lines.append(f"{m.group(1).strip()}: {m.group(2).strip()}")
    text = "\n".join(lines)
    for n in drug_names(idea_md, log_md):
        text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(n)}(?![A-Za-z0-9])", STUDY_DRUG, text, flags=re.I)
    return text.replace(f"{STUDY_DRUG} ({STUDY_DRUG})", STUDY_DRUG)


# ---------- shared slot files (same as the writer's ClaudeCodeLM.slot) ----------

@contextmanager
def file_slot(lock_dir: Path, n: int = 3, poll: float = 0.2):
    lock_dir.mkdir(parents=True, exist_ok=True)
    while True:
        for i in range(n):
            fh = open(lock_dir / f"slot-{i}.lock", "a+")
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                fh.close()
                continue
            try:
                yield i
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
                fh.close()
            return
        time.sleep(poll)


def make_research_lm(cfg: StepLLM | None = None, lock_dir: Path | None = None) -> dspy.BaseLM:
    """Qwen orch-model, thinking off, recorded in the evqa LM cache, each real call holding a shared slot file."""
    from evqa import lm as evqa_lm
    cfg = cfg or StepLLM(backend="qwen", model="orch-model", think=False)
    raw = evqa_lm.qwen_ask(cfg.model, think=cfg.think) if cfg.backend == "qwen" else evqa_lm.claude_ask(cfg.model)
    ldir = lock_dir or CACHE / "claude-slots"

    def ask(text: str) -> str:
        with file_slot(ldir):
            return raw(text)
    return evqa_lm.make_lm(cfg, ask=ask)


# ---------- the loop ----------

def _norm_q(q: str) -> str:
    return " ".join(q.lower().split())


def query_problem(q: str, tried: list[str], forbidden: list[str]) -> str | None:
    if not q.strip():
        return "empty query"
    if len(q.split()) > MAX_QUERY_WORDS:
        return f"more than {MAX_QUERY_WORDS} words"
    low = q.lower()
    for n in forbidden:
        if re.search(rf"(?<![a-z0-9]){re.escape(n.lower())}(?![a-z0-9])", low):
            return "names the study drug"
    if _norm_q(q) in {_norm_q(t) for t in tried}:
        return "repeated query"
    return None


def _license(r: dict[str, Any]) -> str:
    return r.get("oa_license") or "none"


def _shown(r: dict[str, Any]) -> dict[str, Any]:
    return {"id": r["paperId"], "title": r.get("title"), "year": r.get("year"), "venue": r.get("venue") or "",
            "license": _license(r), "abstract_start": (r.get("abstract") or "")[:ABSTRACT_CHARS]}


def check_picks(picks: list[dict[str, Any]], results: dict[str, dict[str, Any]],
                skip_style_ids: set[str] = frozenset()) -> tuple[list, list, list]:
    """(style rows, reference rows, rejections) from the model's picks."""
    from evqa.research import s2
    style, refs, rejected = [], [], []
    for p in picks:
        r = results.get(p.get("id", ""))
        if r is None:
            rejected.append({**p, "reason": "id not in results"})
        elif p.get("use") == "style":
            if r.get("oa_license") not in s2.OPEN_LICENSES:
                rejected.append({**p, "reason": f"style needs CC BY / CC0, license is {_license(r)}"})
            elif len((r.get("abstract") or "").split()) < 120:
                rejected.append({**p, "reason": "style needs an abstract of >= 120 words"})
            elif r["paperId"] in skip_style_ids:
                rejected.append({**p, "reason": "already a stored style example"})
            elif any(x["paperId"] == r["paperId"] for x in style):
                rejected.append({**p, "reason": "duplicate"})
            elif len(style) >= MAX_STYLE:
                rejected.append({**p, "reason": f"more than {MAX_STYLE} style picks"})
            else:
                style.append({**r, "why": p.get("why", "")})
        elif p.get("use") == "reference":
            if any(x["paperId"] == r["paperId"] for x in refs):
                rejected.append({**p, "reason": "duplicate"})
            elif len(refs) >= MAX_REFS:
                rejected.append({**p, "reason": f"more than {MAX_REFS} reference picks"})
            elif not r.get("authors") or not r.get("year"):
                rejected.append({**p, "reason": "no author or year to cite"})
            else:
                refs.append({**r, "why": p.get("why", "")})
        else:
            rejected.append({**p, "reason": "use must be style or reference"})
    return style, refs, rejected


def research(paper_dir: Path, *, lm: dspy.BaseLM | None = None, search: Callable[..., list] | None = None,
             log_path: Path | None = None, max_searches: int = MAX_SEARCHES, min_searches: int = MIN_SEARCHES,
             skip_style_ids: set[str] = frozenset()) -> dict[str, Any]:
    from evqa.research import s2
    paper_dir = Path(paper_dir)
    idea = (paper_dir / "idea_sparse.md").read_text(encoding="utf-8")
    log_md = (paper_dir / "experimental_log.md").read_text(encoding="utf-8")
    forbidden = drug_names(idea, log_md)
    study = study_text(idea, log_md)
    lm = lm or make_research_lm()
    search = search or (lambda q, n: s2.search(q, n, open_license_only=False, open_access_only=False,
                                               fields=s2.FIELDS_FULL))
    tried: list[str] = []
    results: dict[str, dict[str, Any]] = {}
    steps: list[dict[str, Any]] = []

    def log(rec: dict[str, Any]) -> None:
        steps.append(rec)
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    log({"event": "research_start", "study": study, "forbidden_terms": len(forbidden)})   # names stay out of logs
    picks: list[dict[str, Any]] | None = None
    calls = 0
    feedback = ""
    with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
        while calls < MAX_STEPS and len(tried) < max_searches:
            calls += 1
            shown = json.dumps([_shown(r) for r in results.values()], ensure_ascii=False)
            try:
                out = dspy.Predict(ResearchStep)(study=study, queries_tried=json.dumps(tried), results=shown,
                                                 searches_left=max_searches - len(tried), feedback=feedback)
            except Exception as e:  # noqa: BLE001 - an unparseable step counts against the cap
                log({"event": "step_error", "step": calls, "error": str(e)[:300]})
                feedback = f"step {calls}: the reply could not be parsed; answer with the three output fields"
                continue
            if out.action == "done" and len(tried) < min(min_searches, max_searches):
                log({"event": "done_rejected", "step": calls, "reason": f"fewer than {min_searches} searches"})
                feedback = f"step {calls}: search at least {min_searches} times before done; send a new query"
                continue
            if out.action == "done":
                picks = [p.model_dump() if hasattr(p, "model_dump") else dict(p) for p in out.picks]
                log({"event": "done", "step": calls, "picks": picks})
                break
            problem = query_problem(out.query, tried, forbidden)
            if problem:
                log({"event": "query_rejected", "step": calls, "reason": problem,
                     "query": out.query if not problem.startswith("names") else "[withheld]"})
                # the step number keeps each retry prompt new (a recorded LM would replay the same reply)
                feedback = (f"step {calls}: query rejected ({'names the study drug: use the drug class or design'
                            if problem.startswith('names') else problem}); send a different query")
                continue
            feedback = ""
            rows = search(out.query, RESULTS_PER_SEARCH)
            tried.append(out.query)
            new = [r for r in rows if r.get("paperId") and r["paperId"] not in results]
            for r in new:
                results[r["paperId"]] = r
            log({"event": "search", "step": calls, "query": out.query, "n_results": len(rows), "n_new": len(new),
                 "titles": [r.get("title") for r in new]})
        if picks is None:   # cap reached (searches or steps): one final picking call
            try:
                out = dspy.Predict(FinalPicks)(study=study, results=json.dumps(
                    [_shown(r) for r in results.values()], ensure_ascii=False))
                picks = [p.model_dump() if hasattr(p, "model_dump") else dict(p) for p in out.picks]
            except Exception as e:  # noqa: BLE001
                log({"event": "final_error", "error": str(e)[:300]})
                picks = []
            log({"event": "done_at_cap", "searches": len(tried), "calls": calls, "picks": picks})
    style, refs, rejected = check_picks(picks, results, skip_style_ids)
    log({"event": "research_end", "searches": len(tried), "style": [r["paperId"] for r in style],
         "references": [r["paperId"] for r in refs], "rejected": rejected})
    return {"style": style, "references": refs, "rejected": rejected, "queries": tried, "steps": steps}


# ---------- rows -> writer inputs ----------

def _surname(name: str) -> str:
    parts = name.replace(".", " ").split()
    return parts[-1] if parts else ""


def _gist(abstract: str) -> str:
    """First sentence of the abstract without numbers (the model must not copy results from references)."""
    first = re.split(r"(?<=[.!?])\s+", (abstract or "").strip())[0] if abstract else ""
    first = re.sub(r"^(Background|Aims?|Objectives?|Introduction|Purpose)(/\w+)?\s*:\s*", "", first, flags=re.I)
    # decimals, percentages and 3+ digit numbers out; small integers stay ("type 2", "52 weeks" would go)
    first = re.sub(r"[-−+]?\d+[.,]\d+\s*%?|\d+\s*%|\b\d{3,}\b", "#", first)
    return first[:220].strip()


def as_references(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        authors = r.get("authors") or []
        text = (authors[0] + (" et al." if len(authors) > 1 else "")) if authors else ""
        out.append({"id": f"S2:{r['paperId']}", "first_author": _surname(authors[0]) if authors else "",
                    "authors_text": text, "year": r.get("year"), "venue": r.get("venue") or "",
                    "title": r.get("title") or "", "gist": _gist(r.get("abstract") or ""),
                    "abstract": r.get("abstract") or "", "license": _license(r), "why": r.get("why", "")})
    return out


def as_style(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": f"S2:{r['paperId']}", "about": "", "license": r.get("oa_license"), "source": r.get("url") or "",
             "why": r.get("why", ""), "sections": {"Abstract": (r.get("abstract") or "").strip()}} for r in rows]
