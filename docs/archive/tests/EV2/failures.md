# EV2b failures and deferred steps

## Step 1–2 manifest-check first attempt

- Command: `python "$EV/check-manifest.py" "$C"` in the 41-corpus manifest loop.
- Exit: 1.
- Cause: this login environment has `python3` but no `python` executable. The corpus copy itself completed; no files were changed under the repository corpora.
- Last output lines:

```text
/usr/bin/bash: line 18: python: command not found
FAIL rag-tpl-s1-paraphrased
cf-llm ok
cf-tpl ok
total corpora: 41
```

- Action: reran the same checker with `python3`; all 41 manifests passed, and both counterfactual variant paths passed.

## Step 0.2 stack allocation

- Job 7609 (`llm-stack`, old agent-3x40): RUNNING on gammaweb07. User instructed to leave it running.
- Submitted the required `LLM_SETUP_PROFILE=profiles/orch-3x40.yaml sbatch slurm/llm-stack.sbatch`; new job 7623 is PENDING (`Priority`) with 3 ampere GPUs requested.
- Doctor, live check, and model steps are deferred until Slurm allocates 7623. Continue polling; do not cancel 7609.

## Step 0.4 doctor on the user-selected job 7609

- Command: `srun --jobid 7609 --overlap "$EV/in-job.sh" bash -lc 'cd "$REPO/llm-setup" && uv run llm-setup doctor --profile profiles/agent-3x40.yaml'`
- Exit: 1. This matches 7609's `agent-3x40` profile. Doctor reported all three GPUs and ports 8001, 8002, 8004, 4000, 8010 occupied by already-running processes, while both model weight checks passed.
- Action: used the existing stack as requested; regex-only smoke runs completed successfully. Continue the live `orch-model` check to validate the gateway.

## Step 0.5 direct Slurm step-creation attempt

- Command: the step 0.5 live-check shell launched directly with `srun --jobid 7609 --overlap`.
- Exit: 1 before the command started.
- Output:
  ```text
  srun: error: unable to initialize step request socket: Address already in use
  srun: error: Unable to create step for job 7609: Address already in use
  ```
- Action: retried through `$EV/launch.sh`, which handles this exact socket collision. The retry is currently running.

## Step 3 first launch — missing `PE` in the prepared job environment

- Command: `"$EV/launch.sh" 3-engine "$EV/engine.sh"` on job 7609.
- Exit: 1 before any corpus run. `engine.sh` reported `PE is not set: run step 0.6 first`.
- Cause: step 0.6 produced the escalate protocol, but its path was not exported in the fresh EV2b `in-job.env`.
- Action: added `export PE=$EV/rag-factuality-escalate.yaml`; retry as step `3-engine-r1` with the same untouched cache.

## Finish artifact size preflight

- `find tests/EV2 -type f -size +1M -print` reports the already-committed `tests/EV2/corpora/rag-tpl-hard-complex/ground_truth.json` (1,278,474 bytes).
- This is part of the frozen corpus already on `origin/ev3/claude-writer`; it is not a copied run output. Preserve the committed corpus unchanged; report this size exception. New run outputs over 1 MB will remain on Ceph and be listed separately.
- Secret scan passed after sourcing the ignored `.env` from the original clone; no key values were printed.

## Step 3 launch attempts and priority-order correction

- `3-engine` failed before starting because the fresh `in-job.env` omitted the step 0.6 `PE` path (exit 1; log `3-engine.log`). Added the correct PE export.
- `3-engine-r1` hit `srun: error: unable to initialize step request socket: Address already in use`. Its detached retry process exited without writing a final `.launch` status. Recovered by invoking the launch helper in a foreground session as `3-engine-r2`.
- `3-engine-r2` began `rag-claude-s1-explicit` before the runbook's priority corpus `rag-claude-s1-mixed`. After confirming `7609.25` was only this engine step, cancelled that step with `scancel 7609.25`; job 7609 remains RUNNING. Preserved its completed regex-only and partial cascade directories under `$EV/partial/out-of-priority/`; the engine cache is retained.
- Reordered the external engine and baseline scripts to the runbook's priority list. Restarting lane 3 as `3-engine-priority`; step 5 and 6 continue on their separate caches.

