# Runbook: the evidence-level system on Slurm, second live run (EV2)

The evidence-level system (`evidence/`, `synth/`, `evaluation/`; formats in `docs/evidence-system.md`) is
tested offline with scripted models. EV1 (job 7488/7588, 18-21 Oct; `tests/EV1/`, `docs/ev1-review-diagnosis.md`)
ran it against the real models and found repairs to make; they are merged (plan
`docs/superpowers/plans/2026-10-21-ev1-repairs.md`). **This session, EV2, reruns the whole runbook on the repaired
code** and adds: a 3-study pilot build before the full LLM build (with render-v2 and atomic statements, the new
default of LLM builds), a second cascade arm with `screen.lexical_miss: escalate`, oracle diagnostics (engine
synthesis on the true facts, RAG on the true passages), a larger and harder template benchmark, the fidelity
sample summary, and the proposal flow with its blocking checks and `review.status`. Everything else is the EV1
procedure: LLM-written synthetic corpora (the five levels, the benchmark knobs, a counterfactual variant), the
engine in both strategies (`all`, `gaps`) with the LLM extractors and the agentic extractor, replay and
re-execution, both baselines, the scores with intervals, the shift of the variant, the benchmark records per
extractor, and a dry run of the proposal flow.

**Failures are expected.** When a step fails, record it and go on with the next step that does not depend on
it. The point is that every part meets the real models once and the first numbers exist.

## Rules

- Branch `evidence-ev2b`, made from `origin/ev3/claude-writer` (the EV1 repairs, the 21 Oct review fixes and the
  frozen EV2 corpora). Never push `main`; push `evidence-ev2b` at the end. Leave the earlier `evidence-ev2` as it
  is and bring over only its results: `git checkout origin/evidence-ev2 -- tests/EV2/logs tests/EV2/failures.md
  tests/EV2/ui-case tests/EV2/diagnostics tests/EV2/pilot-corpora docs/claude-ev2-handoff.md`. Its experimental
  `synth/` code stays on that branch.
- **Record every failure** in `$EV/failures.md`: step, exact command, exit code, last 30 lines of its log,
  what you did next (fixed in commit X / skipped / retried). Then continue with the next independent step.
- **Fixes** are allowed on `evidence-ev2`: one commit per fix, each with a test, and
  `uv run pytest <package>/tests -q` green for the package you changed. **Never** change, to make something
  pass: the protocols (`evidence/protocols/`), the extractor prompts (`evidence/extractors/prompts/`), the
  regex vocabularies (`evidence/extractors/terms.py`), the synthesis machinery (`evidence/rules.py`,
  `evidence/synthesis.py`; its parameters are in the protocols), the funnel (`evidence/engine.py`'s screen
  and completeness decisions, `evidence/extractors/screen.py`), the proposal flow's prompts and cards
  (`evidence/propose/prompts/`, `evidence/propose/cards.yaml`), the level
  definitions, knobs and fidelity checks (`synth/levels.py`, `synth/levelcheck.py`, `synth/truth.py`,
  `synth/variant.py`, `synth/fidelity.py`, `synth/assoc.py`), the renderer prompts (`synth/prompts/`), the
  scoring rules (`evaluation/score.py`, `evaluation/stats.py`, `evaluation/shift.py`,
  `evaluation/benchmark.py`), the baselines' prompts and retrieval (`evaluation/baselines/`), the agent's
  prompts and budgets (`agent/prompts/`, `agent/rundir.py`), the anchor rules (`agent/anchor.py`) or any
  threshold or tolerance. Record and continue. Do not change the `llm-setup` submodule.
- **No system under test reads the ground truth.** `ground_truth.json`, `corpus.json`, `fidelity.json`,
  `decoys.json` and `variant.json` are read only by `evaluate score`, `evaluate shift`, `evaluate benchmark`
  and by the laptop build that picked the variant's study (S001, the first of `answer.supporting`). Never pass any of them, or anything derived from
  them, to `evidence run`, `evidence propose`, `evaluate rag-baseline` (without `--oracle-passages`) or
  `evaluate agent-baseline`, and never copy one into a corpus's `papers/`. The exceptions are the **oracle
  diagnostics** (step 6.2): `evaluate oracle` and `evaluate rag-baseline --oracle-passages` read
  `ground_truth.json` on purpose; they are not systems under test, write only under `$RUNS/oracle*`, and are
  labelled "oracle" in every table. The corpus's **`selection`** (requested / retained studies, failed checks
  per level, excluded studies) is in `corpus.json`, never in `manifest.json`.
- **One model.** Every extractor (LLM and agentic), both baselines and the proposal flow run on `orch-model`
  (the default of `evidence run --model`, of the `llm` extractors, of `AgentSettings.model`, of `evaluate …
  --model` and of `evidence propose … --model`), so a comparison isolates the method, not the weights (16 Oct
  decision; `docs/evidence-system.md` Part G.3). Never pass another `--model` to the engine, the baselines or
  the proposal flow. The papers were written on the laptop by other models (Claude Haiku, checked by Claude
  Sonnet), so no extractor reads its own writing.
- **Secrets.** `LITELLM_MASTER_KEY` is only read from the environment. Never print, `echo`, log or commit it;
  no `set -x`; never pass it on a command line; record only "set" / "not set".
- **Ceph, not git.** Runs, caches, proposals, scores and logs live under `$EV` on Ceph. Copy into the repo only
  the small files named under "Finish". The corpora are the exception: they come from git (`tests/EV2/corpora/`).
- Steps marked **USER** need the user: stop and ask; without an answer record `NOT RUN (USER)` and go on.
- Commit messages as in `git log`, ending with your usual attribution line.

## Paths and how commands run

| Name | Value |
|---|---|
| `REPO` | `/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent` (the clone of the earlier sessions) |
| `EV` | `/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-ev2` (new, so no EV1 corpus or cache is reused; everything this session writes) |
| `AGENT_ROOT` | `/mnt/ceph/storage/data-tmp/2026/xepi3167/agent-root-infra-final-3` (pinned agent toolchain) |
| `CORPORA` | `$EV/corpora` (a copy of the frozen `tests/EV2/corpora/`, step 1–2); `RUNS=$EV/runs`, `SCORES=$EV/scores`, `CACHE=$EV/cache`, `PR=$EV/proposals/rag-factuality`; `PE` = the escalate protocol (step 0.6) |
| `JOB` | the stack's Slurm job id (step 0.2) |

