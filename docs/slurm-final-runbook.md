# Runbook: the final Slurm session

The last infrastructure session before implementation. After it, every item in `docs/STATE.md` "Open" that
needs the cluster is closed, the corpus is frozen, and the pieces the harness reuses (sandbox, broker, toolchain
build) exist as scripts. Results go into `tests/RESULTS.md` and `docs/STATE.md`; nothing else needs updating.

## Rules

- Branch `infra-final` in this repo and in `llm-setup` (the submodule, GitHub `thesis-llm-setup`). Never push
  `main` of either; push both branches at the end.
- Never kill or signal a real process to test a permission (`kill -0` only). Never log a secret's content: for
  `.env`, keys or `/proc/<pid>/environ` record only "readable" / "denied" and a byte count.
- Logs under `tests/<id>/`, one row per test in `tests/RESULTS.md`, `NOT RUN` with the reason when a test cannot
  run. Steps marked **USER** need the user: stop and ask.
- Large generated files (outputs over 1 MB, the converted corpus) stay on Ceph, never in git.

## 0. Setup

The submodule moved from `related/final-final-llm-setup` to `llm-setup`, and its `agent-layout` work is now on
`main`. On an existing clone:

```bash
git fetch && git checkout -b infra-final origin/main
git submodule sync && git submodule update --init --recursive
rm -rf related                     # old submodule path, now unused
(cd llm-setup && git checkout -b infra-final origin/main)
set -a; source llm-setup/.env; set +a
```

Stack (for L7, L8, C2b, F1): `cd llm-setup && LLM_SETUP_PROFILE=profiles/agent-3x40.yaml sbatch slurm/llm-stack.sbatch`,
then `srun --jobid <id> --overlap --pty bash -l`. S7 and B0 need only a CPU shell; D5 is its own job.

## B0: make the round-3 setup reproducible (CPU, 30 min)

Turn the S5c steps (`tests/RESULTS.md`, S5c) into `scripts/build-agent-root.sh <AGENT_ROOT>`: `uv venv` +
`uv pip sync --require-hashes tests/S5/agent-requirements.lock`, ripgrep and jq checked against
`tests/S5/binaries.sha256`, the wheel store (`networkx tabulate`), `chmod -R a-w`, then two manifests:
`agent-root.sha256` (file hashes) and `agent-root.modes` (`find $AGENT_ROOT -printf '%m %p\n' | sort`).
Add `scripts/verify-agent-root.sh` that checks both. Run both on a fresh path; record time and result.

## S7: close UDP and Unix sockets (CPU, 1–2 h)

1. In `tests/S5/sandbox.py`, keep Landlock; after `prctl(PR_SET_NO_NEW_PRIVS)` install a seccomp BPF filter
   via ctypes (`prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, …)`, no root) that checks the architecture (x86_64)
   and returns `EPERM` for `socket()` with family `AF_INET`, `AF_INET6`, `AF_UNIX`, `AF_NETLINK`, and for
   `socketpair()`. If hand-written BPF is not feasible, use the `seccomp` Python bindings when `libseccomp` is on
   the node; record which.
2. Broker without a socket path: the runner creates a `socketpair()` before starting the command and passes
   one end as an inherited descriptor (`pass_fds`, number in `CLAIM_FD`). Update `tests/S5/run_sandbox.py`,
   `tests/H1/broker.py` and `tests/H1/client.py` for this.
3. Under the wrapper, record allowed / denied:
   - UDP `sendto` to `1.1.1.1:53` (denied now); pathname Unix socket created outside (denied now);
   - TCP to the internet and to 8001, 8002, 8004, 4000, 8010 (still denied);
   - 100 claims through `CLAIM_FD` with a forged step id: stored with the real id, chain verifies;
   - `python3`, `grep`, `rg`, `jq`, `import numpy, pandas`, writing scratch, and
     `pip install --no-index --find-links $AGENT_ROOT/wheels --target $SCRATCH/pylib networkx` (still work).
4. Write after chmod: inside the wrapper `chmod u+w` one file in `$AGENT_ROOT`, then append to it. Expected:
   chmod succeeds, write denied. Restore the mode outside; `verify-agent-root.sh` must pass.

Pass: everything that should be denied is, everything that should work does, both manifests verify.

