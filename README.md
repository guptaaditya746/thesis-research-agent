# thesis-research-agent

Evidence QA (`evqa`): a seed holds the true facts, papers are written from it, and the QA pipeline
(Spec -> Find -> Extract -> Answer) answers questions from the papers alone; the scorer grades the answers
against the seed. The Workbench (web UI) shows each step. Details: `docs/architecture.md`.

## How the repos fit together

This repo holds the QA engine (`backend/`) and pulls in 7 sub-repos (git submodules, all
github.com/guptaaditya746):

```
                    llm-setup (vLLM + LiteLLM on Slurm: the Qwen models)
                         ^
                         |  model calls (optionally through services/model-queue)
                         |
services/paper-factory --writes papers + facts--> data (thesis-benchmark)
                                                    |  papers, questions, gold
                                                    v
                         backend/evqa (this repo) --answers--> services/thesis-scorer --> scores
                         baselines (PaperQA2, long context) --answers--^
                                                    |
                                                    v
                                     frontend (thesis-workbench): shows it all
```

| Path | Repo | What |
|---|---|---|
| `backend/` | (this repo) | Python packages: `evqa` (QA engine), `modelcall`, `jsonio`, `webapp` (API), `repo_paths` |
| [`data/`](data/README.md) | thesis-benchmark | `seed/` (truth), `dataset/` (papers); `cache/` is local only |
| [`services/paper-factory/`](services/paper-factory/README.md) | Paper-factory | writes the synthetic papers and fact rows into `data/` |
| [`services/thesis-scorer/`](services/thesis-scorer/README.md) | thesis-scorer | scores any system's answers against the gold |
| [`services/model-queue/`](services/model-queue/README.md) | model-queue | one queue in front of LiteLLM so the GPUs never overflow |
| [`baselines/`](baselines/README.md) | thesis-baselines | other answering systems (PaperQA2, long context) to compare with evqa |
| [`frontend/`](frontend/README.md) | thesis-workbench | the Workbench (Vite/React); build `dist/` before `webapp serve` |
| [`llm-setup/`](llm-setup/README.md) | thesis-llm-setup | vLLM + LiteLLM on Slurm; admin-approved, read-only |
| `configs/evqa/` | | run configs (`bench4/` = the four-domain benchmark) |
| `ops/`, `scripts/` | | `injob.sh` (run inside the GPU job), `bench4.sh` (four-domain build), `local-venv.sh`, tunnels |
| `thesis-writing/` | | thesis chapter drafts and evidence audits |
| `docs/` | | `architecture.md`, `prompt-writing.md`, `history.md`, `design/` (current), `archive/` (old notes and results; never edited) |

## Setup

```bash
git submodule update --init --recursive
source ops/local-venv.sh                      # Python env on the node's local disk (/tmp); ~3 min once per job
uv run pytest -q                              # backend tests, ~6.5 min; no cluster or model needed
uv run evqa --help
(cd frontend && uv run --group frontend npm ci && uv run --group frontend npm run build)   # Workbench dist/
uv run webapp serve --port 8080               # Workbench at http://127.0.0.1:8080
```

Without `source ops/local-venv.sh`, `uv run` uses `.venv` on the network disk: same results, about 2x slower tests.

Run on the GPU job (Qwen gateway): `srun --jobid <job> --overlap ops/injob.sh uv run evqa run --config configs/evqa/bench-qwen.yaml`.

Baselines (own uv env in `baselines/`), on the GPU job like any run:

```bash
(cd baselines && uv sync --locked)
uv run evqa run --config configs/evqa/practice-pqa-rag.yaml --text     # also -pqa-agent, -pqa-agent-fixed, -long-context
uv run evqa eval runs/evqa/practice-qwen-<hash> --text                 # the same answer-text score for evqa
uv run evqa compare runs/evqa/practice-qwen-<hash> runs/evqa/practice-pqa-rag-<hash>
```

Four-domain benchmark (paper-factory -> data -> questions): `ops/bench4.sh`, notes in `docs/design/four-domain-benchmark.md`.

- Safety: no auth; binds 127.0.0.1, loopback Host names only (`backend/webapp/guard.py`); the API is read-only.
- Secrets live in `.env` files (never committed), e.g. `llm-setup/.env` (gateway key); `ops/injob.sh` loads it.

## Rules for agents

`AGENTS.md`, `CLAUDE.md`; prompt work: `docs/prompt-writing.md`. Supervisor's feedback: `.claude/skills/tim/`.
