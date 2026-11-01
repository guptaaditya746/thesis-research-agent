# Runbook: EV3b, the question-first runs again after the fixes (Codex)

EV3 (tag `ev3`, branch `results`, `reports/question-first/`) found problems in the engine, the RAG baseline and the
agent baseline. They are fixed in code. This session runs the grid again with the fixed code and writes one new
table. **This file is a differences document.** Everything not written here is as in
`docs/runbook-question-first.md` (called "EV3" below): its rules, the ten question ids, the corpora, the settings,
the stack with GLiNER (section 1), the helper scripts `one.sh`, `grid.sh`, `extra.sh`, `extras.sh`, `launch.sh`,
the failed-call and retry rules, the scoring table, the hand-back commands, the Limits. Read EV3 fully first.
`docs/slurm-evidence-runbook.md` 0.3 still gives `$EV`, `in-job.env`, `launch.sh`, `$AGENT_ROOT`.

**What changed in the code (all on `ev3b-code`)**

- Engine: `evidence run --confirm {none,llm}`, default `llm`. An item that only GLiNER found now counts only when
  the LLM extractor finds it too. The merge events carry `custom_metadata["unconfirmed"]`: the ids of the dropped
  items (the key is there only when something was dropped). Under `gaps` the LLM step of a type runs right after
  its GLiNER step, in the same round, when GLiNER found something. This changes every cascade run. `regex-only` and
  `llm-only` runs have no GLiNER step and are unchanged.
- Engine: `evidence run --relink {on,off}`, default `on`. Under `gaps`, when a later round merges a type again and
  an item gets a new id (the LLM quoted another span of it), the links of the other types' items now follow it;
  before, they pointed at nothing and the study could become `no_pair`. The merge events carry
  `custom_metadata["relinked"]` (the `[old, new]` id pairs, only when not empty), and every run now counts the links
  that point to no item: `dangling_links` in `run.json` and `funnel.json` (expected **0**). This can change cascade
  `gaps` runs of every question, with or without GLiNER, and a study complete earlier needs fewer calls.
- RAG: `evaluate rag-baseline --max-tokens N`. `per_paper` defaults to 16,384 answer tokens (EV3: 4,096, so some
  long answers were cut off). `global` keeps 4,096, so its EV3 cache entries are still hits.
- Agent baseline: the runner now uses prompt **v3** (a repeated command is refused instead of ending the
  research). This changes every agent prompt, so every agent cell is asked again.

**Decisions by Aditya (29 Oct)**

- The per-paper RAG is the main RAG row: `rag-per-paper` with k=2 on the main corpus, k=1 on the hard corpus. The
  top-k global RAG (k 8) moves to "Extra comparisons".
- No agent repeats. No repeat of `engine-r2`, `rag-seed1`, `rag-seed2` either (see section 4).
- The paperwork must be finished: no "Pending" text in `summary.md`, and a final `status` in `session.json`.

**Rules that differ from EV3**

- The code tag is **`ev3b-code`** (not `ev3-code`). Save report files under `reports/ev3b/`, on the branch
  **`results-ev3b`**, tagged **`ev3b`**. Never touch the branch `results` or the tag `ev3`.
- The session directory is new: `export EV=/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-ev3b`. The old one
  (`.../evidence-qf`, "`$EV3`" below) is read, never written.
- Agent baselines go through `evaluate agent-baseline` only (that is what `one.sh` runs). **Never use `agent run`
  for these cells**: its own default is still prompt v2. Do not mix versions in one table: every agent cell must
  show `v3` (section 5).
- The diagnosis (section 1) comes **before any run**.

## 0. Branch and setup

As EV3 section 0, with these values:

