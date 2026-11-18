"""Answer sheets: a checklist of 1 to 6 points per (folder, question), each citing the fact lines it rests on.

A sheet records the hashes of its question and of the folder's truth; a change makes it stale. Code never sets
`checked` by itself: `check_sheet` and `person_sheet` are Aditya's edits.
"""
from __future__ import annotations

import json
import random
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from jsonio import canonical_bytes, sha256_hex, write_json_atomic
from synth2.recipe import Strict
from synth3.questions import Question, sheet_question_sha256
from synth3.sheetfacts import FactLine, Folder, cant_tell, relevant_facts, truth_sha256
from synth3.spec import SPECS

SHEETS = SPECS / "sheets"
RESULTS = SPECS / "results"
BUILT = SPECS / "built"
MAX_POINTS = 6
MAX_POINT_CHARS = 300
CANT_TELL_POINT = "The answer says that the papers in this folder cannot answer the question."
PLANNED_QUESTIONS = 25
_STUDY_ID = re.compile(r"S\d{3}")


def folders_of(domain: str, built: Path = BUILT) -> Path:
    """The real folder set of a domain when it exists, else the template one; each holds `s<seed>/`."""
    real = built / f"{domain}-real"
    return real if real.is_dir() else built / domain


class Point(Strict):
    id: str
    text: str
    facts: list[str]


class Sheet(Strict):
    domain: str
    seed: int
    question_id: str
    question_sha256: str
    truth_sha256: str
    cant_tell: bool
    facts: list[FactLine]
    points: list[Point]
    status: Literal["drafted", "checked"]
    drafted_by: dict
    checked_by: str | None = None
    checked_at: str | None = None
    warnings: list[str] = []


def sheet_path(root: Path, domain: str, seed: int, qid: str) -> Path:
    return root / domain / f"s{seed}" / f"{qid}.json"


def save_sheet(root: Path, sheet: Sheet) -> Path:
    path = sheet_path(root, sheet.domain, sheet.seed, sheet.question_id)
    write_json_atomic(path, sheet.model_dump())
    return path


def load_sheet(root: Path, domain: str, seed: int, qid: str) -> Sheet | None:
    path = sheet_path(root, domain, seed, qid)
    if not path.is_file():
        return None
    return Sheet(**json.loads(path.read_text(encoding="utf-8")))


def sheet_sha256(sheet: Sheet) -> str:
    return sha256_hex(canonical_bytes(sheet.model_dump()))


def check_points(points: list[tuple[str, list[str]]], facts: list[FactLine], *, by_model: bool,
                 names: Sequence[str] = ()) -> list[str]:
    """Problems, each naming the point number. `names` are the spec's own names; digits inside them are allowed."""
    known = {f.id for f in facts}
    if not points:
        return ["no points"]
    problems: list[str] = []
    if len(points) > MAX_POINTS:
        problems.append(f"at most {MAX_POINTS} points are allowed, got {len(points)}")
    seen: dict[str, int] = {}
    for i, (text, cites) in enumerate(points, 1):
        if not text.strip():
            problems.append(f"point {i}: empty text")
        elif len(text) > MAX_POINT_CHARS:
            problems.append(f"point {i}: longer than {MAX_POINT_CHARS} characters")
        key = text.strip()
        if key and key in seen:
            problems.append(f"point {i}: same text as point {seen[key]}")
        seen.setdefault(key, i)
        problems += [f"point {i}: unknown fact {c}" for c in cites if c not in known]
        if by_model:
            if not cites:
                problems.append(f"point {i}: cites no fact")
            rest = _STUDY_ID.sub("", text)
            for n in sorted(names, key=len, reverse=True):
                rest = rest.replace(n, "")
            if re.search(r"\d", rest):
                problems.append(f"point {i}: holds a number")
    return problems


def coverage_warnings(points: list[tuple[str, list[str]]], facts: list[FactLine]) -> list[str]:
    cited = {c for _, cites in points for c in cites}
    return [f"fact {f.id} is in no point" for f in facts
            if f.id.startswith(("pair:", "h2h:")) and f.id not in cited]


