# Runbook: the general evidence system on Slurm (Codex)

This is the hand-off for the general system merged on `main` (word list written by the model, papers and
claims, ontology reasoning, the plan page, DSPy tuning, the whole-run commands). Claude built it; Codex tests it on
Slurm and copies every run folder back. **This file is a differences document.** The stack (profile `orch-3x40` with
GLiNER), `in-job.env`, `in-job.sh`, `launch.sh`, the failed-call and retry rules and `$EV/failures.md` are as in
`docs/runbook-question-first.md` (section 1) and `docs/slurm-evidence-runbook.md` (section 0.3). Read those first.

Rules (from Aditya, 3 Nov):

- One model for everything: `orch-model` (Qwen). The paper writer is Claude (laptop); the word list is written by
  `orch-model`, a different family, so the **leak split uses Claude-written corpora only** (`tests/EV2/corpora/rag-claude-*`).
- Do not change code, packs, prompts, questions or corpora. A failure goes into `$EV/failures.md` (step, command, exit
  code, last 30 log lines); then go on with the next independent step. **USER** marks a stop: stop that step, write what
  you saw, wait for Aditya.
- Never invent a flag: `uv run evidence --help`, `uv run evaluate --help` and each subcommand's `--help` are the truth.
- No pilot run. An empty answer is a valid answer ("No evidence found"). Every number comes with its run folder.
- Size: a fixed sample of 10 questions per real set (`--sample 10 --seed 0`); the rest only if time is left.
- Cut order if time runs short: materials sets (SOFC-Exp, MeasEval) first, then links and builds-on. Words, papers, graph,
  planner, SciLead, SciREX, CochraneForest, the RAG baseline and the off-template check are never cut.
- Windows note (for Aditya, not Codex): `evaluation/tests/test_agentic_agent.py` and `test_runner.py` import only on Linux
  (SIGALRM, SIGKILL). They run in section 1 on the cluster.

Success lines below say what "good" looks like. Exit codes: read them, not printed JSON.

## 0. Setup (login node)

```bash
git fetch origin && git checkout main && git pull --ff-only && git log -1 --oneline   # expect: the handoff docs commit or later
uv sync --locked                                                              # no --all-groups: Docling (torch) comes in 3.5 only
export EV=/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-general           # new session dir; older ones are never written
mkdir -p "$EV"/{logs,corpora,runs,scores,cache,real,ontology,plans,proposals}
```

Start the stack as in `docs/runbook-question-first.md` section 1 (GLiNER included), then write `$EV/in-job.env`,
`in-job.sh` and `launch.sh` as there, with these extra lines in `in-job.env`:

```bash
export RUNS=$EV/runs SCORES=$EV/scores CACHE=$EV/cache REAL=$EV/real PLANS=$EV/plans
export EV_ONTOLOGY_DIR=$EV/ontology            # MeSH / CS-KG / QUDT files (section 2); never committed
export EV_PLAN_CORPUS=$EV/corpora/rag-claude-s1-mixed   # only for plan runs started from the web page
export SCILEAD_DATA=$REAL/scilead              # the unpacked SciLead release (section 3)
export Q="Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?"
```

**Success:** `git log` shows the runbook commit; `uv run evidence --help` lists `run estimate tune fetch propose ...`;
`curl -s $LITELLM_BASE_URL/models` (inside the job) names `orch-model`.

Every long step below runs as `nohup "$EV/launch.sh" <step> <command> > /dev/null 2>&1 &`, one at a time, as in EV4.
Short checks run directly with `"$EV/in-job.sh" <command>`.

## 1. Offline checks (login node, no model)

```bash
uv run pytest evidence synth evaluation modelcall webapp -q          # all of it, on Linux
uv run evidence pack check rag                                       # exit 0
uv run evidence pack check ml                                        # exit 0
uv run evidence estimate --protocol domains/rag/protocols/rag-factuality.yaml \
  --corpus tests/EV2/corpora/rag-claude-s1-mixed --strategy gaps > "$EV/estimate-s1-mixed.json"   # exit 0
```

**Success:** pytest has no failures (skips are fine; the two Linux-only files ran); both pack checks exit 0; the
estimate prints calls and tokens. If pytest fails: record, and go on with sections that do not depend on the failing test.

## 2. Ontology files (login node, network)

