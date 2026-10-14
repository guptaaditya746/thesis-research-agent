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

`RUNS` is one batch root: the `RUNS_ROOT` `scripts/e2e-batch.sh` prints for a manifest
(`RUNS=$RUNS/m4-72` for the experiment, `$RUNS/e2e-smoke` for the smoke batch; docs/e2e-build-plan.md,
Environment), the same root `score batch`, `score report` and `score store` take, so the Results page
shows that batch's report/. The app lists the runs directly in it and one level down: in
`$RUNS/web/`, where the runs it starts go (id `web~<name>`), and in any batch root below it (id
`<batch>~<name>`). Do not point it at the directory above several batches: run ids are directory
names and graph.ttl's IRIs are scoped by them, so the smoke batch's `q01-claim_on-r1-a1` would stand
in for the experiment's in SPARQL (the provenance store loads the first run of a name and refuses a
query scoped to the second) and the Overview's run counts would add both batches together.

### On the Slurm node, through a tunnel

The app has no authentication and binds to 127.0.0.1; it answers only loopback Host names and
takes a write only as a same-origin JSON request (webapp/guard.py), so another web page open in the
browser can neither start jobs nor read the API through DNS rebinding (`WEBAPP_ALLOWED_HOSTS` adds
names). Start it on the node that runs the LLM stack (inside the job, or on the login node with the
runs on Ceph), with the `CONCEPTS`, `GOLD` and `CORPUS` that `scripts/e2e-env.sh` exports and `RUNS`
set to the batch root (`RUNS=$RUNS/m4-72`), then from your laptop:

```sh
ssh -L 8080:127.0.0.1:8080 <user>@<slurm-node>     # add -J <login-node> if the node is behind one
```

and open http://127.0.0.1:8080. Do not pass `--host 0.0.0.0`.

While a batch is running, `POST /api/runs` answers 409: a web run would share the orchestrator
with the batch (its KV cache holds about one long request), slowing the batch runs and inflating
their recorded time, a secondary outcome. Send `force: true` only when that does not matter.

## Endpoints

| Method, path | Returns |
|---|---|
| `GET /api/health`, `GET /api/config` | `Health`, `AppConfig` (whether the LLM key is set, never the key) |
| `GET /api/questions`, `GET /api/questions/{qid}` | `Question` (concept, gold and run status), `QuestionDetail` (+ briefs, pick) |
| `POST /api/questions/{qid}/concepts/propose` `{temperature, seed}` | `Job` running `agent concepts propose` |
| `POST /api/questions/{qid}/concepts/pick` `{choice, picked_by, reason, force}` | `QuestionDetail`; `picked_by` is `user`, `claude` or `provisional-first` |
| `GET /api/runs?qid=&condition=&verify=&include_stale=` | `[RunSummary]` (`qid`: the question's runs on its current concept; `verify=true` runs `agent verify` on runs not checked yet; without it, a run the app has not verified shows score.json's `verify_ok` when the scorer checked it after its last record, `verify_from: score`) |
| `POST /api/runs` `{qid \| concept_path, condition, temperature, seed, steps, tokens, sandbox, attach, force}` | `Job`: `agent run` into `$RUNS/web/`, attach (claim_off), verify, pairs, graph, export-prov, `score run --key` |
| `GET /api/runs/{id}` | `RunDetail` (summary, config, concept, answer, verify) |
| `GET /api/runs/{id}/steps`, `.../steps/{n}/output` | `[Step]`; the command's full output as text |
| `GET /api/runs/{id}/stream` | SSE: `record` per events.jsonl line (id = line number; resumes after `Last-Event-ID`), then `done` once the agent stops writing the run |
| `GET /api/runs/{id}/claims`, `.../graph`, `.../score` | `[Claim]`, graph.json, score.json (404 until scored) |
| `GET /api/runs/{id}/facts/{fact}/walk?judge=` | `FactWalk`: fact, claims, the step behind each, the highlighted passage, the scored verdicts |
| `GET /api/corpus/{paper}?start=&end=&context=1500` | `Passage`: the window around raw offsets, highlight relative to it (code points, and `highlight_utf16` for JavaScript) |
| `GET /api/gold`, `GET /api/gold/{qid}/key`, `POST /api/gold/{qid}/build` | `[GoldEntry]`, the key (reviewed, else draft), a `Job` running `gold build`, `triage`, `pool`, `draft` |
| `GET /api/results?batch=` | a batch root's `report/report.json` (`$RUNS/report/`, else the newest batch's; 404 until there is one) |
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

