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
- Run the code of the tag `ev3-code` (step 0); save report files only, on the `results` branch, and tag them `ev3`
  (step 7).

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
git fetch origin --tags && git checkout --detach ev3-code     # the code: main with the engine, run and score fixes
git describe --tags                       # ev3-code; record this and `git rev-parse HEAD` in summary.md
git submodule update --init --recursive
git -C llm-setup log -1 --oneline         # expect 4c8ccbf GLiNER: start failure keeps the stack, ...
uv sync --locked --all-groups
uv run evidence --help | head -n 3        # the entry points exist
uv run evaluate score --help | grep question-id
```

If the tag `ev3-code` does not exist (`git checkout` fails), stop: **USER**. Never run from a bare `origin/main`:
the tag is the one commit known to hold all three fixes.

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
   `$JOB`). Then add this session's variables (the grid's jobs read them from there). The first line drops 0.3's
   EV2 variables `Q` (the EV2 question's text), `P` and `PA` (its protocols): this session's scripts take the
   question id as an argument, and a leftover `Q` or `P` would only point them at the wrong file.

```bash
cat >> "$EV/in-job.env" <<EOF
unset Q P PA
export C_MAIN=$PWD/tests/EV2/corpora/rag-claude-s1-mixed
export C_HARD=$PWD/tests/EV2/corpora/rag-tpl-hard-complex
export QS="rag-factuality rag-hallucination rag-latency inv-metrics inv-methods inv-datasets cons-accuracy cons-hallucination best-accuracy best-hallucination"
export GLINER_URL=http://127.0.0.1:8090
EOF
source "$EV/in-job.env"
mkdir -p "$EV"/{logs,runs,scores,cache,agent-work}
echo "$JOB $RUNS $C_MAIN $GLINER_URL"; echo "$QS" | wc -w      # the job id, the paths, 10
echo "Q=${Q-unset} P=${P-unset} PA=${PA-unset}"                 # Q=unset P=unset PA=unset
squeue -h -j "$JOB" -o '%i %T'                                  # the job id and RUNNING
```

   Leave out the `GLINER_URL` line only when GLiNER did not start in 1.5 (and say so in the report). `launch.sh`
   reads `JOB` only from in-job.env, so if you start the stack again later, update it there at once (with `JOB`
   set to the new job, as in 1.5), then check it as above:
   `sed -i "s/ JOB=[0-9]*/ JOB=$JOB/" "$EV/in-job.env" && source "$EV/in-job.env" && squeue -h -j "$JOB" -o '%i %T'`.
   A stale `JOB` makes every launch fail at once (srun: invalid job id), before any run starts.

Good, for every finished engine run (section 4 makes them): no GLiNER call was skipped (`skipped=0` on every
line), and GLiNER found something (`found=` above 0) in the runs whose protocol has a `gliner_` step and needed it.
`rag-factuality` and `inv-methods` have no GLiNER step, so `found=0` there is expected; in `gaps` mode GLiNER runs
only where an earlier step left a gap, so a 0 elsewhere is a note, not a failure.

```bash
for N in rag-claude-s1-mixed rag-tpl-hard-complex; do for Q in $QS; do
  G=$Q-cascade-gaps; [ "$Q" = rag-factuality ] && G=cascade-gaps; R=$RUNS/$G/$N   # as one.sh, section 4
  [ -f "$R/run.json" ] || continue
  echo "$N $Q skipped=$(grep '"status":"skipped"' "$R/events.jsonl" | grep -c '"agent_id":"gliner_') found=$(grep -c gliner_ "$R/evidence.jsonl")"
done; done                                  # skipped=0 on every line
```

A skipped GLiNER call (the service was not reachable) is only an `extractor_call` event with status `skipped` in
`events.jsonl`; `evidence run` does not print it, and `funnel.json` leaves it out (its own `skipped` means a paper
the screen left out). The engine asks GLiNER's `/info` when a run starts and, while it gets no answer, again at
most once a minute at a later GLiNER step: the steps before the service answers are skipped, the ones after it run.
A skip is not stored in the record cache, so skipped GLiNER steps need a **plain rerun** after the run dir is moved
aside, not `--retry-errors`: `one.sh <question> <corpus> rerun` (section 4) does exactly that. If the service dies
mid-run, the GLiNER steps return errors (`service_call`, below), the funnel goes to the next extractor and runs
still finish.

**Failed calls.** A failed LLM call (the gateway refused, timed out or was restarting) has the error reason
`model_call` (`evidence/extractors/llm.py`, and the LLM screen); a failed GLiNER `/predict` has `service_call`
(`evidence/extractors/gliner.py`, the only `service_call`). Either way the call's result is `error` (every chunk
failed) or `partial` (some chunks failed), the funnel moves on, and the run finishes with less evidence. These
results are stored in the record cache, so a plain rerun reuses them. So `evidence run` counts them once it has
written the run: above 0 it prints `FAIL engine-errors <run dir> <count>` and exits with code 2 (the run stays on
disk), and `one.sh` then prints `FAIL engine-errors <question> <corpus>`. Retry those runs with
`one.sh <question> <corpus> retry` once the service answers (section 4, "Retries").

## 2. Offline check (login node, no model)

```bash
uv run evidence run --protocol evidence/protocols/inv-datasets.yaml --corpus $C_MAIN --out $EV/runs/check \
  --cache $EV/cache/check --extractors regex-only --strategy gaps --workers 3 --run-id check
