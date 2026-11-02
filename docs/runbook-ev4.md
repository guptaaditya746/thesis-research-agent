# Runbook: EV4, the general evidence system on Slurm (Codex)

EV4 makes the engine general: topics live in domain packs under `domains/` (`rag`, `drugtrials`, `ml`), and the
question kinds grow from four to seven. This session reruns the RAG topic with the EV4 code, runs the new
drug-trials topic, runs four checks on real papers and one arXiv demo, and hands back one report,
`reports/ev4/summary.md`, with the losses first. **This file is a differences document.** Everything not written
here is as in `docs/runbook-question-first.md` (called "EV3" below): the stack with GLiNER (its section 1),
`in-job.env`, `launch.sh`, the failed-call and retry rules, killed runs, the scoring fields, the Limits. Read EV3
and `docs/runbook-ev3b.md` ("EV3b") fully first. `docs/slurm-evidence-runbook.md` 0.3 still gives `$EV`,
`in-job.env`, `launch.sh`, `$AGENT_ROOT`.

Part A lists the steps done **before** this runbook is handed over, on Aditya's machine (not on Slurm). Codex
starts at section 0 and only checks that Part A is done (section 0 and 1 stop when it is not).

**What changed in the code (all on `ev4-code`)**

- Domain packs: every topic word, type and protocol is in `domains/<pack>/` (`pack.yaml`, `words.yaml`,
  `ontology.ttl`, `protocols/`, `questions.yaml`, `FROZEN.json`). RAG paths are `domains/rag/protocols/<id>.yaml`
  and `domains/rag/questions.yaml`. `evidence pack check <pack>` checks one pack.
- New kinds on drug trials: `chaining`, `limitations`, `builds_on` (besides effect, inventory, consistency,
  best). Every drug-trials run uses `--names on`: names of compared things, metrics and datasets are grouped
  across papers (`names.json`), and `run.json` counts the names left (`unresolved_names`).
- Reasoner, `--reason on` (the default): the run reads the pack's ontology, so a narrower metric answers a
  broader question metric, and links to an item of the wrong kind are flagged (`reason.json`, `link_flags`).
- Protocol lock and diff: every run writes `protocol.lock.json` (protocol, pack and ontology sha256, extractor
  ids); `evidence protocol diff A B` compares two protocols or two runs (exit 0 and `same` when nothing differs).
- Sealed runs: every run ends with `manifest.json` (`status: complete`, or `failed` with the error for a crashed
  run, which has no `run.json`). `evidence verify <run>` checks the hash chain and every file hash; **read its
  exit code** (0 good, 1 bad), never its printed JSON.
- `evidence estimate --protocol P --corpus C`: the calls and tokens a run would need, before it is made (D41).
- `evaluate losses`: the losses-first table per domain, with the cause of each engine loss and the cost per
  system; it opens with Tim's sentence. The baselines' mapping prompts are filled from the pack (`map-<kind>-v2`).
- Real-paper checks: `evaluate scirex`, `evaluate yun`, `evaluate scilead`, `evaluate edits`, `evaluate sheet`,
  `evaluate sheet-summary`. `evidence fetch` reads arXiv HTML first and converts PDFs with Docling (the `fetch`
  dependency group; used in Part A only).
- The engine has `--confirm llm` and `--relink on` as EV3b (defaults; `dangling_links` expected 0). The agent
  baseline uses prompt v3.

**Decisions by Aditya**

- The RAG topic is rerun with the EV4 code, not matched to old numbers (D36): EV3 and EV3b numbers are **never a
  comparison point** (spec 6.8). Do not copy them into the report.
- The per-paper RAG (`rag-per-paper`, k=2; k=1 on the 112-paper hard corpus) is the RAG row (29 Oct). No agent
  repeats, no engine repeats.
