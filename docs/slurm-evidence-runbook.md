# Runbook: the evidence-level system on Slurm, first live run

The evidence-level system (`evidence/`, `synth/`, `evaluation/`; formats in `docs/evidence-interfaces.md`) is
built and tested only offline, with scripted models (1052 passed, 1 skipped on `main`). This session runs it
against the real models for the first time: an LLM-written synthetic corpus, the engine with the LLM
extractors and the agentic extractor, replay and re-execution, both baselines, and the scores.

**Failures are expected.** When a step fails, record it and go on with the next step that does not depend on
it. The point is that every part meets the real models once and the first numbers exist.

## Rules

- Branch `evidence-cluster`, made from `origin/main`. Never push `main`; push `evidence-cluster` at the end.
- **Record every failure** in `$EV/failures.md`: step, exact command, exit code, last 30 lines of its log,
  what you did next (fixed in commit X / skipped / retried). Then continue with the next independent step.
- **Fixes** are allowed on `evidence-cluster`: one commit per fix, each with a test, and
  `uv run pytest <package>/tests -q` green for the package you changed. **Never** change, to make something
  pass: the protocols (`evidence/protocols/`), the extractor prompts (`evidence/extractors/prompts/`), the
  regex vocabularies (`evidence/extractors/terms.py`), the synthesis rules (`evidence/rules.py`,
  `evidence/synthesis.py`), the level definitions and fidelity checks (`synth/levels.py`, `synth/levelcheck.py`,
  `synth/fidelity.py`, `synth/assoc.py`), the renderer prompts (`synth/prompts/`), the scoring rules
  (`evaluation/score.py`), the agent's prompts and budgets (`agent/prompts/`, `agent/rundir.py`), the anchor
  rules (`agent/anchor.py`) or any threshold or tolerance. Record and continue. Do not change the `llm-setup`
  submodule.
- **Secrets.** `LITELLM_MASTER_KEY` is only read from the environment. Never print, `echo`, log or commit it;
  no `set -x`; never pass it on a command line; record only "set" / "not set".
- **Ceph, not git.** Corpora, runs, caches, scores and logs live under `$EV` on Ceph. Copy into the repo only
  the small files named under "Finish".
- Steps marked **USER** need the user: stop and ask; without an answer record `NOT RUN (USER)` and go on.
- Commit messages as in `git log`, ending with your usual attribution line.

## Paths and how commands run

| Name | Value |
|---|---|
| `REPO` | `/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent` (the clone of the earlier sessions) |
| `EV` | `/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-cluster` (new; everything this session writes) |
| `AGENT_ROOT` | `/mnt/ceph/storage/data-tmp/2026/xepi3167/agent-root-infra-final-3` (pinned agent toolchain) |
| `CORPORA` | `$EV/corpora` (synthetic corpora); `RUNS=$EV/runs`, `SCORES=$EV/scores`, `CACHE=$EV/cache` |
| `JOB` | the stack's Slurm job id (step 0.2) |

Commands run inside the stack job exactly as in `docs/slurm-e2e-runbook.md` ("Paths and how commands run"):
short ones in `srun --jobid "$JOB" --overlap --pty bash -l` after `source "$EV/in-job.env"`; steps marked
**(long)** from the login node with `nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" <command> >
"$EV/logs/<step>.log" 2>&1 &` and `echo $! > "$EV/logs/<step>.pid"`. Never start a long step from a `--pty`
shell.

## Models (provisional choices, recorded so the user can change them)

