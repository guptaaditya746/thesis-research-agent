/**
 * The mock's writes against the backend's: write-contract.json holds what the real backend answered to each
 * scenario (webapp/tests/write_contract.py, run in order on one world), and the mock must answer the same
 * on the fields both give (status, detail, refs, lane, kind, problems). The scenarios run in order on one
 * mock db, as they ran on one world: scenario 8 proposes `p-new`, whose job is ended with `finishJob` before
 * scenario 9 writes its decisions.
 *
 *     regenerate: uv run python -m webapp.tests.evidence_world <tmp> --mocks webapp/web/src/mocks/ev-fixtures.json
 */
import { beforeAll, describe, expect, it } from "vitest"

import contract from "./write-contract.json"
import { finishJob, resetDb } from "./handlers"

interface Scenario {
  name: string
  method: "POST" | "PUT"
  path: string
  body: Record<string, unknown>
  status: number
  response: Record<string, unknown>
}

const SCENARIOS = contract as Scenario[]
const COMPARED = ["detail", "refs", "lane", "kind", "problems"] as const

/** The fields both sides give, as {status, detail, refs, lane, kind, problems} (absent ones left out). */
const compared = (status: number, response: Record<string, unknown>) =>
  Object.fromEntries([["status", status], ...COMPARED.filter((k) => k in response).map((k) => [k, response[k]])])

const answers: { status: number; response: Record<string, unknown> }[] = []

describe("the mock answers writes as the backend does (write-contract.json)", () => {
  beforeAll(async () => {
    resetDb()
    for (const s of SCENARIOS) {
      const r = await fetch(new URL(s.path, window.location.origin), {
        method: s.method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(s.body),
      })
      const response = (await r.json()) as Record<string, unknown>
      answers.push({ status: r.status, response })
      if (s.path === "/api/ev/jobs/propose" && r.status === 202) finishJob(response.id as string)
    }
  })

  it("holds the ten scenarios", () => {
    expect(SCENARIOS).toHaveLength(10)
  })

  it.each(SCENARIOS.map((s, n) => [n + 1, s.name, n] as const))("%i. %s", (_, __, n) => {
    const s = SCENARIOS[n]
    expect(compared(answers[n].status, answers[n].response)).toEqual(compared(s.status, s.response))
  })
})
