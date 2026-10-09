# Test plan: free research agent on Slurm (3 × A100 40 GB)

Purpose: settle the infrastructure and model-behaviour questions before the harness is built. Every test
writes its logs under `tests/<id>/` and appends one row to `tests/RESULTS.md` (columns: id, date, config,
pass/fail, numbers, notes). Do not skip the "record" lines: the numbers are what the design decisions depend on.

Conventions used below:

- `$NODE` = the GPU node running the vLLM servers (`echo $SLURMD_NODENAME` inside the job).
- Orchestrator server on port 8001, subagent server on port 8002. Clients talk to `http://$NODE:800x/v1`.
- Models are referred to by role: `ORCH` and `SUB`. Candidate checkpoints:
  - `ORCH-A`: `Qwen/Qwen3-Coder-30B-A3B-Instruct` (BF16, MoE 3B active, 256k native, non-thinking).
  - `ORCH-B`: `Qwen/Qwen3-32B` (dense; try `--quantization fp8` first, which runs weight-only on Ampere; if it refuses, use a GPTQ-Int8 or AWQ community checkpoint).
  - `SUB`: an AWQ-4bit checkpoint of `Qwen3-30B-A3B-Instruct-2507` (search Hugging Face; any reputable AWQ or GPTQ-Int4 export) or the Coder variant.
  - Check Hugging Face for newer Qwen releases first; keep the same three roles.
- Everything is run with Python 3.11+, `vllm`, `openai`, `httpx`, `numpy`. Pin versions in `tests/requirements.txt` and record `vllm --version` in RESULTS.md once.

---

## Part A: infrastructure

### A1. Node sanity (5 min)

```bash
srun --gres=gpu:a100:3 --mem=64G --cpus-per-task=8 --time=00:10:00 --pty bash -c '
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
  python3 -c "import torch;print(torch.__version__, torch.version.cuda, torch.cuda.device_count())"
  python3 -c "import vllm;print(vllm.__version__)"
  df -h /scratch $HOME | head
  nproc; free -g | head -2'
```

Pass: 3 GPUs visible, 40 GB each, CUDA visible to torch, vLLM imports.
Record: driver, CUDA, torch, vLLM versions; free disk where model weights will live (need ~150 GB for all candidates).

### A2. Server launch scripts (one sbatch per role)

`tests/A2/serve_orch.sbatch` (ORCH-A shown; ORCH-B is the same with the other model name and `--quantization fp8`):

```bash
#!/bin/bash
#SBATCH --job-name=vllm-orch
#SBATCH --gres=gpu:a100:2
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --time=24:00:00
#SBATCH --output=tests/A2/orch-%j.log
export CUDA_VISIBLE_DEVICES=0,1
export VLLM_LOGGING_LEVEL=INFO
echo "NODE=$SLURMD_NODENAME" > tests/A2/orch.node
vllm serve Qwen/Qwen3-Coder-30B-A3B-Instruct \
  --served-model-name orch \
  --tensor-parallel-size 2 \
  --max-model-len 65536 \
  --gpu-memory-utilization 0.92 \
  --enable-prefix-caching \
  --max-num-seqs 8 \
  --port 8001 --host 0.0.0.0
```

For a thinking model (ORCH-B, Qwen3-32B) add `--reasoning-parser qwen3`. For original Qwen3 checkpoints that are 32k native and need 128k, add
`--rope-scaling '{"rope_type":"yarn","factor":4.0,"original_max_position_embeddings":32768}' --max-model-len 131072`
(not needed for the 2507 / Coder models).

`tests/A2/serve_sub.sbatch`: same shape, `--gres=gpu:a100:1`, `CUDA_VISIBLE_DEVICES=2`, `--tensor-parallel-size 1`,
`--max-model-len 32768`, `--max-num-seqs 8`, `--port 8002`, `--served-model-name sub`, the AWQ model name, and
`--reasoning-parser qwen3` only if the checkpoint is a thinking model.

Note: the two sbatch jobs land on different nodes unless constrained. Either run both servers from ONE job with
`--gres=gpu:a100:3` and launch the two `vllm serve` processes in the background (recommended for the tests), or use
`--nodelist`. Record which.

Pass: `curl http://$NODE:8001/v1/models` returns the model with `max_model_len` equal to what was requested; the
server log shows the KV cache size line (`# GPU blocks: N` or `Maximum concurrency for N tokens per request`).
Record: startup time, GPU memory used per GPU (`nvidia-smi`), the "maximum concurrency at max_model_len" line from the log, for each of ORCH-A, ORCH-B, SUB.

