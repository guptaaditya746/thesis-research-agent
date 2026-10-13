/**
 * MSW handlers: the backend API of docs/e2e-build-plan.md over the fixtures, for `npm run
 * dev:mock` (service worker) and the tests (Node). State lives in one in-memory `db` so that
 * picks, new jobs and the live run's end show up on the next request; `resetDb()` restores it.
 *
 * The streams behave like the backend's: the live run (q01-on-s2) plays its remaining
 * events.jsonl records and `done`, then is marked finished; job logs replay their lines;
 * POST /api/chat answers in the AI SDK v5 UI message stream protocol (what pydantic-ai's
 * VercelAIAdapter sends), with one tool call and a short text.
 */
import { delay, http, HttpResponse } from "msw"

import type {
  Claim,
  ConceptBrief,
  ConceptPick,
  Job,
  PickRequest,
  ProposeRequest,
  QuestionDetail,
  QuestionSummary,
  RunDetail,
  RunSummary,
  SparqlRequest,
  StartRunRequest,
} from "@/api/types"

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
function eventStream(events: () => AsyncGenerator<{ event?: string; data: string }>) {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      for await (const { event, data } of events()) {
        const lines = data.split("\n").map((line) => `data: ${line}`).join("\n")
        controller.enqueue(encoder.encode(`${event ? `event: ${event}\n` : ""}${lines}\n\n`))
      }
      controller.close()
    },
  })
  return new HttpResponse(body, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" } })
}

const notFound = (what: string) => HttpResponse.json({ detail: `${what} not found` }, { status: 404 })
const unprocessable = (detail: string) => HttpResponse.json({ detail }, { status: 422 })

function questionSummary(q: QuestionSummary): QuestionSummary {
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
    gold: gold ? { status: gold.status, rows: gold.counts.rows ?? null, facts: gold.counts.facts ?? null } : q.gold,
    runs: {
      claim_on: db.runs.filter((r) => r.qid === q.id && r.condition === "claim_on").length,
      claim_off: db.runs.filter((r) => r.qid === q.id && r.condition === "claim_off").length,
    },
  }
}

function questionDetail(qid: string): QuestionDetail | null {
  const q = QUESTIONS.find((x) => x.id === qid)
  if (!q) return null
  const pick = db.picks[qid]
  return {
    ...questionSummary(q),
    briefs: db.briefs[qid] ?? [],
    picked: pick ? { choice: pick.choice, picked_by: pick.picked_by, reason: pick.reason } : null,
  }
}

function newJob(kind: string, args: Job["args"], extra: Partial<Job> = {}): Job {
  const job: Job = {
    id: `job-${String(db.nextJob++).padStart(4, "0")}`, kind, args, state: "running",
    started_at: new Date().toISOString(), ended_at: null, exit_code: null, ...extra,
  }
  db.jobs.unshift(job)
  return job
}

function finishJob(id: string, exit = 0) {
  const job = db.jobs.find((j) => j.id === id)
  if (job) Object.assign(job, { state: exit === 0 ? "done" : "failed", ended_at: new Date().toISOString(), exit_code: exit })
}

/** The live run's end: what the backend reports once answer.json exists. */
function finishLiveRun(runId: string) {
  const run = db.runs.find((r) => r.run_id === runId)
  const detail = db.details[runId]
  if (!run || !detail || !run.live) return
  Object.assign(run, {
    live: false, exit_status: "submitted", steps: 6, model_calls: 6, tokens: 42_314, seconds: 52.6, rows: 1, facts: 1,
    claims_accepted: 1, claims_rejected: 1, verify: "ok",
  })
  detail.summary = run
  detail.answer = LIVE_ANSWER
  detail.verify = { ok: true, errors: [], stats: { steps: 6, model_calls: 6, claims_accepted: 1, claims_rejected: 1, tokens: 42_314 } }
  const job = db.jobs.find((j) => j.run_id === runId && j.state === "running")
  if (job) finishJob(job.id)
}