```bash
cd /mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent
git fetch origin --tags
git rev-parse --verify -q 'ev3b-code^{commit}' || echo 'FAIL step 0: no tag ev3b-code; stop, USER'
git checkout --detach ev3b-code
git describe --tags                       # ev3b-code; record this and `git rev-parse HEAD` in summary.md
git submodule update --init --recursive
git -C llm-setup log -1 --oneline         # expect b962edd (the llm-setup commit with the port fix)
git ls-tree HEAD llm-setup               # 160000 commit b962edd83c987efd1275ee535dd19bc4186e4ce3
uv sync --locked --all-groups
uv run evidence run --help | grep -- --confirm
uv run evidence run --help | grep -- --relink
uv run evaluate rag-baseline --help | grep -- --max-tokens
uv run evaluate agent-baseline --help | grep -- --question-id
```

The **USER** creates the tag `ev3b-code` on `main` (after merging the three fixes) and pushes it. If the tag is
missing, `git checkout` fails, `git -C llm-setup log -1` does not show `b962edd`, or one of the four `grep` lines
prints nothing: stop, **USER**. The parent repo must be at the tag `ev3b-code`: it contains `78fbb67` ("fix: use
distinct distributed ports for replicas"), the commit that moves the submodule to `b962edd`. That submodule commit
holds the port fix you made by hand in EV3 (`llm-setup-port-fix.patch` on `results`), so **do not apply that patch
again** and make no llm-setup change
except the profile copy of EV3 step 1.4.

Then EV3 section 1 (GPU report, stack with GLiNER, `in-job.env`, `mkdir`), with the new `$EV`. Its section 2 (offline
check) and the two code checks (`scored_types`, `no_question_metric`) are run again as written, plus these lines,
which must print `confirm`'s default as `llm` and `relink`'s as `on` (the word `(default)` follows `llm:` and `on:`):

```bash
uv run evidence run --help | grep -A1 -- '--confirm {'      # llm: ... (default)
uv run evidence run --help | grep -A2 -- '--relink {'       # on: ... (default); off: ...
```

`one.sh` (EV3 section 4) passes neither flag, so every engine cell runs with `--confirm llm --relink on`.

Seed the caches from EV3 (the old caches make every unchanged call a hit: the global RAG, `regex-only`, `llm-only`,
`rag-oracle`, the seeds, and every engine call that is not new). If `$EV3/cache` is gone from `data-tmp`, rebuild it
from the hand-back:

```bash
EV3=/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-qf
if [ -d "$EV3/cache" ]; then cp -a "$EV3/cache/." "$EV/cache/"
else mkdir -p "$EV/seed" && git archive origin/results reports/question-first | tar -x -C "$EV/seed" \
  && cat "$EV"/seed/reports/question-first/caches.tar.gz.part-* | tar -xz -C "$EV/seed" \
  && cp -a "$EV/seed/cache/." "$EV/cache/"
fi
ls "$EV/cache" | head -20; du -sh "$EV/cache"          # the EV3 cache files and dirs are there
```

If neither source works, go on with empty caches and say so in `summary.md` (the runs are then slower, not
different: temperature 0).

## 1. Diagnose first (read-only, before any run)

Two small reports, written with no model call, from the **EV3** run directories (`$EV3/runs`). Nothing here changes a
run. If `$EV3` is gone from `data-tmp`, write `EV3 run dirs gone` in the report file and go on.

```bash
mkdir -p reports/ev3b
```

**1a. The repeated command of the hard agent runs.** In EV3, three agent runs on the hard corpus ended their
research after the same command came back six times. Find them and print the command (run `source "$EV/in-job.env"` first, and `$EV3` as in section 0). An agent run's folder is
`$EV3/runs/agent-baseline/<corpus>.<question>/agent-runs/<run-id>-<hex>/runs/<run-id>/`; its `events.jsonl` has one
`agent_tool` record per command (`used.command`), `trajectory.json` the whole conversation. A run is listed when one command
comes back **at least 3 times in the run** (identical, not necessarily in a row; the record's
`custom_metadata.repeat` counts the ones in a row).

```bash
uv run python -I - "$EV3/runs/agent-baseline" > reports/ev3b/agent-repeats.md <<'EOF'
import json, sys, glob, collections
root = sys.argv[1]
print("# Repeated agent commands in the EV3 hard runs\n")
for ev in sorted(glob.glob(f"{root}/rag-tpl-hard-complex*/agent-runs/*/runs/*/events.jsonl")):
    cmds = collections.Counter()
    for line in open(ev, encoding="utf-8"):
        r = json.loads(line)
        if r.get("subtype") == "agent_tool":
            cmds[r["used"]["command"]] += 1
    top = cmds.most_common(1)
    if top and top[0][1] >= 3:
        run = ev[len(root) + 1:-len("/events.jsonl")]
        print(f"## {run}\n\n{top[0][1]} identical commands, trajectory: {run}/trajectory.json\n")
        print("```\n" + top[0][0] + "\n```\n")
EOF
cat reports/ev3b/agent-repeats.md
```

Good: it names the three hard runs (expect 3 headings, each with 6 identical commands; if you find another count, report
what you see, do not force it). Add one line under each heading: the exit status and step count of that run from
`$EV3/runs/agent-baseline/<corpus>.<question>/answer.json` (`agent.exit_status`, `agent.steps`).

**1b. The failed per-paper hard calls.** The EV3 `rag-per-paper-k1` answers on the hard corpus that failed or came
back empty. Print each one's output tokens (`answer.json` `model_call`), and the `finish_reason` if the vLLM log has
it (the stack log is `llm-setup/runtime/slurm-<EV3 job>.out` and the service logs under `llm-setup/runtime/`;
`finish_reason` is `length` when the answer was cut at the token limit):

```bash
{ echo "# EV3 per-paper hard RAG calls"; echo
  for A in "$EV3"/runs/rag-per-paper-k1/rag-tpl-hard-complex*/answer.json; do
    uv run python -I -c 'import json, sys; a = json.load(open(sys.argv[1])); m = a.get("model_call") or {}; print(sys.argv[1], "label=", a.get("label"), "in=", m.get("input_tokens"), "out=", m.get("output_tokens"))' "$A"
  done
  echo; echo "finish_reason in the vLLM logs (blank = the logs do not have it):"
  grep -rhoE 'finish_reason[^,}]{0,30}' llm-setup/runtime/ 2>/dev/null | sort | uniq -c
} > reports/ev3b/rag-per-paper-failures.md
cat reports/ev3b/rag-per-paper-failures.md
```

An `out=` near 4096 on a row that is `insufficient` or empty means the answer was cut at the old limit; that is what
`--max-tokens` (16,384 for per-paper) fixes. Say which rows. These two files are the whole of step 1: go on.

## 2. Offline check and mapping check

- EV3 section 2: as written (it only checks spelling and the two code lines).
- EV3 section 3 (the mapping prompts, 4 questions on the main corpus): **not repeated**; the prompts did not change.
  Instead run one cell of all three systems as a v3 smoke test (it is also a real grid cell, so nothing is wasted):

```bash
"$EV/launch.sh" one-check "$EV/one.sh" inv-datasets "$C_MAIN"; tail -n 1 "$EV/logs/one-check.launch"
```

Check it as EV3 section 4 says (run dir, the two answers, `report.md`), plus the agent's prompt version (section 5
below shows the command; expect `v3`). If it is not `v3`, stop: **USER**.

