# State of the system (10 Oct 2026)

The one page to plan the implementation from. Everything here is decided or measured; details live in
the files named at the end, history in git.

## Framing (decided 10 Oct, grill doc)

- One contribution: provenance recorded while the agent researches, not reconstructed afterwards. Not a claim
  to beat DCI on answers; the claim is that answers are easier to check. User: a research supervisor.
- RQ1: recording each fact with a quote as it is found vs attaching sources to the answer afterwards
  (same agent, model and budget, `claim` off), measured as the share of claims judged supported, plus recall
  and tokens. Trace verifiability is reported as secondary measures, not as a second research question.
- 8 concepts. Gold D built as the supervisor proposed. Claims judged by the author in Argilla.
- Not yet decided: novelty against LEDGER and PROV-AGENT, model family for D, scoring of counts, the
  pre-registered test. Proposed but not confirmed: a frontier API model on 2–3 concepts as an upper bound.

## Decided

| Area | Decision | Evidence |
|---|---|---|
| Orchestrator | `Qwen/Qwen3.8-27B-FP8` @ `017b9c7`, GPU 0, 65,536 context, thinking off, `max_tokens` 4096 | A2, A3, B3, L1, L2 |
| Subagent model | `Qwen/Qwen3-30B-A3B-Instruct-2507-FP8` @ `5a5a776`, two replicas (GPUs 1, 2), 32,768 context, 3 active sequences each | A4, A5, L1, L3 |
| Serving | `llm-setup` (GitHub `thesis-llm-setup`, `main`), profile `profiles/agent-3x40.yaml`, `sbatch slurm/llm-stack.sbatch`; models pinned by revision, offline loading, `uv sync --locked` | L1, R3 |
| Model access | Harness talks only to LiteLLM `127.0.0.1:4000` (`orch-model`, `sub-model`); use pinned `sub-model-1` / `sub-model-2` for concurrent fan-out | L2, L7, CONSUMERS.md |
| Subagent routing | LiteLLM shared alias remains available; fan-out uses pinned `sub-model-1` and `sub-model-2` because all tested shared-alias strategies skewed concurrent requests | L7 |
| Context overflow | Proxy returns HTTP 400 `ContextWindowExceededError` with context and token counts; map to “context full” and stop retrying | L8 |
| Reply format | Qwen3.8 with the strict one-bash-block-only instruction: thinking off 50/50; thinking on at low effort 50/50 with 4,096 max tokens and 2.51 s mean; default xhigh at 4,096 gave 48/50 and at 8,192 gave 47/50 due length cuts. Use low effort for routine command turns; keep lenient parser fallback, rate command usefulness, and never run anything from the reasoning field. | B1–B3, B8, B9, L2 |
| Loops | Identical command twice → notice; three times → notice with remaining budget | B4 |
| Sandbox | Every agent command runs under Landlock ABI 8 plus x86_64 seccomp in its own process group (`tests/S5/run_sandbox.py`), with `ulimit -v 2G` and `timeout 120`. System dirs, corpus, agent toolchain, and the resolved uv Python runtime are read-only; one Ceph scratch dir is writable. Seccomp blocks IP, pathname Unix, netlink sockets, and `socketpair()`; a pre-opened claim descriptor remains usable. | S5a, S5b, S6, S7, S1b |
| Toolchain | Pinned, hashed, mode-manifested read-only `agent-venv` (numpy, pandas, regex, rapidfuzz, pyyaml, scikit-learn) + ripgrep + jq, built with `scripts/build-agent-root.sh`; `scripts/verify-agent-root.sh` checks file hashes and modes. Extra packages install from local wheels into scratch. | S5c, B0, S7 |
| Logs and claims | A broker outside the sandbox owns `events.jsonl` and `claims.jsonl` (single writer, hash chain, step id assigned by the harness); the sandbox submits claims over an inherited `CLAIM_FD`. | H1, R2, S7 |
| Output cap | 8 KB of each command's output in context, full output in a file | C1 |
| Corpus | Docling 2.110.0 (OCR off, tables on), 336/337 PDFs converted and hash-verified; omit scanned PDF `p38` per user decision; frozen with hashes in `manifest.json` | D1, D2, D5 |

## Numbers the design must respect

| Quantity | Value | Test |
|---|---|---|
| Orchestrator decode | 41.6 tok/s (one sequence) | A5 |
| Orchestrator prefill | ~2,400 tok/s; 26 s to first token at 60k | A3 |
| Orchestrator KV capacity | 79,371 tokens = 1.21 requests of 65k at once | A2 |
| Worst-case orchestrator step | 112.5 s (54.6k in + 4,096 out) against a 120 s proxy timeout | L6 |
| Prefix cache (Qwen3.8, vLLM 0.21) | 784-token blocks; 30k cold TTFT 12.0 s, cached mean 0.35 s; step-10 masking to 47 tokens gives 0.109 s TTFT | C2, C2b |
| Subagent decode | 130 tok/s; 64,848 KV tokens per replica | A5, L1 |
| Subagent concurrency | 6 × 16k without preemption (3 per replica) | L3 |
| Full paper | 45–230 KB, ~35k tokens: larger than a subagent's 32k context | decisions §5 |
| Stack startup | 11 min 14 s (orchestrator 5 min 20 s) | L1, L5 |
| Agent memory limit | 2 GB `ulimit -v` loads numpy and pandas and stops a 100 GB allocation | S1b |
| Ceph append | 80,000/80,000 lines intact with 8 writers; `fsync` p99 65–104 ms | R2 |
| Job | 3×A100 40 GB, 16 CPUs, 48 h; node has 503 GiB RAM, the job's cgroup has no memory cap | A1, S1b |

## Open: the final Slurm session (`docs/slurm-final-runbook.md`)

| Item | What is missing |
|---|---|
| F1: everything together | Model output → lenient parser → sandbox → `claim` → broker → hash chain, on the frozen corpus |

Not on Slurm: the anchor library (`tests/D3/anchor.py` hashes the quote instead of the file and returns the
quote instead of its position; matching must accept retyped quotes mapped back to raw offsets) is fixed in code
during implementation.

## Later (need the harness)

Context overflow before 61,440 tokens (C8); `claim` quoting on real passages (B5); first end-to-end run (C3),
then re-execution (C5) and replay (C6); `spawn` (C4) only if single-agent runs overflow; Argilla set-up for
judging (H2). Optional: Omen tunnels and Langfuse copy (T2, T3); `save_tool` (C7).

## Where the details are

`tests/RESULTS.md` (every result) · `docs/decisions-after-tests.md` (why each decision) · `docs/plan.md` (the
design, to be revised) · `thesis_pipeline.html` (overview page) · `llm-setup/` (the serving stack).
