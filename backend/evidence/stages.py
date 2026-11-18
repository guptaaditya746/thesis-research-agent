"""The four seams where a later feature plugs into the engine without editing it. Final signatures (`ctx` last):

    before_extract(doc: DocState, ctx: StageContext) -> None                    once per document, before the screen
    after_type(doc: DocState, etype: str, merged: list[Item], ctx: StageContext) -> list[Item]
                                                                                after each merge of a type; returns the
                                                                                (possibly filtered or changed) items
    after_document(doc: DocState, ctx: StageContext) -> list[Item]              after the funnel; returns extra items
    after_run(run: RunDir, ctx: StageContext) -> dict[str, Any]                 after the answer; each result is written
                                                                                as `<name>.json` and hashed into run.json

`StageContext` (frozen): `plan` (the confirmed Plan or None), `calls` (the run's recorded CallCache: ask models through
it so calls are cached and replayable), `mode` (run / replay / reexec), `provider` (the model provider or None) and
`run_dir` (the folder being written), `model` (the run's default model alias), `source_dir` (in a replay or reexec, the
folder of the recorded run; `record_dir` is where a stage's own records are read: OpenAlex answers), `texts()` (paper
id -> text of the run's corpus) and `extra` (the run's own stage set, below), and two helpers for models:
`ctx.ask(instructions, user_prompt, *, output_type, purpose)` is one recorded structured call through exactly the
engine's own path (cache, calls.jsonl row, calls/<id>.json, `stage_call` event, cost and failed-call counts; raises
StageCallError on a failure) and `ctx.dspy_lm(purpose)` returns a RecordedLM whose calls go through `ask`. Never call
the provider or `calls` directly from a stage.

Stage sets. Besides the process-wide registry, one run can carry its own stages (`stage_set`; the engine puts a plan
run's set in `ctx.extra`): they run after the registered ones at each seam, are recorded in run.json `stages` like
them, and never touch the registry, so a plan run in one thread (a web request) adds no stage to a protocol run in
another.

Rules. Stages run in registration order. With none registered every call below is a no-op and a run is byte-identical
to one made before the seams existed. `after_type` runs after EVERY merge of a type (each funnel round), so it must be
idempotent; dropping an item there counts as a gap in `gaps` mode and can trigger escalation. In a model run with workers > 1
the warm pass runs before_extract, after_type and after_document once more per paper (its outputs are
thrown away), so they must be safe to run twice. An exception in a stage fails the run, except in `after_run`, where
it is written as {"failed": "<reason>"} to `<name>.json` and the run continues. run.json lists the registered stage
names under `stages` (only when there are any) and a replay is refused when its registered set differs. A stage name
matches [a-z0-9_-]+ and is not the stem of a file the run folder already holds. Tests use `registered()` so
registrations (including those made when a module is imported) are restored afterwards.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import modelcall
from pydantic import BaseModel
from modelcall.call import PlainTextReply as Reply

if TYPE_CHECKING:
    from .calls import CallCache
    from .contract import Item
    from .engine import DocState
    from .plan import Plan
    from .recording import Provider
    from .rundir import RunDir

__all__ = ["After", "Reply", "StageCallError", "StageContext", "StageSet", "StagesMismatch", "after_document", "after_run",
           "after_type", "before_extract", "check_recorded", "clear", "names", "register", "registered", "stage_set"]

After = Literal["before_extract", "after_type", "after_document", "after_run"]
_AT: tuple[str, ...] = ("before_extract", "after_type", "after_document", "after_run")
_registry: dict[str, list[tuple[str, Callable[..., Any]]]] = {at: [] for at in _AT}
_NAME = re.compile(r"[a-z0-9_-]+")
StageSet = Mapping[str, list[tuple[str, Callable[..., Any]]]]   # seam -> [(name, fn)], one run's own stages


class StageCallError(RuntimeError):
    """A model call a stage made failed (it is recorded as a failed call)."""


class StagesMismatch(RuntimeError):
    """A replay runs with other stages than the recorded run had."""


@dataclass(frozen=True)
class StageContext:
    plan: Plan | None
    calls: CallCache | None
    mode: str
    provider: Provider | None
    run_dir: Path
    _ask: Callable[..., Any]       # the engine's stage_ask (Execution.stage_ask)
    model: str                     # the run's default model alias for `ask`
    source_dir: Path | None = None                 # replay / reexec: the recorded run's folder
    extra: StageSet = field(default_factory=dict)  # the run's own stages (a plan run's), after the registered ones
    _texts: Callable[[], Mapping[str, str]] | None = None   # the corpus texts (lazy)
    _bad_reply: Callable[..., None] | None = None   # the engine's stage_bad_reply: a recorded reply did not parse
    corpus: Path | None = None                      # the run's corpus folder (a stage that reads papers by id)

    def texts(self) -> Mapping[str, str]:
        """{paper id: text} of every paper of the run's corpus (empty when the engine gave none)."""
        return self._texts() if self._texts is not None else {}

    @property
    def record_dir(self) -> Path:
        """Where a stage's own records live: the recorded run's folder in a replay, else the folder being written."""
        return self.source_dir if self.mode == "replay" and self.source_dir is not None else self.run_dir

    def ask(self, instructions: str, user_prompt: str, *, output_type: type[BaseModel], purpose: str,
            model: str | None = None, temperature: float = 0.0, seed: int = 0, max_tokens: int = 2048,
            request_extra: dict[str, Any] | None = None) -> Any:
        """One recorded model call: the cache, the calls.jsonl row, calls/<id>.json, a `stage_call` event, the cost and
        failed-call counts, exactly as the engine's own calls. Returns an `output_type`; raises StageCallError when the
        model call failed (the failure is recorded). `purpose` names the stage's question (part of the cache key)."""
        return self._ask(instructions, user_prompt, output_type, purpose, model or self.model,
                         {"temperature": temperature, "seed": seed, "max_tokens": max_tokens}, request_extra)

    def dspy_lm(self, purpose: str, model: str | None = None) -> Any:
        """A `modelcall.dspy_lm.RecordedLM` whose every call goes through `ask` (so DSPy steps in a stage are recorded
        and replayable too). DSPy's plain-text reply is stored as the text field of a `Reply` model."""
        from modelcall.dspy_lm import RecordedLM
        alias = model or self.model
        bad = self._bad_reply

        def on_bad(text: str, *, attempt: int, settings: Any) -> None:   # the same request `ask` recorded
            if bad is not None:
                bad("", text, Reply, purpose, alias, {"temperature": 0.0, "seed": 0, "max_tokens": 2048},
                    {"attempt": attempt, "settings": settings})
        # the retry number and DSPy's call settings are part of the request, so a retry (same messages, attempt 1) is a
        # new recorded call and never gets the bad reply of attempt 0 back
        return RecordedLM(alias, lambda text, *, attempt, settings: self.ask(
            "", text, output_type=Reply, purpose=purpose, model=alias,
            request_extra={"attempt": attempt, "settings": settings}).text, with_call=True, on_bad=on_bad)


