"""The judge: `sub-model-1` (verification, docs/prompt-writing.md) marks answers in three separate scores.

A: per paper, the judge marks each planted fact in the question's scope as found, wrong or missing among the facts
the system pulled from that paper. Code picks the planted facts from `ground_truth.json` and adds `anchored`, the
share of planted facts whose span a pulled fact touches (code only, not the score).
B: the judge splits the answer into its factual claims and marks each as supported, contradicted or invented
against the facts the answer used (the cited papers' pulled facts, or the baseline's passages).
C: the judge ticks each answer-sheet point as met or not, quoting the answer when met.

Code checks every reply with one repair (`asking.ask_checked`); a reply that stays bad, or a failed call, leaves
the item (A: the paper; B, C: the answer) pending and the run goes on. Every judge call gets the spec's measures
with their direction, so it never guesses what "better" means. The judge never sees the sub-questions, the
answer-sheet fact lines (A, B) or the system name."""
from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from jsonio import canonical
from modelcall import CallSettings, JsonlCache, load_prompt
from synth2.recipe import Strict
from synth3.answers import AnswerRecord, PulledFact
from synth3.asking import ask_checked
from synth3.questions import Question
from synth3.sheetfacts import Folder, scope
from synth3.sheets import Sheet
from synth3.spec import DomainSpec, Measure
from synth3.world import Cell, Study

JUDGE_ALIAS = "sub-model-1"
SETTINGS = CallSettings(max_tokens=4096)
PROMPTS = Path(__file__).resolve().parent / "prompts"
PROMPT_A = PROMPTS / "judge-a-v1.txt"
PROMPT_B = PROMPTS / "judge-b-v1.txt"
PROMPT_C = PROMPTS / "judge-c-v1.txt"
MAX_FACTS = 150      # B: used facts shown to the judge (builder's call)
MAX_PER_PAPER = 60   # A: pulled facts of one paper shown to the judge
_SAYS = {"helps": "does better than", "hurts": "does worse than", "no_effect": "shows no real difference from"}


def squash(text: str) -> str:
    """`text` with every run of white space folded to one space, trimmed, in lower case."""
    return " ".join(text.split()).lower()


class Tick(Strict):
    point: str
    met: bool
    quote: str | None
    reason: str


class Ticks(Strict):
    ticks: list[Tick]


def measures_block(measures: Sequence[Measure]) -> str:
    """One line per measure of the folder's spec with its direction, so the judge never guesses what "better"
    means."""
    return "\n".join(f"{m.name}: {'higher' if m.higher_is_better else 'lower'} is better" for m in measures)


def c_input(q: Question, sheet: Sheet, text: str, measures: Sequence[Measure]) -> str:
    """The main question, the spec's measures with their direction, the sheet points by id, then the answer."""
    points = "\n".join(f"{p.id}: {p.text}" for p in sheet.points)
    return (f"Question: {q.question}\n\nMeasures:\n{measures_block(measures)}\n\nPoints:\n{points}"
            f"\n\nAnswer:\n{text}")


def check_ticks(t: Ticks, sheet: Sheet, text: str) -> list[str]:
    """Problems: a point ticked twice or not at all, an unknown point, a met point whose quote is not in the answer."""
    ids = [p.id for p in sheet.points]
    answer = squash(text)
    problems: list[str] = []
    seen: set[str] = set()
    for tick in t.ticks:
        if tick.point not in ids:
            problems.append(f"unknown point {tick.point}")
        elif tick.point in seen:
            problems.append(f"{tick.point} twice")
        else:
            seen.add(tick.point)
            if tick.met:
                quote = squash(tick.quote or "")
                if not quote:
                    problems.append(f"{tick.point}: a met point needs a quote")
                elif quote not in answer:
                    problems.append(f"{tick.point}: quote not in the answer")
    return problems + [f"{p} missing" for p in ids if p not in seen]


