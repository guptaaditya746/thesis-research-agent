# Earlier work: the research agent and its evaluation (8–14 Oct 2026)

Before the supervisor's design of 14 Oct (now the thesis; [`STATE.md`](STATE.md)), the repository built a
different system: a free LLM research agent that answers a question over the 337-paper corpus and records
every fact with an exact quote while it researches. Its code stays in the repository (`agent/`, `gold/`,
`scoring/`, `webapp/`, `questions/`); since 16 Oct the agent is used only as one extractor (the agentic
extractor) and as the second baseline of the evidence-level system, and the claim on/off study it was built
for is dropped. This page summarises it for a reader of the thesis and keeps the essentials (how to run,
file formats in brief) that code comments point to. The full text of every document it replaces is in git
history: each section ends with the `git show` command that prints it (`3edd23b` is the last commit that
has them).

## 1. What it was

**Flow:** question → concepts → user picks one → agent → knowledge graph → trace back.

- **Corpus.** 337 computer-science papers (37 originals, 150 ACL 2025, 150 EMNLP 2025, verified against
  DBLP), converted once with Docling 2.110.0 into one Markdown file each, frozen with hashes
  (`corpus/manifest.json`); 336 converted (`p38` is a scanned PDF, left out by decision).
- **Concepts.** A question is turned into up to five standalone, unambiguous research briefs (definition with
  its measure, scope, answer shape, competency questions), proposed corpus-blind; the user picks one, the
  pick is frozen and hashed.
- **Agent.** A mini-swe-agent loop on the orchestrator model with complete freedom over the Markdown files
  (grep, read, Python), in a Landlock + seccomp sandbox. Every fact goes through a `claim` command: a broker
  outside the sandbox checks the quote against the frozen file (`agent/anchor.py`) and writes it into one
  hash-chained log (`events.jsonl`). Optional subagents (`spawn`).
- **Knowledge graph and provenance.** One graph edge per accepted claim (`graph.json`), a PROV-O export
  (`graph.ttl`), five provenance queries, and a claim walk from an answer fact to the highlighted quote.
- **Study (dropped).** RQ1: recording each fact with a quote as it is found (`claim_on`) vs attaching
  sources to the answer afterwards (`claim_off` plus an attach step), same agent, model and budget;
  12 questions × 2 conditions × 3 repeats = 72 runs; primary outcome the support share (share of answer
  facts whose quote an LLM judge says supports them), Wilcoxon signed-rank over questions, pre-registered
  13 Oct.
- **Gold.** Per question an evidence document **D** built from the whole corpus by the method of the
  labelling repo (screen every paper, extract, triage, review in Argilla, Cohen's κ), reviewed into an
  answer key; D was the supervisor's earlier idea (to avoid pooling bias). Scoring matched runs against
  the key; a FastAPI + React web app ran and inspected everything.

The design came from the context note of 8 Oct and the plan built on it (§5.1 concepts, §5.2 the research
brief, §5.3 harness and toolbox, §5.4 visibility, §5.5 knowledge graph and provenance anchors, §5.6
evaluation and gold); code comments cite "design §5.x" for these.
Full text: `git show 3edd23b:docs/context.md`, `git show 3edd23b:docs/plan.md`.

On 14 Oct, after the supervisor's first message, an intermediate plan (an explicit "evidence plan" per
question, one agent, 36 runs, no comparison) was drafted and decided the same day; his second message the
same day replaced it with the design that is built now. Full text:
`git show 3edd23b:docs/plan-evidence-level.md`.

## 2. Decisions and numbers worth keeping

Measured on the cluster (gammaweb08, 3×A100 40 GB) in the infrastructure rounds of 8–13 Oct; every row has
its test id in [`tests/RESULTS.md`](../tests/RESULTS.md). The serving stack, the sandbox and the corpus are
what the evidence-level system runs on.

