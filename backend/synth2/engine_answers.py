"""The engine's answers in synth2's answer form, keyed by the corpus id: each run folder's answer.json `conclusion`
(a run of a protocol with subsets: a verdict, the condition it depends on and a direction per side), else its
label."""
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


SIDE = {"supports": "helps", "contradicts": "hurts", "neutral": "no_effect"}


def _own(answer: dict, key: str) -> object:
    """An effect run keeps `key` at the top of answer.json; a plan run keeps the kind's answer under `synthesis`."""
    if key in answer:
        return answer[key]
    synthesis = answer.get("synthesis")
    return synthesis.get(key) if isinstance(synthesis, dict) else None


def _label(answer: dict) -> object:
    return _own(answer, "label")


def answer_form(answer: dict) -> dict:
    """synth2 answer for an answer.json. With a `conclusion` (evidence/synthesis.py, Subsets; a baseline's mapped
    answer has the same shape): `depends` keeps its condition and gives each side helps | hurts | no_effect; any
    other verdict is the label's word; `untested` as given. Without one: `to_answer` of the label. A conclusion
    that is not of that shape is a ValueError."""
    conclusion = _own(answer, "conclusion")
    if conclusion is None:
        return to_answer(_label(answer))   # type: ignore[arg-type]
    try:
        verdict, untested = conclusion["verdict"], sorted(conclusion.get("untested") or [])
        if verdict == "depends":
            return {"verdict": "depends", "condition": conclusion["condition"],
                    "sides": {level: SIDE[word] for level, word in conclusion["sides"].items()}, "untested": untested}
        return {**to_answer(verdict), "untested": untested}
    except (KeyError, TypeError, AttributeError) as err:
        raise ValueError(f"the conclusion is not of the engine's shape: {err!r}") from err


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
            answer = json.loads(answer_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError, TypeError) as err:
            raise ValueError(f"{run_file.parent}: cannot read the run: {err!r}") from err
        if not isinstance(corpus_id, str) or not corpus_id:
            raise ValueError(f"{run_file}: no corpus_id")
        if corpus_id in answers:
            raise ValueError(f"corpus {corpus_id} has more than one run under {runs}")
        try:
            answers[corpus_id] = answer_form(answer)
        except ValueError as err:
            raise ValueError(f"{run_file.parent}: {err}") from err
    if not answers:
        raise ValueError(f"no run (run.json with answer.json) under {runs}")
    return answers