def _reserved() -> frozenset[str]:
    """The stems of the files and folders a run folder holds (derived from rundir/seal), which `<name>.json` of a
    stage must never overwrite."""
    from . import rundir, seal
    files = [v for k, v in vars(rundir).items() if k.endswith(("_FILE", "_DIR")) and isinstance(v, str)]
    files.append(seal.MANIFEST_FILE)
    return frozenset(f.split(".")[0] for f in files)


def _check(name: str, at: str, taken: Mapping[str, list[tuple[str, Any]]]) -> None:
    if at not in _registry:
        raise ValueError(f"unknown seam {at!r}: one of {', '.join(_AT)}")
    if not _NAME.fullmatch(name):
        raise ValueError(f"stage name {name!r} must match [a-z0-9_-]+")
    if name in _reserved():
        raise ValueError(f"stage name {name!r} is a file the run folder already holds")
    if any(n == name for n, _ in taken.get(at, [])):
        raise ValueError(f"a stage named {name!r} is already registered at {at}")


def register(name: str, at: After, fn: Callable[..., Any]) -> None:
    """Add `fn` (called as the seam `at` says above) under `name`; `after_run` writes its result to `<name>.json`."""
    _check(name, at, _registry)
    _registry[at].append((name, fn))


def stage_set(entries: list[tuple[str, After, Callable[..., Any]]]) -> dict[str, list[tuple[str, Callable[..., Any]]]]:
    """One run's own stages from (name, seam, fn) in order, checked like `register` and against the registry."""
    out: dict[str, list[tuple[str, Callable[..., Any]]]] = {}
    for name, at, fn in entries:
        _check(name, at, out)
        _check(name, at, _registry)
        out.setdefault(at, []).append((name, fn))
    return out


