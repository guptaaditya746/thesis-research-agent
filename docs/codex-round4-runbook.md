# Runbook: round 4 on Slurm (short)

Four items left before the harness can run model-written commands. Why they matter: `docs/STATE.md`,
section "Open". Rules as in `docs/codex-sandbox-runbook.md` ("Rules"): branch `infra-round-4`, never push
`main`; submodule changes on `agent-layout`; never kill a real process to test a permission; never log a
secret's content; one row per test in `tests/RESULTS.md`, logs under `tests/<id>/`.

## S7: close UDP and Unix sockets with seccomp (CPU shell, 1–2 h)

1. Extend `tests/S5/sandbox.py` (keep Landlock as is): after `prctl(PR_SET_NO_NEW_PRIVS)`, install a seccomp
   BPF filter through ctypes (`prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, …)`, no root needed) that returns
   `EPERM` for `socket()` with family `AF_INET`, `AF_INET6`, `AF_UNIX` and `AF_NETLINK`, and for
   `socketpair()`. Check the architecture field first (x86_64 only). If writing BPF by hand is not feasible, use
   the `seccomp` Python bindings if `libseccomp` is on the node; record which.
2. Broker access without a socket path: the harness creates a `socketpair()` before starting the command and
   passes one end as an inherited descriptor (`pass_fds`, number in `CLAIM_FD`). Adapt `tests/H1/client.py` to
   use `CLAIM_FD`.
3. Under the wrapper, check and record allowed / denied:
   - UDP `sendto` to `1.1.1.1:53` (must be denied now);
   - TCP to the internet and to ports 8001, 8002, 8004, 4000, 8010 (still denied);
   - connect to a pathname Unix socket created outside (must be denied now);
   - `claim` through `CLAIM_FD`: 100 claims, forged step ids replaced, chain valid (as H1);
   - Python, grep, rg, jq, numpy/pandas import, writing scratch (still work);
   - `pip install --no-index --find-links $AGENT_ROOT/wheels --target $SCRATCH/pylib networkx` (still works).
4. Write after chmod: inside the wrapper run `chmod u+w` on one file in `$AGENT_ROOT`, then try to append to
   it. Expected: the chmod succeeds and the write is denied. Restore the mode outside.
5. Make the toolchain manifest include modes: `find $AGENT_ROOT -printf '%m %p\n' | sort > agent-root.modes`
   next to the sha256 manifest; verify both after the run.

Pass: UDP and pathname sockets denied, everything in step 3 that should work still works, the write in step
4 denied, both manifests verify.

## L7: proxy timeout and replica routing (stack running, 1 h)

1. On `agent-layout`, set LiteLLM `request_timeout` to 600 in `render_litellm`; run `uv run pytest`.
2. Routing: send 24 sequential `sub-model` requests, then 8 concurrent, and count requests per backend from
   each replica's `/metrics` (`vllm:request_success_total`). If the split is worse than 60/40, try in order:
   `routing_strategy: simple-shuffle`; `usage-based-routing-v2`. If none balances, add one alias per replica
   (`sub-model-1`, `sub-model-2`) next to `sub-model`, so the harness can assign each subagent a replica.
   Record the split for each setting.
3. Seed: send two requests with the same `seed` and `temperature 0.8` through the proxy and two directly to
   vLLM. Matching outputs through the proxy and directly shows the seed is forwarded.

## C2b: prefix cache and prefill at 30k (stack running, 1 h)

1. Read the attention block size from the orchestrator's startup log ("block size").
2. Replay a 30,000-token conversation for 20 steps, ~300 new tokens per step, through `orch-model`, once as
   is and once with one masking event at step 10. Per step record: prompt tokens, time to first token,
   `vllm:prefix_cache_hits_total` and `queries_total` deltas.
3. Report prefill seconds per step with and without a cache hit, and the step-10 cost of masking.

Pass is a measurement, not a threshold: it decides whether to try Qwen3-30B-A3B as orchestrator.

## Finish

Rows for S7, L7 and C2b in `tests/RESULTS.md`; in `docs/STATE.md`, move each finished item from "Open" to
"Decided" or "Numbers" with its result in one line. Commit on `infra-round-4` (and `agent-layout`), push both.
