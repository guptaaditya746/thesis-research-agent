"""Model calls: one cached, redacted structured call on one event loop.

`call.ask` (and `ask_sync`) is the entry point: a `Prompt`, a user prompt, a model and its `CallSettings`, cached
under a key, every failure a redacted `ModelCallError`. Under it: `loop` (the one event loop), `gateway` (pinned
models, rotation, settings), `cache` (the append-only result cache, its key and `decode`) and `prompt` (prompt
files and their hash). `structured`, `structured_reply` and `Reply` stay until their callers move onto `ask`."""
from .cache import KEY_LINE, JsonlCache, cache_key, decode
from .call import (Answer, CachedFailure, ModelCallError, Reply, ask, ask_sync, default_key, redact, structured,
                   structured_reply)
from .gateway import (DEFAULT_BASE_URL, ORCH_ALIAS, ORCH_MODEL, ORCHESTRATOR, SUB_ALIASES, SUB_MODEL, SUBAGENTS,
                      CallSettings, Rotation, base_url, model_identity, model_name, openai_model, settings)
from .loop import model_loop, on_model_loop, run_sync
from .prompt import Prompt, load_prompt, prompt_sha256

__all__ = ["DEFAULT_BASE_URL", "JsonlCache", "KEY_LINE", "ORCHESTRATOR", "ORCH_ALIAS", "ORCH_MODEL", "Answer",
           "CachedFailure", "CallSettings", "ModelCallError", "Prompt", "Reply", "Rotation", "SUBAGENTS", "SUB_ALIASES",
           "SUB_MODEL",
           "ask", "ask_sync", "base_url", "cache_key", "decode", "default_key", "load_prompt", "model_identity",
           "model_loop", "model_name", "on_model_loop", "openai_model", "prompt_sha256", "redact", "run_sync",
           "settings", "structured", "structured_reply"]
