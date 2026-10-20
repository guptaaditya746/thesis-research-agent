"""Model calls: one cached, redacted structured call on one event loop (the `ask` entry point comes later).

Four modules: `loop` (the one event loop), `gateway` (pinned models, rotation, settings, structured replies,
redaction), `cache` (the append-only result cache and its key) and `prompt` (prompt files and their hash).
Everything callers used from the old `gold.llm` is re-exported here under the same name."""
from .cache import KEY_LINE, JsonlCache, cache_key
from .gateway import (DEFAULT_BASE_URL, ORCH_ALIAS, ORCH_MODEL, ORCHESTRATOR, SUB_ALIASES, SUB_MODEL, SUBAGENTS,
                      CallSettings, Reply, Rotation, base_url, model_identity, model_name, openai_model, redact,
                      settings, structured, structured_reply)
from .loop import model_loop, on_model_loop, run_sync
from .prompt import Prompt, load_prompt, prompt_sha256

__all__ = ["DEFAULT_BASE_URL", "JsonlCache", "KEY_LINE", "ORCHESTRATOR", "ORCH_ALIAS", "ORCH_MODEL", "CallSettings",
           "Prompt", "Reply", "Rotation", "SUBAGENTS", "SUB_ALIASES", "SUB_MODEL", "base_url", "cache_key",
           "load_prompt", "model_identity", "model_loop", "model_name", "on_model_loop", "openai_model",
           "prompt_sha256", "redact", "run_sync", "settings", "structured", "structured_reply"]