## Step 6 lane order note

The baseline lane had already launched using its original list before the lane priority was rechecked: it completed `rag-claude-s1-mixed`, then `rag-claude-k1-mixed` and the LLM counterfactual before the hard corpora. The loaded process cannot be reordered; it is continuing without restart and will process the hard corpora next. No run failed. The on-disk baseline script now follows the runbook priority for any later invocation.

## User-directed transition from job 7609 to orch-only job 7636

- The user cancelled the running job 7609 to try the replacement allocation. Its active Slurm steps 7609.26 (agentic), 7609.27 (baselines), and 7609.28 (engine) were terminated at about 20:21 CEST. Completed files remain under `$EV/runs`; event/call files in interrupted directories may be partial.
- Before the transition, checkpoint `$EV/checkpoints/20261021T181941Z` captured 2,430 files (30 MB); all 2,430 checksums verified. It contains copies of runs, caches, logs, agent work, partial outputs, lane scripts, and this failure report as it stood at checkpoint time.
- Replacement stack job 7636 started on gammaweb07 using `profiles/orch-3x40.yaml`, `llm-setup` commit `22dae03`. All three orch replicas, gateway, and status service report ready.
- `llm-setup doctor --profile profiles/orch-3x40.yaml` run on gammaweb07 passed all GPU, model health, gateway alias, and status checks. `--smoke` also returned HTTP 200 for `orch-model`.
- An earlier doctor launched through `srun` also inherited the mismatched key and exited 1 with `gateway models: missing orch-model`. After correcting the key source, the direct doctor and all three replica completion checks passed.
- Resumption scripts now skip complete outputs and move incomplete output directories under `$EV/partial/interrupted-<timestamp>/` before retrying. Existing caches are retained for reuse; each long lane keeps its own cache.

## Wrong master key on first resumed-lane attempt

- The first lane launch on job 7636 sourced `LITELLM_MASTER_KEY` from the original `thesis-research-agent/llm-setup/.env`, while the gateway was started with the key from the `evidence-ev2b/llm-setup/.env` worktree. The keys differ. Engine outputs were mostly served from the existing cache; agentic model calls failed with LiteLLM `No connected db.` because the gateway treated the mismatched key as a non-master key and has no DB-backed virtual-key store.
- Stopped only experiment steps 7636.15–7636.17; job 7636 and its three model services remain running.
- Corrected `$EV/in-job.env` to source the EV2b worktree `.env`. Confirmed three concurrent direct completion checks against `orch-model-1`, `orch-model-2`, and `orch-model-3` returned HTTP 200.
- Resumed engine/agentic commands now pass `--retry-errors` so errors cached during the wrong-key attempt are retried and stored as a new attempt. Complete outputs remain; incomplete run directories are quarantined before retry.

- Step 6.1 recovery: the initial RAG-oracle pass left `rag-tpl-hard-complex` without `answer.json`; a dedicated rerun is queued after the engine lanes to avoid sharing the model/cache concurrently.

## Step 0.1 Linux suite

- `uv run pytest -q -W ignore::SyntaxWarning` on `evidence-ev2b` exited 0: 1545 passed, 1 skipped, one Pydantic deprecation warning, in 2169.22 seconds. Full log: `tests/EV2/logs/0.1-pytest.log`.

- 6-oracle-hard-complex failed (exit 1); see /mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-ev2b/logs/6-oracle-hard-complex.log

## Step 6.1 retry: RAG oracle on the hard complex corpus

- Command: `"$EV/launch.sh" 6-oracle-hard-complex "$EV/oracle-hard-complex.sh"` (job 7636); inner command: `uv run evaluate rag-baseline --oracle-passages --corpus "$CORPORA/rag-tpl-hard-complex" --out "$RUNS/rag-oracle-passages/rag-tpl-hard-complex" --cache "$CACHE/rag-oracle.jsonl" --model orch-model`.
- Exit: 1. The final request exceeded Orch's 65,536-token context window: 61,441 input tokens plus 4,096 requested output tokens. Full traceback: `logs/6-oracle-hard-complex.log` (last 30 lines in the launch log).
- Follow-up: no retry with a modified retrieval prompt; continue with step 4. This corpus-level RAG oracle result is missing and will be reported as a failure.

