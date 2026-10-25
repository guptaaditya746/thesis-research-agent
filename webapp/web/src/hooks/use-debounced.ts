import { useEffect, useState } from "react"

/** `value`, but only once it has stopped changing for `ms` (the first value is returned at once). */
export function useDebounced<T>(value: T, ms: number): T {
  const [held, setHeld] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setHeld(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return held
}
