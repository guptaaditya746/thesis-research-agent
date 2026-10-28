/**
 * One paper's text with what the draft would pick up in it (GET /proposals/{name}/preview): the screen terms,
 * the frame's names and the method kinds, marked in place, each with the card it comes from.
 */
import { useState, type ReactNode } from "react"

import { useCorpora, useCorpus, usePreview, type PreviewHit } from "@/api/ev"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

/** The text cut at the hits: `<mark>` per hit, the first of two overlapping hits wins. */
export function Highlighted({ text, hits }: { text: string; hits: PreviewHit[] }) {
  const parts: ReactNode[] = []
  let at = 0
  for (const h of [...hits].sort((a, b) => a.start - b.start)) {
    if (h.start < at || h.end > text.length || h.end <= h.start) continue
    if (h.start > at) parts.push(text.slice(at, h.start))
    parts.push(<mark key={`${h.start}-${h.card}`} title={`${h.card}: ${h.what}`} className="rounded-sm bg-primary/20 px-0.5 text-foreground">{text.slice(h.start, h.end)}</mark>)
    at = h.end
  }
  parts.push(text.slice(at))
  return <>{parts}</>
}

export function PaperPreview({ proposal }: { proposal: string }) {
  const [corpus, setCorpus] = useState<string | null>(null)
  const [paper, setPaper] = useState<string | null>(null)
  const corpora = useCorpora()
  const detail = useCorpus(corpus ?? "")
  const preview = usePreview(proposal, corpus, paper)
  return (
    <section aria-label="Paper preview" className="space-y-3 rounded-lg border p-3">
      <h3 className="text-sm font-semibold">Paper preview</h3>
      <div className="flex flex-wrap gap-3">
        <div className="grid min-w-40 flex-[2] gap-1">
          <Label htmlFor="preview-corpus" className="text-xs">Corpus</Label>
          <Select value={corpus ?? undefined} onValueChange={(c) => { setCorpus(c); setPaper(null) }}>
            <SelectTrigger id="preview-corpus" aria-label="Corpus" className="w-full"><SelectValue placeholder="choose a corpus" /></SelectTrigger>
            <SelectContent>{(corpora.data ?? []).map((c) => <SelectItem key={c.name} value={c.name}>{c.name}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="grid min-w-24 flex-1 gap-1">
          <Label htmlFor="preview-paper" className="text-xs">Paper</Label>
          <Select value={paper ?? undefined} onValueChange={setPaper} disabled={!detail.data}>
            <SelectTrigger id="preview-paper" aria-label="Paper" className="w-full"><SelectValue placeholder="paper" /></SelectTrigger>
            <SelectContent>{(detail.data?.papers_list ?? []).map((p) => <SelectItem key={p.id} value={p.id}>{p.id}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>
      {preview.isError && <p role="alert" className="text-xs text-destructive">The preview failed: {preview.error instanceof Error ? preview.error.message : "unknown error"}</p>}
      {preview.data && (
        <>
          <p className="text-xs text-muted-foreground">{preview.data.hits.length} hit(s) of the draft's terms and names.</p>
          <div className="max-h-96 overflow-auto whitespace-pre-wrap text-sm leading-relaxed"><Highlighted text={preview.data.text} hits={preview.data.hits} /></div>
        </>
      )}
      {!preview.data && !preview.isError && (paper && preview.isFetching
        ? <p className="text-xs text-muted-foreground" role="status">Loading paper {paper}…</p>
        : <p className="text-xs text-muted-foreground">Choose a corpus and a paper to see what the draft picks up.</p>)}
    </section>
  )
}
