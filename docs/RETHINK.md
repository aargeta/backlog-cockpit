# Structure, UI/UX & design-asset rethink

A working note on where this goes next, and which of the researched libraries actually earn a place.

## Architecture (the clean shape)

```
notes (Obsidian / Markdown)                 [your machines — full detail, local only]
   │  harvest.py  (line-based marker harvest, config-driven)
   ▼
dataset  ──► LOCAL build  : cockpit.local.html  (full prose)      → your machines only
         └─► PUBLIC build : data.json + React app                 → Cloudflare Pages + Access
                              modes: denylist (masked)  |  structural (no prose)
```

Three clean stages — **harvest → transform (redact/mode) → render** — so the render can move to
React without touching the harvest logic. The Python engine stays the single source of extraction;
it just emits `data.json` for the React app instead of (or in addition to) the self-contained HTML.

- **Cross-machine:** same repo on both machines; each has its own `config.local.json` with local
  paths. Obsidian already syncs the vault, so both harvest the same projects.
- **Hosting:** deploy the React `dist/` (built against the public `data.json`) to Cloudflare Pages,
  Cloudflare Access in front. The Python harvester runs locally/scheduled and writes the public
  `data.json` the deploy consumes.
- **Phase 2 (mobile file-pull):** a small read-only vault MCP as a Cloudflare Worker behind Access,
  so click-to-Claude on your phone can open the actual note (desktop Claude Code already can).

## UI/UX direction

The current design is right for what this is: a **utility that gets scanned and operated**, not a
page that gets admired. Keep the discipline — clarity and information density over spectacle,
summary-before-detail (focus tiles → goals → items), state encoded in form (kind pills, staleness
color), one ochre accent, semantic status colors kept separate from it, light+dark.

Already in the React build: count-up on the stat tiles, staggered card entrance, animated
collapse, live filtering, reduced-motion support, full keyboard/focus a11y.

Worth adding next (in rough priority):
1. **A "today / focus" mode** — collapse to only stale + decision + not-sent. A few-hundred-item
   firehose is honest but daunting; the value is the *slice*.
2. **Staleness + kind mini-charts** (see Bklit below) — a small "where is the pressure" strip.
3. **Command palette** (`/` to filter, jump to goal) — power-user speed without more chrome.
4. **Saved views** (localStorage) — "my morning filter" persists.

## Design-asset map (the researched GitHubs — where each fits, and where it doesn't)

| Library | Verdict for this app | Why |
|---|---|---|
| **motion.dev** (framer-motion) | ✅ **In use** | The correct animation layer for a React dashboard — entrance, layout, count-up, collapse. Tasteful, gated by reduced-motion. |
| **Bklit UI** | ✅ **Recommended next** | It's a charts/data-viz kit. This is a *data* dashboard — a staleness histogram, a kind-breakdown ring, an open-threads-over-time line all belong here. The one library that adds real capability, not decoration. |
| **Kokonut UI** | ◐ Shell only | Great for a **landing/login page** for the OSS project (it's open source now) — hero, pricing-style feature grid. Not for the dashboard interior. |
| **liquid-glass-js** | ◐ Sparingly | At most a single glass top-bar. Never glass *behind* the data — it hurts legibility on the surface people read all day. Optional flourish, not core. |
| **ShaderGradient** | ✗ Not here | Ambient WebGL gradient = promo/marketing-surface material, not a utility people open on a phone in the field. Perf + battery + clarity all say no. |
| **react-three-fiber** | ✗ Not here | Real 3D has no job in a backlog list. Reserve it for a domain viewer where 3D *is* the data. |
| **liquid-logo** | ✗ Not here | A brand moment for a studio site, not a work tool. |
| **anime.js** | ✗ Superseded | Framework-agnostic animation for static HTML; in React, motion.dev is the pick. (Still the right tool for the *self-contained HTML* build if that stays around.) |

**Principle:** spend the "wow" budget on the promo surfaces; spend the *craft* budget here on
typography, spacing, motion-on-state-change, and the data-viz layer. A dashboard earns trust by
being fast and legible, not flashy.

## Security posture (carry this forward)

The hosted build's real boundary is **Cloudflare Access (identity)**. Redaction is defense-in-depth:
`denylist` mode is best-effort and *will* miss tokens it hasn't been taught (proven in testing —
org names, permit-number formats, path fragments all leaked until patched); `structural` mode is
provably safe because it publishes no prose. Rule of thumb: **denylist behind Access, or structural
anywhere.** The click-to-Claude link is a deliberate outbound channel (redacted text → claude.ai
URL); it carries only the note basename, never the full local path.
