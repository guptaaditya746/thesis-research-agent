# Runbook: paperfactory pilot datasets on Qwen (Slurm), for Codex, UNATTENDED

Updated 22 Nov 2026 (Aditya: "let the system run"). Goal: a pilot dataset of 20 papers for each of four fields (law,
llm, medicine, materials), every model job on Qwen `orch-model` in the Slurm GPU job, overnight, with nobody to ask.
Keep a short log in docs/design/codex-log.md (date, step, command, result, numbers). Aditya reads it in the morning.

**The one principle: nothing soft stops the night.** A bad paper, a failed field, a failing test, a low score or a
warning is logged and the work goes on. The only reasons to stop are in section 6 (the model server cannot be
reached even after a relaunch, or the key is missing).

## 0. Rules

1. Do not commit, push or rewrite git history. Never edit files in llm-setup/ (starting the stack, section 1a, is
   allowed). Do not edit code or packs. The only file edits allowed are the two numbers in section 2.1.
2. Never print or log LITELLM_MASTER_KEY or anything from llm-setup/.env.
3. At most 9 LLM calls at once (Aditya, 22 Nov 2026: three per Qwen replica); paperfactory enforces it with lock
   files (`max_parallel` 9 in configs/qwen/*.json). Run ONE field at a time. Before a field, check
   `pgrep -af "evqa run|evqa paper"`: if another LLM job runs, wait for it at most 30 minutes (check every 5), then
   log "started next to <job>" and start anyway.
4. Run everything from the repo root through the GPU job:
   `srun --jobid <JOB> --overlap ops/injob.sh uv run paperfactory ...` (ops/injob.sh sets LITELLM_BASE_URL to the
   gateway on 127.0.0.1:4000 and loads the key without printing it).
5. Never edit or delete files under runs/; old outputs are kept automatically as `*.stale-N`.
6. Never pass `--allow-mixed` or `--no-cache` (a restart must reuse finished work).

## 1. Setup (no LLM)

```bash
git pull origin main
git submodule update --init llm-setup                # the Qwen stack (thesis-llm-setup), read-only
uv sync --extra deepeval                             # deepeval: the last step's metrics (optional extra)
uv run pytest backend/paperfactory/tests -q          # log the result; failures do NOT stop the night
squeue -u "$USER"                                    # is a Qwen stack job already running?
```

Failing tests: log the names and the first error line of each, then go on (the run itself is the real test).

### 1a. Launch the Qwen job on a compute node (only if squeue shows no llm-stack job)

`llm-setup/.env` must exist with LITELLM_MASTER_KEY set (check with
`test -s llm-setup/.env && grep -q '^LITELLM_MASTER_KEY=.' llm-setup/.env`, never print it); missing: section 6.

```bash
cd llm-setup
LLM_SETUP_PROFILE=profiles/orch-3x40-gliner.yaml LLM_SETUP_BOOTSTRAP_COMPILER=1 \
  sbatch --partition=gammaweb --container-image=pytorch/pytorch:2.8.0-cuda12.9-cudnn9-runtime \
  --container-writable --container-remap-root slurm/llm-stack.sbatch
# note the job id it prints: <JOB>
tail -n 40 runtime/slurm-<JOB>.out        # repeat every few minutes until every model says "ready after M:SS"
cd ..
```

- 3 Ampere GPUs for 48 hours (`#SBATCH` lines in llm-setup/slurm/llm-stack.sbatch). Do not switch to Hopper.
- `ports already in use` (another user's server on gammaweb holds a port, seen on 8090 for GLiNER): do not stop
  their process. `scancel <JOB>` and submit again with the repo's copy of the profile, which moves GLiNER to 8095:
  `LLM_SETUP_PROFILE=$PWD/../ops/llm/orch-3x40-gliner-p8095.yaml` (from inside llm-setup/).
- Already holding a GPU job (3 Ampere GPUs)? Start the stack in it instead:
  `cd llm-setup && LLM_SETUP_PROFILE=profiles/orch-3x40-gliner.yaml slurm/start-in-job.sh <JOB>`.
- Not ready after 40 minutes, or a model failed: log the last 40 lines, `scancel <JOB>` and launch once more. A
  second failure: section 6.

### 1b. Check that the gateway answers (prints model names only)

```bash
srun --jobid <JOB> --overlap ops/injob.sh bash -c \
  'curl -sf -H "Authorization: Bearer $LITELLM_MASTER_KEY" "$LITELLM_BASE_URL/models" | head -c 400; echo'
```

`orch-model` must be in the list. Not there: wait 5 minutes and try again 3 times, then relaunch (1a) once.

## 2. Pre-checks (about 30 minutes; never stop here)

1. GPU memory for 9 calls at once: in the job's logs (`grep -h "Maximum concurrency" -r llm-setup/runtime/`), read
   "Maximum concurrency for 65536 tokens per request" for each replica and log it. If any is below 3, set
   `"max_parallel": 6` and `"parallel": 6` in the four files configs/qwen/{law,llm,medicine,materials}.json (both
   role entries) and log that you did (the only edit allowed; do not commit it).
2. The new prompts on the cases that failed in the smoke runs (Qwen, fast; log results, never stop):
   - `... paperfactory run --config backend/paperfactory/configs/qwen/smoke-llm.json --steps check`: it prints
     "check settings changed" and checks the three smoke papers again. Log the statuses in
     runs/paperfactory/qwen-smoke-llm/work/*/paper.repairs.json and any `drop_sentences` steps.
   - `... run --config backend/paperfactory/configs/qwen/smoke-medicine.json --steps world`, then check-world on it;
     the same for smoke-materials. Log pass/fail and the errors.

## 3. The four pilot datasets: 20 papers each, one field at a time

Order: law, llm, medicine, materials (llm, medicine and materials packs are DRAFTS). For each FIELD:

```bash
CFG=backend/paperfactory/configs/qwen/FIELD.json
nohup srun --jobid <JOB> --overlap ops/injob.sh uv run paperfactory run --config $CFG \
     > runs/paperfactory/qwen-FIELD.log 2>&1 ; echo "exit $?" >> runs/paperfactory/qwen-FIELD.log
srun --jobid <JOB> --overlap ops/injob.sh uv run paperfactory check-world --config $CFG \
     --world runs/paperfactory/qwen-FIELD/world.json > runs/paperfactory/qwen-FIELD.world-check.txt
```

(Run the first command in the background with `&` if you want to watch it; wait for it to end before the next
field.) It runs every step: world, seed (gold by SPARQL), materials, write (PaperOrchestra, 9 papers at once),
check (repairs), eval (tagging, verifier test, judge, QA, BM25, style leak), deepeval (deepeval.json).
Progress: `tail -f runs/paperfactory/qwen-FIELD.log`.

When it ends:
- exit 0: log the field (section 5), go to the next field.
- exit not 0: look at the last 30 lines of the log. Run the SAME command once more (finished work is reused). If it
  fails again, log both errors and go to the next field. If the error says the gateway cannot be reached, do 1b
  first (and 1a if needed), then run it again.
- World step failed ("failed the checks after 2 repairs", "planned N of M papers", "gave no answer in the required
  form"): the same: one more try, then log and go to the next field.

Expected and fine: "warning: writer, rewriter, judge, verifier share the model orch-model", decoy warnings,
papers marked failed by the check (they are left out of the evaluation), questions rescoped or dropped.

Quality notes to log (not gates): `papers_written` below 18, more than 2 papers in `papers_failed_world_check`,
`qa_summary.parse_errors` above 2, more than 10% parse errors in calls.jsonl, any `"skipped": "context_window"`.

## 4. If the GPU job ends or the run is killed

The job has a 48-hour limit. If it ends (squeue shows no llm-stack job) or a run was killed: launch a new job (1a),
check the gateway (1b), and run the SAME command for the field that was running. Every output has a
`<name>.meta.json`; finished work is reused, and anything made under other settings is made again (the run prints
why).

## 5. What to log per field (codex-log.md)

One short entry per field: run folder; start and end time; exit codes; papers planned / written / failed the world
check; world-check warnings (count, first three); repairs (statuses in work/*/paper.repairs.json: clean / repaired /
redone / failed, and how many log steps are `drop_sentences`); verifier_test; judge_validation (paper and answer
wording); qa_summary (questions, recall, answer_recall, precision, parse_errors) and `qa_by_scope` (full /
rescoped); `questions_rescoped` and `questions_dropped` (counts); bm25_baseline.all (rank1_share, median_rank);
style_leak (rate, ci95, chance, `planted_with_pack_words.share` next to
`other_pool_sentences_with_pack_words.share`, first three `hit_sentences`); deepeval.json `summary` and
`gold_grounding_below_0.5` (count); parse-error count from calls.jsonl. Copy numbers; do not interpret them.

At the end of the night: one table with a row per field (papers written, failed, QA recall, style leak, deepeval
gold grounding) and the list of anything that went wrong.

Useful one-liners:

```bash
python3 -c "import json;r=[json.loads(l) for l in open('runs/paperfactory/qwen-FIELD/calls.jsonl')];print(len(r),'calls',sum(x['parse_error'] for x in r),'parse errors',sum(bool(x.get('skipped')) for x in r),'skipped')"
python3 -c "import json;r=json.load(open('runs/paperfactory/qwen-FIELD/report.json'));print(json.dumps({k:r.get(k) for k in ('papers_written','papers_planned','papers_failed_world_check','verifier_test','judge_validation','qa_summary','qa_by_scope','bm25_baseline')},indent=1)[:3000])"
```

## 6. The only reasons to stop (log why, then stop)

- llm-setup/.env or its key is missing.
- The Qwen job cannot be started or the gateway does not answer after one relaunch (1a/1b).
- No GPU allocation possible (sbatch refused, partition down).

Everything else: log it and go on with the next step or field.

Earlier smoke configs (3 papers per field) are in configs/qwen/smoke-*.json; their results are in codex-log.md.
