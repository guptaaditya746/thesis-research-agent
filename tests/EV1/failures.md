# Failures

## LLM stack startup failed on an ephemeral PyTorch port (job 7599)
- Step: 0.2 LLM stack startup, submitted with `LLM_SETUP_PROFILE=profiles/agent-3x40.yaml`.
- Result: the stack exited during `orch` initialization; Slurm then removed the allocation, so later `srun --jobid 7599` reported an invalid job id. This was an application startup failure, not a Slurm time-limit cancellation.
- Root cause: `torch.distributed` could not bind its rendezvous port `50174` (`EADDRINUSE`). vLLM had selected an ephemeral port by probing and closing a socket before PyTorch bound it, leaving a race with other processes on the shared node.
- Durable fix: `llm-setup/slurm/llm-stack.sbatch` now sets a deterministic, job-scoped `VLLM_PORT` base in a non-ephemeral port range. vLLM scans forward if a port in that job's block is occupied. The runbook also captures and exports the submitted job id automatically, avoiding an empty `JOB` in the subsequent `srun` command.
- Job 7600 was submitted before this fix and is unaffected; it is currently loading the model stack. Its later startup result does not verify the new port allocation.

## Step 10 LLM counterfactual variant rejected by fidelity
- Step: LLM counterfactual variant for `rag-llm-s1-mixed`; selected study `S002`, direction `contradicts`.
- Exact command: `uv run synth variant --corpus "$CORPORA/rag-llm-s1-mixed" --study S002 --direction contradicts --model sub-model-1 --verify-model sub-model-2 --cache "$EV/cache/synth-llm.jsonl"`
- Exit code: 1 after three generation attempts.
- Root cause: the paraphrased counterfactual paper did not associate its expected metric with a value. Fidelity reported `values_associated: S002.m2: its sentence names metrics [], not only S002.k1` on the final attempt. This is a renderer/fidelity content mismatch; it is separate from the Slurm step-start socket collision recorded later in this file.
- Impact: no LLM counterfactual corpus was produced, so LLM shift reports for this variant are unavailable. The template counterfactual and its engine run succeeded.
- Follow-up: retain the failed attempt and its log; diagnose the renderer/fidelity mismatch separately without weakening the fidelity check. Do not present the missing variant as a successful shift result.

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

## 2026-10-21: LLM corpus generation produced an empty study set

- Session: `evidence-cluster-20261020`, Slurm job 7588, gammaweb07.
- Main build: `uv run synth build --name rag-llm-s1 --seed 1 --studies 20 --renderer llm --levels all --model sub-model-1 --verify-model sub-model-2 --attempts 5 --out "$CORPORA" --cache "$CACHE/synth-llm.jsonl"`.
- Result: all 20 studies excluded from all six corpora. A build completing is not proof that it produced usable papers. Inspect `fidelity.json`, manifest paper counts and the build's exclusion summary before dependent steps.
- Per-level papers passing their own checks: explicit 16/20; paraphrased 7/20; distributed 6/20; complex 6/20; contradictory 3/20. Mixed selected renderings passed 11/20, but retained zero because exclusions apply across levels.
- Cause of the empty set: `synth/corpus.py:exclusions` intentionally excludes a study from every level if any requested level fails. This preserves comparable study sets. Do not bypass this rule or lower fidelity thresholds to obtain a nonempty corpus.
- Writer failures: repeated result values in Abstract/Discussion or repeated tables (`required_strings`); extra efficacy claims, including aims and negated claims (`added_claims`); inline enumeration digits (`added_numbers`); omitted verbatim metric/condition labels (`values_associated` and level checks); distributed definitions within 300 characters of the table (`level_distributed`). The independent blind verifier is reached only after structural checks pass, so it did not cause these structural failures.
- Retry defect fixed: identical rejection feedback could produce the same prompt and seed, so the cache replayed the same rejected reply. `LlmRenderer.render_one` now varies the writer seed by attempt. A targeted regression test passed. Cache keys retain model identity, prompt and seed; cached evidence is preserved.
- Prompt changes tried: forbid result repetition and additional retrieval efficacy claims, including aims and implications. An explicit-only one-study pilot passed on attempt two. This was insufficient evidence for all levels: the subsequent full all-level build still retained zero. Future pilots must cover every requested level before a full build.
- Diagnostic control: template papers for all 20 seed-1 studies and all five levels pass the LLM locator unchanged. Suspected numeric substring ambiguity was not reproduced by this control; no anchor or numeric fidelity checks were relaxed.
- Next experiment (authorized by user): stronger `orch-model` writer, independent `sub-model-2` verifier, one study, all five levels, five attempts, concurrency one; same checks and current prompt. Log: `logs/1-synth-orch-pilot.log`; output prefix: `corpora/rag-orch-pilot-*`. Outcome pending. Serialize other orch calls during this experiment.

