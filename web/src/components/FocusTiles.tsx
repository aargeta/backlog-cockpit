import { motion } from 'framer-motion'
import { useCountUp } from '../hooks/useCountUp'
import type { Dataset } from '../types'

interface Tile {
  n: number
  label: string
  colorVar: string
}

function StatTile({ tile, index }: { tile: Tile; index: number }) {
  const value = useCountUp(tile.n)
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06, ease: 'easeOut' }}
      className="relative overflow-hidden rounded-[13px] border border-line bg-surface px-3.5 py-[13px] shadow-card"
    >
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-1"
        style={{ background: tile.colorVar }}
      />
      <div className="text-[1.7rem] font-bold leading-none tabular-nums">
        {value}
      </div>
      <div className="mt-[7px] font-mono text-[0.64rem] uppercase tracking-[0.03em] text-ink-faint">
        {tile.label}
      </div>
    </motion.div>
  )
}

export function FocusTiles({ data }: { data: Dataset }) {
  const tiles: Tile[] = [
    { n: data.total, label: 'Open threads', colorVar: 'var(--accent)' },
    { n: data.counts.high, label: 'High priority', colorVar: 'var(--block)' },
    { n: data.counts.not_sent, label: 'Not sent', colorVar: 'var(--wait)' },
    { n: data.counts.stale, label: 'Stale > 10 days', colorVar: 'var(--todo)' },
  ]
  return (
    <div className="my-4 mb-[18px] grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 min-[820px]:grid-cols-4">
      {tiles.map((t, i) => (
        <StatTile key={t.label} tile={t} index={i} />
      ))}
    </div>
  )
}
