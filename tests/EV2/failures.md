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
