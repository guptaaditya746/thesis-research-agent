# Runbook: paperfactory pilot datasets on Qwen (Slurm), for Codex

Written 21 Nov 2026. Goal: a pilot dataset of 20 papers for each of four fields (law, llm, medicine, materials),
every model job on Qwen `orch-model` in the Slurm GPU job. Work through the steps in order. Keep a short log in
docs/design/codex-log.md (date, step, command, result, numbers). Aditya reads that log.

## 0. Rules

1. Do not commit, push or rewrite git history. Never touch llm-setup/ (read-only). Do not edit code, packs or
   configs. If something needs a change, STOP (section 6).
2. Never print or log LITELLM_MASTER_KEY or anything from llm-setup/.env.
3. At most 3 LLM calls at once across ALL processes. paperfactory enforces 3 per server with lock files, so run ONE
   field at a time, and before starting check `pgrep -af "paperfactory|evqa run|evqa paper|paper_writing_cli"`.
   If another LLM job runs, wait (check every 5 minutes).
4. Run everything from the repo root through the GPU job:
   `srun --jobid <JOB> --overlap ops/injob.sh uv run paperfactory ...` (ops/injob.sh sets LITELLM_BASE_URL to the
   gateway on 127.0.0.1:4000 and loads the key without printing it).
5. Never open or edit files under runs/ by hand except to read reports. Never delete a run folder; old outputs are
   kept automatically as `*.stale-N`.

## 1. Before you start (no LLM)

```bash
git pull origin main
uv sync
uv run pytest backend/paperfactory/tests -q          # must pass; otherwise STOP
squeue -u "$USER"                                    # the Qwen job (profile ops/llm/orch-3x40-gliner-p8095.yaml)
```

No Qwen job running: STOP and ask Aditya to start one. Then check that the gateway answers (prints model names only):

```bash
srun --jobid <JOB> --overlap ops/injob.sh bash -c \
  'curl -sf -H "Authorization: Bearer $LITELLM_MASTER_KEY" "$LITELLM_BASE_URL/models" | head -c 400; echo'
```

`orch-model` must be in the list; otherwise STOP.

## 2. Smoke test: 3 law papers (about 1-2 hours)

```bash
CFG=backend/paperfactory/configs/qwen/smoke-law.json
srun --jobid <JOB> --overlap ops/injob.sh uv run paperfactory run --config $CFG --steps world
srun --jobid <JOB> --overlap ops/injob.sh uv run paperfactory check-world --config $CFG \
     --world runs/paperfactory/qwen-smoke-law/world.json
nohup srun --jobid <JOB> --overlap ops/injob.sh uv run paperfactory run --config $CFG \
     > runs/paperfactory/qwen-smoke-law.log 2>&1 &
```

Expected and fine: "warning: writer, rewriter, judge, verifier share the model orch-model". Decoy warnings from
check-world are fine (write them in the log).

Pass when all hold: report.json exists; `papers_written` = 3; no paper in `papers_failed_world_check`;
`qa_summary.parse_errors` = 0; in calls.jsonl fewer than 10% of rows have `"parse_error": true`; no row has
`"skipped": "context_window"`. Otherwise STOP and log the numbers and the first three error messages.

Useful checks:

```bash
python3 -c "import json;r=[json.loads(l) for l in open('runs/paperfactory/qwen-smoke-law/calls.jsonl')];print(len(r),'calls',sum(x['parse_error'] for x in r),'parse errors',sum(bool(x.get('skipped')) for x in r),'skipped')"
python3 -c "import json;r=json.load(open('runs/paperfactory/qwen-smoke-law/report.json'));print(json.dumps({k:r[k] for k in ('papers_written','papers_planned','papers_failed_world_check','verifier_test','judge_validation','qa_summary','bm25_baseline','style_leak')},indent=1)[:3000])"
```

## 3. The four pilot datasets (20 papers each, one field at a time)

Order: law, llm, medicine, materials (llm, medicine and materials packs are DRAFTS: they have never run). For each
FIELD:

```bash
CFG=backend/paperfactory/configs/qwen/FIELD.json
srun --jobid <JOB> --overlap ops/injob.sh uv run paperfactory run --config $CFG --steps world
srun --jobid <JOB> --overlap ops/injob.sh uv run paperfactory check-world --config $CFG \
     --world runs/paperfactory/qwen-FIELD/world.json > runs/paperfactory/qwen-FIELD.world-check.txt
nohup srun --jobid <JOB> --overlap ops/injob.sh uv run paperfactory run --config $CFG \
     > runs/paperfactory/qwen-FIELD.log 2>&1 &
```

Same pass rules as the smoke test, with these limits for 20 papers: `papers_written` >= 18; at most 2 papers in
`papers_failed_world_check`; `qa_summary.parse_errors` <= 2. Then start the next field.

## 4. If a run stops (job ended, timeout, crash)

Run the SAME command again. Finished work is reused; every output has a `<name>.meta.json` with the settings it was
made with, and anything made under other settings is made again (the run prints why). Never pass `--allow-mixed`
or `--no-cache` unless Aditya says so. If the world step fails ("failed the checks after one repair" or "gave no
answer in the required form"), run the world step once more; a second failure: STOP.
If calls.jsonl shows `world:entities` with parse_error and a cut-off answer, STOP (the world role needs a larger
max_tokens; that is a config change for Aditya).

## 5. What to log per field (codex-log.md)

One short entry per field: run folder; start and end time; papers planned / written / failed the world check;
world-check warnings (count, first three); repairs (statuses in work/*/paper.repairs.json: clean / repaired /
redone / failed); verifier_test; judge_validation (paper and answer wording); qa_summary (recall, answer_recall,
precision, parse_errors); bm25_baseline.all (rank1_share, median_rank); style_leak (rate, ci95, chance);
parse-error count from calls.jsonl. Copy numbers; do not interpret them.

## 6. STOP rules (write the reason in codex-log.md, then wait for Aditya)

- Tests fail, no Qwen job, or the gateway does not list orch-model.
- A pass rule in section 2 or 3 fails.
- The world step fails twice, or check-world prints errors (not warnings).
- Any step would need a change to code, packs, configs or llm-setup/, or more than 3 parallel LLM calls.
- A run prints "MixedSettings".
