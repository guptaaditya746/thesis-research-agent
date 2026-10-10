# State of the system (10 Oct 2026)

The one page to plan the implementation from. Everything here is decided or measured; details live in
the files named at the end, history in git.

## Framing (decided 10 Oct, grill doc)

- One contribution: provenance recorded while the agent researches, not reconstructed afterwards. Not a claim
  to beat DCI on answers; the claim is that answers are easier to check. User: a research supervisor.
- RQ1: recording each fact with a quote as it is found vs attaching sources to the answer afterwards
  (same agent, model and budget, `claim` off), measured as the share of claims judged supported, plus recall
  and tokens. Trace verifiability is reported as secondary measures, not as a second research question.
- Concepts per question: as many as the question needs, up to 5; the user picks one. Evaluation size (number of questions) not fixed yet; proposed 8.
- No novelty claim on provenance: adopt the approaches of LEDGER and PROV-AGENT and implement them here
  (`docs/provenance-model.md`).
- Evaluation as the supervisor designed it (`docs/context.md` §2): gold document D per question, its facts
  reviewed by the author in Argilla into an answer key, system output matched against the key.
- Not yet decided: model family for D, scoring of counts, the pre-registered test. Proposed but not confirmed: a frontier API model on 2–3 concepts as an upper bound.

## Decided

| Area | Decision | Evidence |
|---|---|---|
| Orchestrator | `Qwen/Qwen3.8-27B-FP8` @ `017b9c7`, GPU 0, 65,536 context, thinking off, `max_tokens` 4096 | A2, A3, B3, L1, L2 |
| Subagent model | `Qwen/Qwen3-30B-A3B-Instruct-2507-FP8` @ `5a5a776`, two replicas (GPUs 1, 2), 32,768 context, 3 active sequences each | A4, A5, L1, L3 |
| Serving | `llm-setup` (GitHub `thesis-llm-setup`, `main`), profile `profiles/agent-3x40.yaml`, `sbatch slurm/llm-stack.sbatch`; models pinned by revision, offline loading, `uv sync --locked` | L1, R3 |
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

## Open: the final Slurm session (`docs/slurm-final-runbook.md`)

| Item | What is missing |
|---|---|
| B0: reproducible toolchain | The S5c steps as `scripts/build-agent-root.sh` and `verify-agent-root.sh`, with file modes in the manifest |
| S7: UDP and Unix sockets | Landlock allows UDP send and connecting to pathname Unix sockets. Add seccomp after `no_new_privs`; the broker is reached through an inherited descriptor (`CLAIM_FD`), not a socket path |
| L7: proxy | `request_timeout` 120 → 600 s (worst step is 112.5 s); `least-busy` left replica 8004 idle; check that `seed` reaches vLLM |
| L8: failure messages | What the proxy returns for prompts over the context limit, so the harness can stop instead of retrying |
| C2b: orchestrator speed | Prefix-cache hits and prefill seconds per step at 30k tokens; decides whether to try Qwen3-30B-A3B as orchestrator |
| D5: corpus | Convert all 337 PDFs with Docling, freeze them with hashes in `manifest.json` |
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
design, to be revised) · `docs/provenance-model.md` (log and graph schema) · `thesis_pipeline.html` (overview page) · `llm-setup/` (the serving stack).
