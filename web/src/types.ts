export type Kind =
  | 'not_sent'
  | 'gate'
  | 'decision'
  | 'deferred'
  | 'parked'
  | 'awaiting'
  | 'next'
  | 'todo'

export interface Item {
  kind: Kind
  text: string
  project: string
  source: string
  age: number | null
  link: string
}

export interface Goal {
  id: string
  name: string
  icon: string
  color: string
  items: Item[]
}

export interface Dataset {
  generated: string
  title: string
  mode: 'public' | 'local'
  total: number
  labels: Record<Kind, string>
  counts: { not_sent: number; decision: number; stale: number }
  goals: Goal[]
}

export const STALE_DAYS = 10

export function isStale(age: number | null): boolean {
  return age !== null && age > STALE_DAYS
}

export function ageText(age: number | null): string {
  if (age === null) return '—'
  if (age === 0) return 'today'
  return `${age}d`
}

/** Status color bucket per kind — mirrors the original template's pill CSS. */
export const KIND_COLOR: Record<Kind, 'block' | 'wait' | 'todo' | 'doing' | 'accent'> = {
  not_sent: 'block',
  gate: 'block',
  decision: 'wait',
  deferred: 'todo',
  parked: 'todo',
  awaiting: 'doing',
  next: 'accent',
  todo: 'accent',
}
