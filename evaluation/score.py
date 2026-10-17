"""Scoring a run against a corpus's ground truth (docs/evidence-system.md A5, additions F4).

Three parts are scored separately, so an error is counted where it happens (the supervisor's A/B/C):

- **A extraction**: items against the ground-truth facts of the same paper and evidence type.
- **B integration**: whether matched measurements are linked to the right condition and metric, and
  whether each study's rag/baseline pair is the true one.
- **C synthesis**: per-study direction, the answer label and the flags, for the engine and every
  baseline answer.

Plus locate recall, cascade contribution, cost and re-execution stability (A5), and from Part F4 (our
additions): bootstrap intervals, the flag scores, the expected-undetermined rule and the per-extractor
rows `evaluate benchmark` pools into the B11 records.

Matching rules (A; B and the pair check reuse A's matching):

1. An item belongs to the paper of its first span's file (manifest `file` or base name).
2. Items and facts are matched only within one paper and one evidence type, **one to one**.
3. A pair is *compatible* when: measurement, |item value - fact value| <= 0.005 (values are normalised
   fractions on both sides); condition, equal `role`; metric, equal `canonical`; author claim, equal
   `direction`.
4. Among compatible pairs the assignment is a minimum-cost assignment (Hungarian method,
   scipy.optimize.linear_sum_assignment) with cost 1, minus 0.5 if the item's span of the type's main
   role (value / condition_label / metric_label / claim) overlaps a placement of that fact with that
   role, minus 0.25 if the item's `label` or `name` equals the fact's label, name or an alias (case
   folded), plus 0.1 x |difference| / 0.005 for measurements. Incompatible pairs cost 10^6, so the
   assignment first maximises the number of compatible pairs (no pair of them can outweigh one more
   match), then prefers pairs whose spans and labels agree; incompatible pairs it is forced into are
   dropped. The result does not depend on input order except between exactly equal costs, where
   items and facts are sorted by id first, so it is deterministic.
5. Precision = matched / items, recall = matched / facts, F1 their harmonic mean (0 when both are 0).
   Counts are pooled (micro) over papers, per evidence type and difficulty level (the level of the
   paper's study), and over all levels.
6. Span accuracy = share of matched pairs whose main-role span overlaps (shares at least one
   character with) a placement of the matched fact with the main role; an item without a main-role
   span is checked with all its spans.

B: of the matched measurements, the condition link (`links.condition`, else `fields.condition`) must
point to a condition item whose `role` is the true condition's role, and the metric link to a metric
item whose `canonical` is the true metric's canonical (`association` = both). `condition_exact` and
`metric_exact` are the stricter variants: the linked item is the one A matched to the true condition
(metric) fact. True pair: the engine's answer names measurement items for treatment and control per
study; the pair is true when A matched them to the facts `effect.treatment` and `effect.control`.

C: for every ground-truth study with an expected direction, the system's `studies` entry with `document`
= the study's paper gives a direction (a missing entry, or one with a direction outside supports /
contradicts / neutral / undetermined, counts as `undetermined`); it is correct when it equals the
expected direction. The expected direction is `effect.direction`, or `undetermined` for a study that is
`relevant: false` (F2; `expected_direction`); a study without either is not scored. So a study whose
true effect is `undetermined` (missing information) or that is irrelevant is right when the system says
`undetermined` or does not answer it (F4). `direction_accuracy` is over all scored studies; `answered`
(share with a determined given direction) and `accuracy_answered` (accuracy over those) are over the
studies with a *determined* expected direction only, so a system that answers everything is not
rewarded for guessing on a study nobody can determine. The confusion counts include expected
`undetermined`. The label is correct when equal to `answer.label`.

Flags (C, F4; `score_flags`): null for an answer without a `flags` key (the baselines, and engine
answers from before Part F). Otherwise per flag in `rules.FLAGS`: the expected set is the papers whose
ground-truth study lists the flag (`duplicate` also when `duplicate_of` is set), the given set is the
answer's top-level `flags[flag]`, else the documents whose study entry lists the flag; tp/fp/fn,
precision (null when nothing was given) and recall (null when nothing was expected). `counts_correct`:
the answer's `counts` for supporting, contradicting and neutral equal the lengths of the ground-truth
`answer` lists, and `undetermined` and `duplicates` too when both sides have them (null without
`counts`). `duplicates_correct`: the documents flagged as duplicates (the answer's `duplicates` list,
else the given `duplicate` set) are exactly the expected ones and each `duplicate_of` matches the
truth's.

Per extractor (`score_extractors`, pooled by `evaluate benchmark`): every item counts for every
extractor id in its `found_by` (an item two extractors found counts for both), so the per-extractor item
counts can exceed A's. Per extractor, evidence type and level (and `all`): items it found, matched (A's
matching), precision, recall, F1, span hits and span accuracy of its matched items, `only` and
`only_matched` as in `cascade`, and for measurements the association (B's `association`: condition role
and metric canonical both right) of its matched items. The recall denominator is the facts of the
(document, evidence type) pairs the extractor was actually called on (its `extractor_call` events in
`events.jsonl`, `truth.Run.events`): a cascade `until_found` or the funnel's `gaps` strategy (Part D)
skips later positions for documents the earlier ones completed, and those documents' facts are not
misses of an extractor that never saw them. Without events (None), or for an extractor id with no event
at all, every fact of the type and level counts. Cost per extractor from the run directory (`truth.Run`): calls and model calls from calls/*.json,
seconds from the extractor_call events, tokens from the record cache when it still exists (else null).

Intervals (`score_intervals`, rules in `stats`): extraction F1 per evidence type over all levels,
resampling papers (per paper: matched, items, facts; the statistic is the micro F1 of the resample);
direction accuracy per system, resampling studies; and for each baseline the paired difference engine
correct minus baseline correct per study.

Locate recall: a placement is inside the scope when one `locate.json` entry for its paper and its
fact's evidence type has a scope that contains it (`evidence.contract.Scope.contains`).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.optimize import linear_sum_assignment

from evidence.contract import Item, Scope
from evidence.rules import FLAGS

from .stats import bootstrap_f1, bootstrap_mean, interval_row
from .truth import ENGINE, MAIN_ROLE, TYPES, Fact, GroundTruth, Run, document_of, paper_ids, read_json

VALUE_TOLERANCE = 0.005
INFEASIBLE = 1e6
ALL = "all"
DIRECTIONS = ("supports", "contradicts", "neutral", "undetermined")
COUNTED = ("supporting", "contradicting", "neutral")      # the counts the label table sees (C1)
OPTIONAL_COUNTS = ("undetermined", "duplicates")          # compared when both sides report them (F1, F2)


# --- small helpers ---------------------------------------------------------------------------------

def prf(matched: int, items: int, facts: int) -> dict[str, Any]:
    precision = matched / items if items else 0.0
    recall = matched / facts if facts else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"items": items, "facts": facts, "matched": matched, "precision": precision, "recall": recall,
            "f1": f1}


def share(good: int, total: int) -> float | None:
    return good / total if total else None


def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _fold(text: Any) -> str:
    return " ".join(str(text).casefold().split())


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def link(item: Item, name: str) -> str | None:
    """The item id a measurement points to for `name` (condition, metric): links first, then fields."""
    target = item.links.get(name) or item.fields.get(name)
    return target if isinstance(target, str) else None


# --- A: matching -----------------------------------------------------------------------------------

def compatible(item: Item, fact: Fact) -> bool:
    f, d = item.fields, fact.data
    if fact.type == "measurement":
        value = _number(f.get("value"))
        return value is not None and abs(value - float(d["value"])) <= VALUE_TOLERANCE + 1e-12
    if fact.type == "condition":
        return f.get("role") == d.get("role")
    if fact.type == "metric":
        return f.get("canonical") == d.get("canonical")
    return f.get("direction") == d.get("direction")


def main_spans(item: Item) -> list[tuple[int, int]]:
    role = MAIN_ROLE[item.evidence_type]
    spans = [s for s in item.spans if s.role == role] or list(item.spans)
    return [(s.selector["start"], s.selector["end"]) for s in spans]


def span_hit(item: Item, fact: Fact, truth: GroundTruth) -> bool:
    places = [(p["start"], p["end"]) for p in truth.placements_of(fact.id, MAIN_ROLE[fact.type])
              if p.get("paper", fact.paper) == fact.paper]
    return any(overlaps(s, p) for s in main_spans(item) for p in places)


def _labels_agree(item: Item, fact: Fact) -> bool:
    given = {_fold(item.fields[k]) for k in ("label", "name") if isinstance(item.fields.get(k), str)}
    known = {_fold(fact.data[k]) for k in ("label", "name") if isinstance(fact.data.get(k), str)}
    known |= {_fold(a) for a in fact.data.get("aliases") or []}
    return bool(given & known)


def cost(item: Item, fact: Fact, truth: GroundTruth) -> float:
    if not compatible(item, fact):
        return INFEASIBLE
    c = 1.0 - 0.5 * span_hit(item, fact, truth) - 0.25 * _labels_agree(item, fact)
    if fact.type == "measurement":
        c += 0.1 * abs((_number(item.fields["value"]) or 0.0) - float(fact.data["value"])) / VALUE_TOLERANCE
    return c


def match(items: list[Item], facts: list[Fact], truth: GroundTruth) -> list[tuple[Item, Fact]]:
    """One-to-one maximum compatible matching with the cost rules of the module docstring."""
    items = sorted(items, key=lambda i: i.item_id)
    facts = sorted(facts, key=lambda f: f.id)
    if not items or not facts:
        return []
    matrix = np.array([[cost(i, f, truth) for f in facts] for i in items])
    rows, cols = linear_sum_assignment(matrix)
    return [(items[r], facts[c]) for r, c in zip(rows, cols) if matrix[r, c] < INFEASIBLE]


class Matching:
    """A's matching for a whole run: item id <-> fact id, and per (paper, type) the counts."""

    def __init__(self, items: list[Item], truth: GroundTruth, files: dict[str, str]) -> None:
        self.truth = truth
        self.items = {i.item_id: i for i in items}
        self.document = {i.item_id: document_of(i, files) for i in items}
        self.fact_of: dict[str, str] = {}
        self.item_of: dict[str, str] = {}
        self.pairs: list[tuple[Item, Fact]] = []
        grouped: dict[tuple[str, str], list[Item]] = defaultdict(list)
        for item in items:
            grouped[(self.document[item.item_id], item.evidence_type)].append(item)
        self.papers = sorted({s["paper"] for s in truth.studies} | {p for p, _ in grouped})
        self.cells: dict[tuple[str, str], tuple[int, int, int, int]] = {}  # (paper, type) -> items, facts, matched, spans ok
        for paper in self.papers:
            for kind in TYPES:
                its, facts = grouped.get((paper, kind), []), truth.of(paper, kind)
                pairs = match(its, facts, truth)
                self.pairs += pairs
                for item, fact in pairs:
                    self.fact_of[item.item_id] = fact.id
                    self.item_of[fact.id] = item.item_id
                hits = sum(span_hit(i, f, truth) for i, f in pairs)
                if its or facts:
                    self.cells[(paper, kind)] = (len(its), len(facts), len(pairs), hits)


