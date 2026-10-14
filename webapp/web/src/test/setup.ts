/**
 * Vitest setup, run before every test file: installs vitest's jsdom environment once (see
 * src/test/environment.ts for why it is not the configured environment), gives it the
 * EventSource jsdom lacks (the `eventsource` package, a WHATWG implementation over fetch, so MSW
 * serves the streams as it serves every other request), then registers the per-file hooks of
 * src/test/hooks.ts. Everything that touches the DOM at import time (Testing Library's `screen`)
 * is imported only after the DOM exists.
 */
import { builtinEnvironments } from "vitest/environments"

const scope = globalThis as { __testDomInstalled?: boolean }
if (!scope.__testDomInstalled) {
  await builtinEnvironments.jsdom.setup(globalThis, { jsdom: { url: "http://localhost:5173/" } })
  scope.__testDomInstalled = true
}

if (typeof globalThis.EventSource === "undefined") {
  const { EventSource } = await import("eventsource")
  globalThis.EventSource = EventSource as unknown as typeof globalThis.EventSource
}

const { registerHooks } = await import("./hooks")
registerHooks()
