/** One card per seed: the plain table of the world, whether it is approved, and the button that changes it. */
import { useState } from "react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import { useApprove, useWorlds, type WorldRow } from "./api"
import { messageOf } from "./messageOf"

export function WorldsTab({ domain }: { domain: string }) {
  const worlds = useWorlds(domain)
  const approve = useApprove(domain)
  const [asking, setAsking] = useState<WorldRow | null>(null)
  const next = asking ? !asking.approved : true
  if (worlds.error) return <Alert variant="destructive"><AlertDescription>{messageOf(worlds.error)}</AlertDescription></Alert>
  if (worlds.data?.length === 0) return <p className="text-sm text-muted-foreground">No worlds for {domain} yet.</p>
  return (
    <div className="space-y-4">
      {approve.error ? <Alert variant="destructive"><AlertDescription>{messageOf(approve.error)}</AlertDescription></Alert> : null}
      {(worlds.data ?? []).map((w) => (
        <Card key={w.seed}>
          <CardHeader className="flex-row items-center justify-between gap-2">
            <CardTitle className="text-base">Seed {w.seed}</CardTitle>
            <div className="flex items-center gap-2">
              {w.problem ? <Badge variant="destructive">Does not load</Badge> : <Badge variant={w.approved ? "default" : "outline"}>{w.approved ? "Approved" : "Not approved"}</Badge>}
              <Button size="sm" variant="outline" disabled={!!w.problem || approve.isPending} onClick={() => setAsking(w)}>
                {w.approved ? "Withdraw approval" : "Approve"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto text-xs">{w.text}</pre>
          </CardContent>
        </Card>
      ))}
      <AlertDialog open={asking !== null} onOpenChange={(open) => { if (!open) setAsking(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{next ? "Approve" : "Withdraw approval of"} seed {asking?.seed}?</AlertDialogTitle>
            <AlertDialogDescription>This decides which worlds can be built.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => { if (asking) approve.mutate({ seed: asking.seed, approved: next }) }}>
              {next ? "Yes, approve" : "Yes, withdraw"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
