"""The review API under /api/ev/review (synth3, plan 3): Aditya approves worlds, checks and edits answer sheets and
hand-marks the judge-test answers.

    GET /review                              -> {domains: [{domain, questions: n or null, seeds: [n], worlds: [n]}]}
    GET /review/{domain}/worlds              -> [{seed, approved, text, path}] (`text`: synth3.world.describe)
    PUT /review/{domain}/worlds/{seed}       {approved} -> the world row; 422 when the world file does not load
    GET /review/{domain}/sheets              -> synth3.sheets.review_queue rows, with `stale`
    GET /review/{domain}/sheets/{seed}/{qid} -> {question, sub_questions, scope, facts, sheet, stale}
    PUT /review/{domain}/sheets/{seed}/{qid} {points: [{text, facts}]} -> the saved sheet; 400 with the problems
    GET /review/judge-test                   -> [{n, domain, seed, question_id, done}]
    GET /review/judge-test/{n}               -> {n, domain, seed, question_id, question, answer, points, facts,
                                                 facts_cut, marked}; never the judge's ticks or scores, never the
                                                 system
    PUT /review/judge-test/{n}               {points: {pid: bool}, faithful} -> the saved hand mark

Everything lives under `settings.synth3_data`: `<domain>.yaml` (the approved specs; drafts are elsewhere),
`worlds/<domain>/s<n>.json`, `questions/<domain>.yaml`, `sheets/`, `built/` (synth3.sheets.folders_of),
`results/` and `judge-test/`. Every id from a URL or from `sample.json` goes through `files.check_id` and every
path is built with `files.inside` (ReviewFiles). The writes are the world files, the answer sheets (archived
`<qid>.stale-<n>.json` beside a stale one) and the hand marks; they go through one lock and the atomic writers of
synth3 (`save_world`, `save_sheet`, `save_hand_mark`).

A sheet save always lets Aditya fix the sheet: a sheet that is not stale is checked (`check_sheet`); a stale one is
archived and replaced by a new unchecked sheet he wrote (`person_sheet`, so draft-sheets keeps it), which he
checks with a second save; a missing one is written and checked at once.

A judge-test item is blind: it shows the points the C judge saw (kept in the marks file, so they stay as judged
after the sheet is edited), the answer and the facts it used, but never the judge's ticks or scores and never the
system that answered (only the domain, seed and question id; the PUT addresses the item by its number).
"""
from __future__ import annotations

import re
import threading
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from synth3.answers import load_answer
from synth3.judge import used_facts
from synth3.questions import Question, QuestionSet, load_questions
from synth3.report import load_hand_marks, load_sample, save_hand_mark
from synth3.sheetfacts import Folder, check_spec, load_folder, relevant_facts, scope
from synth3.sheets import (Sheet, archive_sheet, check_sheet, folders_of, load_sheet, person_sheet, review_queue,
                           save_sheet, stale)
from synth3.spec import DomainSpec, load_spec
from synth3.world import describe, load_world, save_world

from .files import BadRequest, Conflict, Damaged, NotFound, check_id, inside, read_json
from .settings import Settings

