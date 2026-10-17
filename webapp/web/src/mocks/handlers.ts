/**
 * MSW handlers: the backend API (webapp/app.py) over the fixtures, for `npm run dev:mock` (service
 * worker) and the tests (Node). State lives in one in-memory `db` so that picks, new jobs and the
 * live run's end show up on the next request; `resetDb()` restores it. The refusals follow the
 * backend's: 404 for unknown ids, 400 for a bad choice or query, 409 for a state that forbids the
 * action (briefs already proposed, a pick runs depend on without `force`, a gold build started).
 *
 * The streams behave like the backend's: the live run plays its remaining events.jsonl records as
 * `event: record` and then `event: done`, and is marked finished; job logs send `event: line` per
 * line and `event: done` with the job; POST /api/chat answers in the AI SDK v5 UI message stream
 * protocol (what pydantic-ai's VercelAIAdapter sends), with one tool call and a short text.
 */
import { delay, http, HttpResponse } from "msw"

import type {
  Claim,
  ConceptBrief,
  Job,
  JobStep,
  Pick as ConceptPick,
  PickRequest,
  ProposeRequest,
  Question,
  QuestionDetail,
  RunDetail,
  RunRequest,
  RunSummary,
  SparqlRequest,
} from "@/api/types"

import { evHandlers } from "./ev"
import {
  BRIEFS,
  CLAIMS,
  config,
  GOLD,
  GOLD_KEYS,
  GRAPHS,
  initialRunDetails,
  JOB_LOGS,
  JOBS,
  LIVE_ANSWER,
  LIVE_RECORDS,
  PASSAGES,
  passageOf,
  PICKS,
  QUESTIONS,
  RESULTS,
  RUNS,
  SCORES,
  STEPS,
  walkFor,
} from "./fixtures"

interface Db {
  runs: RunSummary[]
  details: Record<string, RunDetail>
  briefs: Record<string, ConceptBrief[]>
  picks: Record<string, ConceptPick>
  jobs: Job[]
  nextJob: number
}

function freshDb(): Db {
  return {
    runs: structuredClone(RUNS),
    details: initialRunDetails(),
    briefs: structuredClone(BRIEFS),
    picks: structuredClone(PICKS),
    jobs: structuredClone(JOBS),
    nextJob: 8,
  }
}

export const db: Db = freshDb()

export function resetDb() {
  Object.assign(db, freshDb())
}

/** How long the mock streams wait between events (0 in tests). */
export const timing = { streamMs: 900 }

/**
 * A text/event-stream response from an async generator of events. A plain streamed response
 * rather than msw's `sse()`, which needs EventSource where the handler is built (jsdom has none);
 * the browser's EventSource reads it through the service worker all the same.
 */
function eventStream(events: () => AsyncGenerator<{ event?: string; data: string; id?: number }>) {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      for await (const { event, data, id } of events()) {
        const lines = data.split("\n").map((line) => `data: ${line}`).join("\n")
        controller.enqueue(encoder.encode(`${event ? `event: ${event}\n` : ""}${id !== undefined ? `id: ${id}\n` : ""}${lines}\n\n`))
      }
      controller.close()
    },
  })
  return new HttpResponse(body, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" } })
}

const detail = (status: number, text: string) => HttpResponse.json({ detail: text }, { status })
const notFound = (what: string) => detail(404, `no such ${what}`)

const activeJob = (kind: string, qid: string) => db.jobs.find((j) => j.kind === kind && j.qid === qid && (j.state === "queued" || j.state === "running"))
const runsOf = (qid: string) => db.runs.filter((r) => r.qid === qid && r.concept_current !== false)

function questionSummary(q: Question): Question {
  const pick = db.picks[q.id]
  const briefs = db.briefs[q.id] ?? []
  const gold = GOLD.find((g) => g.qid === q.id)
  return {
    ...q,
    concept: pick
      ? { status: "picked", title: pick.title ?? briefs[pick.choice - 1]?.title ?? null, picked_by: pick.picked_by }
      : briefs.length
        ? { status: "proposed", title: null, picked_by: null }
        : { status: "none", title: null, picked_by: null },
    gold: gold ? { status: gold.status, rows: gold.rows ?? null, facts: gold.facts ?? null, stage: gold.stage ?? null } : q.gold,
    runs: {
      claim_on: runsOf(q.id).filter((r) => r.condition === "claim_on").length,
      claim_off: runsOf(q.id).filter((r) => r.condition === "claim_off").length,
    },
  }
}

