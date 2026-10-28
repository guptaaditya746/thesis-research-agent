/**
 * The evidence table's column sets for inventory, consistency and best: each answer on the fixture run (its
 * graph.json and paper S001 are in src/mocks/ev-fixtures.json), each kind's lanes, and a click opening S001
 * with the clicked item's span marked. jsdom is a narrow screen: the source panel is a sheet.
 */
import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import type { EvRunDetail, RunAnswer } from "@/api/ev"
import { evFixture } from "@/mocks/ev"
import { renderWithProviders } from "@/test/render"

import { EvidenceView } from "./EvidenceView"

const T = { timeout: 15_000 }
// items of S001 in the fixture run's graph
const RAG = "c-51d752c251545ddc"          // condition "retrieval-augmented" (rag)
const BASELINE = "c-15b4f5c688653232"     // condition "closed-book model" (baseline)
const VALUE = "m-794d268457cdf26b"        // measurement 0.572 on factual_accuracy
const CLAIM = "a-cba50be387556ca7"        // author claim no_effect

const withAnswer = (answer: RunAnswer): EvRunDetail => ({ ...structuredClone(evFixture<EvRunDetail>("/api/ev/runs/cascade~rag-tpl-w1-explicit")), answer })

/** The sheet's paper text, once loaded, and whether `item`'s spans are the selected ones. */
async function markedIn(item: string) {
  const sheet = await screen.findByRole("dialog", {}, T)
  const text = await within(sheet).findByRole("region", { name: "Text of S001" }, T)
  const marks = [...text.querySelectorAll("mark")].filter((m) => (m.dataset.marks ?? "").split(" ").includes(item))
  return { sheet, marks, pressed: marks.length > 0 && marks.every((m) => m.getAttribute("aria-pressed") === "true") }
}

describe("evidence table by question kind", () => {
  it("inventory: a row per name, its papers open the paper on its items", async () => {
    const user = userEvent.setup()
    renderWithProviders(<EvidenceView run={withAnswer({ kind: "inventory", system: "evidence-engine", target: "condition", entries: [
      { name: "retrieval-augmented", aliases: ["RAG"], papers: ["S001", "S002"], items: [RAG] },
      { name: "closed-book model", aliases: [], papers: ["S001"], items: [BASELINE] },
    ] })} />)
    expect(screen.getByText("2 distinct condition names")).toBeInTheDocument()
    expect(screen.getByText(/Named in 2 of 6 papers; 4 papers name none/)).toBeInTheDocument()
    const table = screen.getByRole("table", { name: "Inventory" })
    expect(within(within(table).getByRole("rowgroup", { name: /^in several papers: 1/ })).getByText("retrieval-augmented")).toBeInTheDocument()
    expect(within(table).getByRole("rowgroup", { name: /^in one paper: 1/ })).toBeInTheDocument()
    expect(screen.getByRole("region", { name: "Papers that name none" })).toHaveTextContent("S003")
    await user.click(within(table).getByRole("button", { name: "closed-book model in S001: show in the paper" }))
    const { pressed, marks } = await markedIn(BASELINE)
    expect(marks.length).toBeGreaterThan(0)
    expect(pressed).toBe(true)
  })

  it("consistency: what the paper says against its numbers, in agree / disagree lanes", async () => {
    const user = userEvent.setup()
    renderWithProviders(<EvidenceView run={withAnswer({ kind: "consistency", system: "evidence-engine", metric: "factual_accuracy",
      agreeing: ["S001"], disagreeing: ["S002"], undetermined: ["S003"],
      studies: [
        { document: "S001", claim: "neutral", direction: "neutral", agrees: true, reason: null },
        { document: "S002", claim: "supports", direction: "contradicts", agrees: false, reason: null },
        { document: "S003", claim: null, direction: "undetermined", agrees: null, reason: { code: "no_claim", text: "no author claim found" } },
      ] })} />)
    expect(screen.getByText("1 agree, 1 disagree")).toBeInTheDocument()
    const table = screen.getByRole("table", { name: "Claims against numbers" })
    expect(within(table).getByRole("rowgroup", { name: /^agrees: 1/ })).toHaveTextContent("S001")
    expect(within(table).getByRole("rowgroup", { name: /^disagrees: 1/ })).toHaveTextContent("S002")
    expect(within(table).getByRole("rowgroup", { name: /^undetermined: 1/ })).toHaveTextContent("no author claim found")
    expect(within(table).getByRole("rowgroup", { name: /^not in the answer: 3/ })).toBeInTheDocument()
    await user.click(within(table).getByRole("button", { name: "S001: the author claim, show in the paper" }))
    expect((await markedIn(CLAIM)).pressed).toBe(true)
  })

  it("best: a column per method kind, the winner marked, wins per kind as the total row", async () => {
    const user = userEvent.setup()
    renderWithProviders(<EvidenceView run={withAnswer({ kind: "best", system: "evidence-engine", metric: "factual_accuracy", wins: { rag: 1 }, winner: "rag", tied: [],
      studies: [
        { document: "S001", winner: "rag", tied: [], values: { rag: 0.572, plain: 0.564 }, reason: null },
        { document: "S002", winner: null, tied: ["plain", "rag"], values: { rag: 0.7, plain: 0.7 }, reason: null },
        { document: "S003", winner: null, tied: [], values: {}, reason: { code: "too_few_kinds", text: "conditions of fewer than two method kinds found" } },
      ] })} />)
    expect(screen.getByText("best: rag")).toBeInTheDocument()
    const table = screen.getByRole("table", { name: "Winner per paper" })
    expect(within(table).getByRole("columnheader", { name: /^rag/ })).toBeInTheDocument()
    expect(within(table).getByRole("columnheader", { name: /^plain/ })).toBeInTheDocument()
    expect(within(table).getByRole("rowgroup", { name: /^tie: 1/ })).toHaveTextContent("tie: plain, rag")
    expect(within(table).getByRole("rowgroup", { name: /^undetermined: 1/ })).toHaveTextContent("fewer than two method kinds")
    const total = within(table).getByRole("rowheader", { name: "papers won" }).closest("tr")!
    expect(total).toHaveTextContent("overall: rag")
    await user.click(await within(table).findByRole("button", { name: "S001: rag 0.572, the top value, show in the paper" }, T))
    expect((await markedIn(VALUE)).pressed).toBe(true)
  })
})
