/**
 * A controlled variant's shift `/report/shifts/:id` (evaluate shift, F3/F4; the supervisor's §6): one study's
 * result was changed and only its paper rewritten; per system, did the changed study's direction and the
 * label move as the variant predicts?
 */
import { CheckCircle2Icon, OctagonXIcon } from "lucide-react"
import { useParams } from "react-router"

import { useShift } from "@/api/ev"
import { StatusBadge } from "@/components/badges"
import { DirectionBadge, JsonBlock, KeyValues, LabelBadge, QueryPage, SystemBadge } from "@/components/ev/bits"
import { PageHeader } from "@/components/layout/PageHeader"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { num } from "@/lib/format"

type Side = { from?: string; to?: string; before?: string; after?: string; before_correct?: boolean; after_correct?: boolean }
type Label = Side & { expected_before?: string; expected_after?: string; changed?: boolean }
type System = { system: string; direction: Side; label: Label; shifted_as_expected: boolean }

export default function ShiftPage() {
  const { id = "" } = useParams()
  const shift = useShift(id)
  return (
    <QueryPage query={shift} what={`shift ${id}`} back={{ to: "/report", label: "Report" }}>
      {({ ref, shift: s, markdown }) => {
        const systems = (s.systems ?? []) as System[]
        const expected = (s.expected ?? {}) as { before?: { label?: string }; after?: { label?: string } }
        return (
          <div className="space-y-6">
            <PageHeader title={<span className="font-mono">{ref.id.replace("~", " / ")}</span>}
              description={`Study ${String(s.study)} (paper ${String(s.paper)}): ${String(s.from)} → ${String(s.to)}.`} />
            <KeyValues items={[
              ["base corpus", <span key="b" className="font-mono text-xs">{String(s.base_corpus_id)}</span>],
              ["variant corpus", <span key="v" className="font-mono text-xs">{String(s.corpus_id)}</span>],
              ["changed values", ((s.changed ?? []) as Record<string, unknown>[]).map((c) => `${String(c.measurement)}: ${num(c.from as number, 3)} → ${num(c.to as number, 3)}`).join("; ") || "—"],
              ["expected label", `${expected.before?.label ?? "?"} → ${expected.after?.label ?? "?"} (${s.label_changes ? "changes" : "does not change"})`],
            ]} />
            <div className="overflow-auto rounded-md border">
              <Table aria-label="Shift per system">
                <TableHeader>
                  <TableRow>{["system", "study before", "study after", "label before", "label after", "shifted as expected"].map((h) => <TableHead key={h} className="text-xs">{h}</TableHead>)}</TableRow>
                </TableHeader>
                <TableBody>
                  {systems.map((x) => (
                    <TableRow key={x.system}>
                      <TableCell><SystemBadge system={x.system} /></TableCell>
                      <TableCell><DirectionBadge direction={x.direction.before} title={`expected ${x.direction.from}`} /></TableCell>
                      <TableCell><DirectionBadge direction={x.direction.after} title={`expected ${x.direction.to}`} /></TableCell>
                      <TableCell><LabelBadge label={x.label.before} correct={x.label.before_correct} /></TableCell>
                      <TableCell><LabelBadge label={x.label.after} correct={x.label.after_correct} /></TableCell>
                      <TableCell>
                        {x.shifted_as_expected
                          ? <StatusBadge tone="good" icon={<CheckCircle2Icon />}>yes</StatusBadge>
                          : <StatusBadge tone="critical" icon={<OctagonXIcon />}>no</StatusBadge>}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {((s.unmatched_systems ?? []) as string[]).length > 0 && (
              <p className="text-sm text-muted-foreground">Scored in only one of the two reports: {(s.unmatched_systems as string[]).join(", ")}.</p>
            )}
            {markdown && <details><summary className="cursor-pointer text-sm">shift.md</summary><JsonBlock value={markdown} className="mt-1" /></details>}
          </div>
        )
      }}
    </QueryPage>
  )
}