def score_extraction(m: Matching) -> dict[str, Any]:
    """A: P/R/F1 and span accuracy per evidence type x level (and over all levels and all types)."""
    sums: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for (paper, kind), cell in m.cells.items():
        level = m.truth.level_of(paper)
        for key in ((kind, level), (kind, ALL), (ALL, level), (ALL, ALL)):
            sums[key] = [a + b for a, b in zip(sums[key], cell)]
    rows = []
    for (kind, level), (n_items, n_facts, matched, hits) in sorted(sums.items()):
        rows.append({"evidence_type": kind, "level": level, **prf(matched, n_items, n_facts),
                     "span_accuracy": share(hits, matched)})
    return {"rows": rows, "missed": sorted(f for f in m.truth.facts if f not in m.item_of),
            "unmatched_items": sorted(i for i in m.items if i not in m.fact_of)}


# --- B: integration --------------------------------------------------------------------------------

def score_integration(m: Matching, answer: dict[str, Any] | None) -> dict[str, Any]:
    truth = m.truth
    per_level: dict[str, Counter[str]] = defaultdict(Counter)
    for item, fact in m.pairs:
        if fact.type != "measurement":
            continue
        true_condition = truth.facts.get(fact.data["condition"])
        true_metric = truth.facts.get(fact.data["metric"])
        condition = m.items.get(link(item, "condition") or "")
        metric = m.items.get(link(item, "metric") or "")
        role_ok = bool(condition and true_condition and condition.fields.get("role") == true_condition.data["role"])
        canon_ok = bool(metric and true_metric and metric.fields.get("canonical") == true_metric.data["canonical"])
        counts = Counter(matched=1, condition_role=role_ok, metric_canonical=canon_ok, association=role_ok and canon_ok,
                         condition_exact=bool(condition and m.fact_of.get(condition.item_id) == fact.data["condition"]),
                         metric_exact=bool(metric and m.fact_of.get(metric.item_id) == fact.data["metric"]))
        for level in (fact.level, ALL):
            per_level[level].update(counts)
    pairs: dict[str, Counter[str]] = defaultdict(Counter)
    studies = {s["document"]: s for s in (answer or {}).get("studies", [])}
    per_study = []
    for study in truth.studies:
        effect = study.get("effect") or {}
        if not effect.get("treatment") or not effect.get("control"):
            continue
        given = studies.get(study["paper"], {})
        treatment = (given.get("treatment") or {}).get("measurement")
        control = (given.get("control") or {}).get("measurement")
        ok = bool(treatment and control and m.fact_of.get(treatment) == effect["treatment"]
                  and m.fact_of.get(control) == effect["control"])
        per_study.append({"study": study["study_id"], "paper": study["paper"], "level": study["level"],
                          "true_pair": ok, "treatment": treatment, "control": control})
        for level in (study["level"], ALL):
            pairs[level].update(studies=1, true_pair=ok)
    rows = []
    for level in sorted(set(per_level) | set(pairs)):
        c, p = per_level.get(level, Counter()), pairs.get(level, Counter())
        rows.append({"level": level, "matched_measurements": c["matched"],
                     "association_accuracy": share(c["association"], c["matched"]),
                     "condition_role_accuracy": share(c["condition_role"], c["matched"]),
                     "metric_accuracy": share(c["metric_canonical"], c["matched"]),
                     "condition_exact": share(c["condition_exact"], c["matched"]),
                     "metric_exact": share(c["metric_exact"], c["matched"]),
                     "studies": p["studies"], "true_pair": share(p["true_pair"], p["studies"])})
    return {"rows": rows, "studies": per_study}


