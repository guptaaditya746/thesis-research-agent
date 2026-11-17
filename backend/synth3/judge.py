"""The judge: `sub-model-1` (verification, docs/prompt-writing.md) marks answers in three separate scores.

C (this part): the judge ticks each answer-sheet point as met or not, quoting the answer when met. Code checks
every tick (each point exactly once, each quote found in the answer) with one repair (`asking.ask_checked`); a
reply that stays bad, or a failed call, leaves the answer pending and the run goes on. The judge reads the main
question, the spec's measures with their direction, the sheet points and the answer text only: never the
sub-questions, the fact lines or the system name."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from modelcall import CallSettings, JsonlCache, load_prompt
from synth2.recipe import Strict
from synth3.answers import AnswerRecord
from synth3.asking import ask_checked
from synth3.questions import Question
from synth3.sheets import Sheet
from synth3.spec import Measure

JUDGE_ALIAS = "sub-model-1"
SETTINGS = CallSettings(max_tokens=4096)
PROMPTS = Path(__file__).resolve().parent / "prompts"
PROMPT_C = PROMPTS / "judge-c-v1.txt"


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


def score_c(q: Question, sheet: Sheet, rec: AnswerRecord, model: Any, cache: JsonlCache, *,
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
                      lambda r: check_ticks(r, sheet, rec.text), model, cache, SETTINGS)
    done = {"calls": out["calls"], "prompt_sha256": out["prompt_sha256"], "served_models": out["served_models"]}
    if out["reply"] is None:
        return {"score": None, "ticks": [], "missed": [], "status": "pending", "problems": out["problems"], **done}
    by_point = {t.point: t for t in out["reply"].ticks}
    ticks = [by_point[p] for p in ids]
    missed = [t.point for t in ticks if not t.met]
    return {"score": (len(ids) - len(missed)) / len(ids), "ticks": [t.model_dump() for t in ticks],
            "missed": missed, "status": "ok", "problems": [], **done}
