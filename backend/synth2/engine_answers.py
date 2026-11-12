"""The engine's answers in synth2's answer form: each run folder's answer.json label, keyed by the corpus id."""
from __future__ import annotations

import json
from pathlib import Path

VERDICT = {"supported": "helps", "refuted": "hurts", "no_effect": "no_effect", "mixed": "mixed",
           "insufficient": "insufficient"}


def to_answer(label: str) -> dict:
    """synth2 answer for an engine label; no condition, no sides, nothing untested. Another label is a ValueError."""
    if label not in VERDICT:
        raise ValueError(f"unknown engine label '{label}'; known: {', '.join(VERDICT)}")
    return {"verdict": VERDICT[label], "condition": None, "sides": {}, "untested": []}


def _label(answer: dict) -> object:
    """An effect run keeps its label at the top of answer.json; a plan run keeps the kind's answer under `synthesis`."""
    if "label" in answer:
        return answer["label"]
    synthesis = answer.get("synthesis")
    return synthesis.get("label") if isinstance(synthesis, dict) else None


def collect(runs: Path) -> dict[str, dict]:
    """{corpus id: synth2 answer} over every `*/run.json` with an answer.json beside it. A corpus id seen twice, or
    no run at all, is a ValueError."""
    answers: dict[str, dict] = {}
    for run_file in sorted(runs.glob("*/run.json")):
        answer_file = run_file.parent / "answer.json"
        if not answer_file.is_file():
            continue
        try:
            corpus_id = json.loads(run_file.read_text(encoding="utf-8"))["corpus_id"]
            label = _label(json.loads(answer_file.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError) as err:
            raise ValueError(f"{run_file.parent}: cannot read the run: {err!r}") from err
        if not isinstance(corpus_id, str) or not corpus_id:
            raise ValueError(f"{run_file}: no corpus_id")
        if corpus_id in answers:
            raise ValueError(f"corpus {corpus_id} has more than one run under {runs}")
        try:
            answers[corpus_id] = to_answer(label)
        except ValueError as err:
            raise ValueError(f"{run_file.parent}: {err}") from err
    if not answers:
        raise ValueError(f"no run (run.json with answer.json) under {runs}")
    return answers
