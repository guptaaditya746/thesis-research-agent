import { screen, within } from "@testing-library/react"
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
    server.events.removeAllListeners("request:start")
  })

  it("opens from any page with Ctrl+J and is not scoped there", async () => {
    const bodies = recordChatBodies()
    const user = userEvent.setup()
    renderRoutes(routes, "/")
    await screen.findByRole("heading", { name: "Overview" }, T)
    await user.keyboard("{Control>}j{/Control}")
    const input = await screen.findByRole("textbox", { name: "Message" }, T)
    const sheet = screen.getByRole("dialog", { name: "Chat about runs" })
    expect(within(sheet).getByText(/All runs\. Open a run page to ask about one run\./)).toBeInTheDocument()
    await user.type(input, "How many runs are there?{Enter}")
    expect(await within(sheet).findByText(/\(mock reply\) There are 6 runs/, {}, { timeout: 10_000 })).toBeInTheDocument()
    expect(bodies[0]).not.toHaveProperty("run_id")
    server.events.removeAllListeners("request:start")
  })
})
