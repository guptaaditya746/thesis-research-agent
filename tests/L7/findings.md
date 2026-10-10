# L7: LiteLLM timeout, routing, and seed

Date: 2026-10-10. LiteLLM `request_timeout` is 600 seconds in generated configs. Seeded outputs at `temperature=0.8`, `seed=90210` matched pairwise through LiteLLM and directly through vLLM; all four outputs have SHA-256 `a6112df90b11c3a8d35e8ce438497e8cc42a0f09dac4fd2613192ebaad5be254`.

Replica request-success deltas (`8002` / `8004`):

| Strategy | 24 sequential shared-alias requests | 8 concurrent shared-alias requests | Assessment |
|---|---:|---:|---|
| `least-busy` | 24 / 0 | 5 / 3 | Sequential routing stuck to one backend. |
| `simple-shuffle` | 15 / 9 | 1 / 7 | Combined 16 / 16, but concurrent sample was skewed. |
| `usage-based-routing-v2` | 12 / 12 | 8 / 0 | Sequential balanced; simultaneous requests all selected one backend. |
| Pinned aliases | — | 4 / 4 | Eight successful concurrent requests using alternating `sub-model-1` and `sub-model-2`. |

The generated config keeps the shared `sub-model` group and adds `sub-model-1` → port 8002 and `sub-model-2` → port 8004. Both pinned LiteLLM entries send the backend served name `sub-model`. Use the pinned aliases for explicit subagent fan-out. The shared alias remains available for normal requests. The stack default remains `least-busy`; no routing strategy alone provided dependable concurrent balance.

Config/runtime logs and measurements: `measure.json`, `measure-simple-shuffle.json`, `measure-usage-based.json`, `measure-aliases.json`, `startup-*.log`. The submodule test suite passes 41 tests; Ruff passes.