uv run evidence replay $EV/runs/check/check | grep '"ok"'           # "ok": true
uv run evaluate score --run $EV/runs/check/check --corpus $C_MAIN --question-id inv-datasets --out $EV/scores/check
```

Good: the score writes `report.json` and `report.md`; `evaluate score --question-id nope` is refused with the list
of ids. This only checks the spelling; the numbers are not results (regex-only recall is low).

Then check that the code holds the scoring and engine fixes. **If either line below prints `MISSING`, stop:
USER** (the wrong code is checked out; scores made with it would count A over every type and the old C rule, or
`best-*` would never escalate the metric):

```bash
uv run python -c 'import json, sys; e = json.load(open(sys.argv[1]))["extraction"]; print("scored_types", e["scored_types"] if "scored_types" in e else "MISSING")' "$EV/scores/check/report.json"
grep -q no_question_metric evidence/kinds/best.py && echo "no_question_metric ok" || echo "no_question_metric MISSING"
```

Good: `scored_types ['dataset']` and `no_question_metric ok`.

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

`one.sh` runs the three systems for one question and one corpus, then scores. Every run is where the web app
keeps it, so the app lists, opens and scores the grid's runs as its own (`$EV` is the app's `$EV`). The engine run
is `$EV/runs/<question>-cascade-gaps/<corpus>`, and for `rag-factuality` `$EV/runs/cascade-gaps/<corpus>`
(`webapp/evjobs.py`, `run_group`: the group of a repo protocol run with the cascade and the `gaps` strategy; the
run name is the corpus, the app's default). A baseline answer is `$EV/runs/<system>/<corpus>.<question>`, and for
`rag-factuality` `$EV/runs/<system>/<corpus>` (`baseline_name`, the EV2 layout), so the app's Score finds it. Each
system has its own cache file, because two processes must never append to the same cache file. A finished system
is skipped (the engine's `run.json`, a baseline's `answer.json`), so `one.sh` and `grid.sh` can be started again
after a stop and only do what is missing; the score is always written again.

```bash
cat > "$EV/one.sh" <<'EOF'
#!/usr/bin/env bash
# one.sh <question-id> <corpus-dir> [retry|rerun]: engine + RAG baseline + agent baseline + score.
# Skips a finished system (the engine's run.json, a baseline's answer.json). `retry` and `rerun` first move the
# engine run aside (kept under runs/failed/<corpus>/) and run it again: `retry` with --retry-errors (cached failed
# calls, status error or partial, are asked again), `rerun` without (skipped GLiNER steps; a killed run).
set -u
Q=$1; C=$2; MODE=${3:-}; N=$(basename "$C")
case $MODE in ""|retry|rerun) ;; *) echo "FAIL one.sh $Q $N: unknown mode '$MODE' (retry or rerun)"; exit 2;; esac
P=evidence/protocols/$Q.yaml
G=$Q-cascade-gaps; [ "$Q" = rag-factuality ] && G=cascade-gaps   # the engine run's group, as the web app names it
BN=$N.$Q; [ "$Q" = rag-factuality ] && BN=$N        # the baselines' run name, as the web app names it
RUN=$RUNS/$G/$N; mkdir -p "$RUNS/$G" "$SCORES/$N"   # the engine run dir: <group>/<corpus>
RETRY=()
if [ -n "$MODE" ] && [ -e "$RUN" ]; then
  mkdir -p "$RUNS/failed/$N"
  mv "$RUN" "$RUNS/failed/$N/$Q-$(date +%Y%m%dT%H%M%S)"   # a run dir is never overwritten; keep it for the report
