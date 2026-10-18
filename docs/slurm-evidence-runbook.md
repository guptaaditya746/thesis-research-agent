# Runbook: the evidence-level system on Slurm, first live run

The evidence-level system (`evidence/`, `synth/`, `evaluation/`; formats in `docs/evidence-system.md`) is
built and tested only offline, with scripted models (1250 passed, 1 skipped on `main`). This session runs it
against the real models for the first time: LLM-written synthetic corpora (the five levels, the benchmark
knobs, a counterfactual variant), the engine in both strategies (`all`, `gaps`) with the LLM extractors and
the agentic extractor, replay and re-execution, both baselines, the scores with intervals, the shift of the
variant, the benchmark records per extractor, and a dry run of the proposal flow.

**Failures are expected.** When a step fails, record it and go on with the next step that does not depend on
it. The point is that every part meets the real models once and the first numbers exist.

## Rules

- Branch `evidence-cluster`, made from `origin/main`. Never push `main`; push `evidence-cluster` at the end.
- **Record every failure** in `$EV/failures.md`: step, exact command, exit code, last 30 lines of its log,
  what you did next (fixed in commit X / skipped / retried). Then continue with the next independent step.
- **Fixes** are allowed on `evidence-cluster`: one commit per fix, each with a test, and
  `uv run pytest <package>/tests -q` green for the package you changed. **Never** change, to make something
  pass: the protocols (`evidence/protocols/`), the extractor prompts (`evidence/extractors/prompts/`), the
  regex vocabularies (`evidence/extractors/terms.py`), the synthesis machinery (`evidence/rules.py`,
  `evidence/synthesis.py`; its parameters are in the protocols), the funnel (`evidence/engine.py`'s screen
  and completeness decisions, `evidence/extractors/screen.py`), the proposal flow's prompts, cards and
  vocabulary (`evidence/propose/prompts/`, `evidence/propose/cards.yaml`, `evidence/vocab/`), the level
  definitions, knobs and fidelity checks (`synth/levels.py`, `synth/levelcheck.py`, `synth/truth.py`,
  `synth/variant.py`, `synth/fidelity.py`, `synth/assoc.py`), the renderer prompts (`synth/prompts/`), the
  scoring rules (`evaluation/score.py`, `evaluation/stats.py`, `evaluation/shift.py`,
  `evaluation/benchmark.py`), the baselines' prompts and retrieval (`evaluation/baselines/`), the agent's
  prompts and budgets (`agent/prompts/`, `agent/rundir.py`), the anchor rules (`agent/anchor.py`) or any
  threshold or tolerance. Record and continue. Do not change the `llm-setup` submodule.
- **No system under test reads the ground truth.** `ground_truth.json`, `corpus.json`, `fidelity.json`,
  `decoys.json` and `variant.json` are read only by `evaluate score`, `evaluate shift`, `evaluate benchmark`
  and by you when you pick the variant's study (step 1.4). Never pass any of them, or anything derived from
  them, to `evidence run`, `evidence propose`, `evaluate rag-baseline` or `evaluate agent-baseline`, and never
  copy one into a corpus's `papers/`.
- **One model.** Every extractor (LLM and agentic), both baselines and the proposal flow run on `orch-model`
  (the default of `evidence run --model`, of the `llm` extractors, of `AgentSettings.model`, of `evaluate …
  --model` and of `evidence propose … --model`), so a comparison isolates the method, not the weights (16 Oct
  decision; `docs/evidence-system.md` Part G.3). Never pass another `--model` to the engine, the baselines or
  the proposal flow; the only other aliases in this runbook are the paper writer (`sub-model-1`) and the
  blind check (`sub-model-2`), so the extractors never read their own writing.
- **Secrets.** `LITELLM_MASTER_KEY` is only read from the environment. Never print, `echo`, log or commit it;
  no `set -x`; never pass it on a command line; record only "set" / "not set".
- **Ceph, not git.** Corpora, runs, caches, proposals, scores and logs live under `$EV` on Ceph. Copy into the
  repo only the small files named under "Finish".
- Steps marked **USER** need the user: stop and ask; without an answer record `NOT RUN (USER)` and go on.
- Commit messages as in `git log`, ending with your usual attribution line.

## Paths and how commands run

| Name | Value |
|---|---|
| `REPO` | `/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent` (the clone of the earlier sessions) |
| `EV` | `/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-cluster` (new; everything this session writes) |
| `AGENT_ROOT` | `/mnt/ceph/storage/data-tmp/2026/xepi3167/agent-root-infra-final-3` (pinned agent toolchain) |
| `CORPORA` | `$EV/corpora` (synthetic corpora); `RUNS=$EV/runs`, `SCORES=$EV/scores`, `CACHE=$EV/cache`, `PR=$EV/proposals/rag-factuality` |
| `JOB` | the stack's Slurm job id (step 0.2) |

