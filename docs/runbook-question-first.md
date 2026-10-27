# Runbook: the question-first runs on Slurm (Codex)

This session runs the 10 questions of `evidence/questions.yaml` on two corpora with three systems (the evidence
engine, the RAG baseline, the agent baseline), scores them, and hands back one table. The environment and session
helpers are those of `docs/slurm-evidence-runbook.md` (section 0.3: `$EV`, `in-job.env`, `launch.sh`,
`$AGENT_ROOT`, `$LITELLM_BASE_URL`). Use them; this file only adds what is new. The stack is started by step 1
below (with the GLiNER service), not as in that file's 0.2.

**Rules**

- Entry points only: `uv run evidence ...`, `uv run evaluate ...`. Never `python -m evidence`.
- **Never rebuild the corpora.** They are built locally and are in git under `tests/EV2/corpora/`.
- Do not change code, protocols, prompts or `evidence/questions.yaml`. Do not change `llm-setup` except as step 1 says
  (only the new profile file `profiles/orch-3x40-gliner.yaml`). A failure is recorded in `$EV/failures.md` (step, command, exit code, last 30 log
  lines), then go on with the next independent step.
- No system under test reads `ground_truth.json`; only `evaluate score` does.
- One model: `orch-model` everywhere (the defaults).
- Run the code from `main`; save report files only, on the `results` branch, and tag them `ev3` (step 7).

**The ten question ids** (kind): `rag-factuality`, `rag-hallucination`, `rag-latency` (effect); `inv-metrics`,
`inv-methods`, `inv-datasets` (inventory); `cons-accuracy`, `cons-hallucination` (consistency); `best-accuracy`,
`best-hallucination` (best). Each has its protocol `evidence/protocols/<id>.yaml`.

**Corpora**: `rag-claude-s1-mixed` (main, 20 papers) and `rag-tpl-hard-complex` (scale, 112 papers), both under
`tests/EV2/corpora/`.

**Engine settings**: `--strategy gaps` (the default, written out), `--workers 3`. The LiteLLM gateway
(profile `orch-3x40`, here its copy `orch-3x40-gliner`) allows 8 active and 8 queued requests per replica; three workers stay well inside that. If a
log shows queue-full or 429 errors, lower `--workers` to 2 and record it.

## 0. Branch and setup (login node)

```bash
cd /mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent
git fetch origin --tags && git checkout --detach origin/main    # the code; main holds Parts A-D (tag qf-v1)
git describe --tags                       # record this in summary.md
git submodule update --init --recursive
git -C llm-setup log -1 --oneline         # expect 4c8ccbf GLiNER: start failure keeps the stack, ...
uv sync --locked --all-groups
uv run evidence --help | head -n 3        # the entry points exist
uv run evaluate score --help | grep question-id
```

`main` records `llm-setup` at `4c8ccbf`: `22dae03`'s orch-only profiles plus the GLiNER service (the llm-setup
branch `gliner`). That commit must be fetchable from the llm-setup remote (the user pushes the branch `gliner`
there). If `git submodule update` cannot find `4c8ccbf` (`not our ref`, `did not contain`), or `git log -1` shows
another commit, stop: **USER** (do not change the submodule yourself). This replaces the `22dae03` check of
`docs/slurm-evidence-runbook.md` 0.2. Do not start the stack as 0.2 does either: step 1 starts it, with GLiNER.

Check: both corpora (`tests/EV2/corpora/rag-claude-s1-mixed` and `tests/EV2/corpora/rag-tpl-hard-complex`) have
`manifest.json`; `uv run evidence protocol check evidence/protocols/inv-datasets.yaml` prints id and sha256 and
exits 0.

## 1. GPU report, the stack with the GLiNER service, the session environment

GLiNER is part of the recorded llm-setup commit, so this is a normal step. The llm-setup side is described in
`llm-setup/docs/OPERATIONS.md`, "GLiNER". If GLiNER itself fails (in 1.3 or at its start in 1.5), record it in
`$EV/failures.md` and go on without it: the engine's GLiNER steps are then recorded as `skipped` and every run
still finishes; say so in the report.

1. On a GPU node: `nvidia-smi`. Report the driver version and the CUDA version it prints. (The cu124 torch index
   is not usable: vLLM pins torch 2.11.0, so torch comes from PyPI together with vLLM, and GLiNER uses that torch.
   The CUDA version is for the record, not for pinning anything.)
