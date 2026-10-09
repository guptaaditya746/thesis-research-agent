# Infrastructure tests still to run (Slurm + Omen services)

*9 Oct 2026. Follows `tests/RESULTS.md` and `docs/decisions-after-tests.md`.*

The first test round (`docs/slurm_test_plan.md`) measured the models and the node. It did not test the
setup the system will actually run in:

- the models are started by `related/final-final-llm-setup` (sbatch job, LiteLLM on `127.0.0.1:4000`,
  status on `:8010`), not by the hand-written `vllm serve` scripts used in A2 to C2;
- the harness runs inside that Slurm job, because every port binds to `127.0.0.1`;
- Docker Compose cannot run on Slurm, so Postgres, Redis, tracing, MinIO and ClickHouse stay on the Omen
  machine and reach the node only through `scripts/omen-tunnels` (Omen → laptop → Webis gateway → compute).

The tests below cover that gap. Each one says why it is needed and which doc it comes from. Logs go to
`tests/<id>/`, and each test adds one row to `tests/RESULTS.md`, as before.

## Findings from reading the code (fix before testing)

1. **`omen-tunnels-external` has no effect.** The wrapper sets `OMEN_TUNNELS_GATEWAY_PORT_OFFSET=1000`, but
   `scripts/omen-tunnels` never reads that variable, so the external gateway gets the normal ports. Test T1.
2. **`llm-setup` cannot start the chosen model layout.** `profile.py` accepts only the roles `heavy`, `lite`
   and `embed`, with one backend each. `decisions-after-tests.md` §1 needs Qwen3.8 as the orchestrator plus two
   Heavy replicas behind one alias. `supervisor._command` also does not pass `--reasoning-parser qwen3` or
   `--generation-config vllm`, which `tests/A2/serve_qwen38.sh` used. Test L1.
3. **LiteLLM is rendered with `drop_params: True`.** This can silently drop `chat_template_kwargs`.
   Qwen3.8 is a hybrid thinking model, so if `enable_thinking: false` is dropped, the orchestrator thinks on
   every step and the B3 compliance result (measured direct to vLLM) no longer applies. Test L2.

## T: tunnels to Omen

| id | Test | Why | Pass |
|---|---|---|---|
| T1 | Run `omen-tunnels-external laptop start --dry-run thesis-postgres` and the `compute` equivalent. Fix the script to add the offset to the gateway ports, then run again. | Finding 1. Without the offset, the external gateway uses ports another session may hold, and the README's description of the wrapper is wrong. | The `-R` and compute `-L` lines show gateway port + 1000 (e.g. 55433 → 56433). |
| T2 | Inside the GPU job (`srun --jobid <id> --overlap --pty bash -l`), run `omen-tunnels-external compute start <services>` for the services the system will use. Then connect to each one: `psql`, `redis-cli ping`, an HTTP GET for tracing/MinIO/ClickHouse. | Nothing has yet confirmed that a Slurm step can open the compute hop: the key `~/.ssh/id_ed25519_webis_tunnel` must exist on the node, and the gateway must allow `-L`. Docker Compose is not available on Slurm, so this tunnel is the only path to the stateful services. | Every chosen service answers on its compute port. Record the round-trip latency (median of 100 pings) and the time for a 100 MB MinIO upload. |
| T3 | Keep the tunnel up for 8 h while a fake agent writes one event per second to the tracing service. Midway, kill the gateway hop and then put the laptop to sleep for 2 min. | The chain passes through the laptop, and an evaluation run lasts 30 to 45 min, 40 runs in total (`decisions-after-tests.md` §6). SSH keep-alive (30 s × 3) notices a drop after about 90 s. The run must not depend on the tunnel staying up. | The harness keeps writing `events.jsonl` on disk (the source of truth, `plan.md` "Interceptor"), logs a `sink_down` event and backfills when the tunnel is back. No step is lost or duplicated. |
| T4 | Start the compute hop twice on the same node, from two job steps or two jobs. | Compute ports are fixed on `127.0.0.1`, and the state directory is keyed by hostname. A second job on the same node will collide. | The second start fails with a clear message, or the ports are made per-job. Record which. |

## L: model stack through `final-final-llm-setup`

