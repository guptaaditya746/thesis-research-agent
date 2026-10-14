/** The run page in view, for the chat's request body (kept apart from the AI SDK so it loads eagerly). */
let runInView: string | null = null

export function setChatRun(runId: string | null) {
  runInView = runId
}

export function chatBody(): Record<string, string> {
  return runInView ? { run_id: runInView } : {}
}
