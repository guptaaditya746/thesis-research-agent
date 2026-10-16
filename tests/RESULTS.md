# Research agent infrastructure and behaviour tests

| id | date | config | pass/fail | numbers | notes |
|---|---|---|---|---|---|
| A1 | 2026-10-08 | Slurm job 7048, gammaweb08, 3×A100 40 GB; setup repo local venv | PASS | 3×40960 MiB; driver 580.159.04; CUDA 13.0; Python 3.13.12; torch 2.11.0+cu130; vLLM 0.21.0; 16 CPUs; 503 GiB RAM; Ceph 3.1 PiB free | Node-local environment import passed and detected 3 GPUs. System Python 3.14.4 lacks torch/vLLM. `/scratch` absent; `/tmp` has 231 GiB free. HF cache totals 365 GB. See `tests/A1/node.txt`. |
| A2 | 2026-10-09 | `final-final-llm-setup` profile plus direct current-Qwen tests; vLLM 0.21.0 on gammaweb08 | PASS (profile and current candidates) | Heavy: 65,024; 65,152 KV tokens, 1.00×. Lite: 32,768; 127,728, 3.90×. Qwen3-30B-A3B-Thinking-2507-FP8: 32,768; 64,848 KV, 1.98×; 11.47 s warm weight load. Qwen3.8-27B-FP8: 65,536; 79,371 KV, 1.21×; 179.82 s warm weight load, 28.9 GiB GPU memory, ~8m27s total startup. | Existing Heavy/Lite/Embed data is reused from `final-final-llm-setup`; current Qwen3.8 is the official latest compact candidate checked on Hugging Face. See the appendices "A2 recorded_profile.md" and "A2 model_candidates.md", and `qwen38-serve.log`. |
| D3 | 2026-10-08 | `tests/D3/anchor.py`; 200 random spans in 20 actual corpus outline files; deterministic seed | PASS | offsets 200/200; after 10-char prepend, quote resolution 200/200; deleted quote broken 200/200; duplicate quote disambiguation PASS | See `tests/D3/verify.py` and `tests/D3/anchor.py`. |
| D4 | 2026-10-08 | Direct compute-node run on 337 corpus Markdown outlines (2,132,514 bytes), no bwrap per instruction | PASS | `grep -il retrieval`: 0.901 s / 53 files; `grep -n -i evaluate | wc -l`: 1.008 s / 649 lines; Python regex `\\bevaluat\\w*`: 0.917 s / 1,909 matches | Corpus is `final-final-frontend/UI/files/harness/corpus_data/outlines`; see `tests/D4/benchmark.py`. |
| A6 | 2026-10-08 | Slurm job 7048 on gammaweb08 | NOT RUN | `bwrap` absent; `unshare -rn` denied (`uid_map: Operation not permitted`) | User requested compute-node execution without a sandbox; no sandbox was launched. See `tests/A6/attempt.txt`. |
| A3 | 2026-10-09 | Heavy setup model (prior run) and Qwen3.8-27B-FP8, max_model_len 65,536; explicit 200-token summary; thinking disabled | PASS | Setup Heavy: prompt 16,008/32,008/48,008/60,008; TTFT 1.81/4.06/7.74/11.20 s. Qwen3.8: prompt usage 16,050/32,050/48,050/60,050; TTFT 6.30/12.59/20.03/26.05 s; prefill 2,538/2,542/2,397/2,303 tok/s; total 11.23/17.69/25.26/31.39 s; 200 output tokens at all lengths. | Both reached 60k with prompt usage within 0.32% of target. Qwen3.8 initial no-query attempt yielded a 2-token “No” at 48k; corrected prompt explicitly asks for a summary. Final metrics and generated summaries are in tests/A3/qwen38-longprompt.jsonl; the no-query run is preserved separately. |
| A4 | 2026-10-08 | Heavy/Lite setup models; direct compute-node HTTP; A4 request sizes | PASS | Heavy N=2/P=48k: 2/2 complete, KV peak 73.9%, 0 preemptions, waiting peak 1, mean/max latency 16.71/22.26 s. Heavy N=4/P=32k: 4/4, KV peak 98.7%, wait peak 2, 0 preemptions, mean/max 13.53/19.35 s. Lite N=6/P=24k: 6/6, KV 94.7%, wait peak 4, 0 preemptions, mean/max 27.31/32.16 s. Lite N=8/P=16k: 8/8, KV 89.0%, wait peak 1, 0 preemptions, mean/max 13.19/18.33 s. | Waiting returned to zero after each test. Heavy N=2 KV peak missed because its first scraper filter did not match vLLM 0.21's kv_cache_usage_perc; other metrics were captured. Per-request data and metric logs under tests/A4/. |
| A5 | 2026-10-09 | 20 sequential requests; 2k prompt/300 max output; temp 0.7; setup Heavy/Lite and Qwen3.8-27B-FP8 | PASS (tested models) | Heavy 130.43 tok/s; Lite 68.29 tok/s; Qwen3.8 41.58 tok/s single-sequence mean. Lite N=6 aggregate 55.96 tok/s wall-clock. | Qwen3.8 used thinking disabled; prompt usage was 2,018–2,019 tokens. For 90k generated tokens, estimates are 11.5 min Heavy, 22.0 min Lite, and 36.1 min Qwen3.8. Logs: tests/A5/. |
| A7 | 2026-10-08 | Same deterministic request direct to non-thinking Heavy vLLM and through LiteLLM | PARTIAL | reasoning_content, content, finish_reason, usage all equal; direct 1.670 s, proxy 0.686 s | Response fields match, but enable_thinking=false remains inconclusive because the selected checkpoint is non-thinking. See tests/A7/result.json. |
| D1 | 2026-10-09 | 10 ACL/EMNLP 2025 PDFs; cached GROBID TEI rendered to Markdown; Docling 2.110.0 PDF pipeline with OCR disabled and table structure enabled | PARTIAL | Docling: titles match DBLP 9/10, author order 9/10, headings 10/10, reference entries detected 10/10, Markdown table rows 10/10; 998.55 s total, 99.85 s mean per paper. GROBID renderer: titles 9/10, author order 9/10, headings/references 10/10, Markdown table rows 0/10. | Marker unavailable; two-column flow has not received visual review. Docling is currently the only tested path with recovered Markdown table rows, but its higher latency and column flow still need review. GROBID timings measure cached-TEI rendering only, not PDF-to-TEI conversion. Per-paper matrix and logs: tests/D1/. |
| B1 | 2026-10-09 | 50 prompts; Qwen3-30B-A3B-Thinking-2507-FP8; vLLM 0.21.0; 8192 max tokens; nominal thinking on/off | FAIL (format, thinking-on condition) | One fenced bash block: 26% in both measured conditions; reasoning nonempty 100%; thinking-on mean/p95 reasoning tokens 988/1,910; no code block missing from content | Model card states Thinking-2507 supports only thinking mode, so the off-mode comparison is invalid. The thinking-on format failure stands. See the appendix "B1 interpretation.md" and raw outputs in `tests/B/B1/`. |
| D2 | 2026-10-09 | Docling 2.110.0; same 10 ACL/EMNLP PDFs and OCR/table settings as D1; independent second conversion | PASS | 10/10 output SHA-256 hashes identical | First/second conversion hashes and per-paper timing logs are in tests/D2/. |
| B6 | 2026-10-09 | Manual by-eye rating of B1's 50 prompts; Qwen3-30B-A3B-Thinking-2507-FP8 | PARTIAL | Sensible next command: 39/50 (78%) thinking on, 38/50 (76%) off; mean latency 7.74/7.54 s; mean parsed reasoning tokens 988/958 | Does not meet one-block compliance from B1. Ratings and criterion are recorded in the appendix "B6 manual_review.md". |
| B2 | 2026-10-09 | Same 50 prompts; Qwen3-30B-A3B-Thinking-2507-FP8; thinking on | PASS (cutoff criterion) | `max_tokens`: 1,024 → 14/50 cuts; 2,048 → 3/50; 4,096 → 0/50; 8,192 → 0/50; 16,384 → 0/50. Smallest tested limit below 2% cuts: 4,096. Mean/p95 reasoning tokens at 4,096: 1,028/2,292. | One-block compliance remained 16%, 16%, 20%, 26%, 20% respectively; increasing the cutoff did not resolve formatting failures. Per-prompt outputs and summaries: tests/B/B2/. |
| C1 | 2026-10-09 | Fake-agent fixed commands on gammaweb08; direct compute-node execution, no bwrap; 8,192-byte stdout/stderr cap | PASS (capping and chain) | Longest paper 19,185 B; stdout 100,001 B; stderr 100,000 B; `yes | head -c 50000000` produced 50,000,000 B; each context observation ≤8,240 B (8 KiB + stub); hash chain verified 4/4 | Full outputs retained under tests/C1/run/work/out; events include `stdout_path`, `stdout_head`, and `prev_hash`. No sandbox was used. Context-token counts and command logs: tests/C1/run.log. |
| B3 | 2026-10-09 | Qwen3.8-27B-FP8, thinking disabled; 20 prompts with 6.6 KB prior output and 20 multi-step invitations | PASS | Exactly one bash block: 19/20 (95%) long-output prompts; 20/20 (100%) multi-step prompts; no multiple blocks; prose-only 1/20 and 0/20 | Meets ≥95% for both groups. This is the current official Qwen candidate, used in place of unavailable planned Qwen3-Coder weights. Raw outputs and counts: tests/B/B3/. |
| B4 | 2026-10-09 | 10 turns of `(no matches)`, no nudges; Qwen3.8-27B-FP8 thinking off and Qwen3-30B-A3B-Thinking-2507-FP8 thinking on | PASS (strategy change); loop risk found | Qwen3.8: 4 unique commands by turn 4; no repeat in 10 turns. Thinking model: 4 unique commands by turn 4; first repeated command at turn 5; one empty command at turn 4 ended by `length`; then repeated `claim` command turns 5–10. | Both changed strategy before turn 4, but the thinking model entered a repeated-claim loop. Loop detection should ship in v1. Raw turns/logs in `tests/B/B4/`. |
| C2 | 2026-10-09 | Qwen3.8-27B-FP8; vLLM 0.21.0; 60 sequential replay requests, masks before 20/40/60; max prompt 1,665 tokens | PARTIAL | Prefix-cache query/hit counters: 45,720/20,384 tokens; hit counters advanced on 24/60 steps. Between-mask hit-token increments: 10,976 (2–19), 4,704 (21–39), 4,704 (41–59). TTFT steps 19/20/21: 0.098/0.110/0.118 s; steps 39/40/41: 0.173/0.113/0.118 s; steps 59/60: 0.172/0.111 s. | Cache hits rose between masks and paused on each boundary; prompt history was too short to verify seconds-long re-prefill timing or high sustained hit rate under realistic context. Mamba `align` prefix caching is experimental in vLLM for this model. See the appendix "C2 result.md" and per-step `steps.jsonl`. |
| B5 | 2026-10-09 | 30 quoted-claim prompts; claim stub execution planned inside bwrap | NOT RUN | 0/30 executed/verified | `bwrap` is unavailable and user requested direct compute-node work; generated model commands were not run unsandboxed. Quoting correctness remains unmeasured; see `tests/A6/attempt.txt`. |
| B7 | 2026-10-09 | Optional tool-output presentation comparison | NOT RUN | — | Optional test deferred while infrastructure and model behavior tests were prioritized. |
| C3 | 2026-10-09 | First end-to-end ACL 2025 first-author run; 150 steps/400k tokens | NOT RUN | — | Minimal agent harness is not present in this repository yet; required per-command bwrap is unavailable on the node. |
| C4 | 2026-10-09 | Five concurrent subagents on SUB server | NOT RUN | — | Depends on the harness `spawn` implementation and a same-node SUB server; neither was built/launched for this run. |
| C5 | 2026-10-09 | Re-execute C3 commands against frozen corpus | NOT RUN | — | Depends on a completed C3 fixture and bwrap execution environment. |
| C6 | 2026-10-09 | Forced loop and 60-step budget behavior | NOT RUN | — | Depends on harness loop detection/budget events and a safe per-command execution boundary, neither present in this repo. |
| C7 | 2026-10-09 | Tool invention round trip | NOT RUN | — | Depends on harness `save_tool` implementation, which is not present. |
| T1 | 2026-10-09 | `omen-tunnels` and `omen-tunnels-external` dry runs on gammaweb08 | PASS | Thesis Postgres gateway target 55433 → 56433; `list` reports gateway ports +1000 | Output saved in `tests/T1/dry-run.txt`. |
| S4 | 2026-10-09 | GPU allocation 7048, gammaweb08; direct HTTPS checks | PARTIAL | example.com 200; huggingface.co 200; pypi.org 200; no proxy variables; Apptainer/Singularity absent | Direct egress works, so the assumed network isolation is false. Apptainer check and A6 sandbox remain unavailable. See `tests/S4/egress.txt`. |
| T2 | 2026-10-09 | GPU allocation 7048; external laptop helper and compute legacy helper; tracing, Thesis Postgres/Redis, MinIO, ClickHouse HTTP | PARTIAL (mapping mismatch diagnosed) | Laptop active SSH `-R` ports are legacy (29304/55433/56380/49000/58123); compute external helper targets +1000 ports, which were refused. Switching the compute hop to base `omen-tunnels` reaches all five: tracing 200, Postgres SSL probe `N`, Redis `NOAUTH`, MinIO 403, ClickHouse 200. | Laptop's installed `omen-tunnels-external` appears not to apply the +1000 offset (stale wrapper or different executable); install/update the repo wrapper on laptop before retesting external-to-external. Current compute hop uses the base helper to match laptop's legacy ports. Redis is reachable but PING needs auth. Logs: `tests/T2/gateway-legacy-ports.txt`, `compute-legacy-mapping-check.txt`, `compute-mapping-switch.log`. All probes were read-only. |
| T4 | 2026-10-09 | Second `srun --overlap` step in job 7048, same host | PASS | Second start returned “Already running”; first tunnel remained up | See `tests/T4/second-start.log` and `first-status-after.txt`. |
| L1 | 2026-10-09 | `agent-3x40.yaml`, direct foreground setup stack in Slurm job 7048 on gammaweb08 | PASS (in-allocation) | all ready 11m14s; orch 5m20s / 79,371 KV tokens / 35,771 MiB; SUB x2 10m57s / 64,848 KV tokens each / 37,311 MiB each; doctor 0 failures | `orch-model`, `sub-model`; status API reports both SUB replicas healthy. Started in existing allocation rather than a new `sbatch` job. Details in `tests/L1/`. |
| L2 | 2026-10-09 | Agent layout through LiteLLM :4000; Qwen3.8-27B-FP8 | PARTIAL | thinking switch honored; response fields equal direct for on/off. B3: 90% one block on long-output group, 100% multi-step; reasoning empty in both | Proxy B3 misses the 95% long-output threshold; retain lenient parser / format recovery. `tests/L2/`. |
| L3 | 2026-10-09 | Two SUB replicas behind LiteLLM; N=4/P=32k and N=8/P=16k, 300 outputs; retest with `max_num_active_seqs=3` and `least-busy` | FAIL (routing balance) | Original: N4 4/4, p95 14.88s, 0 preemptions; N8 8/8, p95 13.14s, preemptions occurred. Tuned N8 runs: 8/8 each, 0 preemptions, p95 latency 17.67s and 20.12s; peak observed KV 49.9%; final counter deltas split 5/3 then 8/0 | Active-sequence limit removed N8 preemptions, but least-busy did not maintain a 60/40 replica split. Retain the concurrency limit and fix/replace routing before relying on fan-out capacity. Raw runs and metric snapshots are in `tests/L3/`. |
| S1 | 2026-10-09 | CPU timeout and live-stack check inside job 7048 | PARTIAL | infinite loop stopped at 120s (`rc=124`); status API and all backends answered after; memory.current 67,931,783,168 B, allocation 64G | Memory allocation and 20G tmpfs cases skipped because the live job was already at its requested memory limit; `/tmp` is tmpfs. Status was `busy`, but each model health was healthy, running/waiting 0. See `tests/S1/`. |
| S3 | 2026-10-09 | Uncredentialed local-port probes, job 7048 | FAIL | raw vLLM :8001/:8002/:8004 `/v1/models` returned 200; status :8010 `/v1/status` returned 200; LiteLLM :4000 `/v1/models` returned 500; Omen forwarded ports reset | No secret-like environment names appeared. Proxy 500 traceback says `ModuleNotFoundError: No module named 'prisma'`; traces/data ports did not answer. Raw vLLM is reachable without auth. See `tests/S3/anonymous-probes.txt`. |
| L4 | 2026-10-09 | Proxy SUB request during owned replica-2 process shutdown | PARTIAL | client got 922 completion tokens, 7.55s total; no proxy retry line found; supervisor restarted backend and marked healthy after 2m30s | SIGTERM allowed the active request to finish before the process exited; no retry behavior was observed. Details in `tests/L4/`. |
| S2 | 2026-10-09 | Fake hash-chained run in Slurm job 7050; backend restart observed in job 7048 via L4 | PARTIAL | `scancel` produced final `run_aborted`; chain verified 4 events. L4 backend returned healthy 2m30s after restart | Job-end event log passes. Backend restart measured in the existing allocation; the planned separate new GPU job was not started. See `tests/S2/` and `tests/L4/`. |
| T3 | 2026-10-09 | 8-hour laptop sleep / tunnel heartbeat | NOT RUN | — | T2 service ports reset, so a stability run would not measure a working tunnel. Awaiting laptop-side checks before this can start. |
| L5 | 2026-10-09 | Compile-cache observation from L1 and L4 | PARTIAL | orch ready in 5m20s, versus 8m27s in round-one cold-start record; SUB-2 restarted in 2m30s | vLLM's default compile cache path is already Ceph (`~/.cache/vllm/torch_compile_cache`). This is not a controlled two-job cache experiment; no `.env` cache override was needed or added. |
| S5a | 2026-10-09 | gammaweb08, Slurm job 7048 | PASS | kernel 7.0.0-22-generic; Landlock ABI 8; LSM includes landlock | ABI supports TCP, signal and abstract-socket rules. `tests/S5/kernel.txt`. |
| S5b | 2026-10-09 | ctypes Landlock sandbox, job 7048 | PASS (tested checks) | Python/grep pass; corpus read-only; internet and ports 8001/8002/8004/4000/8010 denied; scratch writable; home hidden; timeout rc=124 | Exact wrapper invocation and output: `tests/S5/S5b-checks.txt`. No `/corpus` mount on this node; used the recorded Ceph corpus path. |
| S5c | 2026-10-09 | Python 3.13 agent venv and pinned rg/jq under `$AGENT_ROOT` | FAIL (immutability) | 6,221 files / 275 MB; wheel install and import pass; absent wheel fails cleanly; manifest verifies; sandbox `chmod -R u+w` succeeds | Landlock cannot prevent chmod. Restore mode and manifest verification recorded. `tests/S5/`. |
| S6 | 2026-10-09 | Escape probes under Landlock ABI 8 | PARTIAL | kill-0 denied; sensitive file open denied; UDP sent; pathname Unix socket allowed; abstract socket denied; background child cleaned | See the appendix "S6 findings.md"; pathname sockets and UDP remain gaps. |
| S1b | 2026-10-09 | `ulimit -v` at 2/4/8/16 GiB, stack loaded | PASS (memory guard) | numpy/pandas imports succeeded at all four limits; 100 GB allocation raised MemoryError at all four; cgroup memory.max=max; anon 10,293,456,896 B and file 57,997,000,704 B | Values from `tests/S1b/`; allocation and imports were checked in separate corrected runs. |
| L6 | 2026-10-09 | LiteLLM localhost:4000; ORCH Qwen3.8, SUB 2 replicas | PARTIAL | 54,610 prompt + 4,096 output tokens completed in 112.52 s (120 s proxy timeout); 20/20 schemas valid; seed outputs 1/10 distinct alone and under load | Only 7.5 s below timeout. The seventh queued probe returned in 0.41 s while backend port 8004 was idle; queue wait accounting remains unproven. Backend metrics (28 samples per replica) showed 8002 max 3 running / 3 waiting / 0 preemptions while 8004 remained idle. Seeded outputs were identical, but request logs do not prove the seed reached vLLM; vLLM also has no per-request schema log. See `tests/L6/`. |
| R2 | 2026-10-09 | Ceph append, 8 processes × 10,000 lines, fsync each line | PASS | Both modes: 80,000/80,000 valid, 0 corrupt; O_APPEND p50/p99 4.22/104.38 ms, 772 s; O_APPEND+flock 4.11/64.76 ms, 911.5 s; 696,315,600 B each | Flock lowered p99 latency but increased elapsed time by 18%. Detailed results: `tests/R2/`. |
| R3 | 2026-10-09 | vLLM 0.21.0, isolated Python 3.13 environment | PASS | two unique model snapshots pinned across three vLLM instances; `uv sync --locked` succeeds; 40 pytest pass; Ruff and profile validation pass | Revision pinning and offline environment changes are on submodule `agent-layout`; see `tests/R3/models.txt`. Stack not restarted. |
| H1 | 2026-10-09 | Broker outside sandbox, Unix socket in scratch | PASS (prototype) | 100 claims; all assigned current step 42 despite forged 999999; chain valid; head `ad4e4374e0f3bd9e52072674b12ddbf8ae22c3907588bff098cde81d3ba006a` | Private log unreadable/unwritable from sandbox; head copied to `tests/H1/job-log.txt`. See `tests/H1/`. |
| B0 | 2026-10-10 | Fresh Python 3.13 toolchain root on job 7048, gammaweb08 | PASS | Build 105.33 s; 266 MB; 5,867 file hashes and 6,526 mode entries; verifier pass | Includes pip, hash-checked rg/jq, and networkx/tabulate wheels. See the appendix "B0 result.md". |
| S7 | 2026-10-10 | Landlock ABI 8 + x86_64 seccomp BPF, job 7048; inherited `CLAIM_FD` | PASS | IP sockets, AF_UNIX, AF_NETLINK, socketpair, TCP targets, and UDP denied with EPERM; allowed toolchain checks pass; 100/100 claims assigned step 42; chain verifies | `chmod u+w` succeeds but content append is denied; restored mode and both manifests verify. See the appendix "S7 findings.md". |
| L8 | 2026-10-10 | LiteLLM proxy `:4000`, Qwen3.8 ORCH 65,536 and Qwen3 SUB 32,768 | PASS | All 3 overflow requests returned HTTP 400 `BadRequestError` / `ContextWindowExceededError`; ORCH 70k+1 reports 65,536+1; SUB 34k+1 reports 32,768+1; ORCH 64k+2k reports 63,537+2,000 | Error bodies include the limit and token counts, so the harness can stop as “context full.” See `tests/L8/errors.json` and the appendix "L8 findings.md". |
| C2b | 2026-10-10 | Qwen3.8 ORCH through LiteLLM; 30k-token paper-text prompt, 20 steps unmasked and masked at 10; 300 output tokens | PASS (measurement) | Block size 784; cold 30,035-token prompt TTFT 12.03 s, 0 hits; warm steps mean 0.351 s and 29,792–30,576 hits; mask step 10: 47 tokens, 0.109 s, 0 hits; all 40 outputs exactly 300 tokens | Cached prefix hit/query ratio 93.7% unmasked and 86.7% masked. Cold prefill ~2,498 tok/s. Masking reduced context and TTFT sharply. See the appendix "C2b findings.md" and `tests/C2b/steps.jsonl`. |
| L7 | 2026-10-10 | LiteLLM proxy `:4000`, 2 SUB replicas at `:8002`/`:8004`; 24 sequential + 8 concurrent, seed 90210 | PASS (pinned aliases) | timeout 600 s; least-busy 24/0 sequential, 5/3 concurrent; simple-shuffle 15/9, 1/7; usage-based 12/12, 8/0; pinned `sub-model-1`/`sub-model-2` concurrent 4/4; proxy/direct seeded output pairs identical | Shared routing did not reliably balance concurrent requests. Keep `sub-model` and expose pinned replica aliases for fan-out. Generated configs include the 600 s timeout. 41 submodule tests and Ruff pass. See the appendix "L7 findings.md". |
| B8 | 2026-10-10 | Qwen3.8-27B-FP8 ORCH, strict one-block-only prompt; same 50 B tasks | PASS (format off and low effort), PARTIAL (default xhigh) | Thinking off: 50/50 blocks, mean 0.63 s. Thinking on at default xhigh, 4,096 max tokens: 48/50 (96%), 2 length cuts, mean 18.46 s; at 8,192: 47/50 (94%), 3 cuts, mean 31.05 s. Thinking on at low effort, 4,096 max tokens: 50/50, no cuts, mean 2.51 s. | Low effort resolves the observed format/cutoff problem on this 50-task set. Use low as the routine orchestrator setting; still rate command usefulness before treating quality as settled. Raw outputs/summaries in `tests/B/B8/`. |
| A7b | 2026-10-10 | Qwen3.8-27B-FP8, direct vLLM :8001 vs LiteLLM :4000, same request with thinking on/off | PASS | reasoning, content, finish reason, usage all equal in both modes; reasoning absent off and present on; proxy honored switch | Closes the original A7 uncertainty for the current Qwen3.8 profile. Raw responses: `tests/A7/qwen38-result.json`. |
| B9 | 2026-10-10 | Qwen3.8; `structured_outputs.regex` requiring one bash fence; 10 existing B tasks | PASS (thinking off), PARTIAL (thinking on) | Thinking off: direct 10/10 (mean 1.89 s), LiteLLM 10/10 (mean 0.93 s). Thinking on: direct 9/10 (1 length cut; mean 34.90 s), LiteLLM 8/10 (2 length cuts; mean 46.57 s). | Proxy regex passthrough works when using the valid LiteLLM key; initial “No connected db” was caused by the placeholder key. Thinking-on cutoffs remain, so retain an independent format validator. Raw outputs/summaries in `tests/B/B9/`. |
| D5 | 2026-10-10 | Docling 2.110.0, OCR off, tables on; all 337 PDFs; Slurm job 7140 | PASS (one exclusion) | 336/337 converted (28.6 MB Markdown), all source and output hashes verified, tree read-only; 4 h 52 min wall | `p38` is a scanned PDF (222 bytes without OCR) and is excluded by user decision. Corpus on Ceph; manifest in `corpus/manifest.json`. See the appendix "D5 findings.md". |
| F1 | 2026-10-13 | Slurm job 7288, `agent-3x40`; orchestrator → parser → Landlock/seccomp sandbox → `claim` → broker, frozen Ceph corpus | PASS | 164 papers contain “retrieval”; 1 claim stored at step id 1; quote and chain verified; corpus read-only; network blocked; agent root verified; model 8.43 s (305 prompt / 242 completion tokens) | Qwen3.8 returned one fenced bash block. Full record: `tests/F1/run-001/summary.json`; event and claim heads are recorded there. |
| M1-claim-ceph | 2026-10-13 | Slurm job 7288; `agent/bin/claim` from repo under Landlock + seccomp on Ceph, inherited claim FD; agent smoke `smoke-01` also attempted | PASS (repo client path) | Direct check: 1 claim accepted at step id 42; hash valid; process group cleaned up. Agent smoke verified but used 3/3 command steps exploring and produced 0 claims | The smoke did not invoke `claim`; direct sandbox check confirmed the repo path works, so no agent-root fallback was needed. Log: `$RUNS/claim-client-smoke.jsonl`; agent smoke: `$RUNS/smoke-01`. |
| M1-real c3-on-1 | 2026-10-13 | Slurm 7288, Qwen3.8-27B-FP8, claim_on, temp 0.7, seed 1, configured 400k tokens / 150 steps | PARTIAL (verified; no answer) | 28 steps/model calls; 26 commands; 474,372 tokens; 248.402 s; 0 claims; max prompt 34,842; 0 timeouts/nonzero commands/repeats; no answer rows | Ended at token budget, empty answer; verify PASS. All five query commands and graph/PROV export exited successfully (claim queries empty). Quote review N/A. Logs at `$RUNS/c3-on-1`; small artifacts in `tests/M1-real/c3-on-1/`. |
| M1-real c3-on-2 | 2026-10-13 | Slurm 7288, Qwen3.8-27B-FP8, claim_on, temp 0.7, seed 2, configured 400k tokens / 150 steps | PARTIAL (verified; no answer) | 29 steps/model calls; 27 commands; 470,077 tokens; 251.781 s; 1 accepted / 0 rejected claim; max prompt 31,592; 0 timeouts; 4 nonzero commands; no repeats; no answer rows | Ended at token budget, empty answer. Verify PASS; all queries and graph/PROV export succeeded. Hand-check: accepted quote in `2025-acl-long-892.md` lists NQ, PopQA, TriviaQA, WebQA and supports the dataset claim. Logs at `$RUNS/c3-on-2`; small artifacts in `tests/M1-real/c3-on-2/`. |
| M1-real c3-on-3 | 2026-10-13 | Slurm 7288, Qwen3.8-27B-FP8, claim_on, temp 0.7, seed 3, configured 400k tokens / 150 steps | PARTIAL (verified; no answer) | 29 steps/model calls; 27 commands; 489,660 tokens; 204.128 s; 0 claims; max prompt 38,470; 0 timeouts; 1 nonzero command; 8 repeat notices (max repeat 9); no answer rows | Ended at token budget, empty answer; one unparsed model reply. Verify PASS; all queries and graph/PROV export succeeded. Logs at `$RUNS/c3-on-3`; small artifacts in `tests/M1-real/c3-on-3/`. |
| M1-real c3-off-1 | 2026-10-13 | Slurm 7288, Qwen3.8-27B-FP8, claim_off, temp 0.7, seed 1 | PARTIAL (verified; no answer) | 30 steps/model calls; 28 commands; 498,229 tokens; 201.642 s; 0 claims; max prompt 34,769; 0 timeouts; 1 nonzero command; no repeats; no answer rows | Ended at token budget, empty answer. Verify PASS; queries 4–5 and graph/PROV export succeeded. Logs at `$RUNS/c3-off-1`; small artifacts in `tests/M1-real/c3-off-1/`. |
| M2-attach-real | 2026-10-13 | `agent attach` on c3-off-1 under Slurm 7288 | PARTIAL (path passed; no facts to attach) | 0 facts; 0 attached; 0 no-source; 0 model calls, tokens, or steps | Attach completed successfully. Queries 1–3 after attach exited successfully but returned no results; per-fact budget remains untested. Log: `$RUNS/c3-off-1/attach.json`. |
| D1-col | 2026-10-10 | Column order: the 10 D1 Docling 2.110.0 outputs vs the same ACL Anthology PDFs, paragraph probes located in (page, column, y) order with pdfplumber; `tests/D1/column_order.py` | PASS (no interleaving) | 10/10 papers two-column, 0 interleaved; 141 column/page breaks joined inside one paragraph, 5 sentences split into adjacent paragraphs (`\n\n` only), 4 split with a footnote/caption/table inserted between the halves (all at page breaks); 46 residual order inversions, all captions, footnotes, figure-internal text or repeated appendix text | No paper needs excluding or flagging. Quotes across the 4 float-split breaks (and across 6 undecoded formulas) cannot match and are rejected by the anchor library. Details: the appendix "D1-col column-order.md". |
| M1-unit | 2026-10-10 | `m1-core` unit suite (`agent/tests`, pytest 8.4.2): rows 1.2, 1.3, 1.5, 1.6 plus the minus-sign/number-cut fix and LF `.gitattributes`; Windows 11 (Python 3.13, `core.autocrlf=true`) and WSL Ubuntu (Python 3.14.4, uv-locked) | PASS | Windows: 151 passed, 2 skipped (POSIX-only SEQPACKET/SCM_RIGHTS broker tests); WSL Linux: 153/153 passed. By file: anchor 82, concept 35, broker 30, rundir 6. `corpus/manifest.json` sha256 from an LF checkout `22e9471bbed7…` = D5 | Anchor tests run on the 10 D1 Docling papers: 400 random spans at their offsets, 9 retypings each, real retyped quotes, column breaks, rejection, ambiguity, negative numbers in tables. Quotes of a number without its sign or cut mid-number are rejected (`partial_number`). |
| M2-run | 2026-10-11 | Suite after merging `m2-run` (2.1, 2.2, 2.4, 2.5, 2.9) into `main`; scripted model and a fake OpenAI-compatible server, no cluster | PASS (mock model only) | WSL Linux: 265 passed, 1 skipped. Windows (branch): 234 passed, 32 skipped (POSIX-only) | Untested: real Qwen attach step, `SLURM_JOB_END_TIME` and signal delivery on the real Slurm, Landlock during attach (tests ran unsandboxed). |
| M1-loop | 2026-10-11 | Unit and end-to-end suite after merging `m1-loop` (1.8–1.12, 1.14) and `m2-graph` (2.6–2.8) into `main` (`682a66f`); scripted model, no cluster; WSL Ubuntu (uv-locked, Landlock available in WSL 6.18) and Windows 11 (Anaconda 3.13) | PASS (mock model only) | WSL Linux: 232 passed, 1 skipped (the "Landlock missing" test). Windows, `m1-loop` alone: 190 passed, 19 skipped (POSIX-only end-to-end). Covers strict/lenient parsing, coverage record on garbage output, rejected-then-retried claim, 8 KB cap, repeat warnings, step and token budgets, HTTP 400 context-full, `claim_off`, timeout and `ulimit`, tamper detection by `agent verify`, Landlock mode; KG, PROV-O export (byte-identical re-export) and the five queries on a research-style and an attach-style run | Nothing ran on the real model. Landlock rules do not hold on WSL `/mnt/c` (drvfs): `claim` failed with "Permission denied" there; check on Ceph in 1.13, else install the claim client into the agent root. `/usr/bin/timeout` (uutils) fails under Landlock+seccomp, so the wrapper times out commands itself. |