Commands run inside the stack job:
short ones in `srun --jobid "$JOB" --overlap --pty bash -l` after `source "$EV/in-job.env"`; steps marked
**(long)** from the login node with `nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" <command> >
"$EV/logs/<step>.log" 2>&1 &` and `echo $! > "$EV/logs/<step>.pid"`. Never start a long step from a `--pty`
shell.

Corpus names (all under `$CORPORA`; `<level>` is `explicit`, `paraphrased`, `distributed`, `complex`,
`contradictory` or `mixed`):

| Name | What | Step |
|---|---|---|
| `rag-llm-s1-<level>` | seed 1, 20 studies, written by `sub-model-1` | 1.1 |
| `rag-llm-k1-<level>` | the same 20 studies plus the four knobs (2 duplicates, 2 missing, 2 outliers, 2 irrelevant papers) | 1.2 |
| `rag-llm-small-{paraphrased,distributed}` | seed 2, 5 studies, for the agentic extractor (the build writes `rag-llm-small-mixed` too; unused) | 1.3 |
| `rag-llm-s1-mixed-cf-<S>-contradicts` | the counterfactual variant: study `<S>` of `rag-llm-s1-mixed` flipped to contradicts | 1.4 |
| `rag-tpl-s1-<level>`, `rag-tpl-k1-<level>`, `rag-tpl-s1-mixed-cf-<S>-contradicts` | the same three, written by the template | 2 |

Only the `mixed` corpus of a knob build is run and scored (its papers cover every level; the per-level knob
corpora are written by the build anyway and stay unused).

## Models (the 16 Oct decision: one model for every extractor and both baselines)

| Role | Alias | Why |
|---|---|---|
| LLM extractors, LLM screen, agentic extractor, agent baseline, RAG baseline (answer and mapping calls), proposal flow (frame, critic, cards) | `orch-model` (Qwen3.8-27B, the default everywhere) | the same weights for every system under test, so a difference between the engine and the baselines, or between extractors, is the method's |
| Paper writer (synth `--model`, `build` and `variant`) | `sub-model-1` (Qwen3-30B-A3B) | other weights than the readers, so no extractor reads its own writing |
| Blind fidelity check (synth `--verify-model`) | `sub-model-2` | an independent re-reading, on the writer's weights but a separate replica |

GPU use: `orch-model` is GPU 0, the sub-models GPUs 1–2. Step 1 (sub-models) may run next to a CPU step and
next to step 9 (three short `orch-model` calls); steps 3, 4 (re-execution), 5 and 6 all use `orch-model`, so
they run one after the other, never two at once.

## Order and dependencies

