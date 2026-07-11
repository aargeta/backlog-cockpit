import { AnimatePresence, motion } from 'framer-motion'
import { TaskRow } from './TaskRow'
import type { Goal, Item, Kind } from '../types'

interface Props {
  goal: Goal
  items: Item[]
  labels: Record<Kind, string>
  collapsed: boolean
  onToggle: () => void
  index: number
}

export function GoalCard({
  goal,
  items,
  labels,
  collapsed,
  onToggle,
  index,
}: Props) {
  const bodyId = `goal-items-${goal.id}`

  return (
    <motion.section
      layout="position"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.1 + index * 0.07, ease: 'easeOut' }}
      className="overflow-hidden rounded-[15px] border border-line bg-surface shadow-card"
    >
      <button
        type="button"
        aria-expanded={!collapsed}
        aria-controls={bodyId}
        onClick={onToggle}
        className="grid w-full cursor-pointer grid-cols-[auto_1fr_auto] items-center gap-[13px] border-0 bg-transparent px-[17px] py-3.5 text-left text-inherit transition-colors hover:bg-surface-2"
      >
        <span
          aria-hidden
          className="grid size-[34px] place-items-center rounded-[9px] text-[1.05rem]"
          style={{
            background: `color-mix(in srgb, ${goal.color} 15%, transparent)`,
          }}
        >
          {goal.icon}
        </span>
        <h3 className="m-0 text-[1.02rem] font-semibold">{goal.name}</h3>
        <span className="flex items-center gap-3">
          <span className="font-mono text-[0.8rem] text-ink-soft tabular-nums">
            {items.length}
          </span>
          <motion.span
            aria-hidden
            className="text-[0.8rem] text-ink-faint"
            animate={{ rotate: collapsed ? -90 : 0 }}
            transition={{ duration: 0.2 }}
          >
            ▼
          </motion.span>
        </span>
      </button>

      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            id={bodyId}
            key="items"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-line-soft">
              <AnimatePresence initial={false}>
                {items.map((it) => (
                  <TaskRow
                    key={`${it.kind}|${it.text}`}
                    item={it}
                    labels={labels}
                  />
                ))}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  )
}
