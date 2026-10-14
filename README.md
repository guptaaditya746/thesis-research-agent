# thesis-research-agent

A free LLM research agent over 337 computer-science papers (Markdown), which records every fact with an exact
quote while it researches, in a hash-chained log, and builds a knowledge graph with provenance from it.
Around it: the gold standard it is scored against, the scoring, and a web app to run and inspect it all.

**Start here: `docs/STATE.md`**: what is decided, the numbers the design must respect, and what is open.

## Packages

| Package | Command | What |
|---|---|---|
| `agent/` | `agent` | Research loop (mini-swe-agent, Landlock sandbox, broker, `claim`, `spawn`), concepts, attach step, batch runner, verify, pairs, graph, PROV-O, queries, re-execution and replay (milestones 1–2) |
| `gold/` | `gold` | Evidence document D per question, triage, review pool, draft key; Argilla review, answer key, agreement, the LLM judge (milestone 3; `gold/README.md`) |
| `scoring/` | `score` | Runs against the keys, the paired report with the pre-registered test, the SPARQL store (milestone 4; `scoring/README.md`) |
| `webapp/` | `webapp` | FastAPI backend and the React frontend in `webapp/web` (`webapp/README.md`, `webapp/web/README.md`) |
| `questions/` | — | The 12 evaluation questions |
| `evidence/` | `evidence` | Evidence-level system (supervisor's design, 14 Oct): hand-written protocol, extractor contract and library (regex, single-call LLM, agentic), engine with locate, cascade, hash-chained events, record cache, replay and re-execution, evidence graph, deterministic synthesis, PROV-O |
| `synth/` | `synth` | Synthetic benchmark: seeded ground truth, five difficulty levels, template and LLM renderers, fidelity checks, controlled variants (`synth/README.md`) |
| `evaluation/` | `evaluate` | Scoring of extraction (A), integration (B) and synthesis (C), locate recall, cascade contribution; the retrieve-then-answer and agent baselines |

The evidence-level system's files and formats: `docs/evidence-interfaces.md`; the extractor interface:
`docs/extractor-contract.md`. One synthetic corpus end to end, offline (regex extractors, no model):

```bash
uv run evidence run --protocol evidence/protocols/rag-factuality.yaml --corpus synth/examples/rag-demo-explicit \
    --out runs/evidence --extractors regex-only --run-id demo
uv run evidence replay runs/evidence/demo                  # rebuilds from the record cache; every output hash must match
uv run evaluate score --run runs/evidence/demo --corpus synth/examples/rag-demo-explicit --out runs/eval/demo
```

Everything runs through uv (Python 3.13 or later, dependencies pinned in `uv.lock`):

```bash
git submodule update --init --recursive
uv sync --locked --all-groups
uv run pytest -q                              # agent, gold, scoring and webapp tests; no cluster or model needed
uv run agent run --help                       # likewise gold, score, webapp
```

## The web app

```bash
export CORPUS=/path/to/corpus RUNS=runs/m4-72 GOLD=gold-data CONCEPTS=concepts   # RUNS: one batch root
uv run webapp serve                           # http://127.0.0.1:8080; on Slurm: ssh -L 8080:127.0.0.1:8080 <node>
```

`RUNS` is the batch root `scripts/e2e-batch.sh` prints (`RUNS_ROOT=...`), the same one `score batch`,
`score report` and `score store` take: two batches have runs of the same names (webapp/README.md).

The built frontend is committed (`webapp/web/dist`, made by `npm run build`), so the server needs no
Node. To work on the frontend: `cd webapp/web && uv run --group frontend npm ci`, then `npm run dev`
(against `webapp serve`) or `npm run dev:mock` (no backend). After a change to the API models:
`uv run webapp openapi -o webapp/web/openapi.json` and `npm run gen:api`.

## Documents

| Path | What |
|---|---|
| `docs/STATE.md` | The one page to plan from |
| `docs/e2e-build-plan.md` | The end-to-end build: decisions, file contracts between packages, the backend API |
| `docs/milestones-1-2.md` | Triaged build plan and progress for milestones 1 and 2 |
| `docs/milestones-3-4.md` | What was built for milestones 3 and 4, and what still needs the cluster or people |
| `docs/slurm-m1-runbook.md` | First real runs on Slurm, rows 1.1 and 1.13 (Codex ran it) |
| `docs/slurm-e2e-runbook.md` | The whole system on Slurm, end to end: concepts, gold trial, smoke batch, scoring, web app (Codex runs it) |
| `docs/slurm-final-runbook.md` | The final infrastructure session (done) |
| `docs/plan.md` | The design; to be revised from STATE.md |
| `docs/decisions-after-tests.md` | Why each decision was taken, test by test |
| `docs/provenance-model.md` | Log records and the PROV-O graph |
| `docs/context.md` | The original context note |
| `tests/RESULTS.md` | Every infrastructure test result; logs and scripts under `tests/<id>/` |
| `thesis_pipeline.html` | One-page diagram of the design (click any box for details) |
| `llm-setup/` | Submodule [`thesis-llm-setup`](https://github.com/guptaaditya746/thesis-llm-setup): vLLM + LiteLLM on Slurm |
| `scripts/` | `e2e-*.sh` and `e2e-measure.py` for the Slurm session, `omen-tunnels*` (Argilla, Langfuse), the agent root and corpus builds |

Framing discussion: https://claude.ai/code/artifact/c4258535-0673-4590-83f9-4377ee7057fa
