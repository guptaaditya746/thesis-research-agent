/** A CSS media query as React state (false where there is no window, and where jsdom's stub says so). */
import { useSyncExternalStore } from "react"

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query)
      list.addEventListener?.("change", onChange)
      return () => list.removeEventListener?.("change", onChange)
    },
    () => window.matchMedia(query).matches,
    () => false,
  )
}

/** The user asked for less motion: scroll jumps instead of gliding, nothing animates. */
export const useReducedMotion = () => useMediaQuery("(prefers-reduced-motion: reduce)")