| Step | Uses | Needs | Time (not measured) |
|---|---|---|---|
| 0 setup, stack, offline smoke | CPU | — | 1 h |
| 1 LLM corpora: main, knobs, small set, variant | sub-model-1, sub-model-2 | 0 (1.4 needs 1.1) | hours |
| 2 template corpora, same seed: main, knobs, variant | CPU | 0 (2.2 needs 1.4's study) | minutes |
| 9 proposal flow dry run | orch-model (3 calls) | 0; run it while step 1 builds | 15 min |
| 3 engine regex-only, cascade `all` and `gaps` on every corpus | orch-model | 1, 2 | hours |
| 4 replay all, re-execution of two runs | CPU, orch-model | 3, and not while 5 or 6 runs | 1 h |
| 5 agentic protocol, `all` and `gaps`, on the small set | orch-model | 1, and not while 3 or 6 runs | hours |
| 6 baselines (RAG, agent) on the LLM corpora | orch-model | 1, and not while 3, 4 or 5 runs | hours |
| 7 scores, comparisons, shift, benchmark records | CPU | 3–6 | 30 min |
| 8 fidelity hand check (**USER**) | — | 1 | the user's time |
| 10 proposal review (**USER**) | — | 9 | the user's time |

## 0. Setup

### 0.1 Checkout and tests (login node)

```bash
cd /mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent
git status --short                 # nothing tracked changed; otherwise USER
git fetch origin && git checkout -b evidence-cluster origin/main
git submodule update --init --recursive
uv sync --locked --all-groups
uv run pytest -q -W ignore::SyntaxWarning 2>&1 | tail -n 3
```

Expect `1250 passed, 1 skipped` (WSL count; the skip is the "Landlock missing" test, so on a node with
Landlock the split may differ by one). A failure here: record it; fix only clear test-environment
differences.

### 0.2 Stack (login node)

```bash
cd llm-setup && LLM_SETUP_PROFILE=profiles/agent-3x40.yaml sbatch slurm/llm-stack.sbatch; cd ..
export JOB=<the job id sbatch printed>
tail -n 20 llm-setup/runtime/slurm-$JOB.out      # repeat until orch, sub-1 and sub-2 say ready (~11 min)
```

### 0.3 Session environment (login node)

```bash
export EV=/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-cluster
mkdir -p "$EV/logs" "$EV/corpora" "$EV/runs" "$EV/scores" "$EV/cache" "$EV/agent-work" "$EV/proposals"
cat > "$EV/in-job.env" <<EOF
# The evidence session's environment (docs/slurm-evidence-runbook.md). Paths only: the key comes from llm-setup/.env.
set -a; source $PWD/llm-setup/.env; set +a
unset UV_PROJECT_ENVIRONMENT VIRTUAL_ENV
export REPO=$PWD EV=$EV JOB=$JOB
export AGENT_ROOT=/mnt/ceph/storage/data-tmp/2026/xepi3167/agent-root-infra-final-3
export CORPORA=$EV/corpora RUNS=$EV/runs SCORES=$EV/scores CACHE=$EV/cache PR=$EV/proposals/rag-factuality
export EVIDENCE_AGENT_WORK_DIR=$EV/agent-work      # the agentic extractor keeps its agent runs here
export LITELLM_BASE_URL=http://127.0.0.1:4000/v1
export P=evidence/protocols/rag-factuality.yaml PA=evidence/protocols/rag-factuality-agentic.yaml
export Q="Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?"
cd $PWD
EOF
cat > "$EV/in-job.sh" <<'EOF'
#!/usr/bin/env bash
source "$(dirname "$0")/in-job.env"
exec "$@"
EOF
chmod +x "$EV/in-job.sh"
source "$EV/in-job.env"
```

In every new shell: `export EV=...` (as above) and `source "$EV/in-job.env"`.

### 0.4 Environment check and offline smoke (in the job)

```bash
srun --jobid "$JOB" --overlap bash -lc 'cd llm-setup && set -a && source .env && set +a && uv run llm-setup doctor --profile profiles/agent-3x40.yaml' 2>&1 | tail -n 5
test -f "$AGENT_ROOT/agent-root.sha256" && echo "AGENT_ROOT ok"
uv run evidence protocol check $P | head -n 6           # id rag-factuality, version 2, its sha256
uv run evidence protocol check $PA | head -n 6
for L in explicit distributed; do
  uv run evidence run --protocol $P --corpus synth/examples/rag-demo-$L --out $RUNS/smoke \
    --cache $CACHE/smoke --extractors regex-only --run-id smoke-$L
  uv run evidence replay $RUNS/smoke/smoke-$L | grep '"ok"'        # expect "ok": true
done
```

Row `EV-setup`: commit, pytest count, doctor result, job id, node, both protocols' sha256, the two `"ok"`
lines.

## 1. LLM-written corpora **(long)**

### 1.1 Main set (20 studies, all five levels plus mixed)

```bash
nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" uv run synth build --name rag-llm-s1 --seed 1 --studies 20 \
  --renderer llm --levels all --model sub-model-1 --verify-model sub-model-2 --out "$CORPORA" \
  --cache "$EV/cache/synth-llm.jsonl" > "$EV/logs/1-synth-main.log" 2>&1 &
echo $! > "$EV/logs/1-synth-main.pid"
```

### 1.2 Knob set (the same studies plus duplicates, missing values, outliers, irrelevant papers)

When 1.1 has finished (one build at a time on the sub-models):

```bash
nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" uv run synth build --name rag-llm-k1 --seed 1 --studies 20 \
  --renderer llm --levels all --duplicates 2 --missing 2 --outliers 2 --irrelevant 2 \
  --model sub-model-1 --verify-model sub-model-2 --out "$CORPORA" \
  --cache "$EV/cache/synth-llm.jsonl" > "$EV/logs/1-synth-knobs.log" 2>&1 &
echo $! > "$EV/logs/1-synth-knobs.pid"
```

The knobs (`docs/evidence-system.md` F2, `synth/README.md`) draw from their own random streams, so the
studies the knobs leave alone get the same rendering plan as in 1.1 and their papers should come from the
shared cache (expected, not measured: count the model calls in the log against 1.1's). New calls are the
duplicates and the studies an outlier or a missing value changed, at every level; the irrelevant papers make
no call. A `SystemExit` naming a knob (e.g. a natural large effect next to a planted one) is the generator
refusing: record it and build again once with that knob at 0, name unchanged.

### 1.3 Small set for the agentic extractor (5 studies)

When 1.2 has finished:

```bash
nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" uv run synth build --name rag-llm-small --seed 2 --studies 5 \
  --renderer llm --levels paraphrased,distributed --model sub-model-1 --verify-model sub-model-2 --out "$CORPORA" \
  --cache "$EV/cache/synth-llm.jsonl" > "$EV/logs/1-synth-small.log" 2>&1 &
echo $! > "$EV/logs/1-synth-small.pid"
```

### 1.4 Counterfactual variant (one paper, in the job shell)

The supervisor's controlled variant (§6; `docs/evidence-system.md` F3): flip one supporting study of the
mixed corpus to `contradicts` and re-render only its paper. You pick the study from the ground truth (you
are the experimenter, not a system under test): the first study in `answer.supporting`.

```bash
S=$(uv run python -c 'import json, sys; print(json.load(open(sys.argv[1]))["answer"]["supporting"][0])' \
  "$CORPORA/rag-llm-s1-mixed/ground_truth.json")
echo "$S" > "$EV/variant-study.txt"
uv run synth variant --corpus "$CORPORA/rag-llm-s1-mixed" --study "$S" --direction contradicts \
  --model sub-model-1 --verify-model sub-model-2 --cache "$EV/cache/synth-llm.jsonl" 2>&1 | tee "$EV/logs/1-variant.log"
```

It writes `$CORPORA/rag-llm-s1-mixed-cf-$S-contradicts` with `variant.json` (the renderer is the base
corpus's, `llm`). A fidelity failure of the re-rendered paper is an error: record it, then try once with the
next study of `answer.supporting` (`[1]`), and use that study in 2.2 too.

The papers are written by `sub-model-1` and read by `orch-model` (steps 3, 5, 6, 9), different weights.

Every build prints a JSON summary and a WARNING line if studies were excluded. Row `EV-synth`: per build
and level the papers kept, studies excluded (with the failing checks from `fidelity.json`), attempts per
paper (mean, max), model calls and seconds (log), and the corpus ids; for the knob set the planted
duplicates, missing, outliers and irrelevant papers (`ground_truth.json` `answer.duplicates`,
`answer.undetermined`, `answer.flags`); for the variant the study, `changed` and `expected` from
`variant.json` (label before and after, `label_changes`). If more than a quarter of the studies of a build
are excluded, record it and **USER** (the level instructions may be too hard for the writer); still continue
with what was kept.

## 2. Template corpora, same seed (CPU)

### 2.1 Main and knob sets

```bash
uv run synth build --name rag-tpl-s1 --seed 1 --studies 20 --renderer template --levels all --out "$CORPORA"
uv run synth build --name rag-tpl-k1 --seed 1 --studies 20 --renderer template --levels all \
  --duplicates 2 --missing 2 --outliers 2 --irrelevant 2 --out "$CORPORA"
```

Same studies as step 1, written by the template: the difference between the two shows what LLM writing adds.
(The LLM sets lack the studies fidelity excluded; the template sets keep all 20.)

### 2.2 The same variant (after 1.4)

```bash
uv run synth variant --corpus "$CORPORA/rag-tpl-s1-mixed" --study "$(cat "$EV/variant-study.txt")" --direction contradicts
```

## 3. Engine on every corpus **(long)**

```bash
cat > "$EV/engine.sh" <<'EOF'
#!/usr/bin/env bash
# regex-only and the cascade (regex, then the LLM extractor on orch-model) on every main-set corpus, the
# variants and the knob sets' mixed corpora, the cascade in both strategies: `all` (every extractor on every
# paper, the screen recorded) and `gaps` (the funnel: screen, then escalate only the gaps;
# docs/evidence-system.md Part D).
set -u
for C in "$CORPORA"/rag-llm-s1-* "$CORPORA"/rag-tpl-s1-* "$CORPORA"/rag-llm-k1-mixed "$CORPORA"/rag-tpl-k1-mixed; do
  N=$(basename "$C")
  uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/regex-only" --cache "$CACHE/engine" \
    --extractors regex-only --model orch-model --run-id "$N" || echo "FAIL engine regex-only $N"
  uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/cascade" --cache "$CACHE/engine" \
    --extractors cascade --strategy all --model orch-model --run-id "$N" || echo "FAIL engine cascade $N"
  uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/cascade-gaps" --cache "$CACHE/engine" \
    --extractors cascade --strategy gaps --model orch-model --run-id "$N" || echo "FAIL engine cascade-gaps $N"
done
EOF
chmod +x "$EV/engine.sh"
nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" "$EV/engine.sh" > "$EV/logs/3-engine.log" 2>&1 &
echo $! > "$EV/logs/3-engine.pid"
```

The glob `rag-*-s1-*` takes the variants (`…-mixed-cf-…`) too. `--model orch-model` is the default, written
out so the record (`run.json` `settings.model`) is explicit; `--strategy all` is the default too. The `gaps`
run shares the record cache with the `all` run: a call whose task is byte for byte one the `all` run made
is a cache hit, which holds for the screen calls and for the position-0 calls of the types without context
(condition, metric); a position-0 call with context (measurement, author_claim) hits only when the merged
context items are the same, which in `all` they are not when a later position added items; a targeted call
(its task carries a `focus`) is always new. Each run prints its label and counts. Row `EV-engine`: per
corpus and selection (regex-only, cascade, cascade-gaps) the label, the counts (supporting / contradicting /
neutral / undetermined / duplicates), the flags (`answer.json` `flags`), model calls, tokens and seconds
(`run.json` `cost`), rejected items by reason (from `calls/*.json`), for `gaps` the stop positions and
screened-out papers (`funnel.json`; on the knob sets the irrelevant papers should be the screened-out ones),
and every `FAIL` line.

## 4. Replay and re-execution

```bash
for R in "$RUNS"/regex-only/rag-* "$RUNS"/cascade/rag-* "$RUNS"/cascade-gaps/rag-*; do
  case "$R" in *-replay-*|*-reexec-*) continue;; esac
  [ -f "$R/run.json" ] || continue
  uv run evidence replay "$R" | grep -q '"ok": true' && echo "OK $R" || echo "MISMATCH $R"
  uv run evidence verify "$R" | grep -q '"ok": true' || echo "CHAIN $R"
done | tee "$EV/logs/4-replay.log"
uv run evidence reexec "$RUNS/cascade/rag-llm-s1-explicit" | tee "$EV/logs/4-reexec-explicit.log"
uv run evidence reexec "$RUNS/cascade/rag-llm-s1-distributed" | tee "$EV/logs/4-reexec-distributed.log"
```

Every replay must be `OK` and every chain verify clean; a `MISMATCH` is a defect (record, look at
`mismatched`, never "fix" it by rerunning). The re-execution makes new LLM calls (orch-model) and writes
`<run>-reexec-<stamp>/reexec.json` beside the run (step 7 hands it to the score). Row `EV-replay` gets the
OK count, and per extractor the re-execution summary (identical / same items, different spans / items added
/ items missing / fields differ).

## 5. Agentic extractor on the small set **(long)**

```bash
cat > "$EV/agentic.sh" <<'EOF'
#!/usr/bin/env bash
set -u
for C in "$CORPORA"/rag-llm-small-paraphrased "$CORPORA"/rag-llm-small-distributed; do
  N=$(basename "$C")
  uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/cascade" --cache "$CACHE/engine" \
    --extractors cascade --strategy all --model orch-model --run-id "$N" || echo "FAIL cascade $N"
  uv run evidence run --protocol "$PA" --corpus "$C" --out "$RUNS/agentic" --cache "$CACHE/engine" \
    --extractors cascade --strategy all --model orch-model --run-id "$N" || echo "FAIL agentic $N"
  uv run evidence run --protocol "$PA" --corpus "$C" --out "$RUNS/agentic-gaps" --cache "$CACHE/engine" \
    --extractors cascade --strategy gaps --model orch-model --run-id "$N" || echo "FAIL agentic-gaps $N"
done
EOF
chmod +x "$EV/agentic.sh"
nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" "$EV/agentic.sh" > "$EV/logs/5-agentic.log" 2>&1 &
echo $! > "$EV/logs/5-agentic.pid"
```

The LLM extractors and the agent inside the agentic extractor both run on `orch-model` (`AgentSettings.model`).
In `all`, up to 5 papers × 4 evidence types = 20 agent runs per corpus (budget 30 steps / 600,000 tokens
each); in `gaps` the agent runs only for the gap types the regex and LLM steps left, with a targeted task
(`focus`). The agent's own run directories are kept under `$EV/agent-work`. Then replay the four agentic runs
(must be `OK`, with no model running: replay never calls one) and `evidence reexec` one of them:

```bash
for R in "$RUNS"/agentic/rag-* "$RUNS"/agentic-gaps/rag-*; do
  case "$R" in *-replay-*|*-reexec-*) continue;; esac
  [ -f "$R/run.json" ] || continue
  uv run evidence replay "$R" | grep -q '"ok": true' && echo "OK $R" || echo "MISMATCH $R"
done | tee "$EV/logs/5-replay.log"
uv run evidence reexec "$RUNS/agentic/rag-llm-small-distributed" --extractor agentic | tee "$EV/logs/5-reexec.log"
```

Row `EV-agentic`: per corpus and strategy the agentic calls (ok / partial / error, with reasons), the agent's
steps and tokens per call, items it alone found (the score's cascade contribution, step 7), in `gaps` the
agent calls against `all`, replay result, re-execution summary.

## 6. Baselines on the LLM corpora **(long; orch-model, not while 3, 4 or 5 runs)**

```bash
cat > "$EV/baselines.sh" <<'EOF'
#!/usr/bin/env bash
set -u
shopt -s nullglob
# The RAG baseline (one retrieval, one call) on every corpus first; then the agent baseline, the costly one,
# mixed corpora first, so a stopped job still leaves both baselines on the corpora the comparison leans on.
CS=("$CORPORA"/rag-llm-s1-mixed "$CORPORA"/rag-llm-k1-mixed "$CORPORA"/rag-llm-s1-mixed-cf-*)
for C in "$CORPORA"/rag-llm-s1-* "$CORPORA"/rag-llm-small-{paraphrased,distributed}; do
  [[ " ${CS[*]} " == *" $C "* ]] || CS+=("$C")
done
for C in "${CS[@]}"; do
  N=$(basename "$C")
  uv run evaluate rag-baseline --corpus "$C" --out "$RUNS/rag-baseline/$N" --cache "$CACHE/rag-baseline.jsonl" \
    --model orch-model --retrieval global --k 8 || echo "FAIL rag $N"
done
for C in "${CS[@]}"; do
  N=$(basename "$C")
  uv run evaluate agent-baseline --corpus "$C" --out "$RUNS/agent-baseline/$N" --cache "$CACHE/agent-baseline.jsonl" \
    --model orch-model --agent-root "$AGENT_ROOT" --run-id "$N" || echo "FAIL agent $N"
done
EOF
chmod +x "$EV/baselines.sh"
nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" "$EV/baselines.sh" > "$EV/logs/6-baselines.log" 2>&1 &
echo $! > "$EV/logs/6-baselines.pid"
```

The RAG baseline is the plain retrieve-then-answer system (`docs/evidence-system.md` Part G.1): the top 8
BM25 passages of the whole corpus (`--retrieval global --k 8`, the defaults, written out), one answering
call under the neutral prompt (answer text and citations as `[paper id, start-end]`), then the mapping call
shared with the agent baseline (label and per-paper stances for score C; it reads the answer text and the
kept citations' headers, never the passages). `--model orch-model` (the default, written out) is the model
of both calls and of the agent baseline's agent. The glob `rag-llm-s1-*` takes the variant too, so step 7
can score the baselines' shift. If time allows, also once with `--retrieval per_paper` ("every paper seen":
the top 2 passages of every paper) on `rag-llm-s1-mixed` into `$RUNS/rag-baseline-per-paper/`. Row
`EV-baselines`: per corpus the label, studies with a stance, citations kept and dropped (`answer.json`
`citations`, `dropped_citations`), the passages retrieved per paper (`retrieved`), the agent's exit status,
steps, tokens, seconds.

## 7. Scores, comparisons, shift, benchmark records (CPU)

### 7.1 Scores

```bash
for R in "$RUNS"/{regex-only,cascade,cascade-gaps,agentic,agentic-gaps}/rag-*; do
  case "$R" in *-replay-*|*-reexec-*) continue;; esac
  [ -f "$R/answer.json" ] || continue                  # a selection that did not run leaves the glob as is
  N=$(basename "$R"); S=$(basename "$(dirname "$R")")
  B=(); for b in "$RUNS"/rag-baseline/$N/answer.json "$RUNS"/agent-baseline/$N/answer.json; do
    [ -f "$b" ] && B+=(--baseline "$b"); done
  X=$(ls -d "$R"-reexec-*/reexec.json 2>/dev/null | tail -n 1); [ -n "$X" ] && B+=(--reexec "$X")
  uv run evaluate score --run "$R" --corpus "$CORPORA/$N" "${B[@]}" --out "$SCORES/$S/$N" || echo "FAIL score $S $N"
done 2>&1 | tee "$EV/logs/7-score.log"
```

Every `report.json` carries 95 % BCa bootstrap intervals (`intervals`: extraction F1 per evidence type,
direction accuracy per system, the paired engine-minus-baseline difference; F4), shown as `0.812 [0.74,
0.88]` in `report.md` and `compare.md`; a degenerate sample gives the point value with empty bounds. The knob
corpora add flag precision and recall, `counts_correct` and `duplicates_correct`; the `gaps` runs add the
funnel section (calls per document, stop positions, screen precision and recall).

### 7.2 Comparisons

```bash
for S in regex-only cascade cascade-gaps agentic agentic-gaps; do
  [ -d "$SCORES/$S" ] && uv run evaluate compare --out "$SCORES/compare-$S" "$SCORES/$S"/*
done
for N in $(ls "$SCORES/cascade-gaps"); do   # all against gaps, one corpus per table (Part D)
  uv run evaluate compare --out "$SCORES/compare-funnel/$N" "$SCORES/cascade/$N" "$SCORES/cascade-gaps/$N"
done
for N in $(ls "$SCORES/agentic-gaps" 2>/dev/null); do
  uv run evaluate compare --out "$SCORES/compare-funnel-agentic/$N" "$SCORES/agentic/$N" "$SCORES/agentic-gaps/$N"
done
```

`compare-funnel` shows, per corpus, calls and tokens per document and the screen's precision and recall next
to the accuracies (`compare.md` columns `strategy`, `calls_per_document`, `tokens_per_document`,
`screen_precision`, `screen_recall`). Both reports carry the same baseline answers, so a corpus's baseline rows
appear twice in a `compare-funnel` table, identical; read them once.

### 7.3 Shift of the variant

```bash
for V in "$CORPORA"/rag-*-s1-mixed-cf-*; do
  N=$(basename "$V"); BASE=${N%%-cf-*}
  for S in regex-only cascade cascade-gaps; do
    uv run evaluate shift --base "$SCORES/$S/$BASE" --variant "$SCORES/$S/$N" --variant-json "$V/variant.json" \
      --out "$SCORES/shift-$S/$N" || echo "FAIL shift $S $N"
  done
done 2>&1 | tee "$EV/logs/7-shift.log"
```

Per system in both reports (the engine and, on the LLM variant, both baselines) the changed study's direction
before and after against `from`/`to`, the label before and after against `expected`, and
`shifted_as_expected` (`shift.json`, `shift.md`).

### 7.4 Benchmark records per extractor (B11)

```bash
L="explicit paraphrased distributed complex contradictory"
for W in llm tpl; do
  R=(); for d in $(for l in $L; do echo "$SCORES/cascade/rag-$W-s1-$l"; done) "$SCORES"/agentic/rag-$W-small-*; do
    [ -f "$d/report.json" ] && R+=("$d"); done
  uv run evaluate benchmark "${R[@]}" --out "$SCORES/benchmark-$W" || echo "FAIL benchmark $W"
done 2>&1 | tee "$EV/logs/7-benchmark.log"
```

Only `all` runs (in `gaps` an extractor is not called on every paper), only the per-level corpora (a mixed
corpus repeats their papers byte for byte, the knob sets and the variant repeat their studies), and not the
`regex-only` runs (the cascade runs hold the regex extractors already; both would count the same calls
twice). The agentic runs add the seed-2 papers and the agentic extractor. Template and LLM writing stay in
separate records because their levels share names. Stability comes from the reports scored with a
`reexec.json` (7.1).

Row `EV-scores`: the `compare-cascade`, `compare-cascade-gaps`, `compare-regex-only` and `compare-agentic`
tables, and per level for the cascade: extraction F1 per evidence type (with interval), association accuracy,
true pair, direction accuracy (with interval), completeness, accuracy over the answered studies,
traceability (baselines only), label correct, the paired engine-minus-baseline difference with interval, for
the engine and both baselines; the template-vs-LLM difference per level; the cascade contribution (items only
the LLM, only the agent found); on the knob sets flag precision and recall per flag, `counts_correct`,
`duplicates_correct`. Row `EV-funnel`: per corpus from `compare-funnel` (and `compare-funnel-agentic`) the
calls and tokens per document in `all` and `gaps`, the accuracies of both, the stop-position histogram and
the screen's precision and recall. Row `EV-shift`: per variant and selection `shifted_as_expected` per
system. Row `EV-benchmark`: per extractor id of `benchmark-llm/benchmark.md` the F1 per type and level, span
accuracy, cost per call and stability.

## 8. Fidelity hand check (**USER**)

```bash
uv run synth sample --corpus "$CORPORA/rag-llm-s1-mixed" --n 30 --seed 1
```

Tell the user where the review sheet is (`review/review-s1.md` and `.csv` in that corpus); the hand check is
theirs. Record `NOT RUN (USER)` until they report.

## 9. Proposal flow dry run (orch-model, three calls; while step 1 builds)

The proposal flow (`docs/evidence-system.md` Part E) has run only on a scripted model. This runs it once on
`orch-model` for the RAG question with the committed vocabulary snapshot, every decision left at the model's
default (`by: model`), and compares the frozen protocol with the hand-written one. **Nothing runs the
proposed protocol**: no `evidence run --protocol "$PR/protocol.yaml"`, now or later in this session.

```bash
uv run evidence propose frame --question "$Q" --vocab evidence/vocab/rag-factuality.json --out "$PR" \
  --model orch-model 2>&1 | tee "$EV/logs/9-propose.log"
uv run evidence propose draft "$PR" 2>&1 | tee -a "$EV/logs/9-propose.log"
uv run evidence propose critic "$PR" --model orch-model 2>&1 | tee -a "$EV/logs/9-propose.log"
uv run evidence propose cards "$PR" --model orch-model 2>&1 | tee -a "$EV/logs/9-propose.log"
uv run evidence propose freeze "$PR" 2>&1 | tee -a "$EV/logs/9-propose.log"
uv run evidence protocol check "$PR/protocol.yaml" > "$PR/protocol-check.json"; echo "check exit $?"
diff -u "$P" "$PR/protocol.yaml" > "$PR/protocol.diff"; echo "diff exit $?"     # 1 = they differ (expected)
# What the scripted test compares (evidence/propose/compare.py): both protocols parsed, without id, revision,
# descriptions, the screening question and the bm25 query lists; screen terms as a set.
uv run python -m evidence.propose.compare "$P" "$PR/protocol.yaml" > "$PR/protocol-compare.json"
```

`frame`, `critic` and `cards` make one model call each (cached in `$PR/cache.jsonl`); `draft` and `freeze` are
deterministic. Do **not** edit `frame.json` or `decisions.yaml`: the dry run freezes the model's defaults.
A refusal (exit 2) is recorded with its message and the flow stops there (e.g. freeze refusing a failed
`regex_matches_enums`); a failed model call (exit 1) may be retried once; a cached reply the step cannot use
names `--refresh`: rerun that step once with `--refresh`. Row `EV-propose-live`: per step the exit status,
`call.cached` and tokens if logged; from `frame.json` the roles, outcomes and each entry's source (ontology /
invented); `critic.json` `ok` and every failed deterministic check, and the four checklist answers; per card
of `cards.json` the model's default and whether it is `draft`; `proposal.json` `protocol.sha256`,
`run_settings` and `decided_by`; `protocol-compare.json` `equal` and every differing path; the size of
`protocol.diff` (lines).

## 10. Proposal review (**USER**)

Tell the user where the proposal is (`$PR`: `cards.json`, `decisions.yaml`, `critic.json`, `protocol.diff`,
`protocol-compare.json`) and ask, per card: would they keep the model's default, and if not, which option
and why. Record their answers in the `EV-propose-live` row. Do not edit `decisions.yaml` or freeze again:
the directory is frozen, and a different decision becomes a new proposal (or an `amend`) in a later session.
Record `NOT RUN (USER)` until they answer.

## Finish

1. `tests/RESULTS.md`: rows `EV-setup`, `EV-synth`, `EV-engine`, `EV-replay`, `EV-agentic`, `EV-baselines`,
   `EV-scores`, `EV-funnel`, `EV-shift`, `EV-benchmark`, `EV-fidelity`, `EV-propose-live`; date, job id, node,
   commit, PASS / PARTIAL / FAIL / NOT RUN, the numbers, notes with the Ceph paths.
2. Copy into `tests/EV1/` only (each under 1 MB; larger stays on Ceph, path in the row): per corpus
   `corpus.json`, `fidelity.json`, `ground_truth.json`, and for the variants `variant.json`; per run
   `run.json`, `answer.json`, `locate.json`, and for `gaps` runs `funnel.json`; per score `report.json`,
   `report.md`; the `compare-*`, `shift-*` and `benchmark-*` directories; `reexec.json` files; the baselines'
   `answer.json`; from `$PR` every file (`frame.json`, `draft.yaml`, `draft.sources.json`, `critic.json`,
   `cards.json`, `decisions.yaml`, `protocol.yaml`, `protocol.v1.yaml`, `proposal.json`, `written.json`,
   `cache.jsonl`, `protocol-check.json`, `protocol.diff`, `protocol-compare.json`) into `tests/EV1/proposal/`;
   `variant-study.txt`, `logs/` and `failures.md`. Not the papers, not the caches under `$CACHE`, not
   `in-job.env`. Before `git add`: `find tests/EV1 -size +1M` prints nothing and
   `grep -rlF -f <(printf '%s\n' "$LITELLM_MASTER_KEY") tests/EV1` prints nothing.
3. `docs/STATE.md`: under §6 add one line per row with the number that matters.
4. Commit on `evidence-cluster` (results separate from fix commits), `git push -u origin evidence-cluster`.
5. `scancel "$JOB"` when everything has finished (**USER** first if they want to look at anything live).
6. Report: pass / fail per step with the number that matters, the `compare-cascade` table, the
   `compare-funnel` numbers (calls per document `all` vs `gaps`, accuracies, screen precision and recall),
   `shifted_as_expected` per system, the frozen proposal's `protocol-compare.json` `equal` and its differing
   paths, every fix commit (one line each), every failure from `failures.md`, the open **USER** steps, and
   anything surprising.