## 3. What is rerun and what is reused

| system | EV3b | cost |
|---|---|---|
| engine, `cascade`, `gaps`, `--confirm llm --relink on` (defaults) | all 10 questions x both corpora, every run (confirm and relink change it) | engine calls from cache; new: the LLM confirm steps, and any call a funnel decision changed by relink asks for |
| `rag-per-paper` (main k=2, hard k=1), now 16,384 answer tokens | all 10 questions | new calls (the cache key holds the token limit) |
| agent baseline, prompt v3 | all 20 cells | new (v3 changes every prompt); **one run per cell, no repeats** |
| global RAG (k 8), `rag-oracle`, `rag-seed1`, `rag-seed2`, `regex-only`, `llm-only` | run again with the seeded caches | all hits; they only put the EV3 answers into this session's layout so the report is complete |
| `engine-r2` (repeat of the engine) | **not run** | the cascade changed, an old repeat would not compare |

The extras that EV3 ran stay as in EV3 section 4b, from the same `extra.sh`, **except** that `engine-r2` is not run (section 3). Create
`one.sh`, `grid.sh`, `extra.sh` and `extras.sh` exactly as in EV3 sections 4 and 4b (before the one-check cell of
step 2) and do not edit them: `--confirm` and `--relink` are left at their defaults `llm` and `on`, and `rag-per-paper` / `rag-per-paper-k1`
already call `--retrieval per_paper` without `--max-tokens`, so they get 16,384.