| Area | Decision | Tests |
|---|---|---|
| Orchestrator | `Qwen/Qwen3.8-27B-FP8` @ `017b9c7`, GPU 0, 65,536 context, thinking off, `max_tokens` 4096 (conclude replies up to 16,384) | A2, A3, B3, L1, L2 |
| Sub-model | `Qwen/Qwen3-30B-A3B-Instruct-2507-FP8` @ `5a5a776`, two replicas (GPUs 1, 2), 32,768 context, 3 active sequences each | A4, A5, L1, L3 |
| Serving | `llm-setup` (`thesis-llm-setup`), profile `profiles/agent-3x40.yaml`, LiteLLM on `127.0.0.1:4000` (`orch-model`, `sub-model`, pinned `sub-model-1`/`-2` for fan-out, because shared-alias routing skewed) | L1, L2, L7, R3 |
| Context overflow | Proxy returns HTTP 400 `ContextWindowExceededError`; the harness maps it to "context full" and stops retrying | L8 |
| Reply format | Thinking off with a strict one-bash-block instruction: 50/50 blocks, 0.63 s mean; a lenient parser fallback; nothing ever run from the reasoning field | B1–B3, B8, B9 |
| Sandbox | Landlock ABI 8 + x86_64 seccomp per command, own process group, `ulimit -v 2G`, `timeout 120`; corpus and toolchain read-only, one writable scratch; IP, pathname Unix and netlink sockets blocked | S5a–c, S6, S7, S1b |
| Toolchain | Pinned, hashed, read-only `agent-venv` + ripgrep + jq (`scripts/build-agent-root.sh`, `verify-agent-root.sh`) | S5c, B0, S7 |
| Logs and claims | One broker per run, single writer of the hash-chained `events.jsonl`; the sandbox sends claims over an inherited descriptor | H1, R2, S7 |
| Corpus | Docling 2.110.0 (OCR off, tables on): the only path that kept tables; deterministic (10/10 identical hashes); two-column order kept (0/10 papers interleaved) | D1, D2, D5, D1-col |
| Anchors | Selector = file sha256 + raw offsets + exact/prefix/suffix; retyped quotes matched after normalising (NFKC, whitespace, dashes, quote marks) and mapped back; a quote may not cut a number (`partial_number`); case-sensitive | `agent/anchor.py`, `test_anchor` |
| Output cap | 8 KB of each command's output in context, the full output in a file | C1 |

| Quantity | Value | Test |
|---|---|---|
| Orchestrator decode / prefill | 41.6 tok/s (one sequence) / ~2,400 tok/s, 26 s to first token at 60k | A5, A3 |
| Orchestrator KV capacity | 79,371 tokens = 1.21 requests of 65k | A2 |
| Worst-case orchestrator step | 112.5 s (54.6k in + 4,096 out); proxy timeout set to 600 s | L6, L7 |
| Prefix cache at 30k | cold 12.0 s to first token, cached 0.35 s (94 % hits) | C2, C2b |
| Sub-model decode, KV | 130 tok/s; 64,848 KV tokens per replica; 6 × 16k without preemption | A5, L1, L3 |
| Full paper | 45–230 KB, ~35k tokens: larger than the sub-model's context | D1 |
| Stack startup | 11 min 14 s | L1, L5 |
| Ceph append | 80,000/80,000 lines intact with 8 writers; `fsync` p99 65–104 ms | R2 |

**First real runs (13 Oct, Slurm job 7288).** F1 acceptance passed (model → parser → sandbox → `claim` →
broker, one exact quote accepted, chains verified, corpus read-only, network blocked). Four real runs
(M1-real) all verified but ended at the configured budget with empty answers: 470,077–498,229 tokens against
400k, the largest prompt 38,470 tokens; the conclude replies were commands. The fix (prompt v2, conclude
replies decoded under the answer schema, a draft answer file, budget 60 steps / 2M tokens, observation
masking) was built against a scripted model and never met the real model. The attach step ran once with no
facts to process. The end-to-end Slurm session (concepts, gold trial, smoke batch, scoring, web app) was
written but never run.

