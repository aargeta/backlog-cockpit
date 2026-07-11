import { useEffect, useState } from 'react'
import { animate, useReducedMotion } from 'framer-motion'

/** Counts from 0 up to `target` on mount. Respects prefers-reduced-motion. */
export function useCountUp(target: number, duration = 0.7): number {
  const reduced = useReducedMotion()
  const [value, setValue] = useState(reduced ? target : 0)

  useEffect(() => {
    if (reduced) {
      setValue(target)
      return
    }
    const controls = animate(0, target, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setValue(Math.round(v)),
    })
    return () => controls.stop()
  }, [target, duration, reduced])

  return value
}