Commands run inside the stack job:
short ones in `srun --jobid "$JOB" --overlap --pty bash -l` after `source "$EV/in-job.env"`; steps marked
**(long)** from the login node with the launch helper `$EV/launch.sh` (written in step 0.3):
`nohup "$EV/launch.sh" <step> <command> > /dev/null 2>&1 &` and `echo $! > "$EV/logs/<step>.pid"`. It runs
`srun --jobid "$JOB" --overlap "$EV/in-job.sh" <command>` with the output in `$EV/logs/<step>.log`. In EV1
concurrent `nohup srun --jobid … --overlap` launches failed before the command started ("srun: error: unable to
initialize step request socket: Address already in use" / "Unable to create step for job …"; `tests/EV1/failures.md`,
`tests/EV1/live-rerun/logs/*initial-srun-failure.log`), and a plain retry recovered. The helper retries exactly
that case: when the step fails and the first lines of the log name "step request socket: Address
already in use", it keeps that log as `<step>.log.srun-failure-<n>`, waits 20–40 s (jittered) and tries again, at most 3
retries, then exits non-zero; its own lines go to `$EV/logs/<step>.launch`. Any other failure is the command's
and is not retried. Never start a long step from a `--pty` shell. **Start long steps one at a time**: before
launching the next, wait until the previous step's log has its first line, or until `squeue --steps -j "$JOB"`
lists its step (some commands print nothing for minutes). A step-creation failure after the retries is a
failure to record (Rules), then launch that step again by hand once.

Corpus names (all under `$CORPORA`; `<level>` is `explicit`, `paraphrased`, `distributed`, `complex`,
`contradictory` or `mixed`):

| Name | What | Step |
|---|---|---|
| `rag-claude-pilot-<level>` | seed 1, 3 studies (the pilot; not run) | laptop |
| `rag-claude-s1-<level>` | seed 1, 20 studies; written by Claude Haiku subagents (render-v2 plus atomic statements), blind check by Claude Sonnet | laptop |
| `rag-claude-k1-<level>` | the same 20 studies plus the four knobs (2 duplicates, 2 missing, 2 outliers, 2 irrelevant papers) | laptop |
| `rag-claude-small-{paraphrased,distributed}` | seed 2, 5 studies, for the agentic extractor (`rag-claude-small-mixed` exists too; unused) | laptop |
| `rag-claude-s1-mixed-cf-S001-contradicts` | the counterfactual variant: study S001 of `rag-claude-s1-mixed` flipped to contradicts | laptop |
| `rag-tpl-s1-<level>`, `rag-tpl-k1-<level>`, `rag-tpl-s1-mixed-cf-S001-contradicts` | the same three, written by the template | laptop |
| `rag-tpl-hard-<level>` | template only, seed 1, 100 studies, `--hard` plus 6 duplicates, 6 missing, 6 outliers, 6 irrelevant; run and scored on `complex` and `mixed` | laptop |

`$CF_LLM` and `$CF_TPL` below are the two variant corpus directories (`$EV/cf-llm.txt`, `$EV/cf-tpl.txt` hold them).
Only the `mixed` corpus of a knob build is run and scored (its papers cover every level; the per-level knob
corpora are written by the build anyway and stay unused).

## Models (the 16 Oct decision: one model for every extractor and both baselines)

| Role | Alias | Why |
|---|---|---|
| LLM extractors, LLM screen, agentic extractor, agent baseline, RAG baseline (answer and mapping calls), proposal flow (frame, critic, cards) | `orch-model` (Qwen3.8-27B, the default everywhere) | the same weights for every system under test, so a difference between the engine and the baselines, or between extractors, is the method's |
| Paper writer and blind check | none on Slurm: Claude Haiku and Claude Sonnet subagents on the laptop (`docs/claude-writer.md`) | other weights than the readers, so no extractor reads its own writing |

GPU use: the stack serves only `orch-model`, on all three GPUs. The profile `orch-3x40` (llm-setup `22dae03`) runs
three replicas of the same pinned weights behind the one alias, and the gateway sends each call to the least busy
replica. The model identity and the cache keys are those of `agent-3x40`'s orch. The sub-models are gone.

**Up to three long `orch-model` steps may run at once**: step 3, step 5 and step 6, one of each. Each uses its own
cache: `$CACHE/engine`, `$CACHE/engine-agentic`, and the baselines' own files. Two processes must never append to
the same cache file. Step 4's re-execution and step 6.1's RAG oracle also use `orch-model`: start them only when
fewer than three long steps run, and step 4 only after step 3 has finished, because it uses `$CACHE/engine`. The
priority order under step 1–2 says what to start first.

## Order and dependencies

| Step | Uses | Needs | Time (not measured) |
|---|---|---|---|
| 0 setup, stack, offline smoke | CPU | — | 1 h |
| 1–2 copy the frozen corpora from git, check the manifests | CPU | 0 | minutes |
| 9 proposal flow dry run | orch-model (3 calls) | 0; between two long steps | 15 min |
| 3 engine regex-only, cascade `all` and `gaps` (and `gaps` with `escalate`) on every corpus | orch-model | 1–2 | hours |
| 4 replay all, re-execution of two runs | CPU, orch-model | 3 finished | 1 h |
| 5 agentic protocol, `all` and `gaps`, on the small set | orch-model (own cache) | 1–2; may run beside 3 and 6 | hours |
| 6 baselines (RAG, agent) on the LLM corpora and the hard set; oracle diagnostics | orch-model (CPU for the engine oracle) | 1–2; may run beside 3 and 5 | hours |
| 7 scores, comparisons, shift, benchmark records | CPU | 3–6 | 30 min |
| 8 fidelity hand check (**USER**), then its summary | — | 1 | the user's time |
| 10 proposal review (**USER**) | — | 9 | the user's time |

## 0. Setup

### 0.1 Checkout and tests (login node)

```bash
cd /mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent
git status --short                 # nothing tracked changed; otherwise USER
git fetch origin && git checkout -b evidence-ev2b origin/ev3/claude-writer
git submodule update --init --recursive
uv sync --locked --all-groups
uv run pytest -q -W ignore::SyntaxWarning 2>&1 | tail -n 3
```

Linux on `evidence-ev2b` (22 Oct): **1545 passed, 1 skipped**, exit 0, in 2169.22 seconds. One Pydantic
deprecation warning was emitted by `argilla`; see `tests/EV2/logs/0.1-pytest.log`. The integration branch gives
808 passed, 20 skipped on Windows (plus 3 known Windows-only failures) with the offline packages only; the
platform-specific counts differ. The skip is the "Landlock missing" test.

The web app's recorded write contract `webapp/web/src/mocks/write-contract.json` had one sha256 patched by hand
on Windows. Regenerate it on Linux with `uv run python -m webapp.tests.write_contract` (default output is that
file) and check `uv run pytest webapp/tests -q -k recorded_contract` (that is `test_recorded_contract_is_current`);
commit the regenerated file as one fix commit if it differs.

### 0.2 Stack (login node)

The `llm-setup` submodule must be at commit `22dae03` (the orch-only profiles, on top of `fc842bc`'s job-scoped
`VLLM_PORT`): EV1's job 7599 died
at startup on a vLLM/PyTorch port collision (`torch.distributed` could not bind its rendezvous port,
`EADDRINUSE`; `tests/EV1/failures.md`), and that commit gives every job its own port block. Check it before
submitting; if `git log -1` does not show `22dae03`, run `git submodule update --init` (step 0.1) and check
again; if it still differs, **USER** (do not change the submodule yourself).
(The question-first session, `docs/runbook-question-first.md`, records `llm-setup` at `4c8ccbf`, which adds the
GLiNER service on top of `22dae03`; there its steps 0 and 1 replace this check and this stack start.)