fi
[ "$MODE" = retry ] && RETRY=(--retry-errors)
if [ -f "$RUN/run.json" ]; then                     # the engine writes run.json last
  echo "skip engine $Q $N: done"
elif [ -e "$RUN" ]; then
  echo "FAIL engine $Q $N: a run dir without run.json is in the way (a killed run); one.sh $Q $C rerun moves it to $RUNS/failed/$N/ and runs again"
else
  uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/$G" --cache "$CACHE/engine-$N" \
    --model orch-model --strategy gaps --workers 3 --run-id "$N" ${RETRY[@]+"${RETRY[@]}"}
  rc=$?
  if [ "$rc" -eq 2 ] && [ -f "$RUN/run.json" ]; then     # the run is written, but some extractor calls failed
    echo "FAIL engine-errors $Q $N: failed calls (count on the FAIL line above); when the service answers: one.sh $Q $C retry"
  elif [ "$rc" -ne 0 ]; then
    echo "FAIL engine $Q $N (exit $rc)"
  fi
fi
if [ -f "$RUNS/rag-baseline/$BN/answer.json" ]; then
  echo "skip rag $Q $N: done"
else
  uv run evaluate rag-baseline --corpus "$C" --question-id "$Q" --out "$RUNS/rag-baseline/$BN" \
    --cache "$CACHE/rag-baseline-$N.jsonl" --model orch-model --retrieval global --k 8 || echo "FAIL rag $Q $N"
fi
if [ -f "$RUNS/agent-baseline/$BN/answer.json" ]; then
  echo "skip agent $Q $N: done"
else
  uv run evaluate agent-baseline --corpus "$C" --question-id "$Q" --out "$RUNS/agent-baseline/$BN" \
    --cache "$CACHE/agent-baseline-$N.jsonl" --model orch-model --agent-root "$AGENT_ROOT" --run-id "$BN" \
    || echo "FAIL agent $Q $N"
fi
ARGS=()
[ -f "$RUN/run.json" ] && ARGS+=(--run "$RUN")
for s in rag-baseline agent-baseline; do
  [ -f "$RUNS/$s/$BN/answer.json" ] && ARGS+=(--baseline "$RUNS/$s/$BN/answer.json")
done
if [ "${#ARGS[@]}" -eq 0 ]; then
  echo "FAIL score $Q $N: no answer to score"
else
  uv run evaluate score "${ARGS[@]}" --corpus "$C" --question-id "$Q" --out "$SCORES/$N/$Q" || echo "FAIL score $Q $N"