# --- C: synthesis ----------------------------------------------------------------------------------

def expected_direction(study: dict[str, Any]) -> str | None:
    """`effect.direction`; `undetermined` for a `relevant: false` study (F2); None when there is neither."""
    if study.get("relevant") is False:
        return "undetermined"
    return (study.get("effect") or {}).get("direction")


def score_synthesis(truth: GroundTruth, answer: dict[str, Any]) -> dict[str, Any]:
    """Per-study direction accuracy, label correctness and flags of one system's answer.json."""
    given = {s.get("document"): s.get("direction", "undetermined") for s in answer.get("studies", [])}
    per_level: dict[str, Counter[str]] = defaultdict(Counter)
    confusion: Counter[tuple[str, str]] = Counter()
    studies = []
    for study in truth.studies:
        expected = expected_direction(study)
        if expected is None:
            continue
        got = given.get(study["paper"], "undetermined")
        if got not in DIRECTIONS:
            got = "undetermined"
        determined = expected != "undetermined"   # F4: answered/accuracy_answered over determined expectations
        confusion[(expected, got)] += 1
        studies.append({"study": study["study_id"], "paper": study["paper"], "level": study.get("level", "unknown"),
                        "expected": expected, "given": got, "correct": got == expected, "determined": determined})
        for level in (study.get("level", "unknown"), ALL):
            per_level[level].update(studies=1, correct=got == expected, determined=determined,
                                    answered=determined and got != "undetermined",
                                    correct_answered=determined and got == expected and got != "undetermined")
    rows = [{"level": level, "studies": c["studies"], "determined": c["determined"],
             "direction_accuracy": share(c["correct"], c["studies"]),
             "answered": share(c["answered"], c["determined"]),
             "accuracy_answered": share(c["correct_answered"], c["answered"])}
            for level, c in sorted(per_level.items())]
    expected_label = truth.answer.get("label")
    return {"system": answer.get("system", "unknown"), "label": answer.get("label"), "expected_label": expected_label,
            "label_correct": answer.get("label") == expected_label, "rows": rows, "studies": studies,
            "confusion": [{"expected": e, "given": g, "n": n} for (e, g), n in sorted(confusion.items())],
            "flags": score_flags(truth, answer)}