| id | Test | Why | Pass |
|---|---|---|---|
| L1 | Extend `llm-setup` for the agent layout: an `orch` role (Qwen3.8-27B-FP8, GPU 0, 65,536 tokens, reasoning parser) and `sub` with two replicas on GPUs 1 and 2. Add profile `profiles/agent-3x40.yaml`, start it with `sbatch slurm/llm-stack.sbatch`, then run `llm-setup doctor`. | Finding 2. `decisions-after-tests.md` §1 picked this layout, and the README of the setup repo makes `llm-setup` the only supported way to serve. Embed is not needed: the new design has no index (`context.md` §3). | All backends `ready` in `/v1/status`. `max_model_len` and KV tokens match A2 (79,371 for Qwen3.8). Startup completes within `STARTUP_TIMEOUT_S`, since the cold start measured in A2 was 8.5 min. |
| L2 | Re-run A7 with Qwen3.8 through LiteLLM: send the same request with `chat_template_kwargs: {enable_thinking: false}` direct to vLLM and through `:4000`. Then re-run B3 (20 + 20 prompts) through the proxy. | Finding 3. A7 was inconclusive because its model could not think anyway. `CONSUMERS.md` forbids raw vLLM ports, so the harness has to use the proxy. | Through the proxy: no `reasoning_content`, reasoning tokens 0, and B3 still ≥ 95% one-block compliance. If the field is dropped, set `drop_params` per model or allow-list the field, and record the change. |
| L3 | Run A4 again through the proxy with the `sub` alias: 4 and 8 concurrent 16k–32k requests. Scrape `/metrics` on both replicas. | `decisions-after-tests.md` §1 relies on round-robin over two replicas for a fan-out of 4 to 8. LiteLLM's `max_parallel_requests` and its 120 s `request_timeout` may queue or cut requests before vLLM sees them. | Both replicas receive load (split within 60/40), 0 preemptions, no 408 or 429 responses from LiteLLM. Record p95 latency against A4. |
| L4 | Check the proxy's retry on 5xx (`InternalServerErrorRetries: 1`): kill one backend during a request. | A retried model call is a second call the interceptor must log. Otherwise the hash-chained log (C1) records one call where two happened. | The harness logs both attempts, or the retry is disabled for the agent's alias. |
| L5 | Time a second start of the stack in the same job and in a new job, with the vLLM/torch compile cache on Ceph instead of the node-local `/tmp`. | Qwen3.8 took ~8.5 min to start (A2), including 114 s of compilation. The venv and caches on `/tmp` are lost with each allocation (`.env.example`). | Record time-to-ready for both. Keep the compile cache on Ceph if it saves more than 1 min. |

## S: the harness inside the Slurm job

| id | Test | Why | Pass |
|---|---|---|---|
| S1 | Run a fake harness in an `srun --overlap` step. One command allocates memory until it fails (`python3 -c "x=' '*10**11"`), and another writes 20 GB to `/tmp`. | Agent commands, the harness and vLLM share one job with 16 CPUs and 64 GB. Without a sandbox (A6), an agent's script that runs away could OOM-kill the model servers. `/tmp` is tmpfs (A1), so files written there count as RAM. | `ulimit -v` and `timeout 120` per command (`decisions-after-tests.md` §4 option 3) stop the command. vLLM stays healthy in `/v1/status`. Record the limit values that work. |
| S2 | Run `scancel` on the job during a fake run, and separately let a backend crash so the supervisor restarts it. | The job has a 48 h limit and sends SIGTERM 180 s before it ends (`llm-stack.sbatch`). A run that dies mid-step must still leave a valid run directory (`plan.md`: the run directory is the contract). | The run directory is on Ceph, the hash chain verifies up to the last event, and a `run_aborted` event is present. After a backend restart the harness waits and continues instead of crashing. |
| S3 | From an agent-style command, try every local port: LiteLLM 4000, status 8010, raw vLLM ports, and every tunnelled Omen port. | There is no network namespace, so every command can reach 127.0.0.1. Raw vLLM ports have no auth, and the tunnelled databases expose the trace store. `plan.md` "Logging from outside" requires that the agent cannot reach or change its own trace. | No credentials in the agent's environment, and the trace store refuses writes or deletes without them. Record every port that answers anonymously. |
| S4 | On the node, check egress: `curl -m 5 https://example.com` and `curl -m 5 https://huggingface.co`. Also run `which apptainer singularity`. | `decisions-after-tests.md` §4 option 3 assumes the node has no direct internet. The sbatch file runs `uv sync` and downloads from Hugging Face, which suggests it does. Apptainer is the preferred sandbox (§4 option 1). | Record yes/no for each. If egress exists, the "no network" guardrail needs Apptainer or the admins; the convention-only option 3 does not hold. |

## Still open from the first round (unchanged, see `RESULTS.md`)

- **Blocked on the harness and a sandbox decision:** B5, C3, C4, C5, C6, C7.
- **Re-run on full-text Docling files once the corpus is frozen:** C1 and D4 (`decisions-after-tests.md` §5).
- **Re-run with a realistic 30k-token history:** C2, through the proxy after L2.

## Order

1. T1, S4, L1 (half a day): fix the wrapper, learn whether the node has egress and Apptainer, and get the
   chosen models running under `llm-setup`.
2. L2, L3, T2, S3 (half a day): the proxy keeps thinking off, the replicas share load, the tunnels work
   from the job, and nothing the agent can reach is unprotected.
3. S1, S2, L4, T3, T4, L5 (one day): failure behaviour of the job, the proxy and the tunnel.
4. Then the blocked tests above, once the minimal harness exists.