fi
EOF
cat > "$EV/grid.sh" <<'EOF'
#!/usr/bin/env bash
# grid.sh <corpus-dir>: one.sh for every question of $QS (from in-job.env), one after another
set -u
for Q in $QS; do "$EV/one.sh" "$Q" "$1"; done
EOF
chmod +x "$EV/one.sh" "$EV/grid.sh"
```

The scripts read `RUNS`, `SCORES`, `CACHE`, `AGENT_ROOT`, `EV` and `QS` from `in-job.env` (0.3 and step 1.6), and
the relative protocol path needs the repository root as working directory, which `in-job.env` sets. Run them
through `launch.sh`, never as plain commands on the login node.

First run `one.sh` once on one question and check its output (`$EV/logs/one-check.log`, the run dir, the two
answers, `report.md`) before starting the grid; the grid skips what this run finished:

```bash
"$EV/launch.sh" one-check "$EV/one.sh" inv-datasets "$C_MAIN"; tail -n 1 "$EV/logs/one-check.launch"
```

Run the questions of one corpus one after another (they share that corpus's three cache files, and two processes must
never append to the same cache file). The two corpora may run side by side, so two long `orch-model` steps are
active at once:

```bash
nohup "$EV/launch.sh" grid-main "$EV/grid.sh" "$C_MAIN" > /dev/null 2>&1 &
nohup "$EV/launch.sh" grid-hard "$EV/grid.sh" "$C_HARD" > /dev/null 2>&1 &
```

The logs are `$EV/logs/grid-main.log` and `grid-hard.log` (`launch.sh` starts a step's log afresh, so give a new
step name to every later launch); `FAIL` lines list what to retry. Starting a grid again is safe: it only runs
what is not finished (an engine run without `run.json`, a baseline without `answer.json`), and a killed engine run
dir is reported, not overwritten (see "Killed runs" below).

Retries: for a `FAIL engine-errors` line (failed LLM calls, `model_call`, or failed GLiNER calls, `service_call`;
section 1, "Failed calls"), once the gateway or the service answers again, or for a `FAIL engine` line, run `one.sh`
with `retry`. It moves the run dir aside to `$RUNS/failed/<corpus>/`, runs the engine again with `--retry-errors`
(the cached `error` and `partial` results are asked again), runs any baseline that has no answer, and scores again.
Run it in the job, and only when no grid is running on that corpus (it appends to that corpus's caches):

```bash
"$EV/launch.sh" retry-main-inv-metrics "$EV/one.sh" inv-metrics "$C_MAIN" retry
```

Killed runs: an engine run dir without `run.json` (the Slurm time limit, a lost node, a cancelled step) blocks its
own rerun: `evidence run` refuses it ("exists without run.json: a run that was killed or crashed ... Move it aside,
to $RUNS/failed/<corpus>/ ..., and run again") and `one.sh` prints `FAIL engine <question> <corpus>: a run dir
without run.json is in the way`. Do what it says: `one.sh <question> <corpus> rerun` moves it to
`$RUNS/failed/<corpus>/` and runs again (the record cache keeps the calls it finished, so this is cheap). A run
that is still going has no `run.json` either, so first make sure nothing runs on that corpus: every step you
launched for it (`grid-*`, `one-*`, `retry-*`, `rerun-*`) has its `exit` line as the last line of
`$EV/logs/<step>.launch` (launch.sh writes it when the command ends), and `squeue --steps -j "$JOB"` shows no
step you cannot account for. Never move a live run dir.

Reruns: for a run with skipped GLiNER steps (step 5 counts them; the service was not up yet), once GLiNER answers,
run `one.sh` with `rerun` instead: it moves the run dir aside the same way and runs the engine again **without**
`--retry-errors` (skips are not cached, so a plain run makes those GLiNER calls; every other call comes from the
cache). Same rules: in the job, no grid on that corpus, a new step name:
`"$EV/launch.sh" rerun-main-inv-metrics "$EV/one.sh" inv-metrics "$C_MAIN" rerun`.

(Pass the question and corpus as arguments, as above: a command run through `launch.sh` sees only `in-job.env`,
never a `Q` set in your login shell, and `in-job.env` unsets 0.3's `Q`, `P` and `PA` (step 1.6).)

The hard corpus (112 papers) is the slow one; if the job is about to end, finish the main corpus first and report
the hard corpus as partial.

## 4b. Extra rows on the main corpus

The grid's RAG baseline reads 8 passages of the whole corpus, so it sees at most 8 papers, and a paper it leaves
out counts as wrong in C. The rows below make the comparison fair and show how much of a number is noise.
`extra.sh` runs one extra system (a "variant") for every question on one corpus and scores each answer **on its
own**, in `$SCORES/<corpus>/<question>.<variant>/`. Each variant has its own cache file or dir, so it never shares
a cache with the grid or with another variant; never run the same variant twice at once on one corpus.

```bash
cat > "$EV/extra.sh" <<'EOF'
#!/usr/bin/env bash
# extra.sh <variant> <corpus-dir> [question-id|all] [retry|rerun]: one extra system for every question of $QS
# (or one), each scored on its own in $SCORES/<corpus>/<question>.<variant>. Skips a finished answer or run.
# RAG variants: rag-per-paper (top 2 passages of every paper), rag-per-paper-k1 (top 1 of every paper),
# rag-oracle (the passages truth needs; a diagnostic that reads ground_truth.json), rag-seed1, rag-seed2 (the
# grid's RAG with another seed).
# Engine variants: regex-only, llm-only (--extractors), run in $RUNS/<question>-<variant>/<corpus>; engine-r2,
# the grid's engine again with a fresh cache, in the grid's group as <corpus>-r2.
# `retry` and `rerun` move an engine variant's run dir aside first, as one.sh does.
set -u
V=$1; C=$2; ONLY=${3:-all}; MODE=${4:-}; N=$(basename "$C")
case $MODE in ""|retry|rerun) ;; *) echo "FAIL extra.sh $V $N: unknown mode '$MODE' (retry or rerun)"; exit 2;; esac
RAG=(); EXT=cascade; RID=$N; GV=$V
case $V in
  rag-per-paper) RAG=(--retrieval per_paper --k 2) ;;
  rag-per-paper-k1) RAG=(--retrieval per_paper --k 1) ;;
  rag-oracle) RAG=(--oracle-passages) ;;
  rag-seed1) RAG=(--retrieval global --k 8 --seed 1) ;;
  rag-seed2) RAG=(--retrieval global --k 8 --seed 2) ;;
  regex-only|llm-only) EXT=$V ;;
  engine-r2) RID=$N-r2; GV=cascade-gaps ;;
  *) echo "FAIL extra.sh: unknown variant '$V'"; exit 2;;
