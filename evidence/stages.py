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
`run_dir` (the folder being written).

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
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .calls import CallCache
    from .contract import Item
    from .engine import DocState
    from .plan import Plan
    from .recording import Provider
    from .rundir import RunDir

__all__ = ["After", "StageContext", "StagesMismatch", "after_document", "after_run", "after_type", "before_extract",
           "check_recorded", "clear", "names", "register", "registered"]

After = Literal["before_extract", "after_type", "after_document", "after_run"]
_AT: tuple[str, ...] = ("before_extract", "after_type", "after_document", "after_run")
_registry: dict[str, list[tuple[str, Callable[..., Any]]]] = {at: [] for at in _AT}
_NAME = re.compile(r"[a-z0-9_-]+")


class StagesMismatch(RuntimeError):
    """A replay runs with other stages than the recorded run had."""


@dataclass(frozen=True)
class StageContext:
    plan: Plan | None
    calls: CallCache | None
    mode: str
    provider: Provider | None
    run_dir: Path


def _reserved() -> frozenset[str]:
    """The stems of the files and folders a run folder holds (derived from rundir/seal), which `<name>.json` of a
    stage must never overwrite."""
    from . import rundir, seal
    files = [v for k, v in vars(rundir).items() if k.endswith(("_FILE", "_DIR")) and isinstance(v, str)]
    files += [seal.MANIFEST_FILE, "plan.json"]
    return frozenset(f.split(".")[0] for f in files)


def register(name: str, at: After, fn: Callable[..., Any]) -> None:
    """Add `fn` (called as the seam `at` says above) under `name`; `after_run` writes its result to `<name>.json`."""
    if at not in _registry:
        raise ValueError(f"unknown seam {at!r}: one of {', '.join(_AT)}")
    if not _NAME.fullmatch(name):
        raise ValueError(f"stage name {name!r} must match [a-z0-9_-]+")
    if name in _reserved():
        raise ValueError(f"stage name {name!r} is a file the run folder already holds")
    if any(n == name for n, _ in _registry[at]):
        raise ValueError(f"a stage named {name!r} is already registered at {at}")
    _registry[at].append((name, fn))


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


def names() -> dict[str, list[str]]:
    """{seam: [stage names]} of the seams that have any, in registration order (what run.json records)."""
    return {at: [n for n, _ in v] for at, v in _registry.items() if v}


def check_recorded(recorded: dict[str, list[str]] | None) -> None:
    """Raise StagesMismatch when the registered stages differ from the `stages` of a recorded run."""
    now, then = names(), recorded or {}
    if now != then:
        raise StagesMismatch(f"the run was made with stages {then or 'none'}, but {now or 'none'} are registered: "
                             "import the modules that register them (settings imports) before replaying")


def before_extract(doc: DocState, ctx: StageContext) -> None:
    for _, fn in list(_registry["before_extract"]):
        fn(doc, ctx)


def after_type(doc: DocState, etype: str, merged: list[Item], ctx: StageContext) -> list[Item]:
    for _, fn in list(_registry["after_type"]):
        merged = fn(doc, etype, merged, ctx)
    return merged


def after_document(doc: DocState, ctx: StageContext) -> list[Item]:
    extra: list[Item] = []
    for _, fn in list(_registry["after_document"]):
        extra.extend(fn(doc, ctx))
    return extra


def after_run(run: RunDir, ctx: StageContext) -> dict[str, Any]:
    """{name: result} in registration order; the engine writes and hashes each. A stage that raises gives
    {"failed": reason} and the others still run."""
    out: dict[str, Any] = {}
    for name, fn in list(_registry["after_run"]):
        try:
            out[name] = fn(run, ctx)
        except Exception as exc:
            out[name] = {"failed": f"{type(exc).__name__}: {str(exc)[:300]}"}
    return out
