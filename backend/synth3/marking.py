"""`synth3 judge`: three separate scores (A, B, C) for every saved answer, written beside it as `<qid>.marks.json`.

The judge runs on drafted sheets too (the sheet check is a sample); each marks file records the sheet's `status`
so the report can count marks made against unchecked sheets. A failed model call leaves that score pending, the
marks file is still written and the next answer follows. `sheet.points` keeps the points the C judge saw
(`[{id, text}]` in sheet order), so the judge test shows what was ticked even after the sheet is edited. An
existing marks file is kept (no calls) only when the answer, the sheet and the three prompts are the ones it was
made from and nothing in it is pending."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import modelcall
from jsonio import canonical_bytes, sha256_hex, write_json_atomic
from modelcall import JsonlCache, load_prompt
from synth3.answers import AnswerRecord, item_id, load_answer
from synth3.judge import (PROMPT_A, PROMPT_B, PROMPT_C, ClaimChecks, PaperMarks, Ticks, score_a, score_b, score_c)
from synth3.questions import Question, QuestionSet, question_sha256
from synth3.sheetfacts import Folder, check_spec, load_folder
from synth3.sheets import Sheet, load_sheet, sheet_sha256, stale
from synth3.spec import DomainSpec


def marks_path(results: Path, domain: str, seed: int, system: str, qid: str) -> Path:
    return results / domain / f"s{seed}" / system / f"{qid}.marks.json"


def prompt_shas() -> dict[str, str]:
    """The sha256 of the three judge prompts as they are now (they exist even when no call is made)."""
    return {"a": load_prompt(PROMPT_A, PaperMarks).sha256, "b": load_prompt(PROMPT_B, ClaimChecks).sha256,
            "c": load_prompt(PROMPT_C, Ticks).sha256}


def answer_sha256(rec: AnswerRecord) -> str:
    return sha256_hex(canonical_bytes(rec.model_dump()))


def why_not(folder: Folder, q: Question, sheet: Sheet | None, rec: AnswerRecord) -> str | None:
    """Why this answer is not judged, or None. The stale check comes before anything else reads the sheet."""
    if sheet is None:
        return "no sheet"
    reason = stale(sheet, q, folder)
    if reason:
        return reason
    if rec.question_sha256 != question_sha256(q):
        return "the answer is to an older version of the question"
    if rec.corpus_id != folder.corpus_id:
        return "the answer is from another folder"
    return None


def is_pending(marks: dict) -> bool:
    """Any of A, B, C pending: A with papers left over, B or C with `status` pending."""
    a = marks.get("A")
    return bool((a and a["pending_papers"]) or marks["B"]["status"] == "pending"
                or marks["C"]["status"] == "pending")


def judge_answer(folder: Folder, q: Question, sheet: Sheet, rec: AnswerRecord, model: Any,
                 cache: JsonlCache, *, fresh: str | None = None) -> dict:
    """The marks of one answer. A is None for a record with no per-paper facts (the baseline); `judge.prompts`
    always holds the three prompt hashes."""
    measures = folder.spec.measures
    a = score_a(folder, q, rec, model, cache, fresh=fresh)
    b = score_b(q, rec, model, cache, measures=measures, fresh=fresh)
    c = score_c(q, sheet, rec, model, cache, measures=measures, fresh=fresh)
    served = list(dict.fromkeys(s for part in (a, b, c) if part for s in part["served_models"]))
    return {"item": item_id(rec), "question_id": rec.question_id, "seed": rec.seed, "system": rec.system,
            "corpus_id": rec.corpus_id, "answer_sha256": answer_sha256(rec),
            "sheet": {"sha256": sheet_sha256(sheet), "status": sheet.status, "cant_tell": sheet.cant_tell,
                      "points": [{"id": p.id, "text": p.text} for p in sheet.points]},
            "A": a, "B": b, "C": c,
            "judge": {"model": modelcall.model_identity([model]), "served_models": served, "prompts": prompt_shas()},
            "calls": sum(part["calls"] for part in (a, b, c) if part)}


def _kept(path: Path, rec: AnswerRecord, sheet: Sheet) -> bool:
    """True when the marks file at `path` was made from this answer, this sheet and today's three prompts and has
    nothing pending. A file that cannot be read is not kept."""
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        return (old["answer_sha256"] == answer_sha256(rec) and old["sheet"]["sha256"] == sheet_sha256(sheet)
                and old["judge"]["prompts"] == prompt_shas() and not is_pending(old))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _was_pending(path: Path) -> bool:
    """True when a marks file is there and has something pending."""
    try:
        return is_pending(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _saved(results: Path, domain: str, seed: int, systems: list[str] | None) -> list[AnswerRecord]:
    recs = [load_answer(p) for p in (results / domain / f"s{seed}").glob("*/*.answer.json")]
    recs = [r for r in recs if systems is None or r.system in systems]
    return sorted(recs, key=lambda r: (r.system, r.question_id))


def judge_folder(folder: Folder, systems: list[str] | None, qs: QuestionSet, model: Any, cache: JsonlCache,
                 sheets_root: Path, results: Path) -> dict:
    """Judge every saved answer of one folder; `{"judged", "kept", "skipped": {item: reason}, "pending": [item]}`."""
    domain, seed = folder.spec.domain, folder.seed
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out: dict = {"judged": 0, "kept": 0, "skipped": {}, "pending": []}
    for rec in _saved(results, domain, seed, systems):
        item = item_id(rec)
        try:
            q = qs.get(rec.question_id)
        except KeyError:
            out["skipped"][item] = "the question is not in the question file"
            continue
        sheet = load_sheet(sheets_root, domain, seed, q.id)
        reason = why_not(folder, q, sheet, rec)
        if reason:
            out["skipped"][item] = reason
            continue
        path = marks_path(results, domain, seed, rec.system, q.id)
        if _kept(path, rec, sheet):
            out["kept"] += 1
            continue
        fresh = now if _was_pending(path) else None   # the cached bad replies would give the same pending again
        marks = judge_answer(folder, q, sheet, rec, model, cache, fresh=fresh)
        write_json_atomic(path, marks)
        out["judged"] += 1
        if is_pending(marks):
            out["pending"].append(item)
    return out


def judge_domain(domain: str, folders: Path, seeds: list[int], systems: list[str] | None, spec: DomainSpec,
                 qs: QuestionSet, model: Any, cache: JsonlCache, sheets_root: Path, results: Path) -> dict:
    """Every saved answer of those seeds and systems, one folder after another (`folders/s<seed>`)."""
    total: dict = {"judged": 0, "kept": 0, "skipped": {}, "pending": []}
    for seed in seeds:
        folder = load_folder(folders / f"s{seed}")
        check_spec(folder, spec)
        if folder.spec.domain != domain:
            raise ValueError(f"s{seed}: the folder is of domain {folder.spec.domain!r}, not {domain!r}")
        part = judge_folder(folder, systems, qs, model, cache, sheets_root, results)
        total["judged"] += part["judged"]
        total["kept"] += part["kept"]
        total["skipped"] |= part["skipped"]
        total["pending"] += part["pending"]
    return total