## Appendices

The notes that used to sit beside the logs as `tests/<id>/*.md`, folded in verbatim (headings moved down two
levels). Logs, scripts and raw outputs stay under `tests/<id>/`. Kept as files because code writes them:
`tests/D1/criteria.md` (`tests/D1/evaluate.py`) and `tests/D2/hash_comparison.md` (`tests/D2/compare_hashes.py`).

## Appendix: A2 model_candidates.md

### Current Qwen model candidate check

Checked Hugging Face on 2026-10-09 before choosing the test model. The Qwen organization currently publishes Qwen3.8, including a 180B Flash-Next model that is too large for this node and the official `Qwen/Qwen3.8-27B-FP8` checkpoint as the compact current candidate. The node's Hugging Face metadata reported a total repository size of 28.77 GiB (commit `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`). Its config uses the `Qwen3_5ForCausalLM` architecture, implemented in vLLM 0.21.0. The checkpoint has now been tested on one A100: it starts at 65,536 tokens and passes the 60k prompt test.

The local setup cache also had a community `abihsoro/Qwen3.8-27B-AWQ-INT4` entry, but it only contained tokenizer/config assets (about 20 MiB) and no weights, so it was not launchable. The current reasoning-separation and cutoff tests continue on the cached Qwen3-30B-A3B-Thinking-2507-FP8 checkpoint because those tests require a thinking model.