# --- C flags (F4, our addition) --------------------------------------------------------------------

def expected_flags(truth: GroundTruth, flag: str) -> set[str]:
    """Papers whose ground-truth study carries `flag` (F2; `duplicate` also from `duplicate_of`)."""
    return {s["paper"] for s in truth.studies
            if flag in (s.get("flags") or []) or (flag == "duplicate" and s.get("duplicate_of"))}


def score_flags(truth: GroundTruth, answer: dict[str, Any]) -> dict[str, Any] | None:
    """Flag precision and recall, counts and duplicates of one answer (docstring: Flags); None without `flags`."""
    if "flags" not in answer:
        return None
    top = answer.get("flags") if isinstance(answer.get("flags"), dict) else {}
    entries = {s.get("document"): s for s in answer.get("studies", []) if isinstance(s, dict)}
    rows = []
    given_sets: dict[str, set[str]] = {}
    for flag in FLAGS:
        expected = expected_flags(truth, flag)
        if isinstance(top.get(flag), list):
            given = {str(d) for d in top[flag]}
        else:
            given = {d for d, s in entries.items() if flag in (s.get("flags") or [])}
        given_sets[flag] = given
        tp = len(expected & given)
        rows.append({"flag": flag, "expected": sorted(expected), "given": sorted(given), "tp": tp,
                     "fp": len(given - expected), "fn": len(expected - given),
                     "precision": share(tp, len(given)), "recall": share(tp, len(expected))})
    counts = answer.get("counts") if isinstance(answer.get("counts"), dict) else None
    expected_counts = {k: len(v) for k, v in truth.answer.items() if isinstance(v, list)}
    compared = [k for k in (*COUNTED, *OPTIONAL_COUNTS)
                if k in expected_counts and (k in COUNTED or k in (counts or {}))]
    counts_correct = None
    if counts is not None and all(k in expected_counts for k in COUNTED):
        counts_correct = all(counts.get(k) == expected_counts[k] for k in compared)
    expected_dups = {s["paper"]: s.get("duplicate_of") for s in truth.studies
                     if s.get("duplicate_of") or "duplicate" in (s.get("flags") or [])}
    flagged = ({str(d) for d in answer["duplicates"]} if isinstance(answer.get("duplicates"), list)
               else given_sets["duplicate"])
    given_dups = {d: (entries.get(d) or {}).get("duplicate_of") for d in sorted(flagged)}
    return {"rows": rows, "counts_correct": counts_correct,
            "counts": {"expected": {k: expected_counts[k] for k in compared},
                       "given": {k: (counts or {}).get(k) for k in compared}},
            "duplicates_correct": given_dups == expected_dups,
            "duplicates": {"expected": dict(sorted(expected_dups.items())), "given": given_dups}}