```bash
git -C llm-setup log -1 --oneline                   # expect 22dae03 Add orch-only profiles …
cd llm-setup
JOB=$(LLM_SETUP_PROFILE=profiles/orch-3x40.yaml sbatch slurm/llm-stack.sbatch)
JOB=${JOB##* }
export JOB
cd ..
echo "Slurm job: $JOB"
tail -n 20 llm-setup/runtime/slurm-$JOB.out      # repeat until orch, orch-2 and orch-3 say ready
```

### 0.3 Session environment (login node)

```bash
export EV=/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-ev2
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
cat > "$EV/launch.sh" <<'EOF'
#!/usr/bin/env bash
# launch.sh <step> <command...>: run <command> in the stack job (srun --overlap, through in-job.sh) with its
# output in $EV/logs/<step>.log. Retries only when srun could not create the job step (EV1: "unable to
# initialize step request socket: Address already in use" / "Unable to create step for job"): it waits 20-40 s
# and tries again, at most 3 retries, then exits non-zero. Its own lines go to $EV/logs/<step>.launch.
set -u
source "$(dirname "$0")/in-job.env"
STEP=$1; shift
LOG="$EV/logs/$STEP.log"
for try in 1 2 3 4; do
  srun --jobid "$JOB" --overlap "$EV/in-job.sh" "$@" > "$LOG" 2>&1
  rc=$?
  if [ "$rc" -ne 0 ] && head -n 5 "$LOG" | grep -q 'step request socket: Address already in use'; then
    cp "$LOG" "$LOG.srun-failure-$try"
    if [ "$try" -lt 4 ]; then
      wait_s=$((20 + RANDOM % 21))
      echo "$(date -Is) $STEP: srun could not create the step (try $try, exit $rc); retrying in ${wait_s}s" >> "$EV/logs/$STEP.launch"
      sleep "$wait_s"
      continue
    fi
    echo "$(date -Is) $STEP: srun could not create the step after 3 retries (exit $rc)" >> "$EV/logs/$STEP.launch"
    exit 1
  fi
  echo "$(date -Is) $STEP: exit $rc (try $try)" >> "$EV/logs/$STEP.launch"
  exit "$rc"
done
EOF
chmod +x "$EV/launch.sh"
source "$EV/in-job.env"
```

In every new shell: `export EV=...` (as above) and `source "$EV/in-job.env"`. A long step's exit status is the
last line of `$EV/logs/<step>.launch`.

### 0.4 Environment check and offline smoke (in the job)

```bash
srun --jobid "$JOB" --overlap bash -lc 'cd llm-setup && set -a && source .env && set +a && uv run llm-setup doctor --profile profiles/orch-3x40.yaml' 2>&1 | tail -n 5
test -f "$AGENT_ROOT/agent-root.sha256" && echo "AGENT_ROOT ok"
uv run evidence protocol check $P | head -n 6           # id rag-factuality, version 2, its sha256
uv run evidence protocol check $PA | head -n 6
command -v jq >/dev/null && echo "jq ok"              # step 1–2 does not need it any more; without it use uv run python -c 'import json,sys; print(json.load(sys.stdin)["out"])'
for L in explicit distributed; do
  uv run evidence run --protocol $P --corpus synth/examples/rag-demo-$L --out $RUNS/smoke \
    --cache $CACHE/smoke --extractors regex-only --run-id smoke-$L
  uv run evidence replay $RUNS/smoke/smoke-$L | grep '"ok"'        # expect "ok": true
done
```

Row `EV-setup`: commit, pytest count, doctor result, job id, node, both protocols' sha256, the two `"ok"`
lines.

### 0.5 Live check after the 20 Oct architecture change (in the job, before step 3; once)

Extractor ids hash their source files, several of which moved or changed, so the engine's record cache misses
once: the next cascade, LLM-extractor or agentic run makes its model calls again (GPU hours). The callers' own
caches (baselines, propose, judge, gold, synth) keep their keys and still hit. The Recorder no longer opens a
fresh event loop per call. At pydantic-ai 2.55 that bug was not live in engine runs (the engine's default
provider builds a fresh model and HTTP client per call); the change guards a shared-model setup.
It runs on the committed offline example corpus `synth/examples/rag-demo-mixed`, so it needs nothing from step 1 and
costs little before the long steps start.

```bash
C=synth/examples/rag-demo-mixed                      # committed offline corpus; the LLM corpora do not exist yet
L="$EV/live-check"                                   # outside $RUNS, so the web app does not list it as a run group
uv run evaluate rag-baseline --corpus "$C" --out "$L/rag1" --cache "$CACHE/live-check-rag.jsonl" \
  --model orch-model --retrieval global --k 8
wc -l < "$CACHE/live-check-rag.jsonl"                # n1: one line per model call made; record it
uv run evaluate rag-baseline --corpus "$C" --out "$L/rag2" --cache "$CACHE/live-check-rag.jsonl" \
  --model orch-model --retrieval global --k 8        # immediate rerun: every call a cache hit
wc -l < "$CACHE/live-check-rag.jsonl"                # expect n1 again: no line appended
cmp "$L/rag1/answer.json" "$L/rag2/answer.json" && echo "answers identical"   # expect "answers identical"
uv run evidence run --protocol $P --corpus "$C" --out "$L" --cache "$CACHE/live-check" \
  --extractors cascade --strategy all --model orch-model --run-id cascade-check
grep -l "Event loop is closed" "$L"/cascade-check/calls/*.json    # expect no output
```

Row `EV-setup`, notes: no `Event loop is closed` in any `calls/*.json` error; the RAG cache's line count
after the second run equals the count after the first (n1, recorded) and `cmp` printed `answers identical`
(the rerun made no model call); the cascade run completed.

### 0.6 The escalate protocol (once)

The cascade runs twice (step 3): with `screen.lexical_miss: reject` (the default and EV1's behaviour: a regex
"not relevant" ends the cascade for that paper) and with `escalate` (the miss passes the paper on, the next
extractor in the screen decides; the record carries `escalated: true`). The second protocol is a copy with
that one line added; nothing else differs. This is a copy for the run, not a change of `evidence/protocols/`.

```bash
PE=$EV/rag-factuality-escalate.yaml
sed 's/^  on_fail: skip .*$/&\n  lexical_miss: escalate/' $P > "$PE"
diff $P "$PE"                                           # exactly one added line: "  lexical_miss: escalate"
uv run evidence protocol check "$PE" | head -n 6        # valid; a different sha256 than $P
grep -q '^export PE=' "$EV/in-job.env" || echo "export PE=$PE" >> "$EV/in-job.env"
```

## 1–2. Corpora: frozen in git, built on the laptop (no synth on Slurm)