esac
QL=$QS; [ "$ONLY" = all ] || QL=$ONLY
for Q in $QL; do
  BN=$N.$Q; [ "$Q" = rag-factuality ] && BN=$N       # the baselines' run name, as one.sh
  OUT=$SCORES/$N/$Q.$V; mkdir -p "$SCORES/$N"
  if [ "${#RAG[@]}" -gt 0 ]; then                     # a RAG variant
    A=$RUNS/$V/$BN/answer.json
    if [ -f "$A" ]; then
      echo "skip $V $Q $N: done"
    else
      uv run evaluate rag-baseline --corpus "$C" --question-id "$Q" --out "$RUNS/$V/$BN" \
        --cache "$CACHE/$V-$N.jsonl" --model orch-model "${RAG[@]}" || echo "FAIL $V $Q $N"
    fi
    if [ -f "$A" ]; then
      uv run evaluate score --baseline "$A" --corpus "$C" --question-id "$Q" --out "$OUT" || echo "FAIL score $V $Q $N"
    fi
    continue
  fi
  G=$Q-$GV; [ "$V" = engine-r2 ] && [ "$Q" = rag-factuality ] && G=cascade-gaps   # r2: the grid's group
  RUN=$RUNS/$G/$RID; mkdir -p "$RUNS/$G"              # an engine variant
  if [ -n "$MODE" ] && [ -e "$RUN" ]; then
    mkdir -p "$RUNS/failed/$N"; mv "$RUN" "$RUNS/failed/$N/$Q-$V-$(date +%Y%m%dT%H%M%S)"
  fi
  RETRY=(); [ "$MODE" = retry ] && RETRY=(--retry-errors)
  if [ -f "$RUN/run.json" ]; then
    echo "skip $V $Q $N: done"
  elif [ -e "$RUN" ]; then
    echo "FAIL $V $Q $N: a run dir without run.json is in the way; extra.sh $V $C $Q rerun"
  else
    uv run evidence run --protocol "evidence/protocols/$Q.yaml" --corpus "$C" --out "$RUNS/$G" \
      --cache "$CACHE/$V-$N" --model orch-model --extractors "$EXT" --strategy gaps --workers 3 --run-id "$RID" \
      ${RETRY[@]+"${RETRY[@]}"}
    rc=$?
    if [ "$rc" -eq 2 ] && [ -f "$RUN/run.json" ]; then
      echo "FAIL engine-errors $V $Q $N: when the service answers: extra.sh $V $C $Q retry"
    elif [ "$rc" -ne 0 ]; then
      echo "FAIL $V $Q $N (exit $rc)"
    fi
  fi
  if [ -f "$RUN/run.json" ]; then
    uv run evaluate score --run "$RUN" --corpus "$C" --question-id "$Q" --out "$OUT" || echo "FAIL score $V $Q $N"
  fi
done
EOF
cat > "$EV/extras.sh" <<'EOF'
#!/usr/bin/env bash
# extras.sh <corpus-dir> <variant>...: extra.sh for each variant, one after another
set -u
C=$1; shift
for V in "$@"; do "$EV/extra.sh" "$V" "$C"; done
EOF
chmod +x "$EV/extra.sh" "$EV/extras.sh"
```

Start the extras on the main corpus **after `grid-main` has finished** (its log ends and `launch.sh` printed its
exit), so the GPU is shared with at most the hard grid; they write `FAIL` lines as the grid does:

```bash
nohup "$EV/launch.sh" extras-main "$EV/extras.sh" "$C_MAIN" rag-per-paper rag-oracle regex-only llm-only \
  rag-seed1 rag-seed2 engine-r2 > /dev/null 2>&1 &
