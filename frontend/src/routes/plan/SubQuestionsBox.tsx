/** The optional sub-questions box on the plan page: one per line, they help draft the plan and are never scored. */
import { Textarea } from "@/components/ui/textarea"

/** Lines trimmed, empty lines dropped. */
// The brief asks for the parser next to the box; it is a plain function the page and its tests import.
// eslint-disable-next-line react-refresh/only-export-components
export function parseSubQuestions(text: string): string[] {
  return text.split("\n").map((line) => line.trim()).filter((line) => line !== "")
}

export function SubQuestionsBox({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <label className="block space-y-1 text-sm font-medium">
      <span>Sub-questions (optional, one per line; they help draft the plan and are never scored)</span>
      <Textarea rows={3} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  )
}