# --- intervals (F4, our addition) ------------------------------------------------------------------

def score_intervals(m: Matching | None, systems: list[dict[str, Any]]) -> dict[str, Any]:
    """Bootstrap intervals (docstring: Intervals; rules in stats.py) for extraction F1, direction accuracy
    and the paired engine-minus-baseline difference."""
    extraction = []
    if m is not None:
        for kind in (*TYPES, ALL):
            kinds = TYPES if kind == ALL else (kind,)
            rows = []
            for paper in m.papers:
                cells = [m.cells.get((paper, k), (0, 0, 0, 0)) for k in kinds]
                rows.append((sum(c[2] for c in cells), sum(c[0] for c in cells), sum(c[1] for c in cells)))
            extraction.append(interval_row(bootstrap_f1(rows), evidence_type=kind))
    synthesis = [interval_row(bootstrap_mean(int(s["correct"]) for s in system["studies"]), system=system["system"])
                 for system in systems]
    engine = next((s for s in systems if s["system"] == ENGINE), None)
    paired = []
    if engine is not None:
        engine_correct = {s["paper"]: int(s["correct"]) for s in engine["studies"]}
        for system in systems:
            if system is engine:
                continue
            diffs = [engine_correct[s["paper"]] - int(s["correct"]) for s in system["studies"]
                     if s["paper"] in engine_correct]
            paired.append(interval_row(bootstrap_mean(diffs), system=system["system"]))
    return {"extraction": extraction, "synthesis": synthesis, "paired": paired}


