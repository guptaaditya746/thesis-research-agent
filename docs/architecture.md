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

## Baselines (compare with other answering systems)

```
configs/evqa/practice-pqa-rag.yaml (system: paperqa2-rag | paperqa2-agent | long-context)
        |  evqa run --config ... --text
        v
evqa/baselines  --subprocess-->  baselines/ (submodule thesis-baselines, own uv env: PaperQA2, long context)
        |  same questions (corpus.py), same papers, same Qwen gateway alias
        v
runs/evqa/<run>/<qid>/find.jsonl + answer_text.json  --  prism (L0, L1)  +  eval/text_answer.py (L3-text)
        |
        v
evqa compare evqa-run baseline-run   (l3_text is the score every system has)
```

L3-text grades the answer text of every run the same way (evqa answers are written out as text first): an LLM
lists the values the text states, code checks each against the text and against the gold rows. Frontend plan:
`docs/design/frontend-baselines.md`.

## Repo layout

| Path | What |
|---|---|
| `backend/` | Python packages (`evqa`, `modelcall`, `jsonio`, `webapp`, `repo_paths`) |
| `frontend/` | submodule `thesis-workbench`: Vite/React Workbench; `dist/` is not committed, build it (`npm ci && npm run build`) before `webapp serve` |
| `data/` | `seed/` (truth), `dataset/` (papers), `cache/` (downloads, not committed) |
| `configs/evqa/` | run configs |
| `external/paperorchestra/` | vendored paper writer (own uv env) |
| `ops/`, `scripts/` | cluster helpers, tunnels |
| `tests/`, `reports/` | recorded results of the earlier system; never edited |
| `llm-setup/` | submodule: vLLM + LiteLLM stack on Slurm |
| `baselines/` | submodule thesis-baselines: PaperQA2 and long-context baselines (own uv env) |
