"""The screening check (labelling screening.py, ported): how many relevant papers did C1's screening mark
not relevant?

C1 screens every paper of the corpus for a question (whole chunks, no ranker) and records a status per
paper in screening.jsonl. A paper marked `not_relevant` is never extracted, so a wrong "not relevant"
silently removes its facts from the gold. `gold screening-sample` draws a seeded random sample of those
papers per question (default 5) into screening.sample.json; `gold screening-push` loads them into the
`<name>-screening` dataset, where people answer "is this paper relevant? if yes, which facts are
missing?"; `gold agreement` estimates the screening's false-negative rate per question with a 95 % Wilson
interval, scaled to the number of papers marked not relevant. Facts people add on these records join the
key like missing facts (gold/export.py).

A paper counts as relevant when anyone who checked it says so (the conservative reading for a
completeness claim). Papers left unread (`no_text`, `error`) are outside the sampling frame; the sample
file counts them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import argilla_io, review
from .agreement import wilson

DEFAULT_SIZE = 5
DEFAULT_SEED = "gold-v1"
SAMPLE_FILE = "screening.sample.json"


def sample(root: Path, qid: str, *, size: int = DEFAULT_SIZE, seed: str = DEFAULT_SEED) -> dict[str, Any]:
    """Draw `size` papers at random (fixed by `seed`) from those screened not relevant; write the sample."""
    rows = review.screening(root, qid)
    status = [str(r.get("status")) for r in rows]
    frame = sorted(str(r["paper_id"]) for r in rows if r.get("status") == "not_relevant")
    drawn = review.seeded_order(frame, f"{seed}:screening:{qid}")[:max(0, size)]
    out = {"qid": qid, "seed": seed, "size": size, "papers_screened": len(rows), "not_relevant": len(frame),
           "relevant": status.count("relevant"), "unread": status.count("no_text") + status.count("error"),
           "sampled": len(drawn), "papers": sorted(drawn), "drawn_at": review.utc_now()}
    review.write_json(review.qdir(root, qid) / SAMPLE_FILE, out)
    return out


def load_sample(root: Path, qid: str) -> dict[str, Any] | None:
    return review.read_json(review.qdir(root, qid) / SAMPLE_FILE)


def records(root: Path, qid: str, corpus: review.Corpus, *, question: str, concept_md: str) -> list[dict[str, Any]]:
    """Argilla records for the drawn papers: the question, the concept and the whole paper."""
    drawn = load_sample(root, qid)
    if not drawn:
        return []
    out = []
    for paper in drawn["papers"]:
        file = corpus.file_name(paper)
        text = corpus.text(file) if corpus.has(file) else "_This paper is not in the corpus directory._"
        out.append(argilla_io.screening_record(
            qid, paper, question=question, concept_md=concept_md, paper_md=argilla_io.paper_markdown(text, file),
            not_relevant=drawn["not_relevant"], sampled=drawn["sampled"]))
    return out


def verdicts(record: dict[str, Any]) -> list[str]:
    return [str(a["relevant"]) for a in review.submitted(record).values() if a.get("relevant") in ("yes", "no")]


def _r(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def report(records: list[dict[str, Any]], drawn: dict[str, Any] | None) -> dict[str, Any]:
    """One question: papers checked, found relevant, the false-negative rate with a 95 % Wilson interval,
    and the relevant papers estimated among all marked not relevant (rate x N, interval x N)."""
    n_total = int((drawn or {}).get("not_relevant") or max(
        [int((r.get("metadata") or {}).get("not_relevant_total") or 0) for r in records] or [0]))
    checked = [(r, v) for r in records if (v := verdicts(r))]
    found = sorted(str((r.get("metadata") or {}).get("paper_id") or r["id"]) for r, v in checked if "yes" in v)
    k, n = len(found), len(checked)
    low, high = wilson(k, n)
    rate = k / n if n else None
    return {"not_relevant": n_total, "sampled": int((drawn or {}).get("sampled") or len(records)),
            "unread": (drawn or {}).get("unread"), "checked": n, "found_relevant": k,
            "false_negative_rate": _r(rate), "false_negative_rate_95": [_r(low), _r(high)],
            "estimated_missed_papers": _r(n_total * rate, 1) if rate is not None else None,
            "estimated_missed_papers_95": [_r(n_total * low, 1), _r(n_total * high, 1)],
            "papers_found_relevant": found}


def overall(sections: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Across questions: the per-question estimates added up (a stratified total; summing the bounds is
    conservative), and the plain Wilson interval of the pooled checked papers, which weights questions by
    their sample, not by N (labelling screening.report)."""
    total = sum(s["not_relevant"] for s in sections.values())
    checked = sum(s["checked"] for s in sections.values())
    relevant = sum(s["found_relevant"] for s in sections.values())
    low, high = wilson(relevant, checked)
    missed = sum(s["estimated_missed_papers"] or 0.0 for s in sections.values())
    return {"not_relevant": total, "checked": checked, "found_relevant": relevant,
            "estimated_missed_papers": round(missed, 1),
            "estimated_missed_papers_bounds": [round(sum(s["estimated_missed_papers_95"][i] for s in sections.values()), 1)
                                               for i in (0, 1)],
            "checked_rate": _r(relevant / checked) if checked else None,
            "checked_rate_95": [_r(low), _r(high)]}