| Role | Alias | Why |
|---|---|---|
| Paper writer (synth `--model`) | `orch-model` (Qwen3.8-27B) | not the weights that extract, so the extractors do not read their own writing |
| Blind fidelity check (synth `--verify-model`) | `sub-model-2` | an independent re-reading |
| LLM extractors | `sub-model-1` (the protocol's default) | as in the protocol; never override with `--model` here |
| Agentic extractor, agent baseline, RAG baseline | `orch-model` (their defaults) | the agent's model; the RAG baseline uses the same model as the agent so the two baselines compare like with like |

GPU use: `orch-model` is GPU 0, the sub-models GPUs 1–2. Steps on different models may run in parallel (the
dependency table says which); never two `orch-model` steps at once.

## Order and dependencies

| Step | Uses | Needs | Time (not measured) |
|---|---|---|---|
| 0 setup, stack, offline smoke | CPU | — | 1 h |
| 1 LLM corpora (20 studies; 5-study set for the agent) | orch-model, sub-model-2 | 0 | hours |
| 2 template corpora, same seed | CPU | 0 | minutes |
| 3 engine regex-only and cascade on every corpus | sub-model-1 | 1, 2 | hours |
| 4 replay all, re-execution of two runs | CPU, sub-model-1 | 3 | 1 h |
| 5 agentic protocol on the 5-study set | orch-model, sub-model-1 | 1 | hours |
| 6 baselines (RAG, agent) on the LLM corpora | orch-model | 1, and not while 1 or 5 uses orch-model | hours |
| 7 scores and comparison | CPU | 3–6 | 30 min |
| 8 fidelity hand check (**USER**) | — | 1 | the user's time |

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

Expect `1052 passed, 1 skipped` (WSL count; the skip is the "Landlock missing" test, so on a node with
Landlock the split may differ by one). A failure here: record it; fix only clear test-environment
differences.

### 0.2 Stack (login node)

Start the stack exactly as `docs/slurm-e2e-runbook.md` step 0.2 (`profiles/agent-3x40.yaml`), wait until
`orch`, `sub-1` and `sub-2` are ready, `export JOB=<id>`.

### 0.3 Session environment (login node)

```bash
export EV=/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-cluster
mkdir -p "$EV/logs" "$EV/corpora" "$EV/runs" "$EV/scores" "$EV/cache" "$EV/agent-work"
cat > "$EV/in-job.env" <<EOF
# The evidence session's environment (docs/slurm-evidence-runbook.md). Paths only: the key comes from llm-setup/.env.
set -a; source $PWD/llm-setup/.env; set +a
unset UV_PROJECT_ENVIRONMENT VIRTUAL_ENV
export REPO=$PWD EV=$EV JOB=$JOB
export AGENT_ROOT=/mnt/ceph/storage/data-tmp/2026/xepi3167/agent-root-infra-final-3
export CORPORA=$EV/corpora RUNS=$EV/runs SCORES=$EV/scores CACHE=$EV/cache
export EVIDENCE_AGENT_WORK_DIR=$EV/agent-work      # the agentic extractor keeps its agent runs here
export LITELLM_BASE_URL=http://127.0.0.1:4000/v1
export P=evidence/protocols/rag-factuality.yaml PA=evidence/protocols/rag-factuality-agentic.yaml
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
for L in explicit distributed; do
  uv run evidence run --protocol $P --corpus synth/examples/rag-demo-$L --out $RUNS/smoke \
    --cache $CACHE/smoke --extractors regex-only --run-id smoke-$L
  uv run evidence replay $RUNS/smoke/smoke-$L | grep '"ok"'        # expect "ok": true
done
```

Row `EV-setup`: commit, pytest count, doctor result, job id, node, the two `"ok"` lines.

## 1. LLM-written corpora **(long)**

The main set (20 studies, all five levels plus mixed) and a small set for the agentic extractor (5 studies):

```bash
nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" uv run synth build --name rag-llm-s1 --seed 1 --studies 20 \
  --renderer llm --levels all --model orch-model --verify-model sub-model-2 --out "$CORPORA" \
  --cache "$EV/cache/synth-llm.jsonl" > "$EV/logs/1-synth-main.log" 2>&1 &
echo $! > "$EV/logs/1-synth-main.pid"
```

When it has finished (never both at once on `orch-model`):

```bash
nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" uv run synth build --name rag-llm-small --seed 2 --studies 5 \
  --renderer llm --levels paraphrased,distributed --model orch-model --verify-model sub-model-2 --out "$CORPORA" \
  --cache "$EV/cache/synth-llm.jsonl" > "$EV/logs/1-synth-small.log" 2>&1 &
```

The command prints a JSON summary and a WARNING line if studies were excluded. Row `EV-synth`: per level the
papers kept, studies excluded (with the failing checks from `fidelity.json`), attempts per paper (mean, max),
model calls and seconds (log), and the corpus ids. If more than a quarter of the studies are excluded, record
it and **USER** (the level instructions may be too hard for the writer); still continue with what was kept.

## 2. Template corpora, same seed (CPU)

```bash
uv run synth build --name rag-tpl-s1 --seed 1 --studies 20 --renderer template --levels all --out "$CORPORA"
```

Same studies as step 1, written by the template: the difference between the two shows what LLM writing adds.

## 3. Engine on every corpus **(long)**

```bash
cat > "$EV/engine.sh" <<'EOF'
#!/usr/bin/env bash
# regex-only and the cascade (regex, then the LLM extractor) on every 20-study corpus.
set -u
for C in "$CORPORA"/rag-llm-s1-* "$CORPORA"/rag-tpl-s1-*; do
  N=$(basename "$C")
  for S in regex-only cascade; do
    uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/$S" --cache "$CACHE/engine" \
      --extractors "$S" --run-id "$N" || echo "FAIL engine $S $N"
  done
done
EOF
chmod +x "$EV/engine.sh"
nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" "$EV/engine.sh" > "$EV/logs/3-engine.log" 2>&1 &
```

Each run prints its label and counts. Row `EV-engine`: per corpus and selection the label, the counts
(supporting / contradicting / neutral / undetermined), model calls, tokens and seconds (`run.json` `cost`),
rejected items by reason (from `calls/*.json`), and every `FAIL` line.

## 4. Replay and re-execution

```bash
for R in "$RUNS"/regex-only/rag-* "$RUNS"/cascade/rag-*; do
  case "$R" in *-replay-*|*-reexec-*) continue;; esac
  uv run evidence replay "$R" | grep -q '"ok": true' && echo "OK $R" || echo "MISMATCH $R"
  uv run evidence verify "$R" | grep -q '"ok": true' || echo "CHAIN $R"
done | tee "$EV/logs/4-replay.log"
uv run evidence reexec "$RUNS/cascade/rag-llm-s1-explicit" | tee "$EV/logs/4-reexec-explicit.log"
uv run evidence reexec "$RUNS/cascade/rag-llm-s1-distributed" | tee "$EV/logs/4-reexec-distributed.log"
```

Every replay must be `OK` and every chain verify clean; a `MISMATCH` is a defect (record, look at
`mismatched`, never "fix" it by rerunning). The re-execution makes new LLM calls (sub-model-1): row
`EV-replay` gets the OK count, and per extractor the re-execution summary (identical / same items, different
spans / items added / items missing / fields differ).

## 5. Agentic extractor on the small set **(long)**

```bash
cat > "$EV/agentic.sh" <<'EOF'
#!/usr/bin/env bash
set -u
for C in "$CORPORA"/rag-llm-small-paraphrased "$CORPORA"/rag-llm-small-distributed; do
  N=$(basename "$C")
  uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/cascade" --cache "$CACHE/engine" \
    --extractors cascade --run-id "$N" || echo "FAIL cascade $N"
  uv run evidence run --protocol "$PA" --corpus "$C" --out "$RUNS/agentic" --cache "$CACHE/engine" \
    --extractors cascade --run-id "$N" || echo "FAIL agentic $N"
done
EOF
chmod +x "$EV/agentic.sh"
nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" "$EV/agentic.sh" > "$EV/logs/5-agentic.log" 2>&1 &
```

Up to 5 papers × 4 evidence types = 20 agent runs per corpus (budget 30 steps / 600,000 tokens each); the
agent's own run directories are kept under `$EV/agent-work`. Then replay both agentic runs (must be `OK`,
with no model running: replay never calls one) and `evidence reexec` one of them. Row `EV-agentic`: per corpus
the agentic calls (ok / partial / error, with reasons), the agent's steps and tokens per call, items it alone
found (the score's cascade contribution, step 7), replay result, re-execution summary.

## 6. Baselines on the LLM corpora **(long; orch-model, not while 1 or 5 runs)**

```bash
cat > "$EV/baselines.sh" <<'EOF'
#!/usr/bin/env bash
set -u
for C in "$CORPORA"/rag-llm-s1-* "$CORPORA"/rag-llm-small-*; do
  N=$(basename "$C")
  uv run evaluate rag-baseline --corpus "$C" --out "$RUNS/rag-baseline/$N" --cache "$CACHE/rag-baseline.jsonl" \
    || echo "FAIL rag $N"
  uv run evaluate agent-baseline --corpus "$C" --out "$RUNS/agent-baseline/$N" --cache "$CACHE/agent-baseline.jsonl" \
    --agent-root "$AGENT_ROOT" --run-id "$N" || echo "FAIL agent $N"
done
EOF
chmod +x "$EV/baselines.sh"
nohup srun --jobid "$JOB" --overlap "$EV/in-job.sh" "$EV/baselines.sh" > "$EV/logs/6-baselines.log" 2>&1 &
```

The RAG baseline runs with its defaults (top 2 BM25 passages per paper). If time allows, also once with
`--retrieval global` on `rag-llm-s1-mixed` into `$RUNS/rag-baseline-global/` (the plain top-8 form). Row
`EV-baselines`: per corpus the label, studies with a stance, the agent's exit status, steps, tokens, seconds.

## 7. Scores and comparison (CPU)

```bash
for R in "$RUNS"/cascade/rag-* "$RUNS"/regex-only/rag-* "$RUNS"/agentic/rag-*; do
  case "$R" in *-replay-*|*-reexec-*) continue;; esac
  N=$(basename "$R"); S=$(basename "$(dirname "$R")")
  B=(); for b in "$RUNS"/rag-baseline/$N/answer.json "$RUNS"/agent-baseline/$N/answer.json; do
    [ -f "$b" ] && B+=(--baseline "$b"); done
  uv run evaluate score --run "$R" --corpus "$CORPORA/$N" "${B[@]}" --out "$SCORES/$S/$N" || echo "FAIL score $S $N"
done
for S in cascade regex-only agentic; do
  uv run evaluate compare --out "$SCORES/compare-$S" "$SCORES/$S"/*
done
```

Row
`EV-scores`: the three `compare.md` tables, and per level for the cascade: extraction F1 per evidence type,
association accuracy, true pair, direction accuracy, answered, label correct, for the engine and both
baselines; the template-vs-LLM difference per level; the cascade contribution (items only the LLM, only the
agent found).

## 8. Fidelity hand check (**USER**)

```bash
uv run synth sample --corpus "$CORPORA/rag-llm-s1-mixed" --n 30 --seed 1
```

Tell the user where the review sheet is (`review/review-s1.md` and `.csv` in that corpus); the hand check is
theirs. Record `NOT RUN (USER)` until they report.

## Finish

1. `tests/RESULTS.md`: rows `EV-setup`, `EV-synth`, `EV-engine`, `EV-replay`, `EV-agentic`, `EV-baselines`,
   `EV-scores`, `EV-fidelity`; date, job id, node, commit, PASS / PARTIAL / FAIL / NOT RUN, the numbers, notes
   with the Ceph paths.
2. Copy into `tests/EV1/` only (each under 1 MB; larger stays on Ceph, path in the row): per corpus
   `corpus.json`, `fidelity.json`, `ground_truth.json`; per run `run.json`, `answer.json`, `locate.json`; per
   score `report.json`, `report.md`; the `compare-*` directories; `reexec.json` files; the baselines'
   `answer.json`; `logs/` and `failures.md`. Not the papers, not caches, not `in-job.env`. Before `git add`:
   `find tests/EV1 -size +1M` prints nothing and
   `grep -rlF -f <(printf '%s\n' "$LITELLM_MASTER_KEY") tests/EV1` prints nothing.
3. `docs/STATE.md`: under the evidence-level note add one line per row with the number that matters.
4. Commit on `evidence-cluster` (results separate from fix commits), `git push -u origin evidence-cluster`.
5. `scancel "$JOB"` when everything has finished (**USER** first if they want to look at anything live).
6. Report: pass / fail per step with the number that matters, the `compare-cascade` table, every fix commit
   (one line each), every failure from `failures.md`, the open **USER** steps, and anything surprising.
