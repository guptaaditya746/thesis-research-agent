"""The extractor library: a registry of named factories behind the one contract (evidence/contract.py).

A protocol's cascade names extractors; the engine builds each with `get(name, config)`, where `config` is
the protocol's configuration for that step plus what the engine adds (the evidence type, its field
schema, links and span roles, a model alias override). Other packages register their own kinds with
`register`; the agentic extractor (evidence/agentic) registers itself on first use.
"""
from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from ..contract import Extractor

Factory = Callable[[dict[str, Any]], Extractor]
_FACTORIES: dict[str, Factory] = {}
# Imported on first use: the agentic extractor loads the research agent (loop, sandbox, broker), which a
# regex- or LLM-only run does not need.
_LAZY = {"agentic": "evidence.agentic.register"}


def register(name: str, factory: Factory) -> None:
    """Make `name` buildable; registering a name again replaces its factory (a module reloaded in tests)."""
    if not name or not name.replace("_", "").isalnum() or name != name.lower():
        raise ValueError(f"extractor names are a-z0-9_: {name!r}")
    _FACTORIES[name] = factory


def get(name: str, config: dict[str, Any] | None = None) -> Extractor:
    if name not in _FACTORIES and name in _LAZY:
        importlib.import_module(_LAZY[name])
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise KeyError(f"no extractor named {name!r}; registered: {names()}") from None
    return factory(dict(config or {}))


def names() -> list[str]:
    return sorted(set(_FACTORIES) | set(_LAZY))


def _builtins() -> None:
    from . import abbrev, conditions, dataset, llm, numbers, regex, screen, units
    # screen: the funnel's regex_screen and llm_screen (Part D); conditions, units: kind-aware regex (A4); abbrev:
    # self-defined names (C1); numbers: number-first measurements (C2)
    for module in (regex, llm, screen, dataset, conditions, units, abbrev, numbers):
        for name, factory in module.FACTORIES.items():
            register(name, factory)


_builtins()
