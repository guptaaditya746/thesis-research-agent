"""The answer-sheet drafter: `orch-model` (generation) turns the facts a question needs into checklist points.

Code picks the facts (`sheetfacts`), writes can't-tell sheets with no call, and checks every draft
(`sheets.check_points`) with one repair (`asking.ask_checked`). Sub-questions never reach the drafter, so a sheet
point can never come from one. `draft_folder_sheets` never overwrites a checked sheet that is not stale."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from modelcall import CallSettings, JsonlCache, model_name
from synth2.recipe import Strict
from synth3.asking import ask_checked
from synth3.questions import Question, QuestionSet
from synth3.sheetfacts import FactLine, Folder, relevant_facts
from synth3.sheets import (Sheet, archive_sheet, cant_tell_sheet, check_points, load_sheet, make_sheet, save_sheet,
                           stale)

DRAFTER_ALIAS = "orch-model"
PROMPT = Path(__file__).resolve().parent / "prompts" / "sheet-v1.txt"
SETTINGS = CallSettings(max_tokens=2048)


class DraftPoint(Strict):
    text: str
    facts: list[str]


class DraftSheet(Strict):
    points: list[DraftPoint]


def _pairs(draft: DraftSheet) -> list[tuple[str, list[str]]]:
    return [(p.text, list(p.facts)) for p in draft.points]


def drafter_input(q: Question, facts: list[FactLine]) -> str:
    """The main question and the fact lines; sub-questions are left out."""
    lines = "\n".join(f"{f.id}: {f.text}" for f in facts)
    return f"Question: {q.question}\n\nFacts:\n{lines}"


def draft_sheet(folder: Folder, q: Question, model: Any, cache: JsonlCache, *, fresh: str | None = None) -> Sheet:
    """A can't-tell sheet by code (no call), else a checked model draft. No accepted draft (a failed call
    included) is a `ValueError` naming the question, the seed and the problems."""
    code = cant_tell_sheet(folder, q)
    if code is not None:
        return code
    facts = relevant_facts(folder.spec, folder.truth, q)
    names = folder.spec.names()
    out = ask_checked(PROMPT, DraftSheet, drafter_input(q, facts),
                      lambda r: check_points(_pairs(r), facts, by_model=True, names=names),
                      model, cache, SETTINGS, fresh=fresh)
    if out["reply"] is None:
        raise ValueError(f"{q.id} s{folder.seed}: {'; '.join(out['problems'])}")
    return make_sheet(folder, q, _pairs(out["reply"]),
                      {"model": model_name(model), "served_models": out["served_models"],
                       "prompt_sha256": out["prompt_sha256"], "attempts": out["calls"]})


def draft_folder_sheets(folder: Folder, qs: QuestionSet, model: Any, cache: JsonlCache, root: Path, *,
                        redraft: set[str] = frozenset(), now: str) -> dict:
    """Draft the missing and stale sheets of one folder, and those in `redraft` (with `fresh=now`, past the cache).

    A checked sheet that is not stale is always kept (`kept_checked` lists those asked for in `redraft`); a stale
    checked sheet is kept and listed under `stale_checked` unless it is in `redraft`: then it is archived once the
    new draft is accepted. A sheet Aditya wrote (`drafted_by` names a person), checked or not, stale or not, is
    kept unless it is in `redraft`, and then archived the same way. One failure does not stop the others. Lists of question ids: `drafted` (every new
    sheet), `cant_tell` (the code sheets among them), `kept` (every sheet left as it was), `kept_checked`,
    `stale_checked`; `failed` maps a question id to its problem."""
    out: dict = {"drafted": [], "cant_tell": [], "kept": [], "kept_checked": [], "stale_checked": [], "failed": {}}
    for q in qs.questions:
        again = q.id in redraft
        old = load_sheet(root, folder.spec.domain, folder.seed, q.id)
        why = stale(old, q, folder) if old is not None else None
        if old is not None and old.status == "checked" and (why is None or not again):
            out["kept"].append(q.id)
            if why is not None:
                out["stale_checked"].append(q.id)   # Aditya fixes it on the review page
            elif again:
                out["kept_checked"].append(q.id)
            continue
        mine = old is not None and (old.status == "checked" or "person" in old.drafted_by)   # Aditya's work
        if old is not None and (why is None or mine) and not again:
            out["kept"].append(q.id)   # a fresh draft, or a sheet Aditya wrote (stale or not)
            continue
        try:
            sheet = draft_sheet(folder, q, model, cache, fresh=now if again else None)
        except ValueError as err:
            out["failed"][q.id] = str(err)
            continue
        if mine:
            archive_sheet(root, old)   # only once the new draft is accepted
        save_sheet(root, sheet)
        out["drafted"].append(q.id)
        if sheet.cant_tell:
            out["cant_tell"].append(q.id)
    return out