## 4. The grid and the extras

The grid is EV3 section 4, unchanged, **after the one-check cell of step 2**:

```bash
nohup "$EV/launch.sh" grid-main "$EV/grid.sh" "$C_MAIN" > /dev/null 2>&1 &
nohup "$EV/launch.sh" grid-hard "$EV/grid.sh" "$C_HARD" > /dev/null 2>&1 &
```

The extras, after `grid-main` and `grid-hard` have finished (EV3 4b order, minus the repeats):

```bash
nohup "$EV/launch.sh" extras-main "$EV/extras.sh" "$C_MAIN" rag-per-paper rag-oracle regex-only llm-only \
  rag-seed1 rag-seed2 > /dev/null 2>&1 &
nohup "$EV/launch.sh" extras-hard "$EV/extras.sh" "$C_HARD" rag-per-paper-k1 > /dev/null 2>&1 &
```

The hard `rag-per-paper-k1` still needs `max_model_len` of 65536 or more in the `orch` line of the profile (EV3 4b
item 1); otherwise write "rag-per-paper not run on hard: max_model_len <n>" in the summary. The counterfactual
(EV3 4c) is run again as written (`one.sh rag-factuality "$C_CF"` and `evaluate shift`), with the same corpus. Its
agent cell is v3 too.

No agent repeats: a failed agent cell is retried as in EV3 ("retry-hard-agents" style, the same `one.sh` with an
empty answer), at most twice, and recorded under Failures; do not run an agent cell a second time to "see if it
changes".

## 5. Checks (EV3 section 5, plus these)

**Agent prompt version.** Every agent cell must have used v3. The version is in the agent's `config.json`, in
`agent-runs/<run-id>-<hex>/runs/<run-id>/config.json` under each baseline's `--out`, key `prompt.version`:

```bash
for C in "$RUNS"/agent-baseline/*/agent-runs/*/runs/*/config.json; do
  uv run python -I -c 'import json, sys; c = json.load(open(sys.argv[1])); print(c["prompt"]["version"], sys.argv[1])' "$C"
done | awk '{print $1}' | sort | uniq -c                # one line: "<N> v3"; N is 20 or more (21 with the counterfactual): a retried cell leaves an extra
# agent-runs/<run-id>-<hex> dir, which is expected as long as every line says v3
```

Anything but `v3` on every line: stop and report which runs (**USER**); never put a non-v3 cell into the table. The
`agent.exit_status` / `agent.steps` listing of EV3 section 6 item 1 is made again for the v3 runs, and compare with
the EV3 hard runs of step 1a: report whether the three runs now end `submitted` and whether any command still
repeats (run the script of 1a on `$RUNS/agent-baseline` and say "no repeats" or list them).

**GLiNER confirm.** For every engine run of the grid (not the extras), the numbers of GLiNER items proposed,
confirmed and dropped. The merge events' `sources` map each item id to the **call ids** that found it; the extractor
of a call is the `agent_id` of its `extractor_call` event (same `task_id`). GLiNER-proposed items are the ones with a
`gliner_*` call among their sources; dropped are the ids in `unconfirmed`; confirmed = proposed minus dropped. Under
`gaps` a merge event is written again for each type and round, and a later merge can give an item a new id, so the
script reads only the **last** merge event of each (document, evidence type): its `sources` cover every call of that
type so far. No model call; login node is fine (first `source "$EV/in-job.env"`, so `$EV`, `$RUNS` and `$QS` are
set):

