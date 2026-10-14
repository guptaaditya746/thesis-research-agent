/**
 * In mock mode (`npm run dev:mock`, VITE_MOCK=1) every response is MSW fixture data (src/mocks),
 * including a complete, significant mock report: a banner on every page says so, so no screenshot
 * or demo of the mock server passes for a thesis result. The production build has no mocks.
 */
import { FlaskConicalIcon } from "lucide-react"

export function MockBanner() {
  if (import.meta.env.VITE_MOCK !== "1") return null
  return (
    <div
      role="note"
      aria-label="Mock data"
      className="flex items-center justify-center gap-2 border-b border-status-warning/50 bg-status-warning/15 px-4 py-1.5 text-center text-xs font-medium"
    >
      <FlaskConicalIcon className="size-3.5 shrink-0 text-status-warning" aria-hidden="true" />
      Mock data (npm run dev:mock): every number on these pages is a fixture, not a result.
    </div>
  )
}