Full text of the old state page (the "Decided" table in full, including loop, prompts, concepts, batch,
re-execution, replay, graph, subagents, gold, judge, scoring and web app rows): `git show 3edd23b:docs/STATE.md`.

### Decisions after tests (9 Oct)

Why each infrastructure decision was taken, test by test: §1 models and GPU layout (Qwen3.8 is the only
tested model that holds 65k on one GPU and follows the one-block rule; the Thinking-2507 model fails it:
26 % compliance, a repeated-`claim` loop); §2 the parser (one fenced bash block, else a single bare line,
else a nudge and a `format_error` record; two blocks run the first; never the reasoning field); §3 loop
notices (an identical command twice → a notice, three times → the notice names the budget left); §4 the
sandbox (no bwrap or user namespaces on the node, direct egress open, so Landlock + seccomp); §5 the corpus
(Docling, frozen once; a full paper does not fit a 32k context); §6 budgets from the decode rate. Full text:
`git show 3edd23b:docs/decisions-after-tests.md`. Research into the partial tests of 10 Oct (LiteLLM model
list error, replica balance, reasoning effort, B6 usefulness, D1 reading order, L6 headroom; superseded rows
A7, C2, L3, B1/B2): `git show 3edd23b:docs/research-open-test-findings.md`.

## 3. Provenance model

Adopted from PROV-AGENT (record schema, field names; Souza et al., arXiv 2508.02866, code ORNL/flowcept,
MIT) and LEDGER (claim-to-evidence edges `uses`, `produces`, `informs`, `supports`, `checked_by`; Kim, Miao,
Liu, arXiv 2608.18398); no novelty claim. Records in `events.jsonl`, one per activity: `task_id, subtype,
used, generated, parent_task_id, group_id, agent_id, source_agent_id, workflow_id, started_at, ended_at,
status, custom_metadata`, plus `step_id`, `prev_hash`, `hash`.

| `subtype` | Event | `used` | `generated` |
|---|---|---|---|
| `ai_model_invocation` | one model call | prompt hash, model (name, revision, temperature, seed) | response hash, token usage |
| `agent_tool` | one bash command | command, files read | output hash, output file |
| `claim` | one `claim` through the broker | anchor (file, start, end, exact, prefix, suffix, file hash) | claim id |
| `spawn` | a subagent start, return, cancellation or refusal | task text, files, steps | child agent id, sub-model; on return its status and result hash |
| `coverage` | unparsable output, a dropped or truncated output | raw output hash | reason |

Edge table (PROV-O in the export): model call → command `wasInformedBy`; command → corpus file `used`;
claim → step `wasGeneratedBy`; claim `wasDerivedFrom` its anchor; the broker's anchor check is a validation
`prov:Activity` (`checked_by`); subagent `actedOnBehalfOf` its parent; every activity `wasAssociatedWith`
its agent; a graph edge `wasDerivedFrom` its claim. Temporal order is the hash chain. The five queries:
graph edge → claim → step → passage; which command and model call produced a fact; all claims of a step or
subagent; claims whose anchor no longer resolves; answer facts with no claim. The evidence engine keeps the
same record fields (`docs/evidence-system.md` B7). Full text: `git show 3edd23b:docs/provenance-model.md`.

## 4. Build rows (milestones 1–4)

Code comments cite these row numbers. Milestone 1: the agent answers one question end to end; milestone 2:
the full system and the claim_off baseline; milestones 3–4: gold, the 72 runs, scores.