### Empty-build exit status defect

- Reproduction: `uv run pytest -q synth/tests/test_example.py::test_cli_fails_when_fidelity_excludes_every_paper` initially failed with `assert 0 == 1`: real corpus writing excluded the only study, persisted an empty manifest and fidelity evidence, but `synth build` returned success.
- Fix: `synth/cli.py` now returns exit status 1 with `ERROR: no papers retained after fidelity checks; see fidelity.json` if fidelity exclusions leave all emitted corpora empty. Diagnostic artifacts and exclusion checks are preserved. Successful and partially retained builds keep their existing behavior.
- Verification: `uv run pytest -q synth/tests/test_llm.py synth/tests/test_example.py::test_cli_fails_when_fidelity_excludes_every_paper synth/tests/test_example.py::test_cli_build_and_sample` passed: 12 tests in 21.80 seconds.

- Failed sub-model main-build metadata preserved before replacement under `$EV/diagnostics/synth-main-submodel-20261021/` (`fidelity.json`, `manifest.json`, `corpus.json` for all six corpora). Shared model-call cache retains rejected replies.

### Background build progress

- Earlier detached build logs were empty until completion, so tailing them could not distinguish progress from a stuck request.
- `LlmRenderer.render_one` now flushes one stderr line per completed attempt with study, level, attempt count and failing check names (or `passed`). This reports live progress without logging credentials or full prompts. The existing multi-level rejection/retry regression now checks these lines.

### Repeated feedback at temperature zero

- Follow-up regression: the repeated-bad-reply test confirmed three attempts produced only two unique prompts (`assert 2 == 3`), even after seeds became distinct. Sampling temperature is zero; a new seed alone does not make an identical request an effective correction.
- Fix: retries now include the rejected draft, the specific failed checks, and a distinct revision number. The writer can edit the actual failed text instead of reconstructing an unseen paper from error messages. Unchanged initial prompts retain their cache entries; revised prompts get separate content-addressed entries. No cache is deleted and no fidelity check is bypassed.
- Regression asserts distinct seeds, distinct prompts, and inclusion of the rejected draft. Targeted verification passed: 12 tests in 22.16 seconds (renderer tests plus empty-build and successful CLI regressions).

### Stronger writer baseline and a claim-pattern false positive

- Initial `orch-model` pilot (one seed-1 study, all levels, independent `sub-model-2` verifier, five attempts, concurrency one) still excluded its study. Explicit, paraphrased and complex passed on attempt one; distributed and contradictory exhausted five attempts. Artifacts: `$EV/corpora/rag-orch-pilot-*/fidelity.json`; log: `$EV/logs/1-synth-orch-pilot.log`.
- Contradictory repeated both measurements in table and Results prose on all five attempts; its last four cached drafts each had 674 words. This is direct live evidence that distinct seeds alone did not correct repeated deterministic failures.
- Distributed errors included changed claim sentences, an extra `100` used to explain percent conversion, and the metric abbreviation redefined within 300 characters of the table.
- A separate checker defect was exposed by the distributed draft: `The use of a dense retriever is a standard choice in the field, and we did not explore alternative retrieval methods in this study.` was flagged as an effect claim. The negated-verb regex used `alter` followed by unrestricted `\w*`, incorrectly treating `alternative` as an inflection of `alter`. This is a false positive in both the shared regex extractor and the fidelity guard.
- New regressions exercise the actual regex extraction path and the fidelity checker with this sentence. Fix/verification pending.
- Full synthesis regression suite before this new claim regression: 211 passed in 59.39 seconds. Example corpus metadata was refreshed only for the generator source hash; example facts and papers were not changed.
- Repaired-retry all-level pilot is running serially on `orch-model`; log: `logs/1-synth-orch-repair-pilot.log`. Initial explicit and paraphrased renderings replayed from cache and passed. No simultaneous orch step was launched.