def score_c(q: Question, sheet: Sheet, rec: AnswerRecord, model: Any, cache: JsonlCache, *, fresh: str | None = None,
            measures: Sequence[Measure]) -> dict:
    """Met points / points; `measures` are the folder spec's (`folder.spec.measures`). An empty answer misses
    every point with no call. Pending (the reply still fails its checks, or the call failed): `score` None, the
    problems say why."""
    ids = [p.id for p in sheet.points]
    if not rec.text.strip():
        empty = [Tick(point=p, met=False, quote=None, reason="the answer is empty").model_dump() for p in ids]
        return {"score": 0.0, "ticks": empty, "missed": ids, "status": "ok", "problems": [], "calls": 0,
                "prompt_sha256": load_prompt(PROMPT_C, Ticks).sha256, "served_models": []}
    out = ask_checked(PROMPT_C, Ticks, c_input(q, sheet, rec.text, measures),
                      lambda r: check_ticks(r, sheet, rec.text), model, cache, SETTINGS, fresh=fresh)
    done = {"calls": out["calls"], "prompt_sha256": out["prompt_sha256"], "served_models": out["served_models"]}
    if out["reply"] is None:
        return {"score": None, "ticks": [], "missed": [], "status": "pending", "problems": out["problems"], **done}
    by_point = {t.point: t for t in out["reply"].ticks}
    ticks = [by_point[p] for p in ids]
    missed = [t.point for t in ticks if not t.met]
    return {"score": (len(ids) - len(missed)) / len(ids), "ticks": [t.model_dump() for t in ticks],
            "missed": missed, "status": "ok", "problems": [], **done}


# --- A: planted facts found among the pulled facts, per paper ---------------------------------------------------

class PlantedFact(Strict):
    id: str
    paper: str
    text: str
    spans: list[tuple[int, int]]


def _levels(spec: DomainSpec, cell: Cell) -> str:
    """The level names of a cell, one per condition in spec order, as the paper prints its subset."""
    return ", ".join(next(lv.name for lv in c.levels if lv.id == cell.levels[c.id]) for c in spec.conditions)


def _row_text(spec: DomainSpec, cell: Cell, arm: str) -> str:
    m, r = spec.measure(cell.measure), cell.result(arm)
    label = next(a.label for a in spec.arms if a.id == arm)
    if m.kind == "count":
        value = f"{r.k} of {r.n} ({100 * r.k / r.n:.1f}%)"
    else:
        value = f"mean {r.mean:.{m.decimals}f}, SD {r.sd:.{m.decimals}f}, n {r.n}"
    return f"{label}, {m.name}, {_levels(spec, cell)}: {value}"


def planted_facts(folder: Folder, q: Question) -> dict[str, list[PlantedFact]]:
    """The planted facts the question needs, by paper in paper order: the result rows of the named treatments (all
    when none is named) on the named measures (all when none), with the control's row of those cells; the authors'
    claims between those arms and the control on those measures; the setting of each paper with any of these.
    `spans`: the placements of the fact id or of its parts (`<id>.k`, `<id>.abstract`, ...)."""
    spec = folder.spec
    n = scope(spec, q)
    T = [t.id for t in spec.treatments if t.id in n.arms] or [t.id for t in spec.treatments]
    M = n.measures or [m.id for m in spec.measures]
    arms = {*T, spec.control.id}
    label = {a.id: a.label for a in spec.arms}
    places: dict[str, list[dict]] = {}
    for pl in folder.truth["placements"]:
        places.setdefault(pl["paper"], []).append(pl)
    out: dict[str, list[PlantedFact]] = {}
    for raw in folder.truth["studies"]:
        s = Study.parse(raw)
        texts: list[tuple[str, str]] = []
        for cell in s.cells:
            if cell.measure in M and any(r.arm in T for r in cell.results):
                texts += [(f"{s.id}.c{cell.index}.{r.arm}", _row_text(spec, cell, r.arm))
                          for r in cell.results if r.arm in arms]
        for key, word in s.claims.items():
            arm, against, m = key.split("|")
            if m in M and arm in arms and against in arms:
                texts.append((f"{s.id}.claim.{arm}.{against}.{m}", f"The authors say {label[arm]} {_SAYS[word]} "
                                                                   f"{label[against]} on {spec.measure(m).name}"))
        if not texts:
            continue
        texts.append((f"{s.id}.setting", f"The study ran at {s.setting}"))
        mine = places.get(s.id, [])
        out[s.id] = [PlantedFact(id=fid, paper=s.id, text=text,
                                 spans=[(pl["start"], pl["end"]) for pl in mine
                                        if pl["fact"] == fid or pl["fact"].startswith(f"{fid}.")])
                     for fid, text in texts]
    return out


def anchored(planted: dict[str, list[PlantedFact]], facts: list[PulledFact]) -> float | None:
    """The share of planted facts with a span that shares a character with a pulled fact's [start, end) in the
    same paper (code only); None when nothing is planted."""
    total = sum(len(ps) for ps in planted.values())
    if not total:
        return None
    pulled: dict[str, list[tuple[int, int]]] = {}
    for f in facts:
        if f.start is not None and f.end is not None:
            pulled.setdefault(f.paper, []).append((f.start, f.end))
    hit = sum(1 for ps in planted.values() for p in ps
              if any(s < b and a < e for a, b in p.spans for s, e in pulled.get(p.paper, [])))
    return hit / total


