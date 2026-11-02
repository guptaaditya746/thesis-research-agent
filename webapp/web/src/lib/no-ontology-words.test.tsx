/** The web app never shows OWL or ontology words (D13): not on the pages, and not in the strings the pages are written with. */
import { screen } from "@testing-library/react"
import { beforeAll, describe, expect, it } from "vitest"

import { routes } from "@/app/routes"
import { renderRoutes } from "@/test/render"

const T = { timeout: 15_000 }
const MIXED = "rag-tpl-w1-mixed"
const RUN = encodeURIComponent(`cascade-gaps~${MIXED}`)
const JARGON = /\b(owl|ontology|ontologies|class|subclass|superclass|rdf|rdfs|cskg|iri)\b/i

/** The text a user can read in a component's source: JSX text nodes and the string literals given to title,
 *  description, label and aria-label (a regex pass, not a parser; it may miss a string built by code). */
export function userStrings(source: string): string[] {
  const out: string[] = []
  for (const m of source.matchAll(/>([^<>{}]+)</g)) out.push(m[1].trim())
  for (const m of source.matchAll(/\b(?:title|description|label|aria-label)\s*[=:]\s*(?:\{\s*)?(?:"([^"]*)"|'([^']*)'|`([^`]*)`)/g)) out.push(m[1] ?? m[2] ?? m[3])
  return out.filter(Boolean)
}

beforeAll(async () => {
  await Promise.all([import("@/pages/ev/ReportPage"), import("@/pages/ev/RunPage")])
}, 180_000)

describe("no ontology words on screen", () => {
  it.each(["/report", `/runs/${RUN}?tab=dev&dev=graph`, `/runs/${RUN}?tab=scores`])("%s shows no ontology words", async (path) => {
    renderRoutes(routes, path)
    await screen.findByRole("main", {}, T)
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
