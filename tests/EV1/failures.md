# Failures

## Tunnel UI route test loader
- Step: UI tunnel support implementation (targeted test)
- Exact command: `uv run pytest tests/T3/test_omen_tunnels_ui.py -q`
- Exit code: 2
- Last output lines:
  ```
  ERROR collecting tests/T3/test_omen_tunnels_ui.py
  tests/T3/test_omen_tunnels_ui.py:9: in <module>
      assert SPEC and SPEC.loader
  E   assert (None)
  ERROR tests/T3/test_omen_tunnels_ui.py - assert (None)
  Interrupted: 1 error during collection
  1 error in 20.76s
  ```
- Next: corrected the loader and reran the targeted test (3 passed); fix commit `5fc5235`.

## LLM synthesis paused for interactive UI run
- Step: 1 LLM corpus synthesis (`rag-llm-s1`)
- Exact command: `nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" uv run synth build --name rag-llm-s1 --seed 1 --studies 20 --renderer llm --levels all --model orch-model --verify-model sub-model-2 --out "$CORPORA" --cache "$EV/cache/synth-llm.jsonl" > "$EV/logs/1-synth-main.log" 2>&1 &`
- Exit code: 143 (terminated with SIGTERM to serialize `orch-model` use)
- Last 30 lines of log: none; the log was empty when paused. The synthesis cache contains 109 entries; no `rag-llm-s1-*` corpus directories were produced.
- Next: let UI run `20261015T070737-run-87e01b` finish, then resume this command with the same cache and output paths.

## LLM synthesis paused for UI concept generation
- Step: 1 LLM corpus synthesis (`rag-llm-s1`), resumed from the saved cache
- Exact command: `nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" uv run synth build --name rag-llm-s1 --seed 1 --studies 20 --renderer llm --levels all --model orch-model --verify-model sub-model-2 --out "$CORPORA" --cache "$EV/cache/synth-llm.jsonl" > "$EV/logs/1-synth-main.log" 2>&1 &`
- Exit code: 143 (terminated with SIGTERM after UI concept job `20261015T073812-concepts-61359a` started against the same model)
- Last 30 lines of log: none; the log was empty when paused. The cache is 405 KB; no `rag-llm-s1-*` corpus directories were produced.
- Next: wait for all UI jobs using `orch-model` to finish, then resume with the same cache and output paths.

## 0.1 branch already existed
- Step: 0.1 checkout
- Exact command: `git fetch origin && git checkout -b evidence-cluster origin/main`
- Exit code: 128
- Last 30 lines of its log:
  ```
  fatal: a branch named 'evidence-cluster' already exists
  ```
- Next: preserved the old ref as `evidence-cluster-prior-session`, then created `evidence-cluster` from `origin/main`; the prior commit remains available.

## 0.4 live stack doctor
- Step: 0.4 environment check
- Exact command: `srun --jobid 7488 --overlap bash -lc 'cd llm-setup && set -a && source .env && set +a && uv run llm-setup doctor --profile profiles/agent-3x40.yaml'`
- Exit code: 1
- Last 30 lines of its log (`logs/0-doctor.log`):
  ```
  INFO  host: gammaweb08, Slurm job 7488
  PASS  time left in the allocation: 1-23:48:29
  PASS  LITELLM_MASTER_KEY: set
  PASS  profile: agent-3x40 (profiles/agent-3x40.yaml)
  INFO  session: none running
  FAIL  GPU 0 (orch): 35771 MiB already in use with no session running: a leftover process (nvidia-smi lists it)
  FAIL  GPU 1 (sub): 30691 MiB already in use with no session running: a leftover process (nvidia-smi lists it)
  FAIL  GPU 2 (sub-2): 30691 MiB already in use with no session running: a leftover process (nvidia-smi lists it)
  PASS  weights orch: Qwen/Qwen3.8-27B-FP8
  PASS  weights sub: Qwen/Qwen3-30B-A3B-Instruct-2507-FP8
  FAIL  port 8001 (orch): in use with no session running: another server holds it (`ss -ltnp | grep :8001`)

  First problem: GPU 0 (orch): 35771 MiB already in use with no session running: a leftover process (nvidia-smi lists it)
  srun: error: gammaweb08: task 0: Exited with exit code 1
  ```
- Next: keep the live processes untouched; verify the model endpoint and proceed with independent steps. The processes are listed under Slurm job 7488.

## 9 proposal frame attempt
- Step: 9 proposal flow dry run
- Exact command: `uv run evidence propose frame --question "$Q" --vocab evidence/vocab/rag-factuality.json --out "$PR" --model orch-model`
- Exit code: 1 (the enclosing run was stopped after this first failure; its srun was interrupted)
- Last 30 lines of its log (`logs/9-propose.log`):
  ```
  error: model call failed: ModelAPIError: Connection error.
  error: /mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-cluster/proposals/rag-factuality/frame.json does not exist: run `evidence propose frame` first
  error: /mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-cluster/proposals/rag-factuality/frame.json does not exist: run `evidence propose frame` first
  ```
- Next: confirm endpoint health, then retry the failed frame call once; do not proceed past a failed prerequisite.

