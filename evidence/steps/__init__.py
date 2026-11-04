"""DSPy steps: every new model step is a `dspy.Signature` run through `Step` on the recorded gateway.

The model is chosen per call, never shared between threads: `Step(signature, name)(lm=<RecordedLM>, **inputs)`, else
the model of the innermost `with using(lm):` in this thread, else the process default `configure(lm)` (one-thread
tools and tests). So two papers of the warm pass, or two web requests, each record on their own model with no lock.
A step runs the signature with the JSON adapter (typed outputs). Instructions come from `evidence/steps/tuned/<name>.json` (`{"instructions": ...}`,
written by the DSPy tuning step) when that file exists, else from the signature's docstring."""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import dspy
from dspy.utils.exceptions import AdapterParseError

from modelcall.dspy_lm import RecordedLM

TUNED_DIR = Path(__file__).parent / "tuned"
_LM: RecordedLM | None = None
_local = threading.local()     # this thread's stack of `using` models


def configure(lm: RecordedLM) -> None:
    """Set the process default model: what a `Step` runs on when neither `lm=` nor `using` gives one."""
    global _LM
    _LM = lm


@contextmanager
def using(lm: RecordedLM) -> Iterator[RecordedLM]:
    """Run the steps called inside on `lm`, in this thread only (other threads keep theirs); nests and restores."""
    stack = _local.__dict__.setdefault("stack", [])
    stack.append(lm)
    try:
        yield lm
    finally:
        stack.pop()


def current() -> RecordedLM | None:
    """The model a step called now in this thread runs on (without `lm=`)."""
    stack = _local.__dict__.get("stack")
    return stack[-1] if stack else _LM


def tuned(name: str) -> tuple[str, str] | None:
    """(instructions, sha256 of the file's bytes) of the tuned step `name` as `TUNED_DIR` holds it now; None when it
    has no file for it."""
    path = Path(TUNED_DIR) / f"{name}.json"
    if not path.is_file():
        return None
    data = path.read_bytes()
    return json.loads(data.decode("utf-8"))["instructions"], hashlib.sha256(data).hexdigest()


def tuned_sha256(steps: list[Step | str]) -> dict[str, str]:
    """{name: sha256} of the tuned instructions each of `steps` runs on: a `Step` instance by what it loaded when it
    was made (a module-level step keeps what it read at import), a name by the file now (a step made per call reads
    it then); {} when none is tuned."""
    out: dict[str, str] = {}
    for s in steps:
        sha = s.tuned_sha256 if isinstance(s, Step) else (t[1] if (t := tuned(s)) is not None else None)
        if sha:
            out[s.name if isinstance(s, Step) else s] = sha
    return dict(sorted(out.items()))


class Step:
    ATTEMPTS = 3

    def __init__(self, signature: type[dspy.Signature], name: str) -> None:
        self.signature = signature
        self.name = name
        loaded = tuned(name)
        self._instructions = loaded[0] if loaded is not None else signature.instructions
        self.tuned_sha256 = loaded[1] if loaded is not None else None   # the tuned file this step runs on

    def instructions(self) -> str:
        return self._instructions

    def __call__(self, *, lm: RecordedLM | None = None, **inputs) -> dspy.Prediction:
        lm = lm if lm is not None else current()
        if lm is None:
            raise RuntimeError("no model for the step: pass lm=, use `with evidence.steps.using(lm):` or call "
                               "evidence.steps.configure(RecordedLM(...)) first")
        predict = dspy.Predict(self.signature.with_instructions(self._instructions))
        # An unparseable reply stays recorded under attempt 0; the retry is a new recorded call (attempt 1, 2).
        for attempt in range(self.ATTEMPTS):
            try:
                with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
                    return predict(config={"attempt": attempt}, **inputs)
            except AdapterParseError:
                mark = getattr(lm, "bad_reply", None)
                if callable(mark):   # the recorded reply did not parse: a rerun with retry_errors asks it again
                    mark()
                if attempt == self.ATTEMPTS - 1:
                    raise
        raise AssertionError("unreachable")
