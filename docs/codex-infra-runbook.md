# Runbook: infrastructure test round 2 on Slurm

You are running the tests in `docs/infra-tests-next.md` on the Webis Slurm cluster. Read that file first:
it says why each test exists. This file says how to run each one, what to record and what not to touch.
Background, if you need it: `docs/decisions-after-tests.md` (decisions from round 1), `tests/RESULTS.md`
(round 1 numbers), `docs/slurm_test_plan.md` (round 1 method).

## Rules

- Work in this repository's checkout on Ceph. The model stack is the submodule `related/final-final-llm-setup`;
  its own docs (`README.md`, `docs/OPERATIONS.md`, `docs/CONSUMERS.md`) describe how it runs.
- Create a branch `infra-round-2` in this repo before changing anything. Never commit to or push `main`.
  Push the branch at the end if push works. If it does not, leave the commits local and say so.
- Changes to the submodule go on a branch `agent-layout` inside `related/final-final-llm-setup`. Commit there,
  do not push it, and do not update the submodule pointer in this repo.
- Never print, log or commit `.env`, `LITELLM_MASTER_KEY`, `HF_TOKEN`, SSH keys or database passwords.
  Redact them in every log you save.
- The services on Omen (Postgres, Redis, tracing, MinIO, ClickHouse) hold real data. Connect, ping and read
  only. Never write, delete, flush or migrate anything there.
- Do not touch other users' jobs or processes. Only `scancel` jobs you started in this session.
- For every test: save logs under `tests/<id>/` and add one row to `tests/RESULTS.md` in the existing format
  (id, date, config, pass/fail, numbers, notes). Use `NOT RUN` with the reason when a test cannot run. A
  partial result with the exact error is more useful than a guess.
- Some steps need the user (marked **USER**). Stop at those, say exactly what you need, and wait.

## 0. Setup (once)

```bash
cd <this repo on Ceph>
git checkout -b infra-round-2
git submodule update --init --recursive
ls related/final-final-llm-setup/profiles/        # a100-3x40.yaml must exist
```

1. **`.env` for the stack.** If `related/final-final-llm-setup/.env` is missing, copy it from the existing
   setup checkout (`/mnt/ceph/storage/data-tmp/current/xepi3167/thesis/final-final-llm-setup/.env`). If that
   does not exist either, stop and ask the user (**USER**). Do not create keys yourself.
2. **Corpus.** The round-1 scripts read `final-final-frontend/...` relative to this repo's root. If
   `final-final-frontend` is not in the repo root, find it on Ceph (start with
   `/mnt/ceph/storage/data-tmp/current/xepi3167/thesis/`) and symlink it:
   `ln -s <path>/final-final-frontend final-final-frontend`. It is git-ignored. If you cannot find it, ask.
3. **Tunnel helpers.** Install them as the README says:
   `install -m 755 scripts/omen-tunnels scripts/omen-tunnels-external ~/.local/bin/`.
4. **Python for the test scripts:** use the stack's environment (`$UV_PROJECT_ENVIRONMENT/bin/python`, after
   `set -a; source related/final-final-llm-setup/.env; set +a`). It has `openai`, `httpx` and `transformers`.

## Step 1: quick checks (no GPU job needed except S4)

### T1. Gateway port offset

`scripts/omen-tunnels` now reads `OMEN_TUNNELS_GATEWAY_PORT_OFFSET` (it ignored it before, so the external
wrapper did nothing).

```bash
omen-tunnels compute start thesis-postgres --dry-run
omen-tunnels-external compute start thesis-postgres --dry-run
omen-tunnels-external list
```

Pass: the second command's `-L` target port is the first one's + 1000 (55433 → 56433), and `list` shows
the gateway column + 1000. Save the output to `tests/T1/dry-run.txt`.

### S4. Egress and Apptainer (on the GPU node, inside the job from step 2, or any short `srun`)

