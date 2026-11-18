# synth3 readable programs and re-run measure (plan 5 of 5): handoff

Finished 18 Nov 2026 on branch `synth3-replay` (from synth3-system @ e8da1e8e to 64788609). Merged to main and pushed
on Aditya's instruction.

## State
- 11 tasks done, each reviewed. Middle tasks ran in parallel lanes in their own worktrees, merged back locally;
  the cli.py / README.md merge conflicts were resolved by hand (08e9911c). Worktrees and lane branches are removed.
- Final whole-branch review (0 critical, 1 important, 11 minor); one fix pass (12 commits, 2fa38a48..64788609); a
  scoped re-check found every item addressed. Two notes parked (below).
- Tests: per-task sets green (readable 75, stability 27, remeasure 6, evsystem 18); frontend 193 tests, typecheck
  and lint clean; whole backend suite run at close.
- New commands: `evidence program RUN --out FILE.py`, `evidence reexec RUN --all-calls [--times N --out DIR]`,
  `synth3 reexec --domain D --seed N [--times 5]`. New web route GET /api/ev/system/runs/{rid}/program and a
  download link on the answer box.
- Nothing ran on the cluster. No program or re-run exists yet.

## What it does, in one breath
`evidence program` writes one standard-library Python file per run: it holds the facts the run used, rebuilds the
answer from them with the same rules as the engine, and prints CHECK_OK only when the rebuilt text equals the
answer the sealed run recorded (it refuses a run whose answer, evidence.jsonl or reason.json no longer match
run.json). `reexec --all-calls` asks every model call again with no cache; `stability` compares the re-runs with
the original: identical calls, items found again, same answer.

## Judgement calls (cost if wrong)
- The program rebuilds the answer from the values recorded per paper; it does not choose them again — cost: the
  word "rebuilds" may need a footnote in the thesis.
- "Same answer" measures one run's calls asked again, not the writer retry policy — cost: a separate measure if
  wanted.
- Non-finite values are written as float('nan') / float('inf') — cost: none seen; a real run cannot hold one.
- Parked: the edited-file check does not cover protocol.yaml or plan.json (evidence verify does) — cost: an edited
  protocol after sealing is not refused by the program.

## For Aditya
1. Before the 5 re-runs: confirm the LiteLLM proxy has no response cache (else every call reads "identical").
2. Cluster: `uv run synth3 reexec --domain medicine --seed 1 --times 5` after plan 4's system runs exist.
3. Keep downloaded programs local: they quote renamed real papers.
4. Decide whether to measure the agentic extractor on an old RAG run.