- RAG is scored on its four kinds; chaining, limitations and builds-on only on drug trials (D43).
- Real-paper checks are reported apart from the synthetic scores, never in the same table (D42).
- Papers and corpora are built on Aditya's machine and committed; only runs go to Slurm (D32). No `evidence
  fetch` and no `synth` on Slurm.
- The arXiv edit set holds number and name edits only, until Aditya decides on limitation edits (preflight F25).
- The paperwork is finished at hand-back: no "Pending" text in `summary.md`, a final `status` in `session.json`.

**Rules that differ from EV3**

- The code tag is **`ev4-code`**. The packs are frozen under their tags: `domains/rag` under `ev4-pack-rag-v1`,
  `domains/drugtrials` under `ev4-pack-drugtrials-v1`, `domains/ml` under `ev4-ml-pack` (the names Aditya
  tagged; if he gives others, use his). Every file of a pack folder that differs between its tag and `ev4-code`
  is logged in the report (section 1).
- The session directory is new: `export EV=/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-ev4`. Earlier
  session directories are never written.
- Save report files under `reports/ev4/`, on the branch **`results-ev4`** (made from `origin/results`), tagged
  **`ev4`**. Never push to `main` or `results`. Never touch the tags `ev3` or `ev3b`.
- `uv sync --locked` only (no `--all-groups`): the `fetch` group (Docling, torch) is not installed on Slurm (F44).
- `evidence estimate` before every Slurm run (section 2).
- Do not change code, packs, protocols, prompts, questions or corpora. A failure is recorded in
  `$EV/failures.md` (step, command, exit code, last 30 log lines); then go on with the next independent step.
- **USER** marks every stop: stop that step, write what you saw, and wait for the user.

## Part A. Before the hand-over: local steps (Aditya's machine, not Slurm)

Done in this order with Aditya's go; Codex does none of them. "Claude" is the builder session on Aditya's machine.
Each ends in a commit on the EV4 code branch, before the tag `ev4-code`.

1. **Benchmark downloads and pinned commits** (Claude). Clone `hyesunyun/llm-meta-analysis` at `1bc768d4` and
   `jayded/evidence-inference` at `a661e8c1` (`git checkout` the commit; `evaluate yun corpus` records the commits
   it finds). Download the SciREX release (github.com/allenai/SciREX, its `test.jsonl`) and the SciLead release
   (`https://aclanthology.org/attachments/2024.emnlp-main.453.data.zip`). Confirm the layouts the readers assume
   (Task 8, 9, 10 reports: SciREX `coref` salient clusters; SciLead link key, paper-key format, counts 43 / 295 /
   27). Write `tests/EV4/real/SOURCES.md`: each source's URL, commit or file sha256, licence. Commit the SciREX
   `test.jsonl` as `tests/EV4/real/scirex/test.jsonl` and the unpacked SciLead release as
   `tests/EV4/real/scilead/` (the scorers' gold); build `uv run evaluate yun corpus --repo <clone> --ei
   <evidence-inference>/annotations --out tests/EV4/corpora/real-yun` and commit it.
2. **Fill `domains/heldout.yaml`** (Claude; Aditya checks): the 120 PMCIDs of Yun et al.'s
   `annotated_rct_dataset.csv` under `yun2024`, the paper ids of SciLead (`evaluate scilead ids`) and SciREX
   under `scilead` and `scirex`. `synth draft` refuses an empty list.
3. **Build the drug-trials pack** (plan 2 Task 18; Claude, with Aditya's two review stops):
   - `synth draft --domain drugtrials ... --verify-model <another model>` from 5-10 real PMC OA RCT reports
     (none in `heldout.yaml`); **Aditya's first stop**: his ~10-minute review of `generator.yaml`;
   - hand-write the effect protocol's `synthesis` block (Task 18 Step 3b);
   - `synth trial --domain drugtrials ... --verify-model ...` until `"passed"` is true;
   - `synth build --domain drugtrials --name drug-s1 ... --out tests/EV4/corpora` (the corpus
     `tests/EV4/corpora/drug-s1-mixed`);
   - `packbuilder propose ... --verify-model ...`, or the D34 fallback `packbuilder helper ... --root <scratch>`
     then `packbuilder adopt --from <scratch>/drugtrials --into domains/drugtrials`; **Aditya's second stop**: his
     check of the proposed pack; then the other six protocols and `questions.yaml` by hand;
   - `packbuilder freeze domains/drugtrials`: it writes `FROZEN.json` and only **prints** the tag command; Aditya
     runs it.
4. **Confirm `ltx_page_main`** (Claude): open 3 live arXiv HTML pages and check that the reader's main-content
   selector `ltx_page_main` is on each. If not, fix `evidence/arxiv.py` before step 5.
5. **arXiv fetches** (Claude; Docling needs the `fetch` group once on this machine:
   `uv sync --group fetch --locked`):
   - the 5 arXiv RAG papers of the edit test: `evidence fetch --ids <file of the 5 ids> --out
     tests/EV4/corpora/real-arxiv5`; then a fresh subagent that sees only the 5 papers writes
     `evaluation/realpapers/data/arxiv-edits.yaml` (3-5 edits per paper, **number and name edits only**, each on a
     sentence that states a compared thing's measured value, each `find` exactly once in its paper:
     `evaluate edits apply` refuses otherwise, so run it once as the check); frozen and committed **before any
     run** ("data: arXiv edit set (frozen before runs)");
   - the demo corpus, about 30 papers: `evidence fetch --query "retrieval augmented generation" --category cs.CL
     --max 30 --out tests/EV4/corpora/real-arxiv-demo`;
   - the SciLead papers: `evaluate scilead ids --data tests/EV4/real/scilead --out <ids file>`, then `evidence
     fetch --ids <ids file> --out tests/EV4/corpora/real-scilead`.
   Aditya decides before the commit whether the papers' licences allow them in git (arXiv's default licence does
   not grant redistribution); if not, the corpora are copied to `$EV/corpora/` by hand and only their
   `manifest.json` is committed, and sections 5-6 read them from there.
6. **ml pack words and freeze** (Claude; Aditya tags): a fresh helper drafts `domains/ml/words.yaml` from 10
   SciREX **train** papers (none in `test.jsonl`), logged in `domains/ml/provenance.json`; `uv run pytest -q
   evidence/tests/test_no_topic_words.py`; `packbuilder freeze domains/ml`; Aditya tags `ev4-ml-pack`.
   The same for the rag pack: `packbuilder freeze domains/rag`; Aditya tags `ev4-pack-rag-v1`.
7. **The frontend Node pass** (Claude or Aditya, on a machine with Node 22; the fixtures on Linux):
   `npm --prefix webapp/web ci`, `npm --prefix webapp/web run gen:api`, `npm --prefix webapp/web test` (vitest),
   `npm --prefix webapp/web run typecheck`, `npm --prefix webapp/web run build`, commit `webapp/web/dist/`, and
   regenerate the mock fixtures (`ev-fixtures.json`) on Linux, then commit.
8. **Merge and tag** (Aditya): merge the EV4 branches into `main`, tag `ev4-code` there, push `main`, `ev4-code`
   and the three pack tags. Then he writes the call plan of section 2 into the hand-over message and hands this
   runbook to Codex.

## 0. Branch and setup (login node)

```bash
cd /mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent
git fetch origin --tags
export TAG_RAG=ev4-pack-rag-v1 TAG_DT=ev4-pack-drugtrials-v1 TAG_ML=ev4-ml-pack   # or the names the USER gave
for T in ev4-code "$TAG_RAG" "$TAG_DT" "$TAG_ML"; do
  git rev-parse --verify -q "$T^{commit}" > /dev/null || echo "FAIL step 0: no tag $T; stop, USER"
done
git checkout --detach ev4-code
git describe --tags                       # ev4-code; record this and `git rev-parse HEAD` in summary.md
git submodule update --init --recursive
git -C llm-setup log -1 --oneline         # record it; it must be the commit `git ls-tree HEAD llm-setup` names
git ls-tree HEAD llm-setup
uv sync --locked
uv run evidence run --help | grep -- '--names {'
uv run evidence run --help | grep -- '--reason {'
uv run evidence estimate --help | grep -- --from-run
uv run evaluate losses --help | grep -- --scores
```

`uv sync --locked` installs the main environment and the `dev` group (pytest), **not** the `fetch` group (Docling,
torch, several GB, and Docling downloads layout models on first use, which compute nodes may not reach). Nothing
on Slurm converts a PDF: the corpora come from Part A. Never run `uv sync --all-groups` here.

Stop (**USER**) if a tag is missing, `git checkout` fails, the submodule commit differs from `git ls-tree`, or one
of the four `grep` lines prints nothing. Check that Part A is in the checkout (each line prints a path; a missing
one is a stop, **USER**):

```bash
ls -d tests/EV2/corpora/rag-claude-s1-mixed tests/EV2/corpora/rag-tpl-hard-complex \
  tests/EV4/corpora/drug-s1-mixed tests/EV4/corpora/real-yun tests/EV4/corpora/real-arxiv5 \
  tests/EV4/corpora/real-arxiv-demo tests/EV4/corpora/real-scilead tests/EV4/real/scirex/test.jsonl \
  tests/EV4/real/scilead evaluation/realpapers/data/arxiv-edits.yaml \
  domains/drugtrials/FROZEN.json domains/ml/FROZEN.json domains/rag/FROZEN.json
grep -nE '^(yun2024|scilead|scirex): \[\]' domains/heldout.yaml   # prints nothing: every held-out list is filled
```

(If Part A step 5 left a corpus out of git, the USER says where it is under `$EV/corpora/`; use that path.)

Then EV3 section 1 (GPU report, the stack with GLiNER, `in-job.env`, `mkdir`), with the new `$EV`, and append
this session's variables. The first line drops EV2's `Q P PA` as EV3 1.6 does:

```bash
cat >> "$EV/in-job.env" <<EOF
unset Q P PA
export TAG_RAG=$TAG_RAG TAG_DT=$TAG_DT TAG_ML=$TAG_ML
export C_MAIN=$PWD/tests/EV2/corpora/rag-claude-s1-mixed
export C_HARD=$PWD/tests/EV2/corpora/rag-tpl-hard-complex
export C_DRUG=$PWD/tests/EV4/corpora/drug-s1-mixed
export R4=$PWD/reports/ev4
export RAG_QS="rag-factuality rag-hallucination rag-latency inv-metrics inv-methods inv-datasets cons-accuracy cons-hallucination best-accuracy best-hallucination"
export DT_QS="$(uv run python -c 'from evidence import questions; print(" ".join(q.id for q in questions.load("domains/drugtrials/questions.yaml")))')"
export GLINER_URL=http://127.0.0.1:8090
EOF
source "$EV/in-job.env"
mkdir -p "$EV"/{logs,runs,scores,cache,agent-work,estimates,frozen,check} "$R4/real"
echo "$RAG_QS" | wc -w; echo "$DT_QS"              # 10; the drug-trials ids (seven, one per kind)
```

Write `reports/ev4/session.json` now and keep it current (EV3b section 6, "Paperwork"): `code_tag` (`ev4-code`),
`commit`, `pack_tags` (the three), `handback_branch` (`results-ev4`), `handback_tag` (`ev4`), `plan` (section 2),
`status`, `next_steps`.

## 1. Offline check (login node, no model)

```bash
uv run pytest -q 2>&1 | tail -n 3          # record the passed / skipped count in summary.md
for P in rag drugtrials ml; do uv run evidence pack check "$P" || echo "FAIL pack check $P"; done
```

Every pack check exits 0. A failing test or pack check: stop, **USER**.

**The packs against their frozen tags.** Unpack each pack as its tag froze it, log every file that changed
after the tag, and diff every protocol against its frozen copy:

```bash
for X in "rag $TAG_RAG" "drugtrials $TAG_DT" "ml $TAG_ML"; do set -- $X
  mkdir -p "$EV/frozen/$1" && git archive "$2" "domains/$1" | tar -x -C "$EV/frozen/$1"
  echo "== $1 ($2): files changed after the tag"; git diff --stat "$2" ev4-code -- "domains/$1"
  for F in domains/$1/protocols/*.yaml; do
    echo "$F $(uv run evidence protocol diff "$EV/frozen/$1/$F" "$F" | tr '\n' ' ')"
  done
done 2>&1 | tee "$EV/frozen/report.txt"
```

Good: no file listed under "files changed after the tag", and every protocol line ends in `same`. Copy
`$EV/frozen/report.txt` into `reports/ev4/frozen.txt`. A changed file or a protocol that is not `same`: stop,
**USER** (the runs would be made from a pack nobody froze).

The frozen digests that section 7 compares every run's lock with:

```bash
uv run python - "$EV/frozen" > "$EV/frozen/digests.json" <<'EOF'
import json, sys
from pathlib import Path
from evidence.pack import load_pack
from evidence.reasoner import ontology_sha256
out = {}
for name in ("rag", "drugtrials", "ml"):
    root = Path(sys.argv[1]) / name / "domains"
    pack = load_pack(name, root=root)
    out[name] = {"pack_sha256": pack.sha256, "ontology_sha256": ontology_sha256(pack, root)}
print(json.dumps(out, indent=1))
EOF
cat "$EV/frozen/digests.json"
```

**One check run, sealed.** As EV3 section 2, with a regex-only run (no model), then the sealing checks:

```bash
uv run evidence run --protocol domains/rag/protocols/inv-datasets.yaml --corpus "$C_MAIN" --out "$EV/check" \
  --cache "$EV/check/cache" --extractors regex-only --strategy gaps --workers 3 --run-id check
uv run evidence verify "$EV/check/check" > "$EV/check/verify.json"; echo "verify exit $?"    # verify exit 0
uv run evidence replay "$EV/check/check" > /dev/null; echo "replay exit $?"                  # replay exit 0
uv run python -c 'import json, sys; print(json.load(open(sys.argv[1]))["status"])' "$EV/check/check/manifest.json"  # complete
uv run evidence protocol diff "$EV/check/check" "$EV/check/check"                            # same
```

**The drug-trials questions reach the baselines and the scorer.** `evaluate rag-baseline`, `agent-baseline` and
`score` take `--question-id`; it must know the drug-trials ids. This asks no model (the corpus does not exist):

```bash
for Q in $DT_QS; do
  uv run evaluate rag-baseline --question-id "$Q" --corpus "$EV/no-such-corpus" --out "$EV/check/probe-$Q" 2>&1 \
    | grep -q 'unknown question id' && echo "FAIL probe $Q: the baselines do not know the drug-trials ids"
done
```

Prints nothing when the ids are known. A `FAIL probe` line: stop, **USER** (section 4 cannot run its baselines
or its scores; sections 3, 5 and 6 can, so go on with them while the USER decides).

## 2. Estimate before every Slurm run (D41)

Before an engine run, `evidence estimate` gives its calls (`calls.low`, `calls.high`) and tokens from a regex-only
pass, with no model call. Run it for **every engine cell** of sections 3-6 before that section starts, and save
each as JSON:

```bash
cat > "$EV/protocol-of.py" <<'EOF'
# protocol-of.py <pack> <question-id>: the protocol file the question names in domains/<pack>/questions.yaml
import sys
from evidence import questions
path = f"domains/{sys.argv[1]}/questions.yaml"
entry = {q.id: q for q in questions.load(path)}[sys.argv[2]]
print(questions.protocol_file(entry.protocol, path).as_posix())
EOF
cat > "$EV/est.sh" <<'EOF'
#!/usr/bin/env bash
# est.sh <section>.<cell> <protocol> <corpus>: the estimate of one engine cell -> $EV/estimates/<section>.<cell>.json
uv run evidence estimate --protocol "$2" --corpus "$3" > "$EV/estimates/$1.json" || echo "FAIL estimate $1"
EOF
chmod +x "$EV/est.sh"
for N in "$C_MAIN" "$C_HARD"; do for Q in $RAG_QS; do
  "$EV/est.sh" "rag.$(basename "$N").$Q" "domains/rag/protocols/$Q.yaml" "$N"
done; done
for Q in $DT_QS; do
  "$EV/est.sh" "drugtrials.$(basename "$C_DRUG").$Q" "$(uv run python "$EV/protocol-of.py" drugtrials "$Q")" "$C_DRUG"
done
```

The real-paper and demo cells are estimated in sections 5 and 6 with the same `est.sh`, before their runs; run
the sum below again after each.

The **plan**: the USER gives one call budget per section in the hand-over message (`rag`, `drugtrials`, `scirex`,
`yun`, `scilead`, `edits`, `demo`); write it into `session.json` as `plan`. Then sum each section's `calls.high`:

```bash
uv run python - "$EV/estimates" "$R4/session.json" <<'EOF'
import json, sys
from pathlib import Path
plan = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")).get("plan", {})
sums = {}
for f in sorted(Path(sys.argv[1]).glob("*.json")):
    e = json.loads(f.read_text(encoding="utf-8"))
    section = f.name.split(".")[0]
    if section == "full":          # the whole SciREX split, only for choosing --limit (section 5)
        continue
    s = sums.setdefault(section, {"cells": 0, "low": 0, "high": 0, "input_high": 0, "output_high": 0})
    s["cells"] += 1; s["low"] += e["calls"]["low"]; s["high"] += e["calls"]["high"]
    s["input_high"] += e["tokens"]["input"]["high"]; s["output_high"] += e["tokens"]["output"]["high"]
for section, s in sums.items():
    p = plan.get(section)
    flag = "STOP, USER: no plan" if p is None else ("STOP, USER: over 2x plan" if s["high"] > 2 * p else "ok")
    print(section, s, "plan", p, flag)
EOF
```

A `STOP` line: do not start that section; send the USER the line and wait. Copy `$EV/estimates/` to
`reports/ev4/estimates/`; section 8 puts the estimate next to the calls the runs made.

## 3. RAG rerun

The four kinds of `domains/rag/questions.yaml` (effect, inventory, consistency, best: the ten ids of `$RAG_QS`) x
the two RAG corpora (`$C_MAIN`, `$C_HARD`) x three systems: the engine (cascade, `gaps`, the defaults
`--confirm llm --relink on --reason on`), `rag-per-paper` (the RAG row; k=2, k=1 on the hard corpus), the agent
baseline (prompt v3). EV3's numbers are never a comparison point (spec 6.8).

`cell.sh` is EV3's `one.sh` (section 4) with three changes: it takes the pack first, the RAG system is
`rag-per-paper` (not the global top-k 8), and a drug-trials engine run gets `--names on`. The run layout is
EV3's, so the web app finds the runs. `cell.sh` finds the protocol through `protocol-of.py` (section 2). Write
the two scripts once:

```bash
cat > "$EV/cell.sh" <<'EOF'
#!/usr/bin/env bash
# cell.sh <pack> <question-id> <corpus-dir> [retry|rerun]: engine + rag-per-paper + agent baseline + score.
# As EV3 one.sh: skips a finished system; `retry` and `rerun` move the engine run to runs/failed/<corpus>/ first.
set -u
PK=$1; Q=$2; C=$3; MODE=${4:-}; N=$(basename "$C")
case $MODE in ""|retry|rerun) ;; *) echo "FAIL cell.sh $Q $N: unknown mode '$MODE' (retry or rerun)"; exit 2;; esac
P=$(uv run python "$EV/protocol-of.py" "$PK" "$Q") || { echo "FAIL cell.sh $Q: no protocol in domains/$PK"; exit 2; }
G=$Q-cascade-gaps; [ "$Q" = rag-factuality ] && G=cascade-gaps   # the engine run's group, as the web app names it
BN=$N.$Q; [ "$Q" = rag-factuality ] && BN=$N        # the baselines' run name, as the web app names it
NAMES=(); [ "$PK" = drugtrials ] && NAMES=(--names on)
K=2; [ "$N" = rag-tpl-hard-complex ] && K=1         # per-paper passages: k=1 on the 112-paper corpus
RUN=$RUNS/$G/$N; mkdir -p "$RUNS/$G" "$SCORES/$N"
if [ -n "$MODE" ] && [ -e "$RUN" ]; then
  mkdir -p "$RUNS/failed/$N"; mv "$RUN" "$RUNS/failed/$N/$Q-$(date +%Y%m%dT%H%M%S)"
fi
RETRY=(); [ "$MODE" = retry ] && RETRY=(--retry-errors)
if [ -f "$RUN/run.json" ]; then
  echo "skip engine $Q $N: done"
elif [ -e "$RUN" ]; then
  echo "FAIL engine $Q $N: a run dir without run.json is in the way; cell.sh $PK $Q $C rerun"
else
  uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/$G" --cache "$CACHE/engine-$N" \
    --model orch-model --strategy gaps --workers 3 --run-id "$N" ${NAMES[@]+"${NAMES[@]}"} ${RETRY[@]+"${RETRY[@]}"}
  rc=$?
  if [ "$rc" -eq 2 ] && [ -f "$RUN/run.json" ]; then echo "FAIL engine-errors $Q $N: cell.sh $PK $Q $C retry"
  elif [ "$rc" -ne 0 ]; then echo "FAIL engine $Q $N (exit $rc)"; fi
fi
if [ -f "$RUNS/rag-per-paper/$BN/answer.json" ]; then
  echo "skip rag $Q $N: done"
else
  uv run evaluate rag-baseline --corpus "$C" --question-id "$Q" --out "$RUNS/rag-per-paper/$BN" \
    --cache "$CACHE/rag-per-paper-$N.jsonl" --model orch-model --retrieval per_paper --k "$K" || echo "FAIL rag $Q $N"
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
for s in rag-per-paper agent-baseline; do
  [ -f "$RUNS/$s/$BN/answer.json" ] && ARGS+=(--baseline "$RUNS/$s/$BN/answer.json")
done
if [ "${#ARGS[@]}" -eq 0 ]; then echo "FAIL score $Q $N: no answer to score"
else uv run evaluate score "${ARGS[@]}" --corpus "$C" --question-id "$Q" --out "$SCORES/$N/$Q" || echo "FAIL score $Q $N"; fi
EOF
cat > "$EV/grid.sh" <<'EOF'
#!/usr/bin/env bash
# grid.sh <pack> <corpus-dir> <question-id>...: cell.sh for each question, one after another
set -u
PK=$1; C=$2; shift 2
for Q in "$@"; do "$EV/cell.sh" "$PK" "$Q" "$C"; done
EOF
chmod +x "$EV/cell.sh" "$EV/grid.sh"
```

One cell first, checked as EV3 section 4 says (run dir, the two answers, `report.md`) and the agent's prompt
version `v3` (EV3b section 5); then the two corpora side by side (one process per corpus, as EV3: two processes
never append to one cache file):

```bash
"$EV/launch.sh" one-check "$EV/cell.sh" rag inv-datasets "$C_MAIN"; tail -n 1 "$EV/logs/one-check.launch"
nohup "$EV/launch.sh" rag-main "$EV/grid.sh" rag "$C_MAIN" $RAG_QS > /dev/null 2>&1 &
nohup "$EV/launch.sh" rag-hard "$EV/grid.sh" rag "$C_HARD" $RAG_QS > /dev/null 2>&1 &
```

The hard `rag-per-paper` (k=1, 112 papers) needs `max_model_len` of 65536 or more in the `orch` line of the
profile (EV3 4b item 1); otherwise write "rag-per-paper not run on hard: max_model_len <n>" in the summary.
Retries, reruns and killed runs as EV3 section 4, with `cell.sh <pack> <question> <corpus> retry|rerun` and a new
step name for each launch. A failed cell is retried at most twice and recorded under Failures; no repeats.

## 4. Drug trials

All kinds of `domains/drugtrials/questions.yaml` (`$DT_QS`: effect, inventory, consistency, best, chaining,
limitations, builds_on) on `$C_DRUG` x the same three systems. The baselines answer with the mapping prompts of
each kind (`map-<kind>-v2`, filled from the pack); the engine runs with `--names on` (`cell.sh` adds it for the
pack `drugtrials`). Only after the probe of section 1 printed nothing.

```bash
"$EV/launch.sh" dt-check "$EV/cell.sh" drugtrials "$(echo $DT_QS | cut -d' ' -f1)" "$C_DRUG"; tail -n 1 "$EV/logs/dt-check.launch"
nohup "$EV/launch.sh" dt-grid "$EV/grid.sh" drugtrials "$C_DRUG" $DT_QS > /dev/null 2>&1 &
```

It may run beside the two RAG grids (its own corpus, so its own cache files). Check every drug-trials engine
run's `run.json`: `settings.names` is `on` and `unresolved_names` is there (section 7 counts it). For the
chaining question, `comparisons.json` in its run dir is not empty; an empty one is a note under Failures.

## 5. Real-paper checks

Each check runs the engine (no baselines) and writes `real.json` and `real.md` under `reports/ev4/real/<name>/`.
Its runs are under `$RUNS/real/`, never under `$SCORES`, so `evaluate losses` never mixes them with the synthetic
scores. Estimate each before its run (section 2, `est.sh`, then the sum), then launch the run in the job.

**SciREX** (names at mention and salient-cluster level, D21). The limit comes from the estimate of the whole
test split:

```bash
uv run evaluate scirex corpus --jsonl tests/EV4/real/scirex/test.jsonl --out "$EV/corpora/scirex-all"
"$EV/est.sh" full.scirex domains/ml/protocols/names.yaml "$EV/corpora/scirex-all"
uv run python -c 'import json, sys; e = json.load(open(sys.argv[1])); print(e["papers"], e["calls"]["high"])' "$EV/estimates/full.scirex.json"
```

`--limit` N = the papers that fit the `scirex` plan: `floor(plan / (calls.high / papers))`, at most all. Write N
and how you got it into `session.json` (`scirex_limit`). Then, with `NLIM` set to N:

```bash
uv run evaluate scirex corpus --jsonl tests/EV4/real/scirex/test.jsonl --out "$EV/corpora/scirex" --limit "$NLIM"
"$EV/est.sh" scirex.limit domains/ml/protocols/names.yaml "$EV/corpora/scirex"
"$EV/launch.sh" real-scirex uv run evidence run --protocol domains/ml/protocols/names.yaml --corpus "$EV/corpora/scirex" \
  --out "$RUNS/real/scirex" --cache "$CACHE/real-scirex" --model orch-model --strategy gaps --workers 3 --run-id scirex
uv run evaluate scirex score --run "$RUNS/real/scirex/scirex" --corpus "$EV/corpora/scirex" \
  --out "$R4/real/scirex" --estimate "$EV/estimates/scirex.limit.json"
```

**Yun et al. + Evidence Inference** (drug trials, A / B / C separately, D42). The corpus is Part A's (120 papers):
there is no `--limit`, so if the estimate is over 2x the `yun` plan, stop (**USER**).

```bash
QE=$(uv run python -c 'from evidence import questions; print(next(q.id for q in questions.load("domains/drugtrials/questions.yaml") if q.kind == "effect"))')
PY=$(uv run python "$EV/protocol-of.py" drugtrials "$QE")          # the drug-trials effect protocol
"$EV/est.sh" yun.real-yun "$PY" tests/EV4/corpora/real-yun
"$EV/launch.sh" real-yun uv run evidence run --protocol "$PY" --corpus "$PWD/tests/EV4/corpora/real-yun" \
  --out "$RUNS/real/yun" --cache "$CACHE/real-yun" --model orch-model --strategy gaps --workers 3 --run-id yun --names on
uv run evaluate yun score --run "$RUNS/real/yun/yun" --corpus tests/EV4/corpora/real-yun --out "$R4/real/yun"
```

`real.md` prints `SOURCES` and the commits found: they must be `1bc768d4` and `a661e8c1`. Report the
`prompt_ids_not_in_ei` count and `complete_share` (about 0.59 expected) as they come.

**SciLead** (ML values, best per leaderboard, pairwise order, D42). The papers were fetched in Part A (`fetch
--ids`); the gold is the release in `tests/EV4/real/scilead`:

```bash
"$EV/est.sh" scilead.real-scilead domains/ml/protocols/values.yaml tests/EV4/corpora/real-scilead
"$EV/launch.sh" real-scilead uv run evidence run --protocol domains/ml/protocols/values.yaml \
  --corpus "$PWD/tests/EV4/corpora/real-scilead" --out "$RUNS/real/scilead" --cache "$CACHE/real-scilead" \
  --model orch-model --strategy gaps --workers 3 --run-id scilead --names on
uv run evaluate scilead score --run "$RUNS/real/scilead/scilead" --corpus tests/EV4/corpora/real-scilead \
  --data tests/EV4/real/scilead --out "$R4/real/scilead"
```

**The arXiv edit test** (the frozen `evaluation/realpapers/data/arxiv-edits.yaml`, number and name edits). One
edited corpus per edit; the engine runs on the original and on each edited corpus with the effect protocol
`rag-factuality` (its compared things and measured values are what the edits change), all with one cache, one
after another (the unchanged papers come from the cache):

```bash
E4=evaluation/realpapers/data/arxiv-edits.yaml
uv run evaluate edits apply --corpus tests/EV4/corpora/real-arxiv5 --edits "$E4" --out "$EV/corpora/edits"
"$EV/est.sh" edits.original domains/rag/protocols/rag-factuality.yaml tests/EV4/corpora/real-arxiv5
cat > "$EV/edits.sh" <<'EOF'
#!/usr/bin/env bash
# edits.sh: the original run, then one run per edited corpus (run id = edit id), one cache
set -u
PE=domains/rag/protocols/rag-factuality.yaml
run() { uv run evidence run --protocol "$PE" --corpus "$1" --out "$2" --cache "$CACHE/real-edits" \
          --model orch-model --strategy gaps --workers 3 --run-id "$3" || echo "FAIL edits $3"; }
[ -f "$RUNS/real/edits-original/original/run.json" ] || run "$REPO/tests/EV4/corpora/real-arxiv5" "$RUNS/real/edits-original" original
for D in "$EV"/corpora/edits/*/; do
  I=$(basename "$D"); [ -f "$RUNS/real/edits/$I/run.json" ] || run "$D" "$RUNS/real/edits" "$I"
done
EOF
chmod +x "$EV/edits.sh"
"$EV/launch.sh" real-edits "$EV/edits.sh"; tail -n 1 "$EV/logs/real-edits.launch"
uv run evaluate edits check --original "$RUNS/real/edits-original/original" --runs "$RUNS/real/edits" \
  --edits "$E4" --corpora "$EV/corpora/edits" --out "$R4/real/edits"
```

Report the share carried through per part (`item`, `link`, `answer`) and the edits left out as not testable
(`None`), as `real.md` lists them. This shows the system follows the text, not that it is right.

## 6. arXiv demo

The frozen RAG protocols on the about 30 papers of Part A's `tests/EV4/corpora/real-arxiv-demo` (built by
`evidence fetch`, HTML first), engine only, no ground truth:

```bash
for Q in $RAG_QS; do "$EV/est.sh" "demo.real-arxiv-demo.$Q" "domains/rag/protocols/$Q.yaml" tests/EV4/corpora/real-arxiv-demo; done
cat > "$EV/demo.sh" <<'EOF'
#!/usr/bin/env bash
# demo.sh: every RAG protocol on the arXiv demo corpus, one after another (run dir $RUNS/real/demo/<question>/demo)
set -u
for Q in $RAG_QS; do
  [ -f "$RUNS/real/demo/$Q/demo/run.json" ] && continue
  uv run evidence run --protocol "domains/rag/protocols/$Q.yaml" --corpus "$REPO/tests/EV4/corpora/real-arxiv-demo" \
    --out "$RUNS/real/demo/$Q" --cache "$CACHE/real-demo" --model orch-model --strategy gaps --workers 3 \
    --run-id demo || echo "FAIL demo $Q"
done
EOF
chmod +x "$EV/demo.sh"
nohup "$EV/launch.sh" real-demo "$EV/demo.sh" > /dev/null 2>&1 &
```

Then the hand-check sheet of the first 5 papers of the `rag-factuality` run (every item with its source sentence):

```bash
mkdir -p "$R4/real/arxiv-demo"
uv run evaluate sheet --run "$RUNS/real/demo/rag-factuality/demo" --corpus tests/EV4/corpora/real-arxiv-demo \
  --papers 5 --out "$R4/real/arxiv-demo/sheet.csv"
```

Send the sheet to the USER, who fills `right_or_wrong` (**USER**). When it comes back marked:

```bash
uv run evaluate sheet-summary "$R4/real/arxiv-demo/sheet.csv" --out "$R4/real/arxiv-demo"
```

The sampled precision with its Wilson 95% interval is labelled "demonstration, not an evaluation" wherever it is
written. If the marks have not come back by the hand-back, write `not run: the sheet waits for the USER's marks`.

## 7. Checks, per run

For every engine run dir under `$RUNS` (the grids, the real-paper and demo runs), except `$RUNS/failed/`. No
model call; login node:

```bash
cat > "$EV/runcheck.py" <<'EOF'
# runcheck.py <frozen digests.json> <run dir>: one line per run (status, links, names, flags, lock vs frozen)
import json, sys
from pathlib import Path
frozen = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
run = Path(sys.argv[2])
def read(name):
    p = run / name
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
manifest, record, lock, reason = read("manifest.json"), read("run.json"), read("protocol.lock.json"), read("reason.json")
pack = lock.get("pack", {}).get("name")
want = frozen.get(pack, {})
pack_ok = bool(want) and lock["pack"]["sha256"] == want["pack_sha256"]
onto_ok = bool(want) and lock.get("ontology_sha256") == want["ontology_sha256"]
print(f"status={manifest.get('status')} dangling={record.get('dangling_links', 'MISSING')} "
      f"unresolved={record.get('unresolved_names', '-')} reason={record.get('settings', {}).get('reason', 'off')} "
      f"link_flags={len(reason.get('link_flags', []))} pack={pack} pack_frozen={pack_ok} ontology_frozen={onto_ok}")
EOF
find "$RUNS" -name run.json -not -path "$RUNS/failed/*" | sort | while read -r F; do
  R=$(dirname "$F"); [ -f "$R/protocol.yaml" ] || continue          # an engine run, not a baseline answer
  uv run evidence verify "$R" > /dev/null; V=$?                       # the exit code: 0 good
  echo "${R#"$RUNS"/} verify_exit=$V $(uv run python "$EV/runcheck.py" "$EV/frozen/digests.json" "$R")"
done | tee "$EV/runcheck.txt"
```

Good, on every line:

- `verify_exit=0` (`evidence verify` checks the chain and every file hash against `manifest.json`; judge it only by
  its exit code);
- `status=complete`;
- `dangling=0` (EV3b section 5: `MISSING` is a stop, **USER**; above 0 is an engine bug: list it in `failures.md`
  and report it, keep the run in the table);
- `unresolved=<n>` on every drug-trials run (reported, not a failure; `-` on a run without `--names on`);
- `reason=on`, and `link_flags=<n>` counted (report the total per pack);
- `pack_frozen=True` and `ontology_frozen=True`: the lock's pack and ontology digests equal the frozen tag's.

A `False`, a `verify_exit` other than 0 or a status other than `complete`: stop, **USER**. Also as before: the
failed-call count per run (EV3 section 5) and the agent prompt version count (EV3b section 5, every line `v3`).
Failed and killed runs go to `$RUNS/failed/<corpus>/` (cell.sh `retry` / `rerun`, as EV3); a crashed run there has
`manifest.json` with `status: failed` and its error, and no `run.json`. List them under Failures with that error.

## 8. The deliverable: `reports/ev4/summary.md`

```bash
uv run evaluate losses --scores "$SCORES" --out "$R4/losses"
```

`summary.md`, in this order:

1. **Losses first**: the content of `reports/ev4/losses/losses.md` as it is: Tim's sentence opens the comparison,
   then per domain (`rag`, `drugtrials`) the losses-first table, each engine loss with its cause line (missed,
   wrongly linked, names not grouped, wrong rule). Under it, per corpus, the A / B / C table of EV3 section 6
   (three systems per question; the RAG row is `rag-per-paper`, k=2 main, k=1 hard: "every paper is seen, so a
   left-out paper is the model's choice, not the retriever's"), the GLiNER confirm line (EV3b section 5) and
   `dangling links: <total> over <N> engine runs`. The B and C fields of the three new kinds are those `report.md`
   shows for them; copy them by name.
2. **Cost per system**: calls, input and output tokens per system and domain (the cost columns of `losses.md`),
   next to the estimate of section 2 (sum of `calls.low` / `calls.high` per section) and the plan.
3. **Real-paper checks**, apart from everything above: SciREX (with N and how it was chosen), Yun et al. + Evidence
   Inference (A, B, C separately), SciLead, the edit test; each the headline lines of its `real.md`, with a link
   to `real/<name>/real.md`. Never in the synthetic tables.
4. **Demo**: the arXiv demo's runs (papers, items per question) and the sampled precision with its interval,
   headed "demonstration, not an evaluation".
5. **Checks** (section 7: the `runcheck.txt` totals), **Frozen packs** (section 1: `frozen.txt`, the files changed
   after a tag, or "none"), **Versions** (EV3 section 6 item 4: commit, vLLM, served models, GPU and GLiNER),
   **Failures** (every `FAIL` line and what you did).
6. **Limits**: EV3 section 8, copied, with limit 4 as EV3b reads it ("the main RAG row reads every paper"), plus:
   the drug-trials corpus is synthetic on one generator recipe; the real-paper checks are small and each scores
   only what its gold holds; the demo precision rests on one hand-checked sheet.

**Paperwork** (as EV3b): no "Pending" text in `summary.md`; a missing cell is `not run: <reason>`. `session.json`
has a final `status`, `code_tag` `ev4-code`, `handback_branch` `results-ev4`, `handback_tag` `ev4`, and
`next_steps` empty. This must print nothing:

```bash
grep -n "Pending\|running" reports/ev4/summary.md reports/ev4/session.json
```

If it prints a line, fix that line (say what the state is now) and run it again. Do not commit until it prints
nothing.

## 9. Hand-back

As EV3 section 7 (the run files under `reports/ev4/runs/`, the score dirs, the caches), with `reports/ev4` in
place of `reports/question-first`: `R=$PWD/reports/ev4`, the score dirs from `$SCORES`, the run files from
`$RUNS` (the real-paper and demo runs under `runs/real/` come along; `$RUNS/failed` is kept), and
`cp "$EV/failures.md" "$R/"`. The `reports/ev4/real/` folders are already in place.

```bash
git fetch origin
git checkout -b results-ev4 origin/results      # the only branch you create
grep -qxF 'reports/** -text' .gitattributes 2>/dev/null || printf 'reports/** -text\n' >> .gitattributes
git add .gitattributes
git commit -m "reports: keep report files byte for byte (reports/** -text)"   # the FIRST commit, before any report
git add -f reports/ev4                           # -f: .gitignore ignores runs/
n=$(git ls-files reports/ev4/runs | wc -l)
if [ "$n" -gt 0 ]; then echo "runs files staged: $n"
else echo 'FAIL hand-back: no file under reports/ev4/runs is staged; do not commit, USER'; fi
git status --short | grep -v '^A  reports/ev4' ; echo "(nothing above but ' M llm-setup': only report files)"
git commit -m "reports: EV4 runs on Slurm"
git push origin results-ev4
git tag -a ev4 -m "EV4: RAG rerun, drug trials, real-paper checks, arXiv demo" && git push origin ev4
```

The `.gitattributes` commit comes first (preflight F29): `results-ev4` starts from `origin/results`, which has no
such line, and without it a Windows checkout of the reports rewrites their line ends and breaks their hashes. If
`.gitattributes` already had the line, `git commit` says "nothing to commit": go on. The branch `results-ev4`
takes `.gitattributes` and `reports/ev4/` only. Never push to `main` or `results`. Send the user the tag `ev4`,
`reports/ev4/summary.md`, the prompt-version count of section 7 and the `runcheck.txt` totals.
