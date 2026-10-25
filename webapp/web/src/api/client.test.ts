import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"

import { finishJob } from "@/mocks/handlers"
import { server } from "@/mocks/node"

import { ApiError, apiUrl, getJson, isConflict, isNotFound } from "./client"
import { evApi } from "./ev"

describe("API client", () => {
  it("builds absolute URLs and drops empty and false parameters", () => {
    expect(apiUrl("/api/ev/jobs/x/log", { lines: 40, a: undefined, b: "", c: false })).toBe("http://localhost:5173/api/ev/jobs/x/log?lines=40")
  })

  it("reads typed JSON and encodes path segments", async () => {
    const [q] = await evApi.questions()
    expect(q).toMatchObject({ id: "rag-factuality", protocol: "rag-factuality", agentic_protocol: "rag-factuality-agentic" })
    const run = await evApi.run("cascade~rag-tpl-w1-explicit")
    expect(run.id).toBe("cascade~rag-tpl-w1-explicit")
  })

  it("starts a job with a JSON body, lists it, tails its log and cancels it", async () => {
    const job = await evApi.startJob("rag-baseline", { corpus: "rag-tpl-w1-paraphrased", question: "rag-factuality", model: "orch-model", retrieval: "global", k: 8 })
    expect(job).toMatchObject({ kind: "rag-baseline", lane: "model", state: "running", refs: { run: "rag-baseline~rag-tpl-w1-paraphrased" } })
    expect((await evApi.jobs())[0].id).toBe(job.id)
    expect(await evApi.jobLog(job.id)).toContain("$ python -m webapp.tool rag-baseline")
    const again = await evApi.startJob("rag-baseline", { corpus: "rag-tpl-w1-paraphrased", question: "rag-factuality" }).catch((e: unknown) => e)
    expect(isConflict(again)).toBe(true)
    expect(await evApi.cancelJob(job.id)).toMatchObject({ state: "failed", error: "cancelled" })
  })

  it("raises ApiError with FastAPI's detail, validation errors with their field", async () => {
    const taken = await evApi.startJob("run", { corpus: "rag-tpl-w1-mixed", protocol: { source: "repo", name: "rag-factuality" } }).catch((e: unknown) => e)
    expect(taken).toBeInstanceOf(ApiError)
    expect(taken).toMatchObject({ status: 409, path: "/api/ev/jobs/run", message: "run cascade/rag-tpl-w1-mixed exists; give the run another name" })
    await expect(evApi.startJob("synth", { name: "../x" })).rejects.toMatchObject({ status: 422, message: "name: String should match pattern" })
    server.use(http.get("/api/ev/config", () => new HttpResponse("upstream down", { status: 502, statusText: "Bad Gateway" })))
    await expect(evApi.config()).rejects.toMatchObject({ status: 502, message: "502 Bad Gateway" })
  })

  it("a finished propose job makes a proposal whose decisions can be written", async () => {
    const job = await evApi.startJob("propose", { proposal: "p1", question: "rag-factuality" })
    finishJob(job.id)
    const p = await evApi.proposal("p1")
    expect(p).toMatchObject({ frozen: false, decision_problems: [] })
    const decisions = p.cards.map((c) => ({ card: c.id, choice: c.default ?? "draft", reason: "", by: "model", value: null }))
    const stale = await evApi.putDecisions("p1", { decisions, base_sha256: "not-what-was-loaded" }).catch((e: unknown) => e)
    expect(isConflict(stale)).toBe(true)
    const result = await evApi.putDecisions("p1", { decisions, base_sha256: p.decisions_sha256 })
    expect(result.sha256).not.toBe(p.decisions_sha256)
    expect(result.problems).toContain("screen: a decision without a reason is refused")
    await expect(evApi.startJob("freeze", { proposal: "p1" })).rejects.toMatchObject({ status: 409 })
  })

  it("maps 404 to isNotFound and passes the abort signal through", async () => {
    const missing = await evApi.run("nope~nope").catch((e: unknown) => e)
    expect(isNotFound(missing)).toBe(true)
    const controller = new AbortController()
    controller.abort()
    await expect(getJson("/api/ev/questions", undefined, controller.signal)).rejects.toThrow()
  })
})