### Repaired heavy-writer pilot: PASS

- Command: `uv run synth build --name rag-orch-repair-pilot --seed 1 --studies 1 --renderer llm --levels all --model orch-model --verify-model sub-model-2 --attempts 5 --concurrency 1 --out "$CORPORA" --cache "$CACHE/synth-llm.jsonl"` (background `nohup srun`, serialized after the first pilot).
- Result: exit 0; all five levels pass, one study retained in every corpus, `excluded: []` in every fidelity file. Attempts: explicit 1, paraphrased 1, distributed 3, complex 1, contradictory 2. Independent blind verification is enabled for all levels. Initial passing papers replayed from cache; rejected papers were revised with their drafts included. No fidelity threshold was relaxed.
- Evidence: `$EV/logs/1-synth-orch-repair-pilot.log` and `$EV/corpora/rag-orch-repair-pilot-*/fidelity.json`.
- This validates one study across levels, not a full 20-study success rate. The authorized full main build will use `orch-model` and the repaired feedback loop. Inspect its retained counts before dependent runs.

### Claim-pattern correction

- Both new tests reproduced the false positive before the fix: regex extraction emitted `author_claim/no_effect`, and fidelity reported `added_claims`, for the limitations sentence about alternative retrieval methods.
- Fix: replace the negated verb pattern's arbitrary word suffix with explicit verb endings and an end word boundary. `alter`, `alters`, `altered`, and `altering` remain supported; `alternative` is not treated as that verb. Existing no-effect, improvement and worsening cases remain in the regression suite. The extractor config records the changed regex, so its content-derived identity changes with the rule.
- Combined claim and synthesis regression suite is running. This correction fixes a word-classification error; it does not waive a fidelity requirement.

### Distributed prompt/check mismatch

- The checker requires at least 300 characters after the last code or metric-abbreviation definition, but the writer instruction only requested two paragraphs. Two short paragraphs or a repeated definition near Results could still fail.
- Fix: distributed level instructions now explicitly state the checker's `DISTANCE` requirement and require definitions only once, early in Method. This uses the existing constant; the check itself is unchanged.
- Final all-level heavy-writer pilot started with this clearer instruction and the corrected claim pattern: `rag-orch-final-pilot`, same seed/study/model/verifier/attempt count. Log: `logs/1-synth-orch-final-pilot.log`. Other initial renderings can replay from cache; changed distributed instructions have distinct cache keys. Outcome pending.

### Final pilot: PASS; regression rerun after source edits

- Final `rag-orch-final-pilot` all-level build exited 0 and retained its study everywhere. Attempts: explicit 1, paraphrased 1, distributed 2, complex 1, contradictory 2; every fidelity record passes and all exclusion lists are empty. This uses the repaired feedback loop, explicit distributed spacing rule, and corrected claim pattern.
- Combined test run: 219 passed, 3 failed in 86.37 seconds. The failures were `test_same_seed_identical_bytes`, `test_corpus_json_and_fidelity_json`, and `test_example_corpus_is_up_to_date`: generator source was edited while this run was building hash-pinned fixtures, so the fixture hash differed from the later source hash. This was a test-execution mistake, not a paper-content difference. Example metadata has been refreshed, and the same suite is rerunning after all generator edits stopped. Keep source edits and provenance/determinism tests sequential in future.
- The new alternative/alter regressions and existing claim-direction tests passed in that run; no semantic failure remained there.

