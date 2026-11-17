/** The text of a refused request, for the message near a button (400 problems, 409 files, 422 body). */
export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
