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
| Orchestrator | `Qwen/Qwen3.8-27B-FP8` @ `017b9c7`, GPU 0, 65,536 context, thinking off, `max_tokens` 4096 (a conclude reply up to 16,384 within the context, 1.13: a whole answer to a corpus-wide question needs more) | A2, A3, B3, L1, L2 |
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
| Manifest hash | Take the `corpus/manifest.json` hash from an LF checkout (`22e9471b…`); `.gitattributes` now forces LF on the corpus, D1 papers, schemas, fixtures, `*.jsonl`, the prompt and scripts | D5, m1-core |
| F1 acceptance | Whole path passed on Slurm job 7288: orchestrator, parser, Landlock/seccomp sandbox, `claim`, and broker. One exact quote was accepted at step id 1; event/claim chains verified; corpus stayed read-only and network access was blocked. | F1, `tests/F1/run-001/summary.json` |
| `claim` under Landlock on Ceph | The repo path `agent/bin/claim` worked under Landlock + seccomp on Ceph with the inherited broker descriptor; one claim was accepted at step id 42 and its log hash verified. The `smoke-01` agent run did not call `claim`, so this result is from the direct sandbox check. | M1-claim-ceph, `$RUNS/claim-client-smoke.jsonl` |
| First real M1 runs | All four runs verified and all graph/PROV/query commands exited successfully. All reached budget with empty answers; actual tokens were 470,077–498,229 against configured 400k. Largest prompt was 38,470 (<61,440), so C8 was not triggered. One accepted quote in c3-on-2 was checked against its cited paper and supports its dataset claim. | M1-real, `tests/M1-real/` |
| Real attach | `attach` executed on c3-off-1 and completed cleanly, but had 0 facts to process. Per-fact 6-step/60k-token budget remains unmeasured. | M2-attach-real, `$RUNS/c3-off-1/attach.json` |
| Column order | Docling keeps two-column reading order: 0/10 papers interleaved; a quote across one of the 4 footnote/caption splits at page breaks is rejected (`not_found`) | D1-col, `test_anchor` |
| Anchors | Selector = file sha256 + raw offsets + exact/prefix/suffix; offsets are tried first, else the retyped quote is matched after normalising (NFKC, whitespace, dashes, quote marks, entities) and mapped back to raw offsets; minus signs are kept and a quote may not cut a number (`partial_number`); case-sensitive | `agent/anchor.py`, 1.5, `test_anchor` (82) |
| Broker | One process per run; one hash chain over `events.jsonl`, `claims.jsonl` a checked copy of its claim records; claim ids `claim-NNNNNN`; rejection reason returned to the agent (`not_found`, `partial_number`, `ambiguous`, `unknown_file`, …) | `agent/broker.py`, 1.6, `test_broker` (30) |
| Main loop | mini-swe-agent 2.4.6 subclass (`agent/loop.py`). A step is one model reply; the token budget sums `total_tokens` over all calls. Repeats counted consecutively after collapsing whitespace. After the budget or a context-full 400: 2 more replies, no commands; on context-full, old outputs become stubs (claim replies kept), then old replies are shortened, the third 400 ends the run; never the same request twice. The wrapper times commands out itself (120 s, process group, exit 124) because uutils `timeout` fails under Landlock+seccomp; `ulimit -v` set in the shell. `agent run` defaults to Landlock and refuses without it; `unsandboxed` is for tests only and recorded in `config.json`. API key only from `$LITELLM_MASTER_KEY`, never logged. After M1-real (prompt v2, `LoopSettings` in `config.json` `loop`; v1 keeps the old loop): conclude replies decoded under the reply schema (`extra_body.structured_outputs`, parse `guided_answer`, `used.decoding` and `used.max_tokens` in the call record) with up to 16,384 reply tokens, fitted to what the context leaves; a guided call the server refuses (a 4xx that is not context-full) is recorded (`guided_decoding_rejected`) and asked again decoded freely, as are later conclude replies; the agent keeps `scratch/answer-draft.json`, taken when a run ends without an answer; notices at 50/75/90 % of either budget; outputs older than the last 8 commands become stubs (last 4 after a prompt over 45k tokens), count in each call record, the text first shown kept in `trajectory.json` (`extra.original_content`) so every `prompt_sha256` can be rebuilt; six identical commands end research (`repeats`). Provisional budget 60 steps / 2M tokens (`agent run` defaults, `m4-72.json`); `--prompt-version v1` defaults to the M1-real budget (150 / 400k) and wording | 1.8, 1.13, 1.15, `test_loop`, `test_loop_v2`, M1-loop, M1-real |
| Answer and records | The agent writes `{rows, notes}`; the harness adds concept hash, `claims: []`, `origin`, and rejects unaccepted claim ids; NaN/Infinity, non-list facts and deep nesting are answer problems, never crashes. No valid final answer → the draft if it passes the same check: `answer.json` notes start "harness: answer taken from the agent's draft file (exit status X)", `answer_from_draft` coverage record with the draft's sha256 and its copy `answer.draft.json` (run root; `agent verify` checks it); else empty `answer.json` + `no_final_answer` (with why the draft was not taken). `Outcome.answer_from` = final / draft / none. PROV: `ours:answerSource` (`final_answer`, `draft`, `none`, `unknown`) on the answer, which is `prov:wasGeneratedBy` the final-answer call or that coverage record (`prov:wasDerivedFrom` an `ours:AnswerDraft`); after an attach step the answer is generated by the attach activity and derived from `answer-research` (answer.research.json), which takes those links. `agent_tool` records list `used.files_read` (`p<N>.md` names and ACL Anthology ids in the command); the answer's model call has `custom_metadata.final_answer`; a claim step is a command that sent at least one claim | 1.9, 1.12, 1.13 |
| Prompts | `agent/prompts/system-v2.txt` (default since 1.13: real file names, claim where found, draft answer, budget plan and notices) and `attach-v2.txt` (v2's corpus paragraph and claim rules, verbatim); `system-v1.txt` and `attach-v1.txt` kept byte for byte for the M1-real runs (test pins the hashes): `agent run --prompt-version v1` reproduces them (loop, wording and budget), and `agent attach` follows the run's version; baseline = the prompt minus the claim block (`system-<v>.diff`, tested); a test fails if the broker gains a rejection reason a research or attach prompt does not explain | 1.10, 1.13, `test_prompts`, `test_attach` |
| Concepts, attach, batch | Concepts proposed corpus-blind (≤5, one repair) and picked into `concepts/<qid>/concept.json` with a `concept_pick` record. Attach step uses `claim` with `origin="attach"`, per-fact budget 6 steps / 60k tokens (freeze after 1.13); prompt version and conclude decoding default to the run's (config `attach.conclude_decoding`), its conclude reply is decoded under the result schema (refusal → free), and a fact left without a result gets the last of its own accepted claims with exactly its s/p/o (`attach_from_claim` coverage, `how` in attach.json). Batch runner never resumes a cut run in place: it marks it (`coverage`, `job_time_limit`) and reruns it fresh, up to 3 attempts; the manifest's `prompt_version` and `conclude_decoding` reach runs and attach steps | 2.1–2.5, 2.9, 1.13 |
| Graph and PROV-O | `graph.json` one edge per accepted claim, free predicates mapped to CS-KG/DBLP or `ours:`; `graph.ttl` deterministic (rdflib 7.6.0); attach records marked `origin = "attach"` | 2.6–2.8, `docs/milestones-1-2.md` |
| Subagents | `spawn` built (2.12, `agent/spawn.py`), off unless `agent run --spawn on` (manifest `spawn`; the 72 runs keep it off unless decided otherwise; recorded in `config.json` `spawn`). `spawn --task ... [--files a.md,b.md] [--steps N]` over an inherited SPAWN_FD (one reply pipe per request, so `spawn ... & spawn ... & wait` works); 2 at once on `sub-model-1`/`-2`, the rest queued; each a research loop on the sub model (32,768 context, 15 steps / 300k tokens, provisional: `--spawn-steps/--spawn-tokens`, manifest `spawn_budget`; `sub-v1.txt`, no nested spawn, claim iff claim_on, own scratch), at most 20 per run; its records and claims in the run's chain as `sub-NN` with `spawned_by_step`; result = its summary plus the claims it recorded, `ok` for every subagent that started (its status says how it ended); its failure is `subagent_error`, never the run's `run_error`. `spawn` is on the PATH (`agent/spawn-bin`) only when on, in both conditions; a masked spawn result keeps agent id, status and (claim_on) claim ids alike in both. A command that starts a subagent gets 1,800 s (known from its spawn channel); on SIGTERM subagents get at most 15 s in all. The parent's budget counts its own calls; `agent verify` gives the run total and per agent (attach apart). Not yet run on the real model (C4) | 2.12, `test_spawn` |

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
| Anchor library | Fixed in `agent/anchor.py` (row 1.5, m1-core); see Decided "Anchors". B5 remains open: one real claim passed, but there were no rejections to evaluate case sensitivity or a minimum quote length. |
| Run budget | Provisional 60 steps / 2,000,000 tokens (`agent/rundir.py`, `agent run`, `m4-72.json`; e2e build plan, 13 Oct); the user freezes it after the Slurm e2e test. Attach stays 6 steps / 60k per fact. |

No further infrastructure session is planned: B0, S7, L7, L8, C2b and D5 closed on 10 Oct.

## Later (need the harness)

Real run budget and answer completion (M1-real: all four trials ended at the configured 400k budget, with actual totals 470k–498k and no answer; both conclude replies of every run were commands). The fix is built but has not met the real model: check on Slurm that vLLM/LiteLLM honour `structured_outputs` with the reply and attach result schemas (count `guided_decoding_rejected` records; if the server refuses, set `conclude_decoding` in the manifest), how often a conclude reply is still cut (`finish_reason` length) per condition and how long the longest takes (16,384 tokens at 41.6 tok/s is ~400 s, inside the 600 s proxy timeout), how often the draft is the answer and how often attach takes a fact from a claim (`attach_from_claim`) per condition, and how far 60 steps / 2M tokens go with masking; then freeze the budget. C8 was not triggered: largest prompt 38,470 and no context-full 400; masking (1.15) is on anyway for the larger budget. B5 remains open: one accepted quote supports its claim, but the sample has no rejected claims. Attach per-fact budget remains open because the real attach had no facts. Re-execution (C5) and replay (C6); `spawn` is built (2.12) and tried on Slurm (C4) only if single-agent runs overflow; Argilla set-up for
judging (H2); blind usefulness rating of the 50 B8 commands (B6 rubric). Closed: column order (D1-col, now in Decided). Optional: Omen tunnels and Langfuse copy (T2, T3); `save_tool` (C7).

## Where the details are

`docs/milestones-1-2.md` (triaged build plan, milestones 1–2) · `tests/RESULTS.md` (every result) · `docs/decisions-after-tests.md` (why each decision) · `docs/plan.md` (the
design, to be revised) · `docs/provenance-model.md` (log and graph schema) · `docs/research-open-test-findings.md` (follow-ups for partial tests) · `thesis_pipeline.html` (overview page) · `llm-setup/` (the serving stack).