MeSH (medicine), CS-KG (computer science) and the full QUDT units go into `$EV_ONTOLOGY_DIR`. The MeSH URL in
`evidence/ontology/sources.py` (`PINNED["mesh"]["url"]`, the current year's `descYYYY.xml`) is **untested**; CS-KG has no
URL and needs `$EV_CSKG_URL` (**USER** gives it; without it CS stays on `domains/rag/ontology.ttl`, which is fine).

```bash
uv run python -c "from evidence.ontology.sources import fetch; print(fetch('qudt'))"     # a download that does not parse is refused
uv run python -c "from evidence.ontology.sources import fetch; print(fetch('mesh'))"     # several minutes; parses a large XML
uv run python -c "from evidence.ontology.sources import fetch; print(fetch('cskg'))"     # only when $EV_CSKG_URL is set
uv run python -c "from evidence.ontology.sources import ontology_hashes; import json; print(json.dumps(ontology_hashes(), indent=1))" | tee "$EV/ontology-hashes.json"
```

**Success:** each `fetch` prints a path under `$EV/ontology/`; the last command prints one sha256 per file. Write the
hashes into `$EV/ontology-hashes.json` and hand them back: Aditya pastes them into `PINNED[...]["sha256"]` in
`evidence/ontology/sources.py` (Codex does not edit code). A wrong URL, a 404 or an HTML page: record the error text and
the URL that failed. Without the MeSH file medicine runs with "reasoning off: no tree" (not a crash).

## 3. Real sets (login node, then the job)

Layouts of CochraneForest, SOFC-Exp and MeasEval are **assumed, not verified** (their outputs say `layout_verified: false`).
Everything here is read-only until a **USER** stop is cleared.

3.1 **Sources and licences.** Aditya puts each release under `$REAL/<set>/` (his decision per source, as EV4 Part A):
`$REAL/scilead/` (unpacked release), `$REAL/scirex/test.jsonl`, `$REAL/cochraneforest/release.json`,
`$REAL/sofc/sofc.json`, `$REAL/measeval/measeval.json`. **USER stop:** a missing set is skipped and listed in the report;
CochraneForest also needs `release.json` to say `"released": true` and a CC-BY/CC0 licence, else `to_corpus` refuses.

3.2 **Verify the layouts** (print the real keys next to the assumed ones; any difference is a **USER** stop for that set,
never a code edit):

```bash
uv run python -c "import json,sys; d=json.load(open(sys.argv[1]+'/release.json',encoding='utf-8')); print(sorted(d)); print(sorted(d['plots'][0])); print(sorted(d['plots'][0]['studies'][0]))" "$REAL/cochraneforest"
# assumed: release.json {licence, released, plots[{id, question, conclusion, studies[{id, direction, text}]}]}
uv run python -c "import json,sys; d=json.load(open(sys.argv[1]+'/sofc.json',encoding='utf-8'))['papers']; print(sorted(d[0])); print(sorted(d[0]['values'][0])); print(sorted(d[0]['experiments'][0]))" "$REAL/sofc"
# assumed: sofc.json {papers[{id, text, values[{value, unit, material, measure}], experiments[{id, slots}]}]}
uv run python -c "import sys; from evaluation.realpapers import measeval; print(measeval.fields(sys.argv[1]))" "$REAL/measeval"
# assumed: measeval.json {fields, papers[{id, text, field, quantities[{value, unit, entity}]}]}; fields unlisted = "unverified"
uv run python -c "import sys; from evaluation.realpapers import sofc; print(sofc.label_check(sys.argv[1])); print(sofc.LOWER_IS_BETTER)" "$REAL/sofc"
```

**Success:** the key lists equal the assumed ones; `label_check` says `complete: true`. **SOFC lower-is-better list:** list
every measure with its direction and **USER** checks it (the list is `("resistance", "degradation")`; a measure such as
"area specific resistance" is lower-is-better, "power density" is not):

```bash
uv run python -c "import sys; from evaluation.realpapers import sofc; print('\n'.join(f'{q.gold[\"measure\"]}\t{\"higher\" if q.gold[\"higher_is_better\"] else \"lower\"}\t{q.question}' for q in sofc.questions(sys.argv[1])))" "$REAL/sofc" | tee "$EV/sofc-directions.tsv"
```

3.3 **Corpora** (the set's `corpus` folders; `manifest.json` + `papers/`):

```bash
uv run evaluate scirex corpus --jsonl "$REAL/scirex/test.jsonl" --out "$REAL/scirex/corpus" --limit 40
uv run evaluate scilead ids --data "$SCILEAD_DATA" --out "$REAL/scilead/ids.txt"        # prints the papers with no arXiv id
uv run evidence fetch --ids "$REAL/scilead/ids.txt" --out "$REAL/scilead/corpus"          # arXiv HTML first, Docling for PDFs (3.5)
uv run python scripts/real-set-prep.py cochrane-corpus --src "$REAL/cochraneforest"       # prints "left out: N of M (no open full text)"
uv run python scripts/real-set-prep.py sofc-corpus --src "$REAL/sofc"                     # same line for SOFC
```

`--limit` for SciREX: run `evidence estimate` on the corpus first and keep the run inside about 6 h (as EV4 did).
**Success:** every `corpus/manifest.json` exists; the left-out lines are copied into the report.

3.4 **Key records, the 27 boards.** The SciLead / SciREX answer-key mapping (records for the synthesis-vs-extraction
split) has only been tried on fixtures:

```bash
uv run pytest evaluation/tests/test_real_questions_cs.py -q        # with SCILEAD_DATA set it must count 27 boards, not skip
uv run python -c "import sys; from evaluation.realpapers import scilead, scirex; q=scilead.questions(sys.argv[1]); print(len(q), sum(len(x.records or []) for x in q)); q=scirex.questions(sys.argv[2]); print(len(q), sum(len(x.records or []) for x in q))" "$SCILEAD_DATA" "$REAL/scirex/test.jsonl"
```

**Success:** `27 <records>` for SciLead (a test that skips = `SCILEAD_DATA` not set right: record), and SciREX questions
with records greater than 0. A board with 0 records says "not available" in the error split (fine, but record which).

3.5 **Real Docling conversion** (tests monkeypatch it). The `fetch` group brings torch; keep it out of the stack's env:

```bash
UV_PROJECT_ENVIRONMENT="$EV/venv-fetch" uv sync --locked --group fetch
head -n 3 "$REAL/scilead/ids.txt" > "$EV/ids-pdf.txt"
UV_PROJECT_ENVIRONMENT="$EV/venv-fetch" uv run evidence fetch --ids "$EV/ids-pdf.txt" --out "$EV/docling-check"
```

**Success:** exit 0; `$EV/docling-check/papers/*.md` hold readable text with tables as Markdown rows (open two and look; a
garbled table is a finding). Exit 1 with "Docling is missing": the sync failed; record it. Do the SciLead fetch in 3.3
in the same env when it needs PDFs (`UV_PROJECT_ENVIRONMENT="$EV/venv-fetch"`).

## 4. Real-model checks (in the job)

4.1 **Word list and the planner's fresh queries** are checked by the runs of sections 6 and 7 (word list in each
`plan.json`; fresh-query rows in `offtemplate.json`). Nothing to run here.

4.2 **ReadClaim against the old RAG claim labels** (the claim step with the real model, on the old RAG corpus):

```bash
"$EV/in-job.sh" uv run python scripts/check-readclaim.py --corpus tests/EV2/corpora/rag-claude-s1-mixed --list    # offline: 80 sentences
"$EV/launch.sh" readclaim uv run python scripts/check-readclaim.py --corpus tests/EV2/corpora/rag-claude-s1-mixed --cache "$CACHE/readclaim.jsonl"
```

**Success:** the log ends with a JSON report (`n`, `mean_metric`, `claims_called_claims` as `k/40`,
`claims_right_direction` as `k/40`). Record the numbers. **USER** reads them: a mean metric near 0.5 means the step calls
everything a claim (or nothing).

## 5. Synthetic corpora and tuning

5.1 **The two harder levels.** No corpus has `multi_experiment` or `messy_tables` yet. Generate them (template renderer,
no model, seconds), two seeds so tuning has disjoint train and test:

```bash
for S in 1 2; do uv run synth build --name rag-tpl-gen-s$S --seed $S --studies 20 \
  --levels multi_experiment,messy_tables --out "$EV/corpora"; done
```

**Success:** `$EV/corpora` holds `rag-tpl-gen-s{1,2}-{multi_experiment,messy_tables,mixed}`, each with `corpus.json`,
`ground_truth.json`, `papers/`. These are **template-written**: they tune `map_experiments`, but they never feed `leak`.
The Claude-written corpora (`tests/EV2/corpora/rag-claude-*`) are in git: do not rebuild them (no `synth` LLM renderer on Slurm).

5.2 **Held-out slice of each real set** (written once, by whole questions; `evaluate wholerun` drops the held questions,
tuning trains on their papers). Do this **before** `evaluate wholerun` draws its sample:

```bash
uv run evaluate tune-split --set sofc --src "$REAL/sofc" --corpus "$REAL/sofc/corpus"
uv run evaluate tune-split --set cochraneforest --src "$REAL/cochraneforest" --corpus "$REAL/cochraneforest/corpus"
uv run evaluate tune-split --set scilead --src "$SCILEAD_DATA" --corpus "$REAL/scilead/corpus"
uv run evaluate tune-split --set scirex --src "$REAL/scirex/test.jsonl" --corpus "$REAL/scirex/corpus"
```

**Success:** each prints `wrote .../tune_split.json: kept N questions, held K for tuning (...)`. The file is written once
(a second run refuses). The old `real-set-prep.py tune-split` (paper level) is not used any more.

5.3 **`tune_examples.json`**. The real-paper steps `recheck`, `map_experiments`, `claims.read_claim` refuse to tune on
synthetic corpora only (`TuneError`); they need `<corpus>/tune_examples.json` next to `tune_split.json`, in the format of
the docstring of `evidence/steps/tune.py`. A script builds it from the set's own labels (run it after 5.2):

```bash
uv run python scripts/real-set-prep.py tune-examples --set "$REAL/sofc"          # writes $REAL/sofc/corpus/tune_examples.json
uv run python scripts/real-set-prep.py tune-examples --set "$REAL/cochraneforest"
```

**Success:** SOFC prints example counts for `recheck` and `map_experiments` and `no examples for claims.read_claim`; the
other sets print `no examples for ...` (Cochrane has no sentences) and may write nothing. So only SOFC gives real examples,
and `claims.read_claim` stays **untuned**. **USER** may add or fix examples by hand (same format); Codex does not edit them.
Check the SOFC file:

```bash
uv run python -c "import sys; from pathlib import Path; from evidence.steps import tune; d=Path(sys.argv[1]); [print(s, len(tune.examples_of(tune.SPECS[s], tune.sources(s,[d],'train'))), len(tune.examples_of(tune.SPECS[s], tune.sources(s,[d],'test')))) for s in ('recheck','map_experiments')]" "$REAL/sofc/corpus"
```

**Success:** one line per step with train and test counts above 0 (a `TuneError` says what is wrong).

5.4 **Tuning** (GEPA light, capped at 500 model calls per step; `--optimizer gepa` is the default). One step at a time,
model `orch-model` (the default), each with its own cache **folder** (`--cache` is a directory, not a `.jsonl` file).

`write_words` and `write_more_words` are **not tuned**: every Claude corpus shares condition names with the leak corpora,
so a tuned word writer could not be measured honestly by the leak split (`evaluate leak` refuses such files). Do not tune them.

```bash
# the real-paper steps need at least one real set on the train side (refused on synthetic only, exit 2); only SOFC has examples (5.3).
RS="$REAL/sofc/corpus"; STEP=map_experiments
"$EV/launch.sh" tune-$STEP-sofc uv run evidence tune $STEP \
  --train "$EV/corpora/rag-tpl-gen-s1-multi_experiment" "$RS" --test "$EV/corpora/rag-tpl-gen-s2-multi_experiment" "$RS" \
  --optimizer gepa --cache "$CACHE/tune-$STEP-sofc"
# recheck: synthetic side only from corpora never scored (k1 or pilot), NEVER a rag-claude-s1-* corpus
STEP=recheck
"$EV/launch.sh" tune-$STEP-sofc uv run evidence tune $STEP \
  --train tests/EV2/corpora/rag-claude-k1-mixed "$RS" --test tests/EV2/corpora/rag-claude-pilot-mixed "$RS" \
  --optimizer gepa --cache "$CACHE/tune-$STEP-sofc"
```

Train and test share a real set's folder: the train side reads only the held-out slice, the test side only the rest
(disjoint by paper). Train and test never share paper text or ground truth (a `TuneError` says which). A step tuned on
two sets writes one `tuned/<step>.json`: tune it once, with every set that has examples on both sides.

`planner_query` is **not tunable yet** (its metric would be the whole-run score on synthetic questions, which is not
wired): the planner stays untuned. **Untuned steps, listed in the report:** `write_words`, `write_more_words`,
`claims.read_claim`, `planner_query`. **Success:** each step writes
`evidence/steps/tuned/<step>.json` with `instructions`, `light_budget`, `max_metric_calls` (at most 500), the calls really
made and train/test scores before and after. A `TuneError` (overlap, refused synthetic-only, failed parse share) is a
result, not a crash: record its text. Tuned files change the steps' instructions, so **run section 6 after tuning**;
copy `evidence/steps/tuned/` back (Aditya decides which go into git).

## 6. The real sets: plan runs, both confirmation rows, both reasoning settings

A "plan run" is the question planned by the planner, every choice confirmed, then run on the set's papers. `evaluate
wholerun` only **scores** runs; `scripts/plan-runs.py` makes them in the layout it reads:
`<runs>/<auto-confirmed|hand-confirmed>/<on|off>/<question id>/` (the hand row is the **first 5 questions** of `sample.json`).

**Network check first** (inside a job; plan runs ask OpenAlex for links):

```bash
"$EV/in-job.sh" curl -sI --max-time 10 https://api.openalex.org/works/W2741809807
```

If it fails, set `LINKS=off` and pass `--links off` to every `plan-runs.py run`, and report "links not run"; else `LINKS=on`.
(With links on and OpenAlex gone mid-run, a run stops asking after 3 failures: links say "openalex unreachable".)
Every `plan-runs.py run` below carries `--links $LINKS --reasoning on|off`.

For each set `S` in `scilead scirex cochraneforest sofc` (`SRC` = `$REAL/<S>`; for scirex `SRC=$REAL/scirex/test.jsonl`; the
corpus is `$REAL/<S>/corpus`; MeasEval is only a values check, no whole-run questions), with `RUNS_S=$RUNS/real/<S>`:

```bash
SRC=$REAL/sofc; COR=$REAL/sofc/corpus; S=sofc; OUT=$SCORES/real/$S; RUNS_S=$RUNS/real/$S; mkdir -p "$OUT"
# 6.1 the fixed sample (no runs yet: every question is "missing"; this only writes sample.json)
uv run evaluate wholerun --set $S --src "$SRC" --corpus "$COR" --runs "$RUNS_S" --out "$OUT" --system engine --sample 10 --seed 0
# 6.2 plan the 10 questions once (planner + critic, nothing confirmed)
"$EV/launch.sh" plan-$S uv run python scripts/plan-runs.py plan --set $S --src "$SRC" --corpus "$COR" \
  --sample "$OUT/sample.json" --plans "$PLANS/$S" --cache "$CACHE/real-$S"
```

**USER stop (hand row).** A person must read and confirm the first 5 plans: Aditya gives a name for `--by` / `--confirm-by`.
Codex never confirms as a person and never uses the name `system` for the hand row (`evaluate wholerun` refuses it).
Without that name, skip the hand row and say so. With the name, write the hand files and print every decision and word list:

```bash
uv run python scripts/plan-runs.py confirm --set $S --src "$SRC" --corpus "$COR" --sample "$OUT/sample.json" \
  --plans "$PLANS/$S" --by "<NAME>"
```

**USER:** Aditya reads the printout and may edit the decisions or words in `$PLANS/$S/hand-confirmed/<id>.json` before 6.4;
`run` never overwrites an existing hand file (`--confirm-by` is then optional). Never edit them yourself.

```bash
# 6.3 auto row: all 10 questions, decisions confirmed by "system"; reasoning on, then off
for R in on off; do "$EV/launch.sh" runs-$S-auto-$R uv run python scripts/plan-runs.py run --set $S --src "$SRC" --corpus "$COR" \
  --sample "$OUT/sample.json" --plans "$PLANS/$S" --cache "$CACHE/real-$S" --runs "$RUNS_S" --confirm auto --reasoning $R --links $LINKS; done
# after each row, once (not in a loop): redo runs a failed call left unchecked
#   (same command again with --redo-unchecked added; the old folder stays as <qid>.redo-<n>)
# 6.4 hand row: first 5, confirmed by the named person
for R in on off; do "$EV/launch.sh" runs-$S-hand-$R uv run python scripts/plan-runs.py run --set $S --src "$SRC" --corpus "$COR" \
  --sample "$OUT/sample.json" --plans "$PLANS/$S" --cache "$CACHE/real-$S" --runs "$RUNS_S" --confirm hand --confirm-by "<NAME>" --reasoning $R --links $LINKS; done
# once after the row, not in a loop: the same two lines with --redo-unchecked added
# 6.5 score: engine rows and the RAG baseline (global and per_paper), same questions, papers and model
"$EV/launch.sh" score-$S uv run evaluate wholerun --set $S --src "$SRC" --corpus "$COR" --runs "$RUNS_S" --out "$OUT" \
  --confirm both --reasoning both --system both --sample 10 --seed 0 --cache "$CACHE/rag-real-$S.jsonl"
```

**Success:** every `<runs>/<conf>/<on|off>/<qid>/` has `plan.json`, `run.json`, `answer.json`; `wholerun.json` and
`wholerun.md` list rows `auto-confirmed/on`, `auto-confirmed/off`, `hand-confirmed/on`, `hand-confirmed/off`, `rag/global`,
`rag/per_paper`, wins/losses/ties and a paired interval per engine row against each RAG row, the "left out: N of M (no
open full text)" line, and how many questions got a fresh query. A missing run is a loss (headline 0), never hidden.
`plan-runs.py run` exits 1 when a question failed (it names it, others still run). `evaluate wholerun` exit 2 = refused
(different model or papers between engine and RAG, wrong confirmation, or no manifest): read the message, fix the cause.

**Reruns.** `plan-runs.py run` skips only runs sealed complete. A failed or unsealed folder is moved to
`<qid>.failed-<n>` and the question runs again with failed calls asked again: just rerun the same command. After each row,
run it once more with `--redo-unchecked` (not in a loop): a complete run whose `stage_report.json` or `recheck_report.json`
lists items a failed call left unchecked moves to `<qid>.redo-<n>` and runs again. **Never start two jobs on the same row**
(the second would move the first one's unfinished folder). The sibling `.failed-<n>` and `.redo-<n>` folders are handed back too.

**Reasoning off is a real switch** (`--reasoning off`): no reasoner, no field ontology in the graph, `ontology.json` says
`reasoning off: no tree`, lock `field_ontology_sha256` is `{}`. The saved templates do **not** use the ontology tree, so
on and off differ only on fresh queries (and the unscored synthesis): the report must say so. The word list (with its
ontology names) is the same plan for both rows. A run's new files: `stage_report.json` (items skipped as `unchecked: ...`,
keys claims, experiments, links, groups) and, when OpenAlex failed, `openalex-failed.jsonl`; links with `resolve_failed` count
as outside the set.

**Fresh query returns rows?** For each set the report lists the share of fresh queries; for each fresh question open its
`answer.json` and say whether its line has rows ("done" with rows, or "done" with none, or "failed: ..."). Generality
depends on this: an empty answer is allowed, but a failed or always-empty fresh query is a finding.

Cochrane note: its questions have one corpus per plot, so `--corpus` is the root `$REAL/cochraneforest/corpus`; if
`evaluate wholerun` cannot find a question's papers, stop (**USER**), do not edit.

## 7. Synthetic checks

7.1 **Off-template (the generality check)**: 12 questions on `rag-claude-s1-mixed`, each planned, confirmed by "system",
run, then compared with its reference query (each plan run writes `records.nq` beside `plan.json`; the report lists `failed: ...` per question):

```bash
"$EV/launch.sh" plan-offtemplate uv run python scripts/plan-runs.py plan --set offtemplate --plans "$PLANS/offtemplate" --cache "$CACHE/offtemplate"
"$EV/launch.sh" runs-offtemplate uv run python scripts/plan-runs.py run --set offtemplate --plans "$PLANS/offtemplate" \
  --cache "$CACHE/offtemplate" --runs "$RUNS/offtemplate" --confirm auto --reasoning on --links $LINKS
uv run evaluate offtemplate --runs "$RUNS/offtemplate" --out "$SCORES/offtemplate"
```

**Success:** `offtemplate.json` has `summary` with `fresh_share` and `match_rate` (the two generality numbers), `not_run` 0.
Never edit `evaluation/offtemplate/questions.yaml` or the reference queries.

7.2 **Leak split** (Claude-written corpora only; the word list is the run's `plan.json`): one plan run per corpus, then:

```bash
for C in rag-claude-s1-mixed rag-claude-s1-distributed rag-claude-s1-complex; do
  "$EV/launch.sh" plan-leak-$C uv run python scripts/plan-runs.py plan --set synthetic --corpus tests/EV2/corpora/$C --question "$Q" --plans "$PLANS/leak" --cache "$CACHE/leak"
  "$EV/launch.sh" run-leak-$C uv run python scripts/plan-runs.py run --set synthetic --corpus tests/EV2/corpora/$C --question "$Q" \
    --plans "$PLANS/leak" --cache "$CACHE/leak" --runs "$RUNS/leak" --confirm auto --reasoning on --links $LINKS
  uv run evaluate leak --run "$RUNS/leak/effect-$C" --corpus tests/EV2/corpora/$C --out "$SCORES/leak/$C"
done
```

(one at a time: wait for each `launch.sh` step to finish.) **Success:** `leak.json` has recall for "on the list" and
"unseen". A corpus that is not Claude-written is refused (`evaluate leak: ...`, exit 1), and so is a run when a tuned
`write_words` / `write_more_words` / `recheck` file saw corpora with the same condition names (none should exist: 5.4). If a
tuned file lists corpora elsewhere, add `--corpora "$EV/corpora" --corpora tests/EV2/corpora`. Never tune on a `rag-claude-s1-*` corpus.

7.3 **The Claude-written corpora at every level, engine and RAG baseline** (`--protocol` runs, as EV3/EV4; the model is
`orch-model`; each its own run folder). Levels: `explicit paraphrased distributed complex contradictory mixed`
(`rag-claude-s1-*`). `multi_experiment` and `messy_tables` have only template-written corpora (5.1):

```bash
for C in tests/EV2/corpora/rag-claude-s1-{explicit,paraphrased,distributed,complex,contradictory,mixed} \
         "$EV/corpora"/rag-tpl-gen-s1-{multi_experiment,messy_tables}; do N=$(basename $C)
  "$EV/launch.sh" run-$N uv run evidence run --protocol domains/rag/protocols/rag-factuality.yaml --corpus $C --out "$RUNS/synthetic" --cache "$CACHE/synthetic" --run-id $N
  "$EV/launch.sh" rag-$N uv run evaluate rag-baseline --corpus $C --out "$RUNS/synthetic-rag/$N" --retrieval per_paper --k 2
  uv run evaluate score --run "$RUNS/synthetic/$N" --corpus $C --baseline "$RUNS/synthetic-rag/$N/answer.json" --out "$SCORES/synthetic/$N"
done
```

(one launch at a time; at most three long `orch-model` steps at once, own cache each.) **Success:** every run folder has
`run.json` and `manifest.json`; `evidence verify "$RUNS/synthetic/<N>"` exits 0; `report.json` per corpus. Report the
tpl-written levels apart from the Claude-written ones.

7.4 **Links** (chaining against the synthetic truth network; builds-on by OpenAlex references). `evaluate links` needs a
chaining question id and a corpus with a truth network (built with `synth build --preset builds_on`); the `rag` pack's
`questions.yaml` has **no chaining question** (its ids: `rag-factuality`, the `cons-*`, `best-*`, `inv-*` ones), so chaining is
not run unless Aditya names a corpus and a question (**USER**; do not invent one). Builds-on needs a references file
`{paper id: [OpenAlex work ids]}` (the run's OpenAlex client saves `openalex.jsonl` beside a plan run; `--build-references` builds the file from it, offline). When both exist:

```bash
uv run evaluate links --run "$RUNS/synthetic/<N>" --corpus <corpus with a truth network> --question-id <chaining id> --out "$SCORES/links/chaining"
uv run evaluate links --run "$RUNS/<plan run>" --corpus <its corpus> --build-references --out "$SCORES/links/builds-on"   # writes <out>/openalex-references.json
uv run evaluate links --run "$RUNS/<plan run>" --references "$EV/openalex-references.json" --out "$SCORES/links/builds-on"   # or your own file
```

**Success:** `links.json` with recall numbers. "links not run: <why>" is a valid outcome (`builds_on.status`; recall is `None`,
never 0): copy the reason (links off, no chaining question, no references, no OpenAlex work ids). When some cited works are in
the set (`n_in_set` > 0) they cannot be scored, so links recall is a **lower bound**.

## 8. Hand-back

1. `$EV/failures.md` (even if empty: "none").
2. Copy every run folder back: `rsync -a "$RUNS/" <laptop or results branch>/runs/` (all of `real/`, `offtemplate/`,
   `leak/`, `synthetic/`, `synthetic-rag/`), plus `$SCORES`, `$PLANS`, `$CACHE/*.jsonl` of the baselines, `$EV/ontology-hashes.json`,
   `$EV/sofc-directions.tsv`, `$EV/estimate-*.json`, `evidence/steps/tuned/`, and every `tune_split.json` (and
   `tune_examples.json`) of the real sets; in every run folder `stage_report.json` and, when present, `openalex-failed.jsonl`
   (also the `<qid>.failed-<n>` / `<qid>.redo-<n>` folders). Branch `results-general` from `origin/results`; tag `general`; never push to `main`
   or `results`.
3. Write `reports/general/summary.md`, losses first: per real set the engine rows against RAG (wins, losses, ties, paired
   interval); the fresh-query share and off-template match rate; the leak split; the left-out lines; the ReadClaim numbers;
   what stayed untuned (`write_words`, `write_more_words`, `claims.read_claim`, `planner_query`, and any real step without examples); every **USER** stop and its answer; every
   layout difference found in 3.2; whether links were on or off and why; that on/off reasoning differ only on fresh queries.
   **Replay:** replaying a plan run needs the same ontology files (it reads `$EV_ONTOLOGY_DIR` again): hand back
   `ontology-hashes.json` and fetch the same files before replaying, else `lock.json` / `records.nq` mismatch. Plan runs
   recorded before this merge do not replay (none exist on the cluster yet).
4. No "pending" text; a final status in the report.

## 9. After the 4 Nov fixes (Codex, next run)

What changed and why: `reports/general/decisions.md` (entries of 4 Nov from "Headline and answer-key split judge one
line" on). Code is local `main` after the merge of `fix/general-run`; `llm-setup` stays `b962edd`. Run folders of the
first run are on `codex/general-system-run` (`reports/general/runs/`), not on `main`: fetch them from that branch.

9.1 **Offline suite on Linux** (all of it, including the POSIX-only agent and web-app tests Windows cannot run):
`uv run pytest evidence synth evaluation modelcall webapp agent -q`. The four failures of the first run are fixed
(lock fixture now versioned v1/v2, golden test machine-independent, web-app group `...-cascade-gaps`); anything red is
a finding: stop, **USER**.

9.2 **Rescore what needs no model call** (into new score folders, `*-v2`; keep the old ones):

```bash
G=<checkout of codex/general-system-run>/reports/general
uv run evaluate wholerun --set scilead --src "$REAL/scilead" --corpus "$REAL/scilead/corpus" --runs "$G/runs/full/scilead" \
  --out "$SCORES/full-v2/scilead" --confirm auto --reasoning both --system engine --sample 22 --seed 0
uv run evaluate wholerun --set scirex --src "$REAL/scirex" --corpus "$REAL/scirex/corpus" --runs "$G/runs/fixed/scirex" \
  --out "$SCORES/fixed-v2/scirex" --confirm auto --reasoning both --system engine --sample 15 --seed 0
uv run evaluate offtemplate --runs "$G/runs/offtemplate" --out "$SCORES/offtemplate-v2"
```

Expect the SciLead engine headline to drop (the headline no longer reads a later line when the rank line is empty;
about 0.136 to 0.045 reasoning on) and most "synthesis error" labels to become "extraction error" (the key store now
names metrics as the plan does); scilead-05/06 now say "plan error". Then the RAG rows: the same commands with
`--system both --cache <the first run's RAG cache>`; the run must make **no** model call (the RAG answers are cached).
If it would call the model, stop and say so. Report old and new numbers side by side, never only the new.

9.3 **Re-plan the flagged plans.** `plan-runs.py plan` now runs the plan check on every plan, prints `plan problems
<id>: ...` and exits 1 (it never edits a plan). Known flagged: scilead-05, -06, -19 (no measure for `$metric`), all 15
SciREX plans (`kg:dataset`, which the graph never emits), off-template q05, q09 (an unplanned line) and q08 (`ev:value`).
For each: move the plan file aside as `<id>.v1.json` and run `plan` again (the planner's repair loop now sees the refusal);
keep the new plan only if the check passes, else report the problem text. Never edit a plan by hand.

9.4 **Rerun what the fixes changed** (model calls; new run folders `*-v2`, plan runs are now `plan_version: v2`:
best thing named, names matched by the word list's aliases and bracket forms, no experiment map for papers the screen
drops, no request over the context window):
- SciREX, all 15 (new plans): `plan-runs.py run` both reasoning rows, then 6.5 scoring.
- SciLead, all 22 kept questions, both rows (names matter for -10, -27; the map now skips screened-out papers, so the
  context-window failures should mostly go: count `too_long` notes in `stage_report.json`).
- Off-template: all 12 again (q06, q10 now plan with treatment `any`), then `evaluate offtemplate`.
- Leak: 7.2 as written (the type error is fixed; `runs/leak` was never handed back). If "unseen" recall stays near 0,
  report it with the run's item counts by type: the scorer may not read conditions held inside experiment records
  (open question, not changed).
- Synthetic `paraphrased` and `complex` (7.3): a reply that never validates is now a warning, not exit 2. Count the
  `warning: N extractor call(s) got a model reply that did not validate` lines. The cause (Qwen looping whitespace or
  quotes to max_tokens) is not fixed: check whether the stack's vLLM has a structured-output option that disables free
  whitespace, and report what you find; do not change the stack yourself (**USER**).

9.5 **Robustness, if time allows** (Aditya's ask): all kept questions per set (not a 10-question sample: `--sample` = the
kept count); 3 repeats of each engine and RAG row into separate folders (`rep-1..3`, same seed: the spread shows run-to-run
variance of the served model). A stronger RAG setting needs a retrieval-size flag that `evaluate wholerun` does not have
yet: skip it and say "not available".

Old runs: a replay of a run recorded before 4 Nov now stops with `CodeChanged` (the llm_* extractor ids changed with the
plain-text replies) and names the commit to replay it from; that is expected, not a failure.

## Limits (say them in the report)

Saved templates do not use the ontology tree: reasoning on/off differ only on fresh queries (section 6). Layouts of
CochraneForest, SOFC-Exp and MeasEval stay `layout_verified: false` until Aditya clears 3.2. Real-paper steps tune only on
held-out slices with `tune_examples.json`, and only SOFC has them (`recheck`, `map_experiments`). Untuned: `write_words`,
`write_more_words`, `claims.read_claim`, `planner_query`. Links recall is a lower bound when `n_in_set` > 0, and "links not
run" is a valid outcome. The sample is 10 questions per set, a hand row of 5. Leak uses Claude-written corpora only.
