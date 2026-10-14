import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"

import { RUN } from "@/mocks/fixtures"
import { server } from "@/mocks/node"

import { api, ApiError, apiUrl, isConflict, isNotFound, urls } from "./client"

describe("API client", () => {
  it("builds absolute URLs, drops empty and false parameters and encodes path segments", () => {
    expect(apiUrl("/api/runs", { qid: "q01", condition: undefined, x: "", include_stale: false })).toBe("http://localhost:5173/api/runs?qid=q01")
    expect(urls.runStream("a b")).toBe("http://localhost:5173/api/runs/a%20b/stream")
    expect(urls.runStream(RUN.on)).toBe("http://localhost:5173/api/runs/m4-72~q01-claim_on-r1-a1/stream")
    expect(urls.stepOutput("r1", 3)).toBe("http://localhost:5173/api/runs/r1/steps/3/output")
    // a subagent's output file is asked for with its id; the main agent's without
    expect(urls.stepOutput("r1", 6, "sub-01")).toBe("http://localhost:5173/api/runs/r1/steps/6/output?agent_id=sub-01")
    expect(urls.stepOutput("r1", 6, "main")).toBe("http://localhost:5173/api/runs/r1/steps/6/output")
  })

  it("reads typed JSON", async () => {
    const questions = await api.questions()
    expect(questions).toHaveLength(12)
    expect(questions[0]).toMatchObject({ id: "q01", concept: { status: "picked", picked_by: "provisional-first" }, runs: { claim_on: 2, claim_off: 1 } })
    expect(questions[0].gold).toMatchObject({ status: "reviewed", rows: 5, facts: 5 })
  })

  it("passes filters as query parameters", async () => {
    const off = await api.runs({ qid: "q01", condition: "claim_off" })
    expect(off.map((r) => r.run_id)).toEqual([RUN.off])
    const all = await api.runs()
    expect(all.length).toBeGreaterThan(off.length)
  })

  it("posts JSON bodies and returns the reply", async () => {
    const question = await api.pickConcept("q07", { choice: 2, picked_by: "user", reason: "test" })
    expect(question.picked).toMatchObject({ choice: 2, picked_by: "user", reason: "test", title: "Head-to-head comparisons" })
    expect(question.concept.status).toBe("picked")
    const job = await api.startRun({ qid: "q01", condition: "claim_off", temperature: 0.7, seed: 3, steps: null, tokens: null, sandbox: "landlock", attach: true })
    expect(job).toMatchObject({ kind: "run", state: "queued", qid: "q01" })
    expect(job.steps?.map((s) => s.name)).toEqual(["run", "attach", "verify", "pairs", "graph", "export-prov", "score"])
    expect((await api.jobs())[0].id).toBe(job.id)
  })

  it("raises ApiError with FastAPI's detail", async () => {
    const error = await api.pickConcept("q07", { choice: 4 }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 400, message: "choice must be 1..3", path: "/api/questions/q07/concepts/pick" })
    const conflict = await api.startRun({ qid: "q05", condition: "claim_on" }).catch((e: unknown) => e)
    expect(conflict).toMatchObject({ status: 409, message: "q05 has no picked concept yet" })
    expect(isConflict(conflict)).toBe(true)
    // the gold build of q02 has started on its pick: the pick can no longer change
    await expect(api.pickConcept("q02", { choice: 1 })).rejects.toMatchObject({ status: 409 })
  })

  it("joins FastAPI validation errors and survives a non-JSON error body", async () => {
    await expect(api.pickConcept("q07", { choice: 9 })).rejects.toMatchObject({ status: 422, message: "Input should be between 1 and 5" })
    server.use(http.get("/api/config", () => new HttpResponse("upstream down", { status: 502, statusText: "Bad Gateway" })))
    await expect(api.config()).rejects.toMatchObject({ status: 502, message: "502 Bad Gateway" })
  })

  it("maps 404 to null where absence is a state, and to an error elsewhere", async () => {
    expect(await api.score(RUN.live)).toBeNull()
    expect(await api.goldKey("q12")).toBeNull()
    expect((await api.score(RUN.on))?.support?.support_share).toBe(0.6)
    const missing = await api.run("nope").catch((e: unknown) => e)
    expect(isNotFound(missing)).toBe(true)
    server.use(http.get("/api/results", () => HttpResponse.json({ detail: "boom" }, { status: 500 })))
    await expect(api.results()).rejects.toMatchObject({ status: 500, message: "boom" })
  })

  it("asks for a batch's report by name", async () => {
    let asked: string | null = null
    server.use(http.get("/api/results", ({ request }) => {
      asked = new URL(request.url).searchParams.get("batch")
      return HttpResponse.json({ generated_at: "x" })
    }))
    await api.results("m4-72")
    expect(asked).toBe("m4-72")
  })

  it("reads a fact's walk, and asks the judge only when told to", async () => {
    const scored = await api.factWalk(RUN.live, "f1").catch((e: unknown) => e)
    expect(isNotFound(scored)).toBe(true) // no answer yet
    const walk = await api.factWalk(RUN.on, "f4")
    expect(walk).toMatchObject({ run_id: RUN.on, row_id: "r4", label: "partial", support: { label: "partial", source: "score" } })
    expect(walk.claims[0]).toMatchObject({ claim_id: "claim-000005", anchor_status: "ok", step: { step: 6, agent_id: "sub-01" } })
    let judged = false
    server.use(http.get("/api/runs/:run/facts/:fact/walk", ({ request }) => {
      judged = new URL(request.url).searchParams.get("judge") === "true"
      return HttpResponse.json(walk)
    }))
    await api.factWalk(RUN.on, "f4")
    expect(judged).toBe(false)
    await api.factWalk(RUN.on, "f4", { judge: true })
    expect(judged).toBe(true)
  })

  it("links step output as text (the walk's 'full output') and returns the five queries with their rows", async () => {
    expect(await (await fetch(urls.stepOutput(RUN.on, 3))).text()).toContain('"claim_id": "claim-000001"')
    expect(await (await fetch(urls.stepOutput(RUN.on, 6, "sub-01"))).text()).toContain("claim-000007")
    const unsourced = await api.provQuery(5, RUN.on)
    expect(unsourced).toEqual({ n: 5, name: "unsourced_facts", run_id: RUN.on, rows: [{ fact_id: "f5", row_id: "r5", s: "p3", p: "evaluatesOn", o: "HellaSwag", origin: "research", cited: [] }] })
    await expect(api.provQuery(3, RUN.on)).rejects.toMatchObject({ status: 400 })
    expect((await api.provQuery(3, RUN.on, { agent: "sub-01" })).rows).toHaveLength(3)
  })

  it("sends SPARQL with the run scope and surfaces the read-only refusal", async () => {
    const result = await api.sparql({ query: "SELECT * WHERE { ?s ?p ?o }", run_id: RUN.off })
    expect(result.vars).toContain("claim_id")
    expect(result.rows).toHaveLength(3)
    expect(await api.sparql({ query: "ASK { ?s ?p ?o }" })).toMatchObject({ boolean: true, rows: [] })
    await expect(api.sparql({ query: "PREFIX x: <y>\nDELETE WHERE { ?s ?p ?o }" })).rejects.toMatchObject({ status: 400 })
  })

  it("starts a gold build and cancels a job", async () => {
    const job = await api.buildGold("q03")
    expect(job).toMatchObject({ kind: "gold", qid: "q03", state: "queued" })
    await expect(api.buildGold("q03")).rejects.toMatchObject({ status: 409 })
    expect(await api.cancelJob(job.id)).toMatchObject({ id: job.id, state: "failed", error: "cancelled" })
    await expect(api.cancelJob(job.id)).rejects.toMatchObject({ status: 409 })
  })

  it("passes the abort signal through", async () => {
    const controller = new AbortController()
    controller.abort()
    await expect(api.questions(controller.signal)).rejects.toThrow()
  })
})
