# Runbook: the whole system on Slurm, end to end (e2e build)

Everything in milestones 1–4 is built on `e2e-build` and tested only against scripted models, fake
servers, an in-memory Argilla and the D1 fixture papers (`docs/milestones-3-4.md`, `tests/RESULTS.md`).
This one session runs every part on the cluster for the first time, together: the fixed agent loop, the 12
concepts, a gold trial and two gold builds, the e2e smoke batch, replay and re-execution, scoring and the
SPARQL store, the web app with the real chat model, and (if reachable) Argilla.

**Scope (14 Oct).** The thesis design changed after this build: one agent, `claim` always on. The claim_off
condition, the attach step and subagents (`spawn`) are dropped, so this session runs **claim_on only**
(`agent/manifests/e2e-smoke.json`: q01 and q10, two repeats) and **no** `--spawn on` run. The code for them is
still in the branch (it is removed later); do not run or test it here. Concepts are still proposed and picked
as written: they become evidence plans later, and this session measures the propose step on the real model.

**Failures are expected.** When a step fails, record it (below) and go on with the next step that does not
depend on it. The point is that every part has met the real models, the corpus and the node once, and that
the numbers exist from which the user freezes the budget.

## Rules

- Branch `e2e-cluster`, made from `origin/e2e-build`. Never push `main` or `e2e-build`; push `e2e-cluster`
  at the end.
- **Record every failure** in `$E2E/failures.md`, one entry each: step number, the exact command, its exit
  code, the last 30 lines of its output (from the step's log), and what you did next (fixed in commit X /
  skipped / retried). Then continue with the next independent step (dependency column of the step list).
- **Fixes** are allowed on `e2e-cluster`: one commit per fix, each with a test, and
  `uv run pytest <package>/tests -q -W ignore::SyntaxWarning` green for the package you changed before you
  go on. **Never** change the budgets, the prompts (`agent/prompts/`, `gold/prompts/`), the anchor rules
  (`agent/anchor.py`), the questions, the pre-registered analysis (`scoring/`), or any threshold to make
  something pass: record it and continue. Do not change the `llm-setup` submodule in this session.
- **Secrets.** `LITELLM_MASTER_KEY` and `ARGILLA_API_KEY` are only read from the environment. Never print,
  `echo`, log or commit a key; no `set -x`; never pass a key on a command line. For a secret record only
  "set" / "not set". Never kill or signal a process to test a permission (`kill -0` only).
- **Ceph, not git.** Run directories, gold directories, the store and logs live under `$E2E` on Ceph,
  outside the repo. Copy into the repo only the small files named under "Finish" (each under 1 MB).
- Steps marked **USER** need the user: stop and ask. If the user does not answer, record `NOT RUN (USER)`
  and go on.
- Commit messages as in `git log` (subject naming the row or area, body saying why), ending with your usual
  attribution line.

## Paths and how commands run

| Name | Value |
|---|---|
| `REPO` | the clone used for the M1 session: `/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent` |
| `E2E` | `/mnt/ceph/storage/data-tmp/2026/xepi3167/e2e-cluster` (new; everything this session writes) |
| `CORPUS` | `/mnt/ceph/storage/data-tmp/2026/xepi3167/research-agent-corpus-docling-2.110.0` (frozen, read-only) |
| `AGENT_ROOT` | `/mnt/ceph/storage/data-tmp/2026/xepi3167/agent-root-infra-final-3` (as in `tests/M1-real/*/config.json`) |
| `RUNS` | `$E2E/runs`; the smoke batch goes to `$RUNS/e2e-smoke` (= `$SMOKE`, the batch root scoring and the web app take) |
| `GOLD` | `$E2E/gold`: the session's gold, built on the **provisional** picks. Not the thesis gold: that is built after the user confirms the picks. The trial goes to `$GOLD-trial` |
| `CONCEPTS` | `$REPO/concepts` (committed in step 2) |
| `JOB` | the stack's Slurm job id (step 0) |

If `CORPUS` or `AGENT_ROOT` is not there: **USER**.

Every command from step 0.4 on runs **inside the stack job** with the session environment, in one of two ways:

- short commands: in an interactive job shell, `srun --jobid "$JOB" --overlap --pty bash -l`, then
  `source "$E2E/in-job.env"` (made in 0.3), then the commands (or one at a time:
  `srun --jobid "$JOB" --overlap "$E2E/in-job.sh" <command>`);
