# backend/

Every Python package. Import names unchanged (`import evidence`); `pyproject.toml` sets `module-root = "backend"`.
Services = groups of packages in one process; no HTTP between them yet.

## Service map

| Service | Packages | Command | Does |
|---|---|---|---|
| gateway | `modelcall` | (library) | every model call (`modelcall.ask`), JSONL call cache, recorder, prompt loader, model pins |
| engine | `evidence`, `agent`, `gold`, `jsonio` | `evidence`, `agent`, `gold` | papers, screen, extractors, graph, plans, synthesis, answers, seal, replay; agent = agentic extractor + agent baseline; `jsonio` = canonical JSON, atomic writes |
| evaluation | `evaluation`, `scoring`, `synth`, `synth2`, `synth3`, `packbuilder` | `evaluate`, `score`, `synth`, `synth2`, `packbuilder` | scores A/B/C, RAG + agent + PaperQA2 baselines, real sets, whole-run, leak, off-template; synthetic corpora; pack builder; synth2 = hidden-law corpora and their scores |
| api | `webapp` | `webapp` | FastAPI front door, job runner (argv templates), serves `frontend/dist` |
| (shared) | `repo_paths` | - | repo folder locations (`data/`, `tests/`, `frontend/`, ...) |

Direction: api -> evaluation -> engine -> gateway; api -> engine allowed. Lower never imports higher.
`tests/test_boundaries.py` parses every import outside `*/tests/` and fails on a new wrong-way one.

Imports today (non-test): engine -> gateway (evidence, agent, gold -> modelcall); evaluation -> engine, gateway;
api -> engine, evaluation (`synth`), gateway. Tests reach across (e.g. evidence tests use evaluation fakes): not checked.

Known exceptions (wrong way, kept):

| Import | Why kept |
|---|---|
| `modelcall` -> `jsonio` | gateway uses canonical JSON + atomic writes; `jsonio/__init__.py` is hashed into extractor ids, so it cannot move to gateway |

## Hashed files: never edit

Extractor ids = sha256 over source paths relative to `backend/` + bytes (`evidence/extractors/base.py`). Editing or moving these changes ids and breaks replay of recorded runs:

- `evidence/extractors/*.py`, `evidence/extractors/prompts/*`, `evidence/prompts/*`
- `evidence/{contract,evidence_types,recording,names}.py`, `agent/anchor.py`, `jsonio/__init__.py`, `gold/chunks.py`
- `modelcall/{gateway,pins,call,prompt}.py`
- agentic extractor: `evidence/agentic/*.py` + `agent/{loop,answer,broker,anchor,parse,sandbox,claim_client,rundir,concept,stopping,prompts,spawn}.py`
- synthetic generator: `synth/*.py`, `synth/prompts/*` (hashed into `corpus.json`)
- prompt files of `gold/`, `evidence/propose/`, `evaluation/baselines/` (hashed into cache keys)

Proof: `evidence/tests/test_plan.py::test_old_protocol_lock_unchanged` (v2 lock fixture).

## Run

```bash
uv sync --locked                     # from repo root; --all-groups for Docling + Node
uv run evidence --help               # also: evaluate, synth, webapp, agent, gold, score, packbuilder
uv run webapp serve --port 8080      # UI at http://127.0.0.1:8080 (serves frontend/dist)
uv run synth2 build --out DIR --seeds 10                          # hidden-law corpus families: law kind x text level x seed
uv run synth2 reference --root DIR --rule pooled --out FILE       # answers of a reference rule: pooled (the key) | vote | lumped | trusts_claims
uv run synth2 score --root DIR --answers FILE --out FILE          # score an answers file {corpus id: answer} by code
uv run synth2 export-scir --root DIR --out FILE                   # the same corpora as one SciR-shaped task file
uv run synth2 written-corpus --template DIR --papers DIR --out DIR   # a corpus from model-written rewrites of a template's papers
uv run synth2 engine-answers --runs DIR --out FILE                # engine run folders (run.json + answer.json) as an answers file
uv run synth3 pool-fetch --domain D                                # real papers from PubMed Central into data/synth3/pools/D (git-ignored)
uv run synth3 pool-import --domain D --from DIR                   # or add .md, .xml, .pdf files you hold
uv run synth3 pool-split --domain D                               # once: test papers vs source papers
uv run synth3 build-real --domain D --seeds 1,2 --out DIR         # folders from approved worlds and renamed real papers
uv run synth3 realism --domain D --folder DIR/s1 --out FILE       # real-vs-synthetic classifier, raw and masked (no pass mark)
uv run synth3 reader --domain D --folder DIR/s1                   # blind reader (sub-model-1, cluster): notes vs truth in DIR/s1/real/reader-check.json
# subsets: run and score a synth2 corpus with data/domains/rag/protocols/rag-factuality-subsets.yaml (question id
# rag-factuality-subsets, also for the baselines' --question-id); its answer.json `conclusion` can say "depends"
```

## Test

```bash
uv run pytest -q                     # testpaths = backend; xdist + 600 s timeout by default
# Windows: POSIX-only files
uv run pytest -q --ignore backend/evaluation/tests/test_agentic_agent.py --ignore backend/evaluation/tests/test_runner.py
```

Windows: 10 `agent/tests` files error at import (`signal.SIGKILL`); they run on Linux.