2. Login node, in `llm-setup`: `uv lock --check` first. `uv.lock` was edited by hand on the laptop; if the check
   fails, run `uv lock` on the cluster, record that it changed, and go on. Then download GLiNER's weights and its
   backbone's tokenizer (GLiNER loads offline):

```bash
cd llm-setup
uv lock --check
huggingface-cli download urchade/gliner_medium-v2.1 --revision 40ec419335d09393f298636f471328b722c6da9e
huggingface-cli download microsoft/deberta-v3-base config.json tokenizer_config.json spm.model
cd ..
```

3. Only if you can get a GPU of your own for a few minutes (a short allocation, before the stack starts): load
   GLiNER alone, offline, and call it. An error here is cheaper than in the batch job. Without such a GPU, skip
   this: 1.5 checks the same inside the stack.

```bash
cd llm-setup
uv sync --python 3.13 --extra serve --extra gliner
HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=0 uv run python -m llm_setup.gliner_server \
  --model urchade/gliner_medium-v2.1 --revision 40ec419335d09393f298636f471328b722c6da9e --port 8090 &
curl -s 127.0.0.1:8090/info               # repeat until it answers (loading takes a minute)
curl -s 127.0.0.1:8090/predict -H 'Content-Type: application/json' \
  -d '{"text": "We evaluate RAG on SQuAD.", "labels": ["method", "dataset"], "threshold": 0.5}'
kill %1
cd ..
```

   Good: `/info` names the model and revision; `/predict` returns `{"entities": [...]}` with at least one entity
   (for example `SQuAD`).
4. The profile. `profiles/orch-3x40.yaml` carries the `gliner:` block commented out; never edit that file. Copy it
   to `profiles/orch-3x40-gliner.yaml` with the block enabled (port 8090, GPU 0, shared with the first orch
   replica). This copy is the only llm-setup change you may make, and it is not committed to any branch except one
   the user names.

```bash
cd llm-setup
sed -e 's/^# gliner:$/gliner:/' -e 's/^#   \(enabled\|gpu\|port\|model\|revision\|max_chars\):/  \1:/' \
  profiles/orch-3x40.yaml > profiles/orch-3x40-gliner.yaml
diff profiles/orch-3x40.yaml profiles/orch-3x40-gliner.yaml | grep -c '^>'          # 7: the gliner lines only
uv run llm-setup profile validate --profile profiles/orch-3x40-gliner.yaml          # Profile valid: orch-3x40
uv run llm-setup profile extras --profile profiles/orch-3x40-gliner.yaml            # gliner
cd ..
```

5. Start the stack with it. The batch job installs the `gliner` extra itself (because `profile extras` prints it)
   and starts GLiNER after the models are ready.

```bash
cd llm-setup
JOB=$(LLM_SETUP_PROFILE=profiles/orch-3x40-gliner.yaml sbatch slurm/llm-stack.sbatch); JOB=${JOB##* }; export JOB
cd ..
echo "Slurm job: $JOB"
tail -n 20 llm-setup/runtime/slurm-$JOB.out     # repeat until orch, orch-2, orch-3 and gliner say "ready after"
srun --jobid "$JOB" --overlap bash -lc 'cd llm-setup && set -a && source .env && set +a && uv run llm-setup doctor --profile profiles/orch-3x40-gliner.yaml' 2>&1 | tail -n 8
srun --jobid "$JOB" --overlap curl -s 127.0.0.1:8090/info
srun --jobid "$JOB" --overlap nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv
```

   Good: the log has `gliner: ready after ...` and no `gliner: start failed, continuing without it`; `doctor`
   shows `gliner health ok`; `/info` names `urchade/gliner_medium-v2.1`. Write down what GLiNER uses on GPU 0
   (`nvidia-smi` lists its process) and the memory left free there.
   - **If under about 1 GB stays free on GPU 0**: `scancel $JOB`, set the orch model's
     `gpu_memory_utilization: 0.88` in `profiles/orch-3x40-gliner.yaml` (not in `orch-3x40.yaml`), and do 1.5
     again. Record it.
   - If GLiNER did not start (`start failed`), the stack runs without it: record the log lines
     (`uv run llm-setup logs --service gliner` in `llm-setup/`, through `srun` as for `doctor`) and go on.
6. The session environment. Write `$EV/in-job.env`, `in-job.sh` and `launch.sh` as in
   `docs/slurm-evidence-runbook.md` 0.3, from the repository root, with
   `export EV=/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-qf`, and **after** 1.5 (in-job.env records
   `$JOB`). Then add this session's variables (the grid's jobs read them from there):

