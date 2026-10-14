# Runbook: first real runs on Slurm (rows 1.1 and 1.13)

> Since the 1.13 fix (`e2e/agent-fix`), `agent run` defaults to prompt v2 at 60 steps / 2,000,000 tokens.
> The commands below were run with the defaults of that time; to repeat them as they ran (prompt v1, its
> loop, 150 steps / 400,000 tokens, attach prompt v1) add `--prompt-version v1` to each `agent run`
> (`agent attach` then follows the run's prompt version). Without it they start v2 runs, and the budget
> row of the measurement table below no longer applies.

Everything in milestones 1 and 2 that can be built without the cluster is on `main` and passes its tests with a
scripted model (`tests/RESULTS.md`, M2-run). This session runs it on the real models for the first time. The
results decide the run budget, which is then frozen for both conditions.

## Rules

- Work on branch `m1-cluster` (`git checkout -b m1-cluster origin/main`). Never push `main`; push the branch at the end.
- Never kill or signal a real process to test a permission (`kill -0` only). Never log a secret's content: for
  `.env`, keys or `/proc/<pid>/environ` record only "readable" / "denied" and a byte count. The API key is read
  only from `$LITELLM_MASTER_KEY`.
- Run directories (`--runs-root`) go on Ceph outside the repo, never in git. Copy into the repo only the small
  files named under "Finish".
- Fixing a bug is allowed on the branch: one commit per fix, with a test, and `uv run pytest agent/tests` green
  before the next run. Do not change budgets, prompts or the anchor rules to make a run pass; record and stop.
- Steps marked **USER** need the user: stop and ask.

## 0. Setup

```bash
git fetch && git checkout -b m1-cluster origin/main
git submodule update --init --recursive
uv sync --locked && uv run pytest agent/tests -q      # expect the M2-run count: 265 passed, 1 skipped
set -a; source llm-setup/.env; set +a
export CORPUS=<frozen corpus on Ceph, from D5>        # read-only, has manifest.json
export AGENT_ROOT=<agent root on Ceph>                 # build with scripts/build-agent-root.sh if missing
scripts/verify-agent-root.sh "$AGENT_ROOT"
export RUNS=<Ceph dir outside the repo>/runs
```

Check that `sha256sum $CORPUS/manifest.json` equals the hash of `corpus/manifest.json` from an LF checkout (`22e9471b…`).

Stack: `cd llm-setup && LLM_SETUP_PROFILE=profiles/agent-3x40.yaml sbatch slurm/llm-stack.sbatch`, wait for
ready (~11 min), then `srun --jobid <id> --overlap --pty bash -l` and repeat the exports above in that shell.

## 1. F1 acceptance (row 1.1, 30 min)

```bash
uv run python tests/F1/acceptance.py
```

Pass: every check in its output is true (corpus read-only, claim stored with the broker's step id, quote found
in the manifest's file, chain verifies, agent root verifies, no network). Record a row `F1` in `tests/RESULTS.md`.
If F1 fails, stop here: fix on the branch or report.

## 2. `claim` from the repo under Landlock on Ceph (10 min, before any agent run)

On WSL `/mnt/c` the Landlock rules did not hold and `claim` (`agent/bin/claim`) was denied. Check it here with a
one-step run, condition `claim_on`, then look for a claim record in `claims.jsonl`:

```bash
uv run agent run --concept agent/concepts/rag-eval-datasets.json --run-id smoke-01 --runs-root "$RUNS" \
  --condition claim_on --temperature 0.7 --seed 1 --agent-root "$AGENT_ROOT" --steps 3 --tokens 40000
uv run agent verify "$RUNS/smoke-01"
```

If `claim` is denied (Permission denied, or no claim record although the agent called it): make the claim client
available from `$AGENT_ROOT` instead of the repo (the fallback in `docs/STATE.md`, Open), add a test, rerun the
smoke run. Record which path worked.

## 3. First real runs (row 1.13, ~half a day)

Temperature 0.7 is provisional (Qwen's recommendation for thinking off); keep it for every run in this session.

```bash
for s in 1 2 3; do
  uv run agent run --concept agent/concepts/rag-eval-datasets.json --run-id c3-on-$s --runs-root "$RUNS" \
    --condition claim_on --temperature 0.7 --seed $s --agent-root "$AGENT_ROOT"
done
uv run agent run --concept agent/concepts/rag-eval-datasets.json --run-id c3-off-1 --runs-root "$RUNS" \
  --condition claim_off --temperature 0.7 --seed 1 --agent-root "$AGENT_ROOT"
uv run agent attach "$RUNS/c3-off-1"
```

After each run:

```bash
R=$RUNS/<run-id>
uv run agent verify "$R"
uv run agent pairs "$R"; uv run agent timeline "$R"
uv run agent graph "$R" --manifest "$CORPUS/manifest.json"; uv run agent export-prov "$R"
uv run agent query 1 "$R" --edge edge-000001
uv run agent query 2 "$R" --claim claim-000001
uv run agent query 3 "$R" --agent main
uv run agent query 4 "$R" --corpus "$CORPUS" --manifest "$CORPUS/manifest.json"
uv run agent query 5 "$R"
```

For a `claim_off` run before `attach` there are no claims, so queries 1–3 return nothing; run them after `attach`.

## What to measure (per run, one line each)

| Measure | Where | Decides |
|---|---|---|
| Steps, total tokens, wall time, how it ended (answer, budget, context full, no answer) | `agent verify`, `config.json`, last records | the budget (400k / 150 steps): note how far into it the answer came |
| Largest prompt in tokens; any HTTP 400 context-full | `ai_model_invocation` records | C8: does a run reach 61,440? If yes, row 1.15 (masking) is needed |
| Claims sent / accepted / rejected, by reason | `claims.jsonl`, `agent verify` | B5: rejection share; whether to relax case sensitivity or set a minimum quote length |
| Answer rows; rows with no claim (query 5) | `answer.json`, query 5 | whether the prompt needs a change before the 72 runs |
| Unparseable replies (coverage records), repeat notices | `events.jsonl` | parser and loop behaviour on the real model |
| Commands that hit the 120 s timeout or the 2 GB limit | `agent_tool` records | sandbox limits |
| Attach step: facts, quoted / "no source found", tokens and steps per fact | `attach.json`, `agent verify` | the attach budget (6 steps / 60k tokens per fact) |
| Five queries return results without error | step 3 | row 2.10 is ready |

Read 5 accepted quotes by hand per run against the paper: does the quote really support the fact? One line each.

## Do not

- Do not start `agent batch` or the 72 runs; the questions do not exist yet (row 2.3, **USER**).
- Do not change the budget; propose numbers in the report, the user freezes them.

## Finish

1. `tests/RESULTS.md`: rows `F1`, `M1-claim-ceph`, `M1-real` (the table above, one line per run), `M2-attach-real`.
2. Copy into `tests/M1-real/<run-id>/` only: `config.json`, `answer.json`, `verify` output, `pairs.jsonl`,
   `timeline.html` (each under 1 MB; otherwise leave on Ceph and give the path).
3. `docs/STATE.md`: move "`claim` under Landlock on Ceph" and "F1" from Open to Decided with the result; fill
   C8 and B5 under Later or Numbers.
4. Commit on `m1-cluster`, push it. `scancel` the stack job.
5. Report: pass/fail per step, the numbers per run, a proposed run budget and attach budget, every fix made,
   and anything that surprised you.
