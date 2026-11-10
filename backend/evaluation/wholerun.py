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

The `Answer` contract (what an engine run, or the RAG baseline, must produce to be scored; the owner of the engine
side is Wave 2 Task 8.1, the adapter "engine run -> Answer"):
  rank     Answer.ranking   paper ids (the corpus manifest ids) or names, best first; unknown ones are ignored
  list     Answer.names     the names found, once each
  compare  Answer.directions {paper id: "improves"|"worsens"|"no_effect"}; Answer.conclusion the overall direction
  claims   Answer.claims    [{"about": <gold conclusion id>, "direction": ...}]; `about` must be one of
                            `gold["conclusions"][i]["id"]`, the ids the question gives
An unused part stays empty: an empty answer is valid and scores 0 (recall) or None (precision).
`from_run(run, q)` is that adapter for an engine run folder: a plan run's answer.json (its lines' rows: rank and list
read the plan's scored line, `scored_line` — a ranking's first rank/best line, else the line asking the question,
else the first line, the oversell caveat left out; an empty or failed scored line is an empty answer, never a later
line; a folder without plan.json reads the first answered line; a ranking whose gold is paper ids reads the `paper`
column only (none: an empty answer), any other ranking and a list read the first column; compare reads `paper` + `direction` rows, else the kind's answer kept under `synthesis`), and for
claims the run's claim records (evidence.jsonl): one claim per gold conclusion, the majority direction of the run's
directed claims (a question gives one conclusion id per review; with several, a claim is about the conclusion whose
id or text its subject or object names, else it is left out).
`RealQuestion.records` (optional) are the set's answer-key records for the key-records run (see
realpapers/keystore.py); None means "key-records run: not available" (`key_status`).
"""
from __future__ import annotations

import json
import random
import warnings
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from scipy.stats import kendalltau

from evidence.names import NameGroups

from .realpapers.common import manifest_ids, ratio, same_name

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
    records: list[dict[str, Any]] | None = None   # answer-key records (keystore.py); None: not available


@dataclass(frozen=True)
class Answer:
    """A whole-run answer in the shape `score` reads; unused parts stay empty (an empty answer is valid)."""
    ranking: list[str] = field(default_factory=list)            # rank: names, best first
    names: list[str] = field(default_factory=list)              # list: names
    directions: dict[str, str] = field(default_factory=dict)    # compare: study -> direction
    conclusion: str | None = None                               # compare: the overall direction
    claims: list[dict[str, Any]] = field(default_factory=list)  # claims: {"about": conclusion id, "direction": ...}


DIRECTION_OF = {"supports": "improves", "contradicts": "worsens", "neutral": "no_effect",
                "improves": "improves", "worsens": "worsens", "no_effect": "no_effect"}
OVERSELL = "oversell"


def _lines(answer: dict[str, Any]) -> list[dict[str, Any]]:
    """The answered lines with rows, the oversell caveat left out."""
    return [x for x in answer.get("lines") or [] if x.get("status") == "done" and x.get("rows") and x.get("id") != OVERSELL]


def _column(rows: list[dict[str, Any]], prefer: str | None = None) -> list[str]:
    out: list[str] = []
    for row in rows:
        key = prefer if prefer is not None and prefer in row else next(iter(row), None)
        value = row.get(key) if key is not None else None
        if value is not None and str(value) not in out:
            out.append(str(value))
    return out


def paper_gold(q: RealQuestion) -> bool:
    """True for a ranking whose gold is paper ids (SciLead: "which paper reports the best result"): every id of the gold
    ranking is one of the question's papers. A ranking of names (SOFC materials) is not."""
    want = [str(x) for x in q.gold.get("ranking") or []]
    return q.kind == "rank" and bool(want) and set(want) <= set(question_papers(q))


def answer_column(q: RealQuestion) -> str | None:
    """The column of a rank line's rows that holds the answer: `paper` for a paper-id gold, else the first column
    (None). Shared with the error split, so the key store and the run are compared on the same column."""
    return "paper" if paper_gold(q) else None


def _majority(directions: list[str]) -> str | None:
    counts = Counter(d for d in directions if d)
    if not counts:
        return None
    top = counts.most_common()
    return top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else None


