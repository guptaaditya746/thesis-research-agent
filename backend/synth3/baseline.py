"""The plain RAG baseline (`evaluate rag-baseline`) on every question of a folder, saved in the judge's shape.

Sub-questions are never sent: they are planning input for the system (plan 4). The baseline pulls no per-paper
facts, so score A is n/a for it. The mapping call's label stays in the raw `answer.json` and is not scored."""
from __future__ import annotations

from pathlib import Path

from evaluation.baselines.rag import rag_baseline
from jsonio import write_json_atomic
from modelcall import JsonlCache, ModelCallError, redact
from synth3.answers import RAG_SYSTEM, answer_path, from_rag_answer, load_answer, save_answer
from synth3.questions import QuestionSet, question_sha256
from synth3.sheetfacts import Folder

BASELINE = RAG_SYSTEM   # "rag-baseline"


def _answered(results: Path, folder: Folder, qid: str, sha: str) -> bool:
    path = answer_path(results, folder.spec.domain, folder.seed, BASELINE, qid)
    try:
        return load_answer(path).question_sha256 == sha
    except (OSError, ValueError):
        return False


def baseline_folder(folder: Folder, qs: QuestionSet, model, model_id: str, cache: JsonlCache,
                    results: Path) -> dict:
    """Run the RAG baseline (global retrieval, k 8, the command's defaults) on every question of `qs`.

    A record with the same `question_sha256` is skipped. A `ModelCallError` or `ValueError` for one question
    is listed with its redacted reason and the others go on.
    Returns {"answered", "skipped", "failed": {qid: reason}}."""
    out: dict = {"answered": 0, "skipped": 0, "failed": {}}
    domain = folder.spec.domain
    for q in qs.questions:
        sha = question_sha256(q)
        if _answered(results, folder, q.id, sha):
            out["skipped"] += 1
            continue
        raw = results / domain / f"s{folder.seed}" / BASELINE / q.id / "answer.json"
        try:
            answer = rag_baseline(folder.path, model=model, model_id=model_id, question=q.question, cache=cache)
            rec = from_rag_answer(answer, folder, q, str(raw))
        except ModelCallError as err:
            out["failed"][q.id] = f"{q.id} s{folder.seed}: {err.reason}"
            continue
        except ValueError as err:
            out["failed"][q.id] = f"{q.id} s{folder.seed}: {redact(str(err))[:1000]}"
            continue
        write_json_atomic(raw, answer)
        save_answer(results, rec)
        out["answered"] += 1
    return out