**Decision of 21 Oct 2026 (user):** no synthetic paper is generated on Slurm. The cluster's writer (`sub-model-1`)
retained 0 of 3 pilot families (`docs/claude-ev2-handoff.md` on `evidence-ev2`). Every corpus was therefore built on the
laptop and committed under `tests/EV2/corpora/`:

- **LLM-written corpora** were written by Claude subagents through the exchange model: writer `exchange:claude-haiku-5-5`,
  blind verifier `exchange:claude-sonnet-5-5`. They use the same prompts, statement stage and fidelity checks as before
  (`docs/claude-writer.md`).
- **Template corpora** were built with the commands of the old step 2.

**Do not run `synth build` or `synth variant` here**, and never edit a file under `tests/EV2/corpora/`.

Copy the corpora to `$CORPORA` in the job shell. The papers are hashed into `manifest.json`, so the copy checks each one:

```bash
mkdir -p "$CORPORA" && cp -rn "$REPO"/tests/EV2/corpora/. "$CORPORA"/
cat > "$EV/check-manifest.py" <<'EOF'
import hashlib, json, sys, pathlib
c = pathlib.Path(sys.argv[1]); m = json.loads((c / "manifest.json").read_text())
bad = [p["file"] for p in m["papers"] if hashlib.sha256((c / p["file"]).read_bytes()).hexdigest() != p["sha256"]]
sys.exit(f"{c.name}: {bad}" if bad else 0)
EOF
for C in "$CORPORA"/*/; do uv run python "$EV/check-manifest.py" "$C" || echo "FAIL manifest $C"; done
echo "S001" > "$EV/variant-study.txt"
echo "$CORPORA/rag-claude-s1-mixed-cf-S001-contradicts" > "$EV/cf-llm.txt"
echo "$CORPORA/rag-tpl-s1-mixed-cf-S001-contradicts" > "$EV/cf-tpl.txt"
for f in cf-llm cf-tpl; do test -f "$(cat "$EV/$f.txt")/variant.json" && echo "$f ok" || echo "FAIL $f"; done
```

If the manifest check fails, the checkout changed the line endings (`.gitattributes` keeps `tests/EV2/corpora/**` LF).
Record it and **USER**.

Row `EV-synth`:

- copy each corpus's `selection` from `corpus.json`: requested and retained studies, and per level the passed papers,
  failed checks and mean attempts;
- in the notes, say "built on the laptop, Claude writer";
- the calls are in `tests/EV2/claude-writer/`.

This step replaces steps 1.0–1.5 and 2.1–2.3 of earlier versions of this runbook. Step 1.5 (the `--no-statements`
comparison) is dropped.

## Priority on the three orch replicas (steps 3, 5, 6 run side by side)

Three lanes, one per replica. Each lane works through its list in order; stop when time runs out.

| Lane | Step | Order |
|---|---|---|
| A | 3, engine | `rag-claude-s1-mixed` → `rag-tpl-hard-complex`, `rag-tpl-hard-mixed` → the counterfactuals (`cf-llm`, `cf-tpl`) → `rag-claude-k1-mixed`, `rag-tpl-k1-mixed` → the per-level corpora (`rag-claude-s1-<level>`, `rag-tpl-s1-<level>`) |
| B | 6, baselines | the same order as lane A, over step 6's corpora |
| C | 5, then 6.1 | step 5 on `rag-claude-small-*`, then 6.1 (both oracles) on lane A's first corpora |

Engine runs now default to `--workers 3`, so one lane keeps up to 3 model calls in flight (the outputs do not depend on
it). With three lanes the gateway sees up to 9 at once, about 3 per replica under least-busy routing. Each `orch-3x40`
replica allows 8 active and 8 queued requests (`max_num_active_seqs: 8`, `max_num_queued_reqs: 8` in the profile at
llm-setup `22dae03`), so 3 per replica is well inside the limit. Pass `--workers 1` to go back to one call at a time.

When lane A has finished, run step 4 there. Run step 7 per corpus as soon as its engine runs, baselines and oracles
exist: 7.1 and 7.2 for `rag-claude-s1-mixed` first.

The loops in steps 3 and 6 run every corpus. To follow the order, set `CS` to an item's corpora instead of the full
list, and launch the step once per item in its lane. Give each launch its own step name, for example `3-s1-mixed`, so
the logs stay apart.

## 3. Engine on every corpus **(long)**

```bash
cat > "$EV/engine.sh" <<'EOF'
#!/usr/bin/env bash
# regex-only and the cascade (regex, then the LLM extractor on orch-model) on every main-set corpus, the
# variants, the knob sets' mixed corpora and the hard set's complex and mixed corpora; the cascade in both
# strategies: `all` (every extractor on every paper, the screen recorded) and `gaps` (the funnel: screen,
# then escalate only the gaps; docs/evidence-system.md Part D); and `gaps` once more under the escalate
# protocol $PE (screen.lexical_miss: escalate; the only difference to $P), run id "<corpus>-escalate".
set -u
: "${PE:?PE is not set: run step 0.6 first}"
fail=0
CS=()
for W in claude tpl; do
  for L in explicit paraphrased distributed complex contradictory mixed; do CS+=("$CORPORA/rag-$W-s1-$L"); done
done
CS+=("$CORPORA"/rag-claude-k1-mixed "$CORPORA"/rag-tpl-k1-mixed "$CORPORA"/rag-tpl-hard-complex "$CORPORA"/rag-tpl-hard-mixed
     "$(cat "$EV/cf-llm.txt" 2>/dev/null)" "$(cat "$EV/cf-tpl.txt" 2>/dev/null)")
for C in "${CS[@]}"; do
  N=$(basename "$C")
  [ -f "$C/manifest.json" ] || { echo "FAIL engine missing corpus '$C'"; fail=1; continue; }   # excluded or not built
  uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/regex-only" --cache "$CACHE/engine" \
    --extractors regex-only --model orch-model --run-id "$N" || { echo "FAIL engine regex-only $N"; fail=1; }
  uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/cascade" --cache "$CACHE/engine" \
    --extractors cascade --strategy all --model orch-model --run-id "$N" || { echo "FAIL engine cascade $N"; fail=1; }
  uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/cascade-gaps" --cache "$CACHE/engine" \
    --extractors cascade --strategy gaps --model orch-model --run-id "$N" || { echo "FAIL engine cascade-gaps $N"; fail=1; }
  uv run evidence run --protocol "$PE" --corpus "$C" --out "$RUNS/cascade-gaps-escalate" --cache "$CACHE/engine" \
    --extractors cascade --strategy gaps --model orch-model --run-id "$N-escalate" || { echo "FAIL engine cascade-gaps-escalate $N"; fail=1; }
done
exit $fail
EOF
chmod +x "$EV/engine.sh"
nohup "$EV/launch.sh" 3-engine "$EV/engine.sh" > /dev/null 2>&1 &
echo $! > "$EV/logs/3-engine.pid"
```

