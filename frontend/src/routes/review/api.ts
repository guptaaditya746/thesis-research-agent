/**
 * The review API (/api/ev/review, webapp/evreview.py): worlds, answer sheets and the judge test. Types are
 * written by hand from the backend's answers. The judge-test answers carry no system name and no judge marks (the
 * hand marking is blind), so no type here has a field for them.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { getJson, putJson } from "@/api/client"

export interface ReviewDomain {
  domain: string
  questions: number | null
  seeds: number[]
  worlds: number[]
  /** a spec file that does not load: why */
  error?: string
}

export interface WorldRow {
  seed: number
  approved: boolean | null
  text: string
  path: string
  /** a world file that does not load: why */
  problem?: string
}

export interface QueueRow {
  seed: number
  question_id: string
  status: "drafted" | "checked" | "missing"
  stale: string | null
  must_check: "full" | "sample" | null
}

export interface FactLine {
  id: string
  text: string
}

export interface PointIn {
  text: string
  facts: string[]
}

export interface Scope {
  arms: string[]
  measures: string[]
  conditions: string[]
  settings: string[]
}

export interface SheetView {
  question: string
  sub_questions: string[]
  scope: Scope
  facts: FactLine[]
  sheet: { status: "drafted" | "checked"; points: { id: string; text: string; facts: string[] }[]; warnings: string[]; checked_by: string | null } | null
  stale: string | null
}

export interface JudgeRow {
  n: number
  domain?: string
  seed?: number
  question_id?: string
  done: boolean
  /** a broken row of sample.json: why */
  problem?: string
}

export interface JudgeItem {
  n: number
  domain: string
  seed: number
  question_id: string
  question: string | null
  answer: string
  points: { id: string; text: string }[]
  facts: { n: number; paper: string; quote: string }[]
  facts_cut: boolean
  marked: { points: Record<string, boolean>; faithful: boolean | null } | null
}

export interface HandMark {
  points: Record<string, boolean>
  faithful: boolean | null
}

const root = "/api/ev/review"
const seg = encodeURIComponent

export const useOverview = () => useQuery({ queryKey: ["review"], queryFn: () => getJson<{ domains: ReviewDomain[] }>(root) })

export const useWorlds = (domain: string) =>
  useQuery({ queryKey: ["review", domain, "worlds"], queryFn: () => getJson<WorldRow[]>(`${root}/${seg(domain)}/worlds`) })

export function useApprove(domain: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ seed, approved }: { seed: number; approved: boolean }) => putJson<WorldRow>(`${root}/${seg(domain)}/worlds/${seed}`, { approved }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["review", domain, "worlds"] }),
  })
}

export const useQueue = (domain: string) =>
  useQuery({ queryKey: ["review", domain, "sheets"], queryFn: () => getJson<QueueRow[]>(`${root}/${seg(domain)}/sheets`) })

export const useSheet = (domain: string, seed: number, qid: string) =>
  useQuery({ queryKey: ["review", domain, "sheet", seed, qid], queryFn: () => getJson<SheetView>(`${root}/${seg(domain)}/sheets/${seed}/${seg(qid)}`) })

export function useSaveSheet(domain: string, seed: number, qid: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (points: PointIn[]) => putJson<unknown>(`${root}/${seg(domain)}/sheets/${seed}/${seg(qid)}`, { points }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["review", domain] }),
  })
}

export const useJudgeList = () => useQuery({ queryKey: ["review", "judge-test"], queryFn: () => getJson<JudgeRow[]>(`${root}/judge-test`) })

export const useJudgeItem = (n: number) =>
  useQuery({ queryKey: ["review", "judge-test", n], queryFn: () => getJson<JudgeItem>(`${root}/judge-test/${n}`) })

export function useSaveMark(n: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (mark: HandMark) => putJson<unknown>(`${root}/judge-test/${n}`, mark),
    onSuccess: () => client.invalidateQueries({ queryKey: ["review", "judge-test"] }),
  })
}