# --- locate, cascade, cost, stability --------------------------------------------------------------

def locate_entries(data: Any) -> Iterable[tuple[str, str, Scope]]:
    """(document, evidence type, scope) from locate.json.

    Accepted shapes: a list of entries, or {"entries"|"documents"|"locate": [...]}, each entry
    {document, evidence_type, scope, strategy?}; or a mapping {document: {evidence_type: {scope, ...}}}
    (also under "documents"). `scope` is the contract's Scope ({kind, ranges}).
    """
    if isinstance(data, dict):
        for key in ("entries", "documents", "locate"):
            if key in data:
                yield from locate_entries(data[key])
                return
        for document, per_type in data.items():
            if isinstance(per_type, dict):
                for kind, entry in per_type.items():
                    if isinstance(entry, dict) and "scope" in entry:
                        yield document, kind, Scope.model_validate(entry["scope"])
        return
    for entry in data or []:
        yield entry["document"], entry["evidence_type"], Scope.model_validate(entry["scope"])


def score_locate(truth: GroundTruth, locate: Any | None) -> dict[str, Any] | None:
    if locate is None:
        return None
    scopes: dict[tuple[str, str], list[Scope]] = defaultdict(list)
    for document, kind, scope in locate_entries(locate):
        scopes[(document, kind)].append(scope)
    sums: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    outside = []
    for p in truth.placements:
        fact = truth.facts.get(p["fact"])
        if fact is None:
            continue
        inside = any(s.contains(p["start"], p["end"]) for s in scopes.get((p["paper"], fact.type), []))
        if not inside:
            outside.append({"fact": p["fact"], "role": p["role"], "paper": p["paper"]})
        for key in ((fact.type, fact.level), (fact.type, ALL), (ALL, fact.level), (ALL, ALL)):
            sums[key][0] += inside
            sums[key][1] += 1
    rows = [{"evidence_type": kind, "level": level, "placements": n, "inside": k, "recall": share(k, n)}
            for (kind, level), (k, n) in sorted(sums.items())]
    return {"rows": rows, "outside": outside}


def score_cascade(m: Matching, run: dict[str, Any] | None) -> dict[str, Any]:
    """Per extractor: items it found, items only it found, and of those how many matched a fact."""
    rows: dict[str, Counter[str]] = defaultdict(Counter)
    for extractor in (run or {}).get("extractors", []):
        rows[extractor].update(found=0)
    for item in m.items.values():
        by = item.found_by or ("unknown",)
        matched = item.item_id in m.fact_of
        for extractor in by:
            rows[extractor].update(found=1, found_matched=matched)
        if len(set(by)) == 1:
            rows[by[0]].update(only=1, only_matched=matched)
    missed = Counter(m.truth.facts[f].type for f in m.truth.facts if f not in m.item_of)
    return {"rows": [{"extractor": e, "found": c["found"], "found_matched": c["found_matched"], "only": c["only"],
                      "only_matched": c["only_matched"]} for e, c in sorted(rows.items())],
            "missed_by_all": dict(sorted(missed.items()))}


# --- per extractor (F4 / B11, our addition) --------------------------------------------------------

def _seconds(event: dict[str, Any]) -> float | None:
    try:
        started, ended = (datetime.fromisoformat(str(event[k]).replace("Z", "+00:00"))
                          for k in ("started_at", "ended_at"))
    except (KeyError, TypeError, ValueError):
        return None
    return (ended - started).total_seconds()


def score_extractor_cost(run: Run | None) -> list[dict[str, Any]] | None:
    """Per extractor id: calls, model calls, tokens (from the cache, else null) and seconds (from the events,
    else null); None for a run without calls/*.json."""
    if run is None or run.calls is None:
        return None
    rows: dict[str, dict[str, Any]] = {}

    def row(extractor: str) -> dict[str, Any]:
        return rows.setdefault(extractor, {"extractor": extractor, "calls": 0, "model_calls": 0,
                                           "input_tokens": 0 if run.usage is not None else None,
                                           "output_tokens": 0 if run.usage is not None else None,
                                           "seconds": 0.0 if run.events is not None else None})

    for call in run.calls:
        r = row(str(call.get("extractor_id") or "unknown"))
        ids = [str(i) for i in call.get("model_calls") or []]
        r["calls"] += 1
        r["model_calls"] += len(ids)
        for usage in (run.usage.get(i) for i in ids) if run.usage is not None else ():
            if usage:
                r["input_tokens"] += usage["input_tokens"]
                r["output_tokens"] += usage["output_tokens"]
    for event in run.events or []:
        r = row(str(event.get("agent_id") or "unknown"))
        seconds = _seconds(event)
        if seconds is not None:
            r["seconds"] += seconds
    for r in rows.values():
        if r["seconds"] is not None:
            r["seconds"] = round(r["seconds"], 3)
    return [rows[e] for e in sorted(rows)]


