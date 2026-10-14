# End-to-end build plan (13 Oct 2026)

Everything left in milestones 1–4, built on this machine in one go and then tested on Slurm in one Codex
session (`docs/slurm-e2e-runbook.md`, written last). Failures in that session are expected; the point is
that every part exists, is unit-tested here, and runs on the cluster for the first time together.

Starting point: `main` + branch `m1-cluster` (first real runs: infrastructure works, every run ended at the
budget with no answer; see `tests/RESULTS.md` M1-real). Integration branch: `e2e-build`.

## Decisions taken for this build (user delegated, 13 Oct)

| Topic | Decision |
|---|---|
| Final answer on the real model | The conclude replies are decoded under a JSON schema (vLLM structured outputs through LiteLLM, as B9 proved for regex), so the reply *is* the answer object. Budget warnings at 50/75/90 %. The agent also keeps a draft answer file in its scratch directory; if conclusion still fails, the harness validates that draft and uses it, recorded as such. |
| Prompt | v2: correct corpus file names (`p12.md` and anthology ids such as `2025-acl-long-892.md`), claim in the same command that finds a fact, write the draft answer early. v1 stays for reproducing the M1-real runs. |
| Budget (provisional, the user freezes it after the Slurm test) | 60 steps / 2,000,000 tokens per run (the token sum grows with the context, so 400k lasted only ~26 steps); attach 6 steps / 60k per fact unchanged. |
| Context | Proactive observation masking (row 1.15): outputs older than the last 8 commands become one-line stubs (claim replies kept), so prompts stay well under 61,440. |
| Questions | 12 from the labelling repo's set (6 corpus-wide, 6 ambiguous), reworded for the Markdown corpus. Listed below. A later Claude session with corpus access may replace them. |
| Concept pick | Provisional: Codex picks brief 1 on Slurm (`picked_by: provisional-first`); the web app lets the user change a pick before gold is built. Picks are recorded with who picked. |
| Gold D | The method of `github.com/guptaaditya746/labelling` (screen every paper, extract question-scoped facts, model triage, stratified human review in Argilla on Omen, Cohen's κ on ~20 % overlap, screening false-negative check, draft key before review), re-implemented for the Markdown corpus. Model: `sub-model-1`/`-2` (Qwen3-30B-A3B-Instruct), not the agent's orchestrator, to keep gold apart from the system it scores. Whole chunks are screened (no ranker), removing the old ranker bias. Quotes go through `agent/anchor.py`, the same check the agent's claims pass. |
| Judge | LLM judge (`sub-model`) for "does this quote support this fact" and for soft fact matching; calibrated against people in Argilla (200–300 claims, threshold on half, κ on the other half). |
| Primary outcome (pre-registered) | Share of answer facts whose quote supports them (judge), claim_on vs claim_off after attach. Paired over the 12 questions (mean of 3 repeats), Wilcoxon signed-rank, two-sided, α = 0.05, with a BCa bootstrap interval on the mean difference. Secondary: fact precision/recall/F1 and row F1 against the key, unsourced share, tokens and time with and without attach. |
| Frontend | Full app: questions → concept cards → pick → start and watch a run → answer → knowledge graph → claim walk to the highlighted quote; compare conditions; results dashboard; gold status; chat about runs. |
| Packages | Prefer maintained libraries over own code (see below). |

## Packages

Python (pinned in `pyproject.toml`): mini-swe-agent (loop, existing), litellm (via mini), rdflib (PROV-O,
existing), **pyoxigraph** (SPARQL store over all runs), **FastAPI** + uvicorn + **sse-starlette**
(backend, live streams), **pydantic-ai** (`pydantic-ai-slim[openai]`, OpenAI-compatible provider pointed
at LiteLLM) for every LLM call outside the agent loop (gold screening/extraction/triage, judge, chat agent),
**argilla** v2 SDK (review), **scipy** (`scipy.stats.bootstrap` BCa, `wilcoxon`), **numpy**, **pandas**
(report tables), **scikit-learn** (`cohen_kappa_score`), **statsmodels** (`proportion_confint` Wilson),
jsonschema, httpx. Node comes from the `frontend` dependency group (`nodejs-wheel`), so
`uv run --group frontend npm ...` works anywhere uv does.

Frontend (`webapp/web`): Vite + React 19 + TypeScript, Tailwind v4, **shadcn/ui** components (sidebar,
card, table, tabs, badge, sheet, dialog, select, tooltip, scroll-area, resizable, chart, sonner, skeleton,
command), **TanStack Query** (data), **React Router** (pages), **@xyflow/react** + dagre (knowledge graph),
**assistant-ui** (`@assistant-ui/react` + `@assistant-ui/react-ai-sdk`) for the chat, recharts through
shadcn `chart` (dashboard), **openapi-typescript** (types generated from the backend's OpenAPI).

Any new dependency: pin an exact version, say why in the commit.

## Layout and ownership (one work package = one branch)

| WP | Branch | Owns (may create/edit) | Must not edit |
|---|---|---|---|
| A agent fix (1.13, 1.15) | `e2e/agent-fix` | `agent/loop.py`, `agent/prompts/*-v2*`, `agent/prompts.py`, `agent/rundir.py` (BUDGET), `agent/parse.py`, budget fields of `agent/manifests/*.json`, `agent cli run` defaults, tests | gold/, scoring/, webapp/ |
| A2 subagents (2.12) | `e2e/spawn` (after A) | `agent/spawn.py`, `agent/bin/spawn`, loop/broker hooks for spawn, tests | as A |
| B questions, concepts, re-exec, Slurm scripts (2.3, 2.13) | `e2e/questions` | `questions/`, `agent/concept_step.py`, `agent/reexec.py`, `agent/replay.py`, concept/reexec/replay subcommands in `agent/cli.py`, question/concept fields of `agent/manifests/m4-72.json`, `slurm/`, `scripts/e2e-*.sh` | loop.py, budgets |
| C1 gold builder (M3) | `e2e/gold-build` | `gold/{chunks,screen,extract,build,triage,pool,draft,docmd}.py`, `gold/prompts/`, its `gold` subcommands, `gold/tests/` | agent/ (import only) |
| C2 review and judge (M3) | `e2e/gold-review` | `gold/{argilla_io,review,export,agreement,screening_check,judge}.py`, its `gold` subcommands, `gold/tests/` | agent/ (import only) |
| D scoring (M4) | `e2e/scoring` | `scoring/` (`scoring/store.py` exists: `RunStore(path).load_run/load_all/runs/query(sparql, run_id=)`; extend additively) | agent/, gold/ (import only) |
| E backend | `e2e/webapp-api` | `webapp/*.py`, `webapp/tests/` | everything else (import only) |
| F frontend | `e2e/webapp-ui` | `webapp/web/` | everything else |

`gold/llm.py` (pydantic-ai on LiteLLM: model per alias, round-robin `Rotation`, `structured()` call with schema-constrained output, `prompt_sha256`, `JsonlCache`) is shared and already written; extend it only additively. `gold/cli.py`, `scoring/cli.py`, `webapp/cli.py` exist as stubs. Two packages adding subcommands to the same
`cli.py` (C1 and C2) each put theirs in a `register(subparsers)` function in their own module and add one
import line to `gold/cli.py`; the merge resolves the two lines.

## Environment (all components)

| Variable | Meaning | Default |
|---|---|---|
| `CORPUS` | frozen Markdown corpus with `manifest.json` (read-only) | — |
| `RUNS` | runs root; `scripts/e2e-batch.sh <manifest>` puts a manifest's runs in `$RUNS/<manifest name>/` (its last line `RUNS_ROOT=...`), which is the RUNS that scoring and the web app take for that manifest, so the M4 report never mixes in smoke runs | `runs` |
| `GOLD` | gold working directory (D, review exports, keys, judge cache) | `gold-data` |
| `CONCEPTS` | concept sessions | `concepts` |
| `LITELLM_BASE_URL` | LiteLLM proxy | `http://127.0.0.1:4000/v1` |
| `LITELLM_MASTER_KEY` | API key; read at call time, never logged | — |
| `ARGILLA_API_URL`, `ARGILLA_API_KEY` | Argilla on Omen (through `scripts/omen-tunnels`) | — |
| `AGENT_ROOT` | pinned sandbox toolchain | — |

Model aliases: `orch-model` (agent loop, concept step), `sub-model-1`, `sub-model-2` (gold, judge, chat,
subagents; spread load over both). Thinking off everywhere.

## The 12 questions (`questions/questions.json`)

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

Format: `{"schema_version": 1, "questions": [{"id", "category", "question", "source", "notes"}]}`.

## File contracts between packages

### Concepts (B → C1, D, E)
`$CONCEPTS/<qid>/` as `agent/concept_step.py` writes it (`proposal.json`, `concept.json`, `concept.sha256`,
`events.jsonl`, `session.json` with `attempts`: each proposal attempt's sampling, commit and proxy). B adds `$CONCEPTS/picks.json`:
`{"<qid>": {"choice": 1, "title": "...", "picked_by": "provisional-first" | "user" | "claude", "reason": "...", "concept_sha256": "..."}}`.
`concept_step.pick(..., replace=True)` refuses once `$GOLD/<qid>/` holds anything (`concept_step.gold_files`), unless forced;
`propose`, `pick` and the `picks.json` rebuild lock their directory, so callers in threads or processes need no lock of their own.

### Trajectory (A → B)
`agent replay` (C6) rebuilds every prompt from `trajectory.json`, so the loop keeps what the model saw: a message
changed after a call keeps its first text in `extra.original_content`; stubs are always the oldest command outputs
and never change back, and each `ai_model_invocation` records `custom_metadata.masked_observations`; replies are
shortened only after the second context-full 400. `agent/tests/test_replay.py` (`test_a_long_run_replays`,
`test_context_full_run`) checks this on the real loop once `e2e/agent-fix` is merged.

### Gold (C1 → C2 → D, E)
Per question, `$GOLD/<qid>/`:

| File | Writer | Content |
|---|---|---|
| `chunks.jsonl` | C1 | `{paper_id, chunk, start, end, heading, chars}`: raw character offsets into the corpus file |
| `screening.jsonl` | C1 | one per paper: `{paper_id, status: relevant\|not_relevant\|no_text\|error, chunks_relevant: [int], findings: [str], model, prompt_sha256}` |
| `candidates.jsonl` | C1 | one per extracted fact: `{id: "<qid>-c000001", qid, paper_id, file, row: {<column or edge fields>}, s, p, o, quote, anchor: <agent.anchor selector> \| null, anchor_status: "ok" \| <rejection reason>, chunk, model, prompt_sha256}` |
| `doc.json`, `doc.md` | C1 | D: `{qid, concept_sha256, built: {git_commit, models, settings, started_at, ended_at}, coverage: {papers, relevant, not_relevant, no_text, error}, rows: [{key, cells, candidates: [ids]}], counts}`; `doc.md` for reading |
| `triage.jsonl` | C1 | `{id, label: answers\|context\|irrelevant, model}` |
| `pool.jsonl`, `pool.strata.json` | C1 | review records (every answers+context candidate, plus a seeded sample of the rest) and stratum sizes |
| `key.draft.json` | C1 | draft answer key (below) from triage alone, `version: "v1-draft"`, `reviewed: false` |
| `review/*.jsonl`, `snapshots/` | C2 | Argilla exports and pre-adjudication overlap snapshots |
| `key.json` | C2 | reviewed answer key, `version: "v1"`, `reviewed: true` |
| `report.json` | C2 | κ with bootstrap interval, triage miss estimate (Wilson), screening false-negative rate (Wilson) |

**Answer key** (`key.json` / `key.draft.json`) has the agent's answer shape so scoring compares like with
like: `{qid, concept_sha256, kind, version, reviewed, rows: [{id, cells | source/predicate/target..., facts: [{id, s, p, o, paper_id, quote, vital: bool, candidate_id}]}], notes}`. Rows validate against `agent.concept.answer_schema_for(concept)` once the gold-only fact fields (`paper_id`, `quote`, `vital`, `candidate_id`) are stripped.

### Judge (C2 → D, E)
`gold/judge.py`:
- `support(fact: {s, p, o}, quote: str, *, context: str | None = None) -> Verdict` with `Verdict = {label: "supports" | "partial" | "no", rationale, model, prompt_sha256, cached: bool}`;
- `same_fact(run_fact, key_fact, concept) -> {match: bool, rationale, ...}` for soft matching;
- `same_row(run_row, key_row, concept) -> {match: bool, ...}` for row matching when cells differ in wording.
Both cache in `$GOLD/judge-cache.jsonl`, keyed by sha256 of canonical input + model + prompt hash, so a
rescore costs no model calls. Calls go through `gold/llm.py` (pydantic-ai, structured output).
Scoring (D) uses `default_judge()` and awaits its async twins (`asupport_pair(pair, Corpus(corpus))`,
`asame_fact`, `asame_row`) on one event loop (a pydantic-ai HTTP client must not be shared between loops),
so support is judged with `context_for` (paper id + 600 characters each side), the input the calibration
measured; `partial` counts as supporting as `$GOLD/judge-report.json` `calibration.partial_counts_as` says.

### Scores (D → E)
- `<run>/score.json`: `{run_id, qid, condition, seed, exit_status, verify_ok, key_version, rows: {tp, fp, fn, precision, recall, f1}, facts: {strict: {...}, normalised: {...}, soft: {...}}, vital_recall, support: {facts, with_claims, supports, partial, no, unsourced, support_share}, cost: {steps, model_calls, tokens, tokens_without_attach, seconds, seconds_without_attach, claim_steps, claim_step_tokens}}`.
  `score run <run>` without `--key` takes the run's question's `$GOLD/<qid>/key.json`, else `key.draft.json`;
  judged precision reads the facts reviewers rejected as wrong from `$GOLD/<qid>/export.json` (C2). score.json
  adds fields (pending judge decisions, run settings, judge identity, scorer version; `scoring/README.md`).
- `$RUNS/report/`: `scores.jsonl`, `report.json` (per question × condition means, paired differences, BCa intervals, Wilcoxon results, the pre-registered primary test), `report.md`, CSV tables. `score batch $RUNS --manifest $RUNS/<name>/manifest.json` reads the attempts from the manifest's runs_root and writes here.
- `$RUNS/.oxigraph/`: pyoxigraph store, one named graph per run (`urn:thesis-agent:run:<run_id>`), built from each run's `graph.ttl` (`score store`).

## Backend API (E; F builds against this)

FastAPI app `webapp.app:create_app()`, all JSON under `/api`, the built frontend served from
`webapp/web/dist` at `/`. `webapp serve --host 127.0.0.1 --port 8080`; `webapp openapi > webapp/web/openapi.json`.

| Method, path | Returns |
|---|---|
| `GET /api/health` | `{ok, version}` |
| `GET /api/config` | `{corpus, runs_root, gold_root, concepts_root, llm_base_url, llm_key_set: bool, argilla_url}` |
| `GET /api/questions` | `[{id, category, question, concept: {status: none\|proposed\|picked, title, picked_by} , gold: {status: none\|building\|draft\|reviewed, rows, facts}, runs: {claim_on, claim_off}}]` |
| `GET /api/questions/{qid}` | question + `briefs: [concept brief]`, `picked: {choice, picked_by, reason} \| null` |
| `POST /api/questions/{qid}/concepts/propose` `{temperature, seed}` | `Job` |
| `POST /api/questions/{qid}/concepts/pick` `{choice, picked_by, reason}` | updated question |
| `GET /api/runs?qid=&condition=` | `[RunSummary]`: `{run_id, qid, condition, seed, temperature, created_at, exit_status, steps, model_calls, tokens, seconds, rows, facts, claims_accepted, claims_rejected, verify: ok\|failed\|unknown, score: {support_share, fact_f1, row_f1} \| null, live: bool}` |
| `POST /api/runs` `{qid \| concept_path, condition, temperature, seed, steps, tokens, sandbox, attach: bool}` | `Job` (runs `agent run`, then attach for claim_off, verify, pairs, graph, export-prov, score) |
| `GET /api/runs/{run_id}` | `{summary, config, concept, answer, verify: {ok, errors, stats}}` |
| `GET /api/runs/{run_id}/steps` | `[Step]`: `{step, phase, model_call: {tokens, seconds, parse, reply, finish_reason}, command, exit_code, timed_out, output_head, output_bytes, claims: [ClaimRef], coverage: [reason], agent_id, origin}` |
| `GET /api/runs/{run_id}/steps/{step}/output` | text/plain, full output |
| `GET /api/runs/{run_id}/stream` | SSE: `event: record` per new events.jsonl line (raw record JSON), `event: done` when answer.json appears |
| `GET /api/runs/{run_id}/claims` | `[Claim]`: `{claim_id, status, reason, s, p, o, file, paper_id, quote, step, agent_id, origin, anchor: {start, end} \| null}` |
| `GET /api/runs/{run_id}/graph` | graph.json as is (`nodes`, `edges`) |
| `GET /api/runs/{run_id}/facts/{fact_id}/walk` | `{fact, row_id, claims: [{claim, step: Step, passage: Passage}], support: Verdict \| null}` |
| `GET /api/runs/{run_id}/score` | score.json or 404 |
| `GET /api/corpus/{paper_id}?start=&end=&context=1500` | `Passage`: `{paper_id, title, text, highlight: {start, end}, offset}`: the window around the span; `title` from the file's first heading |
| `GET /api/gold` | `[{qid, status, coverage, counts, key_version, report}]` |
| `GET /api/gold/{qid}/key` | key.json or key.draft.json |
| `GET /api/results` | `$RUNS/report/report.json` or 404 |
| `POST /api/sparql` `{query, run_id?}` | `{vars, rows}` from the pyoxigraph store; read-only (SELECT/ASK/CONSTRUCT only) |
| `GET /api/queries/{n}?run_id=&...` | the five provenance queries (agent/queries.py) as JSON rows |
| `GET /api/jobs`, `GET /api/jobs/{id}` | `Job`: `{id, kind, args, state: queued\|running\|done\|failed, started_at, ended_at, run_id?, exit_code}` |
| `GET /api/jobs/{id}/log` | SSE of the job's log lines |
| `POST /api/chat` | Vercel AI SDK UI-message stream (pydantic-ai's Vercel AI adapter): a pydantic-ai agent on `sub-model` with tools `list_runs`, `get_run`, `get_answer`, `get_claims`, `walk_fact`, `sparql`, `read_passage`, `get_results`; read-only |

Jobs run as subprocesses of the server (one at a time per kind by default), logs under `$RUNS/.jobs/`.
No authentication: the server binds to 127.0.0.1 and is reached through an SSH tunnel.

## Frontend pages (F)

Sidebar layout (shadcn `sidebar`), dark/light toggle.
1. **Overview** `/`: one row per question: concept status, gold status, runs per condition, scores; pipeline progress.
2. **Question** `/questions/:qid`: concept brief cards side by side (definition, measure, scope, answer shape as a mini table/graph template, competency questions); pick button with "picked by"; propose button (job).
3. **Runs** `/runs`: filterable table; "New run" dialog (job).
4. **Run** `/runs/:runId`: header stats (exit, steps, tokens, time, claims, verify) and tabs:
   - *Answer*: rows table; each fact a badge (supported / partial / not supported / unsourced); click opens the **claim walk** sheet: fact → claim(s) → step (reasoning-free model call stats, command, output head) → passage with the quote highlighted;
   - *Graph*: React Flow knowledge graph (paper and entity nodes, edges labelled by predicate, click edge → claim walk);
   - *Timeline*: steps in order, live while the run is going (SSE), coverage notices, budget line, phase changes;
   - *Claims*: table with accepted/rejected and reason;
   - *Provenance*: the five queries as buttons + a SPARQL editor;
   - *Score*: score.json against the key (matched / missed / wrong facts).
5. **Compare** `/compare/:qid`: claim_on vs claim_off runs side by side (answers, support, cost).
6. **Results** `/results`: charts (support share by condition with intervals, F1, unsourced, tokens and time with/without attach), per-question table, the primary test.
7. **Gold** `/gold`: per question coverage, counts, review progress, κ, link to Argilla.
8. **Jobs** `/jobs`: list and live log.
9. **Chat**: assistant-ui thread in a right-side sheet available everywhere, scoped to the current run when on a run page.

## Testing rules (every WP)

- Tests run in WSL on the `/mnt/c` checkout with a per-branch environment:
  `UV_PROJECT_ENVIRONMENT=~/.venvs/<branch-name> uv sync --locked --all-groups && uv run pytest -q`.
  The whole suite must stay green (265 passed, 1 skipped at the start).
- No test needs the cluster, a GPU, a network model or Argilla: use scripted models (as `agent/tests`),
  pydantic-ai's `TestModel`/`FunctionModel`, fake HTTP servers, and the D1 fixture papers
  (`agent/tests/conftest.py: write_corpus`).
- Frontend: `npm run build` and `npm run lint` must pass; component tests with Vitest where logic lives.
- Commit on the WP branch, small commits, messages like the existing history; never push `main`.
