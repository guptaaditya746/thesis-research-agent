/** The web app never shows OWL or ontology words (D13): not on the pages, and not in the strings the pages are written with. */
import { screen } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { beforeAll, describe, expect, it } from "vitest"

import type { EvRunDetail } from "@/api/ev"
import { routes } from "@/app/routes"
import { evFixture } from "@/mocks/ev"
import { server } from "@/mocks/node"
import { renderRoutes } from "@/test/render"

const T = { timeout: 15_000 }
const MIXED = "rag-tpl-w1-mixed"
const RUN = encodeURIComponent(`cascade-gaps~${MIXED}`)
const JARGON = /\b(owl|ontology|ontologies|class|subclass|superclass|rdf|rdfs|cskg|iri)\b/i

/** The text a user can read in a component's source: JSX text nodes and the string literals given to title,
 *  description, label and aria-label (a regex pass, not a parser; it may miss a string built by code). */
function userStrings(source: string): string[] {
  const out: string[] = []
  for (const m of source.matchAll(/>([^<>{}]+)</g)) out.push(m[1].trim())
  for (const m of source.matchAll(/\b(?:title|description|label|aria-label)\s*[=:]\s*(?:\{\s*)?(?:"([^"]*)"|'([^']*)'|`([^`]*)`)/g)) out.push(m[1] ?? m[2] ?? m[3])
  return out.filter(Boolean)
}

beforeAll(async () => {
  await Promise.all([import("@/pages/ev/ReportPage"), import("@/pages/ev/RunPage")])
}, 180_000)

describe("no ontology words on screen", () => {
  // each path waits for content that only the loaded page has, never for the shell (<main> is there from the start)
  it.each([
    ["/report", () => screen.findByRole("heading", { name: "Report" }, T)],
    [`/runs/${RUN}?tab=dev&dev=graph`, () => screen.findByText(/cascade-gaps \//, {}, T)],
    [`/runs/${RUN}?tab=scores`, () => screen.findByText(/Values linked to the wrong kind of thing/, {}, T)],
  ] as const)("%s shows no ontology words", async (path, loaded) => {
    renderRoutes(routes, path)
    await loaded()
    expect(document.body.textContent ?? "").not.toMatch(JARGON)
  })

  it("the link flags line, with flags set, shows no ontology words", async () => {
    const detail = evFixture<EvRunDetail>(`/api/ev/runs/cascade-gaps~${MIXED}`)
    server.use(http.get(`/api/ev/runs/${RUN}`, () => HttpResponse.json({ ...detail, link_flags: 2 })))
    renderRoutes(routes, `/runs/${RUN}?tab=scores`)
    const line = await screen.findByText(/Values linked to the wrong kind of thing: 2/, {}, T)
    expect(line.textContent ?? "").not.toMatch(JARGON)
    expect(document.body.textContent ?? "").not.toMatch(JARGON)
  })
})

describe("no ontology words in the source strings", () => {
  it("userStrings picks the text a user reads", () => {
    expect(userStrings(`<Card title="Papers" aria-label='Open'>Hello <b>there</b></Card>`)).toEqual(["Hello", "there", "Papers", "Open"])
  })

  it("source strings shown to users carry no ontology words", () => {
    const files = import.meta.glob("/src/{pages,components,lib}/**/*.tsx", { eager: true, query: "?raw", import: "default" })
    expect(Object.keys(files).length).toBeGreaterThan(20)
    for (const [file, text] of Object.entries(files))
      if (!file.includes(".test.")) expect(userStrings(text as string).filter((s) => JARGON.test(s)), file).toEqual([])
  })
})