function questionDetail(qid: string): QuestionDetail | null {
  const q = QUESTIONS.find((x) => x.id === qid)
  if (!q) return null
  const pick = db.picks[qid] ?? null
  const briefs = db.briefs[qid] ?? []
  return { ...questionSummary(q), briefs, picked: pick, concept_brief: pick ? (briefs[pick.choice - 1] ?? null) : null }
}

function newJob(kind: string, args: Job["args"], steps: JobStep[], extra: Partial<Job> = {}): Job {
  const now = new Date().toISOString()
  const job: Job = {
    id: `job-${String(db.nextJob++).padStart(4, "0")}`, kind, args, state: "queued", created_at: now,
    started_at: null, ended_at: null, run_id: null, qid: null, exit_code: null, error: null, warnings: [], steps, ...extra,
  }
  db.jobs.unshift(job)
  return job
}

const pending = (name: string, command: string): JobStep => ({ name, argv: command.split(" "), command, required: true, needs: [], state: "pending", exit_code: null, started_at: null, ended_at: null })

function finishJob(id: string, exit = 0) {
  const job = db.jobs.find((j) => j.id === id)
  if (!job) return
  Object.assign(job, { state: exit === 0 ? "done" : "failed", ended_at: new Date().toISOString(), exit_code: exit })
  for (const s of job.steps ?? []) if (s.state === "pending" || s.state === "running") Object.assign(s, { state: exit === 0 ? "done" : "skipped", exit_code: exit === 0 ? 0 : null })
}

/**
 * The live run's end: what the backend reports once the agent stops writing it. `run` is the
 * record the stream started on; after a `resetDb()` (a test ended mid-stream) it is not in `db`
 * any more and nothing changes.
 */
function finishLiveRun(run: RunSummary) {
  const runDetail = db.details[run.run_id]
  if (!db.runs.includes(run) || !runDetail || !run.live) return
  Object.assign(run, {
    live: false, exit_status: "submitted", answer_from: "final", steps: 6, model_calls: 6, tokens: 42_314, seconds: 52.6, rows: 1, facts: 1,
    claims_accepted: 1, claims_rejected: 1, verify: "ok",
  })
  runDetail.summary = run
  runDetail.answer = LIVE_ANSWER
  runDetail.verify = { ok: true, errors: [], stats: { steps: 6, model_calls: 6, claims_accepted: 1, claims_rejected: 1, tokens: 42_314 } }
  const job = db.jobs.find((j) => j.run_id === run.run_id && j.state === "running")
  if (job) finishJob(job.id)
}

const claimsOf = (runId: string): Claim[] => CLAIMS[runId] ?? []
const stepOf = (runId: string, c: Claim) => (STEPS[runId] ?? []).find((s) => s.step === c.step && s.agent_id === c.agent_id)

