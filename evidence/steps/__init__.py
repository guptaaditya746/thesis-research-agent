"""DSPy steps: every new model step is a `dspy.Signature` run through `Step` on the recorded gateway.

`configure(lm)` sets the run's `RecordedLM` once. `Step(signature, name)(**inputs)` runs the signature with the
JSON adapter (typed outputs). Instructions come from `evidence/steps/tuned/<name>.json` (`{"instructions": ...}`,
written by the DSPy tuning step) when that file exists, else from the signature's docstring."""
from __future__ import annotations

import json
from pathlib import Path

import dspy

from modelcall.dspy_lm import RecordedLM

TUNED_DIR = Path(__file__).parent / "tuned"
_LM: RecordedLM | None = None


def configure(lm: RecordedLM) -> None:
    """Set the recorded model every `Step` runs on."""
    global _LM
    _LM = lm


class Step:
    def __init__(self, signature: type[dspy.Signature], name: str) -> None:
        self.signature = signature
        self.name = name

    def instructions(self) -> str:
        path = TUNED_DIR / f"{self.name}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["instructions"]
        return self.signature.instructions

    def __call__(self, **inputs) -> dspy.Prediction:
        if _LM is None:
            raise RuntimeError("no model for the step: call evidence.steps.configure(RecordedLM(...)) first")
        predict = dspy.Predict(self.signature.with_instructions(self.instructions()))
        with dspy.context(lm=_LM, adapter=dspy.JSONAdapter()):
            return predict(**inputs)
