# Backlog Cockpit — Web

React version of the Backlog Cockpit dashboard. Vite + React + TypeScript +
Tailwind CSS v4 + framer-motion. Built to be hosted on Cloudflare Pages.

## Run

```sh
npm install
npm run dev      # dev server with HMR
npm run build    # type-check + production build -> dist/
npm run preview  # serve the built dist/ locally
```

## Data

The app fetches `/data.json` at runtime. A **synthetic sample** dataset ships
in `public/data.json` so the app renders out of the box — none of it is real.

### Wiring real data

Today the Python harvester (`../harvest.py`) renders a self-contained
`public/index.html` by injecting a JSON blob into an HTML template
(`write_html` replaces `/*DATA*/` with `json.dumps(data)`).

For this React app the integration point is simpler: have the harvester emit
the **same dataset object as plain JSON** instead of (or in addition to) the
HTML, e.g.:

```python
def write_json(data, out_path):
    open(out_path, "w", encoding="utf-8").write(json.dumps(data))

# public/redacted build -> web/public/data.json  (dev)
# or -> web/dist/data.json after `npm run build` (deploy artifact)
```

The shape is unchanged from what the template already consumes:

```jsonc
{
  "generated": "YYYY-MM-DD",
  "title": "Backlog Cockpit",
  "mode": "public" | "local",
  "total": 15,
  "labels": { "not_sent": "Not sent", /* ... one per kind ... */ },
  "counts": { "not_sent": 2, "decision": 3, "stale": 5 },
  "goals": [
    { "id": "win", "name": "Win work", "icon": "🎯", "color": "#a2641b",
      "items": [
        { "kind": "not_sent", "text": "...", "project": "...",
          "source": "vault-project", "age": 12, "link": "https://..." }
      ] }
  ]
}
```

Only the redacted/**public** dataset should ever be written into this app for
deployment; the local full-detail build stays on the machine.

## Deploy (Cloudflare Pages)

Build command `npm run build`, output directory `dist`, root directory `web`.
Drop the freshly harvested `data.json` into `dist/` (or `public/` before
building) as part of the publish step.

## Structure

```
src/
  App.tsx                 data load, filter state, layout
  types.ts                dataset types, kind→status-color map, age helpers
  index.css               design tokens (light/dark) + Tailwind theme mapping
  hooks/useTheme.ts       data-theme on <html>, localStorage persistence
  hooks/useCountUp.ts     stat count-up (respects reduced motion)
  components/TopBar.tsx   brand, mode pill, collapse-all, theme toggle
  components/FocusTiles.tsx  4 stat tiles with accent stripes
  components/FilterChips.tsx kind filter + stale-only toggle
  components/GoalCard.tsx    collapsible goal card
  components/TaskRow.tsx     kind pill · text/meta · age · open link
```

Animations are disabled automatically under `prefers-reduced-motion`
(`MotionConfig reducedMotion="user"` plus a check in the count-up hook).
