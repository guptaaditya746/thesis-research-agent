"""The pinned models of every run: orchestrator and sub-model replicas (name, revision, context window).

Standard library only, so agent/ can read the pins without importing pydantic-ai. Hashed into the code
hash of the extractors that depend on them: a change here is a new extractor id."""
from __future__ import annotations

# Fixed run settings (docs/earlier-work.md, Fixed run settings).
ORCHESTRATOR = {"alias": "orch-model", "name": "Qwen/Qwen3.8-27B-FP8", "revision": "017b9c7",
                "thinking": False, "max_tokens": 4096, "context_tokens": 65536}
SUBAGENTS = [{"alias": f"sub-model-{i}", "name": "Qwen/Qwen3-30B-A3B-Instruct-2507-FP8",
              "revision": "5a5a776", "context_tokens": 32768} for i in (1, 2)]
SUB_ALIASES = tuple(s["alias"] for s in SUBAGENTS)  # sub-model-1, sub-model-2
SUB_MODEL = {"name": SUBAGENTS[0]["name"], "revision": SUBAGENTS[0].get("revision")}
ORCH_ALIAS = ORCHESTRATOR["alias"]  # orch-model: the one model of every extractor and both baselines
ORCH_MODEL = {"name": ORCHESTRATOR["name"], "revision": ORCHESTRATOR.get("revision")}
