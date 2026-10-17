/**
 * MSW handlers of the evidence-level viewer (/api/ev): the backend's own responses on a world made by the
 * real tools (webapp/tests/evidence_world.py: synth, evidence run, evaluate, evidence propose, with scripted
 * models), dumped by path into ev-fixtures.json:
 *
 *     uv run python -m webapp.tests.evidence_world /tmp/ev-world --mocks webapp/web/src/mocks/ev-fixtures.json
 *
 * Read-only like the backend: a path in the file is answered with its response, any other with the
 * backend's 404 shape. The world's directory reads as /srv/ev.
 */
import { http, HttpResponse } from "msw"

import fixtures from "./ev-fixtures.json"

export const EV_FIXTURES = fixtures as Record<string, unknown>

/** The response the backend gave for `path` (e.g. "/api/ev/runs"), typed by the caller. */
export function evFixture<T>(path: string): T {
  if (!(path in EV_FIXTURES)) throw new Error(`not in the mock fixtures: ${path}`)
  return EV_FIXTURES[path] as T
}

export const evHandlers = [
  http.get("/api/ev/*", ({ request }) => {
    const path = decodeURIComponent(new URL(request.url).pathname)
    return path in EV_FIXTURES
      ? HttpResponse.json(EV_FIXTURES[path] as Record<string, unknown>)
      : HttpResponse.json({ detail: `not in the mock fixtures: ${path}` }, { status: 404 })
  }),
]
