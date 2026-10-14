"""The agentic extractor: our research agent (agent/) as one implementation of the extractor contract.

Imported lazily: `register_agentic()` adds it to the engine's registry under the name `agentic`
(evidence.extractors.register(name, factory)); the agent's own heavy imports (LiteLLM,
mini-swe-agent) happen only when an agent actually runs.
"""
from __future__ import annotations

from typing import Any

NAME = "agentic"


def factory(config: dict[str, Any]) -> Any:
    """Registry factory: config holds AgentSettings fields, `budget` and optionally `work_dir`."""
    from .extractor import AgenticExtractor

    return AgenticExtractor.from_config(config)


def register_agentic() -> None:
    from evidence.extractors import register

    register(NAME, factory)
