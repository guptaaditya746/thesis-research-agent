# thesis-research-agent

Evidence QA (`evqa`): a seed graph holds the truth, papers are written from it, and the QA pipeline
(Spec -> Find -> Extract -> Answer) answers questions from the papers alone; a layered evaluation scores it
against the seed. The Workbench (web UI) shows each step. See `docs/architecture.md`.

## Layout

| Path | What |
|---|---|
| [`backend/`](backend/README.md) | Python packages: `evqa`, `modelcall`, `jsonio`, `webapp`, `repo_paths` |
| `frontend/` | submodule [`thesis-workbench`](https://github.com/guptaaditya746/thesis-workbench): the Workbench (Vite/React); build `dist/` before `webapp serve` |
| [`data/`](data/README.md) | `seed/` (truth), `dataset/` (papers), `cache/` (downloads) |
| `configs/evqa/` | run configs |
| `external/paperorchestra/` | vendored paper writer |
| [`docs/`](docs/) | `architecture.md`, `design/slice1.md`, `prompt-writing.md`, `history.md` |
| `tests/`, `reports/` | recorded results of the earlier system; never edited |
| `ops/`, `scripts/` | cluster helpers, tunnels (`scripts/omen-tunnels`) |
| `llm-setup/` | submodule [`thesis-llm-setup`](https://github.com/guptaaditya746/thesis-llm-setup): vLLM + LiteLLM on Slurm |
| `baselines/` | submodule [`thesis-baselines`](https://github.com/guptaaditya746/thesis-baselines): answering baselines (PaperQA2, ...) to compare with evqa |

## Setup

```bash
git submodule update --init --recursive
uv sync --locked --all-groups                 # Python 3.13+, pins in uv.lock
uv run pytest -q                              # backend/ tests; no cluster or model needed
uv run evqa --help
(cd frontend && uv run --group frontend npm ci && uv run --group frontend npm run build)   # Workbench dist/
uv run webapp serve --port 8080               # Workbench at http://127.0.0.1:8080
```

Baselines (PaperQA2, long context; submodule `baselines/`, own uv env), on the GPU job like any run:

```bash
(cd baselines && uv sync --locked)
uv run evqa run --config configs/evqa/practice-pqa-rag.yaml --text     # also -pqa-agent, -pqa-agent-fixed, -long-context
uv run evqa eval runs/evqa/practice-qwen-<hash> --text                 # the same answer-text score for evqa
uv run evqa compare runs/evqa/practice-qwen-<hash> runs/evqa/practice-pqa-rag-<hash>
```

- Safety: no auth; binds 127.0.0.1, loopback Host names only (`backend/webapp/guard.py`); the API is read-only.

## Rules for agents

`AGENTS.md`, `CLAUDE.md`; prompt work: `docs/prompt-writing.md`. Supervisor's feedback: `.claude/skills/tim/`.
