/**
 * The evidence table on the run fixtures (src/mocks/ev-fixtures.json): rows per paper in lanes, a click on a
 * value opening the paper with that span marked, lane filters, sorting. jsdom is a narrow screen, so the
 * source panel opens as a sheet (a dialog).
 */
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it } from "vitest"

import type { EffectAnswer, EvRunDetail } from "@/api/ev"
import { evFixture } from "@/mocks/ev"
import { renderWithProviders } from "@/test/render"

import { EvidenceView } from "./EvidenceView"

const T = { timeout: 15_000 }
const EXPLICIT = "cascade~rag-tpl-w1-explicit"
const MEASUREMENT = "m-794d268457cdf26b"   // S001's RAG value 0.572 in the fixture's graph

/** The fixture run with S001 compared (no effect), S002 supporting and S003 contradicting. */
function determined(): EvRunDetail {
  const run = structuredClone(evFixture<EvRunDetail>(`/api/ev/runs/${EXPLICIT}`))
  const answer = run.answer as EffectAnswer
  const [s1, s2, s3] = answer.studies
  Object.assign(s1, { direction: "neutral", delta: 0.008, metric: "factual_accuracy", reason: null,
    treatment: { condition: "c-51d752c251545ddc", measurement: MEASUREMENT, value: 0.572 },
    control: { condition: "c-15b4f5c688653232", measurement: "m-none", value: 0.564 } })
  Object.assign(s2, { direction: "supports", delta: 0.09, metric: "factual_accuracy", reason: null,
    treatment: { condition: null, measurement: null, value: 0.71 }, control: { condition: null, measurement: null, value: 0.62 } })
  Object.assign(s3, { direction: "contradicts", delta: -0.06, metric: "factual_accuracy", reason: null,
    treatment: { condition: null, measurement: null, value: 0.55 }, control: { condition: null, measurement: null, value: 0.61 } })
  answer.counts = { supporting: 1, contradicting: 1, neutral: 1, undetermined: 3, duplicates: 0 }
  answer.label = "mixed"
  return run
}

/** A screen this wide: `(min-width: Npx)` queries answer by it (the setup's stub says no to every query). */
const stubbed = window.matchMedia
function screenWidth(px: number) {
  window.matchMedia = (query: string) => {
    const min = /min-width:\s*(\d+)px/.exec(query)
    return { ...stubbed(query), matches: min ? px >= Number(min[1]) : false }
  }
}
afterEach(() => { window.matchMedia = stubbed })

const lane = (table: HTMLElement, name: RegExp) => within(table).getByRole("rowgroup", { name })