```bash
cat >> "$EV/in-job.env" <<EOF
export C_MAIN=$PWD/tests/EV2/corpora/rag-claude-s1-mixed
export C_HARD=$PWD/tests/EV2/corpora/rag-tpl-hard-complex
export QS="rag-factuality rag-hallucination rag-latency inv-metrics inv-methods inv-datasets cons-accuracy cons-hallucination best-accuracy best-hallucination"
export GLINER_URL=http://127.0.0.1:8090
EOF
source "$EV/in-job.env"
mkdir -p "$EV"/{logs,runs,scores,cache,agent-work}
echo "$JOB $RUNS $C_MAIN $GLINER_URL"; echo $QS | wc -w      # the job id, the paths, 10
```

   Leave out the `GLINER_URL` line only when GLiNER did not start in 1.5 (and say so in the report). If you start
   the stack again later, update `JOB` in in-job.env: `sed -i "s/ JOB=[0-9]*/ JOB=$JOB/" "$EV/in-job.env"`.

Good, for each engine run dir `$RUNS/engine/$N/$Q` (corpus name `N`, question id `Q`, section 4): no GLiNER call
was skipped, and GLiNER found something:

```bash
grep '"status":"skipped"' "$RUNS/engine/$N/$Q/events.jsonl" | grep -c '"agent_id":"gliner_'   # 0
grep -c gliner_ "$RUNS/engine/$N/$Q/evidence.jsonl"                                           # more than 0
```

A skipped GLiNER call (the service was not reachable) is only an `extractor_call` event with status `skipped` in
`events.jsonl`; `evidence run` does not print it, and `funnel.json` leaves it out (its own `skipped` means a paper
the screen left out). The engine asks GLiNER's `/info` once per run: if the service was not up when a run started,
all of that run's GLiNER calls are skipped. If the service dies mid-run, the GLiNER steps return errors, the funnel
goes to the next extractor and runs still finish. Errors from the GLiNER service and the LLM (`service_call`) are
cached; after you restart the service, re-run that run as in section 4, "Retries".

## 2. Offline check (login node, no model)

```bash
uv run evidence run --protocol evidence/protocols/inv-datasets.yaml --corpus $C_MAIN --out $EV/runs/check \
  --cache $EV/cache/check --extractors regex-only --strategy gaps --workers 3 --run-id check
uv run evidence replay $EV/runs/check/check | grep '"ok"'           # "ok": true
uv run evaluate score --run $EV/runs/check/check --corpus $C_MAIN --question-id inv-datasets --out $EV/scores/check
```

Good: the score writes `report.json` and `report.md`; `evaluate score --question-id nope` is refused with the list
of ids. This only checks the spelling; the numbers are not results (regex-only recall is low).

## 3. First check of the baseline mapping prompts (once, before the grid)

The mapping prompts `map-effect-v1`, `map-inventory-v1`, `map-consistency-v1` and `map-best-v1` have never run on
the real model. Run one question of each kind on the 20-paper corpus with the RAG baseline, then the score:

```bash
for Q in rag-hallucination inv-metrics cons-accuracy best-accuracy; do
  uv run evaluate rag-baseline --corpus $C_MAIN --question-id $Q --out $EV/runs/mapcheck/rag/$Q \
    --cache $EV/cache/mapcheck-rag.jsonl --model orch-model --retrieval global --k 8
  uv run evaluate score --corpus $C_MAIN --question-id $Q --baseline $EV/runs/mapcheck/rag/$Q/answer.json \
    --out $EV/scores/mapcheck/$Q
done
```

Do the same with `evaluate agent-baseline` for `inv-metrics` and `best-accuracy` only (it is the costly one):
`--agent-root "$AGENT_ROOT" --run-id mapcheck-<id>`, output under `$EV/runs/mapcheck/agent/<id>`.

Look at, and report in the table of step 6, for each of the four:

- the exit code and whether `answer.json` exists, with the kind's shape (`entries` for inventory, `studies` for
  consistency and best, a label for effect);
- any mapping retry or failure: the `mapping_call` record in `answer.json` and the log lines
  (a pydantic validation retry, `ModelCallError`, an empty answer);
- the C row of its `report.md` (not empty; an inventory answer naming something outside the vocabulary counts
  as a false positive, which is correct).

**If any kind fails or retries more than once, stop and report before the full grid** (that is a prompt problem for
Claude, not for you to fix).