### Final verification and full main rebuild

- After source edits stopped and example provenance was refreshed, the identical combined suite passed: `uv run pytest -q evidence/tests/test_claims_review.py synth/tests` -> **222 passed in 56.80 seconds**. This includes both new claim false-positive regressions, the existing claim-direction cases, deterministic corpus/provenance checks, all synthesis fidelity tests, retry/cache checks and CLI success/failure behavior.
- Full main rebuild started with `nohup srun --jobid 7588 --overlap "$EV/in-job.sh" uv run synth build --name rag-llm-s1 --seed 1 --studies 20 --renderer llm --levels all --model orch-model --verify-model sub-model-2 --attempts 5 --concurrency 4 --out "$CORPORA" --cache "$CACHE/synth-llm.jsonl"`.
- This session intentionally changes the main writer from `sub-model-1` to `orch-model`, as requested by the user after failures. Independent verifier remains `sub-model-2`. Writer identity is recorded in corpus metadata; other orch operations must wait until synthesis finishes.
- Log/PID/exit status: `$EV/logs/1-synth-main-orch.{log,pid,exit}`. Earlier failed main metadata is preserved under `$EV/diagnostics/synth-main-submodel-20261021/`. Full 20-study outcome pending; do not infer it from pilot success.

### User stop boundary

- User requested: stop when Step 6 (the full main LLM corpus build) is done. Monitor and record this build's actual result, then stop the workflow. Do not start the knob corpus, small corpus, or any later runbook step automatically. Slurm allocation cancellation is still reserved for completion of all work or a separate user instruction.

### Updated user boundary

- User explicitly changed the stop instruction: **Continue to Step 8** (the knob corpus) after Step 6 finishes and its result is checked. The prior stop-after-Step-6 boundary is superseded. Do not interpret this as a request to repair each excluded paper; fidelity exclusions are recorded and retained studies are used as the runbook specifies.

### Completion alarm requested by user

- User is going to sleep and requested a loud sound when the main build's 100 renderings are done; keep work running and continue to Step 8 as previously authorized.
- Temporary browser page served by the existing UI: `http://127.0.0.1:25173/corpus-alarm.html`. User must click **Enable completion alarm** because the compute node cannot directly play audio on the laptop. The page provides a sound test, a stop button and a 60-second repeating alarm. Tab, tunnel and laptop must remain active.
- Observer: `$EV/corpus_alarm_watch.py`, PID/log under `$EV/logs/corpus-alarm.*`. It publishes numeric progress to the UI's ignored `dist/corpus-alarm-status.json`, and signals done when `1-synth-main-orch.exit` exists. It does not launch model work. HTTP checks confirmed both page and status return 200 with the expected content types.
- The watcher is independent of the model build; the alarm being unarmed or a browser disconnect does not stop synthesis.

### Durable overnight continuation configured

- Supervisor: `$EV/continue_step8.py` (single-instance file lock), PID/log: `$EV/logs/step6-step8-supervisor.{pid,log}`. Startup verified: `$EV/overnight-status.json` reports `waiting_for_step6`.
- It waits for the main build's captured exit status, tails the last five log lines, records real per-level retained/excluded counts and remaining failure details in both failure logs and `$EV/step6-summary.json`. It stops if the build failed or retained zero papers.
- For a usable main corpus, it launches Step 8 with `nohup srun`, `orch-model`, independent `sub-model-2`, the repaired renderer, all four requested knobs, and the shared synth cache. Only one model step runs at a time. High exclusion counts are explicitly flagged for user review, and kept papers are used as the runbook instructs.
- After Step 8 it records `$EV/step8-summary.json`, the knob exit status and final overnight status, then stops. It does not launch Step 9, commit/push results, or cancel the allocation. This durable background continuation implements the user's instruction to keep running while asleep.

## Overnight Step 6 result: rag-llm-s1

