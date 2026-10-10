# State of the system (10 Oct 2026)

The one page to plan the implementation from. Everything here is decided or measured; details and
history live in the files named in each section. Open framing questions (research questions, baseline,
scope) are in the grill doc and are not settled yet.

## Decided

| Area | Decision | Evidence |
|---|---|---|
| Orchestrator | `Qwen/Qwen3.8-27B-FP8` @ `017b9c7`, GPU 0, 65,536 context, thinking off, `max_tokens` 4096 | A2, A3, B3, L1, L2 |
| Subagent model | `Qwen/Qwen3-30B-A3B-Instruct-2507-FP8` @ `5a5a776`, two replicas (GPUs 1, 2), 32,768 context, 3 active sequences each | A4, A5, L1, L3 |
| Serving | `related/final-final-llm-setup` branch `agent-layout`, profile `profiles/agent-3x40.yaml`, `sbatch slurm/llm-stack.sbatch`; models pinned by revision, offline loading, `uv sync --locked` | L1, R3 |
| Model access | Harness talks only to LiteLLM `127.0.0.1:4000` (`orch-model`, `sub-model`) | L2, CONSUMERS.md |
| Reply format | One ```bash block, lenient fallback (single bare command line, else a nudge); never run anything from `reasoning_content` | B1–B3, L2 |
| Loops | Identical command twice → notice; three times → notice with remaining budget | B4 |
| Sandbox | Every agent command runs under the Landlock wrapper (`tests/S5/sandbox.py`, ABI 8) in its own process group (`tests/S5/run_sandbox.py`), with `ulimit -v 2G` and `timeout 120`. Read-only: system dirs, corpus, agent toolchain. Writable: one scratch dir on Ceph. | S5a, S5b, S6, S1b |
| Toolchain | Pinned, hashed, read-only `agent-venv` (numpy, pandas, regex, rapidfuzz, pyyaml, scikit-learn) + ripgrep + jq, built at job start; extra packages only from a local wheel store via `pip install --no-index` into scratch | S5c |
| Logs and claims | A broker outside the sandbox owns `events.jsonl` and `claims.jsonl` (single writer, hash chain, step id assigned by the harness); the sandbox sees only the broker endpoint | H1, R2 |
| Output cap | 8 KB of each command's output in context, full output in a file | C1 |
| Corpus | Docling 2.110.0 (OCR off, tables on), converted once and frozen with hashes in `manifest.json` | D1, D2 |

## Numbers the design must respect

| Quantity | Value | Test |
|---|---|---|
| Orchestrator decode | 41.6 tok/s (one sequence) | A5 |
| Orchestrator prefill | ~2,400 tok/s; 26 s to first token at 60k | A3 |
| Orchestrator KV capacity | 79,371 tokens = 1.21 requests of 65k at once | A2 |
| Worst-case orchestrator step | 112.5 s (54.6k in + 4,096 out) against a 120 s proxy timeout | L6 |
| Prefix cache (Qwen3.8, vLLM 0.21) | Hits only at block boundaries; masking mid-history invalidates the rest | C2 |
| Subagent decode | 130 tok/s; 64,848 KV tokens per replica | A5, L1 |
| Subagent concurrency | 6 × 16k without preemption (3 per replica) | L3 |
| Full paper | 45–230 KB, ~35k tokens: larger than a subagent's 32k context | decisions §5 |
| Stack startup | 11 min 14 s (orchestrator 5 min 20 s) | L1, L5 |
| Agent memory limit | 2 GB `ulimit -v` loads numpy and pandas and stops a 100 GB allocation | S1b |
| Ceph append | 80,000/80,000 lines intact with 8 writers; `fsync` p99 65–104 ms | R2 |
| Job | 3×A100 40 GB, 16 CPUs, 48 h; node has 503 GiB RAM, the job's cgroup has no memory cap | A1, S1b |

## Open before the harness can run model-written commands

| Item | What is missing | Where |
|---|---|---|
| S7: close UDP and Unix sockets | Landlock allows UDP send and connecting to pathname Unix sockets. Add a seccomp filter (unprivileged after `no_new_privs`) that blocks new IP and Unix sockets; the `claim` client uses an inherited descriptor to the broker instead of a socket path | `docs/codex-round4-runbook.md` |
| Proxy timeout | Raise LiteLLM `request_timeout` from 120 to 600 s; retries happen in the harness, each logged | round-4 runbook |
| Replica routing | `least-busy` left replica 8004 idle (L6). Fix the router or give each replica its own alias and let the harness assign subagents | round-4 runbook |
| Orchestrator speed | Re-run C2 at 30k tokens with prefill seconds per step; if prefill dominates, compare Qwen3-30B-A3B as orchestrator | round-4 runbook |
| Anchor library | `tests/D3/anchor.py` hashes the quote instead of the file and returns the quote instead of its position; matching must also accept retyped quotes (whitespace, hyphenation, curly quotes) mapped back to raw offsets | to fix in code |
| Framing | Research questions, baseline, gold, scope | grill doc |

## Later (not blocking the first harness run)

- **After the corpus is frozen:** anchors on full text (R1); C1 and D4 on full text.
- **After the harness exists:** context overflow before 61,440 tokens (C8); hard backend crash (F7); `claim` quoting on real passages (B5); first end-to-end run (C3), then C5 and C6; `spawn` (C4) only if single-agent runs overflow.
- **Before evaluation:** queue wait and total GPU budget (E1); judges on local models (E2); Argilla (H2).
- **Only if wanted:** Omen tunnels and Langfuse copy (T2 retest, T3); `save_tool` (C7).

## Where the details are

`tests/RESULTS.md` (every result, rounds 1–3) · `docs/decisions-after-tests.md` (why each decision) ·
`docs/plan.md` (the design, to be revised after the framing decisions) · `docs/infra-tests-next.md` (test
history) · `thesis_pipeline.html` (overview page).