## 4. The grid: question x corpus x system

The two scripts below have not been run as whole scripts. Run `one.sh` once on one question (for example `inv-datasets`
on `$C_MAIN`) and check its output before starting `grid.sh`.

One script runs the three systems for one question and one corpus, then scores. Names are
`$EV/runs/<system>/<corpus>/<question>`; each system has its own cache file, because two processes must never
append to the same cache file.

```bash
cat > $EV/one.sh <<'EOF'
#!/usr/bin/env bash
# one.sh <question-id> <corpus-dir>: engine + RAG baseline + agent baseline + score
set -u
Q=$1; C=$2; N=$(basename "$C")
P=evidence/protocols/$Q.yaml
RUN=$RUNS/engine/$N; mkdir -p "$RUN" "$RUNS/rag-baseline/$N" "$RUNS/agent-baseline/$N" "$SCORES/$N"
uv run evidence run --protocol "$P" --corpus "$C" --out "$RUN" --cache "$CACHE/engine-$N" \
  --model orch-model --strategy gaps --workers 3 --run-id "$Q" || echo "FAIL engine $Q $N"
uv run evaluate rag-baseline --corpus "$C" --question-id "$Q" --out "$RUNS/rag-baseline/$N/$Q" \
  --cache "$CACHE/rag-baseline-$N.jsonl" --model orch-model --retrieval global --k 8 || echo "FAIL rag $Q $N"
uv run evaluate agent-baseline --corpus "$C" --question-id "$Q" --out "$RUNS/agent-baseline/$N/$Q" \
  --cache "$CACHE/agent-baseline-$N.jsonl" --model orch-model --agent-root "$AGENT_ROOT" --run-id "$Q" \
  || echo "FAIL agent $Q $N"
B=(); for s in rag-baseline agent-baseline; do
  [ -f "$RUNS/$s/$N/$Q/answer.json" ] && B+=(--baseline "$RUNS/$s/$N/$Q/answer.json"); done
RUNARG=(); [ -f "$RUN/$Q/answer.json" ] && RUNARG=(--run "$RUN/$Q")
uv run evaluate score "${RUNARG[@]}" --corpus "$C" --question-id "$Q" "${B[@]}" --out "$SCORES/$N/$Q" \
  || echo "FAIL score $Q $N"
EOF
chmod +x $EV/one.sh
```

Add `export RUNS=$EV/runs SCORES=$EV/scores CACHE=$EV/cache` to `in-job.env` if not already there.

Run the questions of one corpus one after another (they share that corpus's three cache files, and two processes must
never append to the same cache file). The two corpora may run side by side, so two long `orch-model` steps are
active at once:

```bash
cat > $EV/grid.sh <<'EOF'
#!/usr/bin/env bash
C=$1
for Q in $QS; do "$EV/one.sh" "$Q" "$C"; done
EOF
chmod +x $EV/grid.sh
nohup "$EV/launch.sh" grid-main "$EV/grid.sh" "$C_MAIN" > /dev/null 2>&1 &
nohup "$EV/launch.sh" grid-hard "$EV/grid.sh" "$C_HARD" > /dev/null 2>&1 &
```

(Inside the job `in-job.sh` has `QS` and the paths through `in-job.env`; add `QS` and `C_MAIN`, `C_HARD` there.)
Each question's logs are in `$EV/logs/grid-main.log` and `grid-hard.log`; `FAIL` lines list what to retry.
Retries: for an engine run that ended with `service_call` errors (a GLiNER or LLM outage), move the failed run dir
aside (a run dir is never overwritten: the same command again stops with `FileExistsError`), run the engine again
with `--retry-errors`, then score again. With `Q`, `C` and `N` set as in `one.sh`:

```bash
mkdir -p "$RUNS/failed/$N"
mv "$RUNS/engine/$N/$Q" "$RUNS/failed/$N/$Q-$(date +%Y%m%dT%H%M%S)"   # keep it for the report
uv run evidence run --protocol "evidence/protocols/$Q.yaml" --corpus "$C" --out "$RUNS/engine/$N" \
  --cache "$CACHE/engine-$N" --model orch-model --strategy gaps --workers 3 --run-id "$Q" --retry-errors
B=(); for s in rag-baseline agent-baseline; do
  [ -f "$RUNS/$s/$N/$Q/answer.json" ] && B+=(--baseline "$RUNS/$s/$N/$Q/answer.json"); done
uv run evaluate score --run "$RUNS/engine/$N/$Q" --corpus "$C" --question-id "$Q" "${B[@]}" --out "$SCORES/$N/$Q"
```