```bash
for u in https://example.com https://huggingface.co https://pypi.org; do
  curl -sS -m 5 -o /dev/null -w "$u %{http_code}\n" "$u" || echo "$u blocked"; done
env | grep -i -E '^(https?|no)_proxy=' || echo "no proxy vars"
which apptainer singularity || echo "no apptainer/singularity"
```

If Apptainer exists, also try, with `tests/A6/corpus` and `tests/A6/scratch` created as in
`docs/slurm_test_plan.md` A6:
`apptainer exec --containall --no-home --net --network none --bind tests/A6/corpus:/corpus:ro --bind tests/A6/scratch:/work docker://python:3.13-slim python3 -c "print(1+1)"`
and the A6 checks (corpus read-only, no network, `/work` writable, `timeout` works).

Record: egress yes/no per URL, proxy variables, Apptainer version, and whether each A6 check passed.

## Step 2: the model stack with the chosen layout

### L1. Extend `llm-setup` for the agent layout

Today `profile.py` accepts exactly the roles `heavy`, `lite` and `embed`, and `supervisor.py` starts one
backend per role. `decisions-after-tests.md` §1 needs:

| role | alias | model | GPU | port | max_model_len | extra vLLM flags |
|---|---|---|---|---|---|---|
| orch | `orch-model` | `Qwen/Qwen3.8-27B-FP8` | 0 | 8001 | 65536 | `--reasoning-parser qwen3 --generation-config vllm --enable-prefix-caching` |
| sub (replica 1) | `sub-model` | `Qwen/Qwen3-30B-A3B-Instruct-2507-FP8` | 1 | 8002 | 32768 | `--tool-call-parser hermes` as Heavy today |
| sub (replica 2) | `sub-model` | same | 2 | 8004 | 32768 | same |

In `related/final-final-llm-setup`, on branch `agent-layout`:

1. Let a profile define its own role names and aliases instead of the fixed three (keep `a100-3x40.yaml`
   valid and unchanged in behaviour).
2. Add an optional `replicas` list per role (each with `gpu` and `port`). Each replica is one vLLM process.
   In `render_litellm`, emit one `model_list` entry per replica with the same `model_name`. LiteLLM balances
   between entries with the same name.
3. Add an optional `extra_args` list per role, appended to the `vllm serve` command and checked against
   `vllm serve --help=all` like the other flags.
4. Give `orch` a startup timeout of at least 1800 s (it took ~8.5 min in round 1).
5. Add `profiles/agent-3x40.yaml` with the table above. Embed is not needed.
6. Add or extend unit tests in `tests/` and run `uv run pytest`. All must pass.

Then start it and check it:

```bash
cd related/final-final-llm-setup
LLM_SETUP_PROFILE=profiles/agent-3x40.yaml sbatch slurm/llm-stack.sbatch
tail -f runtime/slurm-<jobid>.out                          # until all ready
srun --jobid <jobid> --overlap --pty bash -l               # every later step runs in a shell like this
set -a; source .env; set +a
uv run llm-setup doctor --profile profiles/agent-3x40.yaml
curl -s http://127.0.0.1:8010/v1/status
```

Pass: `doctor` passes. `/v1/status` shows all three backends ready. The startup log shows the KV-token line
for each (round 1: 79,371 for Qwen3.8 at 65,536 and 69,296 for Heavy). Record: the job id, the node, time
to ready per backend, KV tokens, and GPU memory from `nvidia-smi`. Save the startup log to `tests/L1/`.

If you cannot get L1 working in reasonable time, record what failed and run L2 and L3 against a manual
stack instead: `tests/A2/serve_qwen38.sh` plus two Heavy `vllm serve` processes and a hand-written LiteLLM
config. Mark the results "manual stack".

## Step 3: the proxy (stack from step 2 running)

### L2. Thinking switch and one-block compliance through LiteLLM