- commands marked **(long)**: started from the login node with `nohup`, so they keep running when your shell
  closes, with their output in a log you poll (`tail -n 20 <log>`; still running: `kill -0 <pid>`):

  ```bash
  nohup srun --jobid "$JOB" --overlap "$E2E/in-job.sh" <command> > "$E2E/logs/<step>.log" 2>&1 &
  echo $! > "$E2E/logs/<step>.pid"
  ```

  A job shell (`--pty`) kills what it started when it closes, so never start a long step from inside one.

## Order and dependencies

| Step | Uses | Needs | Time (estimate, not measured) |
|---|---|---|---|
| 0 setup, stack | — | — | 1 h (pytest ~10–35 min, stack ~11 min) |
| 1 agent fix check | orch-model | 0 | ≤ 1 h |
| 2 concepts, 12 questions | orch-model | 0 | 30 min |
| 3a gold trial q01 | sub-models | 2 (q01) | 1 h |
| 4a e2e smoke batch, **in parallel with 3a/3b** | orch-model | 2 (q01, q10) | 2–6 h |
| 3b gold full builds q01, q10 | sub-models | 3a (its call rate) | hours |
| 4b replay, re-execution | CPU | 4a | 30 min |
| 5 scoring, store | sub-models (judge) | 4a, and a key from 3b (else 3a) | 30 min |
| 6 web app, chat | sub-model-1 | 4a (5 for scores) | 30 min |
| 7 Argilla push (**USER**: tunnel and key) | — | a pool from 3b (else 3a) | 30 min |
| 8 measurements, proposed budget | — | whatever finished | 1 h |

The batch (orchestrator, GPU 0) and the gold builds (sub-models, GPUs 1–2) use different GPUs, so run them at
the same time; never run two orchestrator steps at once (the orchestrator holds about one long request, and
a second one would inflate the measured run times).

## 0. Setup

### 0.1 Checkout and tests (login node)

```bash
cd /mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent
git status --short                     # expect nothing tracked changed; otherwise USER
git fetch origin
git rev-parse --verify origin/e2e-build   # missing: USER (the user pushes e2e-build)
git checkout -b e2e-cluster origin/e2e-build
git submodule update --init --recursive
uv sync --locked --all-groups
uv run pytest -q -W ignore::SyntaxWarning 2>&1 | tail -n 3
```

Expect `776 passed, 1 skipped` and 0 failed (the count on `e2e-build` in WSL, 6 min from a Linux-side clone; the skip is
the "Landlock missing" test, so on a node with Landlock the split may differ by one). A failure here is a failure of the build: record it, look at it, and fix it on the branch only if
it is clearly a test-environment difference (for example a path); otherwise record and continue.

```bash
test -f webapp/web/dist/index.html && ls webapp/web/dist/assets/   # expect index-*.js and index-*.css
grep -o '^[A-Z_]*=' llm-setup/.env                                  # variable NAMES only, never values
```