- Process exit status: 0.
- Writer: `orch-model`; independent verifier: `sub-model-2`; five attempts; concurrency four.
- Full machine-readable result: `$EV/step6-summary.json`; full checks remain in each corpus's `fidelity.json`.

| Level | Retained | Excluded | Own checks passed | Mean/max attempts |
| --- | ---: | ---: | ---: | --- |
| explicit | 11/20 | 9 | 19 | 1.6/5 |
| paraphrased | 11/20 | 9 | 19 | 1.8/5 |
| distributed | 11/20 | 9 | 14 | 3.3/5 |
| complex | 11/20 | 9 | 17 | 1.9/5 |
| contradictory | 11/20 | 9 | 19 | 1.9/5 |
| mixed | 11/20 | 9 | 19 | 1.6/5 |

- **More than one quarter excluded: user review is pending.** Exclusions are preserved; the runbook says to record them and continue with what was kept. The user explicitly authorized proceeding to Step 8.

Remaining failures after the attempt limit (checks were not relaxed):
- S017/explicit: anchored: S017.c2/condition_label 'RAG pipeline': ambiguous; S017.c2/condition_label 'RAG pipeline': ambiguous; S017.c3/condition_label 'fine-tuned model': ambiguous
- S004/paraphrased: required_strings: S004.m1/value: required string '0.598' is ambiguous: it occurs 2 times (in Results, Conclusion); write it exactly once, where the level instructions put it, and nowhere else; S004.m2/value: required string '589 out of 1,000' is ambiguous: it occurs 2 times (in Results, Conclusion); write it exactly once, where the level instructions put it, and nowhere else
- S001/distributed: level_distributed: S001.k1: abbreviation 'HR' defined within 300 characters of the table
- S006/distributed: level_distributed: S006.k1: abbreviation 'HR' defined within 300 characters of the table
- S011/distributed: level_distributed: S011.k1: abbreviation 'FLA' defined within 300 characters of the table
- S012/distributed: level_distributed: S012.c1: code 'B' defined within 300 characters of the table; S012.c2: code 'R' defined within 300 characters of the table; S012.k1: abbreviation 'HR' defined within 300 characters of the table
- S015/distributed: level_distributed: S015.c1: code 'B' defined within 300 characters of the table; S015.c2: code 'R' defined within 300 characters of the table; S015.c3: code 'A1' defined within 300 characters of the table; S015.k1: abbreviation 'AA' defined within 300 characters of the table
- S018/distributed: level_distributed: S018.c1: code 'B' defined within 300 characters of the table; S018.c2: code 'R' defined within 300 characters of the table
- S010/complex: blind_reextraction: missing ['S010.m2']; blind_extra: extra [('retrieval-augmented model', 0.1)]
- S015/complex: blind_reextraction: missing ['S015.m5']
- S018/complex: blind_reextraction: missing ['S018.m2']
- S001/contradictory: anchored: S001.c2/condition_label 'retrieval-augmented model': ambiguous; S001.c2/condition_label 'retrieval-augmented model': ambiguous

## Overnight Step 8 result: rag-llm-k1

- Process exit status: 0.
- Writer: `orch-model`; independent verifier: `sub-model-2`; five attempts; concurrency four.
- Full machine-readable result: `$EV/step8-summary.json`; full checks remain in each corpus's `fidelity.json`.

| Level | Retained | Excluded | Own checks passed | Mean/max attempts |
| --- | ---: | ---: | ---: | --- |
| explicit | 11/24 | 13 | 23 | 1.5/5 |
| paraphrased | 11/24 | 13 | 23 | 1.67/5 |
| distributed | 11/24 | 13 | 16 | 3.08/5 |
| complex | 11/24 | 13 | 19 | 2.04/5 |
| contradictory | 11/24 | 13 | 22 | 2.08/5 |
| mixed | 11/24 | 13 | 23 | 1.5/5 |

- **More than one quarter excluded: user review is pending.** Exclusions are preserved; the runbook says to record them and continue with what was kept. The user explicitly authorized proceeding to Step 8.