const claimsOf = (runId: string): Claim[] => CLAIMS[runId] ?? []

/** The five provenance queries (agent/queries.py) over the fixtures. */
function provQuery(n: number, runId: string, url: URL): Record<string, unknown>[] | string {
  const detail = db.details[runId]
  const steps = STEPS[runId] ?? []
  const accepted = claimsOf(runId).filter((c) => c.status === "accepted")
  const stepOf = (c: Claim) => steps.find((s) => s.step === c.step && s.agent_id === c.agent_id)
  const facts = (detail?.answer?.rows ?? []).flatMap((r) => r.facts.map((f) => ({ ...f, row_id: r.id })))
  switch (n) {
    case 1: {
      const edge = url.searchParams.get("edge")
      return accepted
        .map((c) => ({
          edge_id: `edge-${c.claim_id!.slice(6)}`, claim_id: c.claim_id, origin: c.origin, s: c.s, p: c.p, o: c.o,
          step_id: c.step, agent_id: c.agent_id, phase: stepOf(c)?.phase ?? null, command: stepOf(c)?.command ?? null,
          file: c.file, start: c.anchor?.start, end: c.anchor?.end, exact: c.quote,
        }))
        .filter((row) => !edge || row.edge_id === edge)
    }
    case 2: {
      const fact = url.searchParams.get("fact")
      return facts
        .filter((f) => !fact || f.id === fact)
        .flatMap((f) => f.claims.map((id) => {
          const c = accepted.find((x) => x.claim_id === id)
          return {
            fact_id: f.id, claim_id: id, origin: f.origin, step_id: c?.step ?? null, agent_id: c?.agent_id ?? null,
            phase: c ? stepOf(c)?.phase ?? null : null, command: c ? stepOf(c)?.command ?? null : null,
            model_call: c ? `t${String(c.step * 3 - 2).padStart(6, "0")}` : null,
            model: c?.agent_id === "main" ? "orch-model" : "sub-model-1",
          }
        }))
    }
    case 3: {
      const step = url.searchParams.get("step")
      const agent = url.searchParams.get("agent")
      if (!step && !agent) return "query 3 needs a step, an agent, or both"
      return claimsOf(runId)
        .filter((c) => (!step || c.step === Number(step)) && (!agent || c.agent_id === agent))
        .map((c) => ({ claim_id: c.claim_id, status: c.status, origin: c.origin, s: c.s, p: c.p, o: c.o, step_id: c.step, agent_id: c.agent_id, file: c.file, exact: c.quote }))
    }
    case 4:
      return []
    case 5:
      return facts.filter((f) => f.claims.length === 0).map((f) => ({ fact_id: f.id, row_id: f.row_id, s: f.s, p: f.p, o: f.o, origin: f.origin, cited: [] }))
    default:
      return `no query ${n}`
  }
}

