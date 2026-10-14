import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeAll, describe, expect, it } from "vitest"

import { routes } from "@/app/routes"
import { RUN } from "@/mocks/fixtures"
import { server } from "@/mocks/node"
import { renderRoutes } from "@/test/render"

beforeAll(async () => {
  await Promise.all([import("./ChatPanel"), import("@/pages/RunPage"), import("@/pages/OverviewPage")])
}, 180_000)

const T = { timeout: 15_000 }

function recordChatBodies() {
  const bodies: unknown[] = []
  server.events.on("request:start", ({ request }) => {
    if (request.url.endsWith("/api/chat")) void request.clone().json().then((body) => bodies.push(body))
  })
  return bodies
}

describe("chat", () => {
  it("is scoped to the run in view, sends its id and shows the streamed reply with the tool call", async () => {
    const bodies = recordChatBodies()
    const user = userEvent.setup()
    renderRoutes(routes, `/runs/${encodeURIComponent(RUN.on)}`)

    await user.click(await screen.findByRole("button", { name: "Ask about this run" }, T))
    // the panel is a lazy chunk: a loading sheet first, then the thread
    const input = await screen.findByRole("textbox", { name: "Message" }, T)
    const sheet = screen.getByRole("dialog", { name: "Chat about runs" })
    expect(within(sheet).getByText(RUN.on)).toBeInTheDocument()

    await user.type(input, "Which facts are unsourced?")
    await user.click(within(sheet).getByRole("button", { name: "Send" }))

    expect(await within(sheet).findByText("Which facts are unsourced?")).toBeInTheDocument()
    expect(await within(sheet).findByText(new RegExp(`\\(mock reply\\) Run ${RUN.on} \\(claim_on, seed 1\\)`), {}, { timeout: 10_000 })).toBeInTheDocument()
    expect(within(sheet).getByText(/get_run\(/)).toBeInTheDocument()
    expect(bodies).toHaveLength(1)
    expect(bodies[0]).toMatchObject({ run_id: RUN.on, trigger: "submit-message" })
    // the reply is Markdown: its table and bold render, its raw HTML does not
    const table = await within(sheet).findByRole("table", {}, { timeout: 10_000 })
    expect(within(table).getByRole("columnheader", { name: "accepted claims" })).toBeInTheDocument()
    expect((await within(sheet).findByText("Read from get_run.", {}, { timeout: 10_000 })).tagName).toBe("STRONG")
    expect(within(sheet).queryByTestId("raw-html")).not.toBeInTheDocument()
    expect(sheet.querySelector("b")).toBeNull()
    server.events.removeAllListeners("request:start")
  })

  it("starts a new thread when another run is in view, so one run's answers never sit in another's thread", async () => {
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, `/runs/${encodeURIComponent(RUN.on)}`)
    await user.click(await screen.findByRole("button", { name: "Ask about this run" }, T))
    const input = await screen.findByRole("textbox", { name: "Message" }, T)
    await user.type(input, "Summarise this run.{Enter}")
    let sheet = screen.getByRole("dialog", { name: "Chat about runs" })
    expect(await within(sheet).findByText(new RegExp(`\\(mock reply\\) Run ${RUN.on}`), {}, { timeout: 10_000 })).toBeInTheDocument()
    await user.click(within(sheet).getByRole("button", { name: "Close" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    await router.navigate(`/runs/${encodeURIComponent(RUN.off)}`)
    await user.click(await screen.findByRole("button", { name: "Ask about this run" }, T))
    sheet = await screen.findByRole("dialog", { name: "Chat about runs" }, T)
    expect(within(sheet).getByText(RUN.off)).toBeInTheDocument()
    expect(within(sheet).queryByText("Summarise this run.")).not.toBeInTheDocument()
    expect(within(sheet).queryByText(/\(mock reply\)/)).not.toBeInTheDocument()
  })

  it("opens from any page with Ctrl+J and is not scoped there", async () => {
    const bodies = recordChatBodies()
    const user = userEvent.setup()
    renderRoutes(routes, "/")
    await screen.findByRole("heading", { name: "Overview" }, T)
    await user.keyboard("{Control>}j{/Control}")
    const input = await screen.findByRole("textbox", { name: "Message" }, T)
    const sheet = screen.getByRole("dialog", { name: "Chat about runs" })
    expect(within(sheet).getByText(/All runs\. Open a run page to ask about one run/)).toBeInTheDocument()
    await user.type(input, "How many runs are there?{Enter}")
    expect(await within(sheet).findByText(/\(mock reply\) There are 6 runs/, {}, { timeout: 10_000 })).toBeInTheDocument()
    expect(bodies[0]).not.toHaveProperty("run_id")
    server.events.removeAllListeners("request:start")
  })
})
