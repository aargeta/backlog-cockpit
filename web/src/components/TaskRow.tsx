import { motion } from 'framer-motion'
import { KIND_COLOR, ageText, isStale, type Item, type Kind } from '../types'

interface Props {
  item: Item
  labels: Record<Kind, string>
}

export function TaskRow({ item, labels }: Props) {
  const c = KIND_COLOR[item.kind]
  const stale = isStale(item.age)

  return (
    <motion.div
      layout
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      className="grid grid-cols-[auto_1fr_auto_auto] items-start gap-[11px] border-b border-line-soft px-[17px] py-2.5 transition-colors last:border-b-0 hover:bg-surface-2"
    >
      <span
        className="mt-px min-w-[74px] whitespace-nowrap rounded-full px-[7px] py-[3px] text-center font-mono text-[0.6rem] font-bold uppercase tracking-[0.03em]"
        style={{
          color: `var(--${c})`,
          background: `color-mix(in srgb, var(--${c}) 14%, transparent)`,
        }}
      >
        {labels[item.kind]}
      </span>
      <div className="min-w-0 text-[0.88rem]">
        {item.text}
        <div className="mt-0.5 font-mono text-[0.7rem] text-ink-faint">
          {item.project} · {item.source}
        </div>
      </div>
      <span
        className={`mt-px whitespace-nowrap text-right font-mono text-[0.72rem] tabular-nums ${
          stale ? 'font-bold text-block' : 'text-ink-faint'
        }`}
      >
        {ageText(item.age)}
      </span>
      <a
        href={item.link}
        target="_blank"
        rel="noopener noreferrer"
        title="Open in Claude"
        aria-label={`Open "${item.text}" in Claude`}
        className="grid h-7 w-[30px] place-items-center rounded-lg border border-line bg-surface text-[0.9rem] text-ink-soft no-underline transition-colors hover:border-accent hover:text-accent"
      >
        ↗
      </a>
    </motion.div>
  )
}