def _sheet(folder: Folder, q: Question, points: list[tuple[str, list[str]]], drafted_by: dict,
           cant: bool) -> Sheet:
    facts = relevant_facts(folder.spec, folder.truth, q)
    return Sheet(domain=folder.spec.domain, seed=folder.seed, question_id=q.id,
                 question_sha256=sheet_question_sha256(q), truth_sha256=truth_sha256(folder.truth),
                 cant_tell=cant, facts=facts,
                 points=[Point(id=f"p{i}", text=t, facts=list(c)) for i, (t, c) in enumerate(points, 1)],
                 status="drafted", drafted_by=drafted_by, warnings=coverage_warnings(points, facts))


def make_sheet(folder: Folder, q: Question, points: list[tuple[str, list[str]]], drafted_by: dict) -> Sheet:
    """Status `drafted`; the points are not checked here (the drafter and `check_sheet` do that)."""
    return _sheet(folder, q, points, drafted_by, False)


def cant_tell_sheet(folder: Folder, q: Question) -> Sheet | None:
    ids = cant_tell(folder.spec, folder.truth, q)
    if ids is None:
        return None
    return _sheet(folder, q, [(CANT_TELL_POINT, ids)], {"code": "cant_tell"}, True)


def stale(sheet: Sheet, q: Question, folder: Folder) -> str | None:
    """Why the sheet no longer fits, or None. A sub-question edit never makes a sheet stale."""
    if sheet.question_sha256 != sheet_question_sha256(q):
        return "the question changed after drafting"
    if sheet.truth_sha256 != truth_sha256(folder.truth):
        return "the folder's truth changed after drafting"
    return None


def _raise(problems: list[str]) -> None:
    if problems:
        raise ValueError("; ".join(problems))


def check_sheet(sheet: Sheet, points: list[tuple[str, list[str]]], by: str, now: str) -> Sheet:
    """Aditya's edit of a sheet that is not stale (the caller checks `stale`)."""
    _raise(check_points(points, sheet.facts, by_model=False))
    return sheet.model_copy(update={
        "points": [Point(id=f"p{i}", text=t, facts=list(c)) for i, (t, c) in enumerate(points, 1)],
        "status": "checked", "checked_by": by, "checked_at": now,
        "warnings": coverage_warnings(points, sheet.facts),
        "cant_tell": [t for t, _ in points] == [CANT_TELL_POINT]})


def person_sheet(folder: Folder, q: Question, points: list[tuple[str, list[str]]], by: str, now: str, *,
                 checked: bool) -> Sheet:
    s = make_sheet(folder, q, points, {"person": by})
    _raise(check_points(points, s.facts, by_model=False))
    update: dict = {"cant_tell": [t for t, _ in points] == [CANT_TELL_POINT]}
    if checked:
        update |= {"status": "checked", "checked_by": by, "checked_at": now}
    return s.model_copy(update=update)


def archive_sheet(root: Path, sheet: Sheet) -> Path:
    """Move the current file to `<qid>.stale-<n>.json` beside it; never deletes. No file there is a `ValueError`
    naming it (callers archive only a sheet they loaded)."""
    path = sheet_path(root, sheet.domain, sheet.seed, sheet.question_id)
    if not path.is_file():
        raise ValueError(f"{path}: no sheet file to archive")
    n = 1
    while (dest := path.with_name(f"{sheet.question_id}.stale-{n}.json")).exists():
        n += 1
    path.replace(dest)
    return dest


def review_queue(root: Path, domain: str, seeds: list[int], qids: list[str], full_seed: int = 1,
                 rate: float = 20 / (4 * PLANNED_QUESTIONS), *, questions: dict[str, Question] | None = None,
                 folders: dict[int, Folder] | None = None) -> list[dict]:
    """One row per (seed, qid). `stale` is reported only when `questions` (by id) and `folders` (by seed) are given."""
    rows = []
    for seed in seeds:
        for qid in qids:
            sheet = load_sheet(root, domain, seed, qid)
            reason = None
            if sheet and questions and folders and qid in questions and seed in folders:
                reason = stale(sheet, questions[qid], folders[seed])
            if seed == full_seed:
                must = "full"
            elif random.Random(f"synth3:review:{domain}:{qid}:{seed}").random() < rate:
                must = "sample"
            else:
                must = None
            rows.append({"seed": seed, "question_id": qid, "status": sheet.status if sheet else "missing",
                         "stale": reason, "must_check": must})
    return rows