Run it in the job like the grid (one run at a time per corpus: it appends to that corpus's engine cache).

The hard corpus (112 papers) is the slow one; if the job is about to end, finish the main corpus first and report
the hard corpus as partial.

## 5. Check each run

- `uv run evidence replay $RUNS/engine/<corpus>/<question> | grep '"ok"'` gives `"ok": true`.
- `$SCORES/<corpus>/<question>/report.md` exists for each of the 20 pairs; note any missing one with its `FAIL` line.
- GLiNER: `grep '"status":"skipped"' $RUNS/engine/<corpus>/<question>/events.jsonl | grep -c '"agent_id":"gliner_'`
  counts the GLiNER calls skipped because the service was not up (0 when it was up). Report the count per run.
  (`funnel.json`'s `skipped` is a paper the screen left out, not GLiNER.)

## 6. The deliverable table

Read `report.json` / `report.md` of each score dir. A and B exist for the engine run only (`extraction`,
`integration`); the baselines are scored on C only (`synthesis`, one row per system: `evidence-engine`,
`rag-baseline`, `agent-baseline`). A is the `all` / `all` row of `extraction` (precision, recall, f1) and is the same for
every kind. B and C by kind, with the field names as they are in `report.json`:

| kind | B (engine only) | C (every system) |
|---|---|---|
| effect | `integration.rows`: `association_accuracy` | `synthesis`: `label_correct`, `direction_accuracy` |
| inventory | `integration`: `clean_share` | `synthesis`: `precision`, `recall`, `f1` |
| consistency | `integration`: `claim_accuracy` | `synthesis`: `per_study_accuracy` |
| best | `integration`: `kind_accuracy` | `synthesis`: `winner_correct`, `per_study_accuracy` |

`report.md` shows the same numbers under "B." and "C." headings; copy from there if a field is nested.

Write `reports/question-first/summary.md` with:

1. **Main table**, one row per question x system, for each corpus:

   | corpus | question | system | A (f1) | B | C |
   |---|---|---|---|---|---|

   Engine rows have A, B and C; the baseline rows have C only, and `-` for A and B. Write B and C as the fields of
   the table above (for example `label_correct / direction_accuracy`).
2. **Per-extractor A**, for each corpus: from `report.json`'s `extractors.rows`, the rows with `level = all`, one
   line per extractor id with precision, recall, f1, for the regex, abbreviation, GLiNER, number and LLM
   extractors (`regex_*`, `abbrev_*`, `gliner_*`, `number_*`, `llm_*`), per question. A GLiNER line that says
   skipped or has zero facts means the service was not up.
3. **Mapping check** from step 3: per kind, the retries and failures you saw (or "none").
4. **GPU and GLiNER**: `nvidia-smi` driver and CUDA, GLiNER's memory use, free memory left on GPU 0, whether
   `orch-3x40-gliner.yaml` needed `gpu_memory_utilization: 0.88`, whether GLiNER started (`gliner health ok`),
   whether `GLINER_URL` was set.
5. **Failures**: each `FAIL` line and what you did; the number of cached errors that needed `--retry-errors`.

## 7. Hand-back

```bash
mkdir -p reports/question-first
for N in rag-claude-s1-mixed rag-tpl-hard-complex; do
  for Q in $QS; do
    D=$SCORES/$N/$Q; [ -f "$D/report.json" ] || continue
    mkdir -p reports/question-first/$N/$Q
    cp "$D"/report.json "$D"/report.md reports/question-first/$N/$Q/
    cp "$RUNS"/engine/$N/$Q/funnel.json reports/question-first/$N/$Q/ 2>/dev/null
  done
done
cp -r $EV/scores/mapcheck reports/question-first/mapcheck 2>/dev/null
cp $EV/failures.md reports/question-first/ 2>/dev/null
git checkout results && git pull --ff-only origin results   # reports/ is untracked, so it comes along
git add reports/question-first
git status --short | grep -v '^A  reports/question-first' ; echo "(nothing above: only report files)"
git commit -m "reports: question-first runs on Slurm"
git push origin results
git tag -a ev3 -m "EV3: question-first runs on Slurm" && git push origin ev3
```

The `results` branch takes report files only: no run directories, no caches, no corpora, no code changes. Never push
to `main`, and never make a new branch. Send the user the tag `ev3` and `reports/question-first/summary.md`.