def _associated(m: Matching, item: Item, fact: Fact) -> bool:
    """B's `association` for one matched measurement: condition role and metric canonical both right."""
    truth = m.truth
    true_condition, true_metric = truth.facts.get(fact.data.get("condition", "")), truth.facts.get(fact.data.get("metric", ""))
    condition, metric = m.items.get(link(item, "condition") or ""), m.items.get(link(item, "metric") or "")
    return bool(condition and true_condition and condition.fields.get("role") == true_condition.data.get("role")
                and metric and true_metric and metric.fields.get("canonical") == true_metric.data.get("canonical"))


def called_on(run: Run | None) -> dict[str, set[tuple[str, str]]] | None:
    """Extractor id -> the (document, evidence type) pairs it has an extractor_call event for; None without events."""
    if run is None or run.events is None:
        return None
    out: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for event in run.events:
        meta = event.get("custom_metadata") if isinstance(event.get("custom_metadata"), dict) else {}
        document, kind = meta.get("document"), meta.get("evidence_type")
        if event.get("agent_id") and document and kind:
            out[str(event["agent_id"])].add((str(document), str(kind)))
    return dict(out)


def fact_counts(truth: GroundTruth, pairs: set[tuple[str, str]] | None = None) -> Counter[tuple[str, str]]:
    """Facts per (evidence type, level) key, over all facts or only those of the (paper, type) pairs given."""
    counts: Counter[tuple[str, str]] = Counter()
    for fact in truth.facts.values():
        if pairs is not None and (fact.paper, fact.type) not in pairs:
            continue
        for key in ((fact.type, fact.level), (fact.type, ALL), (ALL, fact.level), (ALL, ALL)):
            counts[key] += 1
    return counts


def score_extractors(m: Matching, run: Run | None) -> dict[str, Any]:
    """Per extractor id x evidence type x level: P/R/F1, span accuracy, association and `only` counts
    (docstring: Per extractor), plus the per-extractor cost. Recall is against the facts of the
    (document, type) pairs the extractor was called on (`called_on`; all facts without events)."""
    truth = m.truth
    all_facts = fact_counts(truth)
    called = called_on(run)
    # cell: items, matched, span hits, only, only matched, associated (measurements)
    sums: dict[str, dict[tuple[str, str], list[int]]] = defaultdict(lambda: defaultdict(lambda: [0] * 6))
    for extractor in ((run.run or {}) if run else {}).get("extractors", []):
        sums[extractor]
    for extractor, pairs in (called or {}).items():   # a call that found nothing is a row with 0 items
        for document, kind in pairs:
            if kind in TYPES:
                level = truth.level_of(document)
                for key in ((kind, level), (kind, ALL), (ALL, level), (ALL, ALL)):
                    sums[extractor][key]
    for item in m.items.values():
        by = sorted(set(item.found_by or ("unknown",)))
        level = truth.level_of(m.document[item.item_id])
        fact = truth.facts.get(m.fact_of.get(item.item_id, ""))
        matched = fact is not None
        hit = bool(fact) and span_hit(item, fact, truth)
        associated = bool(fact) and fact.type == "measurement" and _associated(m, item, fact)
        only = len(by) == 1
        for extractor in by:
            for key in ((item.evidence_type, level), (item.evidence_type, ALL), (ALL, level), (ALL, ALL)):
                cell = sums[extractor][key]
                cell[0] += 1
                cell[1] += matched
                cell[2] += hit
                cell[3] += only
                cell[4] += only and matched
                cell[5] += associated
    rows = []
    for extractor in sorted(sums):
        facts = fact_counts(truth, called[extractor]) if called and extractor in called else all_facts
        cells = sums[extractor] or {(ALL, ALL): [0] * 6}
        for (kind, level), (n, matched, hits, only, only_matched, associated) in sorted(cells.items()):
            rows.append({"extractor": extractor, "evidence_type": kind, "level": level,
                         **prf(matched, n, facts[(kind, level)]), "span_hits": hits,
                         "span_accuracy": share(hits, matched), "only": only, "only_matched": only_matched,
                         "associated": associated if kind == "measurement" else None,
                         "association_accuracy": share(associated, matched) if kind == "measurement" else None})
    return {"rows": rows, "cost": score_extractor_cost(run), "recall_scope": "called" if called else "all_facts"}