describe("evidence table", () => {
  it("one row per paper, grouped by verdict, from the fixtures", async () => {
    screenWidth(1400)
    renderWithProviders(<EvidenceView run={evFixture<EvRunDetail>(`/api/ev/runs/${EXPLICIT}`)} />)
    const table = screen.getByRole("table", { name: "Evidence per paper" })
    for (const d of ["S001", "S002", "S003", "S004", "S005", "S006"]) {
      expect(within(table).getByRole("button", { name: `${d}: show the evidence in the paper` })).toBeInTheDocument()
    }
    expect(lane(table, /^undetermined: 6/)).toBeInTheDocument()
    expect(screen.getByText("Of 6 papers: 6 are undetermined.")).toBeInTheDocument()
    expect(within(table).getAllByText("no rag and baseline measurement on a question metric")).toHaveLength(4)
    // found by, from graph.json (S001's claim was found by the regex extractor)
    await waitFor(() => expect(within(within(table).getAllByRole("row").find((r) => r.textContent?.includes("S001"))!).getByText("regex")).toBeInTheDocument(), T)
  })

  it("a click on a value opens the paper with that value's span marked, and says why", async () => {
    screenWidth(375)
    const user = userEvent.setup()
    renderWithProviders(<EvidenceView run={determined()} />)
    const table = screen.getByRole("table", { name: "Evidence per paper" })
    expect(within(lane(table, /^no effect: 1/)).getByText("0.572")).toBeInTheDocument()
    expect(within(lane(table, /^supports: 1/)).getByText("0.710")).toBeInTheDocument()
    await user.click(within(table).getByRole("button", { name: /^S001: treatment .*0\.572, show in the paper/ }))
    const sheet = await screen.findByRole("dialog", {}, T)
    const text = await within(sheet).findByRole("region", { name: "Text of S001" }, T)
    const marked = [...text.querySelectorAll("mark")].filter((m) => (m.dataset.marks ?? "").split(" ").includes(MEASUREMENT))
    expect(marked.length).toBeGreaterThan(0)
    for (const m of marked) expect(m).toHaveAttribute("aria-pressed", "true")
    // only the row's items are drawn: the author claim of S001 is, an item of no row is not
    const why = within(sheet).getByRole("list", { name: "Why this verdict" })
    expect(within(why).getByText(/\|Δ\| < margin 0\.01 → no effect/)).toBeInTheDocument()
    expect(within(why).getAllByText("regex_measurement").length).toBeGreaterThan(0)
    // next paper in the table's order
    await user.click(within(sheet).getByRole("button", { name: "Next paper" }))
    expect(await within(sheet).findByRole("heading", { level: 3, name: "S004" }, T)).toBeInTheDocument()
  })

  it("a lane in the coverage legend filters the table; sorting says its order", async () => {
    const user = userEvent.setup()
    renderWithProviders(<EvidenceView run={determined()} />)
    const legend = screen.getByRole("list", { name: "6 papers by lane" })
    await user.click(within(legend).getByRole("button", { name: /contradicts/ }))
    const table = screen.getByRole("table", { name: "Evidence per paper" })
    expect(within(table).getAllByRole("rowgroup")).toHaveLength(2)   // the header and the one lane
    expect(within(table).getByRole("button", { name: "S003: show the evidence in the paper" })).toBeInTheDocument()
    expect(within(table).queryByRole("button", { name: "S001: show the evidence in the paper" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "all papers" }))
    const effect = within(table).getByRole("columnheader", { name: /^effect/ })
    expect(effect).toHaveAttribute("aria-sort", "none")
    await user.click(within(effect).getByRole("button"))
    expect(effect).toHaveAttribute("aria-sort", "descending")   // numbers sort largest first
    await user.click(within(effect).getByRole("button"))
    expect(effect).toHaveAttribute("aria-sort", "ascending")
  })

  it("a baseline lists every paper, the ones it did not cite apart, and opens its cited passages", async () => {
    const user = userEvent.setup()
    renderWithProviders(<EvidenceView run={evFixture<EvRunDetail>("/api/ev/runs/rag-baseline~rag-tpl-w1-mixed")} />)
    const table = screen.getByRole("table", { name: "Evidence per paper" })
    expect(lane(table, /^not in the answer: 4/)).toBeInTheDocument()
    expect(lane(table, /^supports: 2/)).toBeInTheDocument()
    expect(screen.getByRole("table", { name: "Retrieved passages" })).toBeInTheDocument()
    await user.click(within(table).getByRole("button", { name: "S001: show the cited passages" }))
    const sheet = await screen.findByRole("dialog", {}, T)
    const text = await within(sheet).findByRole("region", { name: "Text of S001" }, T)
    expect([...text.querySelectorAll("mark")].some((m) => m.dataset.marks?.startsWith("cited:"))).toBe(true)
  })

  it("on a wide screen the panel sits beside the table and takes the focus; closing returns it", async () => {
    screenWidth(1400)
    const user = userEvent.setup()
    renderWithProviders(<EvidenceView run={determined()} />)
    const table = screen.getByRole("table", { name: "Evidence per paper" })
    const cell = within(table).getByRole("button", { name: /^S001: treatment/ })
    await user.click(cell)
    const panel = await screen.findByRole("complementary", { name: "Source: S001" }, T)
    await waitFor(() => expect(within(panel).getByRole("heading", { level: 3, name: "S001" })).toHaveFocus(), T)
    expect(within(table).getAllByRole("row").find((r) => r.getAttribute("aria-current") === "true")).toHaveTextContent("S001")
    await user.click(within(panel).getByRole("button", { name: "Close the source panel" }))
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument()
    await waitFor(() => expect(cell).toHaveFocus(), T)
  })
})
