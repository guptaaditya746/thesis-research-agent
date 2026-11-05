/**
 * "Fetch from arXiv": real papers for a typed query as a demonstration corpus (`evidence fetch`, POST
 * /api/ev/jobs/fetch; evidence/arxiv.py). The job downloads each paper's PDF from the arXiv API (one request
 * every three seconds) and converts it to Markdown; the corpus appears under the corpora root as
 * `arxiv-<slug>-<yyyymmdd>`. Real papers have no ground truth, so the corpus is shown with a demo badge and a
 * run on it is never scored (DemoScoreNote; the backend refuses Score too).
 */
import { DownloadIcon } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router"

import { useStartJob, type CorpusSummary, type FetchRequest, type Job } from "@/api/ev"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { announceError, announceJob } from "@/lib/toasts"

const MAX_PAPERS = 50   // webapp/evmodels.py FetchRequest
const CATEGORY = /^[a-z][a-z-]*(\.[A-Za-z][A-Za-z-]*)?$/

/** "no ground truth, demo" beside a corpus of real papers (source.json `ground_truth: false`). */
export function DemoBadge({ corpus }: { corpus: Pick<CorpusSummary, "ground_truth"> | undefined }) {
  if (corpus?.ground_truth !== false) return null
  return <Badge variant="outline" className="ml-1" title="real papers from arXiv: nobody knows the right answer, so runs on it are not scored">no ground truth, demo</Badge>
}

/** Why a run on a demonstration corpus has no Score button. */
export function DemoScoreNote({ corpus }: { corpus: string }) {
  return (
    <p className="text-xs text-muted-foreground" role="note">
      <strong className="font-medium text-foreground">Demonstration corpus, no ground truth:</strong> <span className="font-mono">{corpus}</span> holds
      real papers from arXiv, so its runs are not scored. Read the graph, the answer and the trace, and check a few papers by hand.
    </p>
  )
}

export function ArxivFetchDialog({ onStarted }: { onStarted?: (job: Job) => void }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [max, setMax] = useState("10")
  const [category, setCategory] = useState("")
  const start = useStartJob("fetch")
  const navigate = useNavigate()
  const n = Number(max)
  const maxOk = Number.isInteger(n) && n >= 1 && n <= MAX_PAPERS
  const categoryOk = !category.trim() || CATEGORY.test(category.trim())
  const queryOk = query.trim().length >= 3 && /\w/.test(query)
  const ok = queryOk && maxOk && categoryOk
  const submit = () => {
    const body: FetchRequest = { query: query.trim(), max_papers: n, category: category.trim() || null, name: null }
    start.mutate(body, {
      onSuccess: (job) => {
        announceJob(job, navigate)
        setOpen(false)
        onStarted?.(job)
      },
      onError: (err) => announceError("The arXiv fetch did not start", err),
    })
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <DownloadIcon data-icon="inline-start" />
          Fetch from arXiv
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Fetch real papers from arXiv</DialogTitle>
          <DialogDescription>
            A demonstration: real papers have no ground truth, so runs on this corpus are shown but not scored.
            The papers are downloaded from the arXiv API, one request every three seconds.
          </DialogDescription>
        </DialogHeader>
        <form id="arxiv-fetch" className="space-y-4" aria-label="Fetch from arXiv" onSubmit={(e) => { e.preventDefault(); if (ok) submit() }}>
          <div className="grid gap-1.5">
            <Label htmlFor="arxiv-query">Search words</Label>
            <Input id="arxiv-query" placeholder="a few words of your topic" value={query} onChange={(e) => setQuery(e.target.value)}
              aria-describedby="arxiv-query-hint" />
            <p id="arxiv-query-hint" className="text-xs text-muted-foreground">Every word must appear in the paper's arXiv record.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="grid content-start gap-1.5">
              <Label htmlFor="arxiv-max">Papers</Label>
              <Input id="arxiv-max" type="number" className="w-28" min={1} max={MAX_PAPERS} value={max} onChange={(e) => setMax(e.target.value)}
                aria-invalid={!maxOk} aria-describedby="arxiv-max-hint" />
              <p id="arxiv-max-hint" className={maxOk ? "text-xs text-muted-foreground" : "text-xs text-destructive"}>1 to {MAX_PAPERS}</p>
            </div>
            <div className="grid content-start gap-1.5">
              <Label htmlFor="arxiv-category">Category (optional)</Label>
              <Input id="arxiv-category" className="w-36 font-mono" placeholder="cs.CL" value={category} onChange={(e) => setCategory(e.target.value)}
                aria-invalid={!categoryOk} aria-describedby="arxiv-category-hint" />
              <p id="arxiv-category-hint" className={categoryOk ? "text-xs text-muted-foreground" : "text-xs text-destructive"}>An arXiv category, e.g. cs.CL</p>
            </div>
          </div>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
          <Button type="submit" form="arxiv-fetch" disabled={!ok || start.isPending}>Fetch papers</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
