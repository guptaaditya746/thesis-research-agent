# Architecture

Research question about a paper corpus -> plan (protocol) -> run -> answer from extracted evidence, not from authors' conclusions. Evaluated on synthetic corpora with known truth (A extraction, B integration, C synthesis) and real sets, against a retrieve-then-answer (RAG) baseline.

## Design origin

- Tim (14 Oct): evidence-level not answer-level; executable protocol; extractor library; synthetic corpus from ground truth; levels + variants; RAG baseline. Verbatim notes: `.claude/skills/tim/`.
- Ours: agentic extractor, agent baseline, funnel engine, provenance + replay lane, PROV-O, proposal/plan flow, domain packs, LLM word list, ontology reasoning, DSPy tuning.

## Services (one process; modules, no HTTP between them)

| Service | Packages | Does |
|---|---|---|
| gateway | `modelcall` | every model call (`modelcall.ask`), JSONL call cache, recorder, prompt loader, model pins |
| engine | `evidence`, `agent`, `gold`, `jsonio` | papers, screen, extractors, graph, plans, synthesis, answers, seal/replay |
| evaluation | `evaluation`, `scoring`, `synth`, `packbuilder` | scores A/B/C, baselines, real sets, synthetic corpora, pack builder |
| api | `webapp` | FastAPI front door, job runner, serves `frontend/dist` |

Direction: api -> evaluation -> engine -> gateway (api -> engine too). Enforced by `backend/tests/test_boundaries.py`; exceptions in `backend/README.md`.

## Data flow

```
data/domains/<pack>/  (words, types, protocols, questions)
        |                      question --> planner (plan.json) --> confirm (auto | hand)
        v                                           |
corpus/ manifest.json + papers/  ------------------> evidence run
                                                    |  screen -> regex -> GLiNER -> LLM (funnel, gaps only)
                                                    |  every call: modelcall (cache, recorder)
                                                    v
                         run dir: run.json, events.jsonl (hash chain), evidence.jsonl, graph.json, answer.json, manifest.json
                                                    |
                    evaluate score / wholerun / leak / offtemplate  <-- ground_truth.json (synthetic) or gold (real)
                                                    v
                                       report.json, report.md --> webapp pages
```

- Engine and baselines read only `manifest.json` + `papers/`, never `ground_truth.json` (test-enforced).
- Replay: `evidence replay <run>` rebuilds from the record cache; every output hash must match. A miss is an error.
- Extractor id = hash of its source files (paths relative to `backend/`) + config. Moving a hashed file changes ids.

## Files between services

| File | Writer | Reader |
|---|---|---|
| corpus dir: `manifest.json`, `papers/`, `ground_truth.json`, `corpus.json` | `synth`, `evidence fetch`, real-set prep | engine (manifest + papers), evaluation (truth) |
| protocol / `plan.json` | pack, planner, `evidence propose` | engine |
| run dir | `evidence run` | `evaluate`, `webapp`, `evidence replay/verify` |
| `answer.json` (baselines) | `evaluate rag-baseline`, `agent-baseline` | `evaluate score` |
| `report.json`, `wholerun.json` | `evaluate` | `webapp`, reports/ |

## Repo layout

| Path | What |
|---|---|
| `backend/` | all Python packages + `repo_paths.py` (folder locations) |
| `frontend/` | Vite/React UI; `dist/` committed so Slurm serves it without npm |
| `data/` | packs (`domains/`), earlier-work inputs (`questions/`, `concepts/`, `corpus/`) |
| `tests/` | test results and EV corpora (`tests/EV*`); left at root, see `data/README.md` |
| `reports/` | recorded results; never edited |
| `scripts/` | plan runs, real-set prep, tunnels, e2e |
| `llm-setup/` | submodule: vLLM + LiteLLM stack on Slurm |

## Glossary

| Term | Meaning | Avoid |
|---|---|---|
| Research question | question a user asks of a corpus, from the list or typed | query, prompt |
| Question list | fixed ready-made questions, all answerable from one synthetic corpus | question bank, presets |
| Question kind | shape deciding needed evidence: effect, inventory, consistency, best | question type, template |
| Protocol | explicit frozen plan: what evidence, how to extract, connect, synthesize | plan, config, YAML |
| Proposal | step building a protocol for a question before freeze | protocol generation, draft |
| Card | one method decision in a proposal, drafted choice + reason; set per kind | setting, field, option |
| Run trace | step-by-step record of a run: every step and call, inputs, outputs, timing, errors | log, timeline |
| Checker | reviews a proposal during edits; problems serious or advisory | critic, validator, linter |
| Waiver | user's written reason to freeze despite a serious problem | override, skip |
| Consistency check | claim vs numbers: by direction (default) or by size within a margin | claim check |
| Extractor | reusable component finding one evidence kind by one method (patterns, tagger, LLM) | parser, scraper |
| Funnel | extractor order per paper, cheapest first, only missing evidence passed on | cascade, pipeline |
| Domain pack | folder with everything topic-specific (types, words, units, protocols, questions); "topic" in UI; code names no topic | vocabulary file |
| Study | one paper; may hold many comparisons | experiment (whole paper) |
| Comparison | one treatment-vs-control result, one metric, one dataset | pair |
| Treatment / control | the two sides in code; users see domain names (e.g. "RAG system / closed-book model") | rag / baseline |
| Chaining | A vs C from study 1 (A vs B) + study 2 (B vs C), no direct paper | transitivity |
