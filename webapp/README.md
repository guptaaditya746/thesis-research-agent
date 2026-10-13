# Web app backend

FastAPI over the run directories, concept sessions, gold files and reports
(docs/e2e-build-plan.md, "Backend API"). It serves the built frontend (`webapp/web/dist`) at `/`
when that directory exists, and everything else under `/api`.

## Run it

```sh
export CORPUS=/path/to/corpus          # frozen Markdown corpus with manifest.json
export RUNS=runs GOLD=gold-data CONCEPTS=concepts
export LITELLM_BASE_URL=http://127.0.0.1:4000/v1 LITELLM_MASTER_KEY=...   # the key is only read, never logged
uv run webapp serve                    # http://127.0.0.1:8080 (--host, --port, --reload)
```

All settings and their defaults are in `webapp/settings.py` (`CORPUS`, `RUNS`, `GOLD`, `CONCEPTS`,
`QUESTIONS`, `LITELLM_BASE_URL`, `ARGILLA_API_URL`, `AGENT_ROOT`, and `WEBAPP_DIST`,
`WEBAPP_PYTHON`, `WEBAPP_CHAT_MODEL`, `WEBAPP_LIVE_WINDOW_S`, `WEBAPP_POLL_S`).

### On the Slurm node, through a tunnel

The app has no authentication and binds to 127.0.0.1. Start it on the node that runs the LLM
stack (inside the job, or on the login node with the runs on Ceph), then from your laptop:

```sh
ssh -L 8080:127.0.0.1:8080 <user>@<slurm-node>     # add -J <login-node> if the node is behind one
```

and open http://127.0.0.1:8080. Do not pass `--host 0.0.0.0`.

## Endpoints

| Method, path | Returns |
|---|---|
| `GET /api/health`, `GET /api/config` | `Health`, `AppConfig` (whether the LLM key is set, never the key) |
| `GET /api/questions`, `GET /api/questions/{qid}` | `Question` (concept, gold and run status), `QuestionDetail` (+ briefs, pick) |
| `POST /api/questions/{qid}/concepts/propose` `{temperature, seed}` | `Job` running `agent concepts propose` |
| `POST /api/questions/{qid}/concepts/pick` `{choice, picked_by, reason}` | `QuestionDetail`; a pick can change until the gold build starts |
| `GET /api/runs?qid=&condition=&verify=` | `[RunSummary]` (`verify=true` runs `agent verify` on runs not checked yet) |
| `POST /api/runs` `{qid \| concept_path, condition, temperature, seed, steps, tokens, sandbox, attach}` | `Job`: `agent run`, attach (claim_off), verify, pairs, graph, export-prov, `score run` |
| `GET /api/runs/{id}` | `RunDetail` (summary, config, concept, answer, verify) |
| `GET /api/runs/{id}/steps`, `.../steps/{n}/output` | `[Step]`; the command's full output as text |
| `GET /api/runs/{id}/stream` | SSE: `record` per events.jsonl line (id = line number; resumes after `Last-Event-ID`), then `done` |
| `GET /api/runs/{id}/claims`, `.../graph`, `.../score` | `[Claim]`, graph.json, score.json (404 until scored) |
| `GET /api/runs/{id}/facts/{fact}/walk?judge=` | `FactWalk`: fact, claims, the step behind each, the highlighted passage, the judge's verdict |
| `GET /api/corpus/{paper}?start=&end=&context=1500` | `Passage`: the window around raw offsets, highlight relative to it |
| `GET /api/gold`, `GET /api/gold/{qid}/key`, `POST /api/gold/{qid}/build` | `[GoldEntry]`, the key (reviewed, else draft), a `Job` running `gold build` |
| `GET /api/results` | `$RUNS/report/report.json` (404 until there is one) |
| `POST /api/sparql` `{query, run_id?}` | `SparqlResult`; SELECT, ASK, CONSTRUCT, DESCRIBE only |
| `GET /api/queries/{1-5}?run_id=&edge=&fact=&claim=&step=&agent=` | the five provenance queries (agent/queries.py) |
| `GET /api/jobs`, `GET /api/jobs/{id}`, `GET /api/jobs/{id}/log`, `POST /api/jobs/{id}/cancel` | `Job`s; SSE of the log (`line` events, then `done`) |
| `POST /api/chat` | AI SDK v5 UI-message stream (pydantic-ai `VercelAIAdapter`); `run_id` in the query or body scopes it |

The schema is `webapp/web/openapi.json` (the frontend's types are generated from it); regenerate it
after changing a model or a route, a test checks that it is current:

```sh
uv run webapp openapi -o webapp/web/openapi.json
```

## How it behaves

- **Read-only on the data.** The server writes only job state and logs (`$RUNS/.jobs/`) and concept
  picks (`$CONCEPTS/<qid>/`, `$CONCEPTS/picks.json`). Ids in URLs must be plain names, and every
  path is checked to stay inside its root. SPARQL goes through `scoring/store.py`, which refuses
  updates; the server keeps its own in-memory store so it never locks `$RUNS/.oxigraph` away from
  `score store`.
- **Jobs** are CLI subprocesses (`python -m agent.cli ...`), one at a time per kind (concepts, run,
  gold), with their output in `$RUNS/.jobs/<id>.log`. Cancelling sends SIGTERM (a run stops
  cleanly). A job that was running when the server stopped is listed as failed after a restart.
- **Live runs.** A run is live while a job works on it, or while it has no answer.json (or its
  attach step has not finished) and events.jsonl changed in the last `WEBAPP_LIVE_WINDOW_S`
  seconds, which covers runs the batch runner starts on the cluster.
- **Gold, scores and the judge** come from other packages; until their files exist the endpoints
  answer 404 or status `none`, and the claim walk leaves the verdict out.
- **Chat** uses `sub-model-1` through LiteLLM with read-only tools: `list_runs`, `get_run`,
  `get_answer`, `get_claims`, `walk_fact`, `sparql`, `read_passage`, `get_results`.

## Tests

`uv run pytest webapp/tests` builds a small world with the agent's own code (the D1 corpus, a
claim_on and a claim_off run, a concept session, gold and score files) and needs no model, no
network and no cluster: the chat uses a scripted pydantic-ai `FunctionModel`, jobs a fake
interpreter.
