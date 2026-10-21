# EV2 failures

## Step 0.4 — stack doctor reports existing listeners as unowned

- Command: `srun --jobid 7609 --overlap "$EV/in-job.sh" bash -lc 'set -o pipefail; cd "$REPO/llm-setup"; set -a; source /mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/llm-setup/.env; set +a; uv run llm-setup doctor --profile profiles/agent-3x40.yaml'`
- Exit code: 1.
- Complete output (six diagnostic lines):
  ```text
  FAIL  port 8001 (orch): in use with no session running: another server holds it (`ss -ltnp | grep :8001`)
  FAIL  port 8002 (sub): in use with no session running: another server holds it (`ss -ltnp | grep :8002`)
  FAIL  port 8004 (sub-2): in use with no session running: another server holds it (`ss -ltnp | grep :8004`)
  FAIL  port 4000 (gateway): in use with no session running: another server holds it (`ss -ltnp | grep :4000`)
  FAIL  port 8010 (status): in use with no session running: another server holds it (`ss -ltnp | grep :8010`)
  First problem: GPU 0 (orch): 35771 MiB already in use with no session running: a leftover process (nvidia-smi)
  srun: error: gammaweb07: task 0: Exited with exit code 1
  ```
- Follow-up: stack job 7609's runtime log reports `orch`, `sub`, `sub-2`, gateway, and status ready with no restarts. Continue with protocol and smoke checks, then use the pilot result to judge availability. Do not start or cancel another stack while this allocation is active.

## Step 1.0 — pilot retention below threshold

- Command: `uv run synth build --name rag-llm-pilot --seed 1 --studies 3 --renderer llm --levels all --model sub-model-1 --verify-model sub-model-2 --out "$CORPORA" --cache "$EV/cache/synth-llm.jsonl"`
- Exit code: 1; completed 2026-10-21 16:38 CEST.
- Retention: 0/3 (0%). All three failed fidelity and were left out. Per-level: explicit 3/3, paraphrased 3/3, distributed 1/3, complex 3/3, contradictory 0/3. The contradictory level failed `required_strings` for all three; distributed failed `required_strings` for two.
- Per runbook, do not start step 1.1. Continue with the user-requested EV1 corpus runs.

## Protected renderer experiments — live verifier failures remain

- Original pilot retained 0/3 families; protected assembly with the original verifier retained 2/3.
- First source-reading verifier retained 0/3: it emitted `see text` as a number in all complex papers.
- Final numeric-schema/repair experiment retained 1/3: explicit S003 invented relative comparison quotes; complex S001 included an extra wrongly attributed value. All distributed and contradictory papers passed.
- Final synth suite: 269 passed in 88.26 seconds. Passing deterministic tests does not resolve live model failures.
- Full diagnosis and reproduction details: `docs/claude-ev2-handoff.md`. The user requested commit/push of this current state, with failures documented. Further fixes and remaining overnight steps were not executed in this handoff.

## EV2b continuation — 2026-10-21

### Step 1–2 manifest-check first attempt

- Command: `python "$EV/check-manifest.py" "$C"` in the 41-corpus manifest loop.
- Exit code: 1. The login environment has `python3`, but no `python` executable; the corpus copy completed.
- Last output lines:
  ```text
  /usr/bin/bash: line 18: python: command not found
  FAIL rag-tpl-s1-paraphrased
  cf-llm ok
  cf-tpl ok
  total corpora: 41
  ```
- Action: reran with `python3`; all 41 manifests passed, both counterfactual variant paths passed. Full manifest and selection summaries are in `logs/1-2-manifests.log` and `logs/1-2-selection.json`.

### Step 0.2 replacement stack pending

- User directed that job 7609 stay running. It remains `RUNNING` on gammaweb07.
- Submitted `LLM_SETUP_PROFILE=profiles/orch-3x40.yaml sbatch slurm/llm-stack.sbatch`; new job 7623 requests 3 ampere GPUs and remains `PENDING (Priority)`.
- Steps 0.4 (doctor and offline smoke) and 0.5 (live check) cannot start until 7623 is allocated. Continue polling; do not cancel 7609.

## EV2b user-selected job 7609

- Step 0.4 doctor on matching `profiles/agent-3x40.yaml` exited 1: the running job's three GPUs and service ports are occupied, as expected for already-running servers; both weight checks passed. The user instructed us to use this job. Regex-only smoke checks passed; logs are `logs/0.4-doctor-7609.log` and `logs/0.4-smoke-7609.log`.
- Step 0.5's first direct `srun --jobid 7609 --overlap` failed before starting with `unable to initialize step request socket: Address already in use`. Retried through `launch.sh`; see `logs/0.5-live-check-7609.launch` and `.log`.

## Finish size preflight

`find tests/EV2 -type f -size +1M` finds the pre-existing committed frozen corpus file `corpora/rag-tpl-hard-complex/ground_truth.json` (1,278,474 bytes). It is unchanged and will remain as committed; report it as a size exception. Secret scan passed when using the ignored `.env` from the original clone, without printing the key.
- Step 3 setup missed `PE` on first launch; corrected the job environment. A detached retry hit the expected `srun` socket collision and exited before recording a final status. Retried with the launch helper in a foreground session.
- Step 3 initially followed per-level order instead of the runbook's priority list. Cancelled only step 7609.25 (job 7609 remains running), preserved its partial explicit run artifacts under Ceph, reordered lane 3 and restarted with `rag-claude-s1-mixed` first. Lane 5 and 6 were left running.
- Lane 6 began before I corrected its corpus order; completed baseline outputs are `rag-claude-s1-mixed`, `rag-claude-k1-mixed`, and the LLM counterfactual, then the active script proceeds to the hard corpora. This is a priority-order deviation only; no run failed. The script on disk is corrected.