| Row | Item | Row | Item |
|---|---|---|---|
| 1.1 | F1 acceptance on Slurm | 2.1 | Concept step (≤ 5 briefs, corpus-blind) |
| 1.2 | Package and run directory, `config.json` | 2.2 | Pick a concept (`concept_pick` record) |
| 1.3 | Concept brief and answer schema | 2.3 | Concepts for the 12 questions |
| 1.4 | Column-order check (D1) | 2.4 | Baseline switch `--claim off` |
| 1.5 | Anchor library | 2.5 | Attach step |
| 1.6 | Broker (one chain, PROV-AGENT records) | 2.6 | Knowledge graph `graph.json` |
| 1.7 | `claim` command | 2.7 | PROV-O export `graph.ttl` |
| 1.8 | Main loop (mini-swe-agent 2.4.6 subclass) | 2.8 | Five provenance queries |
| 1.9 | Model-call and command records | 2.9 | Batch runner |
| 1.10 | Prompt v1 and one concept | 2.10 | One full run per condition (not run) |
| 1.11 | `agent verify` | 2.11 | Claim walk view (in the web app) |
| 1.12 | Fact–quote export `pairs.jsonl` | 2.12 | `spawn` subagents (built, off) |
| 1.13 | First real runs (M1-real), then the fix | 2.13 | Re-execution (C5) and replay (C6) |
| 1.14 | Trace timeline `timeline.html` | 2.14 | Concept cards (in the web app) |
| 1.15 | Observation masking | 2.15 | Full canonicalisation (not done) |