The corpus list is explicit (the per-level corpora, the variants named in `$EV/cf-*.txt`, the knob sets' mixed
corpora, the hard set's `complex` and `mixed`), so a variant left over from a retry is never run. A non-zero exit
of any run is a `FAIL` line and the script exits 1 (record that; the loop still runs the rest). The hard set is
100 papers per corpus: the long part of this step. `--model orch-model` is the default, written
out so the record (`run.json` `settings.model`) is explicit; `--strategy all` is written out because the default is now `gaps`. The `gaps`
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

Row `EV2-escalate`: the escalate arm against the reject arm (`cascade-gaps` against `cascade-gaps-escalate`, same
corpus, same cache). The escalate runs have the run id `<corpus>-escalate` (`$RUNS/cascade-gaps-escalate/<corpus>-escalate`),
so their run id differs from the reject arm's; steps 4 and 7 strip the suffix to find the corpus. **The escalate
arm gets no cache hits**: the protocol (with its sha256) is part of every task's key (`ExtractionTask.protocol`,
`task_sha256`), so every call of that arm is made again, about one more full `gaps` pass of GPU time per corpus,
the 100-paper hard corpora included. From each `funnel.json` count the papers whose `screen.escalated` is true
and how many of those have `screen.relevant` true (the screen's final decision), per corpus. For the extra screen
calls and tokens of the escalate arm over the reject arm compare cache-independent fields only: the
`llm_screen` row of `report.json` `extractors.cost` (`calls`, `model_calls`, `input_tokens`, `output_tokens`) and
the run totals of `report.json` `cost.total` (`calls`, `model_calls`, `input_tokens`, `output_tokens`); not
`made_model_calls`, `cached_calls` or `seconds`, which differ by cache state. From `compare-lexical` (7.2) the
accuracies and the screen's precision and recall of both (the `lexical_miss` and `protocol` columns name the
arm). Only a cascade whose `lexical_miss` is `escalate` carries the `escalated` key; the reject arm's records have
EV1's shape. Report both; do not pick one.

## 4. Replay and re-execution

```bash
for R in "$RUNS"/regex-only/rag-* "$RUNS"/cascade/rag-* "$RUNS"/cascade-gaps/rag-* "$RUNS"/cascade-gaps-escalate/rag-*; do
  case "$R" in *-replay-*|*-reexec-*) continue;; esac
  [ -f "$R/run.json" ] || continue
  uv run evidence replay "$R" | grep -q '"ok": true' && echo "OK $R" || echo "MISMATCH $R"
  uv run evidence verify "$R" | grep -q '"ok": true' || echo "CHAIN $R"
done | tee "$EV/logs/4-replay.log"
uv run evidence reexec "$RUNS/cascade/rag-claude-s1-explicit" | tee "$EV/logs/4-reexec-explicit.log"
uv run evidence reexec "$RUNS/cascade/rag-claude-s1-distributed" | tee "$EV/logs/4-reexec-distributed.log"
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
for C in "$CORPORA"/rag-claude-small-paraphrased "$CORPORA"/rag-claude-small-distributed; do
  N=$(basename "$C")
  uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/cascade" --cache "$CACHE/engine-agentic" \
    --extractors cascade --strategy all --model orch-model --run-id "$N" || echo "FAIL cascade $N"
  uv run evidence run --protocol "$PA" --corpus "$C" --out "$RUNS/agentic" --cache "$CACHE/engine-agentic" \
    --extractors cascade --strategy all --model orch-model --run-id "$N" || echo "FAIL agentic $N"
  uv run evidence run --protocol "$PA" --corpus "$C" --out "$RUNS/agentic-gaps" --cache "$CACHE/engine-agentic" \
    --extractors cascade --strategy gaps --model orch-model --run-id "$N" || echo "FAIL agentic-gaps $N"
done
EOF
chmod +x "$EV/agentic.sh"
nohup "$EV/launch.sh" 5-agentic "$EV/agentic.sh" > /dev/null 2>&1 &
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
uv run evidence reexec "$RUNS/agentic/rag-claude-small-distributed" --extractor agentic | tee "$EV/logs/5-reexec.log"
```

