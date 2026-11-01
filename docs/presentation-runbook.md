# Presentation runbook — Tim, 22 October 2026

For Aditya, presenting. About 20 minutes plus questions. Everything here runs on the laptop; the Slurm part is optional.

## What you show

| Order | What | Where |
|---|---|---|
| 1 | Slides 1–3 (cover, compiler picture, one paper through the engine) | Deck: https://claude.ai/artifact/VAqrCrv1L6vbnK3DdQHfy6 |
| 2 | The runtime animation: five papers move through screen → locate → extract → check → graph → synthesis | https://claude.ai/artifact/Eb2kRsFjXakdjhAueztuBa (Play, or → key for one step) |
| 3 | Slides 4–5 (benchmark, evaluation with the EV1 numbers) | Deck |
| 4 | Optional live terminal demo, 3 minutes, no GPU (below) | Laptop, Git Bash |
| 5 | Slide 6 (what changed on 21 Oct) and the question for Tim | Deck |

Both links are private. Present from your own browser, or share them from each page's Share menu before the meeting if Tim should open them.

## Tonight (15 minutes)

1. Open both links once, click through all six slides and play the animation to the end (it ends with “mixed (2 supporting, 1 contradicting, 1 neutral)”).
2. Read the speaker notes on each slide (they hold Tim’s quotes and the exact numbers).
3. Run the terminal demo below once, so the files exist and the first run is not live.

## The terminal demo (offline, CPU, about 30 seconds in total)

Uses the integration branch with all 21 Oct changes (worktree `../tra-ev3-int`; `main` does not have them until you approve the merge). Git Bash:

```bash
cd ~/Documents/repo/tra-ev3-int
PY=~/Documents/repo/thesis-research-agent/.venv/Scripts/python.exe
export PYTHONPATH=. PYDANTIC_AI_NO_BANNER=1
D=~/demo-22oct; rm -rf "$D"; mkdir -p "$D"
ev() { $PY -c "import sys; from evaluation.cli import main; sys.exit(main(sys.argv[1:]))" "$@"; }

# 1. ground truth -> 12 synthetic papers at five levels (template writer, seeded)
$PY -m synth.cli build --name demo --seed 1 --studies 12 --out "$D/corpora"

# 2. the engine runs the hand-written protocol, regex extractors only (no model)
$PY -m evidence.cli run --protocol domains/rag/protocols/rag-factuality.yaml \
  --corpus "$D/corpora/demo-mixed" --out "$D/runs" --extractors regex-only --run-id regex

# 3. the oracle: our synthesis on perfect evidence taken from the ground truth
ev oracle --protocol domains/rag/protocols/rag-factuality.yaml --corpus "$D/corpora/demo-mixed" --out "$D/oracle"

# 4. score A/B/C and attribute each wrong study to extraction or synthesis
ev score --run "$D/runs/regex" --corpus "$D/corpora/demo-mixed" --oracle "$D/oracle/answer.json" --out "$D/scores"
```

Then open `$D/scores/report.md` and show two tables:

- **A. Extraction**: regex alone gets precision 0.98 but recall 0.44; paraphrased papers give 0 measurements. This is why the LLM extractors exist.
- **Attribution**: every wrong study is “upstream” (extraction), none “downstream”: the oracle gets all 12 right, so on this set the synthesis rules are not the problem. Say plainly that the oracle and the generator share the same rules, so this checks the code, not the rules.

Optional proof that the fixes hold (about 20 seconds, 34 tests):

```bash
$PY -m pytest -q -p no:cacheprovider evidence synth evaluation \
  --ignore=evaluation/tests/test_agentic_agent.py --ignore=evaluation/tests/test_runner.py \
  -k "rejects_175 or keyword_miss_escalates or condition_roles_resolve_local_qualifiers or rejects_right_values_on_wrong_metric or step10_count_form or freeze_blocks_on_uncovered or dataset_first or count_expressions_become_fractions or missing_gold_label or cluster"
```

And the fidelity review status (shows the human review is still open):

```bash
ev review --csv tests/EV1/live-rerun/corpora/rag-llm-s1-mixed/review/review-s1.csv   # rows 342, reviewed 0
```

## The web app as a case study (laptop, no cluster)

`bash docs/presentation/ui-case.sh` (Git Bash, from the repo) builds a local `$EV` in `~/demo-ev-case` in about a
minute and serves the app on http://127.0.0.1:8080 (`PORT=8091 bash ...` if 8080 is taken). It holds the EV1
LLM-written corpus `rag-llm-s1-mixed` (11 papers), an offline engine run on it (regex extractors, no model), the
oracle run, and all EV1 live scores and comparisons. Later `--serve` alone restarts it without rebuilding.

Click path for Tim: question `rag-factuality` -> protocol -> corpus `rag-llm-s1-mixed` (fidelity, the 9 excluded
studies) -> run `regex-only~rag-llm-s1-mixed` -> paper S005 with its anchored quotes -> evidence graph -> answer
-> Scores (`ev1-compare-cascade` for engine vs RAG vs agent). The live LLM runs are shown through their scores
only: their run directories stayed on Ceph. When EV2 results with `tests/EV2/ui-case/` are committed, rerun the
script and they appear beside the EV1 ones.

## What to say, slide by slide

1. **Cover.** His 14 Oct direction: operationalize the question into evidence requirements; a protocol as the plan; the synthetic benchmark as the main instrument.
2. **Compiler.** Question → protocol (the IR) → engine → evidence graph and answer. Protocol generation exists but stays optional (his §8).
3. **Engine.** Switch to the animation here. Point out S002 (authors’ claim contradicts their numbers, his §7 case), S003 (175 % rejected), S004 (synonym only, now rescued by escalation), X001 (skipped with a reason).
4. **Benchmark.** Ground truth first (his §5); fidelity check (his §6); 11 of 20 studies survived the LLM writer, and that drop is now reported.
5. **Evaluation.** Engine vs RAG: +0.455 [0.18, 0.73]; engine vs agent: +0.182 [0.00, 0.45], not conclusive. Direction at 1.0 means the set is too easy. “We should not assume …” is his line; use it.
6. **What changed.** Four groups; each item has a regression test.

## The question to ask Tim

> For the next run I plan a larger and harder synthetic benchmark (about 100 studies, several experiments per paper, duplicates and missing values) plus the human fidelity check, and keep real papers as the optional extension you mentioned. Is that the right priority?

## Likely questions and short answers

- **“How do you know the synthetic papers say what you planned?”** Deterministic checks plus a blind re-read by a second model that now has to return condition, metric, dataset and value; a 342-row human review sheet is ready but not filled yet.
- **“Is the engine just matching its own generator?”** Partly: generator truth and synthesis share the rules file. That is why the oracle is described as a code check, and why the harder set and a human check come next.
- **“Why not real papers yet?”** You made them optional (§8); the plan keeps them as the last step.
- **“What did the LLM cost?”** Cascade “all”: about 10 calls and 10.6k tokens per paper; “gaps”: 7 calls and 4.3k tokens, with lower accuracy (EV1, LLM mixed corpus).
