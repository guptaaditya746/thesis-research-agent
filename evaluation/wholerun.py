"""Whole-run scoring of the real labelled sets (workstream W6): one question per ranking, list or comparison of a
real set, one `Answer` (what the engine's run, or the RAG baseline, says), one `score`.

Scoring rules (fixed): rankings by top-1 and Kendall tau (over the items both orders contain); lists by precision and
recall (names compared by `names.clean` and the run's name groups); comparisons by direction agreement per study and
overall; claims by direction agreement with the review's conclusions.

Gold per kind (`RealQuestion.gold`, a plain dict; every kind also lists its `papers`):
  rank     {"ranking": [name, ...] best first, "papers": [...]}
  list     {"items": [name, ...], "papers": [...]}
  compare  {"directions": {study: "improves"|"worsens"|"no_effect"}, "conclusion": str | None, "papers": [...]}
  claims   {"conclusions": [{"id": str, "direction": str}], "papers": [...]}

Run rules shared by every real set: `sample` (a fixed sample of questions, saved), `tune_split` (a held-out slice
of each set's papers for tuning, written to tune_split.json; `score` refuses a question whose papers are in it) and
`left_out_line` (the open-full-text count the report states). `score` accepts either plan confirmation row,
"auto-confirmed" or "hand-confirmed", and writes it into the result.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from scipy.stats import kendalltau

from evidence.names import NameGroups

from .realpapers.common import same_name

Kind = Literal["rank", "list", "compare", "claims"]
KINDS = ("rank", "list", "compare", "claims")
CONFIRMATIONS = ("auto-confirmed", "hand-confirmed")
TUNE_FILE = "tune_split.json"
SAMPLE_FILE = "sample.json"


@dataclass(frozen=True)
class RealQuestion:
    id: str
    question: str
    field: str
    corpus_dir: Path
    gold: dict[str, Any]
    kind: Kind


@dataclass(frozen=True)
class Answer:
    """A whole-run answer in the shape `score` reads; unused parts stay empty (an empty answer is valid)."""
    ranking: list[str] = field(default_factory=list)            # rank: names, best first
    names: list[str] = field(default_factory=list)              # list: names
    directions: dict[str, str] = field(default_factory=dict)    # compare: study -> direction
    conclusion: str | None = None                               # compare: the overall direction
    claims: list[dict[str, Any]] = field(default_factory=list)  # claims: {"about": conclusion id, "direction": ...}


def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def _find(name: str, pool: list[str], groups: NameGroups | None) -> str | None:
    return next((p for p in pool if same_name(name, p, groups)), None)


def _rank(answer: Answer, gold: dict[str, Any], groups: NameGroups | None) -> dict[str, Any]:
    want, got = list(gold["ranking"]), list(answer.ranking)
    top1 = int(bool(got) and bool(want) and same_name(got[0], want[0], groups))
    common = [(w, g) for w in want if (g := _find(w, got, groups)) is not None]
    tau = None
    if len(common) >= 2:
        order = [got.index(g) for _, g in common]
        value = float(kendalltau(list(range(len(common))), order).statistic)
        tau = None if value != value else value   # nan (a constant order) is no number
    return {"top1": top1, "kendall_tau": tau, "n_common": len(common)}


def _list(answer: Answer, gold: dict[str, Any], groups: NameGroups | None) -> dict[str, Any]:
    want, got = list(gold["items"]), list(dict.fromkeys(answer.names))
    right = [n for n in got if _find(n, want, groups) is not None]
    found = [w for w in want if _find(w, got, groups) is not None]
    precision, recall = _ratio(len(right), len(got)), _ratio(len(found), len(want))
    f1 = None
    if precision is not None and recall is not None:
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1, "n_answer": len(got), "n_gold": len(want)}


def _compare(answer: Answer, gold: dict[str, Any]) -> dict[str, Any]:
    per = {study: int(answer.directions.get(study) == d) for study, d in gold["directions"].items()}
    out: dict[str, Any] = {"per_study": per, "direction_agreement": _ratio(sum(per.values()), len(per))}
    if gold.get("conclusion") is not None:
        out["conclusion_agrees"] = int(answer.conclusion == gold["conclusion"])
    return out


def _claims(answer: Answer, gold: dict[str, Any]) -> dict[str, Any]:
    want = {c["id"]: c["direction"] for c in gold["conclusions"]}
    right = [c for c in answer.claims if want.get(c.get("about")) == c.get("direction")]
    agreed = {c["about"] for c in right}
    return {"precision": _ratio(len(right), len(answer.claims)), "recall": _ratio(len(agreed), len(want)),
            "n_claims": len(answer.claims), "n_conclusions": len(want)}


def question_papers(q: RealQuestion) -> list[str]:
    """The paper ids a question rests on: its gold's `papers`, else the corpus manifest's."""
    if "papers" in q.gold:
        return [str(p) for p in q.gold["papers"]]
    manifest = Path(q.corpus_dir) / "manifest.json"
    if manifest.is_file():
        return [p["id"] for p in json.loads(manifest.read_text(encoding="utf-8"))["papers"]]
    return []


def tune_papers(q: RealQuestion) -> set[str]:
    """The papers held out for tuning (tune_split.json in the corpus dir or its parent); empty without the file."""
    for folder in (Path(q.corpus_dir), Path(q.corpus_dir).parent):
        path = folder / TUNE_FILE
        if path.is_file():
            return set(json.loads(path.read_text(encoding="utf-8"))["papers"])
    return set()


def score(answer: Answer, q: RealQuestion, *, confirmation: str | None = None,
          groups: NameGroups | None = None) -> dict[str, Any]:
    """The scores of `answer` for `q`, by kind. Refuses a question whose papers appear in tune_split.json and a
    confirmation other than auto-confirmed / hand-confirmed."""
    if q.kind not in KINDS:
        raise ValueError(f"unknown question kind {q.kind!r}")
    if confirmation is not None and confirmation not in CONFIRMATIONS:
        raise ValueError(f"confirmation must be one of {CONFIRMATIONS}, not {confirmation!r}")
    tuned = sorted(set(question_papers(q)) & tune_papers(q))
    if tuned:
        raise ValueError(f"question {q.id}: papers {tuned} are in {TUNE_FILE} (held out for tuning); "
                         "they cannot be scored")
    if q.kind == "rank":
        body = _rank(answer, q.gold, groups)
    elif q.kind == "list":
        body = _list(answer, q.gold, groups)
    elif q.kind == "compare":
        body = _compare(answer, q.gold)
    else:
        body = _claims(answer, q.gold)
    return {"id": q.id, "kind": q.kind, "confirmation": confirmation} | body


def sample(questions: list[RealQuestion], n: int, seed: int = 0, out: Path | None = None) -> list[RealQuestion]:
    """A fixed sample of `n` questions (all when fewer), in the questions' own order; the ids are saved to `out`
    (sample.json) with n and seed."""
    ids = sorted(random.Random(seed).sample(range(len(questions)), min(n, len(questions))))
    chosen = [questions[i] for i in ids]
    if out is not None:
        Path(out).write_text(json.dumps({"seed": seed, "n": n, "ids": [q.id for q in chosen]}, indent=1) + "\n",
                             encoding="utf-8", newline="\n")
    return chosen


def tune_split(papers: list[str], fraction: float = 0.2, seed: int = 0, out: Path | None = None) -> dict[str, Any]:
    """Hold out a slice of a set's papers for tuning: {"papers": [held out], "rest": [...]}, written to `out`."""
    k = min(len(papers), max(1, round(len(papers) * fraction))) if papers else 0
    held = sorted(random.Random(seed).sample(sorted(papers), k))
    split = {"seed": seed, "fraction": fraction, "papers": held, "rest": [p for p in sorted(papers) if p not in held]}
    if out is not None:
        Path(out).write_text(json.dumps(split, indent=1) + "\n", encoding="utf-8", newline="\n")
    return split


def left_out_line(left_out: int, total: int) -> str:
    return f"left out: {left_out} of {total} (no open full text)"
