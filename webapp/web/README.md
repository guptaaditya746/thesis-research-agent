# Web app (frontend)

The browser side of the thesis agent's web app (docs/e2e-build-plan.md, "Frontend pages", WP F):
questions and concept briefs, runs live and finished, the answer with each fact's claim walk to the
highlighted quote, the knowledge graph, provenance queries, scores, the gold standard, the results
dashboard and a chat about runs. The backend (`webapp serve`, WP E) serves the built app at `/` and
the API at `/api`.

Stack: Vite 7, React 19, TypeScript (strict), Tailwind CSS 4, shadcn/ui (Radix), TanStack Query,
React Router 7, React Flow (`@xyflow/react`) with dagre, recharts through shadcn `chart`,
assistant-ui with the AI SDK v5 (`ai`), react-markdown with remark-gfm (the chat's replies; no raw
HTML), sonner, lucide-react, next-themes. Tests: Vitest, Testing
Library, MSW. Every dependency is pinned exactly (`.npmrc` has `save-exact=true`) and
`package-lock.json` is committed.

## Running npm

Node comes from the repo's `frontend` dependency group, so npm runs wherever uv does:

```sh
cd webapp/web
uv run --group frontend npm ci          # install exactly package-lock.json
```

Every command below is `uv run --group frontend npm run <script>` (or plain `npm run <script>` with
your own Node 22).

## Develop with mocks (no backend)

```sh
npm run dev:mock        # vite --mode mock: .env.mock sets VITE_MOCK=1
```

The MSW service worker (`public/mockServiceWorker.js`) answers `/api` from `src/mocks`, shaped like
the backend's responses: 12 questions, briefs and picks; a finished claim_on and claim_off run of
q01 from a batch (real quotes from the D1 papers, a sub-agent, the attach step, score.json with
per-fact verdicts and matches); a web-app run that is still going (its timeline streams, then it
finishes); runs that ended at the budget; gold state with a review report; a results report with
intervals and the primary test; jobs with steps and logs; and a chat that answers in the AI SDK UI
message stream. State is in memory: picks, new jobs and cancellations last until the page reloads.
The refusals are the backend's (409 for a pick the gold build depends on, a second proposal, a run
while a batch is live, and so on). A banner on every page says the data is mock data, and the
fixture paths are under `/mock/`, so no screenshot of the mock server passes for a result.

## Develop against the backend

```sh
webapp serve --host 127.0.0.1 --port 8080      # in another shell, from the repo root
npm run dev                                     # Vite proxies /api to 127.0.0.1:8080
WEBAPP_API=http://127.0.0.1:9000 npm run dev    # another backend address
```

The proxy passes the server-sent event streams (run timeline, job logs, chat) through unbuffered.
On the cluster, the backend binds to 127.0.0.1 and is reached through an SSH tunnel; there is no
authentication in the app.

## Build

```sh
npm run build          # tsc -b, then vite build -> dist/ (served by the backend at /)
npm run preview        # serve dist/ locally
```

`dist/` is committed (made by `npm run build`), so the backend on the Slurm node serves the app
without npm or network access; rebuild and commit it with every frontend change. Pages are lazy
chunks, so React Flow, recharts and the chat load only where they are used.

## Checks

```sh
npm run typecheck      # tsc -b (strict)
npm run lint           # ESLint flat config: typescript-eslint, react-hooks, react-refresh
npm test               # Vitest + Testing Library + MSW (jsdom)
```

The tests cover the API client (URLs, errors, 404 as absence, the judge flag, jobs), the run stream
and job log hooks, the timeline reducer (idempotent merging, phases, budget notices), the graph
mapping and layout, the results report mapping (intervals, paired differences, sensitivity), the
passage highlight (UTF-16 spans), the claim walk (from a badge, a graph edge or a claim; asking the
judge), the chat (the request carries the run id of the page; streamed reply and tool call) and
every page's data, empty and error states, including the live timeline over a real EventSource
(the `eventsource` package, which jsdom lacks) against the MSW stream. They run against the same
MSW handlers as `dev:mock`.

