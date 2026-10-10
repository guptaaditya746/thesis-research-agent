# State of the system (10 Oct 2026)

The one page to plan the implementation from. Everything here is decided or measured; details live in
the files named at the end, history in git.

## Framing (decided 10 Oct, grill doc)

- One contribution: provenance recorded while the agent researches, not reconstructed afterwards. Not a claim
  to beat DCI on answers; the claim is that answers are easier to check. User: a research supervisor.
- RQ1: recording each fact with a quote as it is found vs attaching sources to the answer afterwards
  (same agent, model and budget, `claim` off), scored against the answer key from D (correct and wrong facts),
  the share of facts whose quote really supports them, unsourced facts, and tokens and time. Trace verifiability is reported as secondary measures, not as a second research question.
- Concepts per question: as many as the question needs, up to 5; the user picks one. Evaluation on 12 questions (6 corpus-wide, 6 ambiguous), each with its own gold D.
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
| Model access | Harness talks only to LiteLLM `127.0.0.1:4000` (`orch-model`, `sub-model`); use pinned `sub-model-1` / `sub-model-2` for concurrent fan-out | L2, L7, CONSUMERS.md |
| Subagent routing | LiteLLM shared alias remains available; fan-out uses pinned `sub-model-1` and `sub-model-2` because all tested shared-alias strategies skewed concurrent requests | L7 |
| Context overflow | Proxy returns HTTP 400 `ContextWindowExceededError` with context and token counts; map to “context full” and stop retrying | L8 |
| Reply format | Thinking off with the strict one-bash-block instruction: 50/50 blocks, 0.63 s mean (B8). Thinking on at low effort also gave 50/50 but 2.51 s; default effort loses 2–3/50 to length cuts. Keep thinking off; switch to low effort only if the blind usefulness rating (Later) favours it. Lenient parser fallback stays; never run anything from the reasoning field | B1–B3, B8, B9, L2 |
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
| Worst-case orchestrator step | 112.5 s (54.6k in + 4,096 out); proxy timeout now 600 s | L6, L7 |
| Prefix cache (Qwen3.8, vLLM 0.21) | 784-token blocks; at 30k a cold prompt takes 12.0 s to first token, a cached one 0.35 s (94% hits). Masking one output mid-history re-prefills everything after it at ~2,500 tok/s (up to ~12 s at 30k); C2b masked the whole history, so this is estimated, not measured | C2, C2b |
| Subagent decode | 130 tok/s; 64,848 KV tokens per replica | A5, L1 |
| Subagent concurrency | 6 × 16k without preemption (3 per replica) | L3 |
| Full paper | 45–230 KB, ~35k tokens: larger than a subagent's 32k context | decisions §5 |
| Stack startup | 11 min 14 s (orchestrator 5 min 20 s) | L1, L5 |
| Agent memory limit | 2 GB `ulimit -v` loads numpy and pandas and stops a 100 GB allocation | S1b |
| Ceph append | 80,000/80,000 lines intact with 8 writers; `fsync` p99 65–104 ms | R2 |
| Job | 3×A100 40 GB, 16 CPUs, 48 h; node has 503 GiB RAM, the job's cgroup has no memory cap | A1, S1b |

## Open

| Item | State |
|---|---|
| F1: everything together | `tests/F1/acceptance.py` is written, but only the `claim` smoke test ran. Run it first on the next stack start; it is the first harness step |
| Anchor library | `tests/D3/anchor.py` hashes the quote instead of the file and returns the quote instead of its position; matching must accept retyped quotes mapped back to raw offsets. Fixed in code during implementation |

No further infrastructure session is planned: B0, S7, L7, L8, C2b and D5 closed on 10 Oct.

## Later (need the harness)

Context overflow before 61,440 tokens (C8); `claim` quoting on real passages (B5); first end-to-end run (C3),
then re-execution (C5) and replay (C6); `spawn` (C4) only if single-agent runs overflow; Argilla set-up for
judging (H2); blind usefulness rating of the 50 B8 commands (B6 rubric); column order on 3 two-column papers (D1). Optional: Omen tunnels and Langfuse copy (T2, T3); `save_tool` (C7).

## Where the details are

`docs/milestones-1-2.md` (triaged build plan, milestones 1–2) · `tests/RESULTS.md` (every result) · `docs/decisions-after-tests.md` (why each decision) · `docs/plan.md` (the
design, to be revised) · `docs/provenance-model.md` (log and graph schema) · `docs/research-open-test-findings.md` (follow-ups for partial tests) · `thesis_pipeline.html` (overview page) · `llm-setup/` (the serving stack).