## L7: proxy timeout, routing, seed (stack running, 1 h)

1. In `llm-setup`, set LiteLLM `request_timeout` to 600 in `render_litellm`; `uv run pytest`. Restart the stack
   once so the rest of this session runs with it.
2. Routing: 24 sequential then 8 concurrent `sub-model` requests; count per replica from each replica's
   `/metrics` (`vllm:request_success_total`). If worse than 60/40, try `routing_strategy: simple-shuffle`, then
   `usage-based-routing-v2`. If none balances, add aliases `sub-model-1` and `sub-model-2` (one per replica)
   beside `sub-model`. Record the split for each setting and keep the best.
3. Seed: two requests with the same `seed` and `temperature 0.8` through the proxy, two directly to vLLM.
   Matching outputs in both pairs show the seed is forwarded.

## L8: what the harness sees when a request fails (stack running, 20 min)

Through the proxy, record the HTTP status, error type and message for: an `orch-model` prompt of 70,000 tokens
(over the 65,536 context); a `sub-model` prompt of 34,000 tokens (over 32,768); `max_tokens` that pushes
prompt + output over the context. The harness maps these to "context full" instead of retrying.

## C2b: prefix cache and prefill at 30k (stack running, 1 h)

1. Read the attention block size from the orchestrator's startup log.
2. Replay a 30,000-token conversation for 20 steps, ~300 new tokens per step, through `orch-model`, once as is
   and once with one masking event at step 10. Per step record prompt tokens, time to first token, and the
   deltas of `vllm:prefix_cache_hits_total` and `vllm:prefix_cache_queries_total`.
3. Report prefill seconds per step with and without a cache hit, and the step-10 cost of masking.

A measurement, not a threshold: it decides whether to try Qwen3-30B-A3B as orchestrator.

## D5: convert and freeze the corpus (separate job, ~10 h unattended)

1. `scripts/build-corpus.py`, from `tests/D1/convert_docling.py`: Docling 2.110.0, OCR off, tables on, all 337
   PDFs (source: `final-final-frontend/corpus_acl_emnlp_2025_input` and the 37 originals; **USER** if the
   originals are elsewhere). Paper id as in D1 (`2025-acl-long-1031`). Output `$CORPUS/<id>.md`, with `$CORPUS`
   on Ceph outside the repo.
2. `$CORPUS/manifest.json`: id, source PDF and its sha256, Markdown sha256, byte length, Docling version,
   conversion time. Copy the manifest to `corpus/manifest.json` in this repo (the Markdown stays on Ceph).
3. `chmod -R a-w $CORPUS`. Record failures (no Markdown, or under 5 KB) with the reason; do not retry by hand.

Submit as its own `sbatch` (one GPU if Docling uses it, else 16 CPUs) so it runs while the other steps do.

## F1: everything together (stack running, after S7, L7 and D5, 30 min)

One script, `tests/F1/acceptance.py`, standing in for one harness step loop with nothing mocked:

1. Build `$AGENT_ROOT` with `build-agent-root.sh`; start the broker (log directory outside the sandbox).
2. Ask `orch-model` through the proxy for a ```bash block that counts papers in `$CORPUS` mentioning
   "retrieval" and records one claim with an exact quote from one of them. Parse it with the lenient parser
   rule from STATE.md.
3. Run it through `run_sandbox.py` (Landlock + seccomp, `ulimit -v 2G`, `timeout 120`, `CLAIM_FD`).
4. Check: the command saw the frozen corpus read-only; the claim reached `claims.jsonl` with the broker's
   step id; the quote is found in the file whose hash the manifest lists; the chain verifies; the chain head
   is in the Slurm job log; `verify-agent-root.sh` passes; no network was reachable from the command.

Pass: all checks true. This is the first time model output, sandbox, broker and corpus run as one path.

## Finish

1. Rows for B0, S7, L7, L8, C2b, D5 and F1 in `tests/RESULTS.md`.
2. In `docs/STATE.md`, move each finished item from "Open" to "Decided" or "Numbers", one line each with its
   result, and update the corpus row with the manifest location and the number of papers converted.
3. Commit on `infra-final` in both repos, push both. `scancel` your jobs, stop the broker, delete large
   scratch files.
4. Report: pass/fail per test with the number that matters, every unexpected "allowed", open **USER** steps.
