import { useTheme } from '../hooks/useTheme'
import type { Dataset } from '../types'

interface Props {
  data: Dataset
  allCollapsed: boolean
  onToggleAll: () => void
}

const ghost =
  'rounded-[9px] border border-line bg-surface px-3 py-[7px] font-mono text-[0.76rem] text-ink-soft transition-colors hover:border-accent hover:text-ink cursor-pointer'

export function TopBar({ data, allCollapsed, onToggleAll }: Props) {
  const [theme, toggleTheme] = useTheme()

  return (
    <header className="sticky top-0 z-10 border-b border-line-soft bg-paper/85 backdrop-blur-lg">
      <div className="mx-auto flex h-[58px] max-w-[1080px] items-center justify-between gap-3.5 px-[22px]">
        <div className="flex min-w-0 items-center gap-2.5 font-bold">
          <span
            aria-hidden
            className="grid size-[22px] shrink-0 place-items-center rounded-md bg-gradient-to-br from-accent to-accent-soft font-mono text-[0.7rem] font-extrabold text-white"
          >
            BC
          </span>
          <span className="truncate">{data.title}</span>
          <span className="hidden font-mono text-[0.72rem] font-medium text-ink-faint tabular-nums sm:inline">
            · {data.total} open · {data.generated}
          </span>
          <span
            className={`rounded-full border border-line px-2 py-[3px] font-mono text-[0.62rem] uppercase tracking-[0.05em] ${
              data.mode === 'local' ? 'text-block' : 'text-doing'
            }`}
          >
            {data.mode}
          </span>
        </div>
        <div className="flex shrink-0 gap-2">
          <button type="button" className={ghost} onClick={onToggleAll}>
            {allCollapsed ? 'Expand all' : 'Collapse all'}
          </button>
          <button
            type="button"
            className={ghost}
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {theme === 'dark' ? '☀ Light' : '☾ Dark'}
          </button>
        </div>
      </div>
    </header>
  )
}