/** The five provenance queries (agent/queries.py) over the fixtures; a string is a 400. */
function provQuery(n: number, runId: string, url: URL): Record<string, unknown>[] | string {
  const runDetail = db.details[runId]
  const accepted = claimsOf(runId).filter((c) => c.status === "accepted")
  const facts = (runDetail?.answer?.rows ?? []).flatMap((r) => r.facts.map((f) => ({ ...f, row_id: r.id })))
  switch (n) {
    case 1: {
      const edge = url.searchParams.get("edge")
      return accepted
        .map((c) => ({
          edge_id: `edge-${c.claim_id!.slice(6)}`, claim_id: c.claim_id, origin: c.origin, s: c.s, p: c.p, o: c.o,
          step_id: c.step, agent_id: c.agent_id, phase: stepOf(runId, c)?.phase ?? null, command: stepOf(runId, c)?.command ?? null,
          file: c.file, start: c.anchor?.start, end: c.anchor?.end, exact: c.quote,
        }))
        .filter((row) => !edge || row.edge_id === edge)
    }
    case 2: {
      const fact = url.searchParams.get("fact")
      const claim = url.searchParams.get("claim")
      return facts
        .filter((f) => !fact || f.id === fact)
        .flatMap((f) => f.claims.filter((id) => !claim || id === claim).map((id) => {
          const c = accepted.find((x) => x.claim_id === id)
          const s = c && stepOf(runId, c)
          return {
            fact_id: f.id, claim_id: id, origin: f.origin, step_id: c?.step ?? null, agent_id: c?.agent_id ?? null,
            phase: s?.phase ?? null, command: s?.command ?? null, model_call: s?.model_call?.task_id ?? null,
            model: c?.agent_id === "main" ? "orch-model" : "sub-model-1",
          }
        }))
    }
    case 3: {
      const step = url.searchParams.get("step")
      const agent = url.searchParams.get("agent")
      if (!step && !agent) return "query 3 needs a step, an agent, or both"
      return claimsOf(runId)
        .filter((c) => c.claim_id && (!step || c.step === Number(step)) && (!agent || c.agent_id === agent))
        .map((c) => ({ claim_id: c.claim_id, origin: c.origin, s: c.s, p: c.p, o: c.o, step_id: c.step, agent_id: c.agent_id, file: c.file, exact: c.quote }))
    }
    case 4:
      return []
    case 5:
      return facts.filter((f) => f.claims.length === 0).map((f) => ({ fact_id: f.id, row_id: f.row_id, s: f.s, p: f.p, o: f.o, origin: f.origin, cited: [] }))
    default:
      return `no provenance query ${n}; they are 1-5`
  }
}

const QUERY_NAMES: Record<number, string> = { 1: "edge_to_passage", 2: "fact_producers", 3: "claims_from", 4: "unresolved_anchors", 5: "unsourced_facts" }

/** AI SDK v5 UI message stream chunks for one mock assistant reply. */
function chatChunks(runId: string | undefined, question: string): unknown[] {
  const run = runId ? db.runs.find((r) => r.run_id === runId) : undefined
  const text = run
    ? `(mock reply) Run ${run.run_id} (${run.condition}, seed ${run.seed}) ended with exit status ${run.exit_status}: ` +
      `${run.facts ?? 0} facts, ${run.claims_accepted} accepted and ${run.claims_rejected} rejected claims. ` +
      (run.score?.support_share != null ? `Support share ${(run.score.support_share * 100).toFixed(0)}%. ` : "") +
      `You asked: “${question}”.\n\n` +
      // the chat agent answers with Markdown: a table, bold, and (never rendered) raw HTML
      `| facts | accepted claims | rejected claims |\n|---|---|---|\n| ${run.facts ?? 0} | ${run.claims_accepted} | ${run.claims_rejected} |\n\n` +
      `**Read from get_run.** <b data-testid="raw-html">raw html</b>`
    : `(mock reply) There are ${db.runs.length} runs over ${new Set(db.runs.map((r) => r.qid)).size} questions. Open a run to ask about it. You asked: “${question}”.`
  const words = text.split(/(?<= )/)
  return [
    { type: "start", messageId: `msg-${Date.now()}` },
    { type: "start-step" },
    { type: "tool-input-available", toolCallId: "call-1", toolName: runId ? "get_run" : "list_runs", input: runId ? { run_id: runId } : {} },
    { type: "tool-output-available", toolCallId: "call-1", output: run ?? db.runs.map((r) => r.run_id) },
    { type: "finish-step" },
    { type: "start-step" },
    { type: "text-start", id: "text-1" },
    ...words.map((delta) => ({ type: "text-delta", id: "text-1", delta })),
    { type: "text-end", id: "text-1" },
    { type: "finish-step" },
    { type: "finish" },
  ]
}

