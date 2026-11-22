# Architecture

Evidence QA (`evqa`): a seed graph (the truth) -> papers written from it -> Spec / Find / Extract / Answer per question
-> layered evaluation against the seed. The Workbench (web UI) shows every step. Old step notes: `docs/archive/slice1.md`.

## Services (one process; modules, no HTTP between them)

| Service | Packages | Does |
|---|---|---|
| gateway | `modelcall`, `jsonio` | every model call, JSONL call cache, prompt loader, model pins; canonical JSON |
| engine | `evqa` | seed, questions and gold, QA pipeline, evaluation |
| api | `webapp` | FastAPI: read-only `/api/evqa/*` routes, serves `frontend/dist` |

Direction: api -> engine -> gateway. Enforced by `backend/tests/test_boundaries.py`.

## Data flow

```
services/paper-factory  (paperfactory run + export; ops/bench4.sh for the four domains)
        |  writes facts and papers into the data/ submodule
        v
data/seed/<domain>/ (seed, fact rows, gold; `evqa seed pfbench` makes questions + gold)  -- truth; the pipeline never opens it
        |
        v
data/dataset/<domain>/<paper>/paper.md  -- all the QA system may read
        |  evqa run --config configs/evqa/<x>.yaml   (spec -> find -> extract -> answer)
        v
runs/evqa/<run>/  --  evqa eval  -->  services/thesis-scorer (gold.json + answers.jsonl in, eval.json out)  -->  Workbench
```

## Baselines (compare with other answering systems)

```
configs/evqa/practice-pqa-rag.yaml (system: paperqa2-rag | paperqa2-agent | long-context)
        |  evqa run --config ... --text
        v
evqa/baselines  --subprocess-->  baselines/ (submodule thesis-baselines, own uv env: PaperQA2, long context)
        |  same questions (corpus.py), same papers, same Qwen gateway alias
        v
runs/evqa/<run>/<qid>/find.jsonl + answer_text.json  --  thesis-scorer: L0, L1 + L3-text (same rules for every system)
        |
        v
evqa compare evqa-run baseline-run   (l3_text is the score every system has)
```

L3-text grades the answer text of every run the same way (evqa answers are written out as text first): an LLM
lists the values the text states, code checks each against the text and against the gold rows. How the Workbench
shows baseline runs: `frontend/docs/baselines.md`.

## Repo layout

| Path | What |
|---|---|
| `backend/` | Python packages (`evqa`, `modelcall`, `jsonio`, `webapp`, `repo_paths`) |
| `frontend/` | submodule `thesis-workbench`: Vite/React Workbench; `dist/` is not committed, build it (`npm ci && npm run build`) before `webapp serve` |
| `data/` | submodule thesis-benchmark: `seed/` (truth), `dataset/` (papers); `cache/` is local only |
| `configs/evqa/` | run configs |
| `ops/`, `scripts/` | cluster helpers, tunnels |
| `thesis-writing/` | thesis chapter drafts and evidence audits |
| `docs/archive/` | old design notes, codex logs, and recorded results of the earlier system (`tests/`, `reports/`, `presentations/`); never edited |
| `llm-setup/` | submodule: vLLM + LiteLLM stack on Slurm |
| `baselines/` | submodule thesis-baselines: PaperQA2 and long-context baselines (own uv env) |
| `services/thesis-scorer/` | submodule thesis-scorer: scores any system's answers (gold file + answers JSONL in, report out); evqa uses it via `evqa/scoring.py` |
| `services/paper-factory/` | submodule Paper-factory: writes the synthetic papers and fact rows into `data/` |
| `services/model-queue/` | submodule model-queue: one queue in front of LiteLLM so the GPUs never overflow |