- **Writes.** The server writes job state and logs (`$RUNS/.jobs/`) and, through
  `agent/concept_step.py`, concept picks (`$CONCEPTS/<qid>/`, and `$CONCEPTS/picks.json`, which that
  module rebuilds from the chains). Everything else is written by the jobs it starts, except one
  thing: a claim walk with `?judge=true` asks the judge, which appends to `$GOLD/judge-cache.jsonl`.
  Ids in URLs must be plain names (`batch~name` for runs one level down), and every path is
  checked to stay inside its root. SPARQL goes through `scoring/store.py`, which refuses updates and SERVICE (no request leaves the server);
  the server keeps its own in-memory store so it never locks `$RUNS/.oxigraph` away from
  `score store`.
- **Picks** are `concept_pick` records in the session's hash chain, so `agent concepts check`
  passes after each. A pick can change until the gold build starts (needs WP B's
  `concept_step.pick(replace=True)`; without it the first pick is final), and once runs used the
  current concept only with `force`: those runs then show `concept_current: false` and leave the
  question's counts, `?qid=` and so the Compare page.
- **Jobs** are CLI subprocesses (`python -m agent.cli ...`), one at a time per kind (concepts, run,
  gold), with their output in `$RUNS/.jobs/<id>.log`. A step whose input is missing is skipped
  (no score without an answer key, or for claim_off before the attach step finished); a failed
  optional step is a warning on the job. Cancelling sends SIGTERM (a run stops cleanly). A job that
  was running when the server stopped is listed as failed after a restart.
- **Live runs.** A run is `live` while the agent writes it: for a web run, while its job's `run` or
  `attach` step runs (`post_processing` covers the later steps); for any other run, while it has no
  answer.json (or its attach step has not finished), is not cut, and events.jsonl changed in the
  last `WEBAPP_LIVE_WINDOW_S` seconds (900: longer than a model call's timeout after a command),
  which covers runs the batch runner starts on the cluster.
- **Exit status** follows scoring's rules (cut, error, the loop's own status, submitted), so it
  agrees with score.json; `answer_from` says whether answer.json is the model's final answer, the
  agent's draft taken by the harness, or an empty answer.
- **Gold, scores and the judge** come from other packages; until their files exist the endpoints
  answer 404 or status `none`. A fact's support badge is the verdict score.json counted; before a
  run is scored the walk has none, unless `?judge=true` asks the judge (with scoring's inputs,
  `source: judge`). A score against the draft key is `provisional`.
- **Chat** uses `sub-model-1` through LiteLLM with read-only tools: `list_runs`, `get_run`,
  `get_answer`, `get_claims`, `walk_fact` (scored verdicts only), `sparql`, `read_passage`,
  `get_results`. A list a tool returns is cut to about 16,000 characters of JSON with a last item
  saying how many were left out, so a long run's claims do not overflow the model's 32k context.
- **Gold status** is `reviewing` while key.json comes from an export half way through the review
  (`review.complete` false); scores against it are provisional, as against the draft key.

## Tests

`uv run pytest webapp/tests` builds a small world with the agent's own code (the D1 corpus, a
claim_on and a claim_off run, a concept session, gold and score files) and needs no model, no
network and no cluster: the chat uses a scripted pydantic-ai `FunctionModel`, the judge a fake
callable, jobs a fake interpreter.
