import { useCallback, useSyncExternalStore } from 'react'

type Theme = 'light' | 'dark'

function systemTheme(): Theme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

function currentTheme(): Theme {
  const attr = document.documentElement.getAttribute('data-theme')
  return attr === 'dark' || attr === 'light' ? attr : systemTheme()
}

let listeners: Array<() => void> = []
const notify = () => listeners.forEach((l) => l())

function subscribe(cb: () => void) {
  listeners.push(cb)
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  mq.addEventListener('change', cb)
  return () => {
    listeners = listeners.filter((l) => l !== cb)
    mq.removeEventListener('change', cb)
  }
}

/** Theme state backed by `data-theme` on <html>, persisted to localStorage. */
export function useTheme(): [Theme, () => void] {
  const theme = useSyncExternalStore(subscribe, currentTheme)
  const toggle = useCallback(() => {
    const next: Theme = currentTheme() === 'dark' ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', next)
    try {
      localStorage.setItem('bc-theme', next)
    } catch {
      /* storage unavailable */
    }
    notify()
  }, [])
  return [theme, toggle]
}