```bash
source "$EV/in-job.env"
cat > "$EV/gliner-confirm.py" <<'EOF'
import json, sys
# gliner-confirm.py <run dir>: GLiNER items proposed, confirmed, dropped, over the whole run.
# `sources` of a merge event lists CALL ids; the extractor of a call is the agent_id of its extractor_call event.
events = [json.loads(x) for x in open(sys.argv[1] + "/events.jsonl", encoding="utf-8")]
agent = {e["task_id"]: e["agent_id"] for e in events if e.get("subtype") == "extractor_call"}
last = {}                                 # (document, evidence type) -> its last merge: a merge repeats per round
for e in events:
    if e.get("subtype") == "merge":
        last[(e["custom_metadata"]["document"], e["custom_metadata"]["evidence_type"])] = e["custom_metadata"]
proposed, dropped = set(), set()          # keyed (document, evidence type, item id)
for (doc, etype), c in last.items():
    for item, calls in c["sources"].items():
        if any(agent.get(x, "").startswith("gliner_") for x in calls):
            proposed.add((doc, etype, item))
    dropped |= {(doc, etype, i) for i in c.get("unconfirmed", [])}
dropped &= proposed
print(f"GLiNER confirm: proposed={len(proposed)} confirmed={len(proposed - dropped)} dropped={len(dropped)}")
EOF
for N in rag-claude-s1-mixed rag-tpl-hard-complex; do for Q in $QS; do
  G=$Q-cascade-gaps; [ "$Q" = rag-factuality ] && G=cascade-gaps
  echo "$N $Q $(uv run python -I "$EV/gliner-confirm.py" "$RUNS/$G/$N")"
done; done
```

Good: `confirmed + dropped = proposed` on every line **and** `proposed` above 0 for the GLiNER questions on the main
corpus: `rag-hallucination`, `rag-latency`, `inv-metrics`, `inv-datasets`, `cons-accuracy`, `cons-hallucination`,
`best-accuracy`, `best-hallucination` (their protocols have `gliner_*` steps; `evidence/protocols/*.yaml`). A 0 on
all of them means the script or the run is wrong: stop and report (**USER**). Under `gaps` GLiNER runs only where an
earlier step left a gap, so a 0 on a single question is a note. `rag-factuality` and `inv-methods` use protocols
(`rag-factuality.yaml`, `inv-methods.yaml`) with no GLiNER step, so `proposed=0` there is expected. `dropped` above 0
is the new behaviour, not a failure. Caveat: when the LLM confirm call fails (status `error`), the GLiNER items
of that type are still dropped; they count as `dropped`, so check `failures.md` before reading a high `dropped`.

**Dangling links.** For every engine run (grid and extras, every run dir with a `run.json` under `$RUNS`), the count
of links that point to no item, which the engine writes into `run.json` as `dangling_links` (relink on). No model
call; login node:

```bash
cat > "$EV/dangling.py" <<'EOF'
import json, pathlib, sys
# dangling.py <runs dir>: dangling_links and relink of every engine run (a run.json with extractor_specs).
for p in sorted(pathlib.Path(sys.argv[1]).rglob("run.json")):
    r = json.loads(p.read_text(encoding="utf-8"))
    if "extractor_specs" in r and r.get("mode") == "run":
        print(r.get("dangling_links", "MISSING"), r["settings"].get("relink", "off"), p.parent)
EOF
uv run python -I "$EV/dangling.py" "$RUNS" > "$EV/dangling.txt"
awk '{print $1, $2}' "$EV/dangling.txt" | sort | uniq -c        # expected: one line "<N> 0 on"
```

Good: every engine run says `0 on`. `MISSING off` means the run was made without relink (an old cache dir or an
old checkout): stop, **USER**. A count above 0 is a bug in the engine: list the run dirs and their
`funnel.json` `documents.<id>.dangling_links` entries in `failures.md` and report them (**USER**); do not drop the
runs from the table.