```bash
python tests/A7/passthrough.py --direct-url http://127.0.0.1:8001/v1 --direct-model orch-model \
  --proxy-model orch-model --out tests/L2/passthrough.json
python tests/B/B3/stress.py --base-url http://127.0.0.1:4000/v1 --model orch-model \
  --api-key-env LITELLM_MASTER_KEY --out tests/L2/b3-proxy.jsonl | tee tests/L2/b3-proxy.log
```

Pass: `enable_thinking_honoured_through_proxy` is `true`, and B3 through the proxy gives ≥ 95% exactly one
block in both groups with `nonempty_reasoning` 0. If thinking is not honoured, LiteLLM's `drop_params: True`
is the likely cause: fix it on the `agent-layout` branch (allow `chat_template_kwargs` through), restart,
rerun, and record before and after.

### L3. Load across the two `sub` replicas

```bash
for spec in "4 32000" "8 16000"; do set -- $spec
  python tests/A4/concurrency.py --base-url http://127.0.0.1:4000/v1 --model sub-model \
    --api-key-env LITELLM_MASTER_KEY --n $1 --prompt-tokens $2 \
    --metrics-url http://127.0.0.1:8002/metrics --metrics-url http://127.0.0.1:8004/metrics \
    --out tests/L3/sub-n$1-p$2.jsonl | tee tests/L3/sub-n$1-p$2.log
done
```

Pass: all requests complete, no 408/429/timeout errors, 0 preemptions on both replicas, and both replicas
served requests (use the `request_success` counters in the `.metrics.txt` file; the split should be within
60/40). Record p95 latency and compare with A4.

### L4. Retries through the proxy

During a single long request through `sub-model`, kill the vLLM process serving it (find the PID with
`nvidia-smi` or `/v1/status`; only processes from your job). Record what the client gets (error or a
success from the other replica), and whether the LiteLLM log shows a retry. If a retry happens silently,
note it: the harness logger would see one call where two ran. Let the supervisor restart the backend and
confirm it is ready again.

### L5. Compile cache

Note the time-to-ready from L1. Stop the job, set `VLLM_CACHE_ROOT` to a Ceph directory (add it to `.env`,
do not commit `.env`), start a new job, and record time-to-ready again for both the first start (cache
filling) and a second new job (cache warm). Pass if the warm start saves more than 1 min on `orch`.

## Step 4: tunnels from the job

**USER, before T2:** the laptop hop must be running. Ask the user to run, on the laptop:
`omen-tunnels-external laptop start tracing thesis-postgres thesis-redis minio-api tracing-clickhouse-http`
(or the list they choose), and to confirm it printed "Ready".

### T2. Reach Omen services from the compute node

In a shell on the job (`srun --overlap`):

```bash
ls -l ~/.ssh/id_ed25519_webis_tunnel || echo "tunnel key missing"
omen-tunnels-external compute start tracing thesis-postgres thesis-redis minio-api tracing-clickhouse-http
omen-tunnels-external compute status
```

Then check each port with a read-only call, for example `pg_isready -h 127.0.0.1 -p <port>`,
`redis-cli -p <port> ping`, and `curl -s -o /dev/null -w '%{http_code} %{time_total}\n' http://127.0.0.1:<port>/`
for HTTP services. Use `omen-tunnels-external list` for the compute ports. Measure the median of 100 Redis
`PING` round trips (`redis-cli -p <port> --latency -i 1` for ~30 s, or a short Python loop).
Skip the MinIO upload from `infra-tests-next.md` unless the user names a scratch bucket you may write to.

Pass: every service answers. Record the latency and any service that fails, with its error.

### T4. Two tunnels on one node

In a second `srun --overlap` shell on the same job, run the same `compute start`. Record whether it says
"Already running", fails with a clear message, or breaks the first tunnel (check
`omen-tunnels-external compute status` from the first shell). Stop the second only if it started.

### T3. Long-run stability (**USER** involvement)