## 1.1 LLM main corpus: fidelity exclusions exceed the runbook threshold
- Step: 1.1 LLM main set (`rag-llm-s1`, seed 1, 20 studies, all levels)
- Exact command: `nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" uv run synth build --name rag-llm-s1 --seed 1 --studies 20 --renderer llm --levels all --model sub-model-1 --verify-model sub-model-2 --out "$CORPORA" --cache "$EV/cache/synth-llm.jsonl" > "$EV/logs/1-synth-main.log" 2>&1 &`
- Result: process finished and wrote all six corpus directories. Fidelity excluded 20/20 in complex, contradictory, distributed and mixed; 19/20 in explicit (1 kept); and 20/20 in paraphrased. Every study used 3 attempts. Failures are recorded in each corpus's `fidelity.json`; `required_strings` reports ambiguous required values in the sample checked, with additional checks listed in the fidelity files.
- Exit code: not captured; the detached srun process had ended by the status check. `logs/1-synth-main.log` is empty (no last lines available).
- Next: runbook §1.1 says exclusions above one quarter require USER review, then continue with what was kept. Paused before dependent step 1.2 pending the user's direction; no prompts, fidelity checks, or thresholds changed.

## 1.2 LLM knob set: fidelity exclusions exceed the runbook threshold
- Step: 1.2 LLM knob set (`rag-llm-k1`, seed 1, 20 studies, all levels, 2 duplicates, 2 missing, 2 outliers, 2 irrelevant)
- Exact command: `nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" uv run synth build --name rag-llm-k1 --seed 1 --studies 20 --renderer llm --levels all --duplicates 2 --missing 2 --outliers 2 --irrelevant 2 --model sub-model-1 --verify-model sub-model-2 --out "$CORPORA" --cache "$EV/cache/synth-llm.jsonl" > "$EV/logs/1-synth-knobs.log" 2>&1 &`
- Result: process finished and wrote all six corpus directories. Each level kept 2 papers; explicit excluded 21/24, the other levels 22/24. Each corpus's `fidelity.json` contains per-paper checks and attempts.
- Exit code: not captured; the detached srun process had ended by the status check. `logs/1-synth-knobs.log` is empty (no last lines available).
- Next: record the >25% exclusion rate as required; continue to step 1.3 with the kept papers. No prompts, fidelity checks, or thresholds changed.

## 1.3 LLM small set: all studies excluded
- Step: 1.3 LLM small set (`rag-llm-small`, seed 2, 5 studies, paraphrased and distributed)
- Exact command: `nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" uv run synth build --name rag-llm-small --seed 2 --studies 5 --renderer llm --levels paraphrased,distributed --model sub-model-1 --verify-model sub-model-2 --out "$CORPORA" --cache "$EV/cache/synth-llm.jsonl" > "$EV/logs/1-synth-small.log" 2>&1 &`
- Result: process finished and wrote paraphrased, distributed and mixed corpus directories; all three kept 0/5 papers. Their `fidelity.json` files have the per-paper checks.
- Exit code: not captured; the detached srun process had ended by the status check. `logs/1-synth-small.log` is empty (no last lines available).
- Next: record the >25% exclusion rate; continue with independent steps. Step 1.4 cannot select its required supporting study: `rag-llm-s1-mixed/ground_truth.json` has no supporting studies and its manifest has no papers. Do not alter fidelity checks or fabricate a study.

## RAG baseline mapping failed on the two mixed corpora
- Step: 6 RAG baseline (`rag-llm-s1-mixed`, `rag-llm-k1-mixed`)
- Exact command: `uv run evaluate rag-baseline --corpus "$C" --out "$RUNS/rag-baseline/$N" --cache "$CACHE/rag-baseline.jsonl" --model orch-model --retrieval global --k 8`
- Exit code: 1 for each corpus.
- Last output lines (same for both):
  ```
  File "evaluation/baselines/rag.py", line 151, in rag_baseline
    reply, mapping = map_answer(...)
  File "evaluation/baselines/common.py", line 144, in cached_reply
    raise RuntimeError(redact(f"{type(exc).__name__}: {exc}")) from None
  RuntimeError: RuntimeError: Event loop is closed
  ```
- Next: continued to the other LLM corpora. Seven RAG baseline answers were written; these two have no `answer.json`. Full tracebacks: `$EV/logs/6-baselines-resume.log`. No prompt, retrieval or scoring code changed.

## Template benchmark first attempt used old score reports
- Step: 7.4 template benchmark (`evaluate benchmark` on the five template per-level cascade reports)
- Exact command: `uv run evaluate benchmark "$SCORES/cascade/rag-tpl-s1-explicit" "$SCORES/cascade/rag-tpl-s1-paraphrased" "$SCORES/cascade/rag-tpl-s1-distributed" "$SCORES/cascade/rag-tpl-s1-complex" "$SCORES/cascade/rag-tpl-s1-contradictory" --out "$SCORES/benchmark-tpl"`
- Exit code: 1. The existing template reports were from an older format and had no top-level `extractors` section.
- Last output: `evaluate benchmark: no report has an extractors section (score a run, not answers only)`.
- Next: regenerated the template score reports from their saved runs, reran all available comparisons, and the template benchmark wrote 8 extractor records to `$SCORES/benchmark-tpl/benchmark.md`. The first failed attempt is logged in `$EV/logs/7-refresh-compare-benchmark.log`.