_WRITE = threading.Lock()   # every write of the review API
_SEED_DIR = re.compile(r"^s(\d+)$")
_SEED_FILE = re.compile(r"^s(\d+)\.json$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ReviewFiles:
    """Ids to paths under `settings.synth3_data`; every id is checked and every path stays under the root."""

    def __init__(self, settings: Settings) -> None:
        self.root = Path(settings.synth3_data)

    def under(self, *parts: str) -> Path:
        return inside(self.root, *parts)

    def domains(self) -> list[str]:
        """The approved specs: `<root>/<domain>.yaml` that load."""
        out = []
        for path in sorted(self.root.glob("*.yaml")) if self.root.is_dir() else []:
            try:
                load_spec(check_id(path.stem, "domain"), self.root)
            except (NotFound, ValueError):
                continue
            out.append(path.stem)
        return out

    def spec(self, domain: str) -> DomainSpec:
        check_id(domain, "domain")
        if not self.under(f"{domain}.yaml").is_file():
            raise NotFound(f"no domain {domain!r}")
        try:
            return load_spec(domain, self.root)
        except ValueError as err:
            raise Conflict(str(err)) from err

    def questions(self, domain: str, spec: DomainSpec) -> QuestionSet:
        try:
            return load_questions(check_id(domain, "domain"), spec, self.under("questions"))
        except ValueError as err:
            raise Conflict(str(err)) from err

    def question(self, qs: QuestionSet, qid: str) -> Question:
        check_id(qid, "question")
        try:
            return qs.get(qid)
        except KeyError as err:
            raise NotFound(f"no question {qid!r}") from err

    def world_file(self, domain: str, seed: int) -> Path:
        return self.under("worlds", check_id(domain, "domain"), f"s{int(seed)}.json")

    def world_seeds(self, domain: str) -> list[int]:
        d = self.under("worlds", check_id(domain, "domain"))
        names = [p.name for p in d.glob("s*.json")] if d.is_dir() else []
        return sorted(int(m[1]) for name in names if (m := _SEED_FILE.match(name)))

    def sheets_root(self) -> Path:
        return self.under("sheets")

    def sheet_file(self, domain: str, seed: int, qid: str) -> Path:
        return self.under("sheets", check_id(domain, "domain"), f"s{int(seed)}", f"{check_id(qid, 'question')}.json")

    def folders(self, domain: str) -> Path:
        return folders_of(check_id(domain, "domain"), self.under("built"))

    def built_seeds(self, domain: str) -> list[int]:
        d = self.folders(domain)
        names = [p.name for p in d.iterdir() if p.is_dir()] if d.is_dir() else []
        return sorted(int(m[1]) for name in names if (m := _SEED_DIR.match(name)))

    def folder(self, domain: str, seed: int, spec: DomainSpec) -> Folder:
        path = inside(self.folders(domain), f"s{int(seed)}")
        if not path.is_dir():
            raise NotFound(f"no built folder s{seed} of {domain!r}")
        try:
            folder = load_folder(path)
            check_spec(folder, spec)
        except ValueError as err:
            raise Conflict(f"s{seed}: {err}") from err
        return folder

    def results(self) -> Path:
        return self.under("results")

    def item_file(self, item: str, suffix: str) -> Path:
        """`<domain>/s<seed>/<system>/<qid>` (a judge-test item) to its `<qid><suffix>` under results/."""
        domain, seed, system, qid = self.item_parts(item)
        return self.under("results", domain, f"s{seed}", system, f"{qid}{suffix}")

    @staticmethod
    def item_parts(item: str) -> tuple[str, int, str, str]:
        parts = item.split("/")
        m = _SEED_DIR.match(parts[1]) if len(parts) == 4 else None
        if m is None:
            raise NotFound("a judge-test item in sample.json is not <domain>/s<seed>/<system>/<qid>")
        return check_id(parts[0], "domain"), int(m[1]), check_id(parts[2], "system"), check_id(parts[3], "question")

    def judge_test(self) -> Path:
        return self.under("judge-test")


class Approve(BaseModel):
    approved: bool


class PointIn(BaseModel):
    text: str
    facts: list[str] = []


class SheetIn(BaseModel):
    points: list[PointIn]


class HandMarkIn(BaseModel):
    points: dict[str, bool]
    faithful: bool | None = None


def _names(spec: DomainSpec, q: Question) -> dict[str, list[str]]:
    n = scope(spec, q)
    arm = {a.id: a.label for a in spec.arms}
    cond = {c.id: c.name for c in spec.conditions}
    return {"arms": [arm[a] for a in n.arms], "measures": [spec.measure(m).name for m in n.measures],
            "conditions": [cond[c] for c in n.conditions], "settings": list(n.settings)}


def evreview_router(settings: Settings) -> APIRouter:
    api = APIRouter(generate_unique_id_function=lambda route: route.name)
    files = ReviewFiles(settings)

    def world_row(domain: str, seed: int, spec: DomainSpec) -> dict[str, Any]:
        path = files.world_file(domain, seed)
        if not path.is_file():
            raise NotFound(f"no world s{seed} of {domain!r}")
        try:
            world = load_world(path, spec)
        except ValueError as err:
            raise Damaged(str(err)) from err
        return {"seed": seed, "approved": world.approved, "text": describe(world, spec),
                "path": path.relative_to(files.root).as_posix()}

    @api.get("/review", tags=["review"])
    def review_overview() -> dict[str, Any]:
        rows = []
        for domain in files.domains():
            spec = files.spec(domain)
            try:
                n: int | None = len(files.questions(domain, spec).questions)
            except Conflict:
                n = None
            rows.append({"domain": domain, "questions": n, "seeds": files.built_seeds(domain),
                         "worlds": files.world_seeds(domain)})
        return {"domains": rows}

    @api.get("/review/{domain}/worlds", tags=["review"])
    def review_worlds(domain: str) -> list[dict[str, Any]]:
        spec = files.spec(domain)
        out = []
        for seed in files.world_seeds(domain):
            try:
                out.append(world_row(domain, seed, spec))
            except Damaged as err:   # shown, so Aditya can fix the file
                out.append({"seed": seed, "approved": None, "text": str(err),
                            "path": files.world_file(domain, seed).relative_to(files.root).as_posix(),
                            "problem": str(err)})
        return out

    @api.put("/review/{domain}/worlds/{seed}", tags=["review"])
    def review_approve_world(domain: str, seed: int, req: Approve) -> dict[str, Any]:
        spec = files.spec(domain)
        with _WRITE:
            path = files.world_file(domain, seed)
            if not path.is_file():
                raise NotFound(f"no world s{seed} of {domain!r}")
            try:
                world = load_world(path, spec)
            except ValueError as err:
                raise Damaged(str(err)) from err
            save_world(path, replace(world, approved=req.approved))
            return world_row(domain, seed, spec)

    @api.get("/review/{domain}/sheets", tags=["review"])
    def review_sheets(domain: str) -> list[dict[str, Any]]:
        spec = files.spec(domain)
        qs = files.questions(domain, spec)
        seeds = files.built_seeds(domain)
        folders: dict[int, Folder] = {}
        for seed in seeds:
            try:
                folders[seed] = files.folder(domain, seed, spec)
            except (NotFound, Conflict):
                continue   # its rows still show, without `stale`
        return review_queue(files.sheets_root(), domain, seeds, [q.id for q in qs.questions],
                            questions={q.id: q for q in qs.questions}, folders=folders)

    def sheet_context(domain: str, seed: int, qid: str) -> tuple[Folder, Question, Sheet | None]:
        spec = files.spec(domain)
        q = files.question(files.questions(domain, spec), qid)
        folder = files.folder(domain, seed, spec)
        files.sheet_file(domain, seed, qid)   # the path check
        return folder, q, load_sheet(files.sheets_root(), domain, seed, qid)

    @api.get("/review/{domain}/sheets/{seed}/{qid}", tags=["review"])
    def review_sheet(domain: str, seed: int, qid: str) -> dict[str, Any]:
        folder, q, current = sheet_context(domain, seed, qid)
        return {"question": q.question, "sub_questions": q.sub_questions, "scope": _names(folder.spec, q),
                "facts": [f.model_dump() for f in relevant_facts(folder.spec, folder.truth, q)],
                "sheet": current.model_dump() if current else None,
                "stale": stale(current, q, folder) if current else None}

    @api.put("/review/{domain}/sheets/{seed}/{qid}", tags=["review"])
    def review_save_sheet(domain: str, seed: int, qid: str, req: SheetIn) -> dict[str, Any]:
        points = [(p.text, list(p.facts)) for p in req.points]
        root = files.sheets_root()
        with _WRITE:
            folder, q, current = sheet_context(domain, seed, qid)
            try:
                if current is None:
                    new = person_sheet(folder, q, points, settings.user, now(), checked=True)
                elif stale(current, q, folder):   # before check_sheet: a stale sheet's facts are old
                    new = person_sheet(folder, q, points, settings.user, now(), checked=False)
                    archive_sheet(root, current)
                else:
                    new = check_sheet(current, points, settings.user, now())
            except ValueError as err:
                raise BadRequest(str(err)) from err
            save_sheet(root, new)
            return new.model_dump()

    def item_at(n: int) -> str:
        sample = load_sample(files.judge_test())
        if not 0 <= n < len(sample):
            raise NotFound(f"no judge-test item {n}")
        return sample[n]

    def judged_points(n: int, item: str) -> list[dict[str, str]]:
        """The points the C judge saw, from the marks file (`sheet.points`, in sheet order)."""
        marks = read_json(files.item_file(item, ".marks.json"))
        points = (marks.get("sheet") or {}).get("points") if isinstance(marks, dict) else None
        if not isinstance(points, list):
            raise NotFound(f"judge-test item {n}: not judged yet (no readable marks file)")
        return [{"id": str(p["id"]), "text": str(p["text"])} for p in points]

    def where(item: str) -> dict[str, Any]:
        """The item without the system that answered (Aditya marks blind)."""
        domain, seed, _, qid = files.item_parts(item)
        return {"domain": domain, "seed": seed, "question_id": qid}

    @api.get("/review/judge-test", tags=["review"])
    def review_judge_test() -> list[dict[str, Any]]:
        hand = load_hand_marks(files.judge_test())
        return [{"n": n, **where(item), "done": item in hand}
                for n, item in enumerate(load_sample(files.judge_test()))]

    @api.get("/review/judge-test/{n}", tags=["review"])
    def review_judge_item(n: int) -> dict[str, Any]:
        """Blind: the answer, the points the judge saw and the facts the answer used; never the judge's ticks or
        scores, and never the system that answered."""
        item = item_at(n)
        domain, _, _, qid = files.item_parts(item)
        path = files.item_file(item, ".answer.json")
        if not path.is_file():
            raise NotFound(f"judge-test item {n}: no saved answer")
        rec = load_answer(path)
        try:
            spec = files.spec(domain)
            question: str | None = files.question(files.questions(domain, spec), qid).question
        except (NotFound, Conflict):
            question = None
        used, cut = used_facts(rec)
        return {"n": n, **where(item), "question": question, "answer": rec.text, "points": judged_points(n, item),
                "facts": [{"n": i, "paper": f.paper, "kind": f.kind, "quote": f.quote} for i, f in enumerate(used, 1)],
                "facts_cut": cut, "marked": load_hand_marks(files.judge_test()).get(item)}

    @api.put("/review/judge-test/{n}", tags=["review"])
    def review_hand_mark(n: int, req: HandMarkIn) -> dict[str, Any]:
        with _WRITE:
            item = item_at(n)
            ids = [p["id"] for p in judged_points(n, item)]
            unknown = sorted(set(req.points) - set(ids))
            missing = [p for p in ids if p not in req.points]
            if unknown or missing:
                raise BadRequest("; ".join([*(f"unknown point {p}" for p in unknown),
                                            *(f"point {p} is not marked" for p in missing)]))
            save_hand_mark(files.judge_test(), item, {p: req.points[p] for p in ids}, req.faithful, settings.user,
                           now())
            return load_hand_marks(files.judge_test())[item]

    return api