def _all(at: str, ctx: StageContext | None) -> list[tuple[str, Callable[..., Any]]]:
    return list(_registry[at]) + (list(ctx.extra.get(at, [])) if ctx is not None else [])


def clear() -> None:
    """Remove every registered stage."""
    for stages in _registry.values():
        stages.clear()


@contextmanager
def registered(*, empty: bool = True) -> Iterator[None]:
    """For tests: keep a snapshot of the registry (import-time registrations included) and put it back on exit;
    `empty=True` runs the body with no stages registered."""
    snapshot = {at: list(v) for at, v in _registry.items()}
    if empty:
        clear()
    try:
        yield
    finally:
        for at, v in snapshot.items():
            _registry[at][:] = v


def names(extra: StageSet | None = None) -> dict[str, list[str]]:
    """{seam: [stage names]} of the seams that have any, in registration order, then the run's own set `extra`
    (what run.json records)."""
    out = {at: [n for n, _ in _registry[at]] + [n for n, _ in (extra or {}).get(at, [])] for at in _AT}
    return {at: v for at, v in out.items() if v}


def check_recorded(recorded: dict[str, list[str]] | None, extra: StageSet | None = None) -> None:
    """Raise StagesMismatch when the registered stages (and the run's own set) differ from the `stages` of a recorded
    run."""
    now, then = names(extra), recorded or {}
    if now != then:
        raise StagesMismatch(f"the run was made with stages {then or 'none'}, but {now or 'none'} are registered: "
                             "import the modules that register them (settings imports) before replaying")


def before_extract(doc: DocState, ctx: StageContext) -> None:
    for _, fn in _all("before_extract", ctx):
        fn(doc, ctx)


def after_type(doc: DocState, etype: str, merged: list[Item], ctx: StageContext) -> list[Item]:
    for _, fn in _all("after_type", ctx):
        merged = fn(doc, etype, merged, ctx)
    return merged


def after_document(doc: DocState, ctx: StageContext) -> list[Item]:
    extra: list[Item] = []
    for _, fn in _all("after_document", ctx):
        extra.extend(fn(doc, ctx))
    return extra


def after_run(run: RunDir, ctx: StageContext) -> dict[str, Any]:
    """{name: result} in registration order; the engine writes and hashes each. A stage that raises gives
    {"failed": reason} and the others still run."""
    out: dict[str, Any] = {}
    for name, fn in _all("after_run", ctx):
        try:
            out[name] = fn(run, ctx)
        except Exception as exc:
            out[name] = {"failed": modelcall.redact(f"{type(exc).__name__}: {exc}")[:300]}
    return out


def gateway_ask(alias: str):
    """`ask(text) -> reply text` for a `RecordedLM`: one plain call of `alias` through the gateway (no cache here: the
    RecordedLM records it)."""
    from modelcall import Prompt, ask_sync, openai_model

    def ask(text: str) -> str:
        return ask_sync(Prompt.inline("", Reply), text, model=openai_model(alias)).output.text
    return ask
