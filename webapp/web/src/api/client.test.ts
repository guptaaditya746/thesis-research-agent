import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"

import { server } from "@/mocks/node"

import { api, ApiError, apiUrl, isNotFound, urls } from "./client"

describe("API client", () => {
  it("builds absolute URLs and drops empty parameters", () => {
    expect(apiUrl("/api/runs", { qid: "q01", condition: undefined, x: "" })).toBe("http://localhost:5173/api/runs?qid=q01")
    expect(urls.runStream("a b")).toBe("http://localhost:5173/api/runs/a%20b/stream")
    expect(urls.stepOutput("r1", 3)).toBe("http://localhost:5173/api/runs/r1/steps/3/output")
  })

  it("reads typed JSON", async () => {
    const questions = await api.questions()
    expect(questions).toHaveLength(12)
    expect(questions[0]).toMatchObject({ id: "q01", concept: { status: "picked", picked_by: "provisional-first" }, runs: { claim_on: 2, claim_off: 1 } })
  })

  it("passes filters as query parameters", async () => {
    const off = await api.runs({ qid: "q01", condition: "claim_off" })
    expect(off.map((r) => r.run_id)).toEqual(["q01-off-s1"])
    const all = await api.runs()
    expect(all.length).toBeGreaterThan(off.length)
  })

  it("posts JSON bodies and returns the reply", async () => {
    const question = await api.pickConcept("q07", { choice: 2, picked_by: "user", reason: "test" })
    expect(question.picked).toEqual({ choice: 2, picked_by: "user", reason: "test" })
    expect(question.concept.status).toBe("picked")
    const job = await api.startRun({ qid: "q01", condition: "claim_on", temperature: 0.7, seed: 3, steps: 60, tokens: 2_000_000, sandbox: "landlock", attach: false })
    expect(job).toMatchObject({ kind: "run", state: "queued" })
    expect((await api.jobs())[0].id).toBe(job.id)
  })

  it("raises ApiError with FastAPI's detail", async () => {
    const error = await api.pickConcept("q07", { choice: 9, picked_by: "user", reason: "" }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 422, message: "choice must be between 1 and 3", path: "/api/questions/q07/concepts/pick" })
    const conflict = await api.startRun({ qid: "q05", condition: "claim_on", temperature: 0.7, seed: 1, steps: 60, tokens: 1, sandbox: "landlock", attach: false }).catch((e: unknown) => e)
    expect(conflict).toMatchObject({ status: 409, message: "question q05 has no picked concept" })
  })

  it("joins FastAPI validation errors and survives a non-JSON error body", async () => {
    server.use(
      http.get("/api/health", () => HttpResponse.json({ detail: [{ msg: "field required" }, { msg: "bad seed" }] }, { status: 422 })),
      http.get("/api/config", () => new HttpResponse("upstream down", { status: 502, statusText: "Bad Gateway" })),
    )
    await expect(api.health()).rejects.toMatchObject({ status: 422, message: "field required; bad seed" })
    await expect(api.config()).rejects.toMatchObject({ status: 502, message: "502 Bad Gateway" })
  })

  it("maps 404 to null where absence is a state, and to an error elsewhere", async () => {
    expect(await api.score("q01-on-s2")).toBeNull()
    expect(await api.goldKey("q12")).toBeNull()
    expect((await api.score("q01-on-s1"))?.support.support_share).toBe(0.6)
    const missing = await api.run("nope").catch((e: unknown) => e)
    expect(isNotFound(missing)).toBe(true)
    server.use(http.get("/api/results", () => HttpResponse.json({ detail: "boom" }, { status: 500 })))
    await expect(api.results()).rejects.toMatchObject({ status: 500, message: "boom" })
  })

  it("returns step output as text and the five queries as rows", async () => {
    expect(await api.stepOutput("q01-on-s1", 3)).toContain('"claim_id": "claim-000001"')
    const unsourced = await api.provQuery(5, "q01-on-s1")
    expect(unsourced).toEqual([{ fact_id: "f5", row_id: "r5", s: "p3", p: "evaluatesOn", o: "HellaSwag", origin: "research", cited: [] }])
    await expect(api.provQuery(3, "q01-on-s1")).rejects.toMatchObject({ status: 400 })
    expect(await api.provQuery(3, "q01-on-s1", { agent: "sub-01" })).toHaveLength(3)
  })

  it("sends SPARQL with the run scope and surfaces the read-only refusal", async () => {
    const result = await api.sparql({ query: "SELECT * WHERE { ?s ?p ?o }", run_id: "q01-off-s1" })
    expect(result.vars).toContain("claim_id")
    expect(result.rows).toHaveLength(3)
    await expect(api.sparql({ query: "PREFIX x: <y>\nDELETE WHERE { ?s ?p ?o }" })).rejects.toMatchObject({ status: 400 })
  })

  it("passes the abort signal through", async () => {
    const controller = new AbortController()
    controller.abort()
    await expect(api.questions(controller.signal)).rejects.toThrow()
  })
})
