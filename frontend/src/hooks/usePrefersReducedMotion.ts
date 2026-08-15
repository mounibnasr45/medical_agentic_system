import { useEffect, useState } from 'react'

const QUERY = '(prefers-reduced-motion: reduce)'

/**
 * Tracks the reduced-motion preference.
 *
 * Read as state rather than left to CSS because the monitor's replay is a timer,
 * not an animation: suppressing the transition would still leave lines appearing
 * one by one. When this is true the replay stops advancing on its own.
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => window.matchMedia(QUERY).matches)

  useEffect(() => {
    const media = window.matchMedia(QUERY)
    const update = () => setReduced(media.matches)

    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  return reduced
}