Last 30 lines of `logs/6-oracle-hard-complex.log`:

```text
                          seed=args.seed, oracle=args.oracle_passages)
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/evidence-ev2b/evaluation/baselines/rag.py", line 196, in rag_baseline
    answer, call = cached_reply(cache, INSTRUCTIONS, user_prompt(question, hits), model=model, model_id=model_id,
                   ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                seed=seed, output_type=CitedAnswer)
                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/evidence-ev2b/evaluation/baselines/common.py", line 136, in cached_reply
    answer = ask_sync(Prompt.inline(instructions, output_type), prompt, model=model,
                      settings=CallSettings(seed=seed, max_tokens=max_tokens), cache=cache, key=record)
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/evidence-ev2b/modelcall/call.py", line 168, in ask_sync
    return run_sync(ask(prompt, user_prompt, model=model, settings=settings, cache=cache, key=key,
                        refresh=refresh, extra=extra, timeout_s=timeout_s))
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/evidence-ev2b/modelcall/loop.py", line 44, in run_sync
    return asyncio.run_coroutine_threadsafe(coro, loop).result()
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/.local/share/uv/python/cpython-3.13.12-linux-x86_64-gnu/lib/python3.13/concurrent/futures/_base.py", line 456, in result
    return self.__get_result()
           ~~~~~~~~~~~~~~~~~^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/.local/share/uv/python/cpython-3.13.12-linux-x86_64-gnu/lib/python3.13/concurrent/futures/_base.py", line 401, in __get_result
    raise self._exception
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/evidence-ev2b/modelcall/call.py", line 154, in ask
    reply, messages = await on_model_loop(_attempt(prompt, user_prompt, model, settings, timeout_s))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/evidence-ev2b/modelcall/loop.py", line 51, in on_model_loop
    return await coro
           ^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/evidence-ev2b/modelcall/call.py", line 129, in _attempt
    raise err from None
modelcall.call.ModelCallError: ModelHTTPError: status_code: 400, model_name: orch-model, body: {'message': "litellm.ContextWindowExceededError: litellm.BadRequestError: ContextWindowExceededError: OpenAIException - This model's maximum context length is 65536 tokens. However, you requested 4096 output tokens and your prompt contains at least 61441 input tokens, for a total of at least 65537 tokens. Please reduce the length of the input prompt or the number of requested output tokens. (parameter=input_tokens, value=61441)\nmodel=orch-model. context_window_fallbacks=None. fallbacks=None.\n\nSet 'context_window_fallback' - https://docs.litellm.ai/docs/routing#fallbacks. Received Model Group=orch-model\nAvailable Model Group Fallbacks=None", 'type': 'invalid_request_error', 'param': None, 'code': '400'}
srun: error: gammaweb07: task 0: Exited with exit code 1
```

- 9-propose-live failed (exit 2); see /mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-ev2b/logs/9-propose-live.log

## Final score refresh and packaging status (22 Oct)

- The resumed engine completion added all four strategies for the six three-paper Claude pilot corpora and completed the missing four-strategy `rag-tpl-s1-mixed` group. Each pilot × strategy run was scored.
- `7-postscore` exited 0 on try 1. It refreshed the `rag-tpl-s1-mixed` reports with baseline/oracle answers, refreshed global comparisons, and generated lexical and funnel comparisons for the template mixed corpus and all six pilot corpora.
- Dashboard rebuild completed: 94 reports and 39 corpora detected. The six-pilot cascade `all` evidence-type P/R/F1 values are recorded in `tests/EV2/summary.md`.
- No new run artifact exceeded 1 MiB. The only oversized file is the already committed `tests/EV2/corpora/rag-tpl-hard-complex/ground_truth.json` (1,278,474 bytes); it is unchanged.
- Remaining user-only items: step 8 fidelity review; step 10 proposal card decisions and any explicit human waiver for blocking critic checks. No waiver was made.
