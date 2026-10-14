"""Agreement and what the review missed (labelling gold.py agreement and triage.miss_report, ported).

- Cohen's kappa (scikit-learn `cohen_kappa_score`) between the two most active reviewers of the overlap
  dataset, on the independent round (gold/review.py overlap_records: the earliest snapshot in which both
  had answered a record), for `label` (correct / incorrect / unsure), `keep` (keep/drop by the export's
  own rule, so an unparseable correction counts as dropped) and `vital` (on facts both kept), overall and
  per stratum (triaged / sample, taken from the pool: Argilla never has it), on records that still show
  a current fact (stale ones are counted, not used), with a 95 % percentile bootstrap interval over questions
  (`scipy.stats.bootstrap`, whole questions resampled since the records of one question are not
  independent; resamples where kappa is undefined are counted and left out).
- Triage miss estimate per question, exactly the labelling README formula (triage.miss_report): the kept
  share of the reviewed sample of the rest, times the unreviewed rest, estimates the gold facts triage put
  outside the reviewed tiers, with a 95 % Wilson interval (statsmodels `proportion_confint`);
  `estimated_recall` = tiers_kept / (tiers_kept + sample_kept + estimate), its interval the Wilson bounds
  put into the same ratio.
- The screening's false-negative rate (gold/screening_check.py), Wilson interval as well.

`write_reports` writes `$GOLD/<qid>/report.json` per question and `$GOLD/report.json` over all of them.
"""
from __future__ import annotations

import math
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import bootstrap
from sklearn.metrics import cohen_kappa_score
from statsmodels.stats.proportion import proportion_confint

from . import review
from .export import decide, would_keep

KAPPA_BAR = 0.61  # "substantial" (Landis and Koch 1977)
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 1998
FIELDS = ("label", "keep", "vital")


