# backend/

Every Python package; `pyproject.toml` sets `module-root = "backend"`. Services = groups of packages in one
process; no HTTP between them.

## Service map

| Service | Packages | Command | Does |
|---|---|---|---|
| gateway | `modelcall`, `jsonio` | (library) | every model call, JSONL call cache, prompt loader, model pins; canonical JSON, atomic writes |
| engine | `evqa` | `evqa` | seed, paper writer, Spec/Find/Extract/Answer, evaluation |
| api | `webapp` | `webapp` | FastAPI: `/api/health`, read-only `/api/evqa/*` (the Workbench), serves `frontend/dist` |
| (shared) | `repo_paths` | - | repo folder locations |

Direction: api -> engine -> gateway. Lower never imports higher. `tests/test_boundaries.py` parses every import
outside `*/tests/` and fails on a wrong-way one.

The old system (`evidence`, `agent`, `gold`, `evaluation`, `scoring`, `synth`, `packbuilder`, the `/api/ev` app)
was removed on 21 Nov 2026; backup in `runs/backup/old-code-2026-11-21.tar.gz`, history in git.

## Run

```bash
uv sync --locked                     # from repo root; --all-groups for Node
uv run evqa --help
uv run webapp serve --port 8080      # Workbench at http://127.0.0.1:8080 (serves frontend/dist)
```

## Replay a run offline

Proves a run can be rebuilt exactly from the model-call cache (`runs/evqa/llm-cache.jsonl`, or `EVQA_LM_CACHE`).
With `EVQA_OFFLINE=1` a cache miss calls no model: it raises `OfflineCacheMiss: <qid/step> key <first 12 hex>`,
which stops that question's step (logged as a `problem` in events.jsonl, never skipped as a bad reply).

```bash
sed 's/^name: practice-qwen$/name: replay-practice-qwen/' configs/evqa/practice-qwen.yaml > /tmp/replay.yaml
EVQA_OFFLINE=1 uv run evqa run --config /tmp/replay.yaml   # new name = new run folder, every step runs again
diff -r -x events.jsonl -x config.yaml -x manifest.json runs/evqa/practice-qwen-<hash> runs/evqa/replay-practice-qwen-<hash>
```

Exit code 0 and no difference = rebuilt from the cache. Set `EVQA_MODEL_REVISION` as in the original run (it is
part of the cache key). Covers the DSPy steps (`evqa/lm.py`); the seed tools' `evqa/llm.py` cache
(`seed names`, bench rewording) and the paper writer are not covered.

## Test

```bash
uv run pytest -q                     # testpaths = backend; xdist + 600 s timeout by default
```
