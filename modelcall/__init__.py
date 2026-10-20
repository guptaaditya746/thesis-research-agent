"""Model calls: one cached, redacted structured call on one event loop.

`call.ask` (and `ask_sync`) is the entry point: a `Prompt`, a user prompt, a model and its `CallSettings`, cached
under a key, every failure a redacted `ModelCallError`. Under it: `pins` (the pinned models, standard library
only), `loop` (the one event loop), `gateway` (LiteLLM endpoints, rotation, settings), `cache` (the append-only
result cache, its key and `decode`) and `prompt` (prompt files and their hash). `structured`, `structured_reply`
and `Reply` stay until their callers move onto `ask`. Names load on first use (PEP 562), so
`import modelcall.pins` does not import pydantic-ai."""
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "cache": ("KEY_LINE", "JsonlCache", "cache_key", "decode"),
    "call": ("Answer", "CachedFailure", "ModelCallError", "Reply", "ask", "ask_sync", "default_key", "redact",
             "structured", "structured_reply"),
    "gateway": ("DEFAULT_BASE_URL", "CallSettings", "Rotation", "base_url", "model_identity", "model_name",
                "openai_model", "settings"),
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
