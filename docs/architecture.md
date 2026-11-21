# Architecture

Evidence QA (`evqa`): a seed graph (the truth) -> papers written from it -> Spec / Find / Extract / Answer per question
-> layered evaluation against the seed. The Workbench (web UI) shows every step. Step notes: `docs/design/slice1.md`.

## Services (one process; modules, no HTTP between them)

| Service | Packages | Does |
|---|---|---|
| gateway | `modelcall`, `jsonio` | every model call, JSONL call cache, prompt loader, model pins; canonical JSON |
| engine | `evqa` | seed, paper writer (`external/paperorchestra`), QA pipeline, evaluation |
| api | `webapp` | FastAPI: read-only `/api/evqa/*` routes, serves `frontend/dist` |

Direction: api -> engine -> gateway. Enforced by `backend/tests/test_boundaries.py`.

## Data flow

```
data/seed/<domain>/ (blueprint, seed.ttl, briefs, gold)  -- truth; the pipeline never opens it
        |  evqa paper write
        v
data/dataset/<domain>/<paper>/paper.md  -- all the QA system may read
        |  evqa run --config configs/evqa/<x>.yaml   (spec -> find -> extract -> answer)
        v
runs/evqa/<run>/  --  evqa eval (scores against data/seed)  -->  Workbench
```

## Repo layout

| Path | What |
|---|---|
| `backend/` | Python packages (`evqa`, `modelcall`, `jsonio`, `webapp`, `repo_paths`) |
| `frontend/` | Vite/React Workbench; `dist/` committed so Slurm serves it without npm |
| `data/` | `seed/` (truth), `dataset/` (papers), `cache/` (downloads, not committed) |
| `configs/evqa/` | run configs |
| `external/paperorchestra/` | vendored paper writer (own uv env) |
| `ops/`, `scripts/` | cluster helpers, tunnels |
| `tests/`, `reports/` | recorded results of the earlier system; never edited |
| `llm-setup/` | submodule: vLLM + LiteLLM stack on Slurm |