```

The rows, in this order of importance (stop at the job's end and report what is missing):

1. **`rag-per-paper`** (main): RAG with `--retrieval per_paper --k 2`, the top 2 passages of **every** paper (40
   passages, about 15k tokens). This is the fair RAG row for C: a paper left out counts as wrong, and the grid's
   global RAG leaves out at least 12 of 20 papers by construction. On the hard corpus it only fits with one passage
   per paper (112 x 1 500 characters, about 42k tokens) and a context of at least 64k tokens: check
   `grep -n max_model_len llm-setup/profiles/orch-3x40-gliner.yaml` (the `orch` model's line). Only if it is
   65536 or more, after `grid-hard` has finished:
   `nohup "$EV/launch.sh" extras-hard "$EV/extras.sh" "$C_HARD" rag-per-paper-k1 > /dev/null 2>&1 &`.
   Otherwise write "rag-per-paper not run on hard: max_model_len <n>" in the summary.
2. **`rag-oracle`** (main): RAG on the passages truth needs (`--oracle-passages`) instead of BM25. It reads
   `ground_truth.json` on purpose, so it is a **diagnostic**, not a baseline: its C is the ceiling of RAG's
   reasoning when retrieval is perfect, and the gap to `rag-per-paper` is what retrieval costs. Its answer says
   `system: rag-oracle-passages`; label its row so in the table.
3. **`regex-only`** and **`llm-only`** (main): the engine with one kind of extractor (`--extractors regex-only`,
   no model calls; `--extractors llm-only`). In `gaps` mode a later extractor only sees what the earlier ones left
   open, so the per-extractor rows of step 6 item 2 are not standalone scores. These two rows are: report A, B
   and C of `regex-only`, `llm-only` and the grid's cascade side by side, and read each step as a **marginal gain**
   (cascade minus regex-only is what the later extractors add). Retries and reruns work as in one.sh:
   `"$EV/launch.sh" retry-llm-only-main "$EV/extra.sh" llm-only "$C_MAIN" inv-metrics retry`.
4. **Repeats** (main): `rag-seed1` and `rag-seed2` are the grid's RAG (`global`, k 8) with `--seed 1` and `2`;
   `engine-r2` is the grid's engine once more with a fresh cache dir (`$CACHE/engine-r2-<corpus>`) and
   `--run-id <corpus>-r2`, so every call is asked again. Temperature is 0, but the server batches requests, so
   answers can still differ. Report, per question, the spread of C over the grid's run and its repeats
   (min-max). A difference between systems smaller than that spread is not a result.

## 4c. The counterfactual corpus (main, rag-factuality)

`rag-claude-s1-mixed-cf-S001-contradicts` is the main corpus with one study changed: S001's numbers are rewritten so
its direction goes from `supports` to `contradicts` (`variant.json` lists the changed values). Every system should
change its answer for S001 and nowhere else. **Only if the corpus is present** (it is in git; `ls` below shows its
`variant.json`); if it is not, skip this step and write "counterfactual not run: corpus missing" in the summary.
Run it after `grid-main` has finished (it has its own caches, named after the corpus):

```bash
C_CF=$(dirname "$C_MAIN")/rag-claude-s1-mixed-cf-S001-contradicts
ls "$C_CF/variant.json" "$C_CF/manifest.json"
nohup "$EV/launch.sh" cf-main "$EV/one.sh" rag-factuality "$C_CF" > /dev/null 2>&1 &
```

When `cf-main` has finished and `$SCORES/rag-claude-s1-mixed-cf-S001-contradicts/rag-factuality/report.json`
exists, compare it with the main corpus (no model; login node is fine):

```bash
C_CF=$(dirname "$C_MAIN")/rag-claude-s1-mixed-cf-S001-contradicts
uv run evaluate shift --base "$SCORES/rag-claude-s1-mixed/rag-factuality" \
  --variant "$SCORES/rag-claude-s1-mixed-cf-S001-contradicts/rag-factuality" \
  --variant-json "$C_CF/variant.json" --out "$SCORES/shift-cf-S001"
```

Good: it prints `shifted as expected:` with one `yes` or `no` per system (`evidence-engine`, `rag-baseline`,
`agent-baseline`). Copy that line and `shift.md`'s table into the summary (step 6 item 7). A `no` is a result, not
a failure.

## 5. Check each run

- `uv run evidence replay $RUNS/<question>-cascade-gaps/<corpus> | grep '"ok"'` (for `rag-factuality`
  `$RUNS/cascade-gaps/<corpus>`) gives `"ok": true`. (A replay is also `ok` for a run whose calls failed: it
  replays the cached failures. That is why the next check exists.)
- Failed calls: the count per run, 0 when every LLM and GLiNER call answered. Report it per run (step 6, item 5),
  and retry every run above 0 with `one.sh <question> <corpus> retry` (section 4, "Retries"), then count again.
  Retry one run at most twice: if it is still above 0, stop retrying it and report its count (and the FAIL lines)
  under Failures:

```bash
for N in rag-claude-s1-mixed rag-tpl-hard-complex; do for Q in $QS; do
  G=$Q-cascade-gaps; [ "$Q" = rag-factuality ] && G=cascade-gaps; R=$RUNS/$G/$N   # as one.sh, section 4
  [ -f "$R/run.json" ] || { echo "$N $Q: no finished run"; continue; }
  echo "$N $Q $(uv run python -c 'import sys; from evidence.rundir import RunDir; print(RunDir(sys.argv[1]).failed_calls())' "$R")"