Tests on the `/mnt/c` checkout under WSL are slow (importing jsdom alone reads ~850 files over
the Windows file share): the suite takes a few minutes. That is why `vite.config.ts` runs one
reused worker and `src/test/environment.ts` installs jsdom from the setup file instead of at
worker start (vitest gives a worker 60 s to start).

## API types

The API types are generated from the backend's OpenAPI schema (`webapp openapi`, webapp/models.py)
with openapi-typescript (a pinned devDependency) into `src/api/schema.d.ts`, and the first half of
`src/api/types.ts` aliases them (`export type RunSummary = components["schemas"]["RunSummary"]`),
so the type checker holds the pages, the client and the MSW fixtures to what the backend serves.
After a change to the backend's models:

```sh
uv run webapp openapi -o webapp/web/openapi.json     # from the repo root
npm run gen:api        # openapi-typescript -> src/api/schema.d.ts (--default-non-nullable false keeps
                       # fields the backend defaults optional in request bodies)
npm run typecheck      # then fix what it shows
```

The second half of `types.ts` types the files the backend passes through as open objects (score.json, report.json, the
gold report and counts, config.json): those stay hand-written, and `src/lib` reads them
defensively (`lib/results.ts` is the only reader of report.json, `lib/gold.ts` of the gold files,
`lib/run.ts` of config.json). All HTTP access is in `src/api/` (`client.ts`: one typed client and
the stream URLs; `hooks.ts`: TanStack Query hooks; `stream.ts`: the SSE hooks).

## What the pages show

| Page | Route | Notes |
|---|---|---|
| Overview | `/` | pipeline tiles (picks, reviewed keys, scored runs, report); one row per question |
| Question | `/questions/:qid` | briefs side by side with the answer shape; pick (recorded as `picked_by: user`: `claude` and `provisional-first` are the CLI's; with `force` when runs depend on it; locked once gold is built); propose; gold build, and again when it stopped |
| Runs | `/runs?qid=&condition=&stale=1` | filterable table (unsandboxed runs marked); New run (one condition or both with one seed; unsandboxed only after an explicit yes; "start anyway" when a batch is live) |
| Run | `/runs/:runId?tab=` | stats header (the main agent's research steps and tokens against the budget); Answer (fact badges from score.json), Graph, Timeline (live; budget notices at the thresholds config.json records, none for prompt v1), Claims, Provenance, Score; the claim walk sheet (each claim's recorded quote beside today's passage) |
| Compare | `/compare/:qid?on=&off=` | a claim_on and a claim_off run side by side, with their differences |
| Results | `/results` | warnings, primary test with sensitivity analyses, charts with BCa intervals (questions and runs in the tooltips), per-question differences, secondary outcomes (with paired questions and runs), per-question table |
| Gold | `/gold` | coverage, candidates, key, review progress, κ with its interval (and the warning when the overlap was not independent), triage miss, screening false negatives, key sheet; run a stopped build again |
| Jobs | `/jobs/:jobId?` | jobs with their steps, live log (resumes after a dropped connection), cancel |
| Chat | everywhere (Ctrl+J) | assistant-ui thread in a sheet, replies as Markdown; on a run page it sends the run id, and another run starts a new thread |

Ctrl+K opens the command menu (pages, questions, runs, theme). Colours of the two conditions are
series 1 and 2 of the validated chart palette (light and dark); status colours always come with an
icon and a label.

## Layout

```
src/api/         client, hooks, streams, types
src/app/         providers, routes (lazy pages), route error
src/components/  layout (sidebar, header, command menu, theme, job watcher), run/ (tabs, claim
                 walk), new-run/, question/, results/, chat/, ui/ (shadcn, by the CLI)
src/lib/         pure logic: timeline reducer, graph mapping, results mapping, facts, gold, run
                 config, passage, formats
src/mocks/       MSW handlers and fixtures
src/pages/       one file per route
src/test/        test environment and setup
```

Add shadcn components with `npx shadcn@4.21.4 add <name>` (components.json is committed).
