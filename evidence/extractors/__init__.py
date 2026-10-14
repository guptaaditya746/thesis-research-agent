"""The extractor library: a registry of named factories behind the one contract (evidence/contract.py).

A protocol's cascade names extractors; the engine builds each with `get(name, config)`, where `config` is
the protocol's configuration for that step plus what the engine adds (the evidence type, its field
schema, links and span roles, a model alias override). Other packages register their own kinds
(the agentic extractor in evaluation/) with `register` before a run.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..contract import Extractor

Factory = Callable[[dict[str, Any]], Extractor]
_FACTORIES: dict[str, Factory] = {}


def register(name: str, factory: Factory) -> None:
    """Make `name` buildable; registering a name again replaces its factory (a module reloaded in tests)."""
    if not name or not name.replace("_", "").isalnum() or name != name.lower():
        raise ValueError(f"extractor names are a-z0-9_: {name!r}")
    _FACTORIES[name] = factory


def get(name: str, config: dict[str, Any] | None = None) -> Extractor:
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise KeyError(f"no extractor named {name!r}; registered: {names()}") from None
    return factory(dict(config or {}))


def names() -> list[str]:
    return sorted(_FACTORIES)


def _builtins() -> None:
    from . import llm, regex
    for module in (regex, llm):
        for name, factory in module.FACTORIES.items():
            register(name, factory)


_builtins()