done; done
```

- `$SCORES/<corpus>/<question>/report.md` exists for each of the 20 pairs; note any missing one with its `FAIL` line.
- GLiNER: the loop at the end of section 1 counts, per run, the GLiNER calls skipped because the service was not
  up (`skipped=`, 0 when it was up) and the evidence GLiNER found (`found=`). Report both per run.
  Above 0 while GLiNER now answers (`curl -s 127.0.0.1:8090/info` through `srun`, step 1.5): rerun that run with
  `one.sh <question> <corpus> rerun` (section 4, "Reruns"; not `retry`), then count again.
  (`funnel.json`'s `skipped` is a paper the screen left out, not GLiNER.)

## 6. The deliverable table

Read `report.json` / `report.md` of each score dir. A and B exist for the engine run only (`extraction`,
`integration`); the baselines are scored on C only (`synthesis`, one row per system: `evidence-engine`,
`rag-baseline`, `agent-baseline`). A is the `all` / `all` row of `extraction`: precision, recall, f1 over the
evidence types this question's protocol extracts, listed in `extraction.scored_types` (for example, `inv-datasets`
is scored on datasets only). It is computed the same way for every kind, but over different types, so compare A
within a question (across corpora and systems), not across questions or kinds; copy `extraction.scored_types` into
the summary next to A. Step 2 already stops on scoring code without `scored_types`; if a `report.json` still has
none, write A as `-` for that run and say so under Failures. B and C by kind, with the field names as they are in
`report.json`:

| kind | B (engine only) | C (every system) |
|---|---|---|
| effect | `integration.rows`: `association_accuracy` | `synthesis`: `label_correct`, `direction_accuracy`, `completeness` |
| inventory | `integration`: `clean_share` | `synthesis`: `precision`, `recall`, `f1` (`recall` is inventory's completeness) |
| consistency | `integration`: `claim_accuracy` | `synthesis`: `per_study_accuracy`, `completeness` |
| best | `integration`: `kind_accuracy` | `synthesis`: `winner_correct`, `per_study_accuracy`, `completeness` |

`direction_accuracy` (effect) and `per_study_accuracy` (best, consistency) are over the papers the truth can decide
only (effect: a determined direction; best: a winner or a tie; consistency: `agrees` true or false, so duplicates
and papers with missing data are left out). A decidable paper the system leaves out or calls undetermined counts as
wrong; an empty answer scores 0. `completeness` is the share of those decidable papers the system answered at all,
so "wrong" and "silent" can be told apart. The old numbers over all papers are `direction_accuracy_all_papers` /
`per_study_accuracy_all_papers`; do not copy them into the table.

A precision of `null` (`report.md` shows `n/a`) means the system gave nothing: write `n/a`, never 0. This applies to
inventory C precision and to the per-extractor A rows of an extractor that found nothing.
`report.md` shows the same numbers under "B." and "C." headings; copy from there if a field is nested.

Write `reports/question-first/summary.md` with:

1. **Main table**, one row per question x system, for each corpus:

   | corpus | question | system | A (f1) | B | C |
   |---|---|---|---|---|---|

   Engine rows have A, B and C; the baseline rows have C only, and `-` for A and B. Write B and C as the fields of
   the table above (for example `label_correct / direction_accuracy / completeness`), and give each question's
   `scored_types` once under the table.
2. **Per-extractor A**, for each corpus: from `report.json`'s `extractors.rows`, one line per extractor id with
   precision, recall, f1, for the regex, abbreviation, GLiNER, number and LLM extractors (`regex_*`, `abbrev_*`,
   `gliner_*`, `number_*`, `llm_*`), per question. Each extractor has two rows with `level = all`: copy the
   **per-type row**, the one whose `evidence_type` is the extractor's own type (`metric` for `gliner_metric`), not
   the one with `evidence_type = all`. A GLiNER extractor with no row at all was skipped on every paper (the service
   was not up); one with zero matches found nothing.
3. **Mapping check** from step 3: per kind, the retries and failures you saw (or "none").
4. **GPU and GLiNER**: `nvidia-smi` driver and CUDA, GLiNER's memory use, free memory left on GPU 0, whether
   `orch-3x40-gliner.yaml` needed `gpu_memory_utilization: 0.88`, whether GLiNER started (`gliner health ok`),
   whether `GLINER_URL` was set.
5. **Failures**: each `FAIL` line and what you did; the failed-call count of every engine run (step 5), before
   and after its retry, and which runs needed `one.sh ... retry`.
6. **Extra rows** (step 4b), for each corpus they ran on: one row per question x variant, from
   `$SCORES/<corpus>/<question>.<variant>/report.json`, in the main table's columns (a RAG variant has C only; an
   engine variant has A, B and C). Name the variant in the system column (for example `rag-baseline (per_paper)`).
   Say under the table that the `rag-per-paper` row is the fair RAG comparison for C: every paper is seen, so a
   left-out paper there is the model's choice, not the retriever's.
7. **Counterfactual** (step 4c): the `shifted as expected` line and the table of `shift.md`, or why it did not run.

## 7. Hand-back

The scores alone are not enough: a later scoring fix needs the answers and runs again, and `data-tmp` is cleaned.
So the hand-back keeps, besides every score dir, the files a score is made from, under
`reports/question-first/runs/` with the same paths as under `$RUNS`: of every finished engine run `answer.json`,
`run.json`, `funnel.json` and `events.jsonl` (gzipped); of every baseline its `answer.json`. Run directories are not
copied whole (no `evidence.jsonl`, `reexec.json` or agent work dirs). `$RUNS/check` is left out, `$RUNS/failed`
is kept (it shows what was retried).

```bash
R=$PWD/reports/question-first; mkdir -p "$R/runs" "$R/scores"
for N in rag-claude-s1-mixed rag-tpl-hard-complex; do         # the old layout: <corpus>/<question>/report.*
  for Q in $QS; do
    D=$SCORES/$N/$Q; [ -f "$D/report.json" ] || continue
    mkdir -p "$R/$N/$Q"
    cp "$D/report.json" "$D/report.md" "$R/$N/$Q/"
    G=$Q-cascade-gaps; [ "$Q" = rag-factuality ] && G=cascade-gaps   # the engine run, as one.sh writes it
    cp "$RUNS/$G/$N/funnel.json" "$R/$N/$Q/" 2>/dev/null
  done
