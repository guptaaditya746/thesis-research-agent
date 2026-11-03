"""DSPy steps: every new model step is a `dspy.Signature` run through `Step` on the recorded gateway.

`configure(lm)` sets the run's `RecordedLM` once. `Step(signature, name)(**inputs)` runs the signature with the
JSON adapter (typed outputs). Instructions come from `evidence/steps/tuned/<name>.json` (`{"instructions": ...}`,
written by the DSPy tuning step) when that file exists, else from the signature's docstring."""
from __future__ import annotations

import json
from pathlib import Path

import dspy
from dspy.utils.exceptions import AdapterParseError

from modelcall.dspy_lm import RecordedLM

TUNED_DIR = Path(__file__).parent / "tuned"
_LM: RecordedLM | None = None


def configure(lm: RecordedLM) -> None:
    """Set the recorded model every `Step` runs on."""
    global _LM
    _LM = lm


class Step:
    ATTEMPTS = 3

    def __init__(self, signature: type[dspy.Signature], name: str) -> None:
        self.signature = signature
        self.name = name
        path = TUNED_DIR / f"{name}.json"
        self._instructions = (json.loads(path.read_text(encoding="utf-8"))["instructions"] if path.exists()
                              else signature.instructions)

    def instructions(self) -> str:
        return self._instructions

    def __call__(self, **inputs) -> dspy.Prediction:
        if _LM is None:
            raise RuntimeError("no model for the step: call evidence.steps.configure(RecordedLM(...)) first")
        predict = dspy.Predict(self.signature.with_instructions(self._instructions))
        # An unparseable reply stays recorded under attempt 0; the retry is a new recorded call (attempt 1, 2).
        for attempt in range(self.ATTEMPTS):
            try:
                with dspy.context(lm=_LM, adapter=dspy.JSONAdapter()):
                    return predict(config={"attempt": attempt}, **inputs)
            except AdapterParseError:
                if attempt == self.ATTEMPTS - 1:
                    raise
        raise AssertionError("unreachable")