Sources: [official Qwen model catalog](https://huggingface.co/Qwen/models), [Qwen3.8-27B model card](https://huggingface.co/Qwen/Qwen3.8-27B), [official Qwen3.8-27B-FP8 checkpoint](https://huggingface.co/Qwen/Qwen3.8-27B-FP8).

## Appendix: A2 recorded_profile.md

### A2 current server profile and prior measurements

This uses the existing `final-final-llm-setup/profiles/a100-3x40.yaml` and completed run `runtime/20261007T152525Z-c594d61a` on gammaweb08 (Slurm job 6951). It is not the plan's original 2-GPU ORCH / 1-GPU quantized SUB split; retain that as a separate trial if that exact pairing is needed.

| Setup role | Model | GPUs | max_model_len | Weight load | KV tokens | vLLM maximum concurrency |
|---|---|---:|---:|---:|---:|---:|
| Heavy | Qwen/Qwen3-30B-A3B-Instruct-2507-FP8 | 1 | 32768 | 220.57 s | 69,296 | 2.11 × 32768-token requests |
| Lite | ibm-granite/granite-4.1-8b | 1 | 32768 | 118.30 s | 127,728 | 3.90 × 32768-token requests |
| Embed | Qwen/Qwen3-Embedding-0.6B | 1 | 8192 | 7.71 s | 301,312 | 36.78 × 8192-token requests |
| Thinking candidate | Qwen/Qwen3-30B-A3B-Thinking-2507-FP8 | 1 | 32768 | 11.47 s (warm cache) | 64,848 | 1.98 × 32768-token requests |
| Latest official candidate | Qwen/Qwen3.8-27B-FP8 | 1 | 65536 | 179.82 s (warm cache) | 79,371 | 1.21 × 65536-token requests |

All three servers reached application startup on the recorded run. Heavy listened on loopback port 8002, Lite on 8003, Embed on 8001. The current repository deliberately binds to 127.0.0.1. These are setup-stack results, not externally reachable `8001/8002` test endpoints. No concurrent load or fresh max-model-len sweep has been run for the requested ORCH/SUB roles.

The direct thinking-candidate startup used vLLM 0.21.0, 1×A100, and a warmed weights cache: 29.53 GiB model memory, max concurrency 1.98 at 32,768 tokens. Initial engine startup failed because FlashInfer attempted JIT sampling compilation but `nvcc` was unavailable (`/usr/local/cuda` missing); `VLLM_USE_FLASHINFER_SAMPLER=0` selected vLLM's PyTorch sampler and startup succeeded. The official Qwen3.8-FP8 startup also used the PyTorch sampler fallback. It loaded 28.9 GiB of model memory, exposed a 65,536 max model length, and had 79,371 KV tokens, for 1.21× concurrency at that length. End-to-end startup (command to API health) was about 8m27s, including 179.82s weight load, 113.76s compilation, and multimodal warmup. Cached models also include `Qwen/Qwen3.5-4B`, `Qwen/Qwen3.5-9B`, `Qwen/Qwen3.6-27B`, `Qwen/Qwen3.6-27B-FP8`, and a small metadata-only community Qwen3.8 AWQ cache entry.

## Appendix: B format-and-reasoning-findings.md

### Command formatting and Qwen reasoning findings

#### What B1 measured

B1 used Qwen3-30B-A3B-Thinking-2507-FP8 and asked for plain-text reasoning followed by exactly one fenced bash block. vLLM returned reasoning separately, but only 26% of final `content` fields had exactly one fenced block, both with thinking requested and with `enable_thinking=False`. No code block found in parsed reasoning was missing from `content`. This points to final-answer formatting and to the older model/request's thinking switch behavior; it does not show that LiteLLM moved or dropped the command.

The original A7 used a non-thinking Heavy model. Direct and proxy fields matched, but it could not test the thinking switch. A fresh A7 rerun against Qwen3.8-27B-FP8 found exact direct/proxy equality for reasoning, content, finish reason, and usage in both modes; reasoning was absent with thinking off and present with thinking on. The proxy honored the switch.

#### Alternative output controls tested

- A stricter final-only prompt on Qwen3.8, thinking off, produced exactly one bash block in 50/50 existing B tasks. Mean latency was about 0.63 s.
- A pilot using the same strict prompt with thinking on is running; its results are recorded separately when complete.
- vLLM 0.21 documents online structured outputs using `extra_body={"structured_outputs": {"regex": ...}}`. A direct-vLLM pilot using a regex for one complete bash fence produced one block in 10/10 tasks. The same request through LiteLLM returned HTTP 400 `No connected db`, so proxy passthrough of this field is unverified and fails in the current run.

These runs use the current Qwen3.8 model, unlike B1's Qwen3 Thinking-2507 checkpoint. They support replacing the old checkpoint and using the strict prompt. Regex-constrained decoding is a stronger direct-vLLM fallback if the deployment bypasses or repairs the proxy.

#### B6 meaning and follow-up rating

B6 is a by-eye rating of whether the model's first proposed shell command was an executable, concept-directed research action. It does not rate formatting or whether the command ultimately finds the answer. The original B1 responses scored 39/50 (78%) with thinking on and 38/50 (76%) with thinking off. The B8 response set will be rated using the same criterion before using it to recommend a prompt/model change.

#### Primary references

- vLLM 0.21 structured outputs: <https://docs.vllm.ai/en/v0.21.0/features/structured_outputs/>. The OpenAI-compatible server accepts `structured_outputs.regex` as an extra parameter.
- vLLM 0.21 reasoning outputs: <https://docs.vllm.ai/en/v0.21.0/features/reasoning_outputs/>. The `--reasoning-parser` option extracts the reasoning field; the public field was renamed from `reasoning_content` to `reasoning`.
- vLLM Qwen3 parser: <https://docs.vllm.ai/en/v0.21.0/api/vllm/reasoning/qwen3_reasoning_parser/>. It splits `<think>...</think>` into reasoning and content and handles the strict disabled-thinking template.
- Qwen quickstart: <https://qwen.readthedocs.io/en/stable/getting_started/quickstart.html>. Qwen describes `enable_thinking=False` as the hard switch and gives separate recommended sampling parameters for thinking and non-thinking modes.

## Appendix: B1 interpretation.md

### B1 interpretation after model-card check

The B1 checkpoint, `Qwen/Qwen3-30B-A3B-Thinking-2507`, is explicitly a thinking-only model. Its official model card says it supports only thinking mode and that the default chat template includes `<think>`; `enable_thinking=True` is unnecessary. Thus B1's 50/50 nonempty reasoning fields in the requested “thinking off” condition are expected for this checkpoint and do not show a vLLM parser defect.

The format result remains meaningful for thinking-on use: only 26% of final `content` fields contained exactly one fenced bash block. The block was not lost into the parsed reasoning field. Therefore the unresolved B1 issue was final-answer format compliance. The off-mode half of B1 was not a valid thinking-off comparison.

Official model card: <https://huggingface.co/Qwen/Qwen3-30B-A3B-Thinking-2507> (states the checkpoint supports only thinking mode and describes the default thinking template).

Follow-up results on the actual current hybrid model are in B8 and B9: strict prompt format passed 50/50 with thinking off and 48/50 with thinking on at a 4,096-token cap; regex-constrained output passed 10/10 through both direct vLLM and LiteLLM when thinking was off. Thinking-on constrained results are being tested separately.

## Appendix: B6 manual_review.md

### B6 command-sense review

Manual review of the first command/action in the 50 B1 responses. Marked sensible when it gives an executable, concept-directed first search or inspection step; generic inventory commands and prose without an actionable command are not sensible. This is a by-eye rating, not a second-model score. Source responses: `../B1/thinking-8192.jsonl` and `../B1/no-thinking-8192.jsonl`.

| ID | Thinking on | Thinking off |
|---|---:|---:|
| t01 | yes | yes |
| t02 | no | no |
| t03 | yes | yes |
| t04 | yes | yes |
| t05 | yes | yes |
| t06 | yes | yes |
| t07 | no | no |
| t08 | yes | yes |
| t09 | yes | yes |
| t10 | yes | yes |
| t11 | yes | yes |
| t12 | yes | yes |
| t13 | yes | yes |
| t14 | no | no |
| t15 | yes | yes |
| t16 | yes | yes |
| t17 | yes | yes |
| t18 | yes | yes |
| t19 | no | no |
| t20 | yes | yes |
| t21 | yes | yes |
| t22 | yes | yes |
| t23 | yes | yes |
| t24 | yes | yes |
| t25 | yes | yes |
| t26 | no | no |
| t27 | yes | yes |
| t28 | no | yes |
| t29 | yes | yes |
| t30 | yes | yes |
| t31 | no | no |
| t32 | no | no |
| t33 | yes | yes |
| t34 | yes | yes |
| t35 | yes | yes |
| t36 | yes | yes |
| t37 | no | no |
| t38 | no | no |
| t39 | yes | no |
| t40 | yes | yes |
| t41 | yes | yes |
| t42 | yes | yes |
| t43 | yes | yes |
| t44 | yes | no |
| t45 | yes | yes |
| t46 | yes | yes |
| t47 | no | yes |
| t48 | yes | yes |
| t49 | yes | yes |
| t50 | yes | no |

Sensible rate: 39/50 (78%) thinking on, 38/50 (76%) thinking off. Mean response latency: 7.74 s on, 7.54 s off. Mean parsed reasoning tokens: 988 on, 958 off. The command-sense difference is negligible relative to the formatting failure; the main harness need is robust handling of prose-only and unfenced commands.

## Appendix: B8 findings.md

### B8: format-nudge pilot

The B1 one-block failure was tested with a stricter output instruction on the current ORCH model (Qwen3.8-27B-FP8), thinking disabled. The prompt requires only one executable bash block, gives the exact fence shape, and forbids prose or any second fence.

- 20 prompts from the existing B task set
- Exactly one fenced bash block: 20/20 (100%)
- Prose-only and multiple-block responses: 0/20
- Mean request latency: 0.73 s
- All requests finished normally

This is a pilot, not a replacement for B1's 50-prompt evaluation: it uses the newer non-thinking model and the first 20 prompts. It supports using the strict format instruction with Qwen3.8, but a full 50-prompt rerun is needed before changing the B1 result or treating the threshold as established.

Raw responses and the machine-readable summary are in `results.jsonl` and `summary.json`.

## Appendix: B8 manual-review.md

### B8 command-sense review

Rated the 50 B8 thinking-off commands by the same by-eye rule as B6: the first command must be executable and concept-directed. A generic corpus listing is not sensible for identifying the requested concept; a search command is accepted as an exploratory first step even if later refinements will be needed.

- Sensible: 40/50 (80%)
- Not sensible: 10/50 (20%)
- The nine `ls /corpus` / `ls /corpus | head` replies were generic inventory commands; the task did not ask for a corpus listing.
- One command searched `--include="*.txt"` although the corpus is Markdown.

This is close to the original B6 rates (78% thinking on, 76% off). The stricter format instruction fixed the tested block-compliance problem without a measurable drop in first-command usefulness. This is a by-eye rating and does not establish research-answer accuracy.

## Appendix: B0 result.md

### B0 result

Status: PASS on Slurm job 7048, node gammaweb08.

- Built fresh root `/mnt/ceph/storage/data-tmp/2026/xepi3167/agent-root-infra-final-3` in 105.33 s.
- `uv venv --seed --python 3.13` plus the hash-locked `uv pip sync` installed the pinned agent packages and left a usable `pip` executable for the offline wheel test.
- Installed the checked `rg` and `jq` binaries and copied the `networkx` and `tabulate` wheels from the prior S5c root.
- Root size: 266 MB; file hash manifest: 5,867 files; mode manifest: 6,526 entries. `scripts/verify-agent-root.sh` passed.
- Build and verification logs: `build-3.log`, `time-3.txt`, and `verify-3.log`.

Two early attempts exposed issues in the new builder/verifier: writing manifests after recursively removing write bits, then comparing a duplicate self-entry in the mode manifest. Both were corrected before the successful fresh build and verification.

## Appendix: C2 result.md

### C2 prefix cache and masking replay

Date: 2026-10-09. Node: gammaweb08, Slurm job 7048. Server: Qwen3.8-27B-FP8, vLLM 0.21.0, 65,536 max model length, prefix caching enabled, thinking disabled.

The 60-request sequential replay completed. It retained a stable system/task prefix, appended fixed `(no matches)` observations, and reset older turns immediately before steps 20, 40, and 60. It did not execute any generated shell commands. Prompt size grew only to 1,665 tokens before masking, so this was a cache mechanics check, not a long-context load test.

`vllm:prefix_cache_queries_total` reached 45,720 tokens and `vllm:prefix_cache_hits_total` reached 20,384 tokens. Cache hits increased on 24/60 steps. Between masks, hits increased by 10,976 tokens in steps 2–19, 4,704 in steps 21–39, and 4,704 in steps 41–59. The counters did not rise on the mask steps themselves. This is consistent with a cache-hit dip at masking boundaries, although the dip continued for some following requests.

TTFT at steps 19/20/21 was 0.098/0.110/0.118 s; steps 39/40/41 were 0.173/0.113/0.118 s; steps 59/60 were 0.172/0.111 s. These short prompts did not produce a seconds-long re-prefill. The cache trend is promising, but the requested realistic-history timing criterion remains unverified. vLLM logs note Mamba `align` cache mode is experimental for this architecture.

Raw per-step prompts, outputs, TTFT, usage, and scraped metrics are in `steps.jsonl`; server startup log is `serve.log`.

## Appendix: C2b findings.md

### C2b: 30k-token prefix cache and masking replay

Date: 2026-10-10. Model: `Qwen/Qwen3.8-27B-FP8`, through LiteLLM, thinking disabled, 300 output tokens per step. Attention block size from `tests/L1/runtime/orch.log`: 784 tokens. Prompts were built from converted paper Markdown, with a unique first passage for each sequence so the first request measured a cold cache. vLLM accepted `min_tokens=300`; all 40 requests completed with exactly 300 output tokens.

- Unmasked: cold step 1, 30,035 prompt tokens, 12.025 s TTFT, zero cache hits. Steps 2–20 averaged 0.351 s TTFT. At 30,379 prompt tokens (step 9), 29,792 cache-hit tokens; at step 15, 30,576 hit tokens after crossing the next 784-token boundary.
- Masked sequence: cold step 1, 30,035 prompt tokens, 11.770 s TTFT, zero cache hits. Step 9, 30,379 tokens / 0.413 s TTFT / 29,792 hits. Masking at step 10 reduced the prompt to 47 tokens; TTFT was 0.109 s and hits were zero. Step 11 was 91 tokens / 0.106 s / zero hits.
- Mean TTFT after the cold first step: 0.351 s unmasked, 0.236 s for the masked sequence. The latter includes the short post-mask prompts. Summed prefix-cache hit/query ratios were 93.7% unmasked and 86.7% masked.

Cold prefill at 30k was about 2,495 prompt tokens/s. This supports keeping Qwen3.8 as the orchestrator: a cold long prompt costs about 12 seconds, while matching cached history returns a first token in about 0.3–0.6 seconds. Masking sharply reduces prompt length and prefill latency.

Per-step metrics: `steps.jsonl`; complete output: `replay.log`. An earlier synthetic repeated-token attempt and the warm-cache trial are retained as diagnostic logs and are not used for these numbers.

## Appendix: D1-col column-order.md

### D1 column order (milestone 1, row 1.4)

**Result: no interleaving.** In all 10 papers Docling 2.110.0 (OCR off, tables on) keeps the two
columns in reading order: left column, then right column, then the next page. No paper needs to be
excluded or flagged in the manifest for column order.

#### Setup

- Markdown: the Docling 2.110.0 outputs in `tests/D1/docling/` (same converter and settings as the
  frozen corpus; the frozen corpus itself is on Ceph and was not reachable).
- PDFs: the same 10 files downloaded from the ACL Anthology (`https://aclanthology.org/2025.acl-long.999.pdf`
  etc.; `tests/D1/convert_docling.py` converted the identically named files). They are not committed.
- `tests/D1/column_order.py` (pdfplumber 0.11, used only for this check): words on each PDF page are
  assigned to the left or right half and read as (page, column, top, x). Each Docling body paragraph is
  located in that stream by a unique 40-character alphanumeric probe from its start and from its end, so
  the check is insensitive to Docling's spacing, hyphenation and entity escapes. Raw output:
  `tests/D1/column-order.json`.

#### Numbers

| Paper | Pages | Two-column pages | Body paragraphs | Located | Inversions | Column/page breaks inside one paragraph | Split sentences |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2025-acl-long-1031 | 39 | 31 | 253 | 195 | 2 | 8 | 0 |
| 2025-acl-long-1458 | 28 | 20 | 234 | 157 | 5 | 9 | 0 |
| 2025-acl-long-625 | 35 | 30 | 210 | 166 | 4 | 16 | 2 |
| 2025-acl-long-935 | 20 | 18 | 127 | 100 | 2 | 12 | 0 |
| 2025-acl-long-999 | 38 | 36 | 281 | 195 | 5 | 26 | 1 |
| 2025-emnlp-main-1032 | 13 | 12 | 189 | 67 | 2 | 7 | 2 |
| 2025-emnlp-main-1418 | 37 | 34 | 505 | 280 | 15 | 15 | 6 |
| 2025-emnlp-main-1755 | 32 | 29 | 302 | 247 | 4 | 14 | 8 |
| 2025-emnlp-main-356 | 23 | 22 | 180 | 141 | 1 | 16 | 2 |
| 2025-emnlp-main-971 | 23 | 19 | 230 | 182 | 6 | 18 | 5 |

All 10 papers use the two-column ACL template; the single-column pages are full-page tables, figures and
prompt listings in appendices.

**Inversions** (a paragraph that starts before the previous one ends, in PDF order) were read one by one;
none is a column interleave. Before excluding captions and footnotes there were 121; the 46 left are:
footnotes and reference entries placed after the paragraph that cites them; text inside figures and prompt
boxes (1418 p.15, 999 p.22), which the PDF lays out in narrow sub-columns; appendix paragraphs that repeat
a body paragraph word for word (971 p.3/p.11, 1755), so the probe matched the other copy; and three cases
checked against the PDF page text (1031 p.8, 1458 p.18, 1032 p.2), where Docling's order matches the PDF
and the probe hit a table or figure caption first.

#### What happens at a column break

1. **Joined inside one paragraph (141 cases).** The usual case: the sentence continues in one Markdown
   paragraph, with the line-end hyphen kept as `solu- tions`. A quote across the break is ordinary text.
2. **Split into two adjacent paragraphs (5 cases at a column or page break).** The sentence stops at the
   end of a paragraph and continues lower-case in the next, with only `\n\n` between:
   `2025-acl-long-625` offset 2344 (`improving LLM SFT` / `performance. ALPAGASUS`),
   `2025-acl-long-999` 12336, `2025-emnlp-main-1032` 3565, `2025-emnlp-main-1418` 37127 and 109075.
   A retyped quote across such a break matches once whitespace is normalised (the 1.5 anchor tests cover
   these three: 625, 1032, 1418).
3. **Split with a float placed between the halves (4 cases, all at page breaks).** Docling put the
   footnote, caption, image marker or table that sits at the bottom or top of the page between the two
   halves of a sentence: `2025-emnlp-main-1418` 13463 (footnote + caption + image) and 128907 (table +
   caption), `2025-emnlp-main-1755` 8642 (footnote) and 18024 (caption + image + table). A quote spanning
   such a break does **not** match, because the inserted text is in the file between the two halves. The
   anchor library rejects it as `not_found`; the agent has to quote one side. This is a property of the
   frozen Markdown, not of the anchor code, and it is rare (4 of ~150 breaks).

Not column-related, found on the way: 6 sentences are split by a display formula that Docling did not
decode (`<!-- formula-not-decoded -->`, or dropped entirely in 356), so a quote across a formula cannot match
either.

#### Consequence for 1.5 and the manifest

- No paper is excluded or flagged for column order.
- Anchor normalisation must treat `\n\n` and `- ` line-end hyphenation as whitespace/hyphenation noise,
  which 1.5 does. Quotes across an inserted float or an undecoded formula stay rejected.

## Appendix: D5 findings.md

### D5: Docling corpus conversion

- Input: all 337 PDFs in `final-final-frontend/corpus_acl_emnlp_2025_input` (the user-selected corpus only).
- Converter: Docling 2.110.0, OCR disabled, table structure enabled; output frozen at `/mnt/ceph/storage/data-tmp/2026/xepi3167/research-agent-corpus-docling-2.110.0`.
- Result: 336 PDFs yielded Markdown above the 5 KB minimum; 28,586,882 Markdown bytes total. All 336 source and output hashes verified; the manifest covers all 337 input PDFs. The tree has 338 verified paths and no write bits.
- Accepted exception: `p38` (source `38.pdf`) is an 18-page scanned paper. Without OCR, Docling returned 222 bytes of image markers. Per user direction it is excluded from the usable corpus; no OCR retry is included in the frozen corpus.
- The Slurm conversion took about 4 h 52 min wall time (sum of per-paper conversion times: 17,065 s). The batch step itself returned nonzero for the single rejected output; the explicit verifier passes with the one documented exclusion.
- Manifest SHA-256: `22e9471bbed7fa3e534cecef0d31e83950c88328ff8e7e7916a94b3fe4be9eb4`.

Verification command and result: `tests/D5/verify.py`; see `corpus/manifest.json` and `tests/D5/slurm-7140.out`.

## Appendix: L4 outcome.md

### L4 outcome

A 5,000-token streamed request was routed to SUB replica 2 on port 8004. The process group was verified to be owned by this session and received SIGTERM while one request was active. The client received a successful response (922 completion tokens, 4,140 content characters, 7.55 s total); no retry line was found in the LiteLLM log. The vLLM process exited cleanly after the request, the supervisor waited 30 s before restarting it, and the watchdog recorded the backend healthy again 2:30 after restart. The external health monitor observed HTTP 200 at 2:46.

## Appendix: L7 findings.md

### L7: LiteLLM timeout, routing, and seed

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

## Appendix: L8 findings.md

### L8: proxy context-window failures

Date: 2026-10-10. All three requests through LiteLLM returned HTTP 400 `BadRequestError` with a `ContextWindowExceededError` message. The proxy included the model context limit, minimum counted prompt length, requested output count, and total at least one token over the limit:

- ORCH: 70,000-token prompt + 1 output token; limit 65,536, proxy reports at least 65,536 input tokens and 65,537 total.
- SUB: 34,000-token prompt + 1 output token; limit 32,768, proxy reports at least 32,768 input tokens and 32,769 total.
- ORCH: 64,000-token prompt + 2,000 output tokens; proxy reports 63,537 input + 2,000 output = 65,537 against 65,536.

The harness can map this 400 error to “context full” and stop retrying. Raw bodies are in `errors.json`.

## Appendix: S6 findings.md

### S6 escape checks (Landlock ABI 8)

Commands ran through `tests/S5/run_sandbox.py` and the ctypes Landlock wrapper.

- `kill -0` on orch, two sub models, LiteLLM, status API, tunnel and harness shell: all denied. No signals were sent.
- `/proc/<litellm-pid>/environ`: `test -r` reported readable, but opening it raised `PermissionError`; no bytes or environment values were logged.
- SSH key and repository `.env`: `test -r` reported readable, but opening raised `PermissionError`; no bytes or secret values were logged. `.git-credentials` did not exist.
- `SSH_AUTH_SOCK`: absent.
- UDP `sendto` to `1.1.1.1:53`: one byte sent. Landlock does not constrain UDP; this is an escape.
- Abstract Unix socket: denied. Pathname Unix socket: connection allowed. Landlock's socket scope only covers abstract sockets, not pathname sockets; restrict the visible writable filesystem and avoid exposing sensitive pathname sockets.
- `nohup sleep 1000 &`: child was gone after process-group cleanup.

Separate S5c check: `chmod -R u+w $AGENT_ROOT` succeeded under Landlock and permissions were restored immediately. Landlock does not mediate chmod. The post-test SHA-256 manifest verified successfully.

Logs: `findings.txt`, `background-command.txt`, `private`-safe probe outputs in `tests/S5/`.

## Appendix: S7 findings.md

### S7 result

Status: PASS on Slurm job 7048, node gammaweb08 (x86_64, Landlock ABI 8).

- The Landlock wrapper installs a seccomp BPF filter immediately after `PR_SET_NO_NEW_PRIVS`. `socket()` for AF_INET, AF_INET6, AF_UNIX, and AF_NETLINK and `socketpair()` returned `EPERM`.
- TCP attempts to `1.1.1.1:443` and `127.0.0.1` ports 8001, 8002, 8004, 4000, and 8010 all returned `EPERM` at socket creation. UDP socket creation and pathname Unix socket creation were also denied.
- `run_sandbox.py` created a socketpair before launching the command and passed the command end through `CLAIM_FD`. The command submitted 100 claims that forged step 999999; the broker stored all with step 42 and the hash chain verified. Head: `a1ed25d8e674923691b49c2f42f7e1d161784530e6b44341beddcc115469b44a`.
- Inside the wrapper, Python printed `2`; grep, rg, jq, NumPy and pandas worked; scratch writes worked; offline `pip install` from the root wheel store installed networkx 3.7.
- The venv interpreter is a symlink to the shared uv Python installation. Its resolved runtime directory must be added to Landlock's read-only paths when the harness uses the venv interpreter.
- The expected chmod behavior was reproduced: `chmod u+w` succeeded, appending to the toolchain file failed, its mode was restored outside the wrapper, and the manifest verifier passed.

Logs: `seccomp-probe-final.log`, `inherited-claims.log`, `claims.jsonl`, `allowed-final.log`, `chmod-landlock.log`, and `restored-manifest.log`.
