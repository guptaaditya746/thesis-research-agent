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
   fractions on both sides); condition, equal `role` (an item without a `role` field, from a best or inventory
   protocol: the same name, by `canon.key` or case-folded, or its label span on the condition's placement);
   metric, equal `canonical`, or the item's canonical and the fact's name have one `canon.key` (`latency`, which
   truth files under `other`); dataset (matched only when the run has dataset items or its protocol declares the
   type), the same name; author claim, equal `direction`.
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
   character with) a placement of the matched fact with the main role, over the pairs whose fact has one
   (dataset facts have none); an item without a main-role span is checked with all its spans.

Question kinds (question-first redesign; `score(question_id=...)`, evidence/questions.yaml; without an id, the
question the run's frozen protocol asks, evidence/questions.answered_by): A is computed the same way for every kind,
over the evidence types the run's protocol extracts (`scored_types`; report.json `extraction.scored_types`), so
its `all` / `all` row means "all the types this protocol extracts". B and C follow the question's kind (`integration_kind`, `score_kind`; their docstrings): effect is what this
docstring describes, against the question's own expected answer (`effect_truth`; the corpus's own question keeps
the saved answer, so its numbers are unchanged); inventory, consistency and best compare the answer with
evaluation/expected.py's. Baseline answers are scored on C only. Intervals and attribution are for effect only.

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
`undetermined` or does not answer it (F4). The label is correct when equal to `answer.label`.
Correctness, completeness and traceability are the supervisor's three comparison criteria (STATE.md §1
§7; docs/evidence-system.md Part G.1); the definitions that follow are ours. `direction_accuracy`
(correctness) is over all scored studies. **completeness** = share of the studies with a *determined*
expected direction (not `undetermined`) the system gives a direction for, and `accuracy_answered` =
accuracy over those, so a system that answers everything is not rewarded for guessing on a study nobody
can determine. **traceability** = share of the cited passages (`answer.citations`, a baseline's
`[{document, start, end}]) that overlap (share a character with) a ground-truth placement of role `value`,
`metric_label` or `claim` of the paper they cite (strict: a passage touching only a condition label traces
nothing), over all cited passages; **overlap** is the lenient share, over a placement of any role. The
citations the baseline dropped (`answer.dropped_citations`: ones naming no retrieved passage, the clearest untraceable
case) count as untraced; `null` for an answer without citations (the engine's spans are scored in A).
The confusion counts include expected `undetermined`.

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

Attribution (`attribute`, Tim M2 §5C, our addition; with `evaluate score --oracle`): per scored study, whether
a system's direction is right and whether the oracle's is (evaluation/oracle.py: the synthesis on perfect
evidence; or the RAG baseline on the passages holding the values). A study the system gets wrong is an
`upstream` error (extraction or retrieval) when the oracle gets it right, a `downstream` one (synthesis or
reasoning) when the oracle is wrong too. Counted per level and `all`, only for the oracle's counterpart
(`oracle-synthesis` -> the engine, `rag-oracle-passages` -> the RAG baseline); any other system is listed under
`not_attributed`, since an oracle that is right says nothing about where another system went wrong.

Locate recall: a placement is inside the scope when one `locate.json` entry for its paper and its
fact's evidence type has a scope that contains it (`evidence.contract.Scope.contains`).

Funnel (`score_funnel`, Part D, our addition; None for a run without funnel.json): per document, from the
extractor_call events, the calls, model calls and tokens (the record cache's usage, else null) it cost, and
from funnel.json whether the screen rejected it, whether it was skipped and the position the funnel stopped
after; the means per document; the stop-position histogram (`stopped_after` as a string, `exhausted` when
the funnel ran out of positions without a direction, `skipped` for a screened-out document that got no
extraction; in `all` mode every document is `exhausted`, since the funnel never stops a run there); and,
when the run has `screen` events, screening precision and recall of the decision "relevant" against the
ground truth's `relevant` (F2; a study without the key is relevant): a paper the screen keeps counts as
positive, so recall is the share of the truly relevant papers kept (a screened-out relevant paper is a lost
study) and precision the share of the kept papers that are relevant. `evaluate compare` puts
`calls_per_document`, `tokens_per_document`, `screen_precision` and `screen_recall` beside the headline
numbers, so an `all` run and a `gaps` run of the same protocol stand in two rows.
"""
from __future__ import annotations

import dataclasses
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.optimize import linear_sum_assignment

from evidence.contract import Item, Scope
from evidence.evidence_types import EvidenceType
from evidence.kinds import best as best_rules
from evidence.protocol import Protocol
from evidence.protocol import load as load_protocol
from evidence.questions import QuestionEntry, QuestionTruth
from evidence.questions import answered_by, answers_asked, load as load_questions
from evidence.rundir import PROTOCOL_FILE
from evidence.rules import FLAGS
from synth import vocab

from . import canon
from .expected import expected as expected_answer
from .expected import saved_answer
from .stats import bootstrap_f1, bootstrap_mean, interval_row
from .truth import DATASET, ENGINE, MAIN_ROLE, TYPES, Fact, GroundTruth, Run, document_of, paper_ids, read_json

REPO = Path(__file__).resolve().parents[1]
DEFAULT_QUESTION = "rag-factuality"   # the corpus's own question (its saved answer, _question_text)

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

QUESTION_CANONICALS = frozenset(vocab.QUESTION_METRICS)   # factual_accuracy, hallucination_rate: compared as they are


def same_metric(fields: dict[str, Any], data: dict[str, Any]) -> bool:
    """A metric item names the true metric: equal `canonical`, or, only for a fact truth files under `other` (or
    another canonical that is not a question metric's), a question-specific item canonical such as `latency` that
    has the `canon.key` of the fact's name. A fact with a question metric's canonical needs the equal canonical."""
    if fields.get("canonical") == data.get("canonical"):
        return True
    if data.get("canonical") in QUESTION_CANONICALS:
        return False
    k = canon.key("metric", str(fields.get("canonical") or ""))
    return k is not None and canon.key("metric", str(data.get("name") or "")) == k


def _same_name(item: Item, fact: Fact, target: canon.Target) -> bool:
    """The item's label or name and the fact's label, name or an alias are one name: equal `canon.key`, or equal
    when case-folded with whitespace collapsed."""
    given = [str(item.fields[k]) for k in ("label", "name") if isinstance(item.fields.get(k), str)]
    known = [str(fact.data[k]) for k in ("label", "name") if isinstance(fact.data.get(k), str)]
    known += [str(a) for a in fact.data.get("aliases") or []]
    keys = {k for n in known if (k := canon.key(target, n)) is not None}
    return bool({_fold(n) for n in given} & {_fold(n) for n in known}) or any(canon.key(target, n) in keys
                                                                              for n in given)


def compatible(item: Item, fact: Fact, truth: GroundTruth | None = None) -> bool:
    f, d = item.fields, fact.data
    if fact.type == "measurement":
        value = _number(f.get("value"))
        return value is not None and abs(value - float(d["value"])) <= VALUE_TOLERANCE + 1e-12
    if fact.type == "condition":
        if "role" in f:
            return f.get("role") == d.get("role")
        # a protocol without roles (best, inventory): the same name, or the item's label span on the condition's
        return _same_name(item, fact, "condition") or (truth is not None and span_hit(item, fact, truth))
    if fact.type == "metric":
        return same_metric(f, d)
    if fact.type == DATASET:
        return _same_name(item, fact, "dataset")
    return f.get("direction") == d.get("direction")


def main_spans(item: Item) -> list[tuple[int, int]]:
    role = MAIN_ROLE.get(item.evidence_type)
    spans = [s for s in item.spans if s.role == role] or list(item.spans)
    return [(s.selector["start"], s.selector["end"]) for s in spans]


def placed(fact: Fact, truth: GroundTruth) -> bool:
    """The fact has a main-role placement (dataset facts have none: span accuracy leaves them out)."""
    return any(p.get("paper", fact.paper) == fact.paper for p in truth.placements_of(fact.id, MAIN_ROLE[fact.type]))


def overlap_size(item: Item, fact: Fact, truth: GroundTruth) -> int:
    """Characters the item's main-role spans share with the fact's main-role placements (summed over pairs)."""
    places = [(p["start"], p["end"]) for p in truth.placements_of(fact.id, MAIN_ROLE[fact.type])
              if p.get("paper", fact.paper) == fact.paper]
    return sum(max(0, min(a[1], b[1]) - max(a[0], b[0])) for a in main_spans(item) for b in places)


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
    if not compatible(item, fact, truth):
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


def facts_of(truth: GroundTruth, types: Iterable[str]) -> list[Fact]:
    """Every fact of the given evidence types, the dataset facts included when `dataset` is one of them."""
    types = set(types)
    return [f for f in (*truth.facts.values(), *(truth.datasets.values() if DATASET in types else ())) if f.type in types]


class Matching:
    """A's matching for a whole run: item id <-> fact id, and per (paper, type) the counts.

    `types` are the evidence types matched: the four of TYPES, and `dataset` when the run has dataset items or the
    caller passes it (a protocol that declares the type), so a run without dataset items is scored as before."""

    def __init__(self, items: list[Item], truth: GroundTruth, files: dict[str, str],
                 types: Iterable[EvidenceType] | None = None) -> None:
        self.truth = truth
        self.types: tuple[EvidenceType, ...] = (tuple(types) if types is not None else
                                                TYPES + ((DATASET,) if any(i.evidence_type == DATASET for i in items)
                                                         else ()))
        self.facts = {f.id: f for f in facts_of(truth, self.types)}
        self.items = {i.item_id: i for i in items}
        self.document = {i.item_id: document_of(i, files) for i in items}
        self.fact_of: dict[str, str] = {}
        self.item_of: dict[str, str] = {}
        self.pairs: list[tuple[Item, Fact]] = []
        grouped: dict[tuple[str, str], list[Item]] = defaultdict(list)
        for item in items:
            grouped[(self.document[item.item_id], item.evidence_type)].append(item)
        self.papers = sorted({s["paper"] for s in truth.studies} | {p for p, _ in grouped})
        # (paper, type) -> items, facts, matched, spans ok, matched with a placed fact (span accuracy's denominator)
        self.cells: dict[tuple[str, str], tuple[int, int, int, int, int]] = {}
        for paper in self.papers:
            for kind in self.types:
                its, facts = grouped.get((paper, kind), []), truth.of(paper, kind)
                pairs = match(its, facts, truth)
                self.pairs += pairs
                for item, fact in pairs:
                    self.fact_of[item.item_id] = fact.id
                    self.item_of[fact.id] = item.item_id
                hits = sum(span_hit(i, f, truth) for i, f in pairs)
                if its or facts:
                    self.cells[(paper, kind)] = (len(its), len(facts), len(pairs), hits,
                                                 sum(placed(f, truth) for _, f in pairs))


def scored_types(protocol: Protocol | None, items: Iterable[Item] = ()) -> tuple[EvidenceType, ...]:
    """A's evidence types: the protocol's own (those of TYPES and `dataset` it declares), so A's `all` / `all` row is
    over all the types this protocol extracts and a protocol is never charged with facts of a type it does not ask
    for (an inventory of metrics is not scored on conditions). Without a protocol, the four of TYPES, plus `dataset`
    when the run has dataset items."""
    if protocol is not None:
        return tuple(t for t in (*TYPES, DATASET) if t in protocol.evidence_types)
    return TYPES + ((DATASET,) if any(i.evidence_type == DATASET for i in items) else ())


def protocol_matching(items: list[Item], truth: GroundTruth, files: dict[str, str],
                      protocol: Protocol | None) -> Matching:
    """A's matching of a run with its protocol: over the protocol's evidence types (`scored_types`)."""
    return Matching(items, truth, files, scored_types(protocol, items))


def score_extraction(m: Matching) -> dict[str, Any]:
    """A: P/R/F1 and span accuracy per evidence type x level (and over all levels and all types); span accuracy is
    over the matched facts that have a placement (a dataset fact has none). `scored_types` are the evidence types
    matched (`scored_types()`): the `all` rows pool these only."""
    sums: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])
    for (paper, kind), cell in m.cells.items():
        level = m.truth.level_of(paper)
        for key in ((kind, level), (kind, ALL), (ALL, level), (ALL, ALL)):
            sums[key] = [a + b for a, b in zip(sums[key], cell)]
    rows = []
    for (kind, level), (n_items, n_facts, matched, hits, placed_matched) in sorted(sums.items()):
        rows.append({"evidence_type": kind, "level": level, **prf(matched, n_items, n_facts),
                     "span_accuracy": share(hits, placed_matched)})
    return {"rows": rows, "scored_types": list(m.types), "missed": sorted(f for f in m.facts if f not in m.item_of),
            "unmatched_items": sorted(i for i in m.items if i not in m.fact_of)}


# --- B: integration --------------------------------------------------------------------------------

def score_integration(m: Matching, answer: dict[str, Any] | None, truth: GroundTruth | None = None) -> dict[str, Any]:
    """B for an effect answer (module docstring); `truth` is the effect truth of the question (`effect_truth`: its
    studies' `effect` pairs the question metric), m.truth when not given."""
    truth = truth or m.truth
    per_level: dict[str, Counter[str]] = defaultdict(Counter)
    for item, fact in m.pairs:
        if fact.type != "measurement":
            continue
        true_condition = truth.facts.get(fact.data["condition"])
        true_metric = truth.facts.get(fact.data["metric"])
        condition = m.items.get(link(item, "condition") or "")
        metric = m.items.get(link(item, "metric") or "")
        role_ok = bool(condition and true_condition and condition.fields.get("role") == true_condition.data["role"])
        canon_ok = bool(metric and true_metric and same_metric(metric.fields, true_metric.data))
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


# "traced" (strict traceability): the cited passage overlaps a value, metric-label or claim placement of the cited
# paper. Span overlap only: not "same study or condition", and not entailment (the passage need not support the claim).
TRACED_ROLES = ("value", "metric_label", "claim")


def score_citations(truth: GroundTruth, citations: list[dict[str, Any]] | None,
                    dropped: list[dict[str, Any]] | None = None) -> dict[str, Counter[str]] | None:
    """Traceability counts per level (and ALL): cited passages, `overlaps_placement` (those overlapping a
    placement of any role of the cited paper) and `traced` (those overlapping a `value`, `metric_label` or
    `claim` placement). The baseline's dropped citations (naming no retrieved passage) are cited passages
    that are never traced. A cited paper outside the ground truth counts under ALL only.
    None without a `citations` list (the engine)."""
    if citations is None:
        return None
    places: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    for p in truth.placements:
        places[p["paper"]].append((p["start"], p["end"], p.get("role", "")))
    cited: dict[str, Counter[str]] = defaultdict(Counter)
    for c, kept in [(c, True) for c in citations] + [(c, False) for c in dropped or []]:
        paper = c.get("document")
        span = (int(c["start"]), int(c["end"]))
        hits = [role for a, b, role in places.get(paper, []) if kept and overlaps(span, (a, b))]
        level = truth.level_of(paper)
        for key in ((level, ALL) if level != "unknown" else (ALL,)):
            cited[key].update(citations=1, overlaps_placement=bool(hits),
                              traced=any(role in TRACED_ROLES for role in hits))
    return cited


def score_synthesis(truth: GroundTruth, answer: dict[str, Any]) -> dict[str, Any]:
    """Per-study direction accuracy, completeness, traceability, label correctness and flags of one
    system's answer.json (the module docstring, C)."""
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
                                    complete=determined and got != "undetermined",
                                    correct_answered=determined and got == expected and got != "undetermined")
    cited = score_citations(truth, answer.get("citations"), answer.get("dropped_citations"))
    rows = []
    for level, c in sorted(per_level.items()):
        n = cited.get(level, Counter()) if cited is not None else None
        rows.append({"level": level, "studies": c["studies"], "determined": c["determined"],
                     "direction_accuracy": share(c["correct"], c["studies"]),
                     "completeness": share(c["complete"], c["determined"]),
                     "accuracy_answered": share(c["correct_answered"], c["complete"]),
                     "citations": None if n is None else n["citations"],
                     "traceability": None if n is None else share(n["traced"], n["citations"]),
                     "overlap": None if n is None else share(n["overlaps_placement"], n["citations"])})
    expected_label = truth.answer.get("label")
    errors = [] if expected_label is not None else ["gold answer has no label"]   # undefined, not a match
    return {"system": answer.get("system", "unknown"), "label": answer.get("label"), "expected_label": expected_label,
            "label_correct": None if expected_label is None else answer.get("label") == expected_label,
            "errors": errors, "rows": rows, "studies": studies,
            "confusion": [{"expected": e, "given": g, "n": n} for (e, g), n in sorted(confusion.items())],
            "flags": score_flags(truth, answer)}


# --- C attribution (Tim M2 §5C, our addition) -----------------------------------------------------

def attribute(truth: GroundTruth, system_answer: dict[str, Any], oracle_answer: dict[str, Any]) -> list[dict[str, Any]]:
    """Per scored study: system and oracle correct, and `error` None, `upstream` (only the system wrong) or
    `downstream` (both wrong)."""
    oracle_ok = {s["study"]: s["correct"] for s in score_synthesis(truth, oracle_answer)["studies"]}
    out = []
    for s in score_synthesis(truth, system_answer)["studies"]:
        ok = oracle_ok[s["study"]]
        out.append({"study": s["study"], "system_correct": s["correct"], "oracle_correct": ok,
                    "error": None if s["correct"] else "upstream" if ok else "downstream"})
    return out


# An oracle stands in for one system with its input made perfect; its errors say nothing about another system's.
COUNTERPARTS = {"oracle-synthesis": (ENGINE,), "rag-oracle-passages": ("rag-baseline",)}


def score_attribution(truth: GroundTruth, answers: list[dict[str, Any]], oracle_answer: dict[str, Any] | None
                      ) -> dict[str, Any] | None:
    """`attribute` for the answers of the oracle's counterpart (COUNTERPARTS), with counts per level and `all`;
    every other system but the oracle under `not_attributed`; None without an oracle."""
    if oracle_answer is None:
        return None
    oracle_system = oracle_answer.get("system", "oracle")
    counterparts = COUNTERPARTS.get(oracle_system, ())
    level = {s["study_id"]: s.get("level", "unknown") for s in truth.studies}
    systems: list[dict[str, Any]] = []
    skipped: list[str] = []
    for answer in answers:
        if answer.get("system") == oracle_system:
            continue
        if answer.get("system") not in counterparts:
            skipped.append(answer.get("system", "unknown"))
            continue
        studies = attribute(truth, answer, oracle_answer)
        counts: dict[str, Counter[str]] = defaultdict(Counter)
        for s in studies:
            for key in (level[s["study"]], ALL):
                counts[key].update(studies=1, system_correct=s["system_correct"], oracle_correct=s["oracle_correct"],
                                   upstream=s["error"] == "upstream", downstream=s["error"] == "downstream")
        rows = [{"level": lv, **{k: c[k] for k in ("studies", "system_correct", "oracle_correct", "upstream",
                                                   "downstream")}} for lv, c in sorted(counts.items())]
        systems.append({"system": answer.get("system", "unknown"), "studies": studies, "rows": rows})
    return {"oracle": oracle_system, "systems": systems, "not_attributed": skipped}


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
        for kind in (*m.types, ALL):
            kinds = m.types if kind == ALL else (kind,)
            rows = []
            for paper in m.papers:
                cells = [m.cells.get((paper, k), (0, 0, 0, 0, 0)) for k in kinds]
                rows.append((sum(c[2] for c in cells), sum(c[0] for c in cells), sum(c[1] for c in cells)))
            extraction.append(interval_row(bootstrap_f1(rows), evidence_type=kind, n_rows=len(rows)))
    synthesis = [interval_row(bootstrap_mean(int(s["correct"]) for s in system["studies"]), system=system["system"],
                              n_rows=len(system["studies"])) for system in systems]
    engine = next((s for s in systems if s["system"] == ENGINE), None)
    paired = []
    if engine is not None:
        engine_correct = {s["paper"]: int(s["correct"]) for s in engine["studies"]}
        for system in systems:
            if system is engine:
                continue
            diffs = [engine_correct[s["paper"]] - int(s["correct"]) for s in system["studies"]
                     if s["paper"] in engine_correct]
            excluded = sorted({s["paper"] for s in system["studies"]} ^ engine_correct.keys())   # in only one system
            paired.append(interval_row(bootstrap_mean(diffs), system=system["system"], n_rows=len(diffs),
                                       excluded_ids=excluded))
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


def screen_extractors(run: dict[str, Any] | None) -> set[str]:
    """Extractor ids of the funnel's screening pseudo type (Part D): no facts, so no extraction rows."""
    specs = (run or {}).get("extractor_specs") or {}
    return {ext for ext, spec in specs.items() if isinstance(spec, dict) and list(spec.get("evidence_types") or []) == ["screen"]}


def score_cascade(m: Matching, run: dict[str, Any] | None) -> dict[str, Any]:
    """Per extractor: items it found, items only it found, and of those how many matched a fact. The
    screening extractors are left out (they have no facts; their cost is in `extractors.cost`)."""
    rows: dict[str, Counter[str]] = defaultdict(Counter)
    for extractor in (run or {}).get("extractors", []):
        if extractor not in screen_extractors(run):
            rows[extractor].update(found=0)
    for item in m.items.values():
        by = item.found_by or ("unknown",)
        matched = item.item_id in m.fact_of
        for extractor in by:
            rows[extractor].update(found=1, found_matched=matched)
        if len(set(by)) == 1:
            rows[by[0]].update(only=1, only_matched=matched)
    missed = Counter(f.type for f in m.facts.values() if f.id not in m.item_of)
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
                and metric and true_metric and same_metric(metric.fields, true_metric.data))


def called_on(run: Run | None) -> dict[str, set[tuple[str, str]]] | None:
    """Extractor id -> the (document, evidence type) pairs it has an extractor_call event for; None without events."""
    if run is None or run.events is None:
        return None
    out: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for event in run.events:
        meta = event.get("custom_metadata") if isinstance(event.get("custom_metadata"), dict) else {}
        document, kind = meta.get("document"), meta.get("evidence_type")
        if event.get("agent_id") and document and kind and event.get("status") != "skipped":   # skipped: not called
            out[str(event["agent_id"])].add((str(document), str(kind)))
    return dict(out)


def fact_counts(truth: GroundTruth, pairs: set[tuple[str, str]] | None = None,
                types: Iterable[str] = TYPES) -> Counter[tuple[str, str]]:
    """Facts of `types` per (evidence type, level) key, over all facts or only those of the (paper, type) pairs given."""
    counts: Counter[tuple[str, str]] = Counter()
    for fact in facts_of(truth, types):
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
    all_facts = fact_counts(truth, types=m.types)
    called = called_on(run)
    screens = screen_extractors(run.run if run else None)   # no facts: rows for them would only say 0 (cost kept)
    # cell: items, matched, span hits, only, only matched, associated (measurements), matched with a placed fact
    sums: dict[str, dict[tuple[str, str], list[int]]] = defaultdict(lambda: defaultdict(lambda: [0] * 7))
    for extractor in ((run.run or {}) if run else {}).get("extractors", []):
        if extractor not in screens:
            sums[extractor]
    for extractor, pairs in (called or {}).items():   # a call that found nothing is a row with 0 items
        if extractor in screens:
            continue
        for document, kind in pairs:
            if kind in m.types:
                level = truth.level_of(document)
                for key in ((kind, level), (kind, ALL), (ALL, level), (ALL, ALL)):
                    sums[extractor][key]
    for item in m.items.values():
        by = sorted(set(item.found_by or ("unknown",)))
        level = truth.level_of(m.document[item.item_id])
        fact = m.facts.get(m.fact_of.get(item.item_id, ""))
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
                cell[6] += bool(fact) and placed(fact, truth)
    rows = []
    not_run = {str(e.get("agent_id")) for e in (run.events if run else None) or [] if e.get("status") == "skipped"}         - set(called or {})   # skipped on every document (a GLiNER step without its service): no row, not 0 recall
    kept = [e for e in sorted(sums) if not (e in not_run and not any(c[0] for c in sums[e].values()))]
    for extractor in kept:
        facts = fact_counts(truth, called[extractor], m.types) if called and extractor in called else all_facts
        cells = sums[extractor] or {(ALL, ALL): [0] * 7}
        for (kind, level), (n, matched, hits, only, only_matched, associated, placed_matched) in sorted(cells.items()):
            rows.append({"extractor": extractor, "evidence_type": kind, "level": level,
                         **prf(matched, n, facts[(kind, level)]), "span_hits": hits,
                         "span_accuracy": share(hits, placed_matched), "only": only, "only_matched": only_matched,
                         "associated": associated if kind == "measurement" else None,
                         "association_accuracy": share(associated, matched) if kind == "measurement" else None})
    return {"rows": rows, "cost": score_extractor_cost(run), "recall_scope": "called" if called else "all_facts",
            "papers": _extractor_papers(m, kept, called, screens)}


def _extractor_papers(m: Matching, extractors: Iterable[str], called: dict[str, set[tuple[str, str]]] | None,
                      screens: Iterable[str]) -> list[dict[str, Any]]:
    """Per extractor and paper, the all-type counts (items, matched, facts) with the paper's parent-study
    cluster: what `evaluate benchmark` resamples for its pooled interval. Facts follow `called`, as in
    score_extractors: all facts without events or for an extractor id with no event at all."""
    truth, screens = m.truth, set(screens)
    out = []
    for extractor in sorted(set(extractors) - screens):
        pairs = called.get(extractor) if called else None
        papers: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
        for fact in m.facts.values():
            if pairs is None or (fact.paper, fact.type) in pairs:
                papers[fact.paper][2] += 1
        for document, kind in sorted(pairs or ()):
            if kind in m.types:
                papers[document]
        for item in m.items.values():
            if extractor in (item.found_by or ("unknown",)):
                cell = papers[m.document[item.item_id]]
                cell[0] += 1
                cell[1] += m.fact_of.get(item.item_id, "") in m.facts
        out += [{"extractor": extractor, "paper": p, "cluster": truth.cluster_of(p), "items": c[0],
                 "matched": c[1], "facts": c[2]} for p, c in sorted(papers.items())]
    return out


def score_cost(run: dict[str, Any] | None, papers: int) -> dict[str, Any] | None:
    if not run or "cost" not in run:
        return None
    total = dict(run["cost"])
    per_paper = {k: v / papers for k, v in total.items() if k != "workers" and isinstance(v, (int, float)) and papers}
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


# --- funnel (Part D, our addition) -----------------------------------------------------------------

def score_funnel(truth: GroundTruth, run: Run | None) -> dict[str, Any] | None:
    """Cost per document, the stop-position histogram and the screen's precision and recall (docstring: Funnel)."""
    if run is None or run.funnel is None:
        return None
    documents = run.funnel.get("documents") if isinstance(run.funnel, dict) else None
    if not isinstance(documents, dict):
        return None
    per_doc: dict[str, Counter[str]] = defaultdict(Counter)
    tokens_known = run.usage is not None
    for event in run.events or []:
        meta = event.get("custom_metadata") if isinstance(event.get("custom_metadata"), dict) else {}
        document = meta.get("document")
        if not document or event.get("status") == "skipped":
            continue
        ids = [str(i) for i in meta.get("model_calls") or []]
        per_doc[document].update(calls=1, model_calls=len(ids))
        for usage in (run.usage.get(i) for i in ids) if tokens_known else ():
            if usage:
                per_doc[document].update(input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"])
    expected = {s["paper"]: s.get("relevant", True) is not False for s in truth.studies}
    rows = []
    stops: Counter[str] = Counter()
    for document in sorted(documents):
        entry = documents[document] if isinstance(documents[document], dict) else {}
        screen = entry.get("screen") if isinstance(entry.get("screen"), dict) else None
        relevant = None if screen is None else bool(screen.get("relevant"))
        skipped = bool(entry.get("skipped"))
        stopped = entry.get("stopped_after")
        key = "skipped" if skipped else str(stopped) if isinstance(stopped, int) else "exhausted"
        stops[key] += 1
        c = per_doc.get(document, Counter())
        rows.append({"document": document, "level": truth.level_of(document), "expected_relevant": expected.get(document),
                     "relevant": relevant, "screened": relevant is False, "skipped": skipped, "stop": key,
                     "calls": c["calls"], "model_calls": c["model_calls"],
                     "input_tokens": c["input_tokens"] if tokens_known else None,
                     "output_tokens": c["output_tokens"] if tokens_known else None,
                     "tokens": c["input_tokens"] + c["output_tokens"] if tokens_known else None})
    n = len(rows)
    means = {k: (sum(r[k] for r in rows) / n if n and all(r[k] is not None for r in rows) else None)
             for k in ("calls", "model_calls", "input_tokens", "output_tokens", "tokens")}
    screen_score = None
    if run.screens:
        decided = {e["custom_metadata"]["document"]: bool(e["custom_metadata"].get("relevant"))
                   for e in run.screens if isinstance(e.get("custom_metadata"), dict) and e["custom_metadata"].get("document")}
        scored = [(decided[d], expected[d]) for d in sorted(decided) if d in expected]
        tp = sum(1 for got, want in scored if got and want)
        fp = sum(1 for got, want in scored if got and not want)
        fn = sum(1 for got, want in scored if not got and want)
        tn = sum(1 for got, want in scored if not got and not want)
        screen_score = {"documents": len(scored), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                        "precision": share(tp, tp + fp), "recall": share(tp, tp + fn),
                        "screened_out": sorted(d for d, got in decided.items() if not got),
                        "screened_out_wrongly": sorted(d for d, got in decided.items() if not got and expected.get(d, True))}
    strategy = ((run.run or {}).get("settings") or {}).get("strategy") or run.funnel.get("strategy")
    return {"strategy": strategy, "documents": n, "rows": rows, "per_document": means,
            "stop_positions": dict(sorted(stops.items())), "screen": screen_score}


def score_protocol(run: Run) -> dict[str, Any] | None:
    """The run's protocol {id, sha256} (run.json) and its screen's `lexical_miss` (the run's protocol.yaml; null
    without one): the two cascade arms share run id and strategy, so this is what tells them apart."""
    ref = (run.run or {}).get("protocol")
    path = run.root / PROTOCOL_FILE
    if not ref and not path.is_file():
        return None
    out = {"id": (ref or {}).get("id"), "sha256": (ref or {}).get("sha256"), "lexical_miss": None}
    if path.is_file():
        protocol = load_protocol(path)
        out["lexical_miss"] = protocol.screen.lexical_miss if protocol.screen else None
        out["id"], out["sha256"] = out["id"] or protocol.id, out["sha256"] or protocol.sha256
    return out


# --- per question kind (question-first redesign) ----------------------------------------------------

def effect_truth(truth: GroundTruth, params: QuestionTruth, protocol: Protocol | None) -> GroundTruth:
    """The truth an effect answer is scored against: `truth` itself for the corpus's own question (the saved
    answer, `expected.saved_answer`), else a copy whose studies carry the expected answer's direction, flags,
    duplicate and measurement pair on the question metric and whose `answer` is the expected answer, so
    score_synthesis, score_flags and score_integration's pair check read the question's truth."""
    if saved_answer(truth, "effect", params, protocol):
        return truth
    exp = expected_answer(truth, "effect", params, protocol)
    by_doc = {e["document"]: e for e in exp["studies"]}
    studies = []
    for s in truth.studies:
        e = by_doc[s["paper"]]
        studies.append({**s, "flags": list(e["flags"]), "duplicate_of": e["duplicate_of"],
                        "effect": {**(s.get("effect") or {}), "direction": e["direction"],
                                   "treatment": (e["treatment"] or {}).get("measurement"),
                                   "control": (e["control"] or {}).get("measurement")}})
    return dataclasses.replace(truth, studies=studies, answer=exp)


def _entry_key(truth_entries: list[dict[str, Any]], target: canon.Target) -> Any:
    """A function: system inventory entry -> its key, ("key", folded truth name) or ("unknown", folded name).

    A form (the entry's name, then its aliases) vocab knows gives its `canon.key`; else a form that folds to a
    form of a truth entry vocab does not know (an ablation condition of the hard corpus) gives that entry; else
    the entry is a key of its own (a false positive, never an error)."""
    unkeyed = {canon.fold(form): canon.fold(e["name"]) for e in truth_entries if canon.key(target, e["name"]) is None
               for form in (e["name"], *(e.get("aliases") or []))}

    def key(entry: dict[str, Any]) -> tuple[str, str]:
        forms = [str(f) for f in (entry.get("name"), *(entry.get("aliases") or [])) if f is not None]
        for form in forms:
            if (k := canon.key(target, form)) is not None:
                return "key", canon.fold(k)
        for form in forms:
            if canon.fold(form) in unkeyed:
                return "key", unkeyed[canon.fold(form)]
        return "unknown", canon.fold(forms[0] if forms else "")
    return key


def score_inventory(exp: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    """C, inventory: precision, recall and F1 of the set of keys, and of the set of (key, paper) pairs (sets: the
    engine lists papers in manifest order, truth sorted)."""
    target = exp["target"]
    truth_entries = exp["entries"]
    key = _entry_key(truth_entries, target)
    expected_keys = {canon.fold(e["name"]): e["name"] for e in truth_entries}
    expected_pairs = {(canon.fold(e["name"]), p) for e in truth_entries for p in e["papers"]}
    given: dict[tuple[str, str], str] = {}
    given_pairs: set[tuple[tuple[str, str], str]] = set()
    for entry in answer.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        k = key(entry)
        given.setdefault(k, str(entry.get("name")))
        given_pairs |= {(k, str(p)) for p in entry.get("papers") or []}
    hits = {k for k in given if k[0] == "key" and k[1] in expected_keys}
    pair_hits = {(k, p) for k, p in given_pairs if k[0] == "key" and (k[1], p) in expected_pairs}
    keys = prf(len(hits), len(given), len(expected_keys))
    pairs = prf(len(pair_hits), len(given_pairs), len(expected_pairs))
    return {"kind": "inventory", "system": answer.get("system", "unknown"), "target": target,
            "entries": keys["items"], "expected_entries": keys["facts"], "matched": keys["matched"],
            "precision": keys["precision"], "recall": keys["recall"], "f1": keys["f1"],
            "paper_pairs": pairs["items"], "expected_paper_pairs": pairs["facts"],
            "paper_precision": pairs["precision"], "paper_recall": pairs["recall"], "paper_f1": pairs["f1"],
            "false_positives": sorted(name for k, name in given.items() if k not in hits),
            "missed": sorted(name for k, name in expected_keys.items() if ("key", k) not in hits)}


def _agrees(answer: dict[str, Any]) -> dict[str, bool | None]:
    """document -> the answer's `agrees`: its studies entry, else its `agreeing` / `disagreeing` / `undetermined`
    lists; a document in none of them is absent."""
    out: dict[str, bool | None] = {}
    for name, value in (("undetermined", None), ("agreeing", True), ("disagreeing", False)):
        for d in answer.get(name) or []:
            out[str(d)] = value
    for s in answer.get("studies") or []:
        if isinstance(s, dict) and s.get("document") is not None:
            out[str(s["document"])] = s.get("agrees") if isinstance(s.get("agrees"), bool) else None
    return out


def score_consistency(exp: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    """C, consistency: per-study accuracy of `agrees` (null = undetermined, right when truth's is null too and the
    answer has an entry or list membership for the document; a document it leaves out is wrong) and
    precision/recall of the agreeing and disagreeing sets, over the studies truth lists (those on the claim metric;
    the engine lists every document, the others are left out)."""
    given = _agrees(answer)
    # a document the answer leaves out is wrong, even where truth's `agrees` is null: undetermined must be said
    studies = [{"paper": e["document"], "expected": e["agrees"], "given": given.get(e["document"]),
                "answered": e["document"] in given,
                "correct": e["document"] in given and given[e["document"]] == e["agrees"]} for e in exp["studies"]]
    out: dict[str, Any] = {"kind": "consistency", "system": answer.get("system", "unknown"), "metric": exp["metric"],
                           "studies_scored": len(studies),
                           "per_study_accuracy": share(sum(s["correct"] for s in studies), len(studies)),
                           "studies": studies}
    for name, value in (("agreeing", True), ("disagreeing", False)):
        want = set(exp[name])
        got = {s["paper"] for s in studies if s["given"] is value}
        tp = len(want & got)
        out |= {f"{name}_precision": share(tp, len(got)), f"{name}_recall": share(tp, len(want)),
                f"{name}_tp": tp, f"{name}_given": len(got), f"{name}_expected": len(want)}
    return out


NOT_COUNTED = ("screened_out", "duplicate")   # best: truth's studies that are not counted (the engine may count them)


def score_best(exp: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    """C, best: whether the answer's winner (or, without one, its tie) is truth's, and per-study accuracy of the
    winner and tie over truth's counted studies (not screened out, not a duplicate). The engine does not leave
    duplicates out; that shows in its wins and winner, not here."""
    given = {str(s.get("document")): s for s in answer.get("studies") or [] if isinstance(s, dict)}
    studies = []
    for e in exp["studies"]:
        if (e.get("reason") or {}).get("code") in NOT_COUNTED:
            continue
        g = given.get(e["document"], {})
        got = (g.get("winner"), sorted(g.get("tied") or []))
        studies.append({"paper": e["document"], "expected": e["winner"], "expected_tied": e["tied"],
                        "given": got[0], "given_tied": got[1], "correct": got == (e["winner"], e["tied"])})
    winner = (answer.get("winner"), sorted(answer.get("tied") or []))
    return {"kind": "best", "system": answer.get("system", "unknown"), "metric": exp["metric"],
            "winner": winner[0], "tied": winner[1], "expected_winner": exp["winner"], "expected_tied": exp["tied"],
            "winner_correct": winner == (exp["winner"], exp["tied"]),
            "wins": dict(answer.get("wins") or {}), "expected_wins": exp["wins"], "studies_scored": len(studies),
            "per_study_accuracy": share(sum(s["correct"] for s in studies), len(studies)), "studies": studies}


def score_kind(truth: GroundTruth, kind: str, params: QuestionTruth, protocol: Protocol | None,
               answer: dict[str, Any]) -> dict[str, Any]:
    """C of one system's answer to a question of `kind`, against the expected answer (evaluation/expected.py) with
    the question's truth parameters; `protocol` only decides the saved-answer shortcut (its id) and the effect
    question text. effect: score_synthesis against `effect_truth`."""
    if kind == "effect":
        return score_synthesis(effect_truth(truth, params, protocol), answer)
    exp = expected_answer(truth, kind, params, protocol)   # type: ignore[arg-type]
    return {"consistency": score_consistency, "inventory": score_inventory, "best": score_best}[kind](exp, answer)


def _truth_key(fact: Fact) -> str:
    """The inventory key of a condition, metric or dataset fact: its name's `canon.key`, else the name, folded."""
    name = str(fact.data.get("label") if fact.type == "condition" else fact.data.get("name"))
    target: canon.Target = fact.type if fact.type in ("condition", DATASET) else "metric"   # type: ignore[assignment]
    return canon.fold(canon.key(target, name) or name)


def integration_inventory(m: Matching, answer: dict[str, Any]) -> dict[str, Any]:
    """B, inventory (synonym merging): each answer entry's keys are the truth keys (`canon.key` of the name, else
    the folded name) of the target facts its items matched in A. `split`: truth keys found in more than one entry;
    `merged`: entries holding more than one key; `clean_share`: of the entries with a key, those holding exactly
    one key that no other entry holds."""
    target = answer.get("target")
    per_entry = []
    for entry in answer.get("entries") or []:
        keys = set()
        for item_id in (entry.get("items") or []) if isinstance(entry, dict) else []:
            fact = m.facts.get(m.fact_of.get(str(item_id), ""))
            if fact is not None and (target is None or fact.type == target):
                keys.add(_truth_key(fact))
        per_entry.append(keys)
    holders = Counter(k for keys in per_entry for k in keys)
    keyed = [keys for keys in per_entry if keys]
    clean = sum(1 for keys in keyed if len(keys) == 1 and holders[next(iter(keys))] == 1)
    return {"kind": "inventory", "entries": len(per_entry), "keyed_entries": len(keyed), "keys": len(holders),
            "split": sum(1 for n in holders.values() if n > 1), "merged": sum(1 for keys in keyed if len(keys) > 1),
            "clean_share": share(clean, len(keyed))}


def integration_best(m: Matching, protocol: Protocol | None) -> dict[str, Any]:
    """B, best (kind assignment): of the condition items A matched to a condition whose label vocab gives a kind
    (`canon.KIND_OF`), the share whose kind is that kind; an item's kind is the engine's (kinds.best.kind_of with the
    protocol's `best` block), or its `kind` field without one."""
    n = ok = 0
    for item, fact in m.pairs:
        if fact.type != "condition":
            continue
        want = canon.KIND_OF.get(canon.key("condition", str(fact.data.get("label") or "")) or "")
        if want is None:
            continue
        got = (best_rules.kind_of(item, protocol.best) if protocol is not None and protocol.best is not None
               else item.fields.get("kind"))
        n += 1
        ok += got == want
    return {"kind": "best", "conditions": n, "kind_correct": ok, "kind_accuracy": share(ok, n)}


def integration_consistency(m: Matching) -> dict[str, Any]:
    """B, consistency (claim to result): an author-claim item whose claim span overlaps a claim placement of its
    paper is located on the claim it overlaps most (each item counted once; A matches claims only when the
    direction is equal, so A's pairs cannot show a wrong direction); `claim_accuracy` is the share of located items
    with that claim's direction. `rows` is the
    measurement linkage of score_integration; its pair check needs the treatment and control measurements an
    effect answer names, which a consistency answer does not, so `studies` and `true_pair` are null."""
    n = ok = 0
    for item in m.items.values():
        if item.evidence_type != "author_claim":
            continue
        best: tuple[int, str, Fact] | None = None
        for fact in m.truth.of(m.document[item.item_id], "author_claim"):
            size = overlap_size(item, fact, m.truth)
            if size and (best is None or (size, fact.id) > best[:2]):   # ties: the larger fact id, deterministic
                best = (size, fact.id, fact)
        if best is not None:
            n += 1
            ok += item.fields.get("direction") == best[2].data.get("direction")
    rows = [{**r, "studies": None, "true_pair": None} for r in score_integration(m, None)["rows"]]
    return {"kind": "consistency", "claims": n, "claim_correct": ok, "claim_accuracy": share(ok, n), "rows": rows}


def integration_kind(m: Matching, kind: str, answer: dict[str, Any] | None, protocol: Protocol | None = None,
                     truth: GroundTruth | None = None) -> dict[str, Any]:
    """B of the engine's answer to a question of `kind`; `truth` the effect truth (effect_truth) for effect."""
    if kind == "effect":
        return score_integration(m, answer, truth)
    if kind == "inventory":
        return integration_inventory(m, answer or {})
    if kind == "best":
        return integration_best(m, protocol)
    return integration_consistency(m)


def question(question_id: str) -> QuestionEntry:
    """The entry of evidence/questions.yaml; ValueError naming the known ids for an unknown one."""
    entries = {q.id: q for q in load_questions()}
    if question_id not in entries:
        raise ValueError(f"unknown question id {question_id!r}; evidence/questions.yaml has {', '.join(entries)}")
    return entries[question_id]


def _question_protocol(entry: QuestionEntry) -> Protocol | None:
    return load_protocol(REPO / entry.protocol) if entry.protocol else None


def _run_protocol(run: Run, entry: QuestionEntry) -> Protocol | None:
    """The run's protocol.yaml, else the question's hand-written protocol; a run of another kind is refused."""
    path = run.root / PROTOCOL_FILE
    protocol = load_protocol(path) if path.is_file() else _question_protocol(entry)
    if protocol is not None and protocol.kind != entry.kind:
        raise ValueError(f"the run's protocol {protocol.id!r} is of kind {protocol.kind!r}, question {entry.id!r} of "
                         f"kind {entry.kind!r}: give the --question-id the run answered")
    return protocol


def _question_text(truth: GroundTruth, entry: QuestionEntry) -> str:
    """The corpus's question for its own question id (as before), else the question asked."""
    return truth.question if entry.id == DEFAULT_QUESTION else entry.question


# --- everything ------------------------------------------------------------------------------------

def score(run_dir: Path, corpus: Path, baselines: Iterable[Path] = (), reexec: Path | None = None,
          oracle: Path | None = None, question_id: str | None = None) -> dict[str, Any]:
    """The report for one run (and any baseline answers) on one corpus, for the question `question_id` of
    evidence/questions.yaml (its kind picks B and C: integration_kind, score_kind), by default the one the run
    answers (answered_by; ValueError when that cannot be told); `oracle` an oracle's answer.json (effect
    questions only). Baseline answers are scored on C only."""
    entry = question(question_id) if question_id else answered_by(run_dir, load_questions())
    corpus = Path(corpus)
    truth = GroundTruth.load(corpus / "ground_truth.json")
    files = paper_ids(read_json(corpus / "manifest.json"))
    run = Run.load(run_dir, reexec)
    protocol = _run_protocol(run, entry)
    m = protocol_matching(run.items, truth, files, protocol)
    answers = ([run.answer] if run.answer is not None else []) + [read_json(p) for p in baselines]
    systems = [score_kind(truth, entry.kind, entry.truth, protocol, a) for a in answers]
    effect = entry.kind == "effect"
    scored = effect_truth(truth, entry.truth, protocol) if effect else truth
    return {
        "corpus_id": truth.corpus_id, "corpus_name": corpus.name, "levels": truth.levels,
        "run_id": (run.run or {}).get("run_id", run.root.name), "protocol": score_protocol(run),
        "question_id": entry.id, "kind": entry.kind,
        "question": _question_text(truth, entry), "extraction": score_extraction(m),
        "integration": integration_kind(m, entry.kind, run.answer, protocol, scored), "synthesis": systems,
        "intervals": score_intervals(m, systems if effect else []),
        "locate": score_locate(truth, run.locate), "cascade": score_cascade(m, run.run),
        "extractors": score_extractors(m, run),
        "cost": score_cost(run.run, len(truth.studies)), "stability": score_stability(run.reexec),
        "funnel": score_funnel(truth, run),
        "attribution": (score_attribution(scored, answers, read_json(oracle) if oracle else None) if effect
                        else None),
    }


def score_answers(corpus: Path, answers: Iterable[Path], oracle: Path | None = None,
                  question_id: str | None = None) -> dict[str, Any]:
    """C only, for baseline answers without an engine run (the question's hand-written protocol decides the
    saved-answer shortcut); by default for the question every answer asks (answers_asked)."""
    given = [read_json(p) for p in answers]
    entry = question(question_id) if question_id else answers_asked(given, load_questions())
    truth = GroundTruth.load(Path(corpus) / "ground_truth.json")
    protocol = _question_protocol(entry)
    systems = [score_kind(truth, entry.kind, entry.truth, protocol, a) for a in given]
    effect = entry.kind == "effect"
    scored = effect_truth(truth, entry.truth, protocol) if effect else truth
    return {"corpus_id": truth.corpus_id, "corpus_name": Path(corpus).name, "levels": truth.levels,
            "run_id": None, "protocol": None, "question_id": entry.id, "kind": entry.kind, "question": _question_text(truth, entry),
            "extraction": None, "integration": None, "synthesis": systems,
            "intervals": score_intervals(None, systems if effect else []), "locate": None, "cascade": None,
            "extractors": None, "cost": None, "stability": None, "funnel": None,
            "attribution": (score_attribution(scored, given, read_json(oracle) if oracle else None) if effect
                            else None)}
