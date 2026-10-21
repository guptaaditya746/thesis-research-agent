# thesis-research-agent

Evidence-level answers to research questions: a hand-written executable research protocol, run by a Python
engine with a library of interchangeable evidence extractors, builds an evidence graph from the papers and
derives the answer from it by deterministic rules. It is evaluated on synthetic corpora with known ground
truth (extraction A, integration B, synthesis C) against an answer-level retrieve-then-answer baseline. First
question: "Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?"

**Start here: [`docs/STATE.md`](docs/STATE.md)**: the design, our additions, the decisions, the plan and what
is open.

## Packages

| Package | Command | What |
|---|---|---|
| `evidence/` | `evidence` | The evidence-level system. **Supervisor's design, 14 Oct: protocol, extractor library, engine, evidence graph, deterministic synthesis.** Hand-written protocol (`evidence/protocols/`), regex and single-call LLM extractors behind one contract, the engine, `graph.json`, `answer.json` |
| `synth/` | `synth` | Synthetic benchmark (supervisor's design): seeded ground truth, difficulty levels, template and LLM renderers, fidelity checks ([`synth/README.md`](synth/README.md)) |
| `evaluation/` | `evaluate` | Scores A (extraction), B (integration), C (synthesis) per level (supervisor's design); the retrieve-then-answer baseline; plus our additions below |
| `agent/` | `agent` | Earlier work: the research agent (sandboxed loop, `claim` broker, graph, PROV-O, replay). Now used only as the agentic extractor and the agent baseline |
| `jsonio/`, `modelcall/` | (libraries) | Shared plumbing: canonical JSON and atomic file writers (`jsonio`); every model call through `modelcall.ask` (gateway, one event loop, JSONL cache, prompt loader, model pins), used by the baselines, proposal, judge, gold, synthetic renderer and the engine's recorder |
| `webapp/` | `webapp` | The evidence-level flow as a guided stepper per question: views the files and starts the missing steps as jobs (below) |
| `gold/`, `scoring/`, `questions/` | `gold`, `score` | Earlier work: gold document D and Argilla review, claim on/off scoring, the 12 questions ([`docs/earlier-work.md`](docs/earlier-work.md)). `gold/` is the method planned for the 337-paper check |

**Our additions** (not the supervisor's): the agentic extractor (`evidence/agentic/`), the agent baseline
(`evaluation/baselines/agent.py`), the locate step and locate recall, the extractor cascade with
`found_by` and marginal contribution, the provenance and replay lane (hash-chained events, record cache,
exact replay, re-execution as a stability measurement), the PROV-O export, the funnel engine
(`evidence run --strategy gaps`) and the proposal flow (`evidence propose`, below) with its optional
vocabulary snapshot (`docs/STATE.md`).

Files and formats: [`docs/evidence-system.md`](docs/evidence-system.md) (Part A the files between the
packages, Part B the extractor contract). One synthetic corpus end to end, offline (regex extractors, no
model):

```bash
uv run evidence run --protocol evidence/protocols/rag-factuality.yaml --corpus synth/examples/rag-demo-explicit \
    --out runs/evidence --extractors regex-only --run-id demo
uv run evidence replay runs/evidence/demo                  # rebuilds from the record cache; every output hash must match
uv run evaluate score --run runs/evidence/demo --corpus synth/examples/rag-demo-explicit --out runs/eval/demo
```

A protocol proposed from a question (Part E of `docs/evidence-system.md`; frame, critic and cards call the
model, `orch-model` by default, cached in the proposal directory; nothing runs the result):

```bash
uv run evidence propose frame --question "Does retrieval-augmented generation improve ...?" \
    --vocab rag-factuality --out proposals/rag      # frame.json: population, roles, outcomes, sources
uv run evidence propose draft proposals/rag         # draft.yaml + draft.sources.json, from the example protocol
uv run evidence propose critic proposals/rag        # critic.json: deterministic checks + LLM checklist
uv run evidence propose cards proposals/rag         # cards.json + decisions.yaml (edit: choice, reason, by)
uv run evidence propose freeze proposals/rag        # protocol.yaml (revision 1) + proposal.json
uv run evidence propose amend proposals/rag --reason "..." [--before-main-run]   # after editing protocol.yaml
uv run evidence vocab build --name N --source DIR --out evidence/vocab/N.json    # snapshot from local files
```

## Web app

The supervisor's flow as a guided stepper per question, which views what is on disk and starts what is
missing: select a question (from [`evidence/questions.yaml`](evidence/questions.yaml), never typed) →
protocol → corpus → run → evidence graph → answer → scores A/B/C, the RAG and agent baselines beside the
engine. Every result page of the viewer is linked from it (per paper the funnel, the items with their spans,
every call down to its model records or the agent's trace; scores with 95 % intervals, all against gaps, shift,
benchmark records).

| Step | What the app starts (one job each; the runbook's commands, `python -m webapp.tool ...`) | Lane |
|---|---|---|
| Protocol | the hand-written protocol, its agentic variant or a frozen proposal; **propose**: `evidence propose frame`, `draft`, `critic`, `cards` (resumed from the first missing file), then the eight cards as a form that writes `decisions.yaml` and shows what freeze would refuse, then `evidence propose freeze`. Amendments stay on the command line | model; freeze cpu |
| Corpus | choose one under `$EV/corpora`, or `synth build --renderer template` (name, seed, studies, levels, knobs). LLM-written corpora take hours: Slurm only (runbook step 1) | cpu |
| Run | `evidence run` (regex-only, cascade, or the agentic protocol; all or gaps; model, default `orch-model`) into `runs/<group>/<name>` with the runbook's group names; `evaluate rag-baseline --retrieval global --k 8`, `evaluate agent-baseline`; `evaluate score` (with the corpus's baselines) and `evaluate compare` | model (regex-only, score, compare: cpu) |

At most one model job runs at a time (`WEBAPP_MODEL_JOBS`, default 1; the rest queue), two cpu jobs beside it
(`WEBAPP_CPU_JOBS`). A model job is refused (409, said in the UI) when the server has no `LITELLM_MASTER_KEY` or
the gateway does not answer `GET $LITELLM_BASE_URL/models`, so it never fills the shared record cache with error
results; an engine run that still ends with failed extractor calls is "done with N failed calls" (job, run list
and run page), and "retry errors" (`--retry-errors`) runs them again. Jobs keep their state and logs in
`$EV/.jobs/` (a reload or a restarted server lists them; a job whose process outlived its server stays running
and cancellable, any other one that was running is marked failed); the Jobs page shows status, log tail and
Cancel, which stops the command's whole process group. Saving the cards refuses to overwrite a `decisions.yaml`
changed since the form loaded it (reload or overwrite) and keeps each card's `by` unless you change the card. Outputs go into the same `$EV` layout as the runbook (`corpora/`, `runs/<group>/<name>/`,
`scores/`, `proposals/`, `cache/engine/`, `cache/rag-baseline.jsonl`, `agent-work/`), so a result made in the
app looks exactly like one made on the command line or on Slurm, and the other way round.

On the cluster, start it inside the stack job with the session environment of the runbook (step 0.3), so the
jobs reach the gateway with the key from `llm-setup/.env` (`LITELLM_MASTER_KEY`, `LITELLM_BASE_URL`,
`AGENT_ROOT`, `EVIDENCE_AGENT_WORK_DIR`), and reach it through an SSH tunnel:

```bash
srun --jobid "$JOB" --overlap --pty bash -l          # on the login node; then, on the node:
source "$EV/in-job.env" && uv run webapp serve --port 8080
ssh -L 8080:127.0.0.1:8080 <node>                    # from your machine (via the login node), then http://127.0.0.1:8080
```

Or through the Webis gateway with `scripts/omen-tunnels` (service `harness-ui`: laptop 127.0.0.1:25173 → gateway
127.0.0.1:24173 + offset → the compute end's 127.0.0.1:8080). **Troubleshooting** when the page does not open:

- *Start order.* First the web app, then the compute end **on the node where `webapp serve` runs** (the `-R` hop
  forwards to port 8080 of the machine it is started on, so a start on the login node reaches nothing):
  `srun --jobid "$JOB" --overlap --pty bash -l`, then `scripts/omen-tunnels-external compute start harness-ui`
  (alone it refuses when nothing listens on 127.0.0.1:8080 there, `--no-check` skips that; beside other services it only warns). Then on the laptop
  `omen-tunnels-external laptop start harness-ui`, and open http://127.0.0.1:25173 (not another name: the app
  answers only 127.0.0.1, localhost and ::1, `WEBAPP_ALLOWED_HOSTS`).
- *Same offset on both ends.* Use `omen-tunnels-external` (gateway port 25173) on both, or `omen-tunnels`
  (24173) on both. Each end prints its gateway port in its "Ready" lines and in `status`; they must match. A stale
  copy on the laptop's PATH ignored the offset once (tests/RESULTS.md, T2): the wrapper now runs the
  `omen-tunnels` beside it (install both together; a wrapper copied alone still uses PATH). A laptop hop already running other services refuses a new list: `stop`, then
  start all services together.
- *Three checks.* (1) On the node: `curl -s http://127.0.0.1:8080/api/health` (or `omen-tunnels compute check`)
  answers, so the web app runs there on 8080 and nothing else holds the port. (2) Both ends' `status` say `up` with
  the same gateway port; "Cannot start compute hop; listener port(s): 25173 on gateway" means another session
  holds that port on the shared gateway. (3) On the laptop: `omen-tunnels-external laptop check` GETs
  http://127.0.0.1:25173/ and `/api/health` (5 s) and prints the status, the guard's 400 message, "connection
  refused" (laptop hop down) or "closed without an answer" (laptop hop up, but the compute end is down, on
  another node or on another gateway port).

Offline, with no model (template corpora, regex-only runs, scores, the cards and freeze work; model jobs fail
or record failed calls): `uv run python -m webapp.tests.evidence_world /tmp/ev-world`, then
`EV=/tmp/ev-world uv run webapp serve`. The directories can be set apart (`CORPORA`, `EV_RUNS`, `SCORES`,
`EV_PROPOSALS`, `EV_CACHE`, `EV_AGENT_WORK`, `EV_PROTOCOLS`, `EV_QUESTIONS`; `webapp/settings.py`), but jobs
need `$EV`. Safety: no authentication; the server binds to 127.0.0.1, answers only loopback Host names and
takes writes only from a loopback client as same-origin JSON (`webapp/guard.py`); every job is an argv from a
fixed template (no shell), every name a plain directory name, every path checked to stay inside its root
(`webapp/evjobs.py`). The frontend (`webapp/web`, React, built into `webapp/web/dist`, which is committed):
`uv run --group frontend npm ci` (Node from that dependency group), `npm run dev` (Vite, proxies `/api`),
`npm run dev:mock` (no backend), `npm test`, `npm run build`; after a change to the backend's models
`uv run webapp openapi -o webapp/web/openapi.json && npm run gen:api`. The pre-14-Oct app (questions, concept
pick, claim on/off runs, gold, chat) was removed on 18 Oct; it is in git at `72da5dd`
([`docs/earlier-work.md`](docs/earlier-work.md)).

## Setup

Everything runs through uv (Python 3.13 or later, dependencies pinned in `uv.lock`):

```bash
git submodule update --init --recursive
uv sync --locked --all-groups
uv run pytest -q                              # every package's tests; no cluster or model needed
uv run evidence --help                        # likewise synth, evaluate, agent, gold, score, webapp
```

On WSL over a Windows checkout, give uv its own environment (`UV_PROJECT_ENVIRONMENT=~/.venvs/<name>`) so it
does not replace the Windows `.venv`.

## Documents

| Path | What |
|---|---|
| [`docs/STATE.md`](docs/STATE.md) | The one page to plan from |
| [`docs/evidence-system.md`](docs/evidence-system.md) | Interfaces between the packages (Part A) and the extractor contract (Part B) |
| [`docs/slurm-evidence-runbook.md`](docs/slurm-evidence-runbook.md) | The first live run on Slurm (Codex runs it) |
| [`synth/README.md`](synth/README.md) | The synthetic benchmark generator |
| [`tests/RESULTS.md`](tests/RESULTS.md) | Every infrastructure and behaviour test result; logs and scripts under `tests/<id>/` |
| [`docs/earlier-work.md`](docs/earlier-work.md) | The system before 14 Oct, its measured numbers, and where the removed documents are in git |
| `thesis_pipeline.html` | One-page diagram of the design (click any box for details) |
| `llm-setup/` | Submodule [`thesis-llm-setup`](https://github.com/guptaaditya746/thesis-llm-setup): vLLM + LiteLLM on Slurm |
| `scripts/` | Agent-root and corpus builds, `omen-tunnels*` (Argilla, Langfuse), and the earlier e2e session's `e2e-*.sh` |

Framing discussion: https://claude.ai/code/artifact/c4258535-0673-4590-83f9-4377ee7057fa