Row `EV-agentic`: per corpus and strategy the agentic calls (ok / partial / error, with reasons), the agent's
steps and tokens per call, items it alone found (the score's cascade contribution, step 7), in `gaps` the
agent calls against `all`, replay result, re-execution summary.

## 6. Baselines on the LLM corpora **(long; orch-model, may run beside 3 and 5)**

```bash
cat > "$EV/baselines.sh" <<'EOF'
#!/usr/bin/env bash
set -u
shopt -s nullglob
# The RAG baseline (one retrieval, one call) on every corpus first; then the agent baseline, the costly one,
# mixed corpora first, so a stopped job still leaves both baselines on the corpora the comparison leans on.
fail=0
CS=("$CORPORA"/rag-claude-s1-mixed "$CORPORA"/rag-claude-k1-mixed "$(cat "$EV/cf-llm.txt" 2>/dev/null)"
    "$CORPORA"/rag-tpl-hard-complex "$CORPORA"/rag-tpl-hard-mixed)
for C in "$CORPORA"/rag-claude-s1-{explicit,paraphrased,distributed,complex,contradictory} \
         "$CORPORA"/rag-claude-small-{paraphrased,distributed}; do CS+=("$C"); done
for C in "${CS[@]}"; do
  N=$(basename "$C")
  [ -f "$C/manifest.json" ] || { echo "FAIL baselines missing corpus '$C'"; fail=1; continue; }
  uv run evaluate rag-baseline --corpus "$C" --out "$RUNS/rag-baseline/$N" --cache "$CACHE/rag-baseline.jsonl" \
    --model orch-model --retrieval global --k 8 || { echo "FAIL rag $N"; fail=1; }
done
for C in "${CS[@]}"; do
  N=$(basename "$C")
  [ -f "$C/manifest.json" ] || continue
  uv run evaluate agent-baseline --corpus "$C" --out "$RUNS/agent-baseline/$N" --cache "$CACHE/agent-baseline.jsonl" \
    --model orch-model --agent-root "$AGENT_ROOT" --run-id "$N" || { echo "FAIL agent $N"; fail=1; }
done
exit $fail
EOF
chmod +x "$EV/baselines.sh"
nohup "$EV/launch.sh" 6-baselines "$EV/baselines.sh" > /dev/null 2>&1 &
echo $! > "$EV/logs/6-baselines.pid"
```

The RAG baseline is the plain retrieve-then-answer system (`docs/evidence-system.md` Part G.1): the top 8
BM25 passages of the whole corpus (`--retrieval global --k 8`, the defaults, written out), one answering
call under the neutral prompt (answer text and citations as `[paper id, start-end]`), then the mapping call
shared with the agent baseline (label and per-paper stances for score C; it reads the answer text and the
kept citations' headers, never the passages). `--model orch-model` (the default, written out) is the model
of both calls and of the agent baseline's agent. The list names the variant of `$EV/cf-llm.txt`, so step 7
can score the baselines' shift; the hard set gets both baselines too. If time allows, also once with `--retrieval per_paper` ("every paper seen":
the top 2 passages of every paper) on `rag-claude-s1-mixed` into `$RUNS/rag-baseline-per-paper/`. Row
`EV-baselines`: per corpus the label, studies with a stance, citations kept and dropped (`answer.json`
`citations`, `dropped_citations`), the passages retrieved per paper (`retrieved`), the agent's exit status,
steps, tokens, seconds.

### 6.1 Oracle diagnostics (CPU for the engine oracle; orch-model for the RAG oracle)

Two diagnostics that read `ground_truth.json` on purpose (Rules; labelled "oracle" in every table; never systems
under test). Each tells its own counterpart's upstream errors (extraction or retrieval: the oracle is right) from
downstream ones (synthesis or reasoning: the oracle is wrong too): `oracle-synthesis` attributes only the engine,
`rag-oracle-passages` only the RAG baseline. Any other system scored with an oracle gets no attribution rows; it is
listed under `attribution.not_attributed` ("Not attributed" in `report.md`). The **engine** oracle (`oracle-synthesis`) puts the
true facts through the protocol's synthesis; it shares `evidence/rules.py` with the generator's truth, so for the
engine it checks the code path and is not an independent validation of the rules. The **RAG** oracle
(`rag-oracle-passages`) replaces BM25 by the paragraphs a reader needs to interpret each true value (the value's
paragraph plus the paragraphs of its condition and metric labels), then answers and maps as the baseline does
(it takes no `--k`, `--retrieval` or `--max-chars`; they exit with an error).

```bash
cat > "$EV/oracle.sh" <<'EOF'
#!/usr/bin/env bash
set -u
fail=0
CS=("$CORPORA"/rag-claude-s1-mixed "$CORPORA"/rag-claude-k1-mixed "$(cat "$EV/cf-llm.txt" 2>/dev/null)"
    "$CORPORA"/rag-tpl-s1-mixed "$CORPORA"/rag-tpl-k1-mixed "$(cat "$EV/cf-tpl.txt" 2>/dev/null)"
    "$CORPORA"/rag-tpl-hard-complex "$CORPORA"/rag-tpl-hard-mixed)
for L in explicit paraphrased distributed complex contradictory; do
  CS+=("$CORPORA/rag-claude-s1-$L" "$CORPORA/rag-tpl-s1-$L")
done
for C in "${CS[@]}"; do
  N=$(basename "$C")
  [ -f "$C/manifest.json" ] || { echo "FAIL oracle missing corpus '$C'"; fail=1; continue; }
  uv run evaluate oracle --protocol "$P" --corpus "$C" --out "$RUNS/oracle/$N" || { echo "FAIL oracle $N"; fail=1; }
done
for C in "${CS[@]}"; do      # the RAG oracle, on the corpora that have a RAG baseline
  N=$(basename "$C")
  [ -f "$RUNS/rag-baseline/$N/answer.json" ] || continue
  uv run evaluate rag-baseline --oracle-passages --corpus "$C" --out "$RUNS/rag-oracle-passages/$N" \
    --cache "$CACHE/rag-oracle.jsonl" --model orch-model || { echo "FAIL rag-oracle $N"; fail=1; }
done
exit $fail
EOF
chmod +x "$EV/oracle.sh"
nohup "$EV/launch.sh" 6-oracle "$EV/oracle.sh" > /dev/null 2>&1 &
echo $! > "$EV/logs/6-oracle.pid"
```

`evaluate oracle` prints `<out>: label=… studies=…` and writes a run directory (`answer.json`, `run.json`,
`evidence.jsonl`, `locate.json`; `system: oracle-synthesis`, `mode: oracle`); it is CPU and quick. The RAG oracle
writes `answer.json` with `system: rag-oracle-passages` and `settings.retrieval: oracle_passages`. Run it after
the RAG baselines (it makes orch-model calls: only when fewer than three long steps run). Row `EV2-oracle`: per corpus the
engine oracle's label and direction accuracy, the RAG oracle's label and stance accuracy, and (from 7.1) the
`attribution` counts of each oracle's counterpart: the engine against `oracle-synthesis` (from `$SCORES/<selection>/*`),
the RAG baseline against `rag-oracle-passages` (from `$SCORES/rag-oracle/*`): studies, `system_correct`,
`oracle_correct`, `upstream`, `downstream`. The agent baseline has no oracle and no attribution.

## 7. Scores, comparisons, shift, benchmark records (CPU)

### 7.1 Scores

```bash
( fail=0
for R in "$RUNS"/{regex-only,cascade,cascade-gaps,cascade-gaps-escalate,agentic,agentic-gaps}/rag-*; do
  case "$R" in *-replay-*|*-reexec-*) continue;; esac
  [ -f "$R/answer.json" ] || continue                  # a selection that did not run leaves the glob as is
  N=$(basename "$R"); S=$(basename "$(dirname "$R")")
  [ "$S" = cascade-gaps-escalate ] && N=${N%-escalate}        # the escalate arm's run id is <corpus>-escalate
  B=(); for b in "$RUNS"/rag-baseline/$N/answer.json "$RUNS"/agent-baseline/$N/answer.json; do
    [ -f "$b" ] && B+=(--baseline "$b"); done
  X=$(ls -d "$R"-reexec-*/reexec.json 2>/dev/null | tail -n 1); [ -n "$X" ] && B+=(--reexec "$X")
  O="$RUNS/oracle/$N/answer.json"; [ -f "$O" ] && B+=(--oracle "$O")      # engine oracle: upstream/downstream errors
  uv run evaluate score --run "$R" --corpus "$CORPORA/$N" "${B[@]}" --out "$SCORES/$S/$N" || { echo "FAIL score $S $N"; fail=1; }
done
# The RAG baseline against the RAG oracle (retrieval errors against reading errors): the two answers, no engine run.
for A in "$RUNS"/rag-oracle-passages/rag-*/answer.json; do
  [ -f "$A" ] || continue
  N=$(basename "$(dirname "$A")")
  [ -f "$RUNS/rag-baseline/$N/answer.json" ] || continue
  uv run evaluate score --corpus "$CORPORA/$N" --baseline "$RUNS/rag-baseline/$N/answer.json" --baseline "$A" \
    --oracle "$A" --out "$SCORES/rag-oracle/$N" || { echo "FAIL score rag-oracle $N"; fail=1; }
done
exit $fail ) 2>&1 | tee "$EV/logs/7-score.log"; echo "scores exit ${PIPESTATUS[0]}"      # non-zero: a FAIL line above
```

The hard set's `complex` and `mixed` runs are scored by the same loop (`$CORPORA/rag-tpl-hard-*`), and so
are the escalate arm (its scores under the corpus name, `$SCORES/cascade-gaps-escalate/<corpus>`) and every engine
run with `--oracle` (the `oracle-synthesis` answer of 6.1), so run 6.1 first. With `oracle-synthesis` only the
engine is attributed; the baselines in the same report are listed as not attributed (6.1). Each report now records
the run's `protocol` (`id`, `sha256`, `lexical_miss`). A report now carries `corpus_name` and a `corpus_dir` relative to the report, and `evaluate compare`
reads each corpus's `corpus.json` to add the **Selection** and **Matched** tables (template against LLM, on the
study ids both kept). EV1's `report.json` files predate that: re-score them to get those tables.
**`traceability` now means strict**: the cited paper has an overlap with one of the study's value, metric-label or
claim placements (not "same study or condition", not entailment). `overlap` is the old lenient number. EV1's
traceability is not comparable with EV2's; compare `overlap` to `overlap` if you must compare across the two.