If the server refuses to start with "KV cache is smaller than max_model_len": lower `--max-model-len` in steps of 8k and record the largest that starts. That number is a hard design input.

### A3. Long-prompt test (10 min per model)

Script `tests/A3/longprompt.py`: build a prompt of ~60,000 tokens (concatenate corpus Markdown files; count with the model's tokenizer via `AutoTokenizer`), ask for a 200-token summary, time it.

```python
from openai import OpenAI; import time
c = OpenAI(base_url=f"http://{NODE}:8001/v1", api_key="x")
t=time.time(); r=c.chat.completions.create(model="orch", messages=[{"role":"user","content":prompt}], max_tokens=200)
print(time.time()-t, r.usage)
```

Run at 16k, 32k, 48k, 60k prompt tokens.
Pass: no error at 60k; `usage.prompt_tokens` matches your count within 2%.
Record: time-to-first-token and total time at each length (prefill speed in tokens/s = prompt_tokens / TTFT).

### A4. KV headroom under concurrency (15 min)

`tests/A4/concurrency.py`: with `asyncio` + `AsyncOpenAI`, send N simultaneous requests of P prompt tokens, 300 output tokens each.

- ORCH: N=2, P=48k; then N=4, P=32k.
- SUB: N=6, P=24k; then N=8, P=16k.

While running, scrape `http://$NODE:800x/metrics` every 5 s and keep lines matching `gpu_cache_usage|preempt|num_requests_waiting`.
Pass: zero preemptions (`vllm:num_preemptions_total` does not increase), waiting queue returns to 0, all requests complete.
Record: peak `gpu_cache_usage_perc`, per-request latency.

### A5. Decode throughput (10 min per model)

`tests/A5/decode.py`: 20 sequential requests, 2k-token prompt, `max_tokens=300`, `temperature=0.7`. Compute output tokens per second per request from `usage.completion_tokens / (total_time - TTFT)`. Also run the A4 N=6 case on SUB and compute aggregate tokens/s.
Record: single-sequence tok/s for ORCH-A, ORCH-B, SUB; aggregate tok/s for SUB at 6 concurrent.
This feeds the run-time estimate: a 300-step run at ~300 output tokens/step = 90k output tokens.

### A6. bwrap sandbox inside a Slurm step (15 min)

Test on a CPU partition node (the harness will run there) and once on the GPU node.

```bash
mkdir -p tests/A6/corpus tests/A6/scratch; echo "hello" > tests/A6/corpus/p1.md
srun --cpus-per-task=2 --mem=4G --time=00:10:00 bash -c '
bwrap --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 --ro-bind /bin /bin --ro-bind /etc /etc \
      --ro-bind $PWD/tests/A6/corpus /corpus --bind $PWD/tests/A6/scratch /work \
      --proc /proc --dev /dev --tmpfs /tmp \
      --unshare-net --unshare-pid --unshare-ipc --unshare-uts --die-with-parent --new-session \
      --chdir /work -- bash -c "
        echo PY: \$(python3 -c \"print(1+1)\");
        grep -c hello /corpus/p1.md;
        (touch /corpus/x && echo CORPUS_WRITABLE_FAIL) || echo corpus-ro-ok;
        (timeout 5 curl -sI https://example.com >/dev/null 2>&1 && echo NET_FAIL) || echo net-off-ok;
        touch /work/ok && echo work-ok;
        ls /home 2>/dev/null | head -1 || echo home-hidden-ok;
        timeout 2 bash -c \"while true; do :; done\" ; echo timeout-rc=\$?"'
```

Pass: `PY: 2`, `1`, `corpus-ro-ok`, `net-off-ok`, `work-ok`, `home-hidden-ok`, `timeout-rc=124`.
If `--unshare-net` or user namespaces are refused: record the exact error and try without `--unshare-net` plus an iptables-free alternative (`unshare -rn` or a Slurm `--network=none` if the cluster supports it). Also test that `python3` inside the sandbox can `import re, json, pathlib, collections` and whatever a venv bind-mounted at `/venv` provides (`--ro-bind $VENV /venv`, then `/venv/bin/python3`).
Record: the working bwrap command line verbatim, and CPU-time limit behaviour (`ulimit -t 120` inside the sandbox and `timeout 120` both).

### A7. LiteLLM passthrough fidelity (10 min, only if LiteLLM stays in the path)

Send the same request to vLLM directly and through LiteLLM; compare `reasoning_content`, `finish_reason`, `usage`, and `extra_body={"chat_template_kwargs":{"enable_thinking":False}}`.
Pass: all fields identical, `enable_thinking` honoured through the proxy.
If anything is dropped, the harness calls vLLM directly and LiteLLM is removed from the path. Record the decision.

---

## Part B: model behaviour (before any harness code)

Use the system prompt the agent will get (draft in `tests/B/system_prompt.txt`):

> You work in a Linux shell. The corpus is at /corpus: one Markdown file per paper, read-only. /work is yours. python3 is available. Extra commands: `claim` (records a fact: JSON on stdin with s, p, o, file, quote), `spawn` (starts subagents), `save_tool` (registers a script). Reply with your reasoning in plain text and then EXACTLY ONE fenced bash block. One block per reply.

And 50 task prompts in `tests/B/tasks.jsonl` of the form "Research concept: <brief>. Previous steps: <0 to 5 fake command/output pairs>. What is your next command?" Vary the number of previous steps.

### B1. Reasoning separation (ORCH-B and any thinking SUB)

For each of the 50 prompts, with thinking on: check that `reasoning_content` is non-empty and that `content` contains exactly one ```bash block (regex ```` ```(?:bash|sh)\n(.*?)``` ```` with DOTALL, count matches). Repeat with `enable_thinking: false`.
Pass: ≥ 95% exactly-one-block in both modes; no bash block inside `reasoning_content` that is missing from `content`.
Record: percentage, mean and p95 `reasoning` tokens per step, mean `content` tokens per step.

### B2. max_tokens cut-off

Same 50 prompts, thinking on, `max_tokens` ∈ {1024, 2048, 4096, 8192, 16384}. Count `finish_reason == "length"` and missing bash blocks.
Pass: find the smallest `max_tokens` with < 2% length-cuts. That becomes the harness default (expect 8k to 16k for thinking models, 2k for non-thinking).

### B3. One-block compliance under stress (ORCH-A, non-thinking)

Add 20 prompts whose "previous steps" include a long tool output (6 KB) and 20 whose task invites multi-step plans ("first list, then for each…").
Pass: ≥ 95% exactly one block; record how often the model emits two blocks or prose-only replies (these need a harness nudge).

### B4. Looping tendency

Feed the model a sequence of 10 turns where every command it issues returns "(no matches)". No nudges. Count repeated identical commands and whether it changes strategy (different pattern, different files, a script) by turn 4.
Record: the turn at which strategy changes, per model. Decides whether loop detection ships in v1.

### B5. `claim` quoting via stdin

Write the stub `claim` (reads JSON on stdin, finds `quote` in `/corpus/<file>` with exact match, prints ok/fail). Ask the model (30 prompts) to claim a given sentence that contains double quotes, single quotes, backslashes, `$`, backticks, en-dashes and non-ASCII names. Run the emitted block inside bwrap.
Pass: 30/30 verified. Any failure = note whether the model or the quoting broke it; try `claim <<'EOF' … EOF` enforced in the prompt versus `claim --json '<...>'`.

### B6. Thinking on vs off, cost and quality (ORCH-B)

Same 50 prompts; blind-rate the chosen command (sensible / not) by a second model or by eye; measure seconds per step.
Record: seconds per step and sensible-rate, both modes. Decides the orchestrator's thinking setting.

### B7. Tool-output presentation (optional, mirrors Sen et al.)

20 prompts where the previous grep output is (a) inline, (b) "written to /work/out/12.txt, 41 lines". Count how often (b) leads the model to open the file before acting.
Record: the rate. Inline is the default; this measures the cost of the fallback.

---

## Part C: harness (needs the first version of the loop: mini-SWE-agent fork + interceptor)

Minimal loop requirements before testing: text actions (one bash block), bwrap per command, output cap (bytes), `events.jsonl` written by the harness process with `prev_hash`, `claims.jsonl`, `spawn` and `save_tool` stubs, observation masking every K steps.

### C1. Output capping

Inside the loop, make the agent (or a scripted fake agent) run `cat /corpus/<longest>.md`.
Pass: the message appended to the context is ≤ 8 KB + a stub line naming `/work/out/<step>.txt`; the file holds the full output; `events.jsonl` has `stdout_path` and `stdout_head`. Also cap stderr and a 50 MB `yes | head -c 50M` output without the harness stalling.
Record: context tokens before/after.

### C2. Masking and prefix cache

Scripted 60-step run (fake agent replaying a fixed command list) with masking every 20 steps. Scrape `/metrics` for prefix-cache hit/query counters (grep `prefix_cache`) after each step.
Pass: hit rate stays high between masking steps and dips only at steps 20, 40, 60; re-prefill after a mask (TTFT at that step) is a few seconds.
Record: TTFT at steps 19, 20, 21.

### C3. First end-to-end run (1 to 2 h)

Hand-written concept: "Most first-author papers at ACL 2025" (metadata-only; the answer is checkable by hand from the corpus manifest). Step budget 150, token budget 400k, ORCH-A, no subagents.
Pass: the run ends by itself; every claim's quote resolves; `events.jsonl` hash chain verifies (`tests/C3/verify_chain.py`); offline replay (`replay.py --offline`) re-renders every step; the answer matches the hand count.
Record: steps, wall time, total tokens in/out, number of claims, number of masking events, number of budget warnings, cost per claim. Save the whole run directory as `tests/C3/run-001/` (it becomes the first fixture).

### C4. Subagent fan-out

Concept: "datasets that 5 named papers report a number on". The parent must `spawn` 5 subagents (one per paper) on the SUB server.
Pass: 5 `sub/<id>/events.jsonl`, their claims in the shared `claims.jsonl` tagged with the sub id, 5 `result.json` ≤ 2 KB each, parent context grew by ≤ 5 × 2 KB + stubs; the 5 subagents ran concurrently (overlapping timestamps).
Record: wall time for the fan-out, SUB server peak KV usage.

### C5. Re-execution replay

On the C3 run: `replay.py --reexecute` reruns every command in bwrap against the frozen corpus and diffs stdout with the stored output.
Pass: 100% identical for deterministic commands; any diff is explained (timestamps, `ls` order) and the diff set is recorded.

### C6. Loop and budget behaviour

Force a loop (give the agent a concept with no hits, e.g. "papers evaluated on a dataset named XYZZY"). With loop detection on (identical command twice → one-line notice) and a 60-step budget.
Pass: the run ends with a cited "not answerable from this corpus" claim or an explicit empty result, never with a crash; a `budget_warning` event appears at the budget.

### C7. Tool invention round trip

Prompt a concept that needs a repeated computation (counting per author). Check that the agent calls `save_tool`, that `tools/<name>/SKILL.md` exists with name/description/usage, that a `tool_created` event carries the script hash, that the next turn's context lists the tool name and description (and not the body), and that later calls of the tool carry the hash in their `command` event.

---

## Part D: corpus

### D1. Markdown fidelity

Convert the same 10 PDFs (pick 5 ACL, 5 EMNLP, including 2 with large tables and 1 two-column with footnotes) with each candidate converter: GROBID TEI → Markdown (your existing path), `marker`, `docling`. For each output check by eye and by script: title and author order present and correct against DBLP; section headings present; the reference list present and splittable into entries (regex on `[n]` or numbered lines); at least one results table recoverable as rows; no interleaved columns in body text.
Record: a 10 × 3 table of pass/fail per criterion, plus conversion time per paper. Decides the converter and which concept types (citation-based, table-based) are answerable.

### D2. Determinism

Convert the same 10 PDFs twice with the chosen converter; `sha256sum` both outputs.
Pass: identical hashes. If not, record which converter flags make it deterministic (disable OCR, fixed version, no parallelism), or accept a one-time frozen conversion with hashes in `manifest.json`.

### D3. Anchor library round trip

Implement `anchor(file, start, end) -> selector` and `resolve(selector) -> text | None` (TextQuoteSelector with 32-char prefix/suffix + TextPositionSelector + sha256). Tests: 200 random spans across 20 files resolve by offsets; after inserting 10 characters at the file start, all 200 resolve by quote; after deleting the quoted sentence, all report broken; a quote that appears twice in a file resolves to the right one via prefix/suffix.
Pass: 100% on each case.

### D4. grep speed on the full corpus

Inside bwrap, time `grep -il "retrieval" /corpus/*.md`, `grep -n -i "evaluate" /corpus/*.md | wc -l`, and a python regex scan over all 337 files.
Record: seconds each. (Expected: well under a second for grep; a few seconds for python.) Confirms that no index is needed on this corpus size and sets the per-command timeout.

---

## Order and what each decides

1. A1, A2, A6, D1 first (half a day): which models start, which sandbox command works, which converter to freeze.
2. A3, A4, A5, B1, B2 (half a day): context limits, speed, thinking settings, `max_tokens` default.
3. B3, B4, B5, B6, D2, D3 (one day): prompt rules, loop detection, claim format, anchor library.
4. Build the minimal loop, then C1, C2, C3 (one to two days). C3 produces the first real run and the run-time number for the evaluation budget.
5. C4 to C7, D4, A7 (one day).

Report back with RESULTS.md. The numbers that change the design: largest `max_model_len` that starts per model (A2), decode tok/s (A5), thinking token cost (B1/B6), one-block compliance (B1/B3), the working bwrap line (A6), converter choice and determinism (D1/D2), and the C3 wall time.
