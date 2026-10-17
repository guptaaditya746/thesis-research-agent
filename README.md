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
| `webapp/` | `webapp` | The viewer of the evidence-level flow (below); the earlier flow's pages under `/earlier` |
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

A read-only viewer of the files the commands above write (it starts no run and calls no model): question →
protocol (and proposals) → corpus → run (per paper the funnel, the items with their spans, every call down
to its model records or the agent's trace) → evidence graph → answer → scores A/B/C per level with 95 %
intervals, the RAG and agent baselines beside the engine, all against gaps, shift and benchmark records. The
earlier flow (questions, concept pick, claim on/off runs, gold, jobs, chat) is under `/earlier`.

```bash
EV=/path/to/ev uv run webapp serve --port 8080   # then http://127.0.0.1:8080 (through an SSH tunnel on the cluster)
```

It reads the layout of `docs/slurm-evidence-runbook.md` under `$EV`: `corpora/`, `runs/<group>/<name>/`
(engine runs and baseline answers), `scores/`, `proposals/`, the engine's record cache `cache/engine/` and
the agentic extractor's `agent-work/`; each can be set apart (`CORPORA`, `EV_RUNS`, `SCORES`, `EV_PROPOSALS`,
`EV_CACHE`, `EV_AGENT_WORK`, which defaults to the agentic extractor's own `EVIDENCE_AGENT_WORK_DIR` when that
is set; protocols from `evidence/protocols/`, `EV_PROTOCOLS`). The earlier pages read `RUNS`, `CORPUS`, `GOLD`,
`CONCEPTS` as before: the runbook's `in-job.env` exports `RUNS=$EV/runs`, which the viewer ignores (it reads
`EV_RUNS`) but the earlier pages take as their batch root, so start the app without it (or unset it). A small world made by the real tools with scripted models, to
look at offline: `uv run python -m webapp.tests.evidence_world /tmp/ev-world` and `EV=/tmp/ev-world`. The
frontend (`webapp/web`, React, built into `webapp/web/dist`, which is committed): `uv run --group frontend npm ci`
(Node from that dependency group), `npm run dev` (Vite, proxies `/api`),
`npm run dev:mock` (no backend), `npm test`, `npm run build`; after a change to the backend's models
`uv run webapp openapi -o webapp/web/openapi.json && npm run gen:api`.

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