Every `report.json` carries 95 % BCa bootstrap intervals (`intervals`: extraction F1 per evidence type,
direction accuracy per system, the paired engine-minus-baseline difference; F4). These per-report intervals
resample rows (papers or studies), so on a knob or hard corpus a duplicate counts as its own row; record that
with the numbers. Only the benchmark's pooled F1 (7.4) is cluster-bootstrapped (`cluster_bootstrap` over whole
parent studies, so a duplicate or another level's rendering of a study is not independent evidence). Each
interval row in `report.json` carries its sample size (`n_rows`, `unit`, and `n_clusters` where clustered), and
`compare.md`'s interval table shows it (`extraction_n`, `direction_n`, `paired_n`); record them. Intervals are
shown as `0.812 [0.74, 0.88]` in `report.md` and `compare.md`; a degenerate sample gives the point value with
empty bounds. The knob
corpora add flag precision and recall, `counts_correct` and `duplicates_correct`; the `gaps` runs add the
funnel section (calls per document, stop positions, screen precision and recall).

### 7.2 Comparisons

```bash
for S in regex-only cascade cascade-gaps cascade-gaps-escalate agentic agentic-gaps rag-oracle; do
  [ -d "$SCORES/$S" ] && uv run evaluate compare --corpora "$CORPORA" --out "$SCORES/compare-$S" "$SCORES/$S"/*
done
for N in $(ls "$SCORES/cascade-gaps-escalate" 2>/dev/null); do   # the lexical_miss arms: reject against escalate
  uv run evaluate compare --corpora "$CORPORA" --out "$SCORES/compare-lexical/$N" \
    "$SCORES/cascade-gaps/$N" "$SCORES/cascade-gaps-escalate/$N"
done
for N in $(ls "$SCORES/cascade-gaps"); do   # all against gaps, one corpus per table (Part D)
  uv run evaluate compare --out "$SCORES/compare-funnel/$N" "$SCORES/cascade/$N" "$SCORES/cascade-gaps/$N"
done
for N in $(ls "$SCORES/agentic-gaps" 2>/dev/null); do
  uv run evaluate compare --out "$SCORES/compare-funnel-agentic/$N" "$SCORES/agentic/$N" "$SCORES/agentic-gaps/$N"
done
```

`--corpora "$CORPORA"` tells `compare` where the corpus directories are (for reports copied off the cluster; harmless
here). `compare-lexical` puts the two `lexical_miss` arms side by side per corpus (read it for `EV2-escalate`;
the columns `lexical_miss` and `protocol`, the first 12 hex digits of the protocol sha256, tell the two engine rows
apart, in the interval table too);
`compare-rag-oracle` shows the RAG baseline and `rag-oracle-passages` together, a **diagnostic** row marked as
such. `compare-funnel` shows, per corpus, calls and tokens per document and the screen's precision and recall next
to the accuracies (`compare.md` columns `strategy`, `calls_per_document`, `tokens_per_document`,
`screen_precision`, `screen_recall`). Both reports carry the same baseline answers, so a corpus's baseline rows
appear twice in a `compare-funnel` (and `compare-lexical`) table, identical; read them once. Oracle rows are
marked `(diagnostic)` in the interval table as in the main one.

### 7.3 Shift of the variant

```bash
( fail=0
for F in cf-llm cf-tpl; do
  CF=$(cat "$EV/$F.txt" 2>/dev/null)                   # the variant corpus (step 1–2)
  [ -f "$CF/variant.json" ] || { echo "FAIL shift: no variant in $EV/$F.txt"; fail=1; continue; }
  N=$(basename "$CF"); BASE=${N%%-cf-*}
  for S in regex-only cascade cascade-gaps cascade-gaps-escalate; do
    uv run evaluate shift --base "$SCORES/$S/$BASE" --variant "$SCORES/$S/$N" --variant-json "$CF/variant.json" \
      --out "$SCORES/shift-$S/$N" || { echo "FAIL shift $S $N"; fail=1; }
  done
done
exit $fail ) 2>&1 | tee "$EV/logs/7-shift.log"; echo "shift exit ${PIPESTATUS[0]}"
```

Per system in both reports (the engine and, on the LLM variant, both baselines) the changed study's direction
before and after against `from`/`to`, the label before and after against `expected`, and
`shifted_as_expected` (`shift.json`, `shift.md`).

### 7.4 Benchmark records per extractor (B11)