def score_cost(run: dict[str, Any] | None, papers: int) -> dict[str, Any] | None:
    if not run or "cost" not in run:
        return None
    total = dict(run["cost"])
    per_paper = {k: v / papers for k, v in total.items() if isinstance(v, (int, float)) and papers}
    return {"total": total, "per_paper": per_paper, "papers": papers}


def score_stability(reexec: Any | None) -> dict[str, Any] | None:
    """Per extractor, how many re-executed calls had each outcome (identical, items added, ...).

    Reads the engine's reexec.json (evidence/replay.compare): {"calls": [{extractor, outcome,
    items_original, items_reproduced}], "summary": {...}}; `extractor_id` is taken for the extractor
    too. item_stability = items reproduced / items originally found, over the extractor's calls.
    The report's own `summary` is passed through.
    """
    if reexec is None:
        return None
    rows: dict[str, Counter[str]] = defaultdict(Counter)
    items: dict[str, Counter[str]] = defaultdict(Counter)
    for call in reexec.get("calls", []) if isinstance(reexec, dict) else []:
        name = call.get("extractor") or call.get("extractor_id") or "unknown"
        rows[name][call.get("outcome") or "unknown"] += 1
        items[name].update(original=call.get("items_original") or 0, reproduced=call.get("items_reproduced") or 0)
    out: dict[str, Any] = {"rows": [{"extractor": e, "calls": sum(c.values()), "identical": c["identical"],
                                     "identical_share": share(c["identical"], sum(c.values())),
                                     "item_stability": share(items[e]["reproduced"], items[e]["original"]),
                                     "items_original": items[e]["original"], "items_reproduced": items[e]["reproduced"],
                                     "outcomes": dict(c)}
                                    for e, c in sorted(rows.items())]}
    if isinstance(reexec, dict) and "summary" in reexec:
        out["summary"] = reexec["summary"]
    return out


# --- everything ------------------------------------------------------------------------------------

def score(run_dir: Path, corpus: Path, baselines: Iterable[Path] = (), reexec: Path | None = None) -> dict[str, Any]:
    """The report for one run (and any baseline answers) on one corpus."""
    corpus = Path(corpus)
    truth = GroundTruth.load(corpus / "ground_truth.json")
    files = paper_ids(read_json(corpus / "manifest.json"))
    run = Run.load(run_dir, reexec)
    m = Matching(run.items, truth, files)
    systems = []
    if run.answer is not None:
        systems.append(score_synthesis(truth, run.answer))
    for path in baselines:
        systems.append(score_synthesis(truth, read_json(path)))
    return {
        "corpus_id": truth.corpus_id, "levels": truth.levels, "run_id": (run.run or {}).get("run_id", run.root.name),
        "question": truth.question, "extraction": score_extraction(m),
        "integration": score_integration(m, run.answer), "synthesis": systems,
        "intervals": score_intervals(m, systems),
        "locate": score_locate(truth, run.locate), "cascade": score_cascade(m, run.run),
        "extractors": score_extractors(m, run),
        "cost": score_cost(run.run, len(truth.studies)), "stability": score_stability(run.reexec),
    }


def score_answers(corpus: Path, answers: Iterable[Path]) -> dict[str, Any]:
    """C only, for baseline answers without an engine run."""
    truth = GroundTruth.load(Path(corpus) / "ground_truth.json")
    systems = [score_synthesis(truth, read_json(p)) for p in answers]
    return {"corpus_id": truth.corpus_id, "levels": truth.levels, "run_id": None, "question": truth.question,
            "extraction": None, "integration": None, "synthesis": systems,
            "intervals": score_intervals(None, systems), "locate": None, "cascade": None, "extractors": None,
            "cost": None, "stability": None}
