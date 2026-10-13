"""A run's answer against the answer key: rows and facts (milestone 4, Scores).

Both sides have the agent's answer shape (docs/e2e-build-plan.md, Answer key): rows of a table (cells per
column) or a graph (one edge per row), each row backed by facts {s, p, o}. Gold facts also carry
paper_id, quote, vital and candidate_id.

Rows (set F1 over rows; for graph answers the rows are the edges):
- normalised: a table row matches a key row when every cell the key fills (not null: the gold could not
  establish it) equals the run's cell after normalisation (scoring/normalise.py; lists as sets, count
  cells exactly). A graph row matches on its edge, source, predicate and target; its attributes are
  scored through their facts.
- soft: also when the judge's same_row says the two rows are the same, asked only for rows left over at
  the normalised level that share a value (a table cell or list item; a graph edge's source).

Facts, three cumulative levels (the labelling repo's docs/EVALUATION.md, 3.3, with `normalised` in place
of `entailed`; scoring/normalise.py):
- strict: s, p and o equal as typed; normalised: equal after normalisation and paper-id aliasing;
- soft: also the judge's same_fact, asked only for pairs with the same subject (normalised, or the run's
  subject is the gold fact's paper) where the run fact or the gold fact is left over at the normalised
  level. That covers the augmenting paths of length one and three, as in the labelling scorer.
Facts with one normalised key are one fact on each side (a gold fact is vital if any copy is), so
stating a fact twice neither costs precision nor earns credit twice.

Credit is one-to-one: per level a maximum matching (scipy.optimize.linear_sum_assignment) whose weights
make, in this order, more pairs, more vital gold facts and stricter pairs win. A larger level only adds
edges, so its counts and its vital recall never fall below the stricter level's; each pair is reported
at the strictest level it has.

Judged precision (EVALUATION.md 3.5): correct = run facts matched at the soft level; wrong = left-over
run facts equal (normalised) to a fact the reviewers rejected as wrong, listed in the key's optional
`rejected` array. A key without that array leaves judged precision open (null).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment

from .judge import Judge, run_all
from .normalise import fact_norm, fact_strict, norm, words

RANK = {"strict": 3, "normalised": 2, "soft": 1}
LEVEL = {rank: name for name, rank in RANK.items()}
FACT_LEVELS = ("strict", "normalised", "soft")
ROW_LEVELS = ("normalised", "soft")
GOLD_FIELDS = ("paper_id", "quote", "vital", "candidate_id")


# --- shared --------------------------------------------------------------------------------------------

def prf(tp: int, n_run: int, n_key: int) -> dict[str, Any]:
    """Counts and ratios. An empty answer scores 0 (every attempt counts, EVALUATION.md 5); with an
    empty key, recall and F1 are undefined (null)."""
    precision = tp / n_run if n_run else 0.0
    recall = tp / n_key if n_key else None
    f1 = None if recall is None else (2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return {"tp": tp, "fp": n_run - tp, "fn": n_key - tp, "precision": precision, "recall": recall, "f1": f1}


def assign(n_run: int, n_key: int, edges: dict[tuple[int, int], int], min_rank: int,
           vital: list[bool] | None = None) -> list[tuple[int, int, int]]:
    """Maximum matching over the edges of rank >= min_rank: most pairs, then most vital, then strictest.

    Returns (run index, key index, rank) triples. Weights are integers below 2**53, so exact in floats.
    """
    usable = {ij: r for ij, r in edges.items() if r >= min_rank}
    if not usable:
        return []
    n = min(n_run, n_key)
    b = 3 * (n + 1)  # more than any sum of ranks
    a = b * (n + 1)  # more than any sum of vital bonuses
    weights = np.zeros((n_run, n_key))
    for (i, j), rank in usable.items():
        weights[i, j] = a + (b if vital and vital[j] else 0) + rank
    rows, cols = linear_sum_assignment(weights, maximize=True)
    return sorted((int(i), int(j), usable[(i, j)]) for i, j in zip(rows, cols) if (i, j) in usable)


# --- rows ----------------------------------------------------------------------------------------------

@dataclass
class Row:
    id: str
    key: tuple[Any, ...]
    view: dict[str, Any]  # the row without its facts: what the judge sees
    shared: set[Any]  # values a soft candidate must share
    same: list[str] = field(default_factory=list)  # ids of later rows with the same key


def columns(concept: dict[str, Any]) -> list[str]:
    shape = concept["answer_shape"]
    return [c["name"] for c in shape["columns"]] if shape["kind"] == "table" else []


def row_of(row: dict[str, Any], kind: str, cols: list[str]) -> Row:
    view = {k: v for k, v in row.items() if k not in ("id", "facts")}
    if kind == "table":
        cells = row.get("cells") or {}
        key = tuple(norm(cells.get(c)) for c in cols)
        shared = set().union(*(words(cells.get(c)) for c in cols)) if cols else set()
    else:
        key = (norm(row.get("source")), norm(row.get("predicate")), norm(row.get("target")))
        shared = {("source", key[0], key[1])}
    return Row(str(row.get("id")), key, view, shared)


def unique_rows(rows: list[dict[str, Any]], kind: str, cols: list[str]) -> list[Row]:
    out: dict[tuple[Any, ...], Row] = {}
    for raw in rows:
        row = row_of(raw, kind, cols)
        if row.key in out:
            out[row.key].same.append(row.id)
        else:
            out[row.key] = row
    return list(out.values())


def rows_equal(run: Row, key: Row, kind: str) -> bool:
    if kind == "table":  # a cell the key leaves null is not compared
        return all(k is None or r == k for r, k in zip(run.key, key.key))
    return run.key == key.key


def match_rows(answer: dict[str, Any], key: dict[str, Any], concept: dict[str, Any], judge: Judge | None = None,
               workers: int = 1) -> dict[str, Any]:
    kind, cols = concept["answer_shape"]["kind"], columns(concept)
    run, gold = unique_rows(answer["rows"], kind, cols), unique_rows(key["rows"], kind, cols)
    edges = {(i, j): RANK["normalised"] for i, r in enumerate(run) for j, k in enumerate(gold) if rows_equal(r, k, kind)}
    normalised = assign(len(run), len(gold), edges, RANK["normalised"])
    if judge is not None:
        taken_run, taken_key = {i for i, _, _ in normalised}, {j for _, j, _ in normalised}
        asks = [(i, j) for i, r in enumerate(run) for j, k in enumerate(gold)
                if (i, j) not in edges and (i not in taken_run or j not in taken_key) and r.shared & k.shared]
        answers = run_all([partial(judge.same_row, run[i].view, gold[j].view, concept) for i, j in asks], workers)
        edges |= {ij: RANK["soft"] for ij, yes in zip(asks, answers) if yes}
    soft = assign(len(run), len(gold), edges, RANK["soft"])
    matched_run, matched_key = {i for i, _, _ in soft}, {j for _, j, _ in soft}
    return {
        "levels": {"normalised": prf(len(normalised), len(run), len(gold)),
                   "soft": prf(len(soft), len(run), len(gold))},
        "pairs": [{"run": run[i].id, "key": gold[j].id, "level": LEVEL[rank], "run_same": run[i].same}
                  for i, j, rank in soft],
        "missed": [k.id for j, k in enumerate(gold) if j not in matched_key],
        "extra": [r.id for i, r in enumerate(run) if i not in matched_run],
        "duplicates": sum(len(r.same) for r in run),
    }


# --- facts ---------------------------------------------------------------------------------------------

@dataclass
class Fact:
    key: tuple[Any, Any, Any]  # normalised s, p, o
    spo: dict[str, Any]  # the first copy's s, p, o: what the judge sees
    strict: set[tuple[Any, Any, Any]] = field(default_factory=set)
    members: list[dict[str, str]] = field(default_factory=list)  # every copy: {row, fact}
    subjects: set[Any] = field(default_factory=set)
    vital: bool = False


def unique_facts(rows: list[dict[str, Any]], gold: bool) -> list[Fact]:
    out: dict[tuple[Any, Any, Any], Fact] = {}
    for row in rows:
        for raw in row.get("facts") or []:
            key = fact_norm(raw)
            fact = out.setdefault(key, Fact(key, {k: raw[k] for k in ("s", "p", "o")}))
            fact.strict.add(fact_strict(raw))
            fact.members.append({"row": str(row.get("id")), "fact": str(raw.get("id"))})
            fact.subjects.add(key[0])
            if gold:
                fact.vital |= bool(raw.get("vital"))
                if raw.get("paper_id"):
                    fact.subjects.add(norm(raw["paper_id"]))
    return list(out.values())


def level_counts(pairs: list[tuple[int, int, int]], run: list[Fact], gold: list[Fact]) -> dict[str, Any]:
    vital = sum(f.vital for f in gold)
    vital_tp = sum(gold[j].vital for _, j, _ in pairs)
    return prf(len(pairs), len(run), len(gold)) | {
        "vital": vital, "vital_tp": vital_tp, "vital_recall": vital_tp / vital if vital else None}


def match_facts(answer: dict[str, Any], key: dict[str, Any], concept: dict[str, Any], judge: Judge | None = None,
                workers: int = 1) -> dict[str, Any]:
    run, gold = unique_facts(answer["rows"], gold=False), unique_facts(key["rows"], gold=True)
    vital = [f.vital for f in gold]
    by_key = {f.key: j for j, f in enumerate(gold)}
    edges: dict[tuple[int, int], int] = {}
    for i, f in enumerate(run):
        j = by_key.get(f.key)
        if j is not None:  # strict equality implies normalised equality, so there is no other edge
            edges[(i, j)] = RANK["strict"] if f.strict & gold[j].strict else RANK["normalised"]
    levels = {"strict": assign(len(run), len(gold), edges, RANK["strict"], vital),
              "normalised": assign(len(run), len(gold), edges, RANK["normalised"], vital)}
    if judge is not None:
        taken_run, taken_key = {i for i, _, _ in levels["normalised"]}, {j for _, j, _ in levels["normalised"]}
        asks = [(i, j) for i, f in enumerate(run) for j, g in enumerate(gold)
                if (i, j) not in edges and (i not in taken_run or j not in taken_key) and f.key[0] in g.subjects]
        answers = run_all([partial(judge.same_fact, run[i].spo, gold[j].spo, concept) for i, j in asks], workers)
        edges |= {ij: RANK["soft"] for ij, yes in zip(asks, answers) if yes}
    levels["soft"] = assign(len(run), len(gold), edges, RANK["soft"], vital)
    soft = levels["soft"]
    matched_run, matched_key = {i for i, _, _ in soft}, {j for _, j, _ in soft}
    rejected = rejected_keys(key)
    extra = [{"run": f.members[0], "same": f.members[1:], "spo": f.spo,
              "wrong": None if rejected is None else f.key in rejected}
             for i, f in enumerate(run) if i not in matched_run]
    wrong = None if rejected is None else sum(bool(e["wrong"]) for e in extra)
    return {
        "levels": {name: level_counts(pairs, run, gold) for name, pairs in levels.items()},
        "pairs": [{"run": run[i].members[0], "run_same": run[i].members[1:], "key": gold[j].members[0],
                   "level": LEVEL[rank], "vital": gold[j].vital} for i, j, rank in soft],
        "missed": [{"key": g.members[0], "spo": g.spo, "vital": g.vital}
                   for j, g in enumerate(gold) if j not in matched_key],
        "extra": extra,
        "judged_precision": judged_precision(len(soft), wrong, len(run)),
        "duplicates": sum(len(f.members) - 1 for f in run),
    }


def rejected_keys(key: dict[str, Any]) -> set[tuple[Any, Any, Any]] | None:
    """Normalised keys of the facts reviewers rejected as wrong; None when the key does not list them."""
    if "rejected" not in key:
        return None
    return {fact_norm(f) for f in key["rejected"] or [] if f.get("verdict", "wrong") == "wrong"}


def judged_precision(correct: int, wrong: int | None, scored: int) -> dict[str, Any]:
    if wrong is None:
        return {"correct": correct, "wrong": None, "precision": None, "coverage": None,
                "note": "the key lists no rejected facts"}
    judged = correct + wrong
    return {"correct": correct, "wrong": wrong, "precision": correct / judged if judged else None,
            "coverage": judged / scored if scored else None}


def match(answer: dict[str, Any], key: dict[str, Any], concept: dict[str, Any], judge: Judge | None = None,
          workers: int = 1) -> dict[str, Any]:
    """Rows and facts of one answer against one key."""
    return {"rows": match_rows(answer, key, concept, judge, workers),
            "facts": match_facts(answer, key, concept, judge, workers)}