def _about(claim: dict[str, Any], conclusions: list[dict[str, Any]]) -> str | None:
    if len(conclusions) == 1:
        return str(conclusions[0]["id"])
    said = " ".join(str(claim.get(k) or "") for k in ("subject", "object")).casefold()
    hits = [str(c["id"]) for c in conclusions
            if str(c["id"]).casefold() in said or (c.get("text") and str(c["text"]).casefold() in said)]
    return hits[0] if len(hits) == 1 else None


RANK_TEMPLATES = ("rank", "best")


def scored_line(plan: Any, q: RealQuestion) -> Any:
    """The plan line a rank or list question is scored on, by the headline and the answer-key split alike: for a
    ranking its first rank/best line, else the line asking the question's text, else the first line (oversell left out)."""
    lines = [x for x in plan.lines if x.id != OVERSELL] or list(plan.lines)
    if q.kind == "rank":
        hit = next((x for x in lines if x.template in RANK_TEMPLATES), None)
        if hit is not None:
            return hit
    return next((x for x in lines if x.question == q.question), lines[0])


def _scored_lines(root: Path, answer: dict[str, Any], q: RealQuestion) -> list[dict[str, Any]]:
    """The answered lines `from_run` reads: with the run's plan.json, the scored line only (empty or failed: no line,
    an empty answer, never a later line); a folder without a plan keeps every answered line, the first one read."""
    from evidence.plan import load_plan
    from evidence.rundir import PLAN_FILE
    lines = _lines(answer)
    if q.kind not in ("rank", "list") or not (root / PLAN_FILE).is_file():
        return lines
    spec = scored_line(load_plan(root / PLAN_FILE), q)
    return [x for x in lines if x.get("id") == spec.id]


def from_run(run: Path | str, q: RealQuestion) -> Answer:
    """The `Answer` of an engine run folder for question `q` (the contract above)."""
    root = Path(run)
    answer = json.loads((root / "answer.json").read_text(encoding="utf-8"))
    lines = _scored_lines(root, answer, q)
    if q.kind == "rank":
        column = answer_column(q)
        rows = lines[0]["rows"] if lines else []
        if column is not None:   # paper ids in the gold: the `paper` column only; no such column is an empty answer
            rows = [r for r in rows if column in r]
        return Answer(ranking=_column(rows, column))
    if q.kind == "list":
        return Answer(names=_column(lines[0]["rows"]) if lines else [])
    if q.kind == "compare":
        rows = next((x["rows"] for x in lines if all("paper" in r and "direction" in r for r in x["rows"])), None)
        pairs = ([(r["paper"], r["direction"]) for r in rows] if rows is not None else
                 [(s["document"], s["direction"]) for s in (answer.get("synthesis") or answer).get("studies") or []])
        directions = {str(p): DIRECTION_OF[d] for p, d in pairs if d in DIRECTION_OF}
        return Answer(directions=directions, conclusion=_majority(list(directions.values())))
    from evidence.rundir import EVIDENCE_FILE, read_lines
    path = root / EVIDENCE_FILE
    claims = [r["fields"] for r in (read_lines(path) if path.is_file() else []) if r.get("evidence_type") == "claim"]
    conclusions = list(q.gold.get("conclusions") or [])
    by_about: dict[str, list[str]] = {}
    for c in claims:
        about = _about(c, conclusions) if c.get("direction") in DIRECTION_OF else None
        if about is not None:
            by_about.setdefault(about, []).append(DIRECTION_OF[c["direction"]])
    return Answer(claims=[{"about": a, "direction": d} for a, ds in by_about.items() if (d := _majority(ds))])


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
    want, got = list(gold["items"]), []
    for name in answer.names:    # one entry per name: "SQuAD" and "squad" are one
        if _find(name, got, groups) is None:
            got.append(name)
    right = [n for n in got if _find(n, want, groups) is not None]
    found = [w for w in want if _find(w, got, groups) is not None]
    precision, recall = ratio(len(right), len(got)), ratio(len(found), len(want))
    f1 = None
    if precision is not None and recall is not None:
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1, "n_answer": len(got), "n_gold": len(want)}


def _compare(answer: Answer, gold: dict[str, Any]) -> dict[str, Any]:
    per = {study: int(answer.directions.get(study) == d) for study, d in gold["directions"].items()}
    out: dict[str, Any] = {"per_study": per, "direction_agreement": ratio(sum(per.values()), len(per))}
    if gold.get("conclusion") is not None:
        out["conclusion_agrees"] = int(answer.conclusion == gold["conclusion"])
    return out