Write `tests/T3/heartbeat.py`: every second, ping one tunnelled service read-only (Redis `PING` or
Postgres `SELECT 1`) and append `{time, ok, latency_ms, error}` to `tests/T3/heartbeat.jsonl`. Run it in
the background for 8 h. Ask the user to put the laptop to sleep for 2 min at a time they choose, and tell you
when. Afterwards report: total downtime, how long until the drop was noticed, and whether the tunnel came
back without a manual restart. (The harness-side behaviour — backfilling events after a drop — waits for
the harness and is not part of this run.)

## Step 5: the harness's neighbourhood (stack running)

### S3. What an agent command can reach

From a plain shell in the job, without sourcing `.env` (that is what an agent command would see), try every
port: 4000, 8010, 8001, 8002, 8004, and every tunnelled compute port. For each record: does it answer, and
does it answer without credentials? For example `curl -s http://127.0.0.1:8001/v1/models` (raw vLLM, no
auth expected), `curl -s http://127.0.0.1:4000/v1/models` (should be 401), `redis-cli -p <port> ping`
(answers without `AUTH`?), and `psql -h 127.0.0.1 -p <port> -U postgres -c 'select 1'` with no password set.
Read-only: do not attempt writes. Also record `env | grep -i -E 'key|token|pass|secret' | cut -d= -f1`
(names only) for a shell that has not sourced `.env`.

Pass: nothing that holds traces or data answers without credentials, and no secret names appear in a plain
shell. Every port that answers anonymously is a finding; list it.

### S1. Runaway commands

Write `tests/S1/run.sh` that runs each case under the limits proposed in `decisions-after-tests.md` §4
option 3 (`ulimit -v 8000000`, `timeout 120`), and logs exit codes and `/v1/status` before and after:

1. `python3 -c "x=' '*10**11"` (memory)
2. `python3 -c "while True: pass"` (CPU, should hit `timeout`)
3. `dd if=/dev/zero of=/tmp/s1-fill bs=1M count=20000; rm -f /tmp/s1-fill` (20 GB in tmpfs `/tmp`)

Pass: each case stops on its limit and all backends stay ready. Also record the job's memory limit
(`cat /sys/fs/cgroup/$(cut -d: -f3 /proc/self/cgroup)/memory.max` or `scontrol show job <id>`).
Run case 3 without a size limit only if `/tmp` is tmpfs and the job has more than 30 GB of headroom; delete the
file right after. Do not run case 1 without `ulimit`: if it is needed, ask the user first, because it can
kill the model servers.

### S2. Job end and backend restart

1. Write `tests/S2/fake_run.py`: append one hash-chained event per second to
   `tests/S2/run/events.jsonl` (reuse the format from `tests/C1/capping.py`), with an `fsync` per event and
   a SIGTERM handler that writes a final `run_aborted` event.
2. Start it in the job, then `scancel` the job (it sends SIGTERM to the steps). Verify the chain with
   `tests/C1/verify_chain.py` (adapt the path) and check that `run_aborted` is the last event.
3. In a new job, start it again, kill one backend's vLLM process, and record how long until `/v1/status`
   shows it ready again (the supervisor restarts it).

## Step 6: finish

1. Add rows for T1–T4, L1–L5 and S1–S4 to `tests/RESULTS.md`.
2. Below the table in `docs/infra-tests-next.md`, add a short "Round 2 results" section: one line per test
   with pass/fail and the number that matters, and a list of anything that changes a decision in
   `docs/decisions-after-tests.md` (especially S4: egress and Apptainer).
3. Commit on `infra-round-2` (and `agent-layout` in the submodule) and push `infra-round-2` if you can.
4. Stop every job and tunnel you started (`scancel`, `omen-tunnels-external compute stop`). Kill `heartbeat.py`
   only after T3 has run for 8 h.
5. Report to the user: what passed, what failed with the exact error, what was not run and why, and every
   **USER** step still open.
