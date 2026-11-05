/**
 * The cards form's state per card and what it sends (DecisionEntry, the PUT body of
 * /api/ev/proposals/{name}/decisions), apart from the form so it can be tested on its own.
 */
import type { Card, DecisionEntry } from "@/api/ev"

export const CUSTOM = "custom"

export interface CardState {
  choice: string
  /** the custom value as JSON text (used with choice custom) */
  custom: string
  reason: string
  /** who decided: `model` (the default as it stands), the name in decisions.yaml (kept), or the app's user */
  by: string
}

export function optionValue(card: Card, id: string): unknown {
  return card.options.find((o) => String(o.id) === id)?.value
}

/** The form's starting point: the decision in decisions.yaml, else the model's default. */
export function initialState(card: Card): CardState {
  const d = card.decision
  const choice = d?.choice ?? card.default ?? "draft"
  const value = choice === CUSTOM ? d?.value : optionValue(card, choice)
  return {
    choice,
    custom: JSON.stringify(value ?? optionValue(card, card.default ?? "draft") ?? {}, null, 2),
    reason: d?.reason ?? `default: ${card.rationale ?? ""}`,
    by: d?.by ?? "model",
  }
}

/** What the form would send, and the problem it finds itself (an empty reason, custom JSON that does not parse). */
export function toEntry(card: Card, s: CardState): { entry: DecisionEntry; error: string | null } {
  const entry: DecisionEntry = { card: card.id, choice: s.choice, reason: s.reason, by: s.by, value: null }
  if (!s.reason.trim()) return { entry, error: "a reason is required" }
  if (s.choice === CUSTOM) {
    try {
      entry.value = JSON.parse(s.custom) as unknown
    } catch {
      return { entry, error: "the custom value is not JSON" }
    }
  }
  return { entry, error: null }
}

/** The cards the agent marks `advanced` (cascade, locate): the form folds them away. */
export const advancedCard = (card: Card): boolean => card["advanced"] === true
