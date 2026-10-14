/**
 * Claims tab: every claim of the run, accepted (with the exact quote anchored in the corpus) or
 * rejected (with the broker's reason and the quote as the agent sent it); an accepted one opens
 * its walk.
 */
import { CheckIcon, FootprintsIcon, XIcon } from "lucide-react"
import { useState } from "react"

import { useClaims } from "@/api/hooks"
import type { Answer, Claim } from "@/api/types"
import { StatusBadge } from "@/components/badges"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { factsByClaim, term } from "@/lib/facts"

import { useWalk, walkTargetForClaims } from "./walk-context"

type Filter = "all" | "accepted" | "rejected"

const matches = (c: Claim, text: string) =>
  !text || [c.claim_id, term(c.s), term(c.p), term(c.o), c.file, c.quote, c.reason, c.agent_id].some((v) => v?.toLowerCase().includes(text))

export function ClaimsTab({ runId, answer, live }: { runId: string; answer: Answer | null; live: boolean }) {
  const claims = useClaims(runId, { live })
  const { open } = useWalk()
  const [filter, setFilter] = useState<Filter>("all")
  const [search, setSearch] = useState("")

  if (claims.isPending) return <TableSkeleton rows={8} columns={7} />
  if (claims.isError) return <ErrorState error={claims.error} onRetry={() => void claims.refetch()} />
  if (claims.data.length === 0) {
    return (
      <EmptyState
        title="No claims"
        description={live ? "Claims appear as the agent records them (this list refreshes every few seconds)." : "The run recorded no claims (claim off without attach, or the agent never claimed)."}
      />
    )
  }

  const cited = factsByClaim(answer)
  const text = search.trim().toLowerCase()
  const rows = claims.data.filter((c) => (filter === "all" || c.status === filter) && matches(c, text))
  const accepted = claims.data.filter((c) => c.status === "accepted").length

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3" role="search" aria-label="Filter claims">
        <div className="space-y-1">
          <Label htmlFor="claims-status" className="text-xs text-muted-foreground">Status</Label>
          <Select value={filter} onValueChange={(v) => setFilter(v as Filter)}>
            <SelectTrigger id="claims-status" className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All ({claims.data.length})</SelectItem>
              <SelectItem value="accepted">Accepted ({accepted})</SelectItem>
              <SelectItem value="rejected">Rejected ({claims.data.length - accepted})</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="claims-search" className="text-xs text-muted-foreground">Search</Label>
          <Input id="claims-search" type="search" className="w-64" placeholder="claim id, triple, file, quote" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <p className="pb-2 text-xs text-muted-foreground" role="status">{rows.length} of {claims.data.length} claims</p>
      </div>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Claim</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Triple</TableHead>
              <TableHead>File</TableHead>
              <TableHead>Quote</TableHead>
              <TableHead className="text-right">Step</TableHead>
              <TableHead>Agent · origin</TableHead>
              <TableHead>Cited by</TableHead>
              <TableHead><span className="sr-only">Walk</span></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((c) => (
              <TableRow key={c.task_id}>
                <TableCell className="font-mono text-xs">{c.claim_id ?? "—"}</TableCell>
                <TableCell>
                  {c.status === "accepted" ? (
                    <StatusBadge tone="good" icon={<CheckIcon />}>accepted</StatusBadge>
                  ) : (
                    <StatusBadge tone="critical" icon={<XIcon />} title="the broker's rejection reason">{c.reason ?? "rejected"}</StatusBadge>
                  )}
                </TableCell>
                <TableCell className="max-w-56 font-mono text-xs whitespace-normal">({term(c.s)}, {term(c.p)}, {term(c.o)})</TableCell>
                <TableCell className="font-mono text-xs">{c.file ?? "—"}</TableCell>
                <TableCell className="max-w-72 text-xs whitespace-normal">
                  {c.quote ? <span className="line-clamp-2" title={c.quote}>“{c.quote}”</span> : "—"}
                  {c.status === "rejected" && c.quote && <span className="text-muted-foreground"> (as sent)</span>}
                </TableCell>
                <TableCell className="text-right tabular-nums">{c.step}</TableCell>
                <TableCell className="text-xs">{c.agent_id} · {c.origin}</TableCell>
                <TableCell className="font-mono text-xs">{c.claim_id ? (cited.get(c.claim_id)?.map((r) => r.fact.id).join(", ") ?? "—") : "—"}</TableCell>
                <TableCell>
                  {c.status === "accepted" && c.claim_id && (
                    <Button
                      variant="ghost"
                      size="xs"
                      aria-label={`Walk ${c.claim_id}`}
                      onClick={() => open(walkTargetForClaims([c.claim_id!], answer))}
                    >
                      <FootprintsIcon data-icon="inline-start" />
                      Walk
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {rows.length === 0 && <p className="p-4 text-center text-sm text-muted-foreground">No claim matches.</p>}
      </div>
    </div>
  )
}