def wilson(successes: int, trials: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score interval for a proportion; (0, 1) when there are no trials."""
    if trials == 0:
        return 0.0, 1.0
    low, high = proportion_confint(successes, trials, alpha=alpha, method="wilson")
    return max(0.0, float(low)), min(1.0, float(high))


def kappa(a: list[Any], b: list[Any], *, sample_weight: list[float] | None = None,
          weights: str | None = None) -> float | None:
    """Cohen's kappa of two raters; None when undefined (no items, or both used one and the same label)."""
    if not a or len(set(a) | set(b)) < 2:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        value = cohen_kappa_score(a, b, sample_weight=sample_weight, weights=weights)
    return None if math.isnan(value) else float(value)


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def bootstrap_kappa(groups: dict[str, list[tuple[Any, Any]]], *, resamples: int = BOOTSTRAP_RESAMPLES,
                    seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    """95 % percentile interval for kappa, resampling questions (`groups`: question -> label pairs)."""
    keys = sorted(k for k, pairs in groups.items() if pairs)
    base = {"questions": len(keys), "resamples": 0, "undefined": 0, "seed": seed,
            "method": "percentile, resampling questions (scipy.stats.bootstrap)"}
    if len(keys) < 2:
        return {"interval": None, **base}

    def statistic(index: np.ndarray) -> float:
        pairs = [p for i in index for p in groups[keys[int(i)]]]
        value = kappa([x for x, _ in pairs], [y for _, y in pairs])
        return math.nan if value is None else value

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = bootstrap((np.arange(len(keys)),), statistic, n_resamples=resamples, vectorized=False,
                           method="percentile", rng=np.random.default_rng(seed))
    values = result.bootstrap_distribution[~np.isnan(result.bootstrap_distribution)]
    interval = [_round(float(np.percentile(values, 2.5))), _round(float(np.percentile(values, 97.5)))] \
        if values.size else None
    return {"interval": interval, **base, "resamples": resamples,
            "undefined": int(resamples - values.size)}


# --- the overlap ---------------------------------------------------------------------------------------

def _values(field: str, answer: dict[str, Any]) -> Any:
    if field == "keep":
        return "keep" if would_keep(answer) else "drop"
    if field == "vital":
        return answer.get("vital") or "no"
    return answer.get(field)


def overlap_pairs(records: list[dict[str, Any]], strata: dict[str, str]) -> dict[str, Any]:
    """The two most active reviewers (ties by name) and their answers on the records both submitted:
    `pairs` = [(qid, stratum, answer_a, answer_b)]. `strata`: the stratum of each current record id
    (from the pool: Argilla never sees it); a record not in it shows a fact D no longer has (stale) and
    is left out."""
    stale = sum(1 for r in records if r["id"] not in strata and review.submitted(r))
    answered = [(r, review.submitted(r)) for r in records if r["id"] in strata]
    answered = [(r, a) for r, a in answered if a]
    activity = Counter(user for _, answers in answered for user in answers)
    reviewers = sorted(activity, key=lambda user: (-activity[user], user))[:2]
    if len(reviewers) < 2:
        return {"reviewers": reviewers, "pairs": [], "records_with_responses": len(answered),
                "records_one_reviewer": len(answered), "records_other_reviewers": 0, "records_stale": stale}
    a, b = reviewers
    pairs = [(review.record_qid(r) or "_unknown", strata[r["id"]], answers[a], answers[b])
             for r, answers in answered if a in answers and b in answers]
    single = sum(1 for _, answers in answered if len(answers) == 1)
    return {"reviewers": reviewers, "pairs": pairs, "records_with_responses": len(answered),
            "records_one_reviewer": single, "records_other_reviewers": len(answered) - len(pairs) - single,
            "records_stale": stale}


def _field_kappa(field: str, pairs: list[tuple[str, str, dict[str, Any], dict[str, Any]]], *,
                 interval: bool) -> dict[str, Any]:
    if field == "vital":  # vital is only asked of kept facts: compare where both kept
        pairs = [p for p in pairs if _values("keep", p[2]) == _values("keep", p[3]) == "keep"]
    values = [(q, s, _values(field, x), _values(field, y)) for q, s, x, y in pairs]
    by_stratum: dict[str, list[tuple[Any, Any]]] = defaultdict(list)
    by_question: dict[str, list[tuple[Any, Any]]] = defaultdict(list)
    for q, s, x, y in values:
        by_stratum[s].append((x, y))
        by_question[q].append((x, y))
    out: dict[str, Any] = {
        "items": len(values), "kappa": _round(kappa([v[2] for v in values], [v[3] for v in values])),
        "raw_agreement": _round(sum(v[2] == v[3] for v in values) / len(values)) if values else None,
        "by_stratum": {s: {"items": len(p), "kappa": _round(kappa([x for x, _ in p], [y for _, y in p]))}
                       for s, p in sorted(by_stratum.items())},
    }
    if interval:
        boot = bootstrap_kappa(by_question)
        out["kappa_95"] = boot.pop("interval")
        out["bootstrap"] = boot
    return out


def agreement(records: list[dict[str, Any]], strata: dict[str, str], *, interval: bool = True) -> dict[str, Any]:
    """Kappa per field, overall and per stratum (with the bootstrap interval over questions)."""
    found = overlap_pairs(records, strata)
    pairs = found.pop("pairs")
    out = {**found, "items": len(pairs), "questions": len({p[0] for p in pairs}),
           **{field: _field_kappa(field, pairs, interval=interval) for field in FIELDS}}
    keep = out["keep"]["kappa"]
    out["bar"] = KAPPA_BAR
    out["keep_kappa_meets_bar"] = None if keep is None else keep >= KAPPA_BAR
    return out


# --- the triage miss estimate ------------------------------------------------------------------------------

def _recall(tier_kept: int, sample_kept: int, missed: float) -> float | None:
    denominator = tier_kept + sample_kept + missed
    return round(tier_kept / denominator, 4) if denominator else None


def triage_miss(items: dict[str, dict[str, Any]], decisions: list[Any], sizes: dict[str, Any]) -> dict[str, Any] | None:
    """How many gold facts triage put outside the reviewed tiers (labelling triage.miss_report).

    Only decided records count. Tier records still unreviewed or in an unresolved disagreement are
    missing from `tiers_kept`, which biases the recall estimate down; unresolved sample records shrink
    the sample and widen the interval, and they stay in the unreviewed rest.
    """
    if not sizes.get("triaged"):
        return None
    counts: Counter[str] = Counter()
    for decision in decisions:
        item = items.get(decision.candidate_id)
        if item is not None:
            counts[f"{item['stratum']}_reviewed"] += 1
            counts[f"{item['stratum']}_kept"] += bool(decision.keep)
    trials, kept = counts["sample_reviewed"], counts["sample_kept"]
    unreviewed_rest = sizes["rest"] - trials
    low, high = wilson(kept, trials)
    estimate = unreviewed_rest * kept / trials if trials else None
    tier_kept = counts["triaged_kept"]
    bounds = [_recall(tier_kept, kept, unreviewed_rest * high), _recall(tier_kept, kept, unreviewed_rest * low)]
    return {
        "reviewed_tiers": sizes["reviewed_tiers"], "tiers_reviewed": counts["triaged_reviewed"],
        "tiers_unresolved": sizes["reviewed_tiers"] - counts["triaged_reviewed"], "tiers_kept": tier_kept,
        "rest": sizes["rest"], "sampled": sizes["sampled"], "sample_reviewed": trials,
        "sample_unresolved": sizes["sampled"] - trials, "sample_kept": kept,
        "sample_kept_share": round(kept / trials, 4) if trials else None,
        "estimated_missed": round(estimate, 1) if estimate is not None else None,
        "estimated_missed_95": [round(unreviewed_rest * low, 1), round(unreviewed_rest * high, 1)],
        "estimated_recall": _recall(tier_kept, kept, estimate) if estimate is not None else None,
        "estimated_recall_95": bounds if None not in bounds else None,
    }


# --- reports -----------------------------------------------------------------------------------------------

def sources_note(sources: dict[str, Any]) -> dict[str, Any]:
    """Whether the kappa rests on the independent round only: `independent` false (and a warning) when a
    record pair came from the last pull rather than a snapshot, i.e. possibly after people talked."""
    live = sources.get("records_from_live", 0)
    out: dict[str, Any] = {"independent": live == 0}
    if live:
        out["warning"] = (f"{live} overlap record(s) have no snapshot with both answers and come from the last pull, "
                          "which may already reflect discussion or adjudication: run `gold snapshot` when both have "
                          "finished, before they talk (gold/README.md, Review workflow step 5)")
    return out


def question_report(root: Path, qid: str, *, adjudicator: str | None = None) -> dict[str, Any]:
    """One question: review counts, its overlap kappa (no interval: one question), triage miss, screening."""
    from . import screening_check  # it imports wilson from here

    current = review.current_records(root, qid)
    pulled = review.reviews(root, qid)
    decided = decide(current, pulled["review"] + pulled["overlap"], adjudicator)
    overlap, sources = review.overlap_records(root, qid)
    strata = {rid: item["stratum"] for rid, item in current.items()}
    return {
        "qid": qid, "generated_at": review.utc_now(),
        "review": {"records": len(current), "decided": len(decided.decisions),
                   "kept": sum(d.keep for d in decided.decisions), "unreviewed": len(decided.unreviewed),
                   "disagreements": len(decided.disagreements), "stale": len(decided.stale)},
        "kappa": ({**agreement(overlap, strata, interval=False), **sources, **sources_note(sources)}
                  if overlap else None),
        "triage": triage_miss({i["id"]: i for i in current.values()}, decided.decisions, review.strata(root, qid)),
        "screening": screening_check.report(pulled["screening"], screening_check.load_sample(root, qid)),
    }


def write_reports(root: Path, qids: list[str], *, adjudicator: str | None = None) -> dict[str, Any]:
    """Write each question's report.json and the overall $GOLD/report.json; return the overall one."""
    from . import screening_check

    reports = {qid: question_report(root, qid, adjudicator=adjudicator) for qid in qids}
    for qid, report in reports.items():
        review.write_json(review.qdir(root, qid) / "report.json", report)
    overlap: list[dict[str, Any]] = []
    strata: dict[str, str] = {}
    sources = {"snapshots": 0, "records_from_snapshots": 0, "records_from_live": 0}
    for qid in qids:
        records, found = review.overlap_records(root, qid)
        overlap += records
        strata |= {rid: item["stratum"] for rid, item in review.current_records(root, qid).items()}
        sources["snapshots"] += len(found["snapshots"])
        for name in ("records_from_snapshots", "records_from_live"):
            sources[name] += found[name]
    triage = {q: r["triage"] for q, r in reports.items() if r["triage"]}
    screening = {q: r["screening"] for q, r in reports.items() if r["screening"]["sampled"]}
    overall = {
        "generated_at": review.utc_now(), "questions": qids,
        "overlap_questions": (review.read_json(Path(root) / "overlap.json") or {}).get("overlap", []),
        "kappa": {**agreement(overlap, strata), **sources, **sources_note(sources)},
        "triage": {"questions": triage,
                   "estimated_missed": round(sum(t["estimated_missed"] or 0.0 for t in triage.values()), 1),
                   "estimated_missed_bounds": [round(sum(t["estimated_missed_95"][i] for t in triage.values()), 1)
                                               for i in (0, 1)]},
        "screening": {"questions": screening, "overall": screening_check.overall(screening)},
    }
    review.write_json(Path(root) / "report.json", overall)
    return overall
