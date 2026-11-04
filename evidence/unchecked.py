"""What the plan run's per-item stages could not read (final review C3): one failed model call skips one item, never
the run.

A stage that asks the model once per item (a claim sentence, a citing sentence, a paper's experiment map) catches the
errors of that one call (`ITEM_ERRORS`: the recorded call failed, the reply did not parse after the step's attempts,
or it did not validate), skips the item and notes it here as "unchecked: <where>: <reason>". Nothing is kept about a
failure but this note: the failed model call is in the record cache as an error, an unparseable reply is marked bad
there (CallCache.mark_bad), so a replay fails it the same way and `--retry-errors` asks it again; no stage remembers
it. The run-level claim grouping (planrun.group_claims) notes its failure under "groups" (document id "run"). The `stage_report` stage (after_run) writes the notes of
the run as stage_report.json: {stage: {document id: [note, ...]}}, every stage of `STAGES` present.

A replay's NotRecorded (a call the record does not hold) is not an item error: it still refuses the replay."""
from __future__ import annotations

import threading
from typing import Any

from dspy.utils.exceptions import AdapterParseError
from pydantic import ValidationError

import modelcall

from .stages import StageCallError

__all__ = ["GROUPS", "ITEM_ERRORS", "NAME", "RUN", "STAGES", "note", "reason", "report"]

NAME = "stage_report"
GROUPS, RUN = "groups", "run"   # the claim grouping: one call per run, noted under document id "run"
STAGES = ("claims", "experiments", "links", GROUPS)
ITEM_ERRORS: tuple[type[BaseException], ...] = (StageCallError, AdapterParseError, ValidationError)
_lock = threading.Lock()
# run folder -> {stage: {document id: [note]}}; a later pass over a document (the warm pass) replaces its notes
_STORE: dict[str, dict[str, dict[str, list[str]]]] = {}


def reason(exc: BaseException) -> str:
    """The short, redacted reason of an item error: its type and the first line of its text (library wording past the
    first line, such as pydantic's docs URL, would tie the report to one library version)."""
    first = next((ln.strip() for ln in str(exc).splitlines() if ln.strip()), "")
    return modelcall.redact(f"{type(exc).__name__}: {first}")[:160]


def note(ctx: Any, stage: str, doc_id: str, notes: list[str]) -> None:
    """Set the notes of `stage` for one document of the run `ctx` writes (an empty list clears them). A ctx without
    a run folder (a test's stand-in) keeps none."""
    if getattr(ctx, "run_dir", None) is None:
        return
    with _lock:
        _STORE.setdefault(str(ctx.run_dir), {}).setdefault(stage, {})[doc_id] = list(notes)


def report(run: Any, ctx: Any) -> dict[str, Any]:
    """The `stage_report` stage (after_run): the run's notes, every stage of STAGES present, documents sorted."""
    with _lock:
        done = _STORE.pop(str(getattr(ctx, "run_dir", None)), {})
    return {stage: {doc: notes for doc, notes in sorted(done.get(stage, {}).items()) if notes} for stage in STAGES}
