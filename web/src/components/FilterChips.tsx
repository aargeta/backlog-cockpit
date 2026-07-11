import type { Kind } from '../types'

interface Props {
  labels: Record<Kind, string>
  kindFilter: Kind | null
  staleOnly: boolean
  onKind: (k: Kind | null) => void
  onStale: () => void
}

function Chip({
  pressed,
  onClick,
  children,
}: {
  pressed: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={`cursor-pointer rounded-full border px-3 py-[5px] font-mono text-[0.75rem] transition-colors ${
        pressed
          ? 'border-accent bg-accent text-white'
          : 'border-line bg-surface text-ink-soft hover:border-accent hover:text-ink'
      }`}
    >
      {children}
    </button>
  )
}

export function FilterChips({
  labels,
  kindFilter,
  staleOnly,
  onKind,
  onStale,
}: Props) {
  return (
    <div className="mb-[18px] mt-1.5 flex flex-wrap items-center gap-[7px]">
      <Chip pressed={kindFilter === null} onClick={() => onKind(null)}>
        All kinds
      </Chip>
      {(Object.keys(labels) as Kind[]).map((k) => (
        <Chip
          key={k}
          pressed={kindFilter === k}
          onClick={() => onKind(kindFilter === k ? null : k)}
        >
          {labels[k]}
        </Chip>
      ))}
      <span className="flex-1" />
      <Chip pressed={staleOnly} onClick={onStale}>
        Stale &gt; 10d only
      </Chip>
    </div>
  )
}
