/** The Workbench Domain menu: one entry per field, with its locked hold-out set as a Set choice. */
const HOLDOUT = "_holdout"
/** One menu entry per field: "medical_holdout" is the locked test set of "medical", so it is a set choice, not a domain. */
export function groupDomains(all: string[]): { base: string; holdout: string | null }[] {
  return all.filter((d) => !(d.endsWith(HOLDOUT) && all.includes(d.slice(0, -HOLDOUT.length))))
    .map((d) => ({ base: d, holdout: all.includes(d + HOLDOUT) ? d + HOLDOUT : null }))
}
