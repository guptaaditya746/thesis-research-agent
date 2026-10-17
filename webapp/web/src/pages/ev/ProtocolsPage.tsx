/**
 * Protocol `/protocol`: the hand-written protocols of the repository (evidence/protocols, version 2) and the
 * proposals of the proposal flow (`evidence propose`, Part E: an optional, LLM-drafted protocol a person
 * decides; nothing runs one automatically).
 */
import { FileCode2Icon } from "lucide-react"
import { Link } from "react-router"

import { useProposals, useProtocols } from "@/api/ev"
import { PageHeader } from "@/components/layout/PageHeader"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function ProtocolsPage() {
  const protocols = useProtocols()
  const proposals = useProposals()
  return (
    <div className="space-y-6">
      <PageHeader title="Protocol" description="The executable research protocol: which evidence, how it is extracted, how it is connected and how it is synthesised. Hand-written now; the proposal flow drafts one with the user." />
      <section className="space-y-3">
        <h2 className="text-base font-semibold">Hand-written</h2>
        {protocols.isPending && <TableSkeleton rows={2} />}
        {protocols.isError && <ErrorState error={protocols.error} />}
        <div className="grid gap-4 md:grid-cols-2">
          {protocols.data?.map((p) => (
            <Card key={p.name} className="relative">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileCode2Icon className="size-4" aria-hidden="true" />
                  <Link to={`/protocol/${encodeURIComponent(p.name)}`} className="font-mono hover:underline after:absolute after:inset-0">{p.name}</Link>
                  {p.version && <Badge variant="secondary">version {p.version}</Badge>}
                  {p.error && <Badge variant="destructive">does not validate</Badge>}
                </CardTitle>
                <CardDescription>{p.question ?? p.error}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>
      <section className="space-y-3">
        <h2 className="text-base font-semibold">Proposals</h2>
        {proposals.isError && <ErrorState error={proposals.error} />}
        {proposals.data && !proposals.data.length && (
          <EmptyState title="No proposals" description="Nothing under the proposals root ($EV_PROPOSALS, default $EV/proposals). Run `uv run evidence propose frame ...`." />
        )}
        <div className="grid gap-4 md:grid-cols-2">
          {proposals.data?.map((p) => (
            <Card key={p.name} className="relative">
              <CardHeader>
                <CardTitle className="flex flex-wrap items-center gap-2 text-base">
                  <Link to={`/proposals/${encodeURIComponent(p.name)}`} className="font-mono hover:underline after:absolute after:inset-0">{p.name}</Link>
                  <Badge variant={p.frozen ? "secondary" : "outline"}>{p.frozen ? `frozen, revision ${p.revision ?? 1}` : `at ${p.steps.at(-1) ?? "—"}`}</Badge>
                  {p.amendments > 0 && <Badge variant="outline">{p.amendments} amendment{p.amendments > 1 ? "s" : ""}</Badge>}
                </CardTitle>
                <CardDescription>{p.question}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>
    </div>
  )
}