**Fixed run settings** (every run's `config.json`): models as in §2; budget 150 steps / 400k tokens at
first, provisional 60 steps / 2M tokens after 1.13 (never frozen); temperature and one seed per run; command
limits `timeout 120`, `ulimit -v 2G`, 8 KB output cap; prompt version and hash, concept hash, corpus
manifest hash, agent-root hash, git commit and condition recorded.
Milestones 3–4 (gold D, review, key, judge; batch runs, score per run, report, SPARQL store, web app) were
built in the end-to-end build of 13–14 Oct against scripted models, fake servers and an in-memory Argilla,
and never met the real models, the full corpus, Argilla or a reviewer.
Full text: `git show 3edd23b:docs/milestones-1-2.md`, `git show 3edd23b:docs/milestones-3-4.md`.

## 5. The end-to-end build (13 Oct): environment and contracts

Built in one go on work-package branches with reviewers and merged on `e2e-build`; tested only offline.
Full text, with every file contract and the endpoint list: `git show 3edd23b:docs/e2e-build-plan.md`.

### Environment

| Variable | Meaning | Default |
|---|---|---|
| `CORPUS` | frozen Markdown corpus with `manifest.json` (read-only) | — |
| `RUNS` | runs root; `scripts/e2e-batch.sh <manifest>` puts a manifest's runs in `$RUNS/<manifest name>/` and prints `RUNS_ROOT=...`, the root that scoring and the web app take for that batch | `runs` |
| `GOLD` | gold working directory (D, review exports, keys, judge cache) | `gold-data` |
| `CONCEPTS` | concept sessions | `concepts` |
| `LITELLM_BASE_URL`, `LITELLM_MASTER_KEY` | LiteLLM proxy; the key is read at call time, never logged | `http://127.0.0.1:4000/v1` |
| `ARGILLA_API_URL`, `ARGILLA_API_KEY` | Argilla on Omen through `scripts/omen-tunnels` | — |
| `AGENT_ROOT` | pinned sandbox toolchain | — |

### The 12 questions

`questions/questions.json`; `agent/tests/test_questions.py` checks the file against this table.

| id | category | question | from |
|---|---|---|---|
| q01 | corpus_wide | Which benchmarks and datasets do the retrieval-augmented generation papers in the corpus evaluate on? | nlp33 |
| q02 | corpus_wide | What kinds of attacks or safety risks do the LLM safety and red-teaming papers in the corpus evaluate? | nlp34 |
| q03 | corpus_wide | Which low-resource languages do the papers in the corpus study, and for which tasks? | nlp35 |
| q04 | corpus_wide | What approaches do the papers in the corpus propose to detect or reduce hallucinations in large language models? | nlp36 |
| q05 | corpus_wide | Which metrics do the papers in the corpus use to measure hallucination or factual errors? | nlp42 |
| q06 | corpus_wide | Which EMNLP 2025 papers in the corpus introduce a new benchmark for evaluating large language models, and what does each benchmark measure? | nlp44 |
| q07 | ambiguous | Which retrieval-augmented generation approach is best among the papers in the corpus? | nlp30 |
| q08 | ambiguous | Which paper in this corpus is the most influential? | nlp48 |
| q09 | ambiguous | Who are the leading researchers on retrieval-augmented generation in this corpus? | nlp49 |
| q10 | ambiguous | Which evaluation benchmark is the most popular among the papers in the corpus? | nlp53 |
| q11 | ambiguous | Which large language model is used most successfully across the papers in the corpus? | nlp62 |
| q12 | ambiguous | Is retrieval augmentation or fine-tuning the better approach according to this corpus? | nlp66 |

### Concepts and pick

`$CONCEPTS/<qid>/` holds `proposal.json`, `concept.json`, `concept.sha256`, `events.jsonl` and
`session.json` (with `attempts`); `$CONCEPTS/picks.json` indexes the picks
(`{choice, title, picked_by: provisional-first | user | claude, reason, concept_sha256}`). A pick is frozen;
replacing it is refused once `$GOLD/<qid>/` holds anything (unless forced). Provisional rule for the cluster:
brief 1 (`picked_by: provisional-first`), changeable by the user before gold is built.

### Gold files, answer key, judge, scores

- **Gold** `$GOLD/<qid>/`: `chunks.jsonl`, `screening.jsonl`, `candidates.jsonl`, `doc.json`/`doc.md` (D),
  `triage.jsonl`, `pool.jsonl`/`pool.strata.json`, `key.draft.json`, `review/*.jsonl`, `snapshots/`,
  `key.json`, `export.json`, `report.json` (details in §6).
- **Answer key** (`key.json` / `key.draft.json`) has the agent's answer shape, so scoring compares like with
  like: `{qid, concept_sha256, kind, version, reviewed, rows: [{id, cells…, facts: [{id, s, p, o, paper_id,
  quote, vital, candidate_id}]}], notes}`; stripped of the gold-only fields a row validates as an answer row.
- **Judge** (`gold/judge.py`): `support(fact, quote, context)` → `supports | partial | no`, `same_fact`,
  `same_row`; cached in `$GOLD/judge-cache.jsonl` by exact input, model and prompt; scoring judges each
  quote with the calibrated context (paper id and 600 characters each side).
- **Scores**: `<run>/score.json` per run, `$RUNS_ROOT/report/` (`scores.jsonl`, `report.json`, `report.md`,
  CSV), the pyoxigraph store `$RUNS_ROOT/.oxigraph/` (one named graph per run).

### Backend API and frontend pages

FastAPI `webapp.app:create_app()`, JSON under `/api` (health, config, questions and concept propose/pick,
runs with steps, live stream, claims, graph, fact walk and score, corpus passages, gold, results, SPARQL,
the five queries, jobs, chat), the built frontend at `/`. Pages: Overview, Question (concept cards, pick),
Runs, Run (Answer with claim walk, Graph, Timeline, Claims, Provenance, Score), Compare (claim_on vs
claim_off), Results, Gold, Jobs, Chat. The current endpoint list is `webapp/web/openapi.json`; details in §6.

## 6. Packages of the earlier system

### Questions

`questions/questions.json`: `{"schema_version": 1, "questions": [{"id", "category", "question", "source",
"notes"}]}`, schema `agent/schemas/questions.schema.json`, read by `agent.concept_step.load_questions`. Six
corpus-wide (q01–q06), six ambiguous (q07–q12), taken from the labelling repo's set
(`github.com/guptaaditya746/labelling`, `questions/questions.json` at `a75b372`) and reworded only as far as
the Markdown corpus needs ("the indexed papers" → "the papers in the corpus"; q07 lost "2025" and "and by
which evaluation measure"); each entry's `notes` keeps the original. Replacing a question (before gold is
built): keep its id and category, set `source` and `notes`, update the table in §5 and run
`uv run pytest agent/tests/test_questions.py`, then propose concepts for it. Changing a question's text makes
its concept session `stale` and invalidates its gold and runs.
Full text: `git show 3edd23b:questions/README.md`.

### Gold: build

The labelling repo's method re-implemented for the Markdown corpus (C1): papers cut at Markdown headings
into chunks of up to 40,000 characters (`chunks.py`, markdown-it-py; too-long chunks halved down to 1,000
characters); **every chunk of every paper screened** (`screen.py`; no ranker, which removes the labelling
repo's ranker bias; absence recorded per paper: `relevant`, `not_relevant`, `no_text`, `error`); every
relevant chunk extracted into rows of the concept's answer shape with an exact quote per fact, decoded under
a schema (`extract.py`); every quote through the broker's claim check with one retry; rows merged by one rule
(`build.py` `merge_rows`); triage `answers | context | irrelevant` (`triage.py`, never gold); a seeded blind
review pool (`pool.py`); a draft key (`draft.py`, `v1-draft`, `reviewed: false`). Models `sub-model-1`/`-2`,
thinking off, temperature 0, never the agent's orchestrator. Resumable at call granularity (`cache.jsonl`).

```sh
gold build q01 --max-papers 20 --out $GOLD-trial   # trial; any file in $GOLD/<qid>/ freezes the concept pick
gold build q01                                     # full build; exit 0 complete, 1 rerun retries, 3 unfixable, 143 SIGTERM
gold status; gold triage q01; gold pool q01 --sample 50 --seed 0; gold draft q01
```

Estimated cost (counted, not measured): about 1,000 chunks for the corpus, so about 1,000 screening calls and
7–8 M prompt tokens per question. This method is the one planned for the gold of the 337-paper check
(`STATE.md`). Full text: `git show 3edd23b:gold/README.md`.

### Gold: review

Argilla v2.8.0 on Omen (`gold/argilla/compose.yaml`, tunnel `argilla` in `scripts/omen-tunnels`; accounts with
role `annotator` in workspace `thesis`); reviewers read [`gold/guidelines.md`](../gold/guidelines.md).

| Step | Command | Output |
|---|---|---|
| 1. D, triage and pool built | `gold build`, `gold triage`, `gold pool` | `$GOLD/<qid>/…` |
| 2. Load the review | `gold push all` | datasets `gold-v1-review`, `-overlap`, `-missing`; `$GOLD/overlap.json` |
| 3. Screening sample | `gold screening-sample`, `gold screening-push` | `screening.sample.json`; `gold-v1-screening` |
| 4. Review in the Argilla UI | — | responses |
| 5. Both reviewers finished the overlap, before discussing it | `gold snapshot` | `snapshots/overlap-<time>.json` |
| 6. Pull | `gold pull` | `review/*.jsonl`, `judge/responses.jsonl` |
| 7. Export the keys, adjudicate | `gold export all [--adjudicator NAME]` | `key.json`, `export.json` |
| 8. Agreement | `gold agreement` | `report.json` |
| 9. Judge sample from scored runs | `gold judge-sample --runs $RUNS/m4-72`, `gold judge-push`, `gold pull` | `judge/sample.jsonl` |
| 10. Calibrate the judge | `gold judge-agreement` | `$GOLD/judge-report.json` |

Decision rule: correct keeps the fact (a correction `s | p | o` replaces it), incorrect and unsure drop it;
missing facts are anchored as claims are. Numbers: Cohen's κ on the overlap's independent round with a
bootstrap over questions; triage miss estimate and screening false-negative rate with Wilson intervals.
Judge calibration on 240 sampled pairs: `partial` mapping chosen on one half, κ on the other; below 0.61 the
judge is not used for the primary test. Full text: `git show 3edd23b:gold/README.md` (section "Review").

### Scoring

```sh
R=$RUNS/m4-72                                            # one batch root (RUNS_ROOT from e2e-batch.sh)
score run    <run> [--key $GOLD/<qid>/key.json]         # -> <run>/score.json
score batch  $R --gold $GOLD --manifest $R/manifest.json # -> $R/report/scores.jsonl, batch.json
score report $R                                          # -> $R/report/report.json, report.md, *.csv
score store  $R --path $R/.oxigraph; score sparql <query.rq> [--run <id>]
```

Measures: support share (primary; best judge verdict over a fact's claims, `partial` by the calibration,
unsourced never counts), unsourced share, fact precision/recall/F1 at strict, normalised and soft levels
(one-to-one matching), vital recall, judged precision, row F1 (count cells exactly), cost with and without
the attach step. Pre-registered (13 Oct): per-question means over repeats, Wilcoxon signed-rank on paired
per-question means (two-sided, α 0.05, not computed below 6 pairs or with pending verdicts), 95 % BCa
bootstrap of the mean difference (2,000 resamples, seed 20261013), rank-biserial effect size, three
sensitivity analyses; scores against draft keys are provisional. `score.json` is schema version 3.
Full text: `git show 3edd23b:scoring/README.md`.

### Web app

```sh
export CORPUS=/path/to/corpus RUNS=runs/m4-72 GOLD=gold-data CONCEPTS=concepts   # RUNS: one batch root
uv run webapp serve          # http://127.0.0.1:8080; on Slurm: ssh -L 8080:127.0.0.1:8080 <node>
uv run webapp openapi -o webapp/web/openapi.json   # after a model or route change; a test checks it is current
```

The backend binds to 127.0.0.1, has no authentication, answers only loopback Host names and takes writes only
as same-origin JSON (`webapp/guard.py`); it writes job state and logs (`$RUNS/.jobs/`) and concept picks,
everything else is written by the CLI jobs it starts. `RUNS` must be one batch root: run ids are directory
names, so two batches with runs of the same name would mix. Settings in `webapp/settings.py`. Full text:
`git show 3edd23b:webapp/README.md`.

**Frontend** (`webapp/web`): Vite 7, React 19, TypeScript, Tailwind 4, shadcn/ui, TanStack Query, React
Router 7, React Flow, recharts, assistant-ui; Node from the `frontend` dependency group. `uv run --group
frontend npm ci`, then `npm run dev` (against `webapp serve`) or `npm run dev:mock` (MSW mocks, no backend);
`npm run build` writes `dist/`, which is committed so the node needs no Node; `npm run typecheck`, `lint`,
`test` (Vitest). API types: `npm run gen:api` (openapi-typescript → `src/api/schema.d.ts`). The app is to be
rebuilt for the evidence-level flow (`STATE.md`). Full text: `git show 3edd23b:webapp/web/README.md`.

## 7. Runbooks

Each Slurm session was run by Codex from a runbook on its own branch, results into `tests/RESULTS.md`.

| Runbook | Outcome | Full text |
|---|---|---|
| Final infrastructure session (B0, S7, L7, L8, C2b, D5, F1) | done 10 Oct: agent root reproducible, sockets closed, proxy timeout 600 s and pinned aliases, context-full error shape, prefix cache at 30k, corpus converted and frozen | `git show 3edd23b:docs/slurm-final-runbook.md` |
| First real runs (rows 1.1, 1.13) | done 13 Oct, job 7288: F1 passed, `claim` under Landlock on Ceph, four M1-real runs verified with no answers (§2) | `git show 3edd23b:docs/slurm-m1-runbook.md` |
| The whole system end to end (e2e build: concepts, gold trial, smoke batch, replay, scoring, web app) | written 13–14 Oct, never run (superseded) | `git show 3edd23b:docs/slurm-e2e-runbook.md` |

Its stack and job pattern carry over to [`slurm-evidence-runbook.md`](slurm-evidence-runbook.md): the stack
is `sbatch slurm/llm-stack.sbatch` with `LLM_SETUP_PROFILE=profiles/agent-3x40.yaml` from `llm-setup/`,
short commands run in `srun --jobid "$JOB" --overlap --pty bash -l`, long ones with `nohup srun --jobid
"$JOB" --overlap <env script> <command>` from the login node. `scripts/e2e-*.sh` and `scripts/e2e-measure.py`
belong to the e2e session (step 8 of that runbook is its measurement table).

## 8. What the evidence-level system reuses

| From the earlier system | Used for |
|---|---|
| `agent/anchor.py` (selectors, quote check), `agent/canonical.py`, `agent/chain.py` | every span check, canonical hashes, the engine's hash-chained events |
| The research loop, sandbox, `claim` and broker | the agentic extractor and the agent baseline |
| `gold/llm.py` (structured calls, prompt hash, `JsonlCache`), `gold/chunks.py` | the LLM extractors and the record cache |
| `agent replay` / `agent reexec` pattern, `agent/prov.py` | evidence replay, re-execution, PROV-O export |
| The serving stack, the Slurm job pattern, the frozen corpus | the live runs and the 337-paper check |
| The gold method (`gold/`) | gold for the RAG papers of the 337-paper check |

## 9. Removed documents

| Document | What it was | Full text |
|---|---|---|
| `docs/context.md` | The original context note (8 Oct): the old four-path system, the new free-agent design, related work | `git show 3edd23b:docs/context.md` |
| `docs/plan.md` | Design and brainstorm (8 Oct), §5.1–5.6 | `git show 3edd23b:docs/plan.md` |
| `docs/decisions-after-tests.md` | Why each infrastructure decision was taken (9 Oct) | `git show 3edd23b:docs/decisions-after-tests.md` |
| `docs/research-open-test-findings.md` | Research on partial tests (10 Oct) | `git show 3edd23b:docs/research-open-test-findings.md` |
| `docs/provenance-model.md` | Log records and PROV-O edges (§3) | `git show 3edd23b:docs/provenance-model.md` |
| `docs/milestones-1-2.md` | Triaged build plan and progress, milestones 1–2 (§4) | `git show 3edd23b:docs/milestones-1-2.md` |
| `docs/milestones-3-4.md` | What milestones 3–4 built (§4) | `git show 3edd23b:docs/milestones-3-4.md` |
| `docs/e2e-build-plan.md` | The end-to-end build: decisions, contracts, API (§5) | `git show 3edd23b:docs/e2e-build-plan.md` |
| `docs/plan-evidence-level.md` | Intermediate evidence-plan draft (14 Oct), superseded the same day | `git show 3edd23b:docs/plan-evidence-level.md` |
| `docs/slurm-m1-runbook.md`, `docs/slurm-final-runbook.md`, `docs/slurm-e2e-runbook.md` | Slurm runbooks (§7) | `git show 3edd23b:docs/<name>.md` |
| `docs/evidence-interfaces.md`, `docs/extractor-contract.md` | Now Parts A and B of [`evidence-system.md`](evidence-system.md), verbatim | `git show 3edd23b:docs/evidence-interfaces.md`, `git show 3edd23b:docs/extractor-contract.md` |
| `questions/README.md` | The 12 questions (§6 Questions) | `git show 3edd23b:questions/README.md` |
| `gold/README.md` | Gold build and review (§6 Gold) | `git show 3edd23b:gold/README.md` |
| `scoring/README.md` | Scoring and the pre-registered report (§6 Scoring) | `git show 3edd23b:scoring/README.md` |
| `webapp/README.md`, `webapp/web/README.md` | Web app backend and frontend (§6 Web app) | `git show 3edd23b:webapp/README.md`, `git show 3edd23b:webapp/web/README.md` |
| `tests/<id>/*.md` notes (findings, results, reviews) | Folded verbatim into [`tests/RESULTS.md`](../tests/RESULTS.md), appendices | `git show 3edd23b:tests/<id>/<file>` |