def _claims(answer: Answer, gold: dict[str, Any]) -> dict[str, Any]:
    want = {c["id"]: c["direction"] for c in gold["conclusions"]}
    right = [c for c in answer.claims if want.get(c.get("about")) == c.get("direction")]
    agreed = {c["about"] for c in right}
    return {"precision": ratio(len(right), len(answer.claims)), "recall": ratio(len(agreed), len(want)),
            "n_claims": len(answer.claims), "n_conclusions": len(want)}


def question_papers(q: RealQuestion) -> list[str]:
    """The paper ids a question rests on: its gold's `papers`, else the corpus manifest's."""
    if "papers" in q.gold:
        return [str(p) for p in q.gold["papers"]]
    return manifest_ids(q.corpus_dir) or []


def tune_papers(q: RealQuestion) -> set[str]:
    """The papers held out for tuning (tune_split.json in the corpus dir or its parent); empty without the file.
    Warns when none of the question's paper ids appears in the file's id space (held-out and rest), since the guard
    could then never fire."""
    for folder in (Path(q.corpus_dir), Path(q.corpus_dir).parent):
        path = folder / TUNE_FILE
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            known = set(data["papers"]) | set(data.get("rest", []))
            mine = set(question_papers(q))
            if known and mine and not mine & known:
                warnings.warn(f"{q.id}: none of its paper ids is in {path}; the tune guard cannot check it",
                              stacklevel=2)
            return set(data["papers"])
    return set()


def key_status(q: RealQuestion) -> str:
    """"available" when the set has answer-key records, else the report line for a set without them."""
    return "available" if q.records is not None else "key-records run: not available"


def key_store(q: RealQuestion) -> Any:
    """The question's answer-key records as a graph (keystore.store), or None when the set has none."""
    if q.records is None:
        return None
    from .realpapers.keystore import store
    return store(q.records)


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


def tune_split_questions(questions: list[RealQuestion], fraction: float = 0.2, seed: int = 0,
                         out: Path | None = None) -> dict[str, Any]:
    """Hold out at QUESTION level: pick round(fraction * n) questions (at least 1 when there are two or more); the
    tuning slice ("papers") is the papers of those questions that no kept question uses, so every kept question stays
    scorable (`score` refuses a question that has a held-out paper). Written to `out` in `tune_split`'s format plus
    "questions" (held) and "kept_questions"."""
    ids = [q.id for q in questions]
    k = min(len(ids) - 1, max(1, round(len(ids) * fraction))) if len(ids) > 1 else 0
    held_ids = set(random.Random(seed).sample(sorted(ids), k))
    used = {p for q in questions if q.id not in held_ids for p in question_papers(q)}
    every = {p for q in questions for p in question_papers(q)}
    held = sorted(every - used)
    split = {"seed": seed, "fraction": fraction, "level": "question", "papers": held,
             "rest": sorted(every - set(held)), "questions": sorted(held_ids),
             "kept_questions": [i for i in ids if i not in held_ids]}
    if out is not None:
        Path(out).write_text(json.dumps(split, indent=1) + chr(10), encoding="utf-8", newline=chr(10))
    return split


def left_out_line(left_out: int, total: int) -> str:
    return f"left out: {left_out} of {total} (no open full text)"


def score_set(questions: list[RealQuestion], answers_auto: dict[str, Answer], answers_hand: dict[str, Answer],
              out: Path, *, n: int = 10, seed: int = 0, groups: NameGroups | None = None) -> dict[str, Any]:
    """The two rows of a set, "auto-confirmed" and "hand-confirmed" (hand: the first 5 sampled questions), over the
    fixed sample (n questions, seed); writes sample.json and real_set.json into `out`. A question with no answer in
    a row is scored as an empty answer."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    chosen = sample(questions, n, seed, out / SAMPLE_FILE)
    rows = {"auto-confirmed": [score(answers_auto.get(q.id, Answer()), q, confirmation="auto-confirmed", groups=groups)
                               for q in chosen],
            "hand-confirmed": [score(answers_hand.get(q.id, Answer()), q, confirmation="hand-confirmed",
                                     groups=groups) for q in chosen[:5]]}
    (out / "real_set.json").write_text(json.dumps(rows, indent=1) + chr(10), encoding="utf-8", newline=chr(10))
    return rows
