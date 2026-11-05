# thesis-research-agent

Evidence-level answers to research questions: question -> plan (protocol) -> extractors read the papers -> evidence graph -> answer by deterministic rules. Evaluated on synthetic corpora with known truth (A extraction, B integration, C synthesis) and real sets, against a RAG baseline.

## Layout

| Path | What |
|---|---|
| [`backend/`](backend/README.md) | all Python packages; service map (gateway, engine, evaluation, api) |
| [`frontend/`](frontend/README.md) | web UI (Vite/React); `dist/` committed |
| [`data/`](data/README.md) | checked-in inputs: domain packs, earlier-work questions, concepts, corpus manifest |
| [`docs/`](docs/) | `architecture.md`, `runbook-slurm.md` (Codex), `prompt-writing.md`, `history.md` |
| `tests/` | test results (`tests/RESULTS.md`) and EV corpora (`tests/EV*`), not pytest code |
| `reports/` | recorded results; never edited |
| `scripts/` | plan runs, real-set prep, readclaim check, tunnels, e2e |
| `llm-setup/` | submodule [`thesis-llm-setup`](https://github.com/guptaaditya746/thesis-llm-setup): vLLM + LiteLLM on Slurm |

## Setup

```bash
git submodule update --init --recursive
uv sync --locked --all-groups                 # Python 3.13+, pins in uv.lock
uv run pytest -q                              # backend/ tests; no cluster or model needed
uv run evidence --help                        # also: evaluate, synth, webapp, agent, gold, score, packbuilder
```

WSL over a Windows checkout: `UV_PROJECT_ENVIRONMENT=~/.venvs/<name>` so uv keeps the Windows `.venv`.

## One corpus end to end, offline (regex, no model)

```bash
uv run evidence run --protocol data/domains/rag/protocols/rag-factuality.yaml \
    --corpus backend/synth/examples/rag-demo-explicit --out runs/evidence --extractors regex-only --run-id demo
uv run evidence replay runs/evidence/demo     # rebuilds from the record cache; every output hash must match
uv run evaluate score --run runs/evidence/demo --corpus backend/synth/examples/rag-demo-explicit --out runs/eval/demo
```

## Web app

```bash
uv run webapp serve --port 8080               # http://127.0.0.1:8080; needs $EV for jobs
uv run python -m webapp.tests.evidence_world /tmp/ev-world && EV=/tmp/ev-world uv run webapp serve   # offline world
```

- Flow per question: question -> protocol -> corpus -> run -> graph -> answer -> scores, baselines beside the engine.
- On Slurm: `docs/runbook-slurm.md` 0.3 (srun, ssh tunnel, omen-tunnels).
- Safety: no auth; binds 127.0.0.1, loopback Host names only, writes only same-origin JSON from loopback (`backend/webapp/guard.py`); jobs are fixed argv templates (`backend/webapp/evjobs.py`).
- Settings (dirs, job limits, dist path): `backend/webapp/settings.py`.

## Rules for agents

`AGENTS.md`, `CLAUDE.md`; prompt work: `docs/prompt-writing.md`. Supervisor's feedback: `.claude/skills/tim/`.
