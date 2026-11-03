"""The four seams where a later feature plugs into the engine without editing it.

    before_extract(doc: DocState, plan: Plan | None) -> None          once per document, before the screen
    after_type(doc: DocState, etype: str, merged: list[Item]) -> list[Item]   after each merge of a type; returns the
                                                                      (possibly filtered or changed) items
    after_document(doc: DocState) -> list[Item]                       after the funnel; returns extra items to add
    after_run(run: RunDir, plan: Plan | None) -> dict[str, Any]       after the answer; each result is written as
                                                                      `<name>.json` and hashed into run.json outputs

Stages run in registration order. With none registered every call below is a no-op and a run is byte-identical to
one made before the seams existed. Tests call `clear()` (or use `registered()`) so registrations do not leak.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .contract import Item
    from .engine import DocState
    from .plan import Plan
    from .rundir import RunDir

__all__ = ["After", "after_document", "after_run", "after_type", "before_extract", "clear", "register", "registered"]

After = Literal["before_extract", "after_type", "after_document", "after_run"]
_AT: tuple[str, ...] = ("before_extract", "after_type", "after_document", "after_run")
_registry: dict[str, list[tuple[str, Callable[..., Any]]]] = {at: [] for at in _AT}


def register(name: str, at: After, fn: Callable[..., Any]) -> None:
    """Add `fn` (called as the seam `at` says above) under `name`; `after_run` writes its result to `<name>.json`."""
    if at not in _registry:
        raise ValueError(f"unknown seam {at!r}: one of {', '.join(_AT)}")
    if any(n == name for n, _ in _registry[at]):
        raise ValueError(f"a stage named {name!r} is already registered at {at}")
    _registry[at].append((name, fn))


def clear() -> None:
    """Remove every registered stage (tests)."""
    for stages in _registry.values():
        stages.clear()


@contextmanager
def registered() -> Iterator[None]:
    """Clear on entry and on exit, so what a test registers inside does not leak."""
    clear()
    try:
        yield
    finally:
        clear()


def before_extract(doc: DocState, plan: Plan | None) -> None:
    for _, fn in list(_registry["before_extract"]):
        fn(doc, plan)


def after_type(doc: DocState, etype: str, merged: list[Item]) -> list[Item]:
    for _, fn in list(_registry["after_type"]):
        merged = fn(doc, etype, merged)
    return merged


def after_document(doc: DocState) -> list[Item]:
    extra: list[Item] = []
    for _, fn in list(_registry["after_document"]):
        extra.extend(fn(doc))
    return extra


def after_run(run: RunDir, plan: Plan | None) -> dict[str, Any]:
    """{name: result} in registration order; the engine writes and hashes each."""
    return {name: fn(run, plan) for name, fn in list(_registry["after_run"])}
