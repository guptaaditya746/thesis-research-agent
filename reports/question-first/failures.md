# EV3 failures

## Step 1.5 — stack job 7947

Command: `LLM_SETUP_PROFILE=profiles/orch-3x40-gliner.yaml sbatch slurm/llm-stack.sbatch`

Slurm state: FAILED; exit code 1:0. Both orch-2 and orch-3 failed with `torch.distributed.DistNetworkError: EADDRINUSE` at port 19152. The pinned launcher exports one VLLM_PORT for all replicas.

Next action: asked for authorization for a replica-specific port fix because the EV3 runbook forbids code changes. No model runs launched; offline checks continue independently.

Last 30 stack log lines:

```text
Installed 1 package in 3ms
 + gliner==0.2.29
[07:50:58] starting the stack in the foreground
[0:00:00] checking the profile and vLLM options
[0:00:08] session 20261028T065106Z-e8f7ebcc on gammaweb07; logs in runtime/20261028T065106Z-e8f7ebcc
[0:00:08] models: orch on GPU 0, orch-2 on GPU 1, orch-3 on GPU 2 (loading in parallel; usually 5-20 min)
[0:00:24] orch: initialising the engine (0:00:16) · orch-2: initialising the engine (0:00:16) · orch-3: initialising the engine (0:00:16)
error: startup failed in session 20261028T065106Z-e8f7ebcc: orch-2 exited with status 1 before it became healthy
--- last lines of runtime/20261028T065106Z-e8f7ebcc/orch-2.log ---
(APIServer pid=2447667)     ) as (engine_manager, coordinator, addresses, tensor_queue):
(APIServer pid=2447667)     ^
(APIServer pid=2447667)   File "/tmp/xepi3167/llm-setup/python/cpython-3.13.12-linux-x86_64-gnu/lib/python3.13/contextlib.py", line 148, in __exit__
(APIServer pid=2447667)     next(self.gen)
(APIServer pid=2447667)     ~~~~^^^^^^^^^^
(APIServer pid=2447667)   File "/tmp/xepi3167/llm-setup/venv/lib/python3.13/site-packages/vllm/v1/engine/utils.py", line 1128, in launch_core_engines
(APIServer pid=2447667)     wait_for_engine_startup(
(APIServer pid=2447667)     ~~~~~~~~~~~~~~~~~~~~~~~^
(APIServer pid=2447667)         handshake_socket,
(APIServer pid=2447667)         ^^^^^^^^^^^^^^^^^
(APIServer pid=2447667)     ...<6 lines>...
(APIServer pid=2447667)         coordinator.proc if coordinator else None,
(APIServer pid=2447667)         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(APIServer pid=2447667)     )
(APIServer pid=2447667)     ^
(APIServer pid=2447667)   File "/tmp/xepi3167/llm-setup/venv/lib/python3.13/site-packages/vllm/v1/engine/utils.py", line 1187, in wait_for_engine_startup
(APIServer pid=2447667)     raise RuntimeError(
(APIServer pid=2447667)     ...<3 lines>...
(APIServer pid=2447667)     )
(APIServer pid=2447667) RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {}
logs: runtime/20261028T065106Z-e8f7ebcc
```

User authorized a minimal replica-specific port fix and continuation. Regression check: `uv run --extra dev pytest tests/test_replica_ports.py -q`; patch and test logs retained with the final report.

Applied the authorized fix in `llm_setup.supervisor.build_services`: each model gets the job base VLLM_PORT plus 4 times its model index. Regression changed from shared-port assertion failure to 1 passed; full llm-setup suite: 63 passed (5 deprecation warnings). Replacement job 7954 submitted. Evidence engine and scoring code remain at ev3-code.

- 2026-10-28 08:53 Europe/Berlin: An initial hard-grid launch mistakenly used nonexistent `rag-claude-s1-hard`; engine and RAG commands failed looking for its manifest. Slurm step 7954.78 was cancelled and the grid restarted as `grid-hard-corrected` using the pinned `rag-tpl-hard-complex` corpus. These were launch-path errors, not model or evaluation failures; the failed launch log is retained.

- The completed hard grid logged `UnexpectedModelBehavior: Exceeded maximum output retries (1)` for agent baselines `inv-metrics` and `inv-methods`; no answer.json was produced for those two cells, so their initial reports lack those systems. The remaining grid completed; `retry-hard-agents` reruns only the missing baselines and rescores, using the existing corpus-specific cache. See `logs/grid-hard-corrected.log` and `logs/retry-hard-agents.log` for outcomes.

- The first hard per-paper pass failed output validation for `rag-factuality`, `rag-hallucination`, `inv-metrics`, `inv-methods` and `inv-datasets`; the other five questions produced scored outputs. After that pass ended, `retry-hard-per-paper` began a single retry pass, reusing completed outputs. See its log for final outcomes.
- The main `rag-oracle` `cons-accuracy` comparison failed output validation; `retry-main-oracle-cons` retries it after the oracle variant completed, using its separate cache. See both logs for outcomes.
- The first counterfactual shift launch referenced a helper before it was created and exited 127; `shift-cf-ready` ran the runbook command successfully after creating it.
- `retry-hard-per-paper` recovered hard `rag-factuality` and `rag-hallucination`; `inv-metrics`, `inv-methods` and `inv-datasets` still failed. `retry-hard-per-paper-last` attempts these three a second and final time; see that log for outcomes.
- `retry-main-oracle-cons` recovered the main `rag-oracle` `cons-accuracy` answer and score.
- `retry-hard-agents` recovered the hard `inv-metrics` agent answer and rescored it; `inv-methods` is attempted next.
- Hard `rag-per-paper-k1` `inv-metrics` also failed its second retry with output validation; the retry limit is reached and this extra score remains missing unless an already successful artifact appears. See `logs/retry-hard-per-paper-last.log`.
- Hard `rag-per-paper-k1` `inv-methods` also failed its second retry with output validation; the retry limit is reached and this extra score remains missing. See `logs/retry-hard-per-paper-last.log`.
- Hard `rag-per-paper-k1` `inv-datasets` also failed its second retry with output validation; the retry limit is reached and this extra score remains missing. See `logs/retry-hard-per-paper-last.log`.
- Hard agent `inv-methods` failed again on the first retry with `UnexpectedModelBehavior: Exceeded maximum output retries (1)`. Its research trace also records `context_window_exceeded` near the 65,536-token limit; the agent returned no mapped answer. `retry-hard-agent-methods-last` attempts it one final time; see its log for the outcome.
- `retry-hard-agent-methods-last` recovered hard `inv-methods` with 13 mapped entries and a submitted agent answer; the grid report was rescored. All 20 grid cells now have engine, RAG and agent answers. The prior context-limit and validation failures remain recorded.