class Mark(Strict):
    fact: str
    verdict: Literal["found", "wrong", "missing"]
    pulled: int | None
    reason: str


class PaperMarks(Strict):
    marks: list[Mark]


def _fact_lines(facts: Sequence[PulledFact], *, paper: bool) -> str:
    """One numbered line per pulled fact: `<i>. [<paper> ]<kind> <fields as JSON> quote: "<quote>"`. The quote is a
    JSON string, so a line break or a quote mark in a multi-line baseline passage stays inside its own line."""
    return "\n".join(f"{i}. {f'{f.paper} ' if paper else ''}{f.kind} {canonical(f.fields)} quote: "
                     f"{json.dumps(f.quote, ensure_ascii=False)}" for i, f in enumerate(facts, 1))


def a_input(planted: list[PlantedFact], pulled: list[PulledFact], *, measures: Sequence[Measure]) -> str:
    """One paper: the spec's measures with their direction, its planted facts by id, then its pulled facts
    numbered from 1 (at most MAX_PER_PAPER)."""
    lines = "\n".join(f"{p.id}: {p.text}" for p in planted)
    return (f"Measures:\n{measures_block(measures)}\n\nPlanted facts:\n{lines}\n\nPulled facts:\n"
            f"{_fact_lines(pulled[:MAX_PER_PAPER], paper=False)}")


def check_marks(m: PaperMarks, planted: list[PlantedFact], n_pulled: int) -> list[str]:
    """Problems: a planted fact marked twice or not at all, an unknown fact, a found or wrong mark without a pulled
    fact number in 1..n_pulled, a missing mark that cites one, a wrong mark citing a pulled fact that the same
    reply marks found for another planted fact (that pulled fact is about the other one)."""
    ids = [p.id for p in planted]
    problems: list[str] = []
    seen: set[str] = set()
    found: dict[int, str] = {}
    wrong: list[Mark] = []
    for mark in m.marks:
        if mark.fact not in ids:
            problems.append(f"unknown fact {mark.fact}")
        elif mark.fact in seen:
            problems.append(f"{mark.fact} twice")
        else:
            seen.add(mark.fact)
            if mark.pulled is not None:
                if mark.verdict == "found":
                    found.setdefault(mark.pulled, mark.fact)
                elif mark.verdict == "wrong":
                    wrong.append(mark)
            if mark.verdict == "missing":
                if mark.pulled is not None:
                    problems.append(f"{mark.fact}: missing cites no pulled fact")
            elif mark.pulled is None:
                problems.append(f"{mark.fact}: {mark.verdict} needs a pulled fact number")
            elif not 1 <= mark.pulled <= n_pulled:
                problems.append(f"{mark.fact}: pulled fact {mark.pulled} is not in 1 to {n_pulled}")
    problems += [f"{w.fact}: pulled fact {w.pulled} is found for {found[w.pulled]}, so it is not a wrong version of "
                 "this fact" for w in wrong if w.pulled in found]
    return problems + [f"{i} not marked" for i in ids if i not in seen]


def score_a(folder: Folder, q: Question, rec: AnswerRecord, model: Any, cache: JsonlCache, *,
            fresh: str | None = None) -> dict | None:
    """Found planted facts / planted facts, pooled over the papers not pending; None for a record that pulls no
    per-paper facts (the baseline). A paper with no pulled fact has every planted fact missing, with no call."""
    if rec.facts is None:
        return None
    planted = planted_facts(folder, q)
    papers: dict[str, list[dict]] = {}
    pending, cut, problems, served, calls = [], [], {}, [], 0
    for sid, mine in planted.items():
        pulled = [f for f in rec.facts if f.paper == sid]
        if not pulled:
            papers[sid] = [Mark(fact=p.id, verdict="missing", pulled=None,
                                reason="no fact was pulled from this paper").model_dump() for p in mine]
            continue
        if len(pulled) > MAX_PER_PAPER:
            cut.append(sid)
        shown = pulled[:MAX_PER_PAPER]
        out = ask_checked(PROMPT_A, PaperMarks, a_input(mine, shown, measures=folder.spec.measures),
                          lambda r, mine=mine, n=len(shown): check_marks(r, mine, n), model, cache, SETTINGS,
                          fresh=fresh)
        calls += out["calls"]
        served += out["served_models"]
        if out["reply"] is None:
            pending.append(sid)
            problems[sid] = out["problems"]
            continue
        by_fact = {mk.fact: mk for mk in out["reply"].marks}
        papers[sid] = [by_fact[p.id].model_dump() for p in mine]
    marks = [mk for ms in papers.values() for mk in ms]
    count = {v: sum(mk["verdict"] == v for mk in marks) for v in ("found", "wrong", "missing")}
    return {"score": count["found"] / len(marks) if marks else None, **count, "total": len(marks),
            "anchored": anchored(planted, rec.facts), "pending_papers": pending, "pulled_cut": cut,
            "papers": papers, "problems": problems, "calls": calls,
            "prompt_sha256": load_prompt(PROMPT_A, PaperMarks).sha256, "served_models": served}