done
# every score dir (grid, extras, shift, mapcheck), with its path under $SCORES
(cd "$SCORES" && find . -path ./check -prune -o -type f \( -name 'report.*' -o -name 'shift.*' \) -print0 \
  | xargs -0 -r cp --parents -t "$R/scores")
# the answers and runs the scores are made from, with their paths under $RUNS
(cd "$RUNS" && find . -path ./check -prune -o -type f \( -name answer.json -o -name run.json -o -name funnel.json \) \
  -print0 | xargs -0 -r cp --parents -t "$R/runs")
(cd "$RUNS" && find . -path ./check -prune -o -type f -name events.jsonl -print0 | while IFS= read -r -d '' f; do
  mkdir -p "$R/runs/$(dirname "$f")" && gzip -c "$f" > "$R/runs/$f.gz"; done)
cp "$EV/failures.md" "$R/" 2>/dev/null
du -sh "$R/runs" "$R/scores"; find "$R" -type f -size +50M      # the last line prints nothing
```

The caches hold every model reply; with them a run can be replayed and rescored without the model. Check their
size before packing them:

```bash
du -sh "$CACHE"                                         # the record caches, uncompressed
tar -C "$EV" -czf "$EV/caches.tar.gz" cache && ls -lh "$EV/caches.tar.gz"
```

- If `caches.tar.gz` is under 90 MB: `split -b 45m "$EV/caches.tar.gz" "$R/caches.tar.gz.part-"` (GitHub refuses
  files over 100 MB and warns over 50 MB), and write in `summary.md` how to join them
  (`cat caches.tar.gz.part-* > caches.tar.gz`).
- If it is larger: do not commit it. Copy it off `data-tmp` to a place that is not cleaned
  (`cp "$EV/caches.tar.gz" ~/`, your home directory) and write its path and size in `summary.md`; the **USER**
  collects it.

```bash
git checkout results && git pull --ff-only origin results   # reports/ is untracked, so it comes along
git add reports/question-first
git status --short | grep -v '^A  reports/question-first' ; echo "(nothing above: only report files)"
git commit -m "reports: question-first runs on Slurm"
git push origin results
git tag -a ev3 -m "EV3: question-first runs on Slurm" && git push origin ev3
```

The `results` branch takes the files above only: no whole run directories, no corpora, no code changes. Never push
to `main`, and never make a new branch. Send the user the tag `ev3` and `reports/question-first/summary.md`.
