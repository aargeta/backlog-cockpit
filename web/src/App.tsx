import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, LayoutGroup, motion } from 'framer-motion'
import { TopBar } from './components/TopBar'
import { FocusTiles } from './components/FocusTiles'
import { FilterChips } from './components/FilterChips'
import { GoalCard } from './components/GoalCard'
import { isStale, type Dataset, type Item, type Kind } from './types'

function matches(item: Item, kind: Kind | null, staleOnly: boolean): boolean {
  if (kind && item.kind !== kind) return false
  if (staleOnly && !isStale(item.age)) return false
  return true
}

export default function App() {
  const [data, setData] = useState<Dataset | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [kindFilter, setKindFilter] = useState<Kind | null>(null)
  const [staleOnly, setStaleOnly] = useState(false)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetch('/data.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<Dataset>
      })
      .then(setData)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : String(e)),
      )
  }, [])

  const visibleGoals = useMemo(() => {
    if (!data) return []
    return data.goals
      .map((g) => ({
        goal: g,
        items: g.items
          .filter((it) => matches(it, kindFilter, staleOnly))
          .sort(
            (a, b) =>
              b.priority - a.priority || (b.age ?? -1) - (a.age ?? -1),
          ),
      }))
      .filter((g) => g.items.length > 0)
  }, [data, kindFilter, staleOnly])

  if (error) {
    return (
      <div className="mx-auto max-w-[1080px] p-[22px]">
        <div className="rounded-xl border border-dashed border-line bg-surface-2 px-[15px] py-[13px] text-[0.82rem] text-ink-soft">
          Could not load <code className="font-mono">data.json</code> ({error}
          ). Run the harvester to generate it.
        </div>
      </div>
    )
  }
  if (!data) return null

  const allCollapsed =
    visibleGoals.length > 0 &&
    visibleGoals.every(({ goal }) => collapsed.has(goal.id))

  const toggleAll = () =>
    setCollapsed(
      allCollapsed ? new Set() : new Set(data.goals.map((g) => g.id)),
    )

  const toggleGoal = (id: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <>
      <TopBar data={data} allCollapsed={allCollapsed} onToggleAll={toggleAll} />

      <main className="mx-auto max-w-[1080px] p-[22px]">
        <div>
          <h1 className="m-0 text-2xl font-bold tracking-[-0.01em]">
            Everything that&rsquo;s still open.
          </h1>
          <p className="mt-0.5 mb-0 text-[0.9rem] text-ink-soft">
            {data.mode === 'public'
              ? 'Redacted view — safe to share. Full detail lives on your machine.'
              : 'Harvested from your notes. Stalest first. Nothing left this machine.'}
          </p>
        </div>

        <FocusTiles data={data} />

        <FilterChips
          labels={data.labels}
          kindFilter={kindFilter}
          staleOnly={staleOnly}
          onKind={setKindFilter}
          onStale={() => setStaleOnly((s) => !s)}
        />

        <p className="mb-3 font-mono text-[0.7rem] uppercase tracking-[0.13em] text-ink-faint">
          By goal · highest priority on top
        </p>

        <LayoutGroup>
          <div className="flex flex-col gap-[13px]">
            <AnimatePresence initial={false} mode="popLayout">
              {visibleGoals.map(({ goal, items }, i) => (
                <GoalCard
                  key={goal.id}
                  goal={goal}
                  items={items}
                  labels={data.labels}
                  collapsed={collapsed.has(goal.id)}
                  onToggle={() => toggleGoal(goal.id)}
                  index={i}
                />
              ))}
            </AnimatePresence>
            {visibleGoals.length === 0 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="rounded-xl border border-dashed border-line bg-surface-2 px-[15px] py-[13px] text-[0.82rem] text-ink-soft"
              >
                Nothing matches this filter.
              </motion.div>
            )}
          </div>
        </LayoutGroup>

        <div className="mt-5 rounded-xl border border-dashed border-line bg-surface-2 px-[15px] py-[13px] text-[0.82rem] text-ink-soft">
          Click an item&rsquo;s <b>↗</b> to open a Claude session that pulls
          the note and works it. Re-run <code className="font-mono">harvest.py</code>{' '}
          to refresh. Wrong bucket or noisy line? Markers &amp; routing are all
          in your config.
        </div>
      </main>

      <footer className="mx-auto max-w-[1080px] px-[22px] pb-10 pt-4 font-mono text-[0.7rem] leading-[1.7] text-ink-faint">
        {data.mode === 'public'
          ? 'Redacted build · numbers, paths, emails & your term list stripped.'
          : 'Local build · full detail · never published.'}
      </footer>
    </>
  )
}