# --- B: the answer's claims against the facts it used -----------------------------------------------------------

class ClaimCheck(Strict):
    claim: str
    verdict: Literal["supported", "invented", "contradicted"]
    facts: list[int]
    reason: str


class ClaimChecks(Strict):
    claims: list[ClaimCheck]


def used_facts(rec: AnswerRecord) -> tuple[list[PulledFact], bool]:
    """The facts the answer used and whether they were cut at MAX_FACTS: the baseline's passages; else the pulled
    facts of the cited papers (all pulled facts when no paper is cited)."""
    if rec.facts is None:
        pool = rec.passages
    else:
        pool = [f for f in rec.facts if f.paper in rec.cited] if rec.cited else rec.facts
    return list(pool[:MAX_FACTS]), len(pool) > MAX_FACTS


def b_input(q: Question, rec: AnswerRecord, used: list[PulledFact], *, measures: Sequence[Measure]) -> str:
    """The main question, the spec's measures with their direction, the used facts numbered from 1, the answer."""
    facts = _fact_lines(used, paper=True) or "(none)"
    return (f"Question: {q.question}\n\nMeasures:\n{measures_block(measures)}\n\nFacts:\n{facts}"
            f"\n\nAnswer:\n{rec.text}")


def check_claims(c: ClaimChecks, text: str, n: int) -> list[str]:
    """Problems: a claim that is empty or not in the answer (by `squash`), a supported or contradicted claim
    without a fact number in 1..n, an invented claim that cites a fact."""
    answer = squash(text)
    problems: list[str] = []
    for i, cc in enumerate(c.claims, 1):
        where = f'claim {i} "{cc.claim}"'
        claim = squash(cc.claim)
        if not claim:
            problems.append(f"{where}: empty")
        elif claim not in answer:
            problems.append(f"{where}: not in the answer")
        if cc.verdict == "invented":
            if cc.facts:
                problems.append(f"{where}: invented cites no fact")
        elif not cc.facts:
            problems.append(f"{where}: {cc.verdict} needs a fact number")
        else:
            problems += [f"{where}: fact {k} is not in 1 to {n}" for k in cc.facts if not 1 <= k <= n]
    return problems


def score_b(q: Question, rec: AnswerRecord, model: Any, cache: JsonlCache, *, fresh: str | None = None,
            measures: Sequence[Measure]) -> dict:
    """Supported claims / claims; `measures` are the folder spec's. No text or no claim: `score` None. Pending
    (the reply still fails its checks, or the call failed): `score`, `invented` and `contradicted` None."""
    used, cut = used_facts(rec)
    sha = load_prompt(PROMPT_B, ClaimChecks).sha256
    if not rec.text.strip():
        return {"score": None, "claims": [], "invented": 0, "contradicted": 0, "facts_cut": cut, "status": "ok",
                "problems": [], "calls": 0, "prompt_sha256": sha, "served_models": []}
    out = ask_checked(PROMPT_B, ClaimChecks, b_input(q, rec, used, measures=measures),
                      lambda r: check_claims(r, rec.text, len(used)), model, cache, SETTINGS, fresh=fresh)
    done = {"facts_cut": cut, "calls": out["calls"], "prompt_sha256": out["prompt_sha256"],
            "served_models": out["served_models"]}
    if out["reply"] is None:
        return {"score": None, "claims": [], "invented": None, "contradicted": None, "status": "pending",
                "problems": out["problems"], **done}
    claims = out["reply"].claims
    count = {v: sum(c.verdict == v for c in claims) for v in ("supported", "invented", "contradicted")}
    return {"score": count["supported"] / len(claims) if claims else None,
            "claims": [c.model_dump() for c in claims], "invented": count["invented"],
            "contradicted": count["contradicted"], "status": "ok", "problems": [], **done}