```bash
L="explicit paraphrased distributed complex contradictory"
for W in claude tpl; do
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

Row `EV-scores` (EV2: also the `Selection` and `Matched` tables of `compare-cascade`, the traceability note above, `n_rows` / `n_clusters` beside each interval): the `compare-cascade`, `compare-cascade-gaps`, `compare-regex-only` and `compare-agentic`
tables, and per level for the cascade: extraction F1 per evidence type (with interval), association accuracy,
true pair, direction accuracy (with interval), completeness, accuracy over the answered studies,
traceability (baselines only), label correct, the paired engine-minus-baseline difference with interval, for
the engine and both baselines; the template-vs-LLM difference per level; the cascade contribution (items only
the LLM, only the agent found); on the knob sets flag precision and recall per flag, `counts_correct`,
`duplicates_correct`. Row `EV-funnel`: per corpus from `compare-funnel` (and `compare-funnel-agentic`) the
calls and tokens per document in `all` and `gaps`, the accuracies of both, the stop-position histogram and
the screen's precision and recall. Row `EV-shift`: per variant and selection `shifted_as_expected` per
system. Row `EV-benchmark`: per extractor id of `benchmark-llm/benchmark.md` (and `benchmark-tpl`) the F1 per type
and level, the line "Pooled F1 (cluster bootstrap over parent studies)" (point, interval, method, clusters), span
accuracy, cost per call and stability.

## 8. Fidelity hand check (**USER**)

The review sheet was drawn on the laptop (`synth sample --n 20 --seed 1`: all 20 papers, 483 rows, the 142 priority-1 rows first in each paper) and is committed with the corpus:
`tests/EV2/corpora/rag-claude-s1-mixed/review/review-s1.md` and `.csv`. The hand check is the user's, done on the
laptop, and the **filled sheet is a USER deliverable**. In the CSV, per row, the columns `present`,
`states_truth` and `unambiguous` take `yes` / `y` / `no` / `n`; a row counts only when all three are filled.
Notes go in the `notes` column. Record `NOT RUN (USER)` until they report. When the user returns the sheet (to
`$CORPORA/rag-claude-s1-mixed/review/review-s1.csv`), summarise it:

```bash
uv run evaluate review --csv "$CORPORA/rag-claude-s1-mixed/review/review-s1.csv" | tee "$EV/logs/8-review.log"
```

It prints `rows`, `reviewed` (rows with all three checks filled), the `yes` count per check, and one line per
problem (paper, fact, failing check, the user's note). A malformed sheet exits with `evaluate review: ...`;
record the message and ask the user. Row `EV-fidelity`: those numbers and the sheet's path on Ceph.

## 9. Proposal flow dry run (orch-model, three calls; between two long steps)

The proposal flow (`docs/evidence-system.md` Part E) has run only on a scripted model. This runs it once on
`orch-model` for the RAG question, every decision left at the model's
default (`by: model`), and compares the frozen protocol with the hand-written one. **Nothing runs the
proposed protocol**: no `evidence run --protocol "$PR/protocol.yaml"`, now or later in this session.

```bash
uv run evidence propose frame --question "$Q" --out "$PR" \
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
deterministic. Do **not** edit `frame.json` or `decisions.yaml`: the dry run freezes the model's defaults. Each option on a
card now carries an operational `effect` line (what the option does to a run), and `cards.json` has an advisory
top-level `rationale_contradicts_effect` list (`{card, option, term}`) for model rationales that contradict the
option's effect; record it (empty is fine), it is for the user's card review.
A refusal (exit 2) is recorded with its message and the flow stops there. `freeze` now refuses the
**blocking critic checks** that no person waived: `regex_matches_enums`, `bounds_cover_rate_metrics`,
`metric_rules_collide`, and `terms_cover_synonyms` (when the screen's `on_fail` is `skip` and `lexical_miss`
is `reject`); the message names them. **Do not waive one yourself**: a waiver in `decisions.yaml`
(`waivers: [{check, reason, by}]`) needs a human `by` and a reason, and `by: model` is refused. Record the
refusal and its check ids and hand it to the user in step 10; the dry run then has no `protocol.yaml`, and the
steps that need it (`protocol check`, `diff`, `compare`) are `NOT RUN (freeze refused)`. a failed model call (exit 1) may be retried once; a cached reply the step cannot use
names `--refresh`: rerun that step once with `--refresh`. Row `EV-propose-live`: per step the exit status,
`call.cached` and tokens if logged; from `frame.json` the roles and outcomes; `critic.json` `ok` and every failed deterministic check, and the four checklist answers; per card
of `cards.json` the model's default and whether it is `draft`; `proposal.json` `protocol.sha256`,
`run_settings`, `decided_by` and `review` (`review.status` is `model_defaults` for this dry run, as every decision
is the model's; it becomes `partly_human` or `human` only after the user's decisions; `review.waivers` lists any); `protocol-compare.json` `equal` and every differing path; the size of
`protocol.diff` (lines).

## 10. Proposal review (**USER**)

Tell the user where the proposal is (`$PR`: `cards.json`, `decisions.yaml`, `critic.json`, `protocol.diff`,
`protocol-compare.json`) and ask, per card: would they keep the model's default, and if not, which option
and why; point them at `cards.json`'s `rationale_contradicts_effect` entries and at each option's `effect` line
when they read the cards. Record their answers in the `EV-propose-live` row. Do not edit `decisions.yaml` or freeze
again: the directory is frozen, and a different decision becomes a new proposal (or an `amend`) in a later
session; until the user decides the cards, `proposal.json` `review.status` stays `model_defaults` (say so in the
row). The one exception: if step 9's freeze **refused** on blocking checks, the user alone may waive a check
by adding `waivers: [{check: <id>, reason: <why>, by: <their name>}]` to `decisions.yaml`; only on their word
run `uv run evidence propose freeze "$PR"` once more and record the new `review.status`, `review.waivers` and
`decided_by`. Record `NOT RUN (USER)` until they answer.

## Finish

1. `tests/RESULTS.md`: rows `EV-setup`, `EV-synth`, `EV-engine`, `EV-replay`, `EV-agentic`, `EV-baselines`,
   `EV-scores`, `EV-funnel`, `EV-shift`, `EV-benchmark`, `EV-fidelity`, `EV-propose-live`, and the EV2 rows
   `EV2-escalate` (3, 7.2), `EV2-oracle` (6.1, 7.1), `EV2-hard` (the hard template set); date, job id,
   node, commit, PASS / PARTIAL / FAIL / NOT RUN, the numbers, notes with the Ceph paths. The EV1 rows stay
   as they are; say "EV2" in the notes of every row of this run so the two runs are not confused.
2. Copy into `tests/EV2/` (create it; leave `tests/EV1/` untouched; each file under 1 MB; larger stays on Ceph,
   path in the row): the corpora are already in `tests/EV2/corpora/` (do not copy them again); per run
   `run.json`, `answer.json`, `locate.json`, and for `gaps` runs (both `lexical_miss` arms) `funnel.json`; the
   oracle runs' `answer.json` and `run.json` (`$RUNS/oracle/*`, `$RUNS/rag-oracle-passages/*`); per score
   `report.json`, `report.md`; the `compare-*`, `shift-*` and `benchmark-*` directories; `reexec.json` files; the baselines'
   `answer.json`; from `$PR` every file (`frame.json`, `draft.yaml`, `draft.sources.json`, `critic.json`,
   `cards.json`, `decisions.yaml`, `protocol.yaml`, `protocol.v1.yaml`, `proposal.json`, `written.json`,
   `cache.jsonl`, `protocol-check.json`, `protocol.diff`, `protocol-compare.json`) into `tests/EV2/proposal/`;
   `variant-study.txt`, `cf-llm.txt`, `cf-tpl.txt`, the filled `review-s1.csv` and its summary log, `logs/` and
   `failures.md`. Not the papers, not the caches under `$CACHE`, not `in-job.env`. Before `git add`:
   `find tests/EV2 -size +1M` prints nothing and
   `grep -rlF -f <(printf '%s\n' "$LITELLM_MASTER_KEY") tests/EV2` prints nothing.
3. `docs/STATE.md`: under §6 add one line per row with the number that matters, and the Linux pytest count
   (step 0.1) as the new expected value in §6 and in step 0.1 of this runbook.
4. Commit on `evidence-ev2b` (results separate from fix commits), `git push -u origin evidence-ev2b`.
5. `scancel "$JOB"` when everything has finished (**USER** first if they want to look at anything live).
6. Report: pass / fail per step with the number that matters, the `compare-cascade` table, the `compare-lexical` numbers (reject
   against escalate: escalated papers and how many ended relevant, extra calls and tokens, accuracies), the
   oracle attribution (upstream against downstream per system), the hard set against the easy one,
   the `compare-funnel` numbers (calls per document `all` vs `gaps`, accuracies, screen precision and recall),
   `shifted_as_expected` per system, the frozen proposal's `protocol-compare.json` `equal`, its differing
   paths and `review.status`, every fix commit (one line each), every failure from `failures.md`, the open **USER** steps, and
   anything surprising.
