import type { ConceptBrief } from "@/api/types"

/** A brief's measure as one line: "list Dataset, per Paper, highest first, top 10". */
export function measureText(m: ConceptBrief["measure"]): string {
  const parts = [`${m.operation} ${m.of}`]
  if (m.group_by) parts.push(`per ${m.group_by}`)
  if (m.filter) parts.push(`where ${m.filter}`)
  if (m.order) parts.push(m.order === "desc" ? "highest first" : "lowest first")
  if (m.limit) parts.push(`top ${m.limit}`)
  return parts.join(", ")
}