/** AI SDK v5 UI message stream chunks for one mock assistant reply. */
function chatChunks(runId: string | undefined, question: string): unknown[] {
  const run = runId ? db.runs.find((r) => r.run_id === runId) : undefined
  const text = run
    ? `(mock reply) Run **${run.run_id}** (${run.condition}, seed ${run.seed}) ended with exit status *${run.exit_status ?? "running"}*: ` +
      `${run.facts} facts, ${run.claims_accepted} accepted and ${run.claims_rejected} rejected claims. ` +
      (run.score?.support_share != null ? `Support share ${(run.score.support_share * 100).toFixed(0)}%. ` : "") +
      `You asked: “${question}”.`
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
  http.get("/api/health", () => HttpResponse.json({ ok: true, version: "0.2.0-mock" })),
  http.get("/api/config", () => HttpResponse.json(config)),

  // questions and concepts
  http.get("/api/questions", () => HttpResponse.json(QUESTIONS.map(questionSummary))),
  http.get("/api/questions/:qid", ({ params }) => {
    const detail = questionDetail(String(params.qid))
    return detail ? HttpResponse.json(detail) : notFound(`question ${String(params.qid)}`)
  }),
  http.post("/api/questions/:qid/concepts/propose", async ({ params, request }) => {
    const qid = String(params.qid)
    if (!QUESTIONS.some((q) => q.id === qid)) return notFound(`question ${qid}`)
    const body = (await request.json()) as ProposeRequest
    const job = newJob("propose", { qid, ...body })
    setTimeout(() => {
      if (!db.briefs[qid]?.length) db.briefs[qid] = structuredClone(BRIEFS.q07).map((b) => ({ ...b, title: `${b.title} (${qid})` }))
      finishJob(job.id)
    }, timing.streamMs * 3)
    return HttpResponse.json(job, { status: 202 })
  }),
  http.post("/api/questions/:qid/concepts/pick", async ({ params, request }) => {
    const qid = String(params.qid)
    const body = (await request.json()) as PickRequest
    const briefs = db.briefs[qid] ?? []
    if (!QUESTIONS.some((q) => q.id === qid)) return notFound(`question ${qid}`)
    if (!Number.isInteger(body.choice) || body.choice < 1 || body.choice > briefs.length) {
      return unprocessable(`choice must be between 1 and ${briefs.length}`)
    }
    db.picks[qid] = { ...body, title: briefs[body.choice - 1].title }
    return HttpResponse.json(questionDetail(qid))
  }),

  // runs
  http.get("/api/runs", ({ request }) => {
    const url = new URL(request.url)
    const qid = url.searchParams.get("qid")
    const condition = url.searchParams.get("condition")
    const runs = db.runs
      .filter((r) => (!qid || r.qid === qid) && (!condition || r.condition === condition))
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
    return HttpResponse.json(runs)
  }),
  http.post("/api/runs", async ({ request }) => {
    const body = (await request.json()) as StartRunRequest
    if (!body.qid && !body.concept_path) return unprocessable("give qid or concept_path")
    if (body.qid && !db.picks[body.qid]) return HttpResponse.json({ detail: `question ${body.qid} has no picked concept` }, { status: 409 })
    const job = newJob("run", { ...body }, { state: "queued" })
    return HttpResponse.json(job, { status: 202 })
  }),
  http.get("/api/runs/:runId", ({ params }) => {
    const detail = db.details[String(params.runId)]
    return detail ? HttpResponse.json(detail) : notFound(`run ${String(params.runId)}`)
  }),
  http.get("/api/runs/:runId/steps", ({ params }) => {
    const steps = STEPS[String(params.runId)]
    return steps ? HttpResponse.json(steps) : notFound(`run ${String(params.runId)}`)
  }),
  http.get("/api/runs/:runId/steps/:step/output", ({ params }) => {
    const step = (STEPS[String(params.runId)] ?? []).find((s) => s.step === Number(params.step))
    if (!step?.output_head && step?.output_head !== "") return notFound(`output of step ${String(params.step)}`)
    return new HttpResponse(`${step.output_head}\n`, { headers: { "Content-Type": "text/plain; charset=utf-8" } })
  }),
  http.get("/api/runs/:runId/stream", ({ params }) => {
    const runId = String(params.runId)
    return eventStream(async function* () {
      if (db.runs.find((r) => r.run_id === runId)?.live) {
        for (const record of LIVE_RECORDS) {
          await delay(timing.streamMs)
          yield { event: "record", data: JSON.stringify(record) }
        }
        await delay(timing.streamMs)
        finishLiveRun(runId)
      }
      yield { event: "done", data: "" }
    })
  }),
  http.get("/api/runs/:runId/claims", ({ params }) => HttpResponse.json(claimsOf(String(params.runId)))),
  http.get("/api/runs/:runId/graph", ({ params }) => {
    const graph = GRAPHS[String(params.runId)]
    return graph ? HttpResponse.json(graph) : notFound("graph.json")
  }),
  http.get("/api/runs/:runId/facts/:factId/walk", ({ params }) => {
    const runId = String(params.runId)
    const walk = walkFor(runId, db.details[runId]?.answer ?? null, String(params.factId))
    return walk ? HttpResponse.json(walk) : notFound(`fact ${String(params.factId)}`)
  }),
  http.get("/api/runs/:runId/score", ({ params }) => {
    const score = SCORES[String(params.runId)]
    return score ? HttpResponse.json(score) : notFound("score.json")
  }),

  // corpus
  http.get("/api/corpus/:paperId", ({ params, request }) => {
    const url = new URL(request.url)
    const start = Number(url.searchParams.get("start"))
    const end = Number(url.searchParams.get("end"))
    const known = Object.values(PASSAGES).find((p) => p.paper_id === params.paperId && p.highlight.start === start)
    if (known) return HttpResponse.json(known)
    return HttpResponse.json({
      paper_id: String(params.paperId), title: null, offset: start,
      text: "(mock) the corpus file is not part of the fixtures.", highlight: { start, end: Math.max(start, end) },
    })
  }),

  // gold, results
  http.get("/api/gold", () => HttpResponse.json(GOLD)),
  http.get("/api/gold/:qid/key", ({ params }) => {
    const key = GOLD_KEYS[String(params.qid)]
    return key ? HttpResponse.json(key) : notFound("key.json")
  }),
  http.get("/api/results", () => HttpResponse.json(RESULTS)),

  // provenance
  http.post("/api/sparql", async ({ request }) => {
    const body = (await request.json()) as SparqlRequest
    const query = body.query.replace(/^\s*(PREFIX[^\n]*\n|#[^\n]*\n|\s)*/i, "")
    if (!/^(SELECT|ASK|CONSTRUCT)\b/i.test(query)) {
      return HttpResponse.json({ detail: "read-only store: only SELECT, ASK and CONSTRUCT queries" }, { status: 400 })
    }
    const claims = body.run_id ? claimsOf(body.run_id) : Object.values(CLAIMS).flat()
    return HttpResponse.json({
      vars: ["claim_id", "s", "p", "o", "step_id"],
      rows: claims.filter((c) => c.claim_id).map((c) => ({ claim_id: c.claim_id, s: c.s, p: c.p, o: c.o, step_id: c.step })),
    })
  }),
  http.get("/api/queries/:n", ({ params, request }) => {
    const url = new URL(request.url)
    const runId = url.searchParams.get("run_id") ?? ""
    if (!db.details[runId]) return notFound(`run ${runId}`)
    const rows = provQuery(Number(params.n), runId, url)
    return typeof rows === "string" ? HttpResponse.json({ detail: rows }, { status: 400 }) : HttpResponse.json(rows)
  }),

  // jobs
  http.get("/api/jobs", () => HttpResponse.json(db.jobs)),
  http.get("/api/jobs/:id", ({ params }) => {
    const job = db.jobs.find((j) => j.id === params.id)
    return job ? HttpResponse.json(job) : notFound(`job ${String(params.id)}`)
  }),
  http.get("/api/jobs/:id/log", ({ params }) => {
    const job = db.jobs.find((j) => j.id === params.id)
    const lines = JOB_LOGS[String(params.id)] ?? [`$ ${job?.kind ?? "job"} ${JSON.stringify(job?.args ?? {})}`]
    return eventStream(async function* () {
      for (const line of lines) {
        await delay(timing.streamMs / 3)
        yield { data: line }
      }
      for (let n = 4; job && (job.state === "running" || job.state === "queued") && n < 40; n++) {
        await delay(timing.streamMs * 2)
        yield { data: `step ${n}: waiting for the model …` }
      }
      yield { event: "done", data: "" }
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