Remaining failures after the attempt limit (checks were not relaxed):
- S022/explicit: anchored: S022.c2/condition_label 'retrieval-augmented generator': ambiguous; S022.c3/condition_label 'query-rewriting variant': ambiguous; S022.c2/condition_label 'retrieval-augmented generator': ambiguous; S022.c3/condition_label 'query-rewriting variant': ambiguous
- S004/paraphrased: required_strings: S004.m1/value: required string '0.598' is ambiguous: it occurs 2 times (in Results, Conclusion); write it exactly once, where the level instructions put it, and nowhere else; S004.m2/value: required string '589 out of 1,000' is ambiguous: it occurs 2 times (in Results, Conclusion); write it exactly once, where the level instructions put it, and nowhere else
- S001/distributed: level_distributed: S001.k1: abbreviation 'HR' defined within 300 characters of the table
- S006/distributed: level_distributed: S006.k1: abbreviation 'HR' defined within 300 characters of the table
- S007/distributed: required_strings: S007.m2/value: required string '39.9' is ambiguous: it occurs 2 times (in Method, Results); write it exactly once, where the level instructions put it, and nowhere else; S007.m3/value: required string '18.2' is ambiguous: it occurs 2 times (in Method, Results); write it exactly once, where the level instructions put it, and nowhere else
- S008/distributed: required_strings: S008.m1/value: required string '40.4' is ambiguous: it occurs 2 times (in Method, Results); write it exactly once, where the level instructions put it, and nowhere else; S008.m2/value: required string '8.7' is ambiguous: it occurs 2 times (in Method, Results); write it exactly once, where the level instructions put it, and nowhere else
- S011/distributed: level_distributed: S011.k1: abbreviation 'FLA' defined within 300 characters of the table
- S012/distributed: level_distributed: S012.c1: code 'B' defined within 300 characters of the table; S012.c2: code 'R' defined within 300 characters of the table; S012.k1: abbreviation 'HR' defined within 300 characters of the table
- S014/distributed: level_distributed: S014.k1: abbreviation 'AA' defined within 300 characters of the table
- S015/distributed: level_distributed: S015.c1: code 'B' defined within 300 characters of the table; S015.c2: code 'R' defined within 300 characters of the table; S015.c3: code 'A1' defined within 300 characters of the table; S015.k1: abbreviation 'AA' defined within 300 characters of the table
- S007/complex: blind_reextraction: missing ['S007.m4', 'S007.m10']
- S010/complex: blind_reextraction: missing ['S010.m2']; blind_extra: extra [('retrieval-augmented model', 0.1)]
- S015/complex: blind_reextraction: missing ['S015.m5']
- S018/complex: blind_reextraction: missing ['S018.m2']
- S021/complex: anchored: S021.c2/condition_label 'retrieval-augmented model': ambiguous; S021.c2/condition_label 'retrieval-augmented model': ambiguous
- S001/contradictory: anchored: S001.c2/condition_label 'retrieval-augmented model': ambiguous; S001.c2/condition_label 'retrieval-augmented model': ambiguous
- S021/contradictory: anchored: S021.c2/condition_label 'retrieval-augmented model': ambiguous; S021.c2/condition_label 'retrieval-augmented model': ambiguous

- Overnight sequence stopped after Step 8. No Step 9 or later job was launched; the Slurm allocation remains running. Review `$EV/overnight-status.json` and the Step 6/8 summaries before resuming.

## Slurm continuation launch race (21 Oct 2026)

The first Step 9 and Step 10 `srun --jobid 7588 --overlap` invocations immediately after Step 8 failed with `unable to initialize step request socket: Address already in use`. Step 11 built both template corpora but could not create its counterfactual because Step 10 had not produced the study id. The already-started Step 12 engine pass was allowed to finish; the continuation then retried the missed corpus steps with backoff before rerunning dependent stages. Initial and retry logs are under `tests/EV1/live-rerun/logs/`.