## 6. The deliverable: `reports/ev3b/summary.md`

As EV3 section 6 (cost column, B and C fields, `scored_types`), with these changes:

1. **Main table**, per corpus, three systems per question: `evidence-engine`, `rag-baseline (per_paper)`,
   `agent-baseline`. The RAG row is `rag-per-paper`: **k=2 on the main corpus, k=1 on the hard corpus**; write
   that under the table, together with "every paper is seen, so a left-out paper is the model's choice, not the
   retriever's". The agent rows are prompt v3, one run each.
2. **GLiNER confirm line**, one under each question's rows (both corpora): `GLiNER confirm: proposed=<n>
   confirmed=<n> dropped=<n>` from step 5, and one line under the main table: `dangling links: <total> over <N>
   engine runs` from step 5 (expected `0`).
3. **Extra comparisons**: the top-k global RAG row (`rag-baseline`, global, k 8) per question, **moved here** from
   the main table; then `rag-oracle` (label it a diagnostic), `regex-only`, `llm-only`, the two seeds (global RAG,
   spread of C over the grid and the two seeds only; there is no engine repeat).
4. **EV3 compared with EV3b**, one table per system: C per question in EV3 (read from
   `origin/results:reports/question-first/`, `git show`) and in EV3b, and one line on what changed (confirm: items
   dropped; per-paper: tokens; agent: v3). Name the cells that changed by more than 0.1.
5. **Diagnosis** (step 1): copy the two files `agent-repeats.md` and `rag-per-paper-failures.md`, and say whether the
   v3 runs and the 16,384-token runs fixed the failures.
6. Mapping check: "not repeated; one-check cell as smoke test" (step 2). The other items of EV3 section 6 (per-extractor
   A, GPU and GLiNER and versions, Failures, counterfactual) as written there. Limits: EV3 section 8, copied
   as is, last column filled; limit 4 now reads "the global RAG reads 8 passages; the main RAG row reads every paper".

**Paperwork before the hand-back** (the EV3 hand-back left "Pending final count." in `summary.md` and a running
`status` in `session.json`):

- `reports/ev3b/summary.md` contains no "Pending" text: every number is final, or a missing cell is written
  `not run: <reason>`.
- `reports/ev3b/session.json` has a **final** `status` (for example `finished: all 20 cells scored; hand-back
  pushed`, or `finished with failures: see failures.md`), the new `code_tag` (`ev3b-code`), `handback_branch`
  (`results-ev3b`) and `handback_tag` (`ev3b`), and `next_steps` empty.
- This must print nothing:

```bash
grep -n "Pending\|running" reports/ev3b/summary.md reports/ev3b/session.json
```

If it prints a line, fix that line (say what the state is now), and run it again. Do not commit until it prints nothing.

## 7. Hand-back

As EV3 section 7, with `reports/ev3b` in place of `reports/question-first` (the `R=` line and the `cp "$EV/failures.md"`
line) and:

```bash
git fetch origin
git checkout -b results-ev3b origin/results      # the only branch you create: it starts from the EV3 results
git add -f reports/ev3b                          # -f: .gitignore ignores runs/
n=$(git ls-files reports/ev3b/runs | wc -l)
if [ "$n" -gt 0 ]; then echo "runs files staged: $n"
else echo 'FAIL hand-back: no file under reports/ev3b/runs is staged; do not commit, USER'; fi
git status --short | grep -v '^A  reports/ev3b' ; echo "(nothing above but ' M llm-setup': only report files)"
git commit -m "reports: EV3b runs on Slurm"
git push origin results-ev3b
git tag -a ev3b -m "EV3b: question-first runs after the engine, RAG and agent fixes" && git push origin ev3b
```

The branch `results-ev3b` takes `reports/ev3b/` only (and keeps `reports/question-first/` as EV3 left it). Never
push to `main` or `results`. Send the user the tag `ev3b`, `reports/ev3b/summary.md`, and the prompt-version count of step 5.
