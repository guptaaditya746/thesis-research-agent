"""Model calls: one cached, redacted structured call on one event loop (the `ask` entry point comes later).

Modules: `pins` (the pinned models, standard library only), `loop` (the one event loop), `gateway` (rotation,
settings, structured replies, redaction), `cache` (the append-only result cache and its key) and `prompt`
(prompt files and their hash). Everything callers used from the old `gold.llm` is re-exported here under the
same name. Names load on first use (PEP 562), so `import modelcall.pins` does not import pydantic-ai."""
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "cache": ("KEY_LINE", "JsonlCache", "cache_key"),
    "gateway": ("DEFAULT_BASE_URL", "CallSettings", "Reply", "Rotation", "base_url", "model_identity", "model_name",
                "openai_model", "redact", "settings", "structured", "structured_reply"),
    "loop": ("model_loop", "on_model_loop", "run_sync"),
    "pins": ("ORCH_ALIAS", "ORCH_MODEL", "ORCHESTRATOR", "SUB_ALIASES", "SUB_MODEL", "SUBAGENTS"),
    "prompt": ("Prompt", "load_prompt", "prompt_sha256"),
}
_MODULE_OF = {name: module for module, names in _EXPORTS.items() for name in names}
__all__ = sorted(_MODULE_OF)


def __getattr__(name: str) -> Any:
    module = _MODULE_OF.get(name)
    if module is None:
        raise AttributeError(f"module 'modelcall' has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value