export const handlers = [
  ...evHandlers,
  http.get("/api/health", () => HttpResponse.json({ ok: true, version: "0.2.0-mock" })),
  http.get("/api/config", () => HttpResponse.json(config)),

  // questions and concepts
  http.get("/api/questions", () => HttpResponse.json(QUESTIONS.map(questionSummary))),
  http.get("/api/questions/:qid", ({ params }) => {
    const found = questionDetail(String(params.qid))
    return found ? HttpResponse.json(found) : notFound(`question: '${String(params.qid)}'`)
  }),
  http.post("/api/questions/:qid/concepts/propose", async ({ params, request }) => {
    const qid = String(params.qid)
    if (!QUESTIONS.some((q) => q.id === qid)) return notFound(`question: '${qid}'`)
    if (activeJob("concepts", qid)) return detail(409, `a concept proposal for ${qid} is already queued or running`)
    if (db.briefs[qid]?.length) return detail(409, `${qid} already has proposed briefs; pick one`)
    const body = (await request.json()) as ProposeRequest
    const args = { qid, temperature: body.temperature ?? 0.7, seed: body.seed ?? 1 }
    const job = newJob("concepts", args, [pending("propose", `python -m agent.cli concepts propose ${qid} --temperature ${args.temperature} --seed ${args.seed}`)], { qid, state: "running", started_at: new Date().toISOString() })
    setTimeout(() => {
      db.briefs[qid] = structuredClone(BRIEFS.q07).map((b) => ({ ...b, title: `${b.title} (${qid})` }))
      finishJob(job.id)
    }, timing.streamMs * 3)
    return HttpResponse.json(job, { status: 202 })
  }),
  http.post("/api/questions/:qid/concepts/pick", async ({ params, request }) => {
    const qid = String(params.qid)
    if (!QUESTIONS.some((q) => q.id === qid)) return notFound(`question: '${qid}'`)
    const body = (await request.json()) as PickRequest
    if (!Number.isInteger(body.choice) || body.choice < 1 || body.choice > 5) {
      return HttpResponse.json({ detail: [{ loc: ["body", "choice"], msg: "Input should be between 1 and 5", type: "value_error" }] }, { status: 422 })
    }
    const briefs = db.briefs[qid] ?? []
    if (!briefs.length) return detail(409, `${qid} has no proposed briefs yet; propose first`)
    if (body.choice > briefs.length) return detail(400, `choice must be 1..${briefs.length}`)
    const gold = GOLD.find((g) => g.qid === qid)
    if (gold && gold.status !== "none") return detail(409, `the gold build for ${qid} has started on the current pick; it can no longer change`)
    const current = db.picks[qid]
    const used = db.runs.filter((r) => r.qid === qid && r.concept_current === true)
    if (current && current.choice !== body.choice && used.length && !body.force) {
      return detail(409, `${used.length} run(s) used ${qid}'s current concept; changing the pick leaves them on a replaced concept (set force to change it anyway)`)
    }
    if (current && current.choice !== body.choice) for (const r of used) r.concept_current = false
    db.picks[qid] = {
      choice: body.choice, picked_by: body.picked_by ?? "user", reason: body.reason ?? null, title: briefs[body.choice - 1].title,
      concept_sha256: `${"ab".repeat(31)}${String(body.choice).padStart(2, "0")}`, replaces_concept_sha256: current?.concept_sha256 ?? null,
    }
    return HttpResponse.json(questionDetail(qid))
  }),

  // runs
  http.get("/api/runs", ({ request }) => {
    const url = new URL(request.url)
    const qid = url.searchParams.get("qid")
    const condition = url.searchParams.get("condition")
    const stale = url.searchParams.get("include_stale") === "true"
    const runs = db.runs
      .filter((r) => (!qid || (r.qid === qid && (stale || r.concept_current !== false))) && (!condition || r.condition === condition))
      .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
    return HttpResponse.json(runs)
  }),
  http.post("/api/runs", async ({ request }) => {
    const body = (await request.json()) as RunRequest
    if (!body.qid === !body.concept_path) return detail(400, "give exactly one of qid and concept_path")
    if (body.qid && !db.picks[body.qid]) return detail(409, `${body.qid} has no picked concept yet`)
    const condition = body.condition ?? "claim_on"
    const name = `${body.qid ?? "concept"}-${condition}-s${body.seed ?? 1}-web20261013T090000-${String(db.nextJob).padStart(4, "0")}`
    const steps = ["run", ...(condition === "claim_off" && body.attach !== false ? ["attach"] : []), "verify", "pairs", "graph", "export-prov", "score"]
    const job = newJob("run", { ...body }, steps.map((s) => pending(s, `python -m agent.cli ${s} ${name}`)), { run_id: `web~${name}`, qid: body.qid ?? null })
    return HttpResponse.json(job, { status: 202 })
  }),
  http.get("/api/runs/:runId", ({ params }) => {
    const found = db.details[String(params.runId)]
    return found ? HttpResponse.json(found) : notFound(`run: '${String(params.runId)}'`)
  }),
  http.get("/api/runs/:runId/steps", ({ params }) => {
    const steps = STEPS[String(params.runId)]
    return steps ? HttpResponse.json(steps) : notFound(`run: '${String(params.runId)}'`)
  }),
  http.get("/api/runs/:runId/steps/:step/output", ({ params, request }) => {
    const agent = new URL(request.url).searchParams.get("agent_id") ?? "main"
    const step = (STEPS[String(params.runId)] ?? []).find((s) => s.step === Number(params.step) && s.agent_id === agent)
    if (!step || step.output_head === null || step.output_head === undefined) return notFound(`output of step ${String(params.step)} (${agent})`)
    return new HttpResponse(`${step.output_head}\n`, { headers: { "Content-Type": "text/plain; charset=utf-8" } })
  }),
  http.get("/api/runs/:runId/stream", ({ params }) => {
    const runId = String(params.runId)
    const run = db.runs.find((r) => r.run_id === runId)
    if (!run) return notFound(`run: '${runId}'`)
    return eventStream(async function* () {
      if (run.live) {
        let id = 0
        for (const record of LIVE_RECORDS) {
          await delay(timing.streamMs)
          yield { event: "record", data: JSON.stringify(record), id: ++id }
        }
        await delay(timing.streamMs)
        finishLiveRun(run)
      }
      yield { event: "done", data: JSON.stringify({ run_id: runId, records: LIVE_RECORDS.length, exit_status: run.exit_status }) }
    })
  }),
  http.get("/api/runs/:runId/claims", ({ params }) => {
    const runId = String(params.runId)
    return db.details[runId] ? HttpResponse.json(claimsOf(runId)) : notFound(`run: '${runId}'`)
  }),
  http.get("/api/runs/:runId/graph", ({ params }) => {
    const graph = GRAPHS[String(params.runId)]
    return graph ? HttpResponse.json(graph) : notFound("graph.json yet (run `agent graph` on it)")
  }),
  http.get("/api/runs/:runId/facts/:factId/walk", ({ params, request }) => {
    const runId = String(params.runId)
    const judge = new URL(request.url).searchParams.get("judge") === "true"
    const answer = db.details[runId]?.answer ?? null
    if (!answer) return detail(404, `${runId} has no answer.json yet`)
    const walk = walkFor(runId, answer, String(params.factId), judge)
    return walk ? HttpResponse.json(walk) : detail(404, `${runId} has no fact '${String(params.factId)}'`)
  }),
  http.get("/api/runs/:runId/score", ({ params }) => {
    const score = SCORES[String(params.runId)]
    return score ? HttpResponse.json(score) : detail(404, `${String(params.runId)} has no score.json yet`)
  }),

  // corpus
  http.get("/api/corpus/:paperId", ({ params, request }) => {
    const url = new URL(request.url)
    const start = Number(url.searchParams.get("start"))
    const end = Number(url.searchParams.get("end"))
    const known = passageOf({ paper_id: String(params.paperId), anchor: { start, end } })
    if (known) return HttpResponse.json(known)
    if (!Object.values(PASSAGES).some((p) => p.paper_id === params.paperId)) return notFound(`paper in the corpus manifest: '${String(params.paperId)}'`)
    const text = "(mock) this part of the paper is not in the fixtures."
    return HttpResponse.json({ paper_id: String(params.paperId), title: String(params.paperId), text, offset: start, length: end + 1000, highlight: { start: 0, end: 6 }, highlight_utf16: { start: 0, end: 6 } })
  }),

  // gold, results
  http.get("/api/gold", () => HttpResponse.json(GOLD)),
  http.get("/api/gold/:qid/key", ({ params }) => {
    const key = GOLD_KEYS[String(params.qid)]
    return key ? HttpResponse.json(key) : detail(404, `no answer key for ${String(params.qid)} yet`)
  }),
  http.post("/api/gold/:qid/build", ({ params }) => {
    const qid = String(params.qid)
    if (!QUESTIONS.some((q) => q.id === qid)) return notFound(`question: '${qid}'`)
    if (activeJob("gold", qid)) return detail(409, `a gold build for ${qid} is already queued or running`)
    const job = newJob("gold", { qid }, ["build", "triage", "pool", "draft"].map((s) => pending(`gold ${s}`, `python -m gold.cli ${s} ${qid}`)), { qid })
    return HttpResponse.json(job, { status: 202 })
  }),
  http.get("/api/results", () => HttpResponse.json(RESULTS)),

  // provenance
  http.post("/api/sparql", async ({ request }) => {
    const body = (await request.json()) as SparqlRequest
    const query = body.query.replace(/^\s*(PREFIX[^\n]*\n|#[^\n]*\n|\s)*/i, "")
    if (!/^(SELECT|ASK|CONSTRUCT|DESCRIBE)\b/i.test(query)) {
      return detail(400, "only SELECT, ASK, CONSTRUCT and DESCRIBE queries are allowed (the store is read-only)")
    }
    if (/^ASK\b/i.test(query)) return HttpResponse.json({ vars: [], rows: [], boolean: true })
    if (body.run_id && !db.details[body.run_id]) return notFound(`run: '${body.run_id}'`)
    const claims = body.run_id ? claimsOf(body.run_id) : Object.values(CLAIMS).flat()
    return HttpResponse.json({
      vars: ["claim_id", "s", "p", "o", "step_id"],
      rows: claims.filter((c) => c.claim_id).map((c) => ({ claim_id: c.claim_id, s: c.s, p: c.p, o: c.o, step_id: c.step })),
      boolean: null,
    })
  }),
  http.get("/api/queries/:n", ({ params, request }) => {
    const url = new URL(request.url)
    const runId = url.searchParams.get("run_id") ?? ""
    if (!db.details[runId]) return notFound(`run: '${runId}'`)
    const n = Number(params.n)
    const rows = provQuery(n, runId, url)
    if (typeof rows === "string") return detail(n >= 1 && n <= 5 ? 400 : 404, rows)
    return HttpResponse.json({ n, name: QUERY_NAMES[n], run_id: runId, rows })
  }),

  // jobs
  http.get("/api/jobs", () => HttpResponse.json(db.jobs)),
  http.get("/api/jobs/:id", ({ params }) => {
    const job = db.jobs.find((j) => j.id === params.id)
    return job ? HttpResponse.json(job) : notFound(`job: '${String(params.id)}'`)
  }),
  http.post("/api/jobs/:id/cancel", ({ params }) => {
    const job = db.jobs.find((j) => j.id === params.id)
    if (!job) return notFound(`job: '${String(params.id)}'`)
    if (job.state !== "queued" && job.state !== "running") return detail(409, `job ${job.id} is ${job.state}; only a queued or running job can be cancelled`)
    finishJob(job.id, -15)
    job.error = "cancelled"
    return HttpResponse.json(job)
  }),
  http.get("/api/jobs/:id/log", ({ params }) => {
    const job = db.jobs.find((j) => j.id === params.id)
    if (!job) return notFound(`job: '${String(params.id)}'`)
    const lines = JOB_LOGS[job.id] ?? [`$ ${job.steps?.[0]?.command ?? job.kind}`]
    return eventStream(async function* () {
      let id = 0
      for (const line of lines) {
        await delay(timing.streamMs / 3)
        yield { event: "line", data: line, id: ++id }
      }
      for (let n = 4; (job.state === "running" || job.state === "queued") && n < 40; n++) {
        await delay(timing.streamMs * 2)
        yield { event: "line", data: `step ${n}: waiting for the model …`, id: ++id }
      }
      yield { event: "done", data: JSON.stringify(job) }
    })
  }),

  // chat (AI SDK v5 UI message stream)
  http.post("/api/chat", async ({ request }) => {
    const body = (await request.json()) as { run_id?: string; messages?: { role: string; parts?: { type: string; text?: string }[] }[] }
    const last = [...(body.messages ?? [])].reverse().find((m) => m.role === "user")
    const question = last?.parts?.find((p) => p.type === "text")?.text ?? ""
    const chunks = chatChunks(body.run_id, question)
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      async start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`))
          await delay(timing.streamMs / 20)
        }
        controller.enqueue(encoder.encode("data: [DONE]\n\n"))
        controller.close()
      },
    })
    return new HttpResponse(stream, {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", "x-vercel-ai-ui-message-stream": "v1" },
    })
  }),
]
