import { describe, expect, it } from "vitest"

import { runConfig } from "./run"

describe("runConfig", () => {
  it("reads the budget notices and the draft file the loop recorded", () => {
    const c = runConfig({ loop: { budget_warnings: [50, 75, 90], draft_file: "answer-draft.json", repeat_stop: 6 } })
    expect(c.loop).toEqual({ budget_warnings: [50, 75, 90], draft_file: "answer-draft.json" })
  })

  it("gives no notices to a prompt v1 run and to a run whose config.json predates them", () => {
    // agent/loop.py LEGACY_V1
    expect(runConfig({ loop: { budget_warnings: [], draft_file: null } }).loop).toEqual({ budget_warnings: [], draft_file: null })
    // the M1-real runs: a loop section without the setting, or none at all
    expect(runConfig({ loop: { harness: "mini-swe-agent 2.4.6" } }).loop).toEqual({ budget_warnings: [], draft_file: null })
    expect(runConfig({}).loop).toEqual({ budget_warnings: [], draft_file: null })
    expect(runConfig({ loop: { budget_warnings: ["50", 75] } }).loop?.budget_warnings).toEqual([75])
  })

  it("reads the sandbox mode", () => {
    expect(runConfig({ sandbox: { mode: "unsandboxed", landlock_abi: null } }).sandbox).toEqual({ mode: "unsandboxed" })
    expect(runConfig({}).sandbox).toBeUndefined()
  })
})