The second line must list `LITELLM_MASTER_KEY=`; note whether it also sets `UV_PROJECT_ENVIRONMENT` or
`VIRTUAL_ENV` (0.3 unsets them, so `uv run` uses the repo's `.venv` that `uv sync` just built).

### 0.2 Stack (login node)

```bash
cd llm-setup && LLM_SETUP_PROFILE=profiles/agent-3x40.yaml sbatch slurm/llm-stack.sbatch; cd ..
export JOB=<the job id sbatch printed>
tail -n 20 llm-setup/runtime/slurm-$JOB.out      # repeat until orch and both sub replicas say ready (~11 min)
```

### 0.3 Session environment (login node)

```bash
export E2E=/mnt/ceph/storage/data-tmp/2026/xepi3167/e2e-cluster
mkdir -p "$E2E/logs" "$E2E/measure" "$E2E/verify"
cat > "$E2E/in-job.env" <<EOF
# The e2e session's environment (docs/slurm-e2e-runbook.md). Paths only: the key comes from llm-setup/.env.
set -a; source $PWD/llm-setup/.env; set +a
unset UV_PROJECT_ENVIRONMENT VIRTUAL_ENV
export REPO=$PWD E2E=$E2E JOB=$JOB
export CORPUS=/mnt/ceph/storage/data-tmp/2026/xepi3167/research-agent-corpus-docling-2.110.0
export AGENT_ROOT=/mnt/ceph/storage/data-tmp/2026/xepi3167/agent-root-infra-final-3
export RUNS=$E2E/runs GOLD=$E2E/gold CONCEPTS=$PWD/concepts SMOKE=$E2E/runs/e2e-smoke
export LITELLM_BASE_URL=http://127.0.0.1:4000/v1
cd $PWD
EOF
cat > "$E2E/in-job.sh" <<'EOF'
#!/usr/bin/env bash
# Run the arguments in the repo with the e2e session's environment (inside the stack job).
source "$(dirname "$0")/in-job.env"
exec "$@"
EOF
chmod +x "$E2E/in-job.sh"
source "$E2E/in-job.env"          # the login shell gets the same variables, so the commands below expand alike
```

In every new shell (login or job), first `export E2E=/mnt/ceph/storage/data-tmp/2026/xepi3167/e2e-cluster`
and `source "$E2E/in-job.env"`.

### 0.4 Environment check (in the job)

```bash
srun --jobid "$JOB" --overlap "$E2E/in-job.sh" bash scripts/e2e-env.sh 2>&1 | tee "$E2E/logs/0-env.log"
srun --jobid "$JOB" --overlap bash -lc 'cd llm-setup && set -a && source .env && set +a && uv run llm-setup doctor --profile profiles/agent-3x40.yaml' 2>&1 | tail -n 5
```

(The doctor runs with `llm-setup`'s own environment, as its README says, not through `in-job.sh`.)

Expect `PASS` lines for CORPUS (manifest sha256 `22e9471b…`), RUNS, GOLD, CONCEPTS, questions.json,
AGENT_ROOT, the key ("is set"), the proxy serving `orch-model, sub-model-1, sub-model-2`, Landlock ABI 8 and the
git commit; the doctor with 0 failures. If e2e-env.sh fails, fix the cause (path, stack not ready) and
repeat; nothing after this works without it.

Row `E2E-setup`: commit, pytest count, doctor result, stack job id and node (`squeue -j $JOB -h -o %N`).

## 1. Agent fix check (rows 1.13, 1.15): one claim_on run on prompt v2

The M1-real runs all ended at the budget with no answer. This run checks the fix on the real model before
anything depends on it: the same concept and seed as `c3-on-1`, now with the defaults (prompt v2, 60 steps /
2,000,000 tokens, conclude replies decoded under the reply schema, masking).

**(long)**

```bash
nohup srun --jobid "$JOB" --overlap "$E2E/in-job.sh" uv run agent run \
  --concept agent/concepts/rag-eval-datasets.json --run-id fix-on-1 --runs-root "$E2E/runs/agent-fix" \
  --condition claim_on --temperature 0.7 --seed 1 --agent-root "$AGENT_ROOT" \
  > "$E2E/logs/1-run.log" 2>&1 &
echo $! > "$E2E/logs/1-run.pid"
```

The last log line is `run fix-on-1: exit=<status> steps=<n> tokens=<n> rows=<n> answer=<final|draft|none> head=<hash>`
(exit code 0 only for `exit=submitted`). Then, in the job shell:

```bash
R=$RUNS/agent-fix/fix-on-1
uv run agent verify "$R" --corpus "$CORPUS" | tee "$E2E/verify/fix-on-1.txt"     # last line PASS ...
uv run agent pairs "$R"; uv run agent timeline "$R"
uv run agent graph "$R" --manifest "$CORPUS/manifest.json"; uv run agent export-prov "$R"
uv run agent query 1 "$R" --edge edge-000001
uv run agent query 2 "$R" --claim claim-000001
uv run agent query 3 "$R" --agent main
uv run agent query 4 "$R" --corpus "$CORPUS" --manifest "$CORPUS/manifest.json"
uv run agent query 5 "$R"
uv run agent replay "$R"                                                          # expect PASS replay ...
uv run python scripts/e2e-measure.py runs "$R"
```

Answer the three questions from the measure line and `config.json`:

| Question | Where | Pass |
|---|---|---|
| Answer produced? | `answer` column, `rows` | `final` (or `draft`) with rows > 0 |
| Guided decoding used? | `guided answer`, `guided calls`, `refused` | `yes`, ≥ 1, 0; `config.json` `loop.conclude_decoding` = `structured_outputs` |
| Draft fallback? | `answer` = `draft`; coverage `answer_from_draft` | recorded either way; `draft` means the conclude replies failed |

Also note `cut` (guided replies cut at max_tokens), `timeouts` (`model_timeout`: a conclude reply past the 600 s
proxy timeout), `longest guided s`, `max prompt`, `max masked`, and `budget` in config.json (steps 60,
tokens 2000000). Compare with `tests/M1-real/c3-on-1` (same concept and seed, prompt v1: 28 steps, no answer).

If `refused` > 0 (the server refused `structured_outputs`): run once more with `--conclude-decoding guided_json`
and run id `fix-on-2`. If that one is not refused, add `"conclude_decoding": "guided_json"` to
`agent/manifests/e2e-smoke.json` and `m4-72.json` in one commit (the plan names this switch; it is not a
prompt or budget change) before step 4. If both are refused, record it and go on with free decoding (the loop
falls back by itself).

Row `E2E-agent-fix`: the measure line, the three answers, verify and replay results. A run with `answer=none`
is a failure to record, not a reason to stop: the batch in step 4 is the real test.

## 2. Concepts for the 12 questions (row 2.3)

```bash
srun --jobid "$JOB" --overlap "$E2E/in-job.sh" scripts/e2e-concepts.sh 2>&1 | tee "$E2E/logs/2-concepts.log"
```

Expect, at the end, 12 status lines and `PASS 12 picked`, then `== done: the picks are in .../concepts/picks.json`.
A question that failed is listed (`needs action: q..`); run the script again, which retries only those; if it
fails on its briefs again, retry with another seed:
`srun --jobid "$JOB" --overlap "$E2E/in-job.sh" env E2E_CONCEPT_SEED=2 scripts/e2e-concepts.sh`. After two
seeds, record the question as failed and go on (q01 and q10 are the ones later steps need).

```bash
for q in concepts/q*/; do uv run agent concepts check "$q"; done      # 12 lines: PASS concepts/qNN concept.json sha256=...
du -sh concepts                                                       # expect well under 1 MB
git add concepts
git commit -m "2.3 Concept sessions of the 12 questions, provisional picks (brief 1)"
```

The commit body lists, per question, the number of briefs and the picked title (`uv run agent concepts status`).
Row `E2E-concepts`: questions picked, attempts and seeds used, briefs per question, failures.

## 3. Gold

### 3a. Trial on q01, 20 papers (out of `$GOLD`)

**(long)** — start it, then start step 4a at once (the batch uses the orchestrator, the trial the sub-models).

```bash
nohup srun --jobid "$JOB" --overlap "$E2E/in-job.sh" bash -c '
  uv run gold build q01 --max-papers 20 --out "$GOLD-trial"; echo "build exit $?"
  uv run gold triage q01 --out "$GOLD-trial"; echo "triage exit $?"
  uv run gold pool q01 --allow-partial --out "$GOLD-trial"; echo "pool exit $?"
  uv run gold draft q01 --allow-partial --out "$GOLD-trial"; echo "draft exit $?"
  uv run gold status --out "$GOLD-trial"' > "$E2E/logs/3a-trial.log" 2>&1 &
echo $! > "$E2E/logs/3a-trial.pid"
```

`gold build` exit codes: 0 D complete; 1 failed calls a rerun retries (run the same build once more); 3 only
failures a rerun cannot fix (record which: chunks too long, unreadable papers); 143 stopped (rerun resumes).
When it is done:

```bash
uv run python scripts/e2e-measure.py gold "$GOLD-trial" q01 --json "$E2E/measure/gold-trial.jsonl"
```

The judge's first real call, on the first anchored one-line candidate of the trial:

```bash
uv run python - "$GOLD-trial/q01/candidates.jsonl" > "$E2E/logs/3a-judge-input.txt" <<'PY'
import json, sys
for line in open(sys.argv[1], encoding="utf-8"):
    c = json.loads(line)
    if c["anchor_status"] == "ok" and "\n" not in c["quote"]:
        print(json.dumps({"s": c["s"], "p": c["p"], "o": c["o"]})); print(c["quote"]); break
PY
uv run gold judge "$(sed -n 1p "$E2E/logs/3a-judge-input.txt")" "$(sed -n 2p "$E2E/logs/3a-judge-input.txt")" --gold "$GOLD-trial"
```

Expect one JSON verdict with `label` `supports`, `partial` or `no`, a rationale, `model`, `prompt_sha256`.

What the trial must tell (row `E2E-gold-trial`): whether vLLM honoured the screening, extraction and triage
schemas (no `error` papers, `chunks_error` 0), papers relevant / not relevant, chunks, candidates, the anchor
ok share and rejection reasons, rows, triage split answers/context/irrelevant, pool size, draft facts, calls
made, input tokens and seconds, and the served model name (`served`). From these: **seconds per paper** and
the extrapolated full build per question (seconds × papers_in_corpus / 20).

### 3b. Full builds of q01 and q10 (the smoke questions) into `$GOLD`

Decide from the trial: if the extrapolated full build of one question is over 8 hours, build q01 only. If the
trial failed (no candidates, schema refused), skip 3b and record why.

**(long)**, at the same time as step 4a:

```bash
nohup srun --jobid "$JOB" --overlap "$E2E/in-job.sh" bash -c '
  for q in q01 q10; do
    uv run gold build $q; echo "build $q exit $?"
    uv run gold triage $q; echo "triage $q exit $?"
    uv run gold pool $q; echo "pool $q exit $?"
    uv run gold draft $q; echo "draft $q exit $?"
  done
  uv run gold status' > "$E2E/logs/3b-gold.log" 2>&1 &
echo $! > "$E2E/logs/3b-gold.pid"
```

A build that exits 1 is run again (once) before its triage; pool and draft refuse a partial D, which is
correct: record it. `gold status` while it runs shows progress (`dead` / `stale` mean it stopped). Then:

```bash
uv run python scripts/e2e-measure.py gold "$GOLD" q01 q10 --json "$E2E/measure/gold.jsonl"
```

Row `E2E-gold-full`: per question the same numbers as the trial, plus wall time. Note that a file in
`$GOLD/q01` freezes q01's pick only for this session's `$GOLD`; the thesis gold directory stays empty.

## 4. The e2e smoke batch (rows 2.9, 2.10, 2.13)

### 4a. Batch: q01 and q10, claim_on, two repeats (4 runs)

**(long)**

```bash
nohup srun --jobid "$JOB" --overlap "$E2E/in-job.sh" scripts/e2e-batch.sh agent/manifests/e2e-smoke.json \
  > "$E2E/logs/4a-batch.log" 2>&1 &
echo $! > "$E2E/logs/4a-batch.pid"
```

Expect in the log: `PASS 2 questions x 1 conditions x 2 repeats, sandbox landlock, ...`, `== job <id> ends <time>`
(if this line is missing, the deadline was not found: record it; the batch then runs without one), the four
runs, `== agent batch exit 0`, the status lines `q01-claim_on-r1 seed=<n>:
q01-claim_on-r1-a1=finished` (four keys: q01 and q10, repeats r1 and r2), per finished run `verify, pairs, timeline, graph, export-prov`
with `PASS` lines, and last `RUNS_ROOT=.../runs/e2e-smoke`. Batch exit 2 = out of time, 1 = a run gave up
after its attempts: record and continue with the runs that finished.

Then in the job shell, per finished run (`uv run agent batch "$SMOKE/manifest.json" --status` lists them):

```bash
for R in "$SMOKE"/q*-a*/; do
  id=$(basename "$R")
  uv run agent verify "$R" --corpus "$CORPUS" > "$E2E/verify/$id.txt" 2>&1; echo "$id verify exit $?"
  { uv run agent query 1 "$R" --edge edge-000001
    uv run agent query 2 "$R" --claim claim-000001
    uv run agent query 3 "$R" --agent main
    uv run agent query 4 "$R" --corpus "$CORPUS" --manifest "$CORPUS/manifest.json"
    uv run agent query 5 "$R"; } > "$E2E/logs/4a-queries-$id.log" 2>&1; echo "$id queries exit $?"
done
uv run python scripts/e2e-measure.py runs "$SMOKE"/q*-a* --json "$E2E/measure/smoke.jsonl"
```

Read three accepted quotes per
run against their paper (`uv run agent query 1 "$R" --edge edge-00000N` shows the passage) and write one line
each: does the quote support the fact? (B5: also note any rejected claim and its reason.)

Row `E2E-smoke <run id>`, one per run: the measure line, verify result, queries 1–5 ok or not, the quote checks.

### 4b. Replay of every run, re-execution of one

```bash
srun --jobid "$JOB" --overlap "$E2E/in-job.sh" scripts/e2e-replay.sh agent/manifests/e2e-smoke.json \
  2>&1 | tee "$E2E/logs/4b-replay.log"
```

Expect per run `PASS replay <id>: N/N model calls rebuilt from trajectory.json, M/M
outputs match`, the summary `<id> replay ok` per run and `PASS 4 runs`. Then re-execution of the q01 claim_on
run (its finished attempt, normally `-a1`) — it reruns every command, about as long as the run's commands took:

```bash
uv run agent reexec "$SMOKE/q01-claim_on-r1-a1" --corpus "$CORPUS" 2>&1 | tee "$E2E/logs/4b-reexec.log"; echo "exit $?"
```

Exit 0: every output and claim verdict as recorded; 1: some differ (the `DIFF step` / `DIFF claim` lines say
which; a measurement, not a failure); 2: it could not run (a failure). `WARN toolchain differs` means the agent
root is not the run's. Row `E2E-replay-reexec`: replay per run, reexec `identical/steps` and claims as recorded.

## 5. Scoring with the draft keys (provisional), and the store

```bash
uv run score batch "$SMOKE" --gold "$GOLD" --manifest "$SMOKE/manifest.json" --corpus "$CORPUS" 2>&1 | tee "$E2E/logs/5-score.log"
uv run score report "$SMOKE" 2>&1 | tee -a "$E2E/logs/5-score.log"
uv run score store "$SMOKE" --path "$SMOKE/.oxigraph" 2>&1 | tee -a "$E2E/logs/5-score.log"
printf 'SELECT (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } }\n' > "$E2E/count.rq"
uv run score sparql "$E2E/count.rq" --path "$SMOKE/.oxigraph"
```

Expect: `scored 4, reused 0, skipped 0, failed 0 (PROVISIONAL: draft keys used)` (a question without a key gives `no_key` for its runs: then
fewer scored; if 3b did not produce `$GOLD/q01/key.draft.json`, score once more with `--gold "$GOLD-trial"`
and say so: a 20-paper key, meaningful only as a path test); `report` prints `primary: not computed (...)`
(fewer than 6 paired questions), `PROVISIONAL: ...`, `JUDGE NOT CALIBRATED: ...`, then
`wrote .../report/report.json, report.md and CSV tables`; `store` prints `4 runs with graph.ttl, 4 (re)loaded`;
`sparql` prints `{"vars": ["n"], "rows": [...]}` with a count above 0. The report's paired claim_on/claim_off
sections are empty (no claim_off runs): expected, not a failure.

Row `E2E-score`: per run support share, fact F1 (strict / normalised / soft), row F1, unsourced share,
pending judge decisions, judge calls and errors (`score.json` `judge`), the report's warnings; all marked
provisional. Read `report/report.md` once: does every number have a source?

## 6. Web app on the node

**(long)** — RUNS is the batch root, so the app shows the smoke runs and their report:

```bash
nohup srun --jobid "$JOB" --overlap "$E2E/in-job.sh" env RUNS="$E2E/runs/e2e-smoke" \
  uv run webapp serve --host 127.0.0.1 --port 8080 > "$E2E/logs/6-webapp.log" 2>&1 &
echo $! > "$E2E/logs/6-webapp.pid"
grep -m1 "Uvicorn running" "$E2E/logs/6-webapp.log"     # repeat until it appears
```

Then in the job shell (the app answers only on the node's 127.0.0.1):

```bash
A=http://127.0.0.1:8080
ON=q01-claim_on-r1-a1; ON2=q01-claim_on-r2-a1                        # the finished attempts
F=$(uv run python -c 'import json,sys; a=json.load(open(sys.argv[1])); print(a["rows"][0]["facts"][0]["id"])' "$SMOKE/$ON/answer.json")
for p in /api/health /api/config /api/questions /api/questions/q01 /api/runs "/api/runs/$ON" "/api/runs/$ON/steps" \
         "/api/runs/$ON/steps/1/output" "/api/runs/$ON/claims" "/api/runs/$ON/graph" "/api/runs/$ON/score" \
         "/api/runs/$ON/facts/$F/walk" "/api/runs/$ON2/claims" "/api/corpus/p1?start=100&end=140&context=200" \
         "/api/queries/5?run_id=$ON" /api/gold /api/gold/q01/key /api/results /api/jobs / "/runs/$ON"; do
  curl -sS -o /dev/null -w "%{http_code} $p\n" "$A$p"
done | tee "$E2E/logs/6-endpoints.log"
curl -sS "$A/api/health"; echo                                         # {"ok":true,"version":"0.2.0"}
curl -sS "$A/api/config"; echo                                         # runs_root = .../e2e-smoke, llm_key_set true
curl -sS -X POST -H 'Content-Type: application/json' "$A/api/sparql" \
  -d '{"query": "SELECT (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } }"}'; echo     # {"vars":["n"],"rows":[...]}
curl -sS -o /dev/null -w "%{http_code} DELETE refused\n" -X POST -H 'Content-Type: application/json' "$A/api/sparql" \
  -d '{"query": "DELETE WHERE { ?s ?p ?o }"}'                          # 400
curl -sS -N --max-time 15 "$A/api/runs/$ON/stream" | head -n 3         # id: 1 / event: record / data: {...}
```

Expect 200 for every path (`/api/runs/$ON/score` 404 only if step 5 did not score it; `/api/gold/q01/key` 404
without a key; `/steps/1/output` 404 if step 1 ran no command). Open three of the bodies (run detail, claims,
walk) and check they hold what the run's files say. Then the chat, with the real model (`sub-model-1`), scoped to the run:

```bash
time curl -sS -N --max-time 600 -X POST -H 'Content-Type: application/json' "$A/api/chat?run_id=$ON" \
  -d '{"trigger": "submit-message", "id": "chat-1", "messages": [{"id": "m1", "role": "user", "parts": [{"type": "text", "text": "How many claims did this run record, how many were accepted, and which paper does the first accepted claim quote?"}]}]}' \
  > "$E2E/logs/6-chat.txt"
grep -o '"type": *"[a-z-]*"' "$E2E/logs/6-chat.txt" | uniq -c; tail -n 1 "$E2E/logs/6-chat.txt"
```

Expect frame types `start`, `tool-input-available` and `tool-output-available` (a tool call, e.g. `get_claims`),
`text-delta`s, `finish`, and the last line `data: [DONE]`. Read the text: is the answer right against
`agent verify`'s claim counts? Record the time.

**USER**: give the user the tunnel command and leave the app running for them:
`ssh -L 8080:127.0.0.1:8080 <user>@<node>` (node: `squeue -j $JOB -h -o %N`; add `-J <login node>` if needed),
then http://127.0.0.1:8080. Row `E2E-webapp`: endpoint codes, chat result and time.

## 7. Argilla on Omen (only with the tunnel and the key)

**USER**: this step needs Argilla running on Omen (`gold/argilla/compose.yaml`), the laptop side of the tunnel
(`omen-tunnels laptop start argilla`), and the owner's API key in a file only you can read, for example
`~/.argilla.env` (mode 600) with one line `ARGILLA_API_KEY=...`. If any is missing, record `NOT RUN (USER)`.

In the job shell, with `G=$GOLD` if `$GOLD/q01/pool.jsonl` exists, else `G=$GOLD-trial`:

```bash
scripts/omen-tunnels compute start argilla                     # ARGILLA_API_URL defaults to http://127.0.0.1:36900
set -a; source ~/.argilla.env; set +a
uv run gold push q01 --gold "$G" --name gold-e2etest 2>&1 | tee "$E2E/logs/7-argilla.log"
uv run gold screening-sample q01 --gold "$G" 2>&1 | tee -a "$E2E/logs/7-argilla.log"
uv run gold screening-push q01 --gold "$G" --name gold-e2etest 2>&1 | tee -a "$E2E/logs/7-argilla.log"
uv run gold pull --gold "$G" --name gold-e2etest 2>&1 | tee -a "$E2E/logs/7-argilla.log"
```

Always `--name gold-e2etest`: test records must never meet the real review's datasets (`gold-v1-*`). Do **not**
run `gold export` here: with nothing reviewed it would write a `key.json` that replaces the draft key for
scoring and the web app. Expect the datasets `gold-e2etest-review`, `-overlap`, `-missing`, `-screening` in
workspace `thesis`, the pool's records pushed (count in the log), and the pull writing `review/*.jsonl` with no
responses. Row `E2E-argilla`: records pushed per dataset, push and pull time, any record not pushed and why.
Tell the user the test datasets exist, to delete them after looking.

## 8. Measurements and the proposed budget

```bash
uv run python scripts/e2e-measure.py runs "$RUNS/agent-fix"/fix-on-* "$SMOKE"/q*-a* \
  --json "$E2E/measure/runs.jsonl" | tee "$E2E/measure/runs.md"
uv run python scripts/e2e-measure.py gold "$GOLD-trial" q01 --json "$E2E/measure/gold-trial.jsonl" | tee "$E2E/measure/gold-trial.md"
uv run python scripts/e2e-measure.py gold "$GOLD" q01 q10 --json "$E2E/measure/gold.jsonl" | tee "$E2E/measure/gold.md"
```

Per run (`runs.md`): steps, model calls, tokens and seconds, exit status,
answer source, rows and facts, claims accepted/rejected (`rejected_by_reason` in the JSON), largest prompt,
most outputs masked, guided answer yes/no, guided calls refused / timed out / cut, longest guided call,
unparsed replies. (The attach and subagent columns stay empty.)
Per gold D (`gold*.md`): papers, relevant papers, chunks, relevant chunks, candidates, anchor ok share,
rows, triage split answers/context/irrelevant, pool, draft facts, calls, input tokens, seconds.

Then propose, for the user to freeze (**USER**), each with the measured number it rests on:

| Setting | Now (provisional) | Rests on |
|---|---|---|
| Run budget, steps / tokens | 60 / 2,000,000 | where each run's answer came (submitted before the budget, or at the budget through the conclude replies), steps and tokens used, largest prompt against 61,440 |
| Conclude decoding | `structured_outputs` | refused, cut and timed-out guided calls; longest guided call against the 600 s proxy timeout |
| Time of the 36 main runs | — | 36 × mean seconds of the claim_on runs (12 questions × 3 repeats), in 48-hour jobs (minus ~15 min stack start each) |
| Gold for 12 questions | — | seconds and calls per full build (3b, else the trial × papers_in_corpus / 20) × 12 |

## Finish

1. `tests/RESULTS.md`: one row per step, ids `E2E-setup`, `E2E-agent-fix`, `E2E-concepts`, `E2E-gold-trial`,
   `E2E-gold-full`, `E2E-smoke <run id>` (one per run), `E2E-replay-reexec`, `E2E-score`,
   `E2E-webapp`, `E2E-argilla`; date, config (job id, node, commit), PASS / PARTIAL / FAIL / NOT RUN, the numbers,
   notes with the paths on Ceph.
2. Copy into `tests/E2E/` only these (each under 1 MB; a larger one stays on Ceph, give its path in the row):
   - `runs/<run id>/`: `config.json`, `answer.json`, `pairs.jsonl`, `timeline.html`,
     `replay.json`, `reexec.json` (the one run), `score.json`, and `verify.txt` (from `$E2E/verify/`);
   - `gold/<trial|full>/<qid>/`: `doc.md`, `key.draft.json`, `pool.strata.json`, `progress.json`;
   - `report/`: `report.json`, `report.md`, `batch.json`, `*.csv` from `$SMOKE/report/`;
   - `measure/` (all of `$E2E/measure`), `logs/` (the step logs), and `failures.md`.

   Before `git add tests/E2E`:
   `find tests/E2E -size +1M` must print nothing, and
   `grep -rlF -f <(printf '%s\n' "$LITELLM_MASTER_KEY") tests/E2E` must print nothing (the same for
   `$ARGILLA_API_KEY` if set). Never add `$E2E/in-job.env`.
3. `docs/STATE.md`: in Decided add the first real result to the rows "Main loop", "Concepts, attach, batch",
   "Questions and picks", "Re-execution and replay", "Gold D", "Judge", "Scoring and report",
   "Web app" (one clause each, with the number that matters); in Numbers add the gold call rate (seconds and
   calls per paper), the longest conclude reply; in Open keep "Run budget" with the
   proposed numbers (the user freezes them) and update "Concept picks" (12 provisional picks committed) and
   "Gold and judge"; rewrite the "Later" paragraph for what is still open. In `docs/milestones-1-2.md` set the
   2.10 progress row (done or what failed); in `docs/milestones-3-4.md` mark each "Still needs the cluster"
   item with its result.
4. Commit on `e2e-cluster` (results, copies and docs; separate from the fix commits), then
   `git push -u origin e2e-cluster`.
5. **USER**: ask whether the user still wants to use the web app through the tunnel. When they are done (or
   said beforehand they will not look), `scancel "$JOB"`; this also stops the web app and anything else still
   running in the job.
6. Report: pass / fail per step with the number that matters, the measurement tables, the proposed budget
   table, every fix commit (one line each), every failure from `failures.md`, the open **USER** steps
   (budget freeze, confirming or changing the 12 picks, deleting the `gold-e2etest` datasets), and anything
   that surprised you.
